// Pure functions exported as ESM for unit tests (Node node:test).
// An identical, IIFE-scoped copy of these functions is also embedded in
// inserted_script.js — make_interactive.py does NOT inline this file at
// build time, so any change here must also be reflected in inserted_script.js.

/** Word-level LCS diff. Returns an array of { op, word } segments. */
export function wordDiff(a, b) {
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

/** Merge consecutive same-op `delete` or `insert` segments into one
 *  multi-word segment. Run between wordDiff() and classifyPairs() so
 *  phrase-level rewrites become single replace-pairs instead of being
 *  split into multiple visual fragments.
 *
 *  Example:
 *    [delete "Next", delete "day,",
 *     insert "the", insert "next", insert "day,"]
 *  →
 *    [delete "Next day,",
 *     insert "the next day,"]
 *
 *  classifyPairs then turns this into a single `replace` shape,
 *  rendered as one continuous strike across both deleted words with
 *  one correction phrase centered above. Without coalescing, the same
 *  edit would render as a `^^^` cluster of three separate insertions
 *  plus two separate strikes — visually noisy, hard to read.
 */
export function coalesceAdjacentSameOp(segs) {
  const out = [];
  for (const s of segs) {
    const last = out[out.length - 1];
    if (last && last.op === s.op && (s.op === 'delete' || s.op === 'insert')) {
      last.word = last.word + ' ' + s.word;
    } else {
      out.push({ ...s });
    }
  }
  return out;
}

/** Group adjacent (delete, insert) pairs into one of seven rendering shapes:
 *
 *  A. delete           B. insert            C. replace
 *  D. suffix-add    (Y starts with X, Y!==X)   e.g. child → children   → child<ins>ren</ins>
 *  E. prefix-add    (Y ends with X, Y!==X)     e.g. go → ago           → <ins>a</ins>go
 *  F. suffix-delete (X starts with Y, X!==Y)   e.g. understanding → understand → understand<del>ing</del>
 *  G. prefix-delete (X ends with Y, X!==Y)     e.g. ago → go           → <del>a</del>go
 *
 * D/E/F/G keep the surviving stem in its original style and apply red
 * marks ONLY to the changed letters — the "minimal-red-ink" pedagogy
 * spelt out in the IGCSE port spec. They take precedence over the
 * generic `replace` shape (C), which renders the whole word as a
 * strikethrough plus an above-line correction.
 */
export function classifyPairs(segs) {
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
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** Render an array of classified segments to HTML matching the inserted CSS. */
export function renderMarkup(classified) {
  const parts = [];
  classified.forEach((seg, idx) => {
    const space = idx > 0 ? ' ' : '';
    switch (seg.op) {
      case 'keep':
        parts.push(`${space}${escHtml(seg.word)}`);
        break;
      case 'delete':
        parts.push(`${space}<del class="del">${escHtml(seg.word)}</del>`);
        break;
      case 'insert':
        parts.push(`${space}<span class="gap-anchor"><ins class="ins-above">${escHtml(seg.word)}</ins></span>`);
        break;
      case 'replace':
        parts.push(`${space}<span class="replace-pair"><del class="del">${escHtml(seg.deleted)}</del><ins class="ins-above">${escHtml(seg.inserted)}</ins></span>`);
        break;
      case 'suffix-add':
        parts.push(`${space}${escHtml(seg.kept)}<ins class="ins-suffix">${escHtml(seg.added)}</ins>`);
        break;
      case 'prefix-add':
        parts.push(`${space}<ins class="ins-prefix">${escHtml(seg.added)}</ins>${escHtml(seg.kept)}`);
        break;
      case 'suffix-delete':
        parts.push(`${space}${escHtml(seg.kept)}<del class="del-suffix">${escHtml(seg.deleted)}</del>`);
        break;
      case 'prefix-delete':
        parts.push(`${space}<del class="del-prefix">${escHtml(seg.deleted)}</del>${escHtml(seg.kept)}`);
        break;
    }
  });
  return parts.join('');
}
