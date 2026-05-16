  // 11_voice_recorder.js - Voice recorder feature: per-container MediaRecorder
  // capture with IndexedDB persistence, LRU+quota eviction, 3-minute hard
  // cap, and pause/resume/play/delete UI plumbing. Wires up every
  // .voice-recorder-container present on the page.
  // Exports to ns: (none; called from 13_init via initVoiceRecorder()).
  // Depends on:
  //   - 01_state.js: LESSON_KEY, VR_DB_NAME, VR_STORE, VR_MAX_MS,
  //                  VR_MAX_RECORDINGS, VR_QUOTA_HEADROOM, _vrPersistRequested,
  //                  _activeContainer, _vrMediaRecorder, _vrChunks,
  //                  _vrStartedAt, _vrPausedTotal, _vrPausedAt, _vrTimerId,
  //                  _vrStream, _vrStopPromise, _vrSavedBlobUrls
  //   - 12_email_recordings.js: _showEmailToast (save-confirmation feedback)

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


  // Singleton recording state — only one mic recording at a time.
  // `_activeContainer` tracks WHICH container is currently recording so we
  // know where to save the blob and update the UI on stop.
  // Round 42 — handle on the previous recorder's onstop so a re-entrant
  // vrStart() can await the prior save fully before overwriting the
  // shared chunk/timing globals. Without this, a fast tap on widget B
  // while widget A is still recording could race the new vrStart against
  // A's onstop, losing A's blob to an empty _vrChunks array.

  // Per-container blob URL for playback (keep separate per widget so
  // pressing ▶ on Q1 plays Q1's recording, not whichever was last loaded).

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
    // updates the indicator atomically. Round 55 (2026-05-17): playback
    // also keeps the indicator on, since the saved recording still exists.
    container.classList.toggle('has-recording', state === 'saved' || state === 'playing');

    [btnRec, btnPause, btnStop, btnPlay, btnDelete].forEach(b => b && (b.hidden = true));
    if (btnRec) btnRec.classList.remove('recording');
    if (btnPause) btnPause.classList.remove('paused');
    if (btnPlay) btnPlay.classList.remove('playing');
    if (label) label.classList.remove('error');

    if (state === 'idle') {
      if (btnRec) { btnRec.hidden = false; btnRec.disabled = false; btnRec.title = 'Record / 录音'; }
      if (label) label.textContent = 'Click ⏺ to record (3:00 max)';
    } else if (state === 'recording') {
      // Round 55 (2026-05-17): record button stays enabled and clicking it
      // STOPS the recording — replaces the previous flow that required
      // students to find the separate ⏹ stop button. The stop button is
      // now reserved exclusively for stopping PLAYBACK and is hidden
      // here. Pause stays available for mid-recording breaks.
      if (btnRec) { btnRec.hidden = false; btnRec.classList.add('recording'); btnRec.disabled = false; btnRec.title = 'Stop recording / 停止录音'; }
      if (btnPause) btnPause.hidden = false;
      if (label) label.textContent = 'Recording… (tap ⏺ to stop)';
    } else if (state === 'paused') {
      if (btnRec) { btnRec.hidden = false; btnRec.classList.add('recording'); btnRec.disabled = false; btnRec.title = 'Stop recording / 停止录音'; }
      if (btnPause) { btnPause.hidden = false; btnPause.classList.add('paused'); btnPause.title = 'Resume / 恢复'; btnPause.textContent = '▶'; }
      if (label) label.textContent = 'Paused — tap ⏸ to resume or ⏺ to stop';
    } else if (state === 'saved') {
      if (btnRec) { btnRec.hidden = false; btnRec.disabled = false; btnRec.title = 'Re-record / 重录'; }
      if (btnPlay) btnPlay.hidden = false;
      if (btnDelete) btnDelete.hidden = false;
      if (btnPause) { btnPause.textContent = '⏸'; btnPause.title = 'Pause / 暂停'; }
      if (label) label.textContent = 'Saved — tap ▶ to play, 🗑 to re-record';
    } else if (state === 'playing') {
      // Round 55 (2026-05-17): new 'playing' state for audio playback.
      // The stop button (⏹) is what halts playback — it does NOT stop
      // recording per the new role separation. Keep delete visible so
      // the student can discard mid-listen without an extra tap. Record
      // is hidden during playback to avoid mid-play confusion.
      if (btnStop) btnStop.hidden = false;
      if (btnPlay) { btnPlay.hidden = false; btnPlay.classList.add('playing'); btnPlay.disabled = true; }
      if (btnDelete) btnDelete.hidden = false;
      if (label) label.textContent = 'Playing… (tap ⏹ to stop)';
    } else if (state === 'error') {
      if (btnRec) { btnRec.hidden = false; btnRec.disabled = true; }
      if (label) label.classList.add('error');
    }
    // Round 55 (2026-05-17): re-enable play button after leaving 'playing'.
    if (btnPlay && state !== 'playing') btnPlay.disabled = false;
  }

  function vrUpdateTimer(container) {
    if (_activeContainer !== container) return;
    const elapsed = Date.now() - _vrStartedAt - _vrPausedTotal -
                    (_vrPausedAt ? (Date.now() - _vrPausedAt) : 0);
    const timeEl = container.querySelector('.vr-time');
    if (timeEl) timeEl.textContent = `${vrFormatTime(elapsed)} / 3:00`;
    if (elapsed >= VR_MAX_MS) {
      if (timeEl) timeEl.classList.add('over');
      vrStopRecording(container);
    }
  }

  async function vrStart(container) {
    // Round 55 (2026-05-17): same-widget toggle. If THIS container is
    // already recording (or paused), the record button is now the stop
    // control — call .stop() and let the onstop handler save the blob
    // and transition to 'saved'. Don't start a new recording.
    if (_activeContainer === container && _vrMediaRecorder
        && _vrMediaRecorder.state !== 'inactive') {
      _vrMediaRecorder.stop();
      return;
    }
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

  // Round 55 (2026-05-17): renamed from vrStop. Still called internally
  // by vrUpdateTimer when the 3:00 hard cap fires. The ⏹ button no longer
  // wires to this — its click handler now calls vrStopPlayback instead.
  function vrStopRecording(container) {
    if (!_vrMediaRecorder || _activeContainer !== container) return;
    if (_vrMediaRecorder.state !== 'inactive') _vrMediaRecorder.stop();
  }

  // Round 55 (2026-05-17): the ⏹ button's new role — halt audio playback.
  // Called from the .vr-stop click binding in initVoiceRecorder().
  function vrStopPlayback(container) {
    const audioEl = container.querySelector('audio');
    if (!audioEl) return;
    if (!audioEl.paused) audioEl.pause();
    try { audioEl.currentTime = 0; } catch (e) { /* some browsers can't seek before metadata */ }
    vrSetState(container, 'saved');
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
    if (!audioEl || !audioEl.src) return;
    // Round 55 (2026-05-17): playback now has a discrete 'playing' state
    // so the ⏹ stop button can be exposed (it halts playback). When
    // playback ends naturally (or our stopPlayback handler pauses it),
    // transition back to 'saved'. The onpause handler covers both
    // explicit stops and end-of-stream pauses that some browsers
    // surface as 'pause' rather than 'ended'.
    audioEl.onended = () => vrSetState(container, 'saved');
    audioEl.onpause = () => {
      if (audioEl.ended || audioEl.currentTime === 0 ||
          (audioEl.duration && audioEl.currentTime >= audioEl.duration - 0.05)) {
        vrSetState(container, 'saved');
      }
    };
    const p = audioEl.play();
    if (p && typeof p.then === 'function') {
      p.then(() => vrSetState(container, 'playing'))
       .catch(() => vrSetState(container, 'saved'));
    } else {
      vrSetState(container, 'playing');
    }
  }

  function initVoiceRecorder() {
    if (!('mediaDevices' in navigator) || !window.MediaRecorder) return;
    document.querySelectorAll('.voice-recorder-container').forEach((container) => {
      const q = (sel) => container.querySelector(sel);
      const onIf = (sel, handler) => { const el = q(sel); if (el) el.onclick = handler; };
      onIf('.vr-record', () => vrStart(container));
      onIf('.vr-pause',  () => vrPauseToggle(container));
      // Round 55 (2026-05-17): ⏹ now stops PLAYBACK, not recording. To
      // stop a recording mid-take, tap the pulsing ⏺ record button —
      // see vrStart's same-widget toggle branch.
      onIf('.vr-stop',   () => vrStopPlayback(container));
      onIf('.vr-play',   () => vrPlay(container));
      onIf('.vr-delete', () => vrDelete(container));
      vrLoadIntoUi(container);
    });
  }
