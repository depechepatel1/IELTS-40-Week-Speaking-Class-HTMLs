import { test } from 'node:test';
import assert from 'node:assert/strict';
import { wordDiff, classifyPairs, renderMarkup, coalesceAdjacentSameOp } from './diff_engine.mjs';

test('wordDiff: identical strings → all keep', () => {
  const r = wordDiff('hello world', 'hello world');
  assert.deepEqual(r, [{ op: 'keep', word: 'hello' }, { op: 'keep', word: 'world' }]);
});

test('wordDiff: pure insertion of "the"', () => {
  const r = wordDiff('went to park', 'went to the park');
  assert.deepEqual(r.map(s => s.op), ['keep', 'keep', 'insert', 'keep']);
  assert.equal(r.find(s => s.op === 'insert').word, 'the');
});

test('wordDiff: pure deletion of "very"', () => {
  const r = wordDiff('I have very enjoyed it', 'I have enjoyed it');
  assert.deepEqual(r.map(s => s.op), ['keep', 'keep', 'delete', 'keep', 'keep']);
});

test('wordDiff: empty input → all inserts', () => {
  const r = wordDiff('', 'hello world');
  assert.deepEqual(r.map(s => s.op), ['insert', 'insert']);
});

test('wordDiff: all deletes when polished is empty', () => {
  const r = wordDiff('a b c', '');
  assert.deepEqual(r.map(s => s.op), ['delete', 'delete', 'delete']);
});

test('classifyPairs: suffix-add child→children', () => {
  const segs = [{ op: 'delete', word: 'child' }, { op: 'insert', word: 'children' }];
  const r = classifyPairs(segs);
  assert.equal(r.length, 1);
  assert.equal(r[0].op, 'suffix-add');
  assert.equal(r[0].kept, 'child');
  assert.equal(r[0].added, 'ren');
});

test('classifyPairs: suffix-add see→sees (single letter s)', () => {
  const segs = [{ op: 'delete', word: 'see' }, { op: 'insert', word: 'sees' }];
  const r = classifyPairs(segs);
  assert.equal(r[0].op, 'suffix-add');
  assert.equal(r[0].added, 's');
});

test('classifyPairs: prefix-add go→ago', () => {
  const segs = [{ op: 'delete', word: 'go' }, { op: 'insert', word: 'ago' }];
  const r = classifyPairs(segs);
  assert.equal(r[0].op, 'prefix-add');
  assert.equal(r[0].added, 'a');
  assert.equal(r[0].kept, 'go');
});

test('classifyPairs: pure replacement good→well', () => {
  const segs = [{ op: 'delete', word: 'good' }, { op: 'insert', word: 'well' }];
  const r = classifyPairs(segs);
  assert.equal(r[0].op, 'replace');
  assert.equal(r[0].deleted, 'good');
  assert.equal(r[0].inserted, 'well');
});

test('classifyPairs: identical X==Y is treated as replace (defensive)', () => {
  // LCS shouldn't produce this, but guard against it.
  const segs = [{ op: 'delete', word: 'foo' }, { op: 'insert', word: 'foo' }];
  const r = classifyPairs(segs);
  assert.equal(r[0].op, 'replace');
});

test('classifyPairs: standalone delete and insert pass through', () => {
  const segs = [
    { op: 'keep', word: 'a' },
    { op: 'delete', word: 'foo' },
    { op: 'keep', word: 'b' },
    { op: 'insert', word: 'baz' }
  ];
  const r = classifyPairs(segs);
  assert.equal(r.length, 4);
  assert.equal(r[1].op, 'delete');
  assert.equal(r[3].op, 'insert');
});

test('renderMarkup: produces expected HTML for each shape', () => {
  const html = renderMarkup([
    { op: 'keep', word: 'I' },
    { op: 'delete', word: 'has' },
    { op: 'keep', word: 'went' },
    { op: 'replace', deleted: 'good', inserted: 'well' },
    { op: 'insert', word: 'the' },
    { op: 'suffix-add', kept: 'child', added: 'ren' },
    { op: 'prefix-add', added: 'a', kept: 'go' }
  ]);
  assert.match(html, /<del class="del">has<\/del>/);
  assert.match(html, /<span class="replace-pair"><del class="del">good<\/del><ins class="ins-above">well<\/ins><\/span>/);
  assert.match(html, /<span class="gap-anchor"><ins class="ins-above">the<\/ins><\/span>/);
  assert.match(html, /child<ins class="ins-suffix">ren<\/ins>/);
  assert.match(html, /<ins class="ins-prefix">a<\/ins>go/);
});

test('renderMarkup: HTML-escapes word content', () => {
  const html = renderMarkup([{ op: 'keep', word: '<script>' }]);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});

test('end-to-end: child → children renders as suffix-add (Case D)', () => {
  // Realistic LCS path for a student who wrote "child" instead of "children".
  const segs = wordDiff('lots of child playing', 'lots of children playing');
  const classified = classifyPairs(segs);
  const html = renderMarkup(classified);
  assert.match(html, /child<ins class="ins-suffix">ren<\/ins>/);
});

test('classifyPairs: suffix-delete understanding → understand (Case F)', () => {
  const segs = [{ op: 'delete', word: 'understanding' }, { op: 'insert', word: 'understand' }];
  const r = classifyPairs(segs);
  assert.equal(r[0].op, 'suffix-delete');
  assert.equal(r[0].kept, 'understand');
  assert.equal(r[0].deleted, 'ing');
});

test('classifyPairs: prefix-delete ago → go (Case G)', () => {
  const segs = [{ op: 'delete', word: 'ago' }, { op: 'insert', word: 'go' }];
  const r = classifyPairs(segs);
  assert.equal(r[0].op, 'prefix-delete');
  assert.equal(r[0].deleted, 'a');
  assert.equal(r[0].kept, 'go');
});

test('renderMarkup: suffix-delete renders kept stem + del-suffix', () => {
  const html = renderMarkup([{ op: 'suffix-delete', kept: 'understand', deleted: 'ing' }]);
  assert.match(html, /understand<del class="del-suffix">ing<\/del>/);
});

test('renderMarkup: prefix-delete renders del-prefix + kept stem', () => {
  const html = renderMarkup([{ op: 'prefix-delete', deleted: 'a', kept: 'go' }]);
  assert.match(html, /<del class="del-prefix">a<\/del>go/);
});

test('end-to-end: childrens → children renders as suffix-delete (Case F)', () => {
  // Previously fell through to Case C replace-pair (full strike + above-line).
  // Now correctly classified as suffix-delete: keep "children", strike "s".
  const segs = wordDiff('lots of childrens', 'lots of children');
  const classified = classifyPairs(segs);
  const html = renderMarkup(classified);
  assert.match(html, /children<del class="del-suffix">s<\/del>/);
  assert.doesNotMatch(html, /replace-pair/);
});

test('end-to-end: understanding → understand renders as suffix-delete (Case F)', () => {
  const segs = wordDiff('I am understanding', 'I am understand');
  const classified = classifyPairs(segs);
  const html = renderMarkup(classified);
  assert.match(html, /understand<del class="del-suffix">ing<\/del>/);
});

// === coalesceAdjacentSameOp tests ===

test('coalesceAdjacentSameOp: merges consecutive deletes', () => {
  const r = coalesceAdjacentSameOp([
    { op: 'delete', word: 'Next' },
    { op: 'delete', word: 'day,' },
    { op: 'keep',   word: 'I' }
  ]);
  assert.equal(r.length, 2);
  assert.equal(r[0].op, 'delete');
  assert.equal(r[0].word, 'Next day,');
  assert.equal(r[1].op, 'keep');
});

test('coalesceAdjacentSameOp: merges consecutive inserts', () => {
  const r = coalesceAdjacentSameOp([
    { op: 'insert', word: 'the' },
    { op: 'insert', word: 'next' },
    { op: 'insert', word: 'day,' }
  ]);
  assert.equal(r.length, 1);
  assert.equal(r[0].op, 'insert');
  assert.equal(r[0].word, 'the next day,');
});

test('coalesceAdjacentSameOp: does NOT merge consecutive keeps (no value)', () => {
  const r = coalesceAdjacentSameOp([
    { op: 'keep', word: 'a' },
    { op: 'keep', word: 'b' }
  ]);
  assert.equal(r.length, 2);
});

test('coalesceAdjacentSameOp: del-del-ins-ins becomes del + ins', () => {
  // not understanding → didn't understand
  const r = coalesceAdjacentSameOp([
    { op: 'delete', word: 'not' },
    { op: 'delete', word: 'understanding' },
    { op: 'insert', word: "didn't" },
    { op: 'insert', word: 'understand' }
  ]);
  assert.equal(r.length, 2);
  assert.equal(r[0].word, 'not understanding');
  assert.equal(r[1].word, "didn't understand");
});

test('coalesceAdjacentSameOp: does not mutate input array', () => {
  const input = [{ op: 'delete', word: 'a' }, { op: 'delete', word: 'b' }];
  const r = coalesceAdjacentSameOp(input);
  assert.equal(input[0].word, 'a');
  assert.equal(input[1].word, 'b');
  assert.equal(r[0].word, 'a b');
});

test('end-to-end: not understanding → didn\'t understand renders as ONE replace-pair, no chevron', () => {
  const segs = wordDiff('I am not understanding the rules', "I am didn't understand the rules");
  const coalesced = coalesceAdjacentSameOp(segs);
  const classified = classifyPairs(coalesced);
  const html = renderMarkup(classified);
  // ONE replace-pair containing both deleted words struck together
  assert.match(html, /<del class="del">not understanding<\/del>/);
  // ONE correction phrase above
  assert.match(html, /<ins class="ins-above">didn't understand<\/ins>/);
  // ZERO chevrons (no standalone gap-anchor)
  assert.equal(html.includes('gap-anchor'), false);
});

test('end-to-end: I have → I had a renders as ONE replace-pair', () => {
  const segs = wordDiff('I have very big', 'I had a very big');
  const coalesced = coalesceAdjacentSameOp(segs);
  const classified = classifyPairs(coalesced);
  const html = renderMarkup(classified);
  assert.match(html, /<del class="del">have<\/del><ins class="ins-above">had a<\/ins>/);
  assert.equal(html.includes('gap-anchor'), false);
});

test('end-to-end: triple insertion the+next+day, becomes one insert with one chevron', () => {
  const segs = wordDiff('long. day, I', 'long. the next day, I');
  const coalesced = coalesceAdjacentSameOp(segs);
  const classified = classifyPairs(coalesced);
  const html = renderMarkup(classified);
  // Exactly one gap-anchor
  const matches = html.match(/<span class="gap-anchor">/g) || [];
  assert.equal(matches.length, 1);
  // The single gap-anchor contains the multi-word insertion
  assert.match(html, /<ins class="ins-above">the next<\/ins>/);
});
