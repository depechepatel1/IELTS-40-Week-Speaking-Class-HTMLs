  // 12_email_recordings.js - Email-the-recordings flow: enumerate IndexedDB
  // recordings for the current lesson, build a STORED-mode ZIP client-side
  // (CRC32 + local file headers + central directory), trigger a download,
  // and open the OS mail client via mailto: with subject+body prefilled.
  // Includes a preflight confirmation panel and a completion panel with
  // re-open/copy fallbacks for users without a default mail client.
  // Exports to ns: emailLessonRecordings, __emailBuildZip, __emailFilenameFor.
  // Depends on:
  //   - 01_state.js: LESSON_KEY, _EMAIL_LS_KEY, _EMAIL_VALID_RE, _crcTable
  //   - 11_voice_recorder.js: vrOpenDB, VR_STORE

  // ====================================================================
  // EMAIL RECORDINGS — gather all IndexedDB recordings for THIS lesson,
  // ZIP them client-side, trigger a download, and open the user's email
  // client via mailto: with a pre-filled subject + body. Student attaches
  // the zip manually in their mail client.
  //
  // Public API: ns.emailLessonRecordings()
  // No backend / no network. All client-side.
  // ====================================================================


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
