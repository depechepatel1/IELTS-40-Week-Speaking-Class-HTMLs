  // 09_diff_markup.js - red-pen diff engine + HTML markup renderer.
  // Implements an LCS-based word diff over the student's draft and AI's
  // corrected version, then classifies the resulting segments into 8 visual
  // shapes (keep / delete / insert / replace / suffix-add / prefix-add /
  // suffix-delete / prefix-delete / stem-change) and renders them as HTML
  // with the appropriate <del>/<ins>/<span class="..."> tags.
  // Mirrors scripts/templates/diff_engine.mjs (tested separately).
  // Exports nothing to ns; consumed by ns.correctEssay in 10_ai_correction.js.
  // Depends on: nothing earlier (pure functions).

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

  // Merge consecutive same-op `delete`/`insert` segments into one multi-word
  // segment so phrase-level rewrites render as a single replace-pair instead
  // of multiple fragments. See diff_engine.mjs comments for the rationale.
  function coalesceAdjacentSameOp(segs) {
    const out = [];
    for (const s of segs) {
      const last = out[out.length - 1];
      if (last && last.op === s.op && (s.op === 'delete' || s.op === 'insert')) {
        last.word = last.word + ' ' + s.word;
      } else {
        out.push({ op: s.op, word: s.word });
      }
    }
    return out;
  }

  // Longest common prefix of two strings (case-sensitive). Used by Case H
  // (stem-change) to detect word-form transformations like tired→tiring.
  function longestCommonPrefix(a, b) {
    let i = 0;
    while (i < a.length && i < b.length && a[i] === b[i]) i++;
    return a.slice(0, i);
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
        } else if (y !== x && x.startsWith(y)) {
          // F. suffix-delete — understanding → understand
          out.push({ op: 'suffix-delete', kept: y, deleted: x.slice(y.length) });
        } else if (y !== x && x.endsWith(y)) {
          // G. prefix-delete — ago → go
          out.push({ op: 'prefix-delete', deleted: x.slice(0, x.length - y.length), kept: y });
        } else {
          const lcp = longestCommonPrefix(x, y);
          const xTail = x.slice(lcp.length);
          const yTail = y.slice(lcp.length);
          if (lcp.length >= 3
              && xTail.length >= 1 && xTail.length <= 5
              && yTail.length >= 1 && yTail.length <= 5) {
            // H. stem-change — tired→tiring, heavy→heavily, make→making
            out.push({ op: 'stem-change', kept: lcp, deleted: xTail, inserted: yTail });
          } else {
            out.push({ op: 'replace', deleted: x, inserted: y });
          }
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
        case 'suffix-delete':
          parts.push(`${space}${escHtml(seg.kept)}<del class="del-suffix">${escHtml(seg.deleted)}</del>`); break;
        case 'prefix-delete':
          parts.push(`${space}<del class="del-prefix">${escHtml(seg.deleted)}</del>${escHtml(seg.kept)}`); break;
        case 'stem-change':
          parts.push(`${space}${escHtml(seg.kept)}<span class="stem-change-pair"><del class="del-suffix">${escHtml(seg.deleted)}</del><ins class="ins-above">${escHtml(seg.inserted)}</ins></span>`); break;
      }
    });
    return parts.join('');
  }

