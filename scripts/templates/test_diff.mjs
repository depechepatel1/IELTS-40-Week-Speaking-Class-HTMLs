import { test } from 'node:test';
import assert from 'node:assert/strict';
import { wordDiff, classifyPairs, renderMarkup } from './diff_engine.mjs';

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

test('end-to-end: childrens → children falls through to replace-pair (Case C)', () => {
  // childrens → children is a "suffix-delete" not covered by the 5-case spec.
  // It correctly renders as a Case C replacement (full strikethrough + above-line).
  const segs = wordDiff('lots of childrens', 'lots of children');
  const classified = classifyPairs(segs);
  const html = renderMarkup(classified);
  assert.match(html, /replace-pair/);
});
