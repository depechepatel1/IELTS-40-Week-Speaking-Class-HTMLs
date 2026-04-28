/* === IELTS Interactive AI Correction — injected JS block === */
(function () {
  'use strict';

  // Substituted by make_interactive.py at build time.
  const AI_ENDPOINT = "__AI_ENDPOINT__";
  const PRONUNCIATIONS_URL = "__PRONUNCIATIONS_URL__";
  const LESSON_KEY = "__LESSON_KEY__"; // e.g. "Week_1_Lesson_Plan"

  const ns = (window.__ielts = window.__ielts || {});

  // ====================================================================
  // TTS subsystem — Web Speech API with voice waterfall + karaoke
  // ====================================================================

  // Common female-neural voice names across Edge/Chrome (Windows), Safari/iOS,
  // and Android system voices. The regex covers both modern Edge "Natural"
  // voices and legacy macOS / iOS / Android voices known to sound natural.
  const FEMALE_NEURAL_UK = /Sonia|Libby|Mia|Maisie|Kate|Serena|Sienna|Tessa|Karen|Hazel|Susan|Stephanie/i;
  const MALE_NEURAL_UK   = /Ryan|Thomas.*GB|Noah|Daniel|George|Oliver/i;
  const FEMALE_NEURAL_US = /Aria|Jenny|Ana|Michelle|Emma|Samantha|Allison|Ava|Joanna|Salli|Kendra|Kimberly|Ivy|Nora|Susan.*US|Zira/i;
  const MALE_NEURAL_US   = /Guy|Tony|Jason|Eric|Davis|Alex|Aaron|Brandon|Steffan|Roger/i;

  // Speech rates. Tuned for Chinese L2 listeners — 0.85 is the comfortable
  // default (matches what was previously the "slow" button rate); 0.72 is
  // the new "slow" — about 15% slower than the new default, useful when a
  // student wants to copy pronunciation word-by-word.
  const DEFAULT_RATE = 0.85;
  const SLOW_RATE    = 0.72;

  // ====================================================================
  // AI fetch — jitter + exponential backoff retry
  // ====================================================================
  // Designed for the start-of-class scenario: 200 students click "Correct
  // with AI" within the same second. Without intervention, the FC instance
  // pool (default ~100 concurrent) queues half the requests and Zhipu's
  // rate limiter rejects the herd. With this helper:
  //   - Pre-request jitter (0..500ms) spreads the herd across half a second,
  //     enough to fit under typical FC concurrency caps.
  //   - On 429/503/5xx or network error, retry with exponential backoff
  //     (1s, 2s, 4s) plus per-retry jitter so retries don't re-stampede.
  //   - Per-attempt AbortController timeout (45s) prevents a hung TCP
  //     connection from leaving the user stuck on an infinite spinner.
  //   - Max 3 attempts total — beyond that, we surface the error to the
  //     user rather than retry forever (Zhipu rarely recovers within 10s+
  //     and the student would rather know).
  const AI_FETCH_MAX_ATTEMPTS = 3;
  const AI_FETCH_BASE_BACKOFF_MS = 1000;
  const AI_FETCH_JITTER_MS = 500;
  const AI_FETCH_TIMEOUT_MS = 45000;

  function _aiSleep(ms) { return new Promise(r => setTimeout(r, ms)); }
  function _aiJitter() { return Math.floor(Math.random() * AI_FETCH_JITTER_MS); }

  async function aiCorrectFetchWithRetry(draftText) {
    let lastErr = null;
    // Pre-request jitter — spreads the start-of-class herd.
    await _aiSleep(_aiJitter());

    for (let attempt = 0; attempt < AI_FETCH_MAX_ATTEMPTS; attempt++) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), AI_FETCH_TIMEOUT_MS);
      try {
        const resp = await fetch(AI_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ draft: draftText }),
          signal: ctrl.signal,
        });
        clearTimeout(timer);
        // Treat 429 (Zhipu / FC rate-limited), 503 (FC saturated), and any
        // 5xx as retriable. 4xx other than 429 are NOT retried — they
        // indicate a client-side problem (bad input, missing field, etc.)
        // that won't fix itself by waiting.
        if (resp.status === 429 || resp.status === 503 || resp.status >= 500) {
          lastErr = new Error(`server ${resp.status}`);
          // fall through to backoff
        } else {
          return resp;  // success or non-retriable error — caller handles body
        }
      } catch (e) {
        clearTimeout(timer);
        lastErr = e;
        // Network errors (DNS, TLS, abort) are retriable.
      }
      // Exponential backoff with jitter: 1s, 2s, 4s + 0-500ms each.
      const backoff = AI_FETCH_BASE_BACKOFF_MS * Math.pow(2, attempt) + _aiJitter();
      if (attempt < AI_FETCH_MAX_ATTEMPTS - 1) await _aiSleep(backoff);
    }
    throw lastErr || new Error('AI fetch failed after retries');
  }

  // Score-based picker: prefers high-quality engines (Edge "Online (Natural)",
  // Google network voices, macOS Premium/Enhanced) over legacy local voices.
  // Without scoring, browsers like Chrome on Windows often surface the older
  // "Microsoft Hazel" (low-quality concatenative) ahead of "Microsoft Sonia
  // Online (Natural)" — and Array.find() would return Hazel even though both
  // names match the female regex.
  function pickVoice(lang) {
    if (!('speechSynthesis' in window)) return null;
    const all = window.speechSynthesis.getVoices();
    if (!all.length) return null;

    const langPrefix = lang === 'en-GB' ? 'en-GB' : 'en-US';
    let pool = all.filter(v => v.lang === langPrefix);
    if (!pool.length) pool = all.filter(v => v.lang && v.lang.startsWith('en'));
    if (!pool.length) return all[0];

    const female = lang === 'en-GB' ? FEMALE_NEURAL_UK : FEMALE_NEURAL_US;
    const male   = lang === 'en-GB' ? MALE_NEURAL_UK   : MALE_NEURAL_US;

    const score = (v) => {
      const tag = (v.name || '') + ' ' + (v.voiceURI || '');
      let s = 0;
      if (/Natural/i.test(tag))           s += 100;  // Edge neural voices (best)
      if (/Online/i.test(tag))            s +=  80;  // Microsoft cloud voices
      if (/Google/i.test(tag))            s +=  60;  // Google network voices
      if (/Premium|Enhanced/i.test(tag))  s +=  50;  // macOS / iOS premium
      if (!v.localService)                s +=  30;  // network > local generally
      if (female.test(v.name))            s +=  25;  // female preference
      else if (male.test(v.name))         s +=   5;  // male as fallback
      if (v.lang === langPrefix)          s +=  10;  // exact lang > prefix match
      return s;
    };

    return pool.slice().sort((a, b) => score(b) - score(a))[0];
  }

  function isWeChatBrowser() {
    return /MicroMessenger/i.test(navigator.userAgent || '');
  }

  function wechatFallbackAlert() {
    alert("微信浏览器不支持语音播放，请用 Safari 或 Chrome 打开本页 / WeChat browser doesn't support audio playback. Please open this page in Safari or Chrome.");
  }

  // === Sentence-paced TTS state ============================================
  //
  // Pedagogical model: TTS plays ONE sentence at a time and auto-pauses on
  // completion. Students press transport buttons (Replay / Prev / Next /
  // Slow) to advance, repeat, or slow-down the current sentence. This is
  // the standard listen-and-repeat shadowing flow used in language classes.
  //
  // Per-row state (sentence list + index + accent + karaoke spans) is kept
  // in a WeakMap keyed by the .listen-row DOM element. Multiple rows on
  // the same page each retain their own independent state — pressing Next
  // on row A and then returning to row B picks up where row B left off.
  //
  // _currentRow is the SINGLE row producing audio right now (only one mic
  // can play at a time across the whole page). It's just a pointer to
  // whichever WeakMap entry owns the in-flight utterance.

  const _rowState = new WeakMap();
  let   _currentRow = null;

  function getRowState(rowEl) {
    if (!rowEl) return null;
    let s = _rowState.get(rowEl);
    if (!s) {
      s = {
        sentences:    [],          // string[] — one entry per sentence
        sourceText:   '',          // original full text, pre-normalize
        currentIndex: 0,           // 0-based index into sentences
        lang:         'en-GB',     // 'en-GB' | 'en-US' — last-selected accent
        rate:         DEFAULT_RATE,// inherited from initial play; overridden by 🐢
        // Karaoke (only populated for sentence-paced playback over an
        // element that's been word-wrapped, e.g. #polished-output):
        targetEl:     null,
        spans:        null,
        offsets:      null,        // [{ span, start, end }] over wrappedText
        wrappedText:  null,        // the text snapshot that spans correspond to
      };
      _rowState.set(rowEl, s);
    }
    return s;
  }

  // Char index where sentence i begins in the joined source. Trimmed
  // sentences plus single-space joins matches the normalize() output of
  // splitSentences(), so karaoke offsets line up.
  function sentenceCharStart(sentences, i) {
    let n = 0;
    for (let k = 0; k < i; k++) n += sentences[k].length + 1;
    return n;
  }

  /** Pragmatic sentence splitter — punctuation lookbehind + capital
   *  lookahead. Imperfect on abbreviations like "Mr. Smith" or "U.S.A."
   *  but the IELTS / IGCSE model-answer corpus rarely uses them. */
  function splitSentences(text) {
    const norm = String(text || '').replace(/\s+/g, ' ').trim();
    if (!norm) return [];
    return norm
      .split(/(?<=[.!?])\s+(?=[A-Z"'(])/)
      .map(s => s.trim())
      .filter(Boolean);
  }
  ns.__splitSentences = splitSentences;  // exposed for tests

  /** Mark a single .listen-row as the one currently speaking (for the
   *  pulsing indicator). Pass `null` to clear. */
  function setSpeakingRow(rowEl) {
    document.querySelectorAll('.listen-row.speaking-now, .button-row.speaking-now')
      .forEach(r => r.classList.remove('speaking-now'));
    if (rowEl) rowEl.classList.add('speaking-now');
  }

  /** Sync transport-button enabled state + sentence counter for a row. */
  function updateTransportButtons(rowEl) {
    if (!rowEl) return;
    const st = getRowState(rowEl);
    const total = st.sentences ? st.sentences.length : 0;
    const idx   = st.currentIndex || 0;
    const prev   = rowEl.querySelector('.tts-btn.prev');
    const next   = rowEl.querySelector('.tts-btn.next');
    const slow   = rowEl.querySelector('.tts-btn.slow');
    const replay = rowEl.querySelector('.tts-btn.replay');
    const counter = rowEl.querySelector('.sentence-counter');
    if (slow)   slow.disabled   = (total === 0);
    if (replay) replay.disabled = (total === 0);
    if (prev)   prev.disabled   = (idx <= 0 || total === 0);
    if (next)   next.disabled   = (idx + 1 >= total || total === 0);
    if (counter) counter.textContent = total > 0 ? `${idx + 1}/${total}` : '';
  }

  function setActiveAccent(rowEl, lang) {
    if (!rowEl) return;
    rowEl.querySelectorAll('.tts-btn.uk, .tts-btn.us').forEach(b => b.classList.remove('active'));
    const sel = lang === 'en-US' ? '.tts-btn.us' : '.tts-btn.uk';
    const btn = rowEl.querySelector(sel);
    if (btn) btn.classList.add('active');
  }

  /** Internal: speak the current sentence of the row. On end, do NOT
   *  advance — the student decides what comes next. */
  function _playCurrentSentence(rowEl, rateOverride) {
    if (!rowEl) return;
    const st = getRowState(rowEl);
    if (!st.sentences || !st.sentences.length) return;
    if (st.currentIndex < 0) st.currentIndex = 0;
    if (st.currentIndex >= st.sentences.length) return;

    if ('speechSynthesis' in window) speechSynthesis.cancel();
    _currentRow = rowEl;
    setSpeakingRow(rowEl);

    const sentence      = st.sentences[st.currentIndex];
    const sentenceStart = sentenceCharStart(st.sentences, st.currentIndex);

    const u = new SpeechSynthesisUtterance(sentence);
    u.lang = st.lang;
    u.rate = rateOverride || st.rate || DEFAULT_RATE;
    const v = pickVoice(st.lang);
    if (v) u.voice = v;

    // Karaoke: only when this row owns word-wrapped spans (polished-output path).
    const activeOffsets = (st.spans && st.offsets)
      ? st.offsets.filter(o => o.start >= sentenceStart && o.end <= sentenceStart + sentence.length)
      : null;

    u.onstart = () => setSpeakingRow(rowEl);
    u.onboundary = (ev) => {
      if (ev.name && ev.name !== 'word') return;
      if (!activeOffsets) return;
      activeOffsets.forEach(o => o.span.classList.remove('speaking'));
      const globalIdx = sentenceStart + ev.charIndex;
      const hit = activeOffsets.find(o => globalIdx >= o.start && globalIdx < o.end);
      if (hit) hit.span.classList.add('speaking');
    };
    u.onend = () => {
      if (activeOffsets) activeOffsets.forEach(o => o.span.classList.remove('speaking'));
      // Auto-pause: leave currentIndex where it is; clear pulse; refresh buttons.
      if (_currentRow === rowEl) _currentRow = null;
      setSpeakingRow(null);
      updateTransportButtons(rowEl);
    };

    speechSynthesis.speak(u);
    updateTransportButtons(rowEl);
  }

  ns.speakText = function (text, lang = 'en-GB', rate = DEFAULT_RATE, rowEl = null) {
    if (isWeChatBrowser()) { wechatFallbackAlert(); return; }
    if (!('speechSynthesis' in window)) return;
    if (!text || !String(text).trim()) return;

    // No row → vocab-click / single-shot path. Speak as one utterance,
    // no sentence pacing, no row state. Matches old behaviour for
    // attachWordClicks().
    if (!rowEl) {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text));
      u.lang = lang;
      u.rate = rate;
      const v = pickVoice(lang);
      if (v) u.voice = v;
      speechSynthesis.speak(u);
      return;
    }

    // Row-bound → split into sentences, store state, play sentence 0.
    const st = getRowState(rowEl);
    st.sentences   = splitSentences(text);
    st.sourceText  = String(text);
    st.currentIndex = 0;
    st.lang  = lang;
    st.rate  = rate || DEFAULT_RATE;
    st.targetEl    = null;
    st.spans       = null;
    st.offsets     = null;
    st.wrappedText = null;
    setActiveAccent(rowEl, lang);
    _playCurrentSentence(rowEl);
  };

  /** Replay the current sentence. `slow=true` → SLOW_RATE for this one
   *  utterance only; the row's stored rate is unchanged. */
  ns.replaySentence = function (rowEl, slow) {
    if (!rowEl) return;
    const st = getRowState(rowEl);
    if (!st.sentences || !st.sentences.length) return;
    _playCurrentSentence(rowEl, slow ? SLOW_RATE : st.rate);
  };

  ns.nextSentence = function (rowEl) {
    if (!rowEl) return;
    const st = getRowState(rowEl);
    if (!st.sentences || st.currentIndex + 1 >= st.sentences.length) return;
    st.currentIndex++;
    _playCurrentSentence(rowEl);
  };

  ns.prevSentence = function (rowEl) {
    if (!rowEl) return;
    const st = getRowState(rowEl);
    if (!st.sentences || st.currentIndex <= 0) return;
    st.currentIndex--;
    _playCurrentSentence(rowEl);
  };

  // speakElement / speakElementById — wrap words in <span> for karaoke,
  // split text into sentences, and play sentence 0. Subsequent transport
  // commands (replay / next / prev / slow) re-use the wrapped spans.
  ns.speakElement = function (el, lang = 'en-GB', rate = DEFAULT_RATE) {
    if (isWeChatBrowser()) { wechatFallbackAlert(); return; }
    if (!('speechSynthesis' in window)) return;
    if (!el) return;
    const text = el.textContent.trim();
    if (!text) return;

    // The polished overlay's listen-row is the natural row for el.id === 'polished-output'.
    // For other elements, fall back to a synthetic row state keyed off the element itself
    // (the element doubles as the WeakMap key — same lifecycle).
    const rowEl = (el.id === 'polished-output')
      ? document.getElementById('polished-listen-row')
      : el;

    const st = getRowState(rowEl);

    // Re-wrap only if text changed (e.g. after a fresh AI correction).
    if (st.wrappedText !== text) {
      const tokens = text.split(/(\s+)/);
      el.innerHTML = '';
      const spans = [];
      const offsets = [];
      let charIdx = 0;
      tokens.forEach(tok => {
        if (/^\s+$/.test(tok)) {
          el.appendChild(document.createTextNode(tok));
        } else if (tok.length) {
          const s = document.createElement('span');
          s.textContent = tok;
          offsets.push({ span: s, start: charIdx, end: charIdx + tok.length });
          spans.push(s);
          el.appendChild(s);
        }
        charIdx += tok.length;
      });
      st.wrappedText = text;
      st.spans = spans;
      st.offsets = offsets;
      st.sentences = splitSentences(text);
    } else {
      // Same text — just re-split in case the splitter logic was upgraded.
      st.sentences = splitSentences(text);
    }
    st.sourceText  = text;
    st.targetEl    = el;
    st.currentIndex = 0;
    st.lang = lang;
    st.rate = rate || DEFAULT_RATE;
    setActiveAccent(rowEl, lang);
    _playCurrentSentence(rowEl);
  };

  ns.speakElementById = function (id, lang = 'en-GB', rate = DEFAULT_RATE) {
    const el = document.getElementById(id);
    if (el) ns.speakElement(el, lang, rate);
  };

  /** Polished-output button router. Six modes: en-GB / en-US (start over
   *  in chosen accent), slow / replay (re-speak current sentence), prev /
   *  next (sentence navigation). */
  ns.listenPolished = function (which) {
    const row = document.getElementById('polished-listen-row');
    if (!row) return;
    switch (which) {
      case 'en-GB':
      case 'en-US':
        ns.speakElementById('polished-output', which, DEFAULT_RATE);
        break;
      case 'slow':   ns.replaySentence(row, true);  break;
      case 'replay': ns.replaySentence(row, false); break;
      case 'prev':   ns.prevSentence(row);          break;
      case 'next':   ns.nextSentence(row);          break;
    }
  };

  // Compat stubs — nothing in the new UI calls these, but preserving them
  // keeps any older injected snippet, browser-extension shortcut, or
  // user script from throwing if it references the old API.
  ns.stopSpeaking = function () {
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    document.querySelectorAll('.speaking').forEach(s => s.classList.remove('speaking'));
    _currentRow = null;
    setSpeakingRow(null);
  };
  ns.pauseSpeaking = function () {
    // No-op in sentence-paced mode (sentences auto-pause). Provided for
    // backwards compatibility with anything that still references it.
    ns.stopSpeaking();
  };

  // Voice list loads asynchronously on Chrome. Touching it here primes the cache
  // so the first user click already has voices available.
  if ('speechSynthesis' in window) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => { /* lazy refresh on demand */ };
  }

  // ====================================================================
  // Word count + traffic light  (spec §8.3)
  // ====================================================================

  ns.updateWordCount = function () {
    const draft = document.getElementById('student-draft');
    const span = document.getElementById('word-count');
    if (!draft || !span) return;
    const n = draft.value.trim().split(/\s+/).filter(Boolean).length;
    span.textContent = `${n} / 50–300`;
    span.classList.remove('short', 'ok', 'long');
    if (n < 50) span.classList.add('short');
    else if (n <= 300) span.classList.add('ok');
    else span.classList.add('long');
  };

  // ====================================================================
  // localStorage persistence  (spec §8.6)
  // ====================================================================

  const STORAGE_KEY = `ielts:draft:${LESSON_KEY}`;
  let _saveTimer = null;

  function saveDraft() {
    const draft = document.getElementById('student-draft');
    const polished = document.getElementById('polished-output');
    const markup = document.getElementById('draft-markup');
    if (!draft) return;
    const payload = {
      draft: draft.value,
      polished: polished && !polished.classList.contains('empty') ? polished.textContent : '',
      markupHtml: markup && !markup.hidden ? markup.innerHTML : '',
      timestamp: Date.now()
    };
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(payload)); }
    catch { /* quota exceeded — silently ignore */ }
  }

  function loadDraft() {
    let payload = null;
    try { payload = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); }
    catch { /* corrupt entry — fall through */ }
    if (!payload) return;

    const draft = document.getElementById('student-draft');
    const polished = document.getElementById('polished-output');
    const markup = document.getElementById('draft-markup');
    const correctBtn = document.getElementById('correct-btn');
    const editBtn = document.getElementById('edit-again-btn');

    if (draft) draft.value = payload.draft || '';

    if (payload.polished && polished) {
      polished.classList.remove('empty');
      polished.textContent = payload.polished;
      enablePolishedListenButtons();
    }
    if (payload.markupHtml && markup) {
      markup.innerHTML = payload.markupHtml;
      markup.hidden = false;
      if (draft) draft.style.display = 'none';
      if (correctBtn) correctBtn.hidden = true;
      if (editBtn) editBtn.hidden = false;
    }
    ns.updateWordCount();
  }

  function debouncedSave() {
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(saveDraft, 500);
  }

  ns.clearDraft = function () {
    if (!confirm("清除草稿？/ Clear draft?")) return;
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
    const draft = document.getElementById('student-draft');
    const polished = document.getElementById('polished-output');
    const markup = document.getElementById('draft-markup');
    const correctBtn = document.getElementById('correct-btn');
    const editBtn = document.getElementById('edit-again-btn');
    if (draft) { draft.value = ''; draft.style.display = ''; draft.focus(); }
    if (polished) {
      polished.textContent = '';
      polished.classList.add('empty');
      disablePolishedListenButtons();
    }
    if (markup) { markup.innerHTML = ''; markup.hidden = true; }
    if (correctBtn) correctBtn.hidden = false;
    if (editBtn) editBtn.hidden = true;
    ns.updateWordCount();
  };

  // Target the polished-section TTS row by its ID. The earlier selector
  // `#polished-output ~ .button-row .tts-btn:not(.stop)` was broken: the
  // general-sibling combinator `~` requires both selectors to share a
  // parent, but #polished-output is inside .lines-overlay-host while the
  // button-row is one DOM level up — they're never siblings, so the query
  // matched zero elements and the TTS buttons stayed disabled forever.
  function enablePolishedListenButtons() {
    document.querySelectorAll('#polished-listen-row .tts-btn:not(.stop)')
      .forEach(b => { b.disabled = false; });
  }
  function disablePolishedListenButtons() {
    document.querySelectorAll('#polished-listen-row .tts-btn:not(.stop)')
      .forEach(b => { b.disabled = true; });
  }

  // ====================================================================
  // Diff engine — mirrors scripts/templates/diff_engine.mjs (tested separately)
  // Spec §8.5: 5 correction shapes (delete / insert / replace / suffix-add / prefix-add)
  // ====================================================================

  function wordDiff(a, b) {
    const aw = a.split(/\s+/).filter(Boolean);
    const bw = b.split(/\s+/).filter(Boolean);
    const m = aw.length, n = bw.length;
    const dp = Array.from({ length: m + 1 }, () => new Int32Array(n + 1));
    for (let i = m - 1; i >= 0; i--) {
      for (let j = n - 1; j >= 0; j--) {
        if (aw[i] === bw[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
        else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    const out = [];
    let i = 0, j = 0;
    while (i < m && j < n) {
      if (aw[i] === bw[j]) { out.push({ op: 'keep', word: aw[i] }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ op: 'delete', word: aw[i] }); i++; }
      else { out.push({ op: 'insert', word: bw[j] }); j++; }
    }
    while (i < m) out.push({ op: 'delete', word: aw[i++] });
    while (j < n) out.push({ op: 'insert', word: bw[j++] });
    return out;
  }

  // Merge consecutive same-op `delete`/`insert` segments into one multi-word
  // segment so phrase-level rewrites render as a single replace-pair instead
  // of multiple fragments. See diff_engine.mjs comments for the rationale.
  function coalesceAdjacentSameOp(segs) {
    const out = [];
    for (const s of segs) {
      const last = out[out.length - 1];
      if (last && last.op === s.op && (s.op === 'delete' || s.op === 'insert')) {
        last.word = last.word + ' ' + s.word;
      } else {
        out.push({ op: s.op, word: s.word });
      }
    }
    return out;
  }

  // Longest common prefix of two strings (case-sensitive). Used by Case H
  // (stem-change) to detect word-form transformations like tired→tiring.
  function longestCommonPrefix(a, b) {
    let i = 0;
    while (i < a.length && i < b.length && a[i] === b[i]) i++;
    return a.slice(0, i);
  }

  function classifyPairs(segs) {
    const out = [];
    let i = 0;
    while (i < segs.length) {
      const cur = segs[i];
      const next = segs[i + 1];
      if (cur.op === 'delete' && next && next.op === 'insert') {
        const x = cur.word, y = next.word;
        if (y !== x && y.startsWith(x)) {
          out.push({ op: 'suffix-add', kept: x, added: y.slice(x.length) });
        } else if (y !== x && y.endsWith(x)) {
          out.push({ op: 'prefix-add', added: y.slice(0, y.length - x.length), kept: x });
        } else if (y !== x && x.startsWith(y)) {
          // F. suffix-delete — understanding → understand
          out.push({ op: 'suffix-delete', kept: y, deleted: x.slice(y.length) });
        } else if (y !== x && x.endsWith(y)) {
          // G. prefix-delete — ago → go
          out.push({ op: 'prefix-delete', deleted: x.slice(0, x.length - y.length), kept: y });
        } else {
          const lcp = longestCommonPrefix(x, y);
          const xTail = x.slice(lcp.length);
          const yTail = y.slice(lcp.length);
          if (lcp.length >= 3
              && xTail.length >= 1 && xTail.length <= 5
              && yTail.length >= 1 && yTail.length <= 5) {
            // H. stem-change — tired→tiring, heavy→heavily, make→making
            out.push({ op: 'stem-change', kept: lcp, deleted: xTail, inserted: yTail });
          } else {
            out.push({ op: 'replace', deleted: x, inserted: y });
          }
        }
        i += 2;
      } else {
        out.push(cur);
        i += 1;
      }
    }
    return out;
  }

  function escHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function renderMarkup(classified) {
    const parts = [];
    classified.forEach((seg, idx) => {
      const space = idx > 0 ? ' ' : '';
      switch (seg.op) {
        case 'keep':
          parts.push(`${space}${escHtml(seg.word)}`); break;
        case 'delete':
          parts.push(`${space}<del class="del">${escHtml(seg.word)}</del>`); break;
        case 'insert':
          parts.push(`${space}<span class="gap-anchor"><ins class="ins-above">${escHtml(seg.word)}</ins></span>`); break;
        case 'replace':
          parts.push(`${space}<span class="replace-pair"><del class="del">${escHtml(seg.deleted)}</del><ins class="ins-above">${escHtml(seg.inserted)}</ins></span>`); break;
        case 'suffix-add':
          parts.push(`${space}${escHtml(seg.kept)}<ins class="ins-suffix">${escHtml(seg.added)}</ins>`); break;
        case 'prefix-add':
          parts.push(`${space}<ins class="ins-prefix">${escHtml(seg.added)}</ins>${escHtml(seg.kept)}`); break;
        case 'suffix-delete':
          parts.push(`${space}${escHtml(seg.kept)}<del class="del-suffix">${escHtml(seg.deleted)}</del>`); break;
        case 'prefix-delete':
          parts.push(`${space}<del class="del-prefix">${escHtml(seg.deleted)}</del>${escHtml(seg.kept)}`); break;
        case 'stem-change':
          parts.push(`${space}${escHtml(seg.kept)}<span class="stem-change-pair"><del class="del-suffix">${escHtml(seg.deleted)}</del><ins class="ins-above">${escHtml(seg.inserted)}</ins></span>`); break;
      }
    });
    return parts.join('');
  }

  // ====================================================================
  // correctEssay flow + status messages + edit-again  (spec §8.4, §8.10)
  // ====================================================================

  function setStatus(text, kind) {
    const s = document.getElementById('ai-status');
    if (!s) return;
    s.className = 'ai-status' + (kind ? ' ' + kind : '');
    s.innerHTML = text;
    if (kind === 'success') {
      setTimeout(() => { s.innerHTML = ''; s.className = 'ai-status'; }, 3000);
    }
  }

  ns.correctEssay = async function () {
    const draft = document.getElementById('student-draft');
    const markup = document.getElementById('draft-markup');
    const polished = document.getElementById('polished-output');
    const correctBtn = document.getElementById('correct-btn');
    const editBtn = document.getElementById('edit-again-btn');
    if (!draft || !markup || !polished || !correctBtn) return;

    const text = draft.value.trim();
    const n = text.split(/\s+/).filter(Boolean).length;
    if (n < 50) {
      setStatus(`请至少写 50 个词 / Please write at least 50 words. (Currently ${n})`, 'error');
      return;
    }
    if (n > 300) {
      setStatus(`请控制在 300 个词以内 / Please keep it under 300 words. (Currently ${n})`, 'error');
      return;
    }

    correctBtn.disabled = true;
    setStatus('<span class="spinner"></span>正在修改 / Correcting…');

    let resp;
    try {
      resp = await aiCorrectFetchWithRetry(text);
    } catch (e) {
      setStatus('网络错误 / Network error. ' + (e && e.message ? e.message : ''), 'error');
      correctBtn.disabled = false;
      return;
    }

    let body = null;
    try { body = await resp.json(); } catch { /* leave body null */ }
    if (!resp.ok) {
      setStatus((body && body.error) || `请求失败 / Request failed (${resp.status})`, 'error');
      correctBtn.disabled = false;
      return;
    }

    const corrected = (body && body.corrected) || '';
    polished.classList.remove('empty');
    polished.textContent = corrected;
    enablePolishedListenButtons();

    // Render the red-pen diff over the original draft text. The coalesce
    // step collapses runs of consecutive deletes/inserts into multi-word
    // segments — without it, phrase-level rewrites fragment into multiple
    // visual elements (chevron clusters, split corrections).
    const segs = wordDiff(text, corrected);
    const coalesced = coalesceAdjacentSameOp(segs);
    const classified = classifyPairs(coalesced);
    markup.innerHTML = renderMarkup(classified);
    markup.hidden = false;
    draft.style.display = 'none';
    correctBtn.hidden = true;
    if (editBtn) editBtn.hidden = false;

    saveDraft();
    setStatus('已修改 / Corrected ✓', 'success');
    correctBtn.disabled = false;
  };

  ns.editAgain = function () {
    const draft = document.getElementById('student-draft');
    const markup = document.getElementById('draft-markup');
    const polished = document.getElementById('polished-output');
    const correctBtn = document.getElementById('correct-btn');
    const editBtn = document.getElementById('edit-again-btn');
    if (markup) { markup.hidden = true; markup.innerHTML = ''; }
    if (polished) {
      polished.textContent = '';
      polished.classList.add('empty');
      disablePolishedListenButtons();
    }
    if (draft) {
      draft.style.display = '';
      draft.focus();
    }
    if (correctBtn) correctBtn.hidden = false;
    if (editBtn) editBtn.hidden = true;
    saveDraft();
  };

  // ====================================================================
  // Health-check badge  (spec §8.8)
  // ====================================================================

  async function checkHealth() {
    // The original implementation showed the offline badge whenever the
    // FC's /health route returned non-2xx. But the FC handler only
    // accepts POST and routes all paths to the correction function — a
    // GET /health returns 4xx/405. resp.ok was false → false offline
    // indicator, even though POST corrections work fine.
    //
    // Fix: any HTTP response (200, 4xx, 5xx) means the network is
    // reachable to the FC; only an actual fetch failure (DNS, timeout,
    // CORS, no-network) constitutes "offline". So we hide the badge as
    // long as fetch resolves at all, regardless of status code.
    const badge = document.getElementById('health-badge');
    if (!badge) return;
    try {
      const ctrl = new AbortController();
      // 8s — Aliyun FC cold-start can take 4-6s on first request; the prior
      // 3s timeout was firing the AbortController during cold-start and
      // showing a false "AI offline" badge to the user.
      const t = setTimeout(() => ctrl.abort(), 8000);
      await fetch(AI_ENDPOINT.replace(/\/$/, '') + '/health', { signal: ctrl.signal });
      clearTimeout(t);
      badge.hidden = true;
    } catch {
      badge.hidden = false;
    }
  }

  // ====================================================================
  // Listen-button injection + clickable vocab + IPA tooltip
  // (spec §8.7, §8.9)
  // ====================================================================

  /** True if `node` is a Chinese-gloss element we should NOT read aloud. */
  function isChineseGloss(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE) return false;
    if (node.lang === 'zh' || node.getAttribute('lang') === 'zh') return true;
    const style = node.getAttribute('style') || '';
    return /color\s*:\s*#7f8c8d/i.test(style);
  }

  /** True if `node` is a marker badge we should NOT read aloud (Op/Re/Ex etc.). */
  function isMarkerBadge(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE || !node.classList) return false;
    return node.classList.contains('badge-ore');
  }

  /** Strip parenthesized blocks containing CJK chars (e.g. "(有造诣的 / 成功的)")
   *  AND any standalone CJK runs. Multi-pass to handle nested cases like
   *  "instill (灌输 (价值观))". Used for inline-Chinese-gloss removal that the
   *  element-level skip can't catch. */
  function stripChineseGloss(s) {
    if (!s) return '';
    let prev;
    do {
      prev = s;
      s = s.replace(/\([^()]*[一-鿿][^()]*\)/g, '');
    } while (s !== prev);
    s = s.replace(/[一-鿿　-〿＀-￯]+/g, '');
    return s.replace(/\s+/g, ' ').trim();
  }

  /** Recursively collect text from a node, skipping Chinese-gloss subtrees,
   *  marker badges (Op/Re/Ex), and the listen-row itself. */
  function extractReadableText(node) {
    if (!node) return '';
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (node.nodeType !== Node.ELEMENT_NODE) return '';
    if (isChineseGloss(node)) return '';
    if (isMarkerBadge(node)) return '';
    if (node.classList && node.classList.contains('listen-row')) return '';
    return Array.from(node.childNodes).map(extractReadableText).join(' ');
  }

  function injectListenButtons() {
    document.querySelectorAll('.model-box').forEach((box) => {
      const card = box.closest('.card');
      if (!card) return;
      // Idempotent — one wrapper/row per card (controls the first .model-box).
      if (card.querySelector(':scope > .listen-row-wrapper, :scope > .listen-row')) return;

      const row = document.createElement('div');
      row.className = 'listen-row';
      // Six-button sentence-paced transport — pedagogical listen-and-repeat.
      // Layout: [accent picker | slow] [sentence counter] [prev | replay | next]
      row.innerHTML = `
        <button class="tts-btn uk active" title="UK voice / 英音">🇬🇧</button>
        <button class="tts-btn us"        title="US voice / 美音">🇺🇸</button>
        <button class="tts-btn slow"      title="Slow replay / 慢速重播本句" disabled>🐢</button>
        <span    class="sentence-counter" title="Current sentence / 当前句"></span>
        <button class="tts-btn prev"      title="Previous sentence / 上一句" disabled>⏮</button>
        <button class="tts-btn replay"    title="Replay this sentence / 重播本句" disabled>▶</button>
        <button class="tts-btn next"      title="Next sentence / 下一句" disabled>⏭</button>
      `;
      const btnUK     = row.querySelector('.tts-btn.uk');
      const btnUS     = row.querySelector('.tts-btn.us');
      const btnSlow   = row.querySelector('.tts-btn.slow');
      const btnPrev   = row.querySelector('.tts-btn.prev');
      const btnReplay = row.querySelector('.tts-btn.replay');
      const btnNext   = row.querySelector('.tts-btn.next');
      const textOf = () => stripChineseGloss(extractReadableText(box));

      btnUK.onclick     = () => ns.speakText(textOf(), 'en-GB', DEFAULT_RATE, row);
      btnUS.onclick     = () => ns.speakText(textOf(), 'en-US', DEFAULT_RATE, row);
      btnSlow.onclick   = () => ns.replaySentence(row, /* slow= */ true);
      btnPrev.onclick   = () => ns.prevSentence(row);
      btnReplay.onclick = () => ns.replaySentence(row, /* slow= */ false);
      btnNext.onclick   = () => ns.nextSentence(row);

      // Find the heading (h1-h4) immediately preceding this .model-box in
      // the .card. Walk back through siblings until we hit one or run out.
      let heading = box.previousElementSibling;
      while (heading && !/^H[1-6]$/.test(heading.tagName)) {
        heading = heading.previousElementSibling;
      }

      if (heading) {
        // Wrap heading + listen-row in a flex container so the row sits at
        // the bottom-right of the heading area (right above the .model-box),
        // regardless of whether the heading wraps to 1 or N lines.
        const wrapper = document.createElement('div');
        wrapper.className = 'listen-row-wrapper';
        card.insertBefore(wrapper, heading);
        wrapper.appendChild(heading);
        wrapper.appendChild(row);
      } else {
        // No heading — fall back to inserting just before the .model-box.
        box.parentElement.insertBefore(row, box);
      }
    });
  }

  function attachWordClicks() {
    document.querySelectorAll('.vocab-table strong, .model-box strong').forEach((el) => {
      // Skip <strong> inside any Chinese-gloss ancestor.
      let p = el.parentElement;
      while (p) { if (isChineseGloss(p)) return; p = p.parentElement; }
      // Skip <strong> inside the listen-row buttons or marker badges.
      if (el.closest('.listen-row') || el.closest('.badge-ore')) return;

      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        // Strip any inline CJK gloss like "accomplished (有造诣的 / 成功的)" → "accomplished"
        const word = stripChineseGloss(el.textContent);
        if (!word) return;
        ns.speakText(word, 'en-GB');
        showIpaTooltip(word, ev.pageX, ev.pageY);
      });
    });
  }

  // ---- IPA tooltip (lazy-loaded once per session) ----

  let _pronunciationsCache = null;
  async function loadPronunciations() {
    if (_pronunciationsCache) return _pronunciationsCache;
    try {
      const cached = sessionStorage.getItem('ielts:pronunciations');
      if (cached) { _pronunciationsCache = JSON.parse(cached); return _pronunciationsCache; }
    } catch { /* fall through */ }
    try {
      const resp = await fetch(PRONUNCIATIONS_URL);
      if (!resp.ok) return null;
      const json = await resp.json();
      _pronunciationsCache = json;
      try { sessionStorage.setItem('ielts:pronunciations', JSON.stringify(json)); }
      catch { /* quota exceeded — keep in-memory cache only */ }
      return json;
    } catch {
      return null;
    }
  }

  async function showIpaTooltip(word, x, y) {
    const dict = await loadPronunciations();
    if (!dict) return;
    const ipa = dict[word.toLowerCase()];
    if (!ipa) return;
    const tip = document.createElement('div');
    tip.className = 'ipa-tooltip';
    tip.textContent = `${word} ${ipa}`;
    tip.style.left = (x + 8) + 'px';
    tip.style.top = (y + 8) + 'px';
    document.body.appendChild(tip);
    setTimeout(() => tip.remove(), 3000);
  }

  // ====================================================================
  // __init — wires everything together on DOMContentLoaded
  // ====================================================================

  ns.__init = function () {
    const draft = document.getElementById('student-draft');
    if (draft) {
      draft.addEventListener('input', () => {
        ns.updateWordCount();
        debouncedSave();
      });
    }
    ns.updateWordCount();
    loadDraft();          // restore previous session before adding behavior
    injectListenButtons();
    attachWordClicks();
    checkHealth();
    initVoiceRecorder();  // no-op if no .voice-recorder-container on the page
  };

  // ====================================================================
  // Voice recorder — feature-flagged by .voice-recorder-container presence
  // in DOM. Records via MediaRecorder, persists Blob to IndexedDB keyed by
  // lesson, supports record/pause/resume/stop/play/re-record with a 3-min
  // hard cap. The IELTS DB name is "ielts-recordings"; the IGCSE port uses
  // "igcse-recordings" — different DBs so the two courses can coexist on
  // the same browser origin without colliding.
  // ====================================================================

  const VR_DB_NAME    = 'ielts-recordings';
  const VR_STORE      = 'recordings';
  const VR_MAX_MS     = 3 * 60 * 1000;

  // Singleton recording state — only one mic recording at a time.
  // `_activeContainer` tracks WHICH container is currently recording so we
  // know where to save the blob and update the UI on stop.
  let _vrMediaRecorder = null;
  let _vrChunks        = [];
  let _vrStartedAt     = 0;
  let _vrPausedTotal   = 0;
  let _vrPausedAt      = 0;
  let _vrTimerId       = 0;
  let _vrStream        = null;
  let _activeContainer = null;

  // Per-container blob URL for playback (keep separate per widget so
  // pressing ▶ on Q1 plays Q1's recording, not whichever was last loaded).
  const _vrSavedBlobUrls = new WeakMap();

  // IndexedDB key per container. Each .voice-recorder-container needs a
  // `data-recorder-id` attribute (e.g. "polished", "q1", "map-1") so its
  // recording is stored at a unique key like "Week_1_Lesson_Plan:q1".
  // Falls back to "default" for backward compatibility with old widgets.
  function vrKey(container) {
    const id = (container && container.dataset && container.dataset.recorderId) || 'default';
    return `${LESSON_KEY}:${id}`;
  }

  function vrOpenDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(VR_DB_NAME, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(VR_STORE);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  // === Quota management — one-and-done LRU eviction ============================
  // Goal: never blow past the browser's IndexedDB quota even if a viral cohort
  // of students records 3-min answers in every recorder of every Week. Two
  // belt-and-suspenders mechanisms run together:
  //
  //  1. Persistent storage request: tells the browser "don't auto-evict our
  //     data when disk fills up." Granted automatically in most cases on
  //     desktop Chrome; iOS Safari ignores it but it's still cheap to ask.
  //  2. LRU eviction: enforced via TWO ceilings — a HARD COUNT cap (always
  //     in effect) and a SOFT QUOTA cap (kicks in when the browser tells us
  //     usage is approaching its quota). On iOS Safari (~1 GB origin cap),
  //     the quota ceiling protects against the cap; on Chrome desktop (~60%
  //     of disk), the count cap keeps things tidy regardless.
  //
  // Eviction is FIFO by `createdAt` (oldest recording removed first). The
  // student never sees an error — recordings just silently disappear in age
  // order, which is the right UX for a long-running classroom course.
  const VR_MAX_RECORDINGS = 60;          // hard cap — never exceed this regardless of free quota
  const VR_QUOTA_HEADROOM = 0.20;        // start evicting when free quota < 20% of usable
  let _vrPersistRequested = false;

  async function vrRequestPersistentStorage() {
    if (_vrPersistRequested) return;
    _vrPersistRequested = true;
    try {
      if (navigator.storage && typeof navigator.storage.persist === 'function') {
        await navigator.storage.persist();
      }
    } catch (e) {
      // Older Safari / Firefox quirks — ignore, we have LRU as the safety net.
    }
  }

  // Walk every entry in the store and return [{key, createdAt}, ...] sorted
  // ascending so index 0 is the OLDEST recording (first to evict).
  async function vrListEntriesByAge(db) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(VR_STORE, 'readonly');
      const req = tx.objectStore(VR_STORE).openCursor();
      const out = [];
      req.onsuccess = () => {
        const cur = req.result;
        if (cur) {
          const v = cur.value || {};
          out.push({ key: cur.key, createdAt: v.createdAt || 0 });
          cur.continue();
        } else {
          out.sort((a, b) => a.createdAt - b.createdAt);
          resolve(out);
        }
      };
      req.onerror = () => reject(req.error);
    });
  }

  async function vrDeleteByKey(db, key) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(VR_STORE, 'readwrite');
      tx.objectStore(VR_STORE).delete(key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  // Returns a number 0..1 representing fraction of quota currently in use,
  // or null if the API isn't available (fallback: rely solely on count cap).
  async function vrQuotaUsageRatio() {
    try {
      if (navigator.storage && typeof navigator.storage.estimate === 'function') {
        const { usage, quota } = await navigator.storage.estimate();
        if (quota && quota > 0) return usage / quota;
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  // Run BEFORE saving a new recording. Evicts oldest recordings until BOTH
  // the hard count cap and the soft quota cap are satisfied. Skips the
  // currently-active container's existing key (which the upcoming put() will
  // overwrite anyway — no point evicting it just to write it).
  async function vrEvictIfNeeded(db, exemptKey) {
    let entries = await vrListEntriesByAge(db);
    let evicted = 0;

    // Pass 1 — hard count cap.
    while (entries.length > VR_MAX_RECORDINGS) {
      const oldest = entries.shift();
      if (oldest.key === exemptKey) continue;
      await vrDeleteByKey(db, oldest.key);
      evicted++;
    }

    // Pass 2 — soft quota cap (only if API tells us we're tight).
    let ratio = await vrQuotaUsageRatio();
    while (ratio !== null && ratio > (1 - VR_QUOTA_HEADROOM) && entries.length > 1) {
      const oldest = entries.shift();
      if (oldest.key === exemptKey) continue;
      await vrDeleteByKey(db, oldest.key);
      evicted++;
      ratio = await vrQuotaUsageRatio();
    }

    if (evicted > 0) {
      try { console.info(`[recorder] LRU evicted ${evicted} oldest recording(s) to stay under quota.`); } catch {}
    }
  }

  // Kick off persistent-storage request once at module load — non-blocking.
  vrRequestPersistentStorage();
  // ============================================================================

  async function vrSaveBlob(container, blob, durationMs) {
    const db = await vrOpenDB();
    // Evict before write so a near-full quota doesn't reject our put().
    try { await vrEvictIfNeeded(db, vrKey(container)); } catch (e) { console.warn('vrEvict', e); }
    return new Promise((resolve, reject) => {
      const tx = db.transaction(VR_STORE, 'readwrite');
      tx.objectStore(VR_STORE).put({ blob, duration: durationMs, createdAt: Date.now() }, vrKey(container));
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }
  async function vrLoadBlob(container) {
    const db = await vrOpenDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(VR_STORE, 'readonly');
      const req = tx.objectStore(VR_STORE).get(vrKey(container));
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  }
  async function vrDeleteBlob(container) {
    const db = await vrOpenDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(VR_STORE, 'readwrite');
      tx.objectStore(VR_STORE).delete(vrKey(container));
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  function vrFormatTime(ms) {
    const total = Math.floor(ms / 1000);
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
  }

  function vrSetState(container, state) {
    const $ = (sel) => container.querySelector(sel);
    const btnRec    = $('.vr-record');
    const btnPause  = $('.vr-pause');
    const btnStop   = $('.vr-stop');
    const btnPlay   = $('.vr-play');
    const btnDelete = $('.vr-delete');
    const label    = $('.vr-label');  // optional — inline widgets omit it

    [btnRec, btnPause, btnStop, btnPlay, btnDelete].forEach(b => b && (b.hidden = true));
    if (btnRec) btnRec.classList.remove('recording');
    if (btnPause) btnPause.classList.remove('paused');
    if (label) label.classList.remove('error');

    if (state === 'idle') {
      if (btnRec) { btnRec.hidden = false; btnRec.disabled = false; }
      if (label) label.textContent = 'Click ⏺ to record (3:00 max)';
    } else if (state === 'recording') {
      if (btnRec) { btnRec.hidden = false; btnRec.classList.add('recording'); btnRec.disabled = true; }
      if (btnPause) btnPause.hidden = false;
      if (btnStop) btnStop.hidden = false;
      if (label) label.textContent = 'Recording…';
    } else if (state === 'paused') {
      if (btnRec) { btnRec.hidden = false; btnRec.classList.add('recording'); btnRec.disabled = true; }
      if (btnPause) { btnPause.hidden = false; btnPause.classList.add('paused'); btnPause.title = 'Resume'; btnPause.textContent = '▶'; }
      if (btnStop) btnStop.hidden = false;
      if (label) label.textContent = 'Paused — tap ▶ to resume';
    } else if (state === 'saved') {
      if (btnRec) { btnRec.hidden = false; btnRec.disabled = false; }
      if (btnPlay) btnPlay.hidden = false;
      if (btnDelete) btnDelete.hidden = false;
      if (btnPause) { btnPause.textContent = '⏸'; btnPause.title = 'Pause / resume'; }
      if (label) label.textContent = 'Saved — tap ▶ to play, 🗑 to re-record';
    } else if (state === 'error') {
      if (btnRec) { btnRec.hidden = false; btnRec.disabled = true; }
      if (label) label.classList.add('error');
    }
  }

  function vrUpdateTimer(container) {
    if (_activeContainer !== container) return;
    const elapsed = Date.now() - _vrStartedAt - _vrPausedTotal -
                    (_vrPausedAt ? (Date.now() - _vrPausedAt) : 0);
    const timeEl = container.querySelector('.vr-time');
    if (timeEl) timeEl.textContent = `${vrFormatTime(elapsed)} / 3:00`;
    if (elapsed >= VR_MAX_MS) {
      if (timeEl) timeEl.classList.add('over');
      vrStop(container);
    }
  }

  async function vrStart(container) {
    // If another widget is recording, stop it first so we don't get two
    // active MediaRecorder instances (the browser only allows one anyway).
    if (_activeContainer && _activeContainer !== container && _vrMediaRecorder
        && _vrMediaRecorder.state !== 'inactive') {
      _vrMediaRecorder.stop();
    }
    try {
      _vrStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const label = container.querySelector('.vr-label');
      if (label) label.textContent = 'Microphone permission denied / 麦克风权限被拒绝';
      vrSetState(container, 'error');
      return;
    }
    _activeContainer = container;
    _vrChunks = [];
    _vrStartedAt = Date.now();
    _vrPausedTotal = 0;
    _vrPausedAt = 0;
    _vrMediaRecorder = new MediaRecorder(_vrStream);
    _vrMediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) _vrChunks.push(e.data); };
    _vrMediaRecorder.onstop = async () => {
      const blob = new Blob(_vrChunks, { type: _vrMediaRecorder.mimeType || 'audio/webm' });
      const elapsed = Date.now() - _vrStartedAt - _vrPausedTotal;
      try { await vrSaveBlob(container, blob, elapsed); } catch (e) { console.error('vrSave', e); }
      if (_vrStream) { _vrStream.getTracks().forEach(t => t.stop()); _vrStream = null; }
      clearInterval(_vrTimerId); _vrTimerId = 0;
      _activeContainer = null;
      vrLoadIntoUi(container);
    };
    _vrMediaRecorder.start();
    _vrTimerId = setInterval(() => vrUpdateTimer(container), 250);
    vrSetState(container, 'recording');
  }

  function vrPauseToggle(container) {
    if (!_vrMediaRecorder || _activeContainer !== container) return;
    if (_vrMediaRecorder.state === 'recording') {
      _vrMediaRecorder.pause();
      _vrPausedAt = Date.now();
      vrSetState(container, 'paused');
    } else if (_vrMediaRecorder.state === 'paused') {
      _vrPausedTotal += Date.now() - _vrPausedAt;
      _vrPausedAt = 0;
      _vrMediaRecorder.resume();
      vrSetState(container, 'recording');
    }
  }

  function vrStop(container) {
    if (!_vrMediaRecorder || _activeContainer !== container) return;
    if (_vrMediaRecorder.state !== 'inactive') _vrMediaRecorder.stop();
  }

  async function vrLoadIntoUi(container) {
    const rec = await vrLoadBlob(container);
    const audioEl = container.querySelector('audio');
    // Per-widget blob URL — revoke ONLY this container's old URL.
    const oldUrl = _vrSavedBlobUrls.get(container);
    if (oldUrl) { URL.revokeObjectURL(oldUrl); _vrSavedBlobUrls.delete(container); }
    if (rec && rec.blob) {
      const url = URL.createObjectURL(rec.blob);
      _vrSavedBlobUrls.set(container, url);
      if (audioEl) audioEl.src = url;
      const timeEl = container.querySelector('.vr-time');
      if (timeEl) {
        timeEl.textContent = vrFormatTime(rec.duration || 0);
        timeEl.classList.remove('over');
      }
      vrSetState(container, 'saved');
    } else {
      const timeEl = container.querySelector('.vr-time');
      if (timeEl) {
        timeEl.textContent = '--:--';
        timeEl.classList.remove('over');
      }
      vrSetState(container, 'idle');
    }
  }

  async function vrDelete(container) {
    if (!confirm('Delete recording? / 删除录音？')) return;
    await vrDeleteBlob(container);
    const oldUrl = _vrSavedBlobUrls.get(container);
    if (oldUrl) { URL.revokeObjectURL(oldUrl); _vrSavedBlobUrls.delete(container); }
    vrLoadIntoUi(container);
  }

  function vrPlay(container) {
    const audioEl = container.querySelector('audio');
    if (audioEl && audioEl.src) audioEl.play();
  }

  function initVoiceRecorder() {
    if (!('mediaDevices' in navigator) || !window.MediaRecorder) return;
    document.querySelectorAll('.voice-recorder-container').forEach((container) => {
      const q = (sel) => container.querySelector(sel);
      const onIf = (sel, handler) => { const el = q(sel); if (el) el.onclick = handler; };
      onIf('.vr-record', () => vrStart(container));
      onIf('.vr-pause',  () => vrPauseToggle(container));
      onIf('.vr-stop',   () => vrStop(container));
      onIf('.vr-play',   () => vrPlay(container));
      onIf('.vr-delete', () => vrDelete(container));
      vrLoadIntoUi(container);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ns.__init === 'function') ns.__init();
  });

})();
