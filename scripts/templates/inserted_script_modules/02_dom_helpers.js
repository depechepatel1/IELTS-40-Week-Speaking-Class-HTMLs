// 02_dom_helpers.js - DOM filtering & readable-text extraction helpers.
// Functions for excluding Chinese-gloss subtrees and marker badges from
// anything we read aloud, plus a recursive text-extractor that respects
// those filters.
// Exports (IIFE-closure scope): isChineseGloss, isMarkerBadge,
//   stripChineseGloss, extractReadableText.
// Depends on: nothing from later modules; uses only the Node global and
// the INLINE_GLOSS_RE constant declared in 01_state.js (not referenced
// here directly - stripChineseGloss inlines its own regex for the
// parenthesized-CJK pass).

  /** True if `node` is a Chinese-gloss element we should NOT read aloud. */
  function isChineseGloss(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE) return false;
    if (node.lang === 'zh' || node.getAttribute('lang') === 'zh') return true;
    const style = node.getAttribute('style') || '';
    return /color\s*:\s*#7f8c8d/i.test(style);
  }

  /** True if `node` is a marker badge we should NOT read aloud (Op/Re/Ex etc.). */
  function isMarkerBadge(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE || !node.classList) return false;
    return node.classList.contains('badge-ore');
  }

  /** Strip parenthesized blocks containing CJK chars (e.g. "(有造诣的 / 成功的)")
   *  AND any standalone CJK runs. Multi-pass to handle nested cases like
   *  "instill (灌输 (价值观))". Used for inline-Chinese-gloss removal that the
   *  element-level skip can't catch. */
  function stripChineseGloss(s) {
    if (!s) return '';
    let prev;
    do {
      prev = s;
      s = s.replace(/\([^()]*[一-鿿][^()]*\)/g, '');
    } while (s !== prev);
    s = s.replace(/[一-鿿　-〿＀-￯]+/g, '');
    return s.replace(/\s+/g, ' ').trim();
  }

  /** Recursively collect text from a node, skipping Chinese-gloss subtrees,
   *  marker badges (Op/Re/Ex), and the listen-row itself. */
  function extractReadableText(node) {
    if (!node) return '';
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (node.nodeType !== Node.ELEMENT_NODE) return '';
    if (isChineseGloss(node)) return '';
    if (isMarkerBadge(node)) return '';
    if (node.classList && node.classList.contains('listen-row')) return '';
    return Array.from(node.childNodes).map(extractReadableText).join(' ');
  }
