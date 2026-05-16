// 06_word_click.js - listen-button injection + word-level click-to-speak.
// Loaded after 05_word_wrap.js (ensureWordsWrapped), 04_tts_playback.js
// (ns.speakText, ns.speakElement, ns.replaySentence, ns.prevSentence,
// ns.nextSentence, getRowState), and 02_dom_helpers.js (isChineseGloss,
// stripChineseGloss, extractReadableText). Reads closure state from
// 01_state.js (WORD_CLICK_SCOPE, DEFAULT_RATE, _prefs.lang/Gender/Slow).
// Forward-references showIpaTooltip() from 07_ipa_tooltip.js (hoisted).
//
// Exports (closure-local, no ns.*):
//   injectListenButtons() - per-card 7-button transport row (gender, UK,
//     US, slow, prev, replay, next) on every .model-box card.
//   attachWordClicks()    - two-part word click handler:
//     Part 1 (in WORD_CLICK_SCOPE): eager wrap → delegated click on .tts-word
//     Part 2 (legacy .vocab-table strong, .sec-2 .item-text strong): per-<strong> binding

  // ====================================================================
  // Listen-button injection + clickable vocab + IPA tooltip
  // (spec §8.7, §8.9)
  // ====================================================================

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
      // every click and a global `_prefs.gender` drives every
      // pickVoice() call across the page.
      // Layout: [gender | UK | US | slow] [sentence counter] [prev | replay | next]
      row.innerHTML = `
        <button class="tts-btn gender female" title="Toggle voice gender / 切换男女声">👩</button>
        <button class="tts-btn uk active" title="UK voice / 英音">🇬🇧</button>
        <button class="tts-btn us"        title="US voice / 美音">🇺🇸</button>
        <button class="tts-btn slow"      title="Slow replay / 慢速重播本句" disabled>🐢</button>
        <span    class="sentence-counter" title="Current sentence / 当前句"></span>
        <button class="tts-btn prev"      title="Previous sentence / 上一句" disabled>⏮</button>
        <button class="tts-btn replay"    title="Play / 播放">▶</button>
        <button class="tts-btn next"      title="Next sentence / 下一句" disabled>⏭</button>
      `;
      // Round 55 (2026-05-17) fix #2 — ▶ replay is the ENTRY POINT for
      // first-time play. Previously injected with `disabled`, which
      // suppressed the onclick handler (browser blocks events on disabled
      // buttons). With Batch C making UK/US selector-only, ▶ had to
      // start enabled OR users could never play anything. Prev / Next /
      // Slow stay disabled-by-default because they legitimately can't
      // operate without an existing sentence list; setRowTransport-
      // ButtonStates flips them on once speakElement populates st.sentences.
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
      _syncGenderButtons();

      // Round 39 — same mirror pattern for the persistent slow toggle.
      // If the teacher enabled slow mode earlier (e.g. on the previous
      // card before this row was injected by lazy scroll), this fresh
      // button must visibly show the active state from first render.
      btnSlow.classList.toggle('active', _prefs.slow);
      btnSlow.title = _prefs.slow
        ? 'Slow mode: ON (0.72×) — click for normal speed / 慢速模式：开'
        : 'Slow mode: OFF (0.85×) — click for slow speed / 慢速模式：关';

      // Round 55 (2026-05-17): UK / US accent buttons are now selector-only.
      // Previously they called speakElement which both set _prefs.lang AND
      // started playback. Per user feedback the accent picker should
      // configure the next playback, not trigger one. setActiveAccent
      // updates the .active class on this row's buttons so the choice is
      // visible; _prefs.lang is the global preference read by every
      // subsequent speakElement / speakText / replaySentence call.
      btnUK.onclick = () => { _prefs.lang = 'en-GB'; setActiveAccent(row, 'en-GB'); };
      btnUS.onclick = () => { _prefs.lang = 'en-US'; setActiveAccent(row, 'en-US'); };
      // Round 39 — 🐢 is now a STICKY GLOBAL TOGGLE, not a one-shot replay.
      // Flipping it broadcasts the new state to every visible slow button
      // on the page so all cards show the same on/off indicator. Title
      // attribute updates to make the current state explicit. If a sentence
      // is already loaded on this row, replay it so the teacher hears the
      // new rate immediately.
      btnSlow.onclick   = () => _toggleSlow(row);
      btnPrev.onclick   = () => ns.prevSentence(row);
      btnReplay.onclick = () => {
        // Round 55 (2026-05-17) — fix companion to Batch C: when the accent
        // buttons (UK/US) became selector-only, they stopped initialising
        // the row's sentence state. That meant clicking ▶ replay before
        // any UK/US click would find an empty sentence list and bail out
        // (no audio). Auto-initialise here so ▶ alone is enough to play
        // sentence 0 the first time, and subsequent ▶ taps replay the
        // current sentence via the usual replaySentence path.
        const st = getRowState(row);
        if (!st.sentences || !st.sentences.length) {
          ns.speakElement(box, _prefs.lang || 'en-GB', DEFAULT_RATE, row);
        } else {
          ns.replaySentence(row, /* slow= */ false);
        }
      };
      btnNext.onclick   = () => ns.nextSentence(row);
      // Round 33 — gender toggle. Flips global state, refreshes EVERY visible
      // gender button on the page (so all cards stay in sync), and replays
      // the current sentence so the teacher hears the new voice immediately.
      // If the row hasn't started speaking yet, just toggle silently — the
      // next UK/US click will pick up the new gender.
      btnGender.onclick = () => _toggleGender(row);

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
        ns.speakText(word, _prefs.lang, DEFAULT_RATE, null, clearFlash);
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
        ns.speakText(word, _prefs.lang);
        showIpaTooltip(word, ev.pageX, ev.pageY);
      });
    });
  }
