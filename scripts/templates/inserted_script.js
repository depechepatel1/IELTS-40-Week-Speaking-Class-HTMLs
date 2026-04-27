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

  // === Speech state — owned by us, NOT by the (flaky) Web Speech API ===
  // Chrome's speechSynthesis.pause()/resume() is unreliable across long
  // utterances and after >5s pauses. Instead of trusting it, we track text
  // + current word offset ourselves and on "resume" we cancel + restart
  // from the saved offset. This works reliably across all browsers.
  let _currentText = '';
  let _currentLang = 'en-GB';
  let _currentRate = 1.0;
  let _currentWordOffset = 0;
  let _currentSourceRow = null;
  let _currentSpans = null;     // for karaoke highlight (speakElement)
  let _currentOffsets = null;   // for karaoke highlight (speakElement)
  let _isPaused = false;        // OUR truth, not speechSynthesis.paused

  /** Mark a single .listen-row as the one currently speaking (for the
   *  pulsing indicator). Pass `null` to clear. */
  function setSpeakingRow(rowEl) {
    document.querySelectorAll('.listen-row.speaking-now').forEach(r => r.classList.remove('speaking-now'));
    if (rowEl) rowEl.classList.add('speaking-now');
  }

  /** Sync every .tts-btn.pause to OUR _isPaused state.
   *  ▶ + .paused class when paused, ⏸ when speaking/idle. */
  function updatePauseButtons() {
    document.querySelectorAll('.tts-btn.pause').forEach(b => {
      b.textContent = _isPaused ? '▶' : '⏸';
      b.title = _isPaused ? 'Resume' : 'Pause';
      b.classList.toggle('paused', _isPaused);
    });
  }

  /** Internal: launch a fresh utterance starting at `offset` characters
   *  into _currentText. Used by both speakText/speakElement (offset=0)
   *  and pauseSpeaking (offset=_currentWordOffset on resume). */
  function _speakFromOffset(offset) {
    const remaining = _currentText.slice(offset);
    if (!remaining.trim()) return;
    const u = new SpeechSynthesisUtterance(remaining);
    u.lang = _currentLang;
    u.rate = _currentRate;
    const v = pickVoice(_currentLang);
    if (v) u.voice = v;
    u.onstart = () => { setSpeakingRow(_currentSourceRow); };
    u.onboundary = (ev) => {
      if (ev.name && ev.name !== 'word') return;
      _currentWordOffset = offset + ev.charIndex;
      // Karaoke highlight if spans were registered (speakElement path).
      if (_currentSpans && _currentOffsets) {
        _currentSpans.forEach(s => s.classList.remove('speaking'));
        const hit = _currentOffsets.find(o => _currentWordOffset >= o.start && _currentWordOffset < o.end);
        if (hit) hit.span.classList.add('speaking');
      }
    };
    u.onend = () => {
      // Natural end (NOT a user-initiated pause). Reset state.
      if (_isPaused) return;
      _currentText = '';
      _currentWordOffset = 0;
      if (_currentSpans) _currentSpans.forEach(s => s.classList.remove('speaking'));
      _currentSpans = null;
      _currentOffsets = null;
      setSpeakingRow(null);
      updatePauseButtons();
    };
    window.speechSynthesis.speak(u);
  }

  ns.stopSpeaking = function () {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (_currentSpans) _currentSpans.forEach(s => s.classList.remove('speaking'));
    _currentSpans = null;
    _currentOffsets = null;
    _currentText = '';
    _currentWordOffset = 0;
    _currentSourceRow = null;
    _isPaused = false;
    setSpeakingRow(null);
    updatePauseButtons();
  };

  // Toggle pause/resume. Pause = cancel + remember offset; Resume =
  // restart utterance from the saved offset (avoids Chrome resume bug).
  ns.pauseSpeaking = function () {
    if (!('speechSynthesis' in window)) return;
    if (_isPaused) {
      _isPaused = false;
      updatePauseButtons();
      _speakFromOffset(_currentWordOffset);
    } else if (_currentText && (window.speechSynthesis.speaking || window.speechSynthesis.pending)) {
      _isPaused = true;
      window.speechSynthesis.cancel();
      // Keep _currentText and _currentWordOffset so resume works.
      updatePauseButtons();
    }
  };

  // Tracks the last accent the student picked on each listen-row. Slow
  // playback uses this so it matches whichever voice is currently selected.
  // Map<rowEl, 'en-GB' | 'en-US'>.
  const _lastLangByRow = new WeakMap();

  function setActiveAccent(rowEl, lang) {
    if (!rowEl) return;
    _lastLangByRow.set(rowEl, lang);
    rowEl.querySelectorAll('.tts-btn.uk, .tts-btn.us').forEach(b => b.classList.remove('active'));
    const sel = lang === 'en-US' ? '.tts-btn.us' : '.tts-btn.uk';
    const btn = rowEl.querySelector(sel);
    if (btn) btn.classList.add('active');
  }

  function lastLangFor(rowEl) {
    return _lastLangByRow.get(rowEl) || 'en-GB';
  }

  /** Centralised handler for the polished-output Listen buttons.
   *  Tracks the selected accent on #polished-listen-row so the slow button
   *  uses whichever accent was last picked. */
  ns.listenPolished = function (which) {
    const row = document.getElementById('polished-listen-row');
    if (which === 'en-GB' || which === 'en-US') {
      setActiveAccent(row, which);
      ns.speakElementById('polished-output', which, 1.0);
    } else if (which === 'slow') {
      ns.speakElementById('polished-output', lastLangFor(row), 0.85);
    }
  };

  ns.speakText = function (text, lang = 'en-GB', rate = 1.0, sourceRow = null) {
    // WeChat exposes speechSynthesis but speak() silently no-ops. Detect first.
    if (isWeChatBrowser()) { wechatFallbackAlert(); return; }
    if (!('speechSynthesis' in window)) return;
    if (!text || !String(text).trim()) return;
    ns.stopSpeaking();
    _currentText = String(text);
    _currentLang = lang;
    _currentRate = rate;
    _currentWordOffset = 0;
    _currentSourceRow = sourceRow;
    _currentSpans = null;
    _currentOffsets = null;
    _isPaused = false;
    updatePauseButtons();
    _speakFromOffset(0);
  };

  // Wraps each word in <span> for karaoke highlighting on `boundary` events.
  ns.speakElement = function (el, lang = 'en-GB', rate = 1.0) {
    // WeChat exposes speechSynthesis but speak() silently no-ops. Detect first.
    if (isWeChatBrowser()) { wechatFallbackAlert(); return; }
    if (!('speechSynthesis' in window)) return;
    if (!el) return;
    const text = el.textContent.trim();
    if (!text) return;

    // Re-wrap text in per-word spans so we can highlight by character offset.
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

    ns.stopSpeaking();
    _currentText = text;
    _currentLang = lang;
    _currentRate = rate;
    _currentWordOffset = 0;
    _currentSourceRow = (el.id === 'polished-output')
      ? document.getElementById('polished-listen-row')
      : null;
    _currentSpans = spans;
    _currentOffsets = offsets;
    _isPaused = false;
    updatePauseButtons();
    _speakFromOffset(0);
  };

  ns.speakElementById = function (id, lang = 'en-GB', rate = 1.0) {
    const el = document.getElementById(id);
    if (el) ns.speakElement(el, lang, rate);
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
          out.push({ op: 'replace', deleted: x, inserted: y });
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
      resp = await fetch(AI_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draft: text })
      });
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
      row.innerHTML = `
        <button class="tts-btn uk active" title="UK voice">🇬🇧</button>
        <button class="tts-btn us" title="US voice">🇺🇸</button>
        <button class="tts-btn slow" title="Slow (uses selected accent)">🐢</button>
        <button class="tts-btn pause" title="Pause / resume">⏸</button>
        <button class="tts-btn stop" title="Stop">⏹</button>
      `;
      const [btnUK, btnUS, btnSlow, btnPause, btnStop] = row.children;
      const textOf = () => stripChineseGloss(extractReadableText(box));

      // Default accent is UK (matches the .active class in markup above).
      _lastLangByRow.set(row, 'en-GB');

      btnUK.onclick    = () => { setActiveAccent(row, 'en-GB'); ns.speakText(textOf(), 'en-GB', 1.0, row); };
      btnUS.onclick    = () => { setActiveAccent(row, 'en-US'); ns.speakText(textOf(), 'en-US', 1.0, row); };
      btnSlow.onclick  = () => ns.speakText(textOf(), lastLangFor(row), 0.85, row);
      btnPause.onclick = () => ns.pauseSpeaking();
      btnStop.onclick  = () => ns.stopSpeaking();

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
  let _vrMediaRecorder = null;
  let _vrChunks        = [];
  let _vrStartedAt     = 0;
  let _vrPausedTotal   = 0;
  let _vrPausedAt      = 0;
  let _vrTimerId       = 0;
  let _vrStream        = null;
  let _vrSavedBlobUrl  = null;

  function vrOpenDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(VR_DB_NAME, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(VR_STORE);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  async function vrSaveBlob(blob, durationMs) {
    const db = await vrOpenDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(VR_STORE, 'readwrite');
      tx.objectStore(VR_STORE).put({ blob, duration: durationMs, createdAt: Date.now() }, LESSON_KEY);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }
  async function vrLoadBlob() {
    const db = await vrOpenDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(VR_STORE, 'readonly');
      const req = tx.objectStore(VR_STORE).get(LESSON_KEY);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  }
  async function vrDeleteBlob() {
    const db = await vrOpenDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(VR_STORE, 'readwrite');
      tx.objectStore(VR_STORE).delete(LESSON_KEY);
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
    const label    = $('.vr-label');

    [btnRec, btnPause, btnStop, btnPlay, btnDelete].forEach(b => b && (b.hidden = true));
    btnRec.classList.remove('recording');
    btnPause.classList.remove('paused');
    label.classList.remove('error');

    if (state === 'idle') {
      btnRec.hidden = false;
      label.textContent = 'Click ⏺ to record (3:00 max)';
    } else if (state === 'recording') {
      btnRec.hidden = false; btnRec.classList.add('recording');
      btnPause.hidden = false; btnStop.hidden = false;
      btnRec.disabled = true;
      label.textContent = 'Recording…';
    } else if (state === 'paused') {
      btnRec.hidden = false; btnRec.classList.add('recording');
      btnPause.hidden = false; btnPause.classList.add('paused');
      btnStop.hidden = false;
      btnRec.disabled = true;
      btnPause.title = 'Resume';
      btnPause.textContent = '▶';
      label.textContent = 'Paused — tap ▶ to resume';
    } else if (state === 'saved') {
      btnPlay.hidden = false; btnDelete.hidden = false;
      btnRec.disabled = false;
      label.textContent = 'Saved — tap ▶ to play, 🗑 to re-record';
      btnPause.textContent = '⏸';
      btnPause.title = 'Pause / resume';
    } else if (state === 'error') {
      btnRec.hidden = false; btnRec.disabled = true;
      label.classList.add('error');
    }
  }

  function vrUpdateTimer(container) {
    const elapsed = Date.now() - _vrStartedAt - _vrPausedTotal -
                    (_vrPausedAt ? (Date.now() - _vrPausedAt) : 0);
    const timeEl = container.querySelector('.vr-time');
    timeEl.textContent = `${vrFormatTime(elapsed)} / 3:00`;
    if (elapsed >= VR_MAX_MS) {
      timeEl.classList.add('over');
      vrStop(container);
    }
  }

  async function vrStart(container) {
    try {
      _vrStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const label = container.querySelector('.vr-label');
      label.textContent = 'Microphone permission denied / 麦克风权限被拒绝';
      vrSetState(container, 'error');
      return;
    }
    _vrChunks = [];
    _vrStartedAt = Date.now();
    _vrPausedTotal = 0;
    _vrPausedAt = 0;
    _vrMediaRecorder = new MediaRecorder(_vrStream);
    _vrMediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) _vrChunks.push(e.data); };
    _vrMediaRecorder.onstop = async () => {
      const blob = new Blob(_vrChunks, { type: _vrMediaRecorder.mimeType || 'audio/webm' });
      const elapsed = Date.now() - _vrStartedAt - _vrPausedTotal;
      try { await vrSaveBlob(blob, elapsed); } catch (e) { console.error('vrSave', e); }
      if (_vrStream) { _vrStream.getTracks().forEach(t => t.stop()); _vrStream = null; }
      clearInterval(_vrTimerId); _vrTimerId = 0;
      vrLoadIntoUi(container);
    };
    _vrMediaRecorder.start();
    _vrTimerId = setInterval(() => vrUpdateTimer(container), 250);
    vrSetState(container, 'recording');
  }

  function vrPauseToggle(container) {
    if (!_vrMediaRecorder) return;
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
    if (!_vrMediaRecorder) return;
    if (_vrMediaRecorder.state !== 'inactive') _vrMediaRecorder.stop();
  }

  async function vrLoadIntoUi(container) {
    const rec = await vrLoadBlob();
    const audioEl = container.querySelector('audio');
    if (_vrSavedBlobUrl) { URL.revokeObjectURL(_vrSavedBlobUrl); _vrSavedBlobUrl = null; }
    if (rec && rec.blob) {
      _vrSavedBlobUrl = URL.createObjectURL(rec.blob);
      if (audioEl) audioEl.src = _vrSavedBlobUrl;
      const timeEl = container.querySelector('.vr-time');
      timeEl.textContent = vrFormatTime(rec.duration || 0);
      timeEl.classList.remove('over');
      vrSetState(container, 'saved');
    } else {
      const timeEl = container.querySelector('.vr-time');
      timeEl.textContent = '--:--';
      timeEl.classList.remove('over');
      vrSetState(container, 'idle');
    }
  }

  async function vrDelete(container) {
    if (!confirm('Delete recording? / 删除录音？')) return;
    await vrDeleteBlob();
    if (_vrSavedBlobUrl) { URL.revokeObjectURL(_vrSavedBlobUrl); _vrSavedBlobUrl = null; }
    vrLoadIntoUi(container);
  }

  function vrPlay(container) {
    const audioEl = container.querySelector('audio');
    if (audioEl && audioEl.src) audioEl.play();
  }

  function initVoiceRecorder() {
    if (!('mediaDevices' in navigator) || !window.MediaRecorder) return;
    document.querySelectorAll('.voice-recorder-container').forEach((container) => {
      container.querySelector('.vr-record').onclick = () => vrStart(container);
      container.querySelector('.vr-pause').onclick  = () => vrPauseToggle(container);
      container.querySelector('.vr-stop').onclick   = () => vrStop(container);
      container.querySelector('.vr-play').onclick   = () => vrPlay(container);
      container.querySelector('.vr-delete').onclick = () => vrDelete(container);
      vrLoadIntoUi(container);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ns.__init === 'function') ns.__init();
  });

})();
