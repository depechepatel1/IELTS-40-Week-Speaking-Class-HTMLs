/* === IELTS Interactive AI Correction — injected JS block === */
(function () {
  'use strict';

  // Substituted by make_interactive.py at build time.
  const AI_ENDPOINT = "__AI_ENDPOINT__";
  const PRONUNCIATIONS_URL = "__PRONUNCIATIONS_URL__";
  const LESSON_KEY = "__LESSON_KEY__"; // e.g. "Week_01"

  const ns = (window.__ielts = window.__ielts || {});

  // ====================================================================
  // TTS subsystem — Web Speech API with voice waterfall + karaoke
  // ====================================================================

  // Common female-neural voice names across Edge/Chrome (Windows), Safari/iOS,
  // and Android system voices. The regex covers both modern Edge "Natural"
  // voices and legacy macOS / iOS / Android voices known to sound natural.
  const FEMALE_NEURAL_UK = /Sonia|Libby|Mia|Maisie|Kate|Serena|Sienna|Tessa|Karen|Hazel|Susan|Stephanie/i;
  // Round 33 (2026-05-06) — added "Christopher" so Edge's Microsoft Christopher
  // Online (Natural) en-GB voice ranks correctly when the user selects the
  // male toggle. Christopher was the highest-quality Microsoft natural-male
  // voice missing from the list.
  const MALE_NEURAL_UK   = /Ryan|Thomas.*GB|Christopher|Noah|Daniel|George|Oliver/i;
  // Round 45 (2026-05-13) — added Helena (Windows SAPI en-US female) so the
  // female toggle still wins on Windows installs lacking Edge neural voices.
  const FEMALE_NEURAL_US = /Aria|Jenny|Ana|Michelle|Emma|Samantha|Allison|Ava|Joanna|Salli|Kendra|Kimberly|Ivy|Nora|Susan.*US|Zira|Helena|Heather/i;
  // Round 45 — added David, Mark, Paul, James (Windows SAPI en-US male
  // names) so the male toggle correctly selects a male voice on systems
  // without Edge neural voices. Previously David/Mark were unknown to the
  // regex and the male toggle silently lost — Zira (female) would still
  // win via the +5 cross-gender fallback bonus because no voice scored
  // the +25 male match.
  const MALE_NEURAL_US   = /Christopher|Guy|Tony|Jason|Eric|Davis|Alex|Aaron|Brandon|Steffan|Roger|David\b|Mark\b|Paul\b|James\b/i;
  // iPad / iOS Siri-tier voice names. Apple ships these unmarked but they
  // are the higher-quality "Siri-style" voices on iOS. "Premium" / "Enhanced"
  // tags only appear once the user has manually downloaded the larger voice
  // file via Settings → Accessibility → Spoken Content → Voices.
  const IOS_PREMIUM_NAMES =
    /Ava|Aaron|Nicky|Evan|Joelle|Noelle|Zoe|Catherine|Serena|Stephanie|Daniel|Arthur|Oliver|Martha/i;

  // Round 45 (2026-05-13) — cross-dialect gender regexes. Used by pickVoice
  // ONLY when the exact-dialect pool is empty and we've fallen back to
  // "any en-*" voices. Previously the gender scoring used the UK regex on a
  // US-only fallback pool (or vice versa); since the UK female list (Sonia,
  // Karen, Hazel…) doesn't include US female names (Zira, Aria, Samantha…),
  // every voice scored 0 on gender and the first-in-insertion-order voice
  // won — which on a Windows install with only en-US voices meant David
  // (male) could win an en-GB+female request. Unifying the regexes in the
  // fallback path restores deterministic gender selection.
  const FEMALE_NEURAL_ANY = new RegExp(
    FEMALE_NEURAL_UK.source + "|" + FEMALE_NEURAL_US.source, "i"
  );
  const MALE_NEURAL_ANY = new RegExp(
    MALE_NEURAL_UK.source + "|" + MALE_NEURAL_US.source, "i"
  );

  // Round 46 (2026-05-13) — TTS voice cache keyed by "lang|gender".
  // Guarantees both vocab-click (speakText) and model-answer
  // (_playCurrentSentence) paths reuse the SAME voice for any given
  // (lang, gender) combination. The cache is invalidated on the
  // onvoiceschanged event so async-loaded Edge neural voices upgrade
  // the cache as soon as they arrive.
  const _voiceCache = new Map();

  // Speech rates. Tuned for Chinese L2 listeners — 0.85 is the comfortable
  // default (matches what was previously the "slow" button rate); 0.72 is
  // the new "slow" — about 15% slower than the new default, useful when a
  // student wants to copy pronunciation word-by-word.
  const DEFAULT_RATE = 0.85;
  const SLOW_RATE    = 0.72;

  // Round 31 (2026-05-06) — sticky "current teaching accent". Updated
  // every time `speakElement` runs (which is what UK/US buttons trigger
  // via listenPolished + injectListenButtons). Read by attachWordClicks
  // so single-word vocab/model-answer clicks play in the same accent the
  // teacher is currently using for the model-answer karaoke. Resets to
  // 'en-GB' on first page load so initial vocab clicks (before any
  // model-answer button is pressed) keep the historical default.
  let _userPreferredLang = 'en-GB';

  // Round 33 (2026-05-06) — sticky "current teaching gender". Same
  // pattern as _userPreferredLang. Toggled via the new Male/Female
  // button in the listen-row clusters; read by pickVoice() so that
  // every TTS surface (model-answer karaoke, polished-output, vocab
  // single-word clicks) speaks in whichever gender the teacher has
  // active. 'female' default keeps the historical voice on first load.
  let _userPreferredGender = 'female';

  // Round 39 (2026-05-11) — persistent slow-mode toggle. Replaces the
  // old "play this one sentence slowly, then snap back to normal"
  // behaviour. When true, EVERY TTS surface plays at SLOW_RATE: model
  // answers, vocabulary clicks, prev/next/replay, polished-output —
  // anywhere a rate is consulted, _userPreferredSlow wins. The slow
  // button (🐢) becomes a sticky on/off switch; its .active CSS class
  // is the user-visible "currently slow" indicator.
  let _userPreferredSlow = false;

  // Round 33 — warmup flag. The first speak() call after page load
  // sometimes plays in the system default ("robotic") voice on Edge /
  // Chrome / Windows because the requested voice hasn't fully loaded
  // yet. Workaround: queue a silent (volume:0) priming utterance with
  // the same voice config BEFORE the real one. The real utterance then
  // plays with the correct voice. We only do this once per page load
  // since subsequent speak() calls reuse a primed engine.
  let _ttsWarmedUp = false;
  function ensureTtsWarmup(voice, lang) {
    if (_ttsWarmedUp) return;
    if (!('speechSynthesis' in window)) return;
    try {
      // Single space, normal rate, zero volume — silently primes the
      // engine + voice cache. Queues ahead of the real utterance via
      // Web Speech API's natural FIFO ordering.
      const w = new SpeechSynthesisUtterance(' ');
      w.lang = lang || 'en-GB';
      w.volume = 0;
      w.rate = 1;
      if (voice) w.voice = voice;
      window.speechSynthesis.speak(w);
      _ttsWarmedUp = true;
    } catch (_) {
      // Some browsers throw if speak() fires before any user gesture
      // (autoplay policy). Ignore — the next user-initiated click will
      // try again.
    }
  }

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
  //
  // Round 33 (2026-05-06): added optional `gender` parameter. When 'male' is
  // passed, the +25 bonus that previously locked female-named voices to the
  // top is flipped onto the male regex instead. Falls back to female if
  // omitted to preserve historical default behavior across all callers that
  // haven't been updated yet (none should remain after Round 33, but defensive).
  // True for iPhone, iPod, and iPadOS 13+. iPadOS 13+ reports as "MacIntel"
  // — the maxTouchPoints check is the only reliable signal that distinguishes
  // an iPad from a desktop Mac (desktop Macs return 0 touch points).
  // Note: every iPad browser uses Apple's WebKit engine (Apple App Store
  // policy), so this single check covers iPad Safari, iPad Chrome, AND
  // iPad Microsoft Edge — they all share Apple's voice catalog.
  function isIOS() {
    const ua = navigator.userAgent || '';
    if (/iPhone|iPod|iPad/.test(ua)) return true;
    return navigator.platform === 'MacIntel'
        && (navigator.maxTouchPoints || 0) > 1;
  }

  // ────────────────────────────────────────────────────────────────────
  // TTS ARCHITECTURAL NOTE (Round 47, 2026-05-13)
  //
  // Edge presents TWO distinct categories of voices via getVoices(),
  // only one of which is actually "built into the browser":
  //
  //   1. Local SAPI / system voices (Microsoft Zira, David, Mark,
  //      Hazel, George) — synthesis happens on-device, instant
  //      playback, lower neural quality. localService === true.
  //
  //   2. "Online (Natural)" voices (Microsoft Sonia / Aria /
  //      Christopher / Ryan / Libby / Mia / Guy etc.) — synthesis
  //      happens on Microsoft's TTS servers; every speak() call
  //      POSTs the text and streams back ~100–300 KB of audio.
  //      ~250 ms to several seconds of per-utterance latency
  //      depending on network. localService === false.
  //
  // Our scoring below gives Online (Natural) voices +100 / +80
  // bonuses so the picker PREFERS them for accent training —
  // pedagogically Sonia is a much better UK voice than Hazel. The
  // trade-off is per-click network roundtrip.
  //
  // The Round 46 voice cache (see _voiceCache below) caches the
  // SpeechSynthesisVoice OBJECT REFERENCE so vocab clicks and
  // model-answer playback agree on which voice to use. It does NOT
  // and CANNOT cache the AUDIO BYTES — those are opaque to
  // JavaScript, owned internally by Edge and the Microsoft TTS
  // service.
  //
  // If a future maintainer is investigating "why is there a delay
  // between voice selection and audio playback?" — that delay is
  // inherent to the Online (Natural) voices' network roundtrip,
  // NOT a code-level inefficiency in our voice selection. The
  // only ways to eliminate it are:
  //
  //   (a) Use only local SAPI voices (loses neural quality) —
  //       Round 47 explicitly rejected this.
  //   (b) Pre-render audio to MP3 server-side and host on OSS —
  //       Round 47 explicitly rejected this.
  //   (c) Service Worker proxying the TTS HTTPS calls — infeasible
  //       because Edge uses native APIs, not fetchable network
  //       requests that JS can intercept.
  //
  // Accept the latency. Don't optimize unless one of (a) / (b) /
  // (c) becomes acceptable.
  // ────────────────────────────────────────────────────────────────────
  function pickVoice(lang, gender) {
    if (!('speechSynthesis' in window)) return null;
    const all = window.speechSynthesis.getVoices();
    if (!all.length) return null;

    const langPrefix = lang === 'en-GB' ? 'en-GB' : 'en-US';

    // Round 46 — cache hit. The cache is invalidated by onvoiceschanged
    // so any cached entry is guaranteed to reference a voice from the
    // current voice list (a voice object kept across getVoices() calls
    // remains valid until the underlying list mutates).
    const cacheKey = langPrefix + '|' + (gender === 'male' ? 'male' : 'female');
    if (_voiceCache.has(cacheKey)) {
      const cached = _voiceCache.get(cacheKey);
      try {
        console.info(
          `[TTS] cache HIT  key=${cacheKey}  → ${cached ? cached.name : 'null'}`
        );
      } catch (_) {}
      return cached;
    }

    let pool = all.filter(v => v.lang === langPrefix);
    const exactDialectMatch = pool.length > 0;
    if (!pool.length) pool = all.filter(v => v.lang && v.lang.startsWith('en'));
    if (!pool.length) return all[0];

    // Round 45 — gender regex tracks the POOL's actual dialect, not the
    // original request. If we fell back to a cross-dialect pool (e.g. user
    // requested en-GB but the system only has en-US voices), use the
    // unified regex covering BOTH dialects so gender scoring still works.
    // Otherwise gender preference silently fails on cross-dialect fallbacks.
    const female = exactDialectMatch
      ? (lang === 'en-GB' ? FEMALE_NEURAL_UK : FEMALE_NEURAL_US)
      : FEMALE_NEURAL_ANY;
    const male = exactDialectMatch
      ? (lang === 'en-GB' ? MALE_NEURAL_UK   : MALE_NEURAL_US)
      : MALE_NEURAL_ANY;
    const wantMale = gender === 'male';

    const onIOS = isIOS();
    const score = (v) => {
      const tag = (v.name || '') + ' ' + (v.voiceURI || '');
      let s = 0;
      if (onIOS) {
        // iOS / iPadOS path. Apple's WebKit hides network voices and never
        // tags voices "Natural" / "Online" / "Google", so the desktop tier
        // bonuses below would all score zero and effectively pick at random.
        // Instead, weight by Apple's own quality markers and a curated list
        // of unmarked-but-Siri-tier voice names.
        // Round 51 — on iPad/iPhone the built-in Siri voices are the
        // explicit FIRST CHOICE (per teacher request). Siri now scores
        // ABOVE user-downloaded Premium/Enhanced voices, so a device with
        // the default Siri UK/US male+female voices always uses them.
        if (/Siri/i.test(tag))               s += 130;  // iOS 16+ Siri voices — first choice
        if (/Premium/i.test(tag))            s += 100;  // user-downloaded best
        if (/Enhanced/i.test(tag))           s +=  80;  // user-downloaded medium
        if (IOS_PREMIUM_NAMES.test(v.name))  s +=  40;  // unmarked Siri-tier
        // Do NOT add the !localService bonus on iOS — WebKit reports every
        // voice as local, so the bonus would be a constant and meaningless.
      } else {
        // Desktop / Android — original Round-33 scoring, unchanged.
        if (/Natural/i.test(tag))            s += 100;  // Edge neural voices
        if (/Online/i.test(tag))             s +=  80;  // Microsoft cloud voices
        if (/Google/i.test(tag))             s +=  60;  // Google network voices
        if (/Premium|Enhanced/i.test(tag))   s +=  50;  // macOS / iOS premium
        if (!v.localService)                 s +=  30;  // network > local generally
      }
      // Round 33 — gender preference. Whichever gender is requested gets the
      // +25 ranking bonus; the other gender gets the +5 fallback bonus so that
      // if no requested-gender voice exists in the pool we still pick a
      // sensible alternative rather than randomly returning the lowest-scored
      // voice. Identical for iOS and desktop branches.
      if (wantMale) {
        if (male.test(v.name))            s +=  25;
        else if (female.test(v.name))     s +=   5;
      } else {
        if (female.test(v.name))          s +=  25;
        else if (male.test(v.name))       s +=   5;
      }
      if (v.lang === langPrefix)          s +=  10;  // exact lang > prefix match
      return s;
    };

    // Round 46 — resolve, cache, log.
    const winner = pool.slice().sort((a, b) => score(b) - score(a))[0];
    if (winner) _voiceCache.set(cacheKey, winner);
    try {
      console.info(
        `[TTS] cache MISS key=${cacheKey}  → ` +
        `${winner ? winner.name : 'null'}` +
        ` (voice.lang=${winner ? winner.lang : '-'}; pool=${pool.length}; ` +
        `exact-dialect=${exactDialectMatch}; iOS=${onIOS})`
      );
    } catch (_) {}
    return winner;
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

    // Round 32 (2026-05-06) — defensive clear of EVERY karaoke span on
    // this row before starting a new sentence. Previously the cleanup
    // operated on `activeOffsets` (current sentence only), which left a
    // span permanently lit if it ever got `.speaking` outside the current
    // sentence's char range — e.g. when a stale boundary event fired
    // after speechSynthesis.cancel() but before the new utterance
    // overrode handlers. Clearing ALL spans on entry guarantees no
    // leftover survives a sentence transition.
    if (st.spans) st.spans.forEach(s => s.classList.remove('speaking'));

    const sentence      = st.sentences[st.currentIndex];
    const sentenceStart = sentenceCharStart(st.sentences, st.currentIndex);

    const u = new SpeechSynthesisUtterance(sentence);
    u.lang = st.lang;
    // Round 39 — global slow-mode toggle always wins over whatever rate
    // the caller passed in. When the 🐢 button is active, every sentence
    // plays at SLOW_RATE regardless of which TTS entry point was used.
    u.rate = _userPreferredSlow
           ? SLOW_RATE
           : (rateOverride || st.rate || DEFAULT_RATE);
    const v = pickVoice(st.lang, _userPreferredGender);  // Round 33
    if (v) u.voice = v;
    // Round 33 — warm the engine + voice cache on FIRST speak() of the page
    // session. The silent (volume:0) priming utterance queues ahead of the
    // real one and prevents the "robotic default voice" fallback that
    // sometimes happens before Edge/Chrome finishes loading the requested
    // voice.
    ensureTtsWarmup(v, st.lang);

    // Karaoke: only when this row owns word-wrapped spans (polished-output path).
    const activeOffsets = (st.spans && st.offsets)
      ? st.offsets.filter(o => o.start >= sentenceStart && o.end <= sentenceStart + sentence.length)
      : null;

    u.onstart = () => setSpeakingRow(rowEl);
    u.onboundary = (ev) => {
      if (ev.name && ev.name !== 'word') return;
      if (!activeOffsets) return;
      // Round 32 — clear ALL spans on the row, not just activeOffsets,
      // so any stuck-from-prior-sentence highlight is cleaned up on
      // every word boundary as a belt-and-braces reset.
      if (st.spans) st.spans.forEach(s => s.classList.remove('speaking'));
      const globalIdx = sentenceStart + ev.charIndex;
      const hit = activeOffsets.find(o => globalIdx >= o.start && globalIdx < o.end);
      if (hit) hit.span.classList.add('speaking');
    };
    u.onend = () => {
      // Round 32 — clear ALL row spans, not just activeOffsets, so the
      // last word of every sentence (including end-of-utterance) gets
      // unhighlighted regardless of which sentence's range it fell into.
      if (st.spans) st.spans.forEach(s => s.classList.remove('speaking'));
      // Auto-pause: leave currentIndex where it is; clear pulse; refresh buttons.
      if (_currentRow === rowEl) _currentRow = null;
      setSpeakingRow(null);
      updateTransportButtons(rowEl);
    };

    speechSynthesis.speak(u);
    updateTransportButtons(rowEl);
  }

  ns.speakText = function (text, lang = 'en-GB', rate = DEFAULT_RATE, rowEl = null, onDone = null) {
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
      // Round 39 — vocab single-clicks also respect the global slow toggle.
      u.rate = _userPreferredSlow ? SLOW_RATE : rate;
      const v = pickVoice(lang, _userPreferredGender);  // Round 33
      if (v) u.voice = v;
      ensureTtsWarmup(v, lang);  // Round 33 — silent prime on first vocab click
      // Round 52 — optional completion callback so the word-click handler
      // can clear its .speaking flash exactly when speech ends. onerror
      // fires it too (e.g. an interrupted utterance) so the flash never
      // gets stuck on. Row-bound callers pass nothing and are unaffected.
      if (typeof onDone === 'function') {
        u.onend = onDone;
        u.onerror = onDone;
      }
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

  // Markup-preserving variant of speakElement's wrapping logic. Walks the
  // text-node descendants of `el` and replaces each text node with a
  // fragment that splits the text into per-word <span>s (for karaoke
  // highlighting) while LEAVING element children (e.g. <strong> for vocab,
  // <em> for emphasis) intact. Skips Chinese-gloss / marker-badge /
  // listen-row subtrees so wrapped spans align with what the TTS engine
  // actually speaks.
  //
  // Added 2026 (issue A2): the polished-output element is plain text and
  // the original speakElement could safely innerHTML='' it. Model-answer
  // boxes (Section 7) contain <strong>vocab</strong> highlights and
  // Chinese gloss spans; destroying their innerHTML would lose both.
  // This helper provides a non-destructive wrap path for markup-rich
  // elements. Returns { spans, offsets } with the same shape that the
  // original wrap path produces.
  // Round 30 (2026-05-06) — match stripChineseGloss's element-pruning
  // patterns so karaoke-wrap accumulates char-offsets in the SAME space
  // TTS speaks. Two patterns are stripped: parenthesized blocks that
  // contain CJK ("(灌输 / 价值观)"), and bare CJK runs ("灌输"). Anything
  // matching is rendered as a plain text node — visible to students,
  // never wrapped in a karaoke span. See `stripChineseGloss` below for
  // the source-of-truth regex these mirror.
  const INLINE_GLOSS_RE = /\([^()]*[一-鿿㐀-䶿][^()]*\)|[一-鿿㐀-䶿　-〿＀-￯]+/g;

  function wrapTextNodesInElement(el) {
    const spans = [];
    const offsets = [];
    let charIdx = 0;
    // Track whether the most recent character we've contributed to
    // charIdx is whitespace. stripChineseGloss collapses runs of
    // whitespace (including the gaps left by stripped gloss) to a
    // single space, so we model that here: only the FIRST whitespace
    // token at a boundary counts toward charIdx; subsequent whitespace
    // tokens (e.g. the space immediately before a stripped gloss plus
    // the space immediately after it) are emitted into the DOM but do
    // not advance charIdx. Initialised true so leading whitespace at
    // the very start of the element doesn't off-by-one the first word.
    let lastCountedWasSpace = true;

    function pushWordSpan(frag, tok) {
      const s = document.createElement('span');
      s.textContent = tok;
      offsets.push({ span: s, start: charIdx, end: charIdx + tok.length });
      spans.push(s);
      frag.appendChild(s);
      charIdx += tok.length;
      lastCountedWasSpace = false;
    }

    function pushWhitespace(frag, tok) {
      // Emit the literal whitespace into the DOM (visual fidelity), but
      // count only one space toward charIdx if there hasn't already been
      // a counted whitespace since the last word. This mirrors the
      // `\s+ -> ' '` collapse `stripChineseGloss` performs on the spoken
      // text — without it, the karaoke offsets drift forward by one
      // every time we cross a stripped-gloss boundary.
      frag.appendChild(document.createTextNode(tok));
      if (!lastCountedWasSpace) {
        charIdx += 1;
        lastCountedWasSpace = true;
      }
    }

    function pushGlossText(frag, text) {
      // Inline gloss — visually preserved, never wrapped in a span,
      // does NOT advance charIdx. lastCountedWasSpace is unchanged so
      // surrounding whitespace collapses correctly across the gloss.
      frag.appendChild(document.createTextNode(text));
    }

    function processSegmentText(text, frag) {
      // Tokenise plain (non-gloss) text into word/whitespace runs and
      // emit each.
      const tokens = text.split(/(\s+)/);
      tokens.forEach(tok => {
        if (!tok) return;
        if (/^\s+$/.test(tok)) pushWhitespace(frag, tok);
        else pushWordSpan(frag, tok);
      });
    }

    function processTextNode(t, frag) {
      // Split the text-node content into [non-gloss, gloss, non-gloss, …]
      // segments so we never wrap CJK / paren-CJK blocks as karaoke spans.
      let lastIdx = 0;
      let m;
      INLINE_GLOSS_RE.lastIndex = 0;
      while ((m = INLINE_GLOSS_RE.exec(t)) !== null) {
        if (m.index > lastIdx) processSegmentText(t.slice(lastIdx, m.index), frag);
        pushGlossText(frag, m[0]);
        lastIdx = m.index + m[0].length;
      }
      if (lastIdx < t.length) processSegmentText(t.slice(lastIdx), frag);
    }

    function walk(node) {
      if (!node) return;
      if (node.nodeType === Node.TEXT_NODE) {
        const t = node.textContent;
        if (!t) return;
        const frag = document.createDocumentFragment();
        processTextNode(t, frag);
        node.parentNode.replaceChild(frag, node);
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return;
      if (isChineseGloss(node)) return;
      if (isMarkerBadge(node)) return;
      if (node.classList && node.classList.contains('listen-row')) return;
      // Snapshot childNodes — we'll be replacing some during the walk.
      Array.from(node.childNodes).forEach(walk);
    }
    walk(el);
    return { spans, offsets };
  }

  // Round 52 — module-level cache for ensureWordsWrapped(). Keyed by the
  // wrapped element so the click-to-speak feature (attachWordClicks) and
  // the karaoke feature (speakElement) reuse ONE set of per-word
  // <span class="tts-word"> elements instead of each wrapping the DOM
  // independently and clobbering the other's spans.
  const _wordWrapCache = new WeakMap();

  // Round 52 — idempotent, cached wrapper around wrapTextNodesInElement().
  // First call on `el`: wraps every text node into <span class="tts-word">,
  // caches and returns {spans, offsets}. Repeat calls: returns the cache
  // untouched. This is the SINGLE place DOM word-wrapping happens.
  function ensureWordsWrapped(el) {
    const cached = _wordWrapCache.get(el);
    if (cached) return cached;
    const result = wrapTextNodesInElement(el);
    result.spans.forEach((s) => s.classList.add('tts-word'));
    _wordWrapCache.set(el, result);
    return result;
  }

  // speakElement / speakElementById — wrap words in <span> for karaoke,
  // split text into sentences, and play sentence 0. Subsequent transport
  // commands (replay / next / prev / slow) re-use the wrapped spans.
  // The optional `rowElOverride` arg lets callers pin the WeakMap state
  // to a specific .listen-row element (used by injectListenButtons so
  // its prev/next/replay/slow buttons share state with the speaking text).
  ns.speakElement = function (el, lang = 'en-GB', rate = DEFAULT_RATE, rowElOverride = null) {
    if (isWeChatBrowser()) { wechatFallbackAlert(); return; }
    if (!('speechSynthesis' in window)) return;
    if (!el) return;

    // For markup-rich elements (model answers with <strong>/Chinese gloss),
    // compute the readable text using extractReadableText so it matches
    // what TTS speaks (skipping gloss). For plain-text elements (polished
    // output) we can use textContent directly — same result, less work.
    const hasMarkup = el.children.length > 0;
    const text = (hasMarkup
      ? stripChineseGloss(extractReadableText(el))
      : el.textContent
    ).trim();
    if (!text) return;

    // The polished overlay's listen-row is the natural row for el.id === 'polished-output'.
    // injectListenButtons passes the model-box's .listen-row as the override.
    // For everything else, fall back to using `el` itself as the WeakMap key.
    const rowEl = rowElOverride
      || (el.id === 'polished-output'
          ? document.getElementById('polished-listen-row')
          : el);

    const st = getRowState(rowEl);

    // Re-wrap only if text changed AND the element isn't already wrapped.
    // The data-karaoke-wrapped flag stops a second click from destroying
    // our own spans (which would be st.wrappedText !== text after a wrap
    // reduces all whitespace runs to single spaces).
    const isFreshWrap = (st.wrappedText !== text || !el.dataset.karaokeWrapped);
    if (isFreshWrap) {
      let spans, offsets;
      if (hasMarkup) {
        // Round 52 — go through ensureWordsWrapped() so karaoke highlights
        // the SAME .tts-word spans attachWordClicks() already made
        // clickable (instead of re-wrapping and orphaning them).
        const result = ensureWordsWrapped(el);
        spans = result.spans;
        offsets = result.offsets;
      } else {
        // Plain-text path (original behaviour, used for polished-output).
        const tokens = text.split(/(\s+)/);
        el.innerHTML = '';
        spans = [];
        offsets = [];
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
      }
      el.dataset.karaokeWrapped = '1';
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
    // Round 30 (2026-05-06) — only reset to sentence 0 when the underlying
    // text is fresh. When the SAME text is re-spoken (UK/US accent toggle
    // via listenPolished), preserve st.currentIndex so the teacher can
    // play sentence 3 in UK, then immediately the same sentence in US
    // without the counter snapping back to 1. Clamp on length change just
    // in case a re-split produced fewer sentences than before.
    if (isFreshWrap) {
      st.currentIndex = 0;
    } else if (typeof st.currentIndex !== 'number'
               || st.currentIndex < 0
               || st.currentIndex >= st.sentences.length) {
      st.currentIndex = 0;
    }
    st.lang = lang;
    st.rate = rate || DEFAULT_RATE;
    // Round 31 — record the user's most recent explicit accent choice
    // so single-word vocab clicks (attachWordClicks) play in the same
    // accent. UK/US buttons all route through this function, so this
    // stays in sync with whatever the teacher is currently teaching.
    _userPreferredLang = lang;
    setActiveAccent(rowEl, lang);
    _playCurrentSentence(rowEl);
  };

  ns.speakElementById = function (id, lang = 'en-GB', rate = DEFAULT_RATE) {
    const el = document.getElementById(id);
    if (el) ns.speakElement(el, lang, rate);
  };

  /** Polished-output button router. Round 33 added the 'gender' mode for the
   *  Male/Female toggle button. Other modes: en-GB / en-US (start over in
   *  chosen accent), slow / replay (re-speak current sentence), prev / next
   *  (sentence navigation). */
  ns.listenPolished = function (which) {
    const row = document.getElementById('polished-listen-row');
    if (!row) return;
    switch (which) {
      case 'en-GB':
      case 'en-US':
        ns.speakElementById('polished-output', which, DEFAULT_RATE);
        break;
      case 'slow': {
        // Round 42 (2026-05-12) — bring the polished-output 🐢 button into
        // line with the model-answer card behaviour from Round 39: this is
        // now a sticky GLOBAL toggle, not a one-shot "force slow this once".
        // Mirror the broadcast pattern from injectListenButtons → btnSlow.
        _userPreferredSlow = !_userPreferredSlow;
        document.querySelectorAll('.tts-btn.slow').forEach(b => {
          b.classList.toggle('active', _userPreferredSlow);
          b.title = _userPreferredSlow
            ? 'Slow mode: ON (0.72×) — click for normal speed / 慢速模式：开'
            : 'Slow mode: OFF (0.85×) — click for slow speed / 慢速模式：关';
        });
        // If a sentence has already been queued on this row, replay it at
        // the new rate so the teacher hears the change immediately.
        const _st = getRowState(row);
        if (_st && _st.sentences && _st.sentences.length) {
          ns.replaySentence(row, /* slow= */ false);
        }
        break;
      }
      case 'replay': ns.replaySentence(row, false); break;
      case 'prev':   ns.prevSentence(row);          break;
      case 'next':   ns.nextSentence(row);          break;
      case 'gender': {
        // Round 33 — flip the global gender preference, refresh ALL visible
        // gender buttons on the page so they stay in sync, then replay the
        // current sentence with the new voice for immediate feedback.
        _userPreferredGender = _userPreferredGender === 'male' ? 'female' : 'male';
        document.querySelectorAll('.tts-btn.gender').forEach(b => {
          const isMale = _userPreferredGender === 'male';
          b.classList.toggle('male',   isMale);
          b.classList.toggle('female', !isMale);
          b.textContent = isMale ? '👨' : '👩';
        });
        const st = getRowState(row);
        if (st && st.sentences && st.sentences.length) {
          ns.replaySentence(row, /* slow= */ false);
        }
        break;
      }
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

  // Voice list loads asynchronously on Chrome and especially on iOS Safari /
  // WebKit, where the first getVoices() call commonly returns []. Touching it
  // here primes the cache; the onvoiceschanged handler below picks up the
  // real list when WebKit publishes it. We also clear the warmup flag so the
  // next TTS click re-warms with the upgraded voice (the warmup utterance is
  // silent — no audible glitch).
  if ('speechSynthesis' in window) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.getVoices();
      // Round 46 — invalidate the voice cache so subsequent pickVoice
      // calls re-resolve against the now-upgraded voice list. Edge's
      // "Online (Natural)" neural voices arrive after this event fires;
      // without cache invalidation, the cache would stick with the
      // initial SAPI fallback (Zira/David/Mark) for the rest of the
      // session.
      _voiceCache.clear();
      _ttsWarmedUp = false;
      try {
        console.info(
          `[TTS] voices changed; cache cleared; voices=` +
          (window.speechSynthesis.getVoices() || []).length
        );
      } catch (_) {}
    };
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

    // Defense-in-depth markdown stripper. The FC sanitises Zhipu's
    // response before sending, but old cached HTMLs or any other code
    // path that injects into `body.corrected` could still contain
    // markdown leakage like `**However,**` for transitions. Treat the
    // boundary between FC and renderer as untrusted-w.r.t.-markdown.
    const corrected = String((body && body.corrected) || '')
        .replace(/\*\*([^*]+)\*\*/g, '$1')   // **bold** -> bold
        .replace(/(^|\s)\*\*(\s|$)/g, '$1$2')// stray paired ** at boundaries
        .replace(/\*\*/g, '')                // any remaining lone **
        .trim();
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
      // Round 33 — seven-button sentence-paced transport. New leading
      // Male/Female toggle (👩 / 👨) selects the natural-voice gender
      // for whichever accent is currently active. The label flips on
      // every click and a global `_userPreferredGender` drives every
      // pickVoice() call across the page.
      // Layout: [gender | UK | US | slow] [sentence counter] [prev | replay | next]
      row.innerHTML = `
        <button class="tts-btn gender female" title="Toggle voice gender / 切换男女声">👩</button>
        <button class="tts-btn uk active" title="UK voice / 英音">🇬🇧</button>
        <button class="tts-btn us"        title="US voice / 美音">🇺🇸</button>
        <button class="tts-btn slow"      title="Slow replay / 慢速重播本句" disabled>🐢</button>
        <span    class="sentence-counter" title="Current sentence / 当前句"></span>
        <button class="tts-btn prev"      title="Previous sentence / 上一句" disabled>⏮</button>
        <button class="tts-btn replay"    title="Replay this sentence / 重播本句" disabled>▶</button>
        <button class="tts-btn next"      title="Next sentence / 下一句" disabled>⏭</button>
      `;
      const btnGender = row.querySelector('.tts-btn.gender');
      const btnUK     = row.querySelector('.tts-btn.uk');
      const btnUS     = row.querySelector('.tts-btn.us');
      const btnSlow   = row.querySelector('.tts-btn.slow');
      const btnPrev   = row.querySelector('.tts-btn.prev');
      const btnReplay = row.querySelector('.tts-btn.replay');
      const btnNext   = row.querySelector('.tts-btn.next');
      const textOf = () => stripChineseGloss(extractReadableText(box));

      // Mirror the global gender state onto a freshly-injected button so it
      // matches whichever toggle the teacher set on a sibling card earlier.
      function refreshGenderBtn() {
        const isMale = _userPreferredGender === 'male';
        btnGender.classList.toggle('male',   isMale);
        btnGender.classList.toggle('female', !isMale);
        btnGender.textContent = isMale ? '👨' : '👩';
      }
      refreshGenderBtn();

      // Round 39 — same mirror pattern for the persistent slow toggle.
      // If the teacher enabled slow mode earlier (e.g. on the previous
      // card before this row was injected by lazy scroll), this fresh
      // button must visibly show the active state from first render.
      btnSlow.classList.toggle('active', _userPreferredSlow);
      btnSlow.title = _userPreferredSlow
        ? 'Slow mode: ON (0.72×) — click for normal speed / 慢速模式：开'
        : 'Slow mode: OFF (0.85×) — click for slow speed / 慢速模式：关';

      // A2 2026: switched from speakText (no karaoke) to speakElement
      // (word-by-word karaoke highlight). speakElement wraps each word
      // of `box` in a <span> while preserving existing <strong>/<em>
      // markup, skipping Chinese gloss subtrees. The 4th arg pins the
      // WeakMap state to `row` so prev/next/replay/slow buttons below
      // share state with the speaking text.
      btnUK.onclick     = () => ns.speakElement(box, 'en-GB', DEFAULT_RATE, row);
      btnUS.onclick     = () => ns.speakElement(box, 'en-US', DEFAULT_RATE, row);
      // Round 39 — 🐢 is now a STICKY GLOBAL TOGGLE, not a one-shot replay.
      // Flipping it broadcasts the new state to every visible slow button
      // on the page so all cards show the same on/off indicator. Title
      // attribute updates to make the current state explicit. If a sentence
      // is already loaded on this row, replay it so the teacher hears the
      // new rate immediately.
      btnSlow.onclick   = () => {
        _userPreferredSlow = !_userPreferredSlow;
        document.querySelectorAll('.tts-btn.slow').forEach(b => {
          b.classList.toggle('active', _userPreferredSlow);
          b.title = _userPreferredSlow
            ? 'Slow mode: ON (0.72×) — click for normal speed / 慢速模式：开'
            : 'Slow mode: OFF (0.85×) — click for slow speed / 慢速模式：关';
        });
        const st = getRowState(row);
        if (st && st.sentences && st.sentences.length) {
          ns.replaySentence(row, /* slow= */ false);
        }
      };
      btnPrev.onclick   = () => ns.prevSentence(row);
      btnReplay.onclick = () => ns.replaySentence(row, /* slow= */ false);
      btnNext.onclick   = () => ns.nextSentence(row);
      // Round 33 — gender toggle. Flips global state, refreshes EVERY visible
      // gender button on the page (so all cards stay in sync), and replays
      // the current sentence so the teacher hears the new voice immediately.
      // If the row hasn't started speaking yet, just toggle silently — the
      // next UK/US click will pick up the new gender.
      btnGender.onclick = () => {
        _userPreferredGender = _userPreferredGender === 'male' ? 'female' : 'male';
        document.querySelectorAll('.tts-btn.gender').forEach(b => {
          const isMale = _userPreferredGender === 'male';
          b.classList.toggle('male',   isMale);
          b.classList.toggle('female', !isMale);
          b.textContent = isMale ? '👨' : '👩';
        });
        // If a sentence has been queued/played on this row, replay it with
        // the new voice for instant feedback. ns.replaySentence is a no-op
        // when the row has no st.sentences yet.
        const st = getRowState(row);
        if (st && st.sentences && st.sentences.length) {
          ns.replaySentence(row, /* slow= */ false);
        }
      };

      // Round 49d — insert the listen-row as a direct child of the .card.
      // CSS (`.card > .listen-row`) positions it absolutely in the card's
      // top-right corner, so it occupies ZERO vertical space. Previously the
      // row was flex-wrapped together with the section heading inside a
      // `.listen-row-wrapper`; on cards with a long section title (e.g. IGCSE
      // Section 6 "Circuit Prompt & Model Answer") the wrapper squeezed the
      // heading, forcing the title onto a 2nd line — the extra height pushed
      // page-4's bottom banner off the page. Absolute positioning keeps the
      // buttons in the available top-right space with no layout reflow.
      card.insertBefore(row, card.firstChild);
    });
  }

  // Round 52 — in-scope selector for word-level click-to-speak. ONE
  // hardcoded string, byte-identical in both repos (inserted_script.js is
  // a mirror). It is the UNION of IGCSE + IELTS selectors; each repo
  // simply has no DOM matching the other's selectors, so they are
  // harmless no-ops (same pattern the `.sec-2` selector relied on).
  //   .model-box .......................... model answers + shadowing (both repos)
  //   .sec-4 .item-text, .sec-10 .item-text  IGCSE Warm-Up + Fast Finisher questions
  //   .section-prompt-and-model > p:not(.model-box)  IGCSE Section 6 circuit prompt
  //   .q-prompt ........................... IELTS cue card + Part 3 question <h3>s + brainstorming prompts
  const WORD_CLICK_SCOPE =
    '.model-box, .sec-4 .item-text, .sec-10 .item-text, ' +
    '.section-prompt-and-model > p:not(.model-box), .q-prompt';

  function attachWordClicks() {
    // ---- Part 1: in-scope containers — EVERY word is click-to-speak ----
    // Round 52 — eagerly wrap each in-scope container's words into
    // <span class="tts-word"> via ensureWordsWrapped() (so the karaoke
    // path reuses the same spans), then attach ONE delegated click
    // listener per container.
    document.querySelectorAll(WORD_CLICK_SCOPE).forEach((container) => {
      // Idempotency guard — mirrors the legacy data-wordClickBound flag.
      if (container.dataset.wordClicksDelegated === '1') return;
      ensureWordsWrapped(container);
      container.dataset.wordClicksDelegated = '1';
      container.addEventListener('click', (ev) => {
        const span = ev.target.closest('.tts-word');
        if (!span || !container.contains(span)) return;
        ev.stopPropagation();
        // No stripChineseGloss here — wrapTextNodesInElement already keeps
        // Chinese gloss OUT of .tts-word spans, so textContent is a clean
        // single English token.
        const word = span.textContent;
        if (!word || !word.trim()) return;
        // Defensive: clear any flash still on from a previous rapid click.
        document.querySelectorAll('.tts-word.speaking')
          .forEach((s) => s.classList.remove('speaking'));
        span.classList.add('speaking');
        const clearFlash = () => span.classList.remove('speaking');
        ns.speakText(word, _userPreferredLang, DEFAULT_RATE, null, clearFlash);
        showIpaTooltip(word, ev.pageX, ev.pageY);
      });
    });

    // ---- Part 2: legacy <strong>-only clicks (vocab table + Section 2) ----
    // UNCHANGED behaviour — these areas are OUT of the Round-52 scope, so
    // they keep today's per-<strong> click, the dotted underline, and NO
    // speaking flash. `.model-box strong` is intentionally NOT here any
    // more: model boxes are fully covered by Part 1 above.
    document.querySelectorAll('.vocab-table strong, .sec-2 .item-text strong').forEach((el) => {
      if (el.dataset.wordClickBound === '1') return;
      let p = el.parentElement;
      while (p) { if (isChineseGloss(p)) return; p = p.parentElement; }
      if (el.closest('.listen-row') || el.closest('.badge-ore')) return;
      el.dataset.wordClickBound = '1';
      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const word = stripChineseGloss(el.textContent);
        if (!word) return;
        ns.speakText(word, _userPreferredLang);
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
  // hard cap. Round 42 (2026-05-12): the DB name is now hostname-driven
  // so the IGCSE site uses "igcse-recordings" and the IELTS site uses
  // "ielts-recordings". Previously a single hardcoded constant in this
  // mirrored file gave both sites the same DB name; harmless across the
  // two production origins (per-origin IndexedDB) but broke if both
  // sites were ever loaded from the same local origin during dev/testing.
  // Falls through to "ielts-recordings" for local file:// or unknown hosts,
  // preserving the legacy default.
  // ====================================================================

  const VR_DB_NAME    = /igcse/i.test(window.location.hostname || '')
                          ? 'igcse-recordings'
                          : 'ielts-recordings';
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
  // Round 42 — handle on the previous recorder's onstop so a re-entrant
  // vrStart() can await the prior save fully before overwriting the
  // shared chunk/timing globals. Without this, a fast tap on widget B
  // while widget A is still recording could race the new vrStart against
  // A's onstop, losing A's blob to an empty _vrChunks array.
  let _vrStopPromise   = null;

  // Per-container blob URL for playback (keep separate per widget so
  // pressing ▶ on Q1 plays Q1's recording, not whichever was last loaded).
  const _vrSavedBlobUrls = new WeakMap();

  // IndexedDB key per container. Each .voice-recorder-container needs a
  // `data-recorder-id` attribute (e.g. "polished", "q1", "map-1") so its
  // recording is stored at a unique key like "Week_01:q1".
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
    const allEntries = await vrListEntriesByAge(db);
    // Round 42 — pre-filter out the just-recorded entry instead of using
    // `continue` to skip it inside the loop. Previously, when the exempt
    // entry was among the oldest, `entries.shift()` already removed it from
    // the in-memory array before `continue` ran, so `entries.length` could
    // drop below cap while the exempt entry stayed in IndexedDB — using up
    // a slot that should have been evicted from elsewhere. Filtering up
    // front keeps the slot accounting correct.
    const candidates = allEntries.filter(e => e.key !== exemptKey);
    // remaining = total entries currently on disk (exempt + candidates).
    // We evict candidates until remaining drops to / below the cap.
    let remaining = allEntries.length;
    let evicted = 0;

    // Pass 1 — hard count cap.
    while (remaining > VR_MAX_RECORDINGS && candidates.length > 0) {
      const oldest = candidates.shift();
      await vrDeleteByKey(db, oldest.key);
      evicted++;
      remaining--;
    }

    // Pass 2 — soft quota cap (only if API tells us we're tight).
    // Stop with at least the exempt + 1 candidate so the user keeps SOME
    // history rather than scorching the whole DB on a tight-quota device.
    let ratio = await vrQuotaUsageRatio();
    while (ratio !== null && ratio > (1 - VR_QUOTA_HEADROOM) && candidates.length > 0 && remaining > 1) {
      const oldest = candidates.shift();
      await vrDeleteByKey(db, oldest.key);
      evicted++;
      remaining--;
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

    // `has-recording` is a discrete visual indicator (small green dot via
    // CSS ::after) showing students at-a-glance whether a saved recording
    // exists for this section. Toggled here so every state transition
    // updates the indicator atomically.
    container.classList.toggle('has-recording', state === 'saved');

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
    // If another widget is recording, stop it first AND wait for its
    // onstop to fully drain. Round 42: previously vrStart reassigned
    // _vrChunks / _vrStartedAt / _vrPausedTotal immediately after .stop(),
    // racing against the previous recorder's async onstop (which reads
    // those same globals to build its Blob). The result was a lost blob
    // or chunks mixed across recordings. The promise below is set inside
    // the onstop wrapper farther down and resolves only after the prior
    // recording is fully saved.
    if (_activeContainer && _activeContainer !== container && _vrMediaRecorder
        && _vrMediaRecorder.state !== 'inactive') {
      _vrMediaRecorder.stop();
      if (_vrStopPromise) {
        try { await _vrStopPromise; }
        catch (e) { /* prior save errored; we still want to start the new one */ }
      }
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
    // Round 42 — wrap onstop in a Promise so the next vrStart() can await
    // the prior save's completion. The Promise resolves in a `finally` so
    // even a save failure unblocks the next recording start (we'd rather
    // surface the toast and let the user continue than deadlock the UI).
    _vrStopPromise = new Promise((resolve) => {
      _vrMediaRecorder.onstop = async () => {
        try {
          const blob = new Blob(_vrChunks, { type: _vrMediaRecorder.mimeType || 'audio/webm' });
          const elapsed = Date.now() - _vrStartedAt - _vrPausedTotal;
          // Round 22 (2026-05-03): show explicit save-confirmation toast.
          // Previously the save was silent; users couldn't tell whether ⏹
          // had actually persisted the recording before they navigated away.
          let saved = false;
          try {
            await vrSaveBlob(container, blob, elapsed);
            saved = true;
          } catch (e) {
            console.error('vrSave', e);
            _showEmailToast('⚠ Save failed — check browser storage', 3500);
          }
          if (saved) _showEmailToast('Recording saved ✓', 1800);
          if (_vrStream) { _vrStream.getTracks().forEach(t => t.stop()); _vrStream = null; }
          clearInterval(_vrTimerId); _vrTimerId = 0;
          _activeContainer = null;
          vrLoadIntoUi(container);
        } finally {
          resolve();
        }
      };
    });
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

  // ====================================================================
  // EMAIL RECORDINGS — gather all IndexedDB recordings for THIS lesson,
  // ZIP them client-side, trigger a download, and open the user's email
  // client via mailto: with a pre-filled subject + body. Student attaches
  // the zip manually in their mail client.
  //
  // Public API: ns.emailLessonRecordings()
  // No backend / no network. All client-side.
  // ====================================================================

  const _EMAIL_LS_KEY = 'lessonEmailRecipient';
  const _EMAIL_VALID_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  // Pretty week number from LESSON_KEY (e.g. "Week_05" -> 5).
  function _emailWeekNumber() {
    const m = /^Week_?(\d+)/i.exec(LESSON_KEY || '');
    return m ? parseInt(m[1], 10) : null;
  }

  // Course label for subject line — IELTS vs IGCSE based on hostname.
  function _emailCourseLabel() {
    const host = (location && location.hostname) || '';
    if (host.indexOf('igcse') !== -1) return 'IGCSE';
    return 'IELTS';
  }

  // Walk all IndexedDB recordings for THIS lesson (keys "Week_NN:<id>")
  // and return [{recorderId, blob, createdAt}] sorted by createdAt asc.
  async function _emailEnumerateRecordings() {
    const db = await vrOpenDB();
    const prefix = `${LESSON_KEY}:`;
    // Round 22 (2026-05-03): debug logging — surfaces what the email
    // function actually sees in IndexedDB. Open DevTools → Console
    // before clicking the email button to see what's matched/skipped.
    console.info('[email] enumerate: LESSON_KEY=%s prefix=%s', LESSON_KEY, prefix);
    return new Promise((resolve, reject) => {
      const tx = db.transaction(VR_STORE, 'readonly');
      const store = tx.objectStore(VR_STORE);
      const req = store.openCursor();
      const out = [];
      const skipped = [];
      req.onsuccess = () => {
        const cur = req.result;
        if (cur) {
          const key = String(cur.key || '');
          if (key.startsWith(prefix)) {
            const v = cur.value || {};
            if (v.blob) {
              out.push({
                recorderId: key.slice(prefix.length),
                blob: v.blob,
                createdAt: v.createdAt || 0,
              });
            }
          } else {
            skipped.push(key);
          }
          cur.continue();
        } else {
          out.sort((a, b) => a.createdAt - b.createdAt);
          console.info('[email] enumerate: matched %d recording(s):',
            out.length,
            out.map(r => `${r.recorderId} (${new Date(r.createdAt).toISOString().slice(0,10)})`));
          if (skipped.length) {
            console.info('[email] enumerate: skipped %d non-matching key(s) (other lessons):',
              skipped.length, skipped);
          }
          resolve(out);
        }
      };
      req.onerror = () => reject(req.error);
    });
  }

  // Filename: <LESSON_KEY>_<recorderId>_YYYY-MM-DD.webm
  // Sanitizes recorderId so weird chars don't break filesystems.
  function _emailFilenameFor(rec) {
    const d = new Date(rec.createdAt || Date.now());
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const safeId = String(rec.recorderId || 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
    return `${LESSON_KEY}_${safeId}_${yyyy}-${mm}-${dd}.webm`;
  }

  // Get recipient: first call prompts; subsequent reads from localStorage.
  // Returns null if user cancels.
  function _emailGetRecipient() {
    let saved = '';
    try { saved = localStorage.getItem(_EMAIL_LS_KEY) || ''; } catch (_) { /* private mode */ }
    if (saved && _EMAIL_VALID_RE.test(saved)) return saved;
    let attempts = 0;
    while (attempts++ < 3) {
      const msg = attempts === 1
        ? "Enter the email address to send your recordings to:"
        : "That doesn't look like a valid email. Please try again (or Cancel to abort):";
      const entry = window.prompt(msg, saved);
      if (entry === null) return null; // user cancelled
      const trimmed = entry.trim();
      if (_EMAIL_VALID_RE.test(trimmed)) {
        try { localStorage.setItem(_EMAIL_LS_KEY, trimmed); } catch (_) {}
        return trimmed;
      }
      saved = trimmed; // keep for next prompt
    }
    return null;
  }

  // ----- ZIP encoder (STORED-mode, no compression) -----
  // Audio is already Opus-compressed; DEFLATE adds ~1-2%, not worth the
  // 95KB JSZip dependency. Format ref: PKWARE APPNOTE.TXT 4.5.

  let _crcTable = null;
  function _ensureCrcTable() {
    if (_crcTable) return _crcTable;
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      t[n] = c >>> 0;
    }
    _crcTable = t;
    return t;
  }
  function _crc32(bytes) {
    const t = _ensureCrcTable();
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) {
      crc = (t[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8)) >>> 0;
    }
    return (crc ^ 0xFFFFFFFF) >>> 0;
  }

  // entries: [{name: string, data: Uint8Array}] -> Blob('application/zip')
  async function _emailBuildZip(entries) {
    const enc = new TextEncoder();
    const parts = [];
    const central = [];
    let offset = 0;

    const now = new Date();
    const dosTime = ((now.getHours() & 0x1F) << 11)
                  | ((now.getMinutes() & 0x3F) << 5)
                  | ((now.getSeconds() >> 1) & 0x1F);
    const dosDate = (((now.getFullYear() - 1980) & 0x7F) << 9)
                  | (((now.getMonth() + 1) & 0x0F) << 5)
                  | (now.getDate() & 0x1F);

    for (const e of entries) {
      const nameBytes = enc.encode(e.name);
      const data = e.data;
      const crc = _crc32(data);
      const sz = data.length;

      // Local file header
      const lfh = new Uint8Array(30 + nameBytes.length);
      const lv = new DataView(lfh.buffer);
      lv.setUint32(0, 0x04034b50, true);
      lv.setUint16(4, 20, true);
      lv.setUint16(6, 0, true);
      lv.setUint16(8, 0, true);  // STORED
      lv.setUint16(10, dosTime, true);
      lv.setUint16(12, dosDate, true);
      lv.setUint32(14, crc, true);
      lv.setUint32(18, sz, true);
      lv.setUint32(22, sz, true);
      lv.setUint16(26, nameBytes.length, true);
      lv.setUint16(28, 0, true);
      lfh.set(nameBytes, 30);
      parts.push(lfh, data);

      // Central directory entry
      const cdh = new Uint8Array(46 + nameBytes.length);
      const cv = new DataView(cdh.buffer);
      cv.setUint32(0, 0x02014b50, true);
      cv.setUint16(4, 20, true);
      cv.setUint16(6, 20, true);
      cv.setUint16(8, 0, true);
      cv.setUint16(10, 0, true);
      cv.setUint16(12, dosTime, true);
      cv.setUint16(14, dosDate, true);
      cv.setUint32(16, crc, true);
      cv.setUint32(20, sz, true);
      cv.setUint32(24, sz, true);
      cv.setUint16(28, nameBytes.length, true);
      cv.setUint16(30, 0, true);
      cv.setUint16(32, 0, true);
      cv.setUint16(34, 0, true);
      cv.setUint16(36, 0, true);
      cv.setUint32(38, 0, true);
      cv.setUint32(42, offset, true);
      cdh.set(nameBytes, 46);
      central.push(cdh);

      offset += lfh.length + sz;
    }

    const cdSize = central.reduce((s, c) => s + c.length, 0);
    const cdOffset = offset;
    const eocd = new Uint8Array(22);
    const ev = new DataView(eocd.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(4, 0, true);
    ev.setUint16(6, 0, true);
    ev.setUint16(8, entries.length, true);
    ev.setUint16(10, entries.length, true);
    ev.setUint32(12, cdSize, true);
    ev.setUint32(16, cdOffset, true);
    ev.setUint16(20, 0, true);

    return new Blob([...parts, ...central, eocd], { type: 'application/zip' });
  }

  // Programmatic <a download> click — works without a permission prompt
  // because we're inside a user-gesture handler (the button click).
  function _emailDownloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      try { document.body.removeChild(a); } catch (_) {}
      URL.revokeObjectURL(url);
    }, 1000);
  }

  // Open mailto: via a synchronous <a>.click() so the OS protocol handler
  // intercepts before navigation. Avoids window.open() (which the popup
  // blocker can silently kill if any setTimeout has broken the
  // user-gesture chain). The current page does NOT navigate — the mail
  // client just opens. If there's no registered mail client, the click
  // is a no-op (the completion panel below provides a re-open button).
  function _emailOpenMailto(url) {
    const a = document.createElement('a');
    a.href = url;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { try { document.body.removeChild(a); } catch (_) {} }, 200);
  }

  // Completion panel — shown after successful download + mailto trigger.
  // Acts as a fallback for: (1) browsers that blocked the mailto, (2) users
  // with no default mail client (very common — they use webmail). The
  // "Re-open email" button retries the mailto in a fresh user gesture.
  function _showEmailCompletionPanel(recipient, zipName, mailtoUrl) {
    const existing = document.querySelector('.email-completion-panel');
    if (existing) existing.remove();
    const panel = document.createElement('div');
    panel.className = 'email-completion-panel';
    panel.innerHTML = ''
      + '<div class="ecp-icon">✉️</div>'
      + '<div class="ecp-content">'
      +   '<div class="ecp-line"><strong>Downloaded:</strong> <span class="ecp-mono">' + _emailEsc(zipName) + '</span></div>'
      +   '<div class="ecp-line"><strong>Send to:</strong> ' + _emailEsc(recipient) + '</div>'
      +   '<div class="ecp-hint">Your email program should have opened. If not, click <em>Re-open email</em> below — or copy the details and paste into Gmail / Outlook web.</div>'
      +   '<div class="ecp-actions">'
      +     '<button class="ecp-reopen" type="button">Re-open email</button>'
      +     '<button class="ecp-copy"   type="button">Copy details</button>'
      +     '<button class="ecp-close"  type="button">Close</button>'
      +   '</div>'
      + '</div>';
    document.body.appendChild(panel);
    panel.querySelector('.ecp-close').onclick = () => panel.remove();
    panel.querySelector('.ecp-reopen').onclick = () => _emailOpenMailto(mailtoUrl);
    panel.querySelector('.ecp-copy').onclick = async (ev) => {
      // Decode the mailto URL into copy-friendly text
      const u = new URL(mailtoUrl);
      const subject = decodeURIComponent((u.search.match(/[?&]subject=([^&]*)/) || [,''])[1]);
      const body = decodeURIComponent((u.search.match(/[?&]body=([^&]*)/) || [,''])[1]);
      const text = `To: ${recipient}\nSubject: ${subject}\n\n${body}`;
      try {
        await navigator.clipboard.writeText(text);
        const btn = ev.currentTarget;
        const orig = btn.textContent;
        btn.textContent = '✓ Copied';
        setTimeout(() => { btn.textContent = orig; }, 1600);
      } catch (e) {
        _showEmailToast('Copy failed — your browser blocked clipboard access.');
      }
    };
    // Auto-dismiss after 90s in case the student forgets it's there
    setTimeout(() => { if (panel.parentNode) panel.remove(); }, 90000);
  }

  function _emailEsc(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  function _emailComposeMailto(recipient, recordings, weekNum) {
    const course = _emailCourseLabel();
    const subject = `${course} Week ${weekNum} Speaking Recordings`;
    const today = new Date().toISOString().slice(0, 10);
    const lines = [
      `Hi,`,
      ``,
      `Please find my Week ${weekNum} ${course} speaking recordings.`,
      ``,
      `Attached: ${LESSON_KEY}_recordings_${today}.zip (${recordings.length} recording${recordings.length === 1 ? '' : 's'})`,
      ``,
      `Filenames inside the zip:`,
    ];
    for (const r of recordings) lines.push(`  • ${_emailFilenameFor(r)}`);
    lines.push('', '(Please attach the downloaded zip — your email program should have started a new message.)');
    let body = lines.join('\n');
    if (body.length > 1500) body = body.slice(0, 1500) + '\n…';
    return `mailto:${encodeURIComponent(recipient)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  }

  // Floating bottom-center toast.
  function _showEmailToast(text, ms = 3000) {
    let toast = document.querySelector('.email-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'email-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    requestAnimationFrame(() => toast.classList.add('visible'));
    clearTimeout(toast._dismissTimer);
    toast._dismissTimer = setTimeout(() => toast.classList.remove('visible'), ms);
  }

  // Round 22 (2026-05-03): preflight confirmation before zipping. Lists
  // every recording that's about to be sent so users can spot stale ones
  // from prior sessions BEFORE the zip download fires. Returns a Promise
  // that resolves to true if user clicked Send, false if Cancel.
  function _showEmailPreflightPanel(recordings) {
    return new Promise((resolve) => {
      // Remove any existing preflight panel
      const existing = document.querySelector('.email-preflight-panel');
      if (existing) existing.remove();

      const panel = document.createElement('div');
      panel.className = 'email-preflight-panel';

      const heading = document.createElement('div');
      heading.className = 'epp-heading';
      const n = recordings.length;
      heading.textContent = `Found ${n} recording${n === 1 ? '' : 's'} for this week:`;
      panel.appendChild(heading);

      const list = document.createElement('ul');
      list.className = 'epp-list';
      for (const r of recordings) {
        const li = document.createElement('li');
        const tick = document.createElement('span');
        tick.className = 'epp-tick';
        tick.textContent = '✓';
        const id = document.createElement('strong');
        id.textContent = r.recorderId;
        const date = document.createElement('span');
        date.className = 'epp-date';
        const d = new Date(r.createdAt || Date.now());
        date.textContent = `recorded ${d.toLocaleDateString(undefined, {month: 'short', day: 'numeric'})}`;
        li.appendChild(tick);
        li.appendChild(id);
        li.appendChild(date);
        list.appendChild(li);
      }
      panel.appendChild(list);

      const hint = document.createElement('div');
      hint.className = 'epp-hint';
      hint.textContent = 'To remove an old recording: close this and use the 🗑 button on its widget.';
      panel.appendChild(hint);

      const actions = document.createElement('div');
      actions.className = 'epp-actions';
      const cancelBtn = document.createElement('button');
      cancelBtn.type = 'button';
      cancelBtn.className = 'epp-cancel';
      cancelBtn.textContent = 'Cancel';
      cancelBtn.onclick = () => { panel.remove(); resolve(false); };
      const sendBtn = document.createElement('button');
      sendBtn.type = 'button';
      sendBtn.className = 'epp-send';
      sendBtn.textContent = `Send all ${n}`;
      sendBtn.onclick = () => { panel.remove(); resolve(true); };
      actions.appendChild(cancelBtn);
      actions.appendChild(sendBtn);
      panel.appendChild(actions);

      document.body.appendChild(panel);
      sendBtn.focus();
    });
  }

  ns.emailLessonRecordings = async function () {
    let recordings;
    try {
      recordings = await _emailEnumerateRecordings();
    } catch (e) {
      console.error('emailLessonRecordings: enumerate failed', e);
      _showEmailToast('Could not read recordings (browser storage error).');
      return;
    }
    if (!recordings || recordings.length === 0) {
      _showEmailToast('No recordings saved yet for this week.');
      return;
    }

    // Round 22: preflight panel — let user see what's about to be sent
    // (avoids the "I made 1 recording but 3 zipped" confusion when stale
    // recordings from prior sessions are still in IndexedDB).
    const proceed = await _showEmailPreflightPanel(recordings);
    if (!proceed) return;

    const recipient = _emailGetRecipient();
    if (!recipient) return;

    const entries = [];
    for (const r of recordings) {
      const ab = await r.blob.arrayBuffer();
      entries.push({ name: _emailFilenameFor(r), data: new Uint8Array(ab) });
    }

    const zipBlob = await _emailBuildZip(entries);
    const today = new Date().toISOString().slice(0, 10);
    const zipName = `${LESSON_KEY}_recordings_${today}.zip`;
    _emailDownloadBlob(zipBlob, zipName);

    const weekNum = _emailWeekNumber();
    const mailtoUrl = _emailComposeMailto(recipient, recordings, weekNum);
    // Synchronous <a>.click() in the same user-gesture frame — no popup blocker.
    _emailOpenMailto(mailtoUrl);
    // Show completion panel with "Re-open email" + "Copy details" fallbacks
    // for students whose Windows machine has no default mail client.
    _showEmailCompletionPanel(recipient, zipName, mailtoUrl);
  };

  // Test hooks (only used by Playwright/Node smoke tests)
  ns.__emailBuildZip = _emailBuildZip;
  ns.__emailFilenameFor = _emailFilenameFor;

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ns.__init === 'function') ns.__init();
  });

})();
