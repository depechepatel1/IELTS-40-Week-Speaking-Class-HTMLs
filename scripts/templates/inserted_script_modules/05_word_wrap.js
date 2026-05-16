// 05_word_wrap.js - DOM word-wrapping into <span class="tts-word">.
// Loaded after 02_dom_helpers.js (isChineseGloss, isMarkerBadge) and
// 01_state.js (_wordWrapCache, INLINE_GLOSS_RE). Used by both karaoke
// playback (04_tts_playback.js: speakElement → ensureWordsWrapped on
// markup-rich model boxes) and word-level click-to-speak
// (06_word_click.js: attachWordClicks → ensureWordsWrapped).
//
// Exports (closure-local, no ns.*):
//   wrapTextNodesInElement(el) - non-destructive walk that wraps every
//       text node into per-word <span>s, returns {spans, offsets}.
//       Skips Chinese-gloss / marker-badge / listen-row subtrees.
//   ensureWordsWrapped(el)     - idempotent cache wrapper; adds
//       .tts-word class to spans on first call, returns the cache thereafter.

  // Markup-preserving variant of speakElement's wrapping logic. Walks the
  // text-node descendants of `el` and replaces each text node with a
  // fragment that splits the text into per-word <span>s (for karaoke
  // highlighting) while LEAVING element children (e.g. <strong> for vocab,
  // <em> for emphasis) intact. Skips Chinese-gloss / marker-badge /
  // listen-row subtrees so wrapped spans align with what the TTS engine
  // actually speaks.
  //
  // Added 2026 (issue A2): the polished-output element is plain text and
  // the original speakElement could safely innerHTML='' it. Model-answer
  // boxes (Section 7) contain <strong>vocab</strong> highlights and
  // Chinese gloss spans; destroying their innerHTML would lose both.
  // This helper provides a non-destructive wrap path for markup-rich
  // elements. Returns { spans, offsets } with the same shape that the
  // original wrap path produces.
  // Round 30 (2026-05-06) — match stripChineseGloss's element-pruning
  // patterns so karaoke-wrap accumulates char-offsets in the SAME space
  // TTS speaks. Two patterns are stripped: parenthesized blocks that
  // contain CJK ("(灌输 / 价值观)"), and bare CJK runs ("灌输"). Anything
  // matching is rendered as a plain text node — visible to students,
  // never wrapped in a karaoke span. See `stripChineseGloss` below for
  // the source-of-truth regex these mirror.

  function wrapTextNodesInElement(el) {
    const spans = [];
    const offsets = [];
    let charIdx = 0;
    // Track whether the most recent character we've contributed to
    // charIdx is whitespace. stripChineseGloss collapses runs of
    // whitespace (including the gaps left by stripped gloss) to a
    // single space, so we model that here: only the FIRST whitespace
    // token at a boundary counts toward charIdx; subsequent whitespace
    // tokens (e.g. the space immediately before a stripped gloss plus
    // the space immediately after it) are emitted into the DOM but do
    // not advance charIdx. Initialised true so leading whitespace at
    // the very start of the element doesn't off-by-one the first word.
    let lastCountedWasSpace = true;

    function pushWordSpan(frag, tok) {
      const s = document.createElement('span');
      s.textContent = tok;
      offsets.push({ span: s, start: charIdx, end: charIdx + tok.length });
      spans.push(s);
      frag.appendChild(s);
      charIdx += tok.length;
      lastCountedWasSpace = false;
    }

    function pushWhitespace(frag, tok) {
      // Emit the literal whitespace into the DOM (visual fidelity), but
      // count only one space toward charIdx if there hasn't already been
      // a counted whitespace since the last word. This mirrors the
      // `\s+ -> ' '` collapse `stripChineseGloss` performs on the spoken
      // text — without it, the karaoke offsets drift forward by one
      // every time we cross a stripped-gloss boundary.
      frag.appendChild(document.createTextNode(tok));
      if (!lastCountedWasSpace) {
        charIdx += 1;
        lastCountedWasSpace = true;
      }
    }

    function pushGlossText(frag, text) {
      // Inline gloss — visually preserved, never wrapped in a span,
      // does NOT advance charIdx. lastCountedWasSpace is unchanged so
      // surrounding whitespace collapses correctly across the gloss.
      frag.appendChild(document.createTextNode(text));
    }

    function processSegmentText(text, frag) {
      // Tokenise plain (non-gloss) text into word/whitespace runs and
      // emit each.
      const tokens = text.split(/(\s+)/);
      tokens.forEach(tok => {
        if (!tok) return;
        if (/^\s+$/.test(tok)) pushWhitespace(frag, tok);
        else pushWordSpan(frag, tok);
      });
    }

    function processTextNode(t, frag) {
      // Split the text-node content into [non-gloss, gloss, non-gloss, …]
      // segments so we never wrap CJK / paren-CJK blocks as karaoke spans.
      let lastIdx = 0;
      let m;
      INLINE_GLOSS_RE.lastIndex = 0;
      while ((m = INLINE_GLOSS_RE.exec(t)) !== null) {
        if (m.index > lastIdx) processSegmentText(t.slice(lastIdx, m.index), frag);
        pushGlossText(frag, m[0]);
        lastIdx = m.index + m[0].length;
      }
      if (lastIdx < t.length) processSegmentText(t.slice(lastIdx), frag);
    }

    function walk(node) {
      if (!node) return;
      if (node.nodeType === Node.TEXT_NODE) {
        const t = node.textContent;
        if (!t) return;
        const frag = document.createDocumentFragment();
        processTextNode(t, frag);
        node.parentNode.replaceChild(frag, node);
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return;
      if (isChineseGloss(node)) return;
      if (isMarkerBadge(node)) return;
      if (node.classList && node.classList.contains('listen-row')) return;
      // Snapshot childNodes — we'll be replacing some during the walk.
      Array.from(node.childNodes).forEach(walk);
    }
    walk(el);
    return { spans, offsets };
  }

  // Round 52 — module-level cache for ensureWordsWrapped(). Keyed by the
  // wrapped element so the click-to-speak feature (attachWordClicks) and
  // the karaoke feature (speakElement) reuse ONE set of per-word
  // <span class="tts-word"> elements instead of each wrapping the DOM
  // independently and clobbering the other's spans.

  // Round 52 — idempotent, cached wrapper around wrapTextNodesInElement().
  // First call on `el`: wraps every text node into <span class="tts-word">,
  // caches and returns {spans, offsets}. Repeat calls: returns the cache
  // untouched. This is the SINGLE place DOM word-wrapping happens.
  function ensureWordsWrapped(el) {
    const cached = _wordWrapCache.get(el);
    if (cached) return cached;
    const result = wrapTextNodesInElement(el);
    result.spans.forEach((s) => s.classList.add('tts-word'));
    _wordWrapCache.set(el, result);
    return result;
  }
