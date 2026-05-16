  // 10_ai_correction.js - AI correction flow: fetch-with-retry, status UI,
  // and the ns.correctEssay / ns.editAgain orchestration.
  // Wraps the fetch to the FC endpoint with pre-request jitter +
  // exponential-backoff retry to survive start-of-class herd traffic, then
  // sanitises the response, renders the red-pen diff over the draft, and
  // toggles the polished/correct/edit-again button states.
  // Exports to ns: correctEssay, editAgain.
  // Depends on:
  //   - _header.js: AI_ENDPOINT
  //   - 01_state.js: AI_FETCH_MAX_ATTEMPTS, AI_FETCH_BASE_BACKOFF_MS,
  //                  AI_FETCH_JITTER_MS, AI_FETCH_TIMEOUT_MS
  //   - 08_draft_persistence.js: saveDraft, enablePolishedListenButtons,
  //                              disablePolishedListenButtons
  //   - 09_diff_markup.js: wordDiff, coalesceAdjacentSameOp, classifyPairs,
  //                        renderMarkup

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

