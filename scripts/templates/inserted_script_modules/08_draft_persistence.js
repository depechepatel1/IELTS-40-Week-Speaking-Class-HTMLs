  // 08_draft_persistence.js - draft auto-save, restore, and word-count widget.
  // Auto-saves the student's draft + polished output + diff markup to
  // localStorage on every keystroke (debounced 500ms), and restores them on
  // page load so a refresh never loses work. Also drives the live word-count
  // traffic-light and the enable/disable state of the polished-output TTS
  // buttons.
  // Exports to ns: updateWordCount, clearDraft.
  // Depends on:
  //   - 01_state.js: STORAGE_KEY, _saveTimer
  //   - (used elsewhere later): ns.updateWordCount, enablePolishedListenButtons

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

