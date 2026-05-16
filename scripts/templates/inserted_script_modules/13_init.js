  // 13_init.js - Bootstrap glue: orchestrates all modules at DOMContentLoaded.
  // Defines ns.__init (wires the draft input listener, runs initial word-count,
  // restores saved draft, injects Listen buttons, attaches word-click handlers,
  // probes FC health for the offline badge, and starts the voice recorder) and
  // registers the DOMContentLoaded listener that fires it. Also houses the
  // checkHealth() bootstrap helper used by __init.
  // Exports to ns: __init.
  // Depends on:
  //   - 01_state.js: AI_ENDPOINT
  //   - 05_word_wrap.js: ns.updateWordCount, attachWordClicks
  //   - 06_word_click.js: injectListenButtons
  //   - 08_draft_persistence.js: loadDraft, debouncedSave
  //   - 11_voice_recorder.js: initVoiceRecorder

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
  // Q-prompt typography enhancer (Round 55 design pass — 2026-05-17)
  //
  // The canonical cue-card prompt — e.g. "Describe a family member who
  // you are proud of. You should say: Who… When… What… And…" —
  // historically rendered as one flat run of text, with no visual
  // distinction between the MAIN question and the sub-prompts. This
  // function inspects each .q-prompt and, when it matches the cue-card
  // pattern, splits the content into <span class="q-main"> (the topic
  // sentence) and <span class="q-subs"> (the "You should say:" line).
  // CSS in inserted_css.css then styles them at heading weight vs.
  // small-text, restoring the visual hierarchy a printed cue card has.
  //
  // Runs BEFORE attachWordClicks so the word-wrap walker descends into
  // the newly-split spans and wraps their words for click-to-speak.
  // ====================================================================

  function enhanceQPrompts() {
    // Match: "First sentence ending in period.  You should say: ..."
    // The first group is lazy so it stops at the FIRST period — protects
    // against multi-sentence topic descriptions misaligning the split.
    const splitRe = /^([^.<>]+?\.)\s+(You should say:[\s\S]*)$/i;
    document.querySelectorAll('.q-prompt').forEach((el) => {
      if (el.dataset.qPromptEnhanced === '1') return;
      const inner = el.innerHTML.trim();
      const m = splitRe.exec(inner);
      if (!m) return;  // not the cue-card pattern; leave untouched
      el.innerHTML = `<span class="q-main">${m[1]}</span><span class="q-subs">${m[2]}</span>`;
      // Strip legacy inline overrides so the new .q-main / .q-subs CSS
      // rules can take effect. The canonical brainstorming-map div
      // carries inline `font-size:0.9em; color:#444; padding-left:15px`
      // which collapses the new hierarchy.
      el.style.fontSize  = '';
      el.style.color     = '';
      el.style.paddingLeft = '';
      el.dataset.qPromptEnhanced = '1';
    });
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
    enhanceQPrompts();    // Round 55 — split cue-card prompts BEFORE word-wrap
    injectListenButtons();
    attachWordClicks();
    checkHealth();
    initVoiceRecorder();  // no-op if no .voice-recorder-container on the page
  };

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ns.__init === 'function') ns.__init();
  });

