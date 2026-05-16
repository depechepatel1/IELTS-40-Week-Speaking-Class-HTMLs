// 03_tts_voice.js - TTS voice selection + warmup + platform sniffing.
// Loaded after 01_state.js (closure state: _voiceCache, _ttsWarmedUp,
// FEMALE_NEURAL_*, MALE_NEURAL_*, IOS_PREMIUM_NAMES, FEMALE/MALE_NEURAL_ANY).
// Exports (to IIFE closure, no ns.*):
//   ensureTtsWarmup(voice, lang) - silent priming utterance, once per page
//   isIOS()                     - iPad/iPhone/iPod detection (incl. iPadOS)
//   pickVoice(lang, gender)     - scored picker over getVoices() with cache
//   isWeChatBrowser()           - WeChat in-app browser detection
//   wechatFallbackAlert()       - bilingual alert for WeChat users
// Also attaches the speechSynthesis.onvoiceschanged handler at IIFE-scope
// (clears _voiceCache + _ttsWarmedUp so async-loaded Edge neural voices
// upgrade the cache as soon as they arrive).

  // ====================================================================
  // TTS subsystem — Web Speech API with voice waterfall + karaoke
  // ====================================================================

  // Common female-neural voice names across Edge/Chrome (Windows), Safari/iOS,
  // and Android system voices. The regex covers both modern Edge "Natural"
  // voices and legacy macOS / iOS / Android voices known to sound natural.
  // Round 33 (2026-05-06) — added "Christopher" so Edge's Microsoft Christopher
  // Online (Natural) en-GB voice ranks correctly when the user selects the
  // male toggle. Christopher was the highest-quality Microsoft natural-male
  // voice missing from the list.
  // Round 45 (2026-05-13) — added Helena (Windows SAPI en-US female) so the
  // female toggle still wins on Windows installs lacking Edge neural voices.
  // Round 45 — added David, Mark, Paul, James (Windows SAPI en-US male
  // names) so the male toggle correctly selects a male voice on systems
  // without Edge neural voices. Previously David/Mark were unknown to the
  // regex and the male toggle silently lost — Zira (female) would still
  // win via the +5 cross-gender fallback bonus because no voice scored
  // the +25 male match.
  // iPad / iOS Siri-tier voice names. Apple ships these unmarked but they
  // are the higher-quality "Siri-style" voices on iOS. "Premium" / "Enhanced"
  // tags only appear once the user has manually downloaded the larger voice
  // file via Settings → Accessibility → Spoken Content → Voices.

  // Round 45 (2026-05-13) — cross-dialect gender regexes. Used by pickVoice
  // ONLY when the exact-dialect pool is empty and we've fallen back to
  // "any en-*" voices. Previously the gender scoring used the UK regex on a
  // US-only fallback pool (or vice versa); since the UK female list (Sonia,
  // Karen, Hazel…) doesn't include US female names (Zira, Aria, Samantha…),
  // every voice scored 0 on gender and the first-in-insertion-order voice
  // won — which on a Windows install with only en-US voices meant David
  // (male) could win an en-GB+female request. Unifying the regexes in the
  // fallback path restores deterministic gender selection.

  // Round 46 (2026-05-13) — TTS voice cache keyed by "lang|gender".
  // Guarantees both vocab-click (speakText) and model-answer
  // (_playCurrentSentence) paths reuse the SAME voice for any given
  // (lang, gender) combination. The cache is invalidated on the
  // onvoiceschanged event so async-loaded Edge neural voices upgrade
  // the cache as soon as they arrive.

  // Speech rates. Tuned for Chinese L2 listeners — 0.85 is the comfortable
  // default (matches what was previously the "slow" button rate); 0.72 is
  // the new "slow" — about 15% slower than the new default, useful when a
  // student wants to copy pronunciation word-by-word.

  // Round 31 (2026-05-06) — sticky "current teaching accent". Updated
  // every time `speakElement` runs (which is what UK/US buttons trigger
  // via listenPolished + injectListenButtons). Read by attachWordClicks
  // so single-word vocab/model-answer clicks play in the same accent the
  // teacher is currently using for the model-answer karaoke. Resets to
  // 'en-GB' on first page load so initial vocab clicks (before any
  // model-answer button is pressed) keep the historical default.

  // Round 33 (2026-05-06) — sticky "current teaching gender". Same
  // pattern as _prefs.lang. Toggled via the new Male/Female
  // button in the listen-row clusters; read by pickVoice() so that
  // every TTS surface (model-answer karaoke, polished-output, vocab
  // single-word clicks) speaks in whichever gender the teacher has
  // active. 'female' default keeps the historical voice on first load.

  // Round 39 (2026-05-11) — persistent slow-mode toggle. Replaces the
  // old "play this one sentence slowly, then snap back to normal"
  // behaviour. When true, EVERY TTS surface plays at SLOW_RATE: model
  // answers, vocabulary clicks, prev/next/replay, polished-output —
  // anywhere a rate is consulted, _prefs.slow wins. The slow
  // button (🐢) becomes a sticky on/off switch; its .active CSS class
  // is the user-visible "currently slow" indicator.

  // Round 33 — warmup flag. The first speak() call after page load
  // sometimes plays in the system default ("robotic") voice on Edge /
  // Chrome / Windows because the requested voice hasn't fully loaded
  // yet. Workaround: queue a silent (volume:0) priming utterance with
  // the same voice config BEFORE the real one. The real utterance then
  // plays with the correct voice. We only do this once per page load
  // since subsequent speak() calls reuse a primed engine.
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

  // Round 53 — single named helper for the voice-cache invalidation
  // pattern. Called from onvoiceschanged when Edge publishes its async
  // neural-voice list.
  function _invalidateVoiceState() {
    _voiceCache.clear();
    _ttsWarmedUp = false;
    try {
      console.info(
        `[TTS] voices changed; cache cleared; voices=` +
        (window.speechSynthesis.getVoices() || []).length
      );
    } catch (_) {}
  }

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
      _invalidateVoiceState();
    };
  }
