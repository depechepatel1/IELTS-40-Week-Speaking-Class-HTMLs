  // 07_ipa_tooltip.js - IPA pronunciation tooltip helpers.
  // Lazy-loads the pronunciations JSON dictionary (cached in sessionStorage
  // and the _pronunciationsCache closure variable) on first use, then renders
  // a small absolutely-positioned tooltip near the clicked word for 3 seconds.
  // Exports nothing to ns; called internally from word-click handlers.
  // Depends on:
  //   - 01_state.js: _pronunciationsCache
  //   - _header.js: PRONUNCIATIONS_URL

  // ---- IPA tooltip (lazy-loaded once per session) ----

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

