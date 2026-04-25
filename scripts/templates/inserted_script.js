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
  // and Android system voices. Spec §8.1 voice waterfall.
  const FEMALE_NEURAL_UK = /Sonia|Libby|Mia|Maisie|Jenny.*GB|Kate|Serena/i;
  const MALE_NEURAL_UK   = /Ryan|Thomas.*GB|Noah|Daniel/i;
  const FEMALE_NEURAL_US = /Aria|Jenny|Ana|Michelle|Emma|Samantha|Allison|Ava/i;
  const MALE_NEURAL_US   = /Guy|Tony|Jason|Eric|Davis|Alex|Aaron/i;

  function pickVoice(lang) {
    if (!('speechSynthesis' in window)) return null;
    const all = window.speechSynthesis.getVoices();
    if (!all.length) return null;
    const langPrefix = lang === 'en-GB' ? 'en-GB' : 'en-US';
    const inLang = all.filter(v => v.lang === langPrefix);
    const female = lang === 'en-GB' ? FEMALE_NEURAL_UK : FEMALE_NEURAL_US;
    const male   = lang === 'en-GB' ? MALE_NEURAL_UK   : MALE_NEURAL_US;
    return inLang.find(v => female.test(v.name))
        || inLang.find(v => male.test(v.name))
        || inLang[0]
        || all[0];
  }

  function isWeChatBrowser() {
    return /MicroMessenger/i.test(navigator.userAgent || '');
  }

  function wechatFallbackAlert() {
    alert("微信浏览器不支持语音播放，请用 Safari 或 Chrome 打开本页 / WeChat browser doesn't support audio playback. Please open this page in Safari or Chrome.");
  }

  let _currentSpans = null;

  ns.stopSpeaking = function () {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (_currentSpans) _currentSpans.forEach(s => s.classList.remove('speaking'));
    _currentSpans = null;
  };

  ns.speakText = function (text, lang = 'en-GB', rate = 1.0) {
    if (!('speechSynthesis' in window)) {
      if (isWeChatBrowser()) wechatFallbackAlert();
      return;
    }
    if (!text || !String(text).trim()) return;
    ns.stopSpeaking();
    const u = new SpeechSynthesisUtterance(String(text));
    u.lang = lang;
    u.rate = rate;
    const v = pickVoice(lang);
    if (v) u.voice = v;
    window.speechSynthesis.speak(u);
  };

  // Wraps each word in <span> for karaoke highlighting on `boundary` events.
  ns.speakElement = function (el, lang = 'en-GB', rate = 1.0) {
    if (!('speechSynthesis' in window)) {
      if (isWeChatBrowser()) wechatFallbackAlert();
      return;
    }
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
    _currentSpans = spans;

    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    u.rate = rate;
    const v = pickVoice(lang);
    if (v) u.voice = v;
    u.onboundary = function (ev) {
      if (ev.name && ev.name !== 'word') return;
      const idx = ev.charIndex;
      spans.forEach(s => s.classList.remove('speaking'));
      const hit = offsets.find(o => idx >= o.start && idx < o.end);
      if (hit) hit.span.classList.add('speaking');
    };
    u.onend = function () {
      spans.forEach(s => s.classList.remove('speaking'));
    };
    window.speechSynthesis.speak(u);
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
    span.textContent = `${n} / 50–150`;
    span.classList.remove('short', 'ok', 'long');
    if (n < 50) span.classList.add('short');
    else if (n <= 150) span.classList.add('ok');
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

  function enablePolishedListenButtons() {
    document.querySelectorAll('#polished-output ~ .button-row .tts-btn:not(.stop)')
      .forEach(b => { b.disabled = false; });
  }
  function disablePolishedListenButtons() {
    document.querySelectorAll('#polished-output ~ .button-row .tts-btn:not(.stop)')
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
    if (n > 150) {
      setStatus(`请控制在 150 个词以内 / Please keep it under 150 words. (Currently ${n})`, 'error');
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

    // Render the red-pen diff over the original draft text.
    const segs = wordDiff(text, corrected);
    const classified = classifyPairs(segs);
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
    const badge = document.getElementById('health-badge');
    if (!badge) return;
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 3000);
      const resp = await fetch(AI_ENDPOINT.replace(/\/$/, '') + '/health', { signal: ctrl.signal });
      clearTimeout(t);
      badge.hidden = !!resp.ok;
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

  /** Recursively collect text from a node, skipping any Chinese-gloss subtree
   *  and the listen-row itself (so we don't read button labels). */
  function extractReadableText(node) {
    if (!node) return '';
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (node.nodeType !== Node.ELEMENT_NODE) return '';
    if (isChineseGloss(node)) return '';
    if (node.classList && node.classList.contains('listen-row')) return '';
    return Array.from(node.childNodes).map(extractReadableText).join(' ');
  }

  function injectListenButtons() {
    document.querySelectorAll('.model-box').forEach((box) => {
      // Idempotent — skip if a row already exists.
      if (box.querySelector(':scope > .listen-row')) return;

      const row = document.createElement('div');
      row.className = 'listen-row';
      row.innerHTML = `
        <button class="tts-btn uk" title="UK voice">🇬🇧</button>
        <button class="tts-btn us" title="US voice">🇺🇸</button>
        <button class="tts-btn slow" title="Slow">🐢</button>
        <button class="tts-btn stop" title="Stop">⏹</button>
      `;
      const [btnUK, btnUS, btnSlow, btnStop] = row.children;
      const textOf = () => extractReadableText(box).replace(/\s+/g, ' ').trim();
      btnUK.onclick   = () => ns.speakText(textOf(), 'en-GB', 1.0);
      btnUS.onclick   = () => ns.speakText(textOf(), 'en-US', 1.0);
      btnSlow.onclick = () => ns.speakText(textOf(), 'en-GB', 0.7);
      btnStop.onclick = () => ns.stopSpeaking();
      box.insertBefore(row, box.firstChild);
    });
  }

  function attachWordClicks() {
    document.querySelectorAll('.vocab-table strong, .model-box strong').forEach((el) => {
      // Skip <strong> inside any Chinese-gloss ancestor.
      let p = el.parentElement;
      while (p) { if (isChineseGloss(p)) return; p = p.parentElement; }
      // Skip <strong> inside the listen-row buttons.
      if (el.closest('.listen-row')) return;

      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const word = el.textContent.trim();
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

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ns.__init === 'function') ns.__init();
  });

})();
