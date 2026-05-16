// 04_tts_playback.js - sentence-paced TTS playback + per-row state.
// Loaded after 03_tts_voice.js (pickVoice, ensureTtsWarmup, isWeChatBrowser,
// wechatFallbackAlert) and 02_dom_helpers.js (stripChineseGloss,
// extractReadableText). Reads closure state from 01_state.js (_rowState,
// _currentRow, _prefs.lang/Gender/Slow, DEFAULT_RATE, SLOW_RATE).
// Forward-references ensureWordsWrapped() from 05_word_wrap.js — safe
// because function declarations are hoisted across the concatenated IIFE.
//
// Exports to ns.*:
//   speakText, replaySentence, nextSentence, prevSentence,
//   speakElement, speakElementById, listenPolished,
//   stopSpeaking, pauseSpeaking

  // Round 53 — collapse the duplicated "_prefs.slow ? SLOW_RATE : rate"
  // pattern. Two call sites (_playCurrentSentence, speakText) now use this.
  function effectiveRate(rate) {
    return _prefs.slow ? SLOW_RATE : rate;
  }

  // Round 53 — collapse the duplicated WeChat-guard at the top of
  // speakText and speakElement. Returns true if synthesis may proceed,
  // false if a WeChat fallback was shown (caller should bail).
  function assertSpeakable() {
    if (isWeChatBrowser()) { wechatFallbackAlert(); return false; }
    if (!('speechSynthesis' in window)) return false;
    return true;
  }

  // Round 53 — consolidates 3 copies of the gender-toggle dance:
  //   - listenPolished's 'gender' case
  //   - btnGender.onclick inside injectListenButtons
  //   - refreshGenderBtn() inside injectListenButtons
  function _toggleGender(rowEl) {
    // Round 55 (2026-05-17): selector-only — does NOT replay. Previously
    // this auto-replayed the current sentence so the teacher could hear
    // the voice change immediately, but per user feedback the gender
    // button (and accent / slow buttons) should configure the next
    // playback only. The next ▶ replay / next / prev tap will use the
    // new voice. _rowEl_ retained as a parameter for callers; unused.
    _prefs.gender = _prefs.gender === 'male' ? 'female' : 'male';
    _syncGenderButtons();
  }

  function _syncGenderButtons() {
    const isMale = _prefs.gender === 'male';
    document.querySelectorAll('.tts-btn.gender').forEach(b => {
      b.classList.toggle('male',   isMale);
      b.classList.toggle('female', !isMale);
      b.textContent = isMale ? '👨' : '👩';
    });
  }

  // Round 53 — consolidates 2 copies of the slow-toggle dance:
  //   - listenPolished's 'slow' case
  //   - btnSlow.onclick inside injectListenButtons
  function _toggleSlow(rowEl) {
    // Round 55 (2026-05-17): selector-only — does NOT replay. Same
    // rationale as _toggleGender: the speed selector configures the next
    // playback only, never triggers playback itself. _rowEl_ retained
    // as a parameter for callers; unused.
    _prefs.slow = !_prefs.slow;
    _syncSlowButtons();
  }

  function _syncSlowButtons() {
    document.querySelectorAll('.tts-btn.slow').forEach(b => {
      b.classList.toggle('active', _prefs.slow);
      b.title = _prefs.slow
        ? 'Slow mode: ON (0.72×) — click for normal speed / 慢速模式：开'
        : 'Slow mode: OFF (0.85×) — click for slow speed / 慢速模式：关';
    });
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
    u.rate = effectiveRate(rateOverride || st.rate || DEFAULT_RATE);
    const v = pickVoice(st.lang, _prefs.gender);  // Round 33
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
    if (!assertSpeakable()) return;
    if (!text || !String(text).trim()) return;

    // No row → vocab-click / single-shot path. Speak as one utterance,
    // no sentence pacing, no row state. Matches old behaviour for
    // attachWordClicks().
    if (!rowEl) {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text));
      u.lang = lang;
      // Round 39 — vocab single-clicks also respect the global slow toggle.
      u.rate = effectiveRate(rate);
      const v = pickVoice(lang, _prefs.gender);  // Round 33
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

  // speakElement / speakElementById — wrap words in <span> for karaoke,
  // split text into sentences, and play sentence 0. Subsequent transport
  // commands (replay / next / prev / slow) re-use the wrapped spans.
  // The optional `rowElOverride` arg lets callers pin the WeakMap state
  // to a specific .listen-row element (used by injectListenButtons so
  // its prev/next/replay/slow buttons share state with the speaking text).
  ns.speakElement = function (el, lang = 'en-GB', rate = DEFAULT_RATE, rowElOverride = null) {
    if (!assertSpeakable()) return;
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
    _prefs.lang = lang;
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
        // Round 55 (2026-05-17): selector-only — does NOT play. Previously
        // calling speakElementById here started a fresh playback. Per user
        // feedback the accent picker just updates the preference; the next
        // ▶ replay tap will use the chosen accent.
        _prefs.lang = which;
        setActiveAccent(row, which);
        break;
      case 'slow': {
        _toggleSlow(row);
        break;
      }
      case 'replay': {
        // Round 55 (2026-05-17) — fix companion to Batch C: same as the
        // model-box listen-row's btnReplay (see 06_word_click.js). If the
        // polished-output row's sentence list is empty (because UK/US no
        // longer initialise state), auto-initialise via speakElementById
        // so the first ▶ click plays sentence 0. Subsequent ▶ clicks
        // replay the current sentence.
        const st = getRowState(row);
        if (!st.sentences || !st.sentences.length) {
          ns.speakElementById('polished-output', _prefs.lang || 'en-GB', DEFAULT_RATE);
        } else {
          ns.replaySentence(row, false);
        }
        break;
      }
      case 'prev':   ns.prevSentence(row);          break;
      case 'next':   ns.nextSentence(row);          break;
      case 'gender': {
        _toggleGender(row);
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
