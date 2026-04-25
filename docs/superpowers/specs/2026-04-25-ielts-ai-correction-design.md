# IELTS Interactive HTMLs: AI Correction & Browser TTS — Design Spec

**Date:** 2026-04-25
**Branch:** `feat/ai-correction-and-tts`
**Repo:** `depechepatel1/IELTS-40-Week-Speaking-Class-HTMLs`
**Status:** Draft, pending user approval

---

## 1. Context and motivation

The repo holds 40 self-contained, A4-formatted HTML lesson plans (`Week_*_Lesson_Plan.html`) for a 40-week IELTS speaking course aimed at Chinese teenagers. The HTMLs are converted to PDF for printed handouts via an existing Python pipeline.

We want a parallel set of **interactive web versions** of the same 40 lessons that:

1. Let a student type their week's answer directly into the lesson page and get an AI-powered correction returned inline as red-pen markup over their original handwriting-style text.
2. Read model answers and any clicked English word aloud using browser TTS, with selectable UK and US accents.
3. Persist a student's draft locally so they can leave and return without losing work.
4. Cost zero to operate at student-touch points (Web Speech API for TTS, Zhipu free tier for AI, Function Compute free quota, Supabase Storage public bucket).

The originals remain untouched and serve as the print source. Interactive versions live in a new `Interactive/` subfolder of the same repo and are uploaded to a new public Aliyun Supabase Storage bucket.

## 2. Goals

- One reusable Python script (`scripts/make_interactive.py`) converts any number of original lesson HTMLs into interactive versions, idempotently.
- A single Aliyun Function Compute endpoint at `*.fcapp.run` provides AI essay correction via Zhipu's latest free chat model.
- All 40 interactive HTMLs hosted in a new public Supabase Storage bucket `ielts-interactive`.
- Pedagogically strong UX: red-pen markup over handwriting-style draft, local persistence, click-word pronunciation, model-answer playback with karaoke highlighting.
- No per-student-action cost — service is free to run at student-touch points.
- Zero shift to existing floating-box lesson layout.
- Originals byte-identical post-feature.

## 3. Non-goals

- IGCSE-equivalent port — separate repo, future work.
- Server-side TTS (DashScope CosyVoice or otherwise) — would incur per-character cost, ruled out for this product.
- Authentication, accounts, server-side progress tracking — covered by the separate AI School app, not this product.
- Cross-device draft sync — local-only by design.
- Speech recognition / shadow-and-compare — out of scope.
- Editing the original 40 HTML files in place.
- Modifying `intro_packet.html`.

## 4. Architecture overview

```
[Student browser]
  │ GET interactive HTML
  ▼
[Aliyun Supabase Storage]                bucket: ielts-interactive (public)
  ielts-interactive/Week_N_Lesson_Plan.html
  ielts-interactive/pronunciations.json    (lazy-loaded on first word click)
  │
  │ fetch() POST { draft }
  ▼
[Aliyun Function Compute]                *.fcapp.run, Node.js 18, anonymous, CORS open
  • word-count validate (50–150)
  • rate-limit 30 req/IP/hr in-memory
  • call Zhipu chat completions
  │
  │ POST /api/paas/v4/chat/completions
  ▼
[Zhipu open.bigmodel.cn]                latest free chat model
```

**Boundaries:**
- The static HTML layer (Supabase Storage) and the AI layer (FC) are independent. The HTML files know the FC endpoint via a single `AI_ENDPOINT` constant injected by the build script. Replacing the FC endpoint URL in one place re-points all 40 files at next build.
- The FC endpoint is the only paid-quota touchpoint. Bucket reads are bandwidth-only on Supabase Storage, which is included in the existing AI School plan.
- The browser's Web Speech API handles all TTS. No server TTS path exists.

## 5. Component A — Function Compute endpoint

### 5.1 Runtime configuration

| Setting | Value |
|---|---|
| Runtime | Node.js 18 |
| Region | `cn-beijing` |
| Memory | 128 MB |
| Timeout | 60 seconds |
| HTTP trigger | Anonymous, methods `POST` + `OPTIONS` |
| Handler | `index.handler` |
| Environment variable | `ZHIPU_API_KEY` |

### 5.2 HTTP contract

**Request:**
```http
POST / HTTP/1.1
Content-Type: application/json

{ "draft": "I went to the park yesterday and ..." }
```

**Success response (HTTP 200):**
```json
{ "corrected": "I went to the park yesterday, and ..." }
```

**Error response (HTTP 400 / 429 / 500 / 503):**
```json
{ "error": "Bilingual error message in 中文 / English." }
```

**CORS headers on every response (including OPTIONS):**
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

`OPTIONS` returns 204 with the headers above and an empty body.

### 5.3 Validation

Word count is computed as `draft.trim().split(/\s+/).filter(Boolean).length`.

| Condition | Response |
|---|---|
| Body missing or `draft` not a string | 400, error: `请求格式错误 / Invalid request format.` |
| Word count < 50 | 400, error: `请至少写 50 个词 / Please write at least 50 words. (Currently {n})` |
| Word count > 150 | 400, error: `请控制在 150 个词以内 / Please keep it under 150 words. (Currently {n})` |

### 5.4 Rate limiting

In-memory `Map<ip, { count, windowStart }>`:

- Window: 60 minutes rolling per IP.
- Limit: 30 requests per IP per window.
- IP source: `X-Forwarded-For` header (FC populates this); fallback to `event.clientIP`.
- Reset behavior: when an FC instance recycles, the Map clears. This is acceptable per spec — the limit is a courtesy throttle, not a security boundary.
- Over-limit response: HTTP 429, error: `请稍后再试，每小时最多 30 次 / Rate limit reached. Max 30 requests per hour.`

### 5.5 Zhipu integration

| Setting | Value |
|---|---|
| Endpoint | `https://open.bigmodel.cn/api/paas/v4/chat/completions` |
| Auth | `Authorization: Bearer ${ZHIPU_API_KEY}` |
| Model | **Resolved at deploy time** (see §5.8.1). Hard-coded as a constant in `index.js`. Likely `glm-4.7-flash` or newer (`glm-5-flash` etc.). |
| `max_tokens` | 500 |
| `temperature` | 0.3 |
| `messages` | `[{role:'system', content: SYSTEM_PROMPT}, {role:'user', content: draft}]` |

### 5.6 System prompt — minimal correction

```
You are a careful English teacher correcting a 14-16 year old Chinese student's
short written answer (50-150 words) for an IELTS speaking lesson.

Make the MINIMUM changes needed for the writing to be grammatically correct and
to use words correctly. Your job is correction, not enhancement.

Fix:
- Grammar errors (verb tense, articles, subject-verb agreement, prepositions,
  word order, plurals, capitalization, punctuation)
- Spelling
- Wrong word choice ONLY when a word is genuinely incorrect (mistranslation,
  wrong sense, non-existent word)

Do NOT:
- Replace words that are already correct, even if simple or basic
- Add new ideas, examples, details, opinions, or sentences not in the student's draft
- Delete the student's ideas
- Restructure sentences unless grammar requires it
- Change length by more than 10 words from the student's original

Return ONLY the corrected text as plain prose. No preamble, no markdown,
no commentary, no quotes, no bullet points.
```

**Design rationale.** The earlier draft prompt instructed Zhipu to "replace weak vocabulary with realistic upgrades", which produced unnecessarily aggressive rewrites. The revised prompt is surgical: a draft with five errors yields five fixes, not five fixes plus eight unrequested vocabulary upgrades. This (a) keeps the diff view focused on real mistakes the student can learn from, (b) respects the student's voice, and (c) avoids implying simple-but-correct words are "wrong".

### 5.7 Error handling for upstream Zhipu failures

| Zhipu condition | Detection | Response |
|---|---|---|
| Quota exhausted | `error.code` in `{1113, 1301}` or message containing "quota" / "limit" / "余额" | HTTP 503, `AI 今日额度已用完，请明天再试 / AI quota exhausted today. Try again tomorrow.` |
| Network / timeout | `fetch` throws or response not OK after retry | HTTP 503, `AI 服务暂时不可用 / AI service temporarily unavailable.` |
| Invalid response shape | Missing `choices[0].message.content` | HTTP 500, `AI 返回了意外的响应 / AI returned an unexpected response.` |
| Generic upstream error | Any other non-200 from Zhipu | HTTP 503, `AI 服务出错，请稍后再试 / AI service error. Please try later.` |

One retry on network errors with 500ms delay. No retry on quota errors.

### 5.8 Deployment

- Tool: Serverless Devs (`s deploy`). Config in `function-compute/s.yaml`.
- Project layout:
  ```
  function-compute/
    index.js          (handler — pure JS, no TS, no bundler)
    package.json      (no deps; uses built-in fetch in Node 18)
    s.yaml            (Serverless Devs spec)
    README.md         (deploy instructions)
  ```
- Prerequisites (user-side): `npm i -g @serverless-devs/s`, `s config add` with the `claude-mcp-user` Aliyun AccessKey/SecretKey.
- Output: a `*.fcapp.run` URL printed by `s deploy`. Stored in `function-compute/DEPLOYED_URL.txt` (gitignored) and used as the `--endpoint` argument to `make_interactive.py`.

### 5.8.1 Deploy-time model resolution

Before `s deploy`, the operator runs:

```bash
curl -s -H "Authorization: Bearer $ZHIPU_API_KEY" \
  https://open.bigmodel.cn/api/paas/v4/models | jq -r '.data[].id' | grep -i flash
```

The latest free GLM `*-flash` model ID is selected and pasted into the `MODEL_ID` constant near the top of `function-compute/index.js`. Documented in `function-compute/README.md`. If Zhipu doesn't expose a public model-list endpoint, the operator checks https://open.bigmodel.cn/dev/howuse/model and uses the latest documented free flash model.

### 5.9 Health check

`GET /health` returns 200 `{ "ok": true }` with CORS headers. Used by interactive HTMLs on page load to show a "AI offline" badge if unreachable. Same handler dispatches based on path/method.

## 6. Component B — Interactive HTML generation

### 6.1 Source/target layout

```
IELTS-40-Week-Speaking-Class-HTMLs/
├── Week_*_Lesson_Plan.html       (40 originals — UNTOUCHED)
├── intro_packet.html             (UNTOUCHED)
├── Interactive/                  ← NEW
│   └── Week_*_Lesson_Plan.html   (40 generated, AI-feature-enabled)
├── function-compute/             ← NEW
├── scripts/
│   ├── make_interactive.py       ← NEW
│   └── fonts/                    ← NEW (woff2 files for base64 embed)
│       ├── Caveat-400.woff2
│       └── IndieFlower-400.woff2
├── docs/superpowers/specs/       ← THIS doc
└── pronunciations.json           (uploaded to bucket; not committed if oversized)
```

### 6.2 Three insertion points (per file)

The script does three byte-deterministic transformations on each original HTML:

**Insertion 1 — CSS block.** Inserted in the `<style>` element immediately after the closing `}` of the existing `.lines { … }` rule. Contains:
- Two `@font-face` rules embedding **Caveat 400** and **Indie Flower 400** as base64-encoded woff2 (see §8.13). No Google Fonts CDN dependency — required because the CDN is unreachable from mainland China where the students are.
- Style rules for: `.tts-btn` (and `.uk`, `.us`, `.slow`, `.stop` variants), `.writing-draft`, `.writing-output`, `.correct-btn`, `.button-row`, `.word-count` (with `.short`, `.ok`, `.long` traffic-light variants), `.ai-status` (with `.error`, `.success`), `.spinner` (with `@keyframes spin`), `.speaking` (highlight class for word being read), `.draft-markup`, `.draft-markup .del`, `.draft-markup .ins`, `.lines-overlay-host`, `.ai-only` print suppression, and model-box absolute-positioned listen buttons.

**Insertion 2 — `.draft-page` overlay augmentation.** Scoped to inside `<div class="page draft-page">…</div>`. The original `<div class="lines">` elements stay in the HTML (so the file structure remains regular). Each one is wrapped in a `class="lines-overlay-host"` parent so its sibling overlay elements can position absolutely against it, and additional UI nodes are appended INSIDE the host.

Specifically, in the Draft section: the `<div class="lines">` under `<strong>Draft:</strong>` is wrapped, and the wrapper additionally contains:
- `<textarea id="student-draft" class="writing-draft" placeholder="Type your answer here / 在此处输入你的答案">` — the typing surface, transparent with its own scrolling lined background.
- `<div id="draft-markup" class="draft-markup" hidden>` — the post-correction red-pen view (replaces textarea visually after Correct is clicked).
- `<span id="word-count" class="word-count">0 / 50–150</span>` — absolute-positioned in the top-right corner of the box.
- `<button id="correct-btn" class="correct-btn" onclick="correctEssay()">Correct with AI ✎</button>` — absolute-positioned in the top-right.
- `<button id="edit-again-btn" class="ai-only" hidden onclick="editAgain()">Edit again ✎</button>` and `<button id="clear-draft-btn" class="ai-only" onclick="clearDraft()">Clear ✕</button>` — absolute-positioned in the top-right, mutually exclusive with #correct-btn.
- `<div id="ai-status" class="ai-status"></div>` — absolute-positioned at the bottom-right of the box, transient bilingual status messages.

In the Polished Rewrite section: the `<div class="lines">` under `<strong>Polished Rewrite:</strong>` is wrapped, and the wrapper additionally contains:
- `<div id="polished-output" class="writing-output empty"></div>` — the AI's clean output, transparent overlay with its own scrolling lined background, in the printed Lato font.
- A `<div class="listen-row">` containing buttons `[🇬🇧 Listen][🇺🇸 Listen][🐢 Slow][⏹ Stop]` — absolute-positioned in the top-right corner. Initially disabled until correction completes.

Other `.lines` divs in the file (spider-leg notes, framework slots, etc.) are NOT touched. The replacement is anchored to the `.draft-page` parent only.

**Why "augment" rather than "replace":** the original `.lines` divs are kept in HTML so our pattern-matching script remains anchored to a regular structure across all 40 files. They are made visually invisible by an `.draft-page .lines { display: none; }` rule in the inserted CSS — the overlay elements provide their own (scroll-aware) lined background that replaces what the original `.lines` rendered. See §8.12.

**Concrete HTML transformation** (Draft section shown; Polished section is structurally identical with appropriate ID/class swaps):

*Before* (originals at line ~890–894 of Week_1):

```html
<div style="border:1px solid #eee; padding:10px; border-radius:6px;
            background:var(--bg-pastel-green); flex:1; ...">
  <strong>Draft:</strong>
  <div class="lines" style="flex-grow:1; height:auto;"></div>
</div>
```

*After*:

```html
<div style="border:1px solid #eee; padding:10px; border-radius:6px;
            background:var(--bg-pastel-green); flex:1; ...">
  <strong>Draft:</strong>
  <div class="lines-overlay-host">
    <div class="lines" style="flex-grow:1; height:auto;"></div>  <!-- hidden via CSS -->
    <textarea id="student-draft" class="writing-draft"
              placeholder="Type your answer here / 在此处输入你的答案"></textarea>
    <div id="draft-markup" class="draft-markup" hidden></div>
    <div class="button-row">
      <span id="word-count" class="word-count">0 / 50–150</span>
      <button id="correct-btn" class="correct-btn"
              onclick="correctEssay()">Correct with AI ✎</button>
      <button id="edit-again-btn" class="ai-only" hidden
              onclick="editAgain()">Edit again ✎</button>
      <button id="clear-draft-btn" class="ai-only"
              onclick="clearDraft()">Clear ✕</button>
    </div>
    <div id="ai-status" class="ai-status"></div>
  </div>
</div>
```

**Insertion 3 — `<script>` block before `</body>`.** Contains:
- `const AI_ENDPOINT = '<deploy-time URL>';`
- `const PRONUNCIATIONS_URL = '<bucket URL>/pronunciations.json';`
- TTS functions: `speakText`, `stopSpeaking`, `speakElement`, `speakElementById`, with voice resolution waterfall (UK/US female neural → male neural → any voice for that locale → default) and karaoke highlighting via `boundary` events.
- `injectListenButtons()` — runs on DOMContentLoaded, adds absolute-positioned 🇬🇧/🇺🇸/🐢/⏹ buttons inside each `.model-box` (top-right, in existing padding, no layout shift); makes every bolded English word in `.vocab-table` and `.model-box` clickable for pronunciation.
- `correctEssay()` — POSTs to `AI_ENDPOINT`, handles errors with bilingual messages, renders diff markup over draft, populates polished-output div.
- `updateWordCount()` — wired to textarea `input` event; updates count and traffic-light class.
- `wordDiff(original, polished)` — LCS-based word-level diff returning `[{op, word}]` segments.
- `renderMarkup(diffSegments)` — returns HTML string with `<del>` for deletions and `<ins>` for insertions positioned as superscript above the line.
- `editAgain()` — restores textarea, hides markup, clears polished output.
- `clearDraft()` — empties textarea and removes localStorage entry after confirm.
- localStorage save/load (debounced 500ms) keyed by `ielts:draft:{filename}`.
- `wechatFallbackAlert()` — detects WeChat in-app browser via `navigator.userAgent.match(/MicroMessenger/)` and shows a Chinese+English alert when speech synthesis is requested.
- `checkHealth()` — pings `${AI_ENDPOINT}/health` on load; sets badge state.
- `lookupIPA(word)` — lazy-loads `pronunciations.json` from `PRONUNCIATIONS_URL` on first call, caches in `sessionStorage`, returns IPA for tooltip display.
- WeChat fallback message text: `微信浏览器不支持语音播放，请用 Safari 或 Chrome 打开本页 / WeChat browser doesn't support audio playback. Please open this page in Safari or Chrome.`

### 6.3 `make_interactive.py` script behavior

**Signature:**
```bash
python scripts/make_interactive.py \
  --in <input-folder-or-file> \
  --out <output-folder> \
  --endpoint <FC URL> \
  --bucket-base <Supabase public URL prefix>
```

**Behavior:**
- If `--in` is a folder, processes every `Week_*_Lesson_Plan.html` (skips `intro_packet.html` and any non-matching files).
- For each file, applies the three insertions and writes to `<output-folder>/<basename>`.
- **Idempotent**: if an output file already contains a sentinel comment `<!-- AI-INTERACTIVE-V1 -->`, the script overwrites it (so re-running with a new endpoint URL is safe).
- Pattern-match failures (any of the three anchors not found) cause that single file to be **skipped**, logged, and reported in the final summary; the script does not abort.
- Final summary output: count processed, count skipped, list of skipped files with reason.

**Implementation approach:** plain string operations using anchored regular expressions. No HTML parser dependency. The HTML structure is regular enough across all 40 files (verified: all 40 have exactly one `class="page draft-page"` and one Polished Rewrite section) that regex-based insertion is safe.

### 6.4 Idempotency contract

Running the script twice on the same input must produce byte-identical output. Implementation:
- Sentinel comment `<!-- AI-INTERACTIVE-V1 -->` is the first thing inserted; on re-run, presence of the sentinel triggers overwrite.
- The script does NOT modify originals — it always writes a fresh copy to `--out`.

## 7. Component C — Aliyun Supabase hosting

### 7.1 Bucket setup

- **Name:** `ielts-interactive`
- **Visibility:** public
- **Region:** cn-beijing (matches existing instance `ra-supabase-eer8m96pab9mh2`)
- **CORS:** allow `GET` and `HEAD` from `*` (default for public buckets is sufficient)

### 7.2 Files uploaded

```
ielts-interactive/
├── Week_1_Lesson_Plan.html
├── …
├── Week_40_Lesson_Plan.html
└── pronunciations.json
```

### 7.3 Public URLs

`http://8.168.22.242/storage/v1/object/public/ielts-interactive/Week_N_Lesson_Plan.html`

### 7.4 Upload mechanism

Via the Aliyun-Supabase MCP server (`@aliyun-rds/supabase-mcp-server`) using the `claude-mcp-user` RAM credentials. Bucket creation: `create_storage_bucket` (or via Supabase REST). File upload: `upload_storage_object` per file, or via the MCP's bulk upload if available. Re-upload on each rebuild is idempotent (overwrites existing files).

## 8. Component D — Browser-side JS subsystems

### 8.1 TTS voice resolution waterfall

For each accent:

```
UK button:
  1. voice.lang === 'en-GB' && voice.name matches /Sonia|Libby|Mia|Jenny.*GB/ (female neural names)
  2. voice.lang === 'en-GB' && voice.name matches /Ryan|Thomas.*GB/ (male neural names)
  3. voice.lang === 'en-GB' (any UK voice)
  4. default voice

US button:
  1. voice.lang === 'en-US' && voice.name matches /Aria|Jenny|Ana|Michelle/ (female neural)
  2. voice.lang === 'en-US' && voice.name matches /Guy|Tony|Jason|Eric/ (male neural)
  3. voice.lang === 'en-US' (any US voice)
  4. default
```

Voice names are matched against `speechSynthesis.getVoices()`. Edge/Chrome on Windows ship Microsoft neural voices; Safari/iOS ship platform voices. The waterfall ensures every device gets a working voice for each accent.

### 8.2 Karaoke highlighting

`SpeechSynthesisUtterance.onboundary` fires on word boundaries. The handler:
1. Maintains a running character index of the source text.
2. On each boundary event, computes the word index from `event.charIndex` and `event.charLength`.
3. Adds `.speaking` class to the corresponding `<span>` in the rendered text; removes from previously-highlighted span.

For this to work, the source text must be wrapped per-word in `<span data-word-index="N">` at render time. `speakElement(el)` does this wrapping before utterance.

### 8.3 Word counter and traffic light

| Word count | CSS class | Visual |
|---|---|---|
| 0–49 | `.short` | Red |
| 50–150 | `.ok` | Green |
| 151+ | `.long` | Amber |

Wired to textarea `input` event. Display format: `{n} / 50–150` with class set on the parent `#word-count` span.

### 8.4 `correctEssay()` flow

```
1. Read draft from #student-draft.
2. Word-count check client-side (avoid wasted FC call). If out of range, show ai-status.error with bilingual message; abort.
3. Disable Correct button, show spinner, set ai-status to "Correcting…"
4. POST to AI_ENDPOINT with { draft }.
5. On success:
   a. Compute wordDiff(originalDraft, response.corrected).
   b. Render markup HTML into #draft-markup, hide textarea, show #draft-markup and #edit-again-btn.
   c. Populate #polished-output with response.corrected.
   d. Enable polished-output Listen buttons.
   e. Save { draft, polished, markupHtml, timestamp } to localStorage.
   f. Show ai-status.success "已修改 / Corrected ✓"; clear after 3s.
6. On error: show ai-status.error with bilingual error from response; re-enable Correct button.
```

### 8.5 Diff rendering — red-pen markup

**Algorithm: two stages.**

**Stage 1 — word-level LCS diff.** Standard longest-common-subsequence over the word arrays of the original draft and the polished output. Produces an array of `{op: 'keep'|'delete'|'insert', word}` segments.

**Stage 2 — pair classification.** A second pass walks the segments and groups adjacent `delete`+`insert` pairs into one of five rendering "shapes":

| Shape | Trigger | Example pair | Rendered as |
|---|---|---|---|
| **A. delete only** | `delete X` with no immediately adjacent `insert` | `delete "very"` | `<del>very</del>` inline strikethrough |
| **B. insert only** | `insert Y` with no immediately adjacent `delete` | `insert "the"` | `<span class="gap-anchor"><ins class="ins-above">the</ins></span>` — zero-width anchor between the surrounding kept words; the `<ins>` floats above the gap via absolute positioning |
| **C. replacement** | `delete X, insert Y` where neither `Y.startsWith(X)` nor `Y.endsWith(X)` | `delete "good", insert "well"` | `<span class="replace-pair"><del>good</del><ins class="ins-above">well</ins></span>` — `<del>` stays in flow with strikethrough; `<ins>` floats above it via absolute positioning over the same horizontal range |
| **D. suffix add** | `delete X, insert Y` where `Y.startsWith(X)` | `delete "child", insert "children"` | `child<ins class="ins-suffix">ren</ins>` — the kept stem flows in Caveat blue, the appended letters render inline in Indie Flower red, no strikethrough |
| **E. prefix add** | `delete X, insert Y` where `Y.endsWith(X)` | `delete "go", insert "ago"` | `<ins class="ins-prefix">a</ins>go` — prepended letters in Indie Flower red, kept stem in Caveat blue |

**Why this matters pedagogically.** A standard diff would render every plural fix (`girl → girls`, `child → children`, `play → played`) as a full strikethrough + replacement. That's both visually noisy and pedagogically misleading — it tells the student "you wrote the wrong word" when in fact they wrote the right word missing a letter. Shapes D and E preserve the student's correct stem and call attention only to the actual missing/extra letters.

**Worked example.**

Original draft:
> *I has went to park yesterday and I see lots of childrens playing very good.*

Polished:
> *I went to the park yesterday and I saw lots of children playing very well.*

Stage 1 LCS output (compacted):
```
keep "I", delete "has", keep "went to", insert "the", keep "park yesterday and I",
delete "see", insert "saw", keep "lots of", delete "childrens", insert "children",
keep "playing very", delete "good", insert "well".
```

Stage 2 classification + render:
```
keep "I "
A. <del>has</del>
keep " went to "
B. <span class="gap-anchor"><ins class="ins-above">the</ins></span>
keep " park yesterday and I "
C. <span class="replace-pair"><del>see</del><ins class="ins-above">saw</ins></span>
keep " lots of "
D-ish (variant): childrens has 's' suffix that polished lacks → handled as
  inverse: kept stem "children" + struck "s". For symmetry, classify as a
  "trailing-letter delete" (sub-case of A): render "children" + <del>s</del>.
keep " playing very "
C. <span class="replace-pair"><del>good</del><ins class="ins-above">well</ins></span>
keep "."
```

**CSS** (paired with the overlay/scroll/font rules in §8.12 and the embedded fonts in §8.13):

```css
/* A. simple deletion — strikethrough in place, retains horizontal flow */
.draft-markup .del {
  font-family: 'Indie Flower', 'Comic Sans MS', cursive;
  font-size: 0.95em;
  color: #c0392b;
  text-decoration: line-through;
  text-decoration-color: #c0392b;
  text-decoration-thickness: 1.5px;
}

/* C. replacement — the <del> stays in flow; the <ins> floats above it. */
.draft-markup .replace-pair {
  position: relative;
  display: inline-block;
  vertical-align: baseline;
}

/* B. pure insertion — zero-width anchor in the gap between two kept words.
   The <ins> floats above the gap. */
.draft-markup .gap-anchor {
  position: relative;
  display: inline-block;
  width: 0;
  height: 0;
  vertical-align: baseline;
}

/* C/B shared — the floating insertion above the line. */
.draft-markup .ins-above {
  position: absolute;
  bottom: 0.85em;          /* lift above the host's text baseline; visually tuned in Phase B */
  left: 0;
  white-space: nowrap;
  font-family: 'Indie Flower', 'Comic Sans MS', cursive;
  font-size: 0.7em;
  color: #c0392b;
  line-height: 1;          /* prevent the floating insertion from expanding line height */
}

/* D, E — letter additions inline as part of the kept stem. */
.draft-markup .ins-suffix,
.draft-markup .ins-prefix {
  font-family: 'Indie Flower', 'Comic Sans MS', cursive;
  color: #c0392b;
  font-size: 1em;          /* same size as surrounding text — looks like the student wrote it */
  text-decoration: none;
}
```

`.kept` segments deliberately have no rule — they inherit `font-family: Caveat`, `color: #1a4d80`, and weight 400 from `.draft-markup`.

**Layout invariants enforced by this CSS:**

1. **No horizontal expansion**: kept words flow normally; `.replace-pair` occupies the same horizontal width as its `<del>` child (the absolute-positioned `<ins>` doesn't claim flow space); `.gap-anchor` is zero-width.
2. **No paragraph height increase**: `.ins-above` uses `position: absolute` and `line-height: 1`, never participating in line height calculations. The 24px line stride is preserved.
3. **No new gaps between existing words**: the only gaps are the ones already present in the kept text. Inserted words slot above existing gaps, not beside them.

**Visual design choice on font/color/size pairing.** Indie Flower is a noticeably more childlike, casual handwriting than Caveat — distinct enough that a quick glance immediately separates "what the student wrote" from "what the teacher wrote on top". Size scaling: strikethroughs at 0.95em (close to natural reading size, since the student needs to see what they wrote), floating insertions at 0.7em (smaller because they live in the gap between lines and need to stay subordinate visually), inline suffix/prefix at 1em (looks like the missing letter is part of the original word).

**Visual tuning gates in Phase B.** Three values may need a small adjustment when first viewed in a browser on Week_1: (a) the `.del` strikethrough thickness (1.5px → 1px or 2px depending on legibility), (b) the `.ins-above` `bottom: 0.85em` offset (too low overlaps the kept text; too high overlaps the previous line), (c) the `.ins-above` font-size (0.7em → 0.65em if the gap above the line is too small). These are tuned once on Week_1 and propagated to all 40 files on the next script run.

### 8.6 localStorage persistence

| Key | Value | Written when |
|---|---|---|
| `ielts:draft:{filename}` | `{ draft, polished, markupHtml, timestamp }` | On textarea input (debounced 500ms); on successful correction; on Edit again (clears polished+markup, keeps draft) |

On `DOMContentLoaded`:
- If entry exists: repopulate `#student-draft`, and if `polished` is non-empty: also restore `#draft-markup` and `#polished-output`, hide textarea.
- Footer note in interactive HTMLs: `*Your work is saved on this device only / 您的作业仅保存在本设备*`

`clearDraft()` confirms with `confirm("清除草稿？/ Clear draft?")` then deletes the localStorage key and resets UI.

### 8.7 IPA tooltip (item 8)

On click of any bolded English word in `.vocab-table` or `.model-box`:
1. Always: speak the word via Web Speech API (default UK voice).
2. Lazy-load `pronunciations.json` (cached in `sessionStorage` after first fetch). The JSON is a small map `{ "word": "/ɪpə/" }` derived from CMU dict for vocabulary covered in the 40 lessons.
3. If word found in dict: show a small tooltip near the click position with the IPA for 3 seconds.
4. If not found: speak only, no tooltip.

`pronunciations.json` is generated as a one-off offline step from CMU IPA dict, scoped to vocabulary that appears in the 40 lesson HTMLs (extracted by the script). Expected size <500 KB.

### 8.8 Health check badge

On `DOMContentLoaded`:
- Fetch `${AI_ENDPOINT}/health` with 3-second timeout.
- If 200: show no badge.
- If error or timeout: show small `🔴 AI 离线 / AI offline` badge near the Correct button. The Correct button stays clickable (will show error on click) so the page is not artificially blocked.

### 8.9 `injectListenButtons()`

Runs on `DOMContentLoaded`:
1. For each `.model-box` element, prepend a positioned button row with 🇬🇧/🇺🇸/🐢/⏹ buttons. Position absolute, top right, slotted into the box's existing padding so no content shifts.
2. For each `<strong>` element inside `.vocab-table` or `.model-box`, attach a click handler that calls `lookupIPA(word)` (which speaks + tooltips).
3. Skip `.model-box` content within Chinese-gloss spans. Detection: an element is treated as a gloss if **either** of these applies — (a) `style` attribute contains `color: #7f8c8d` (the existing gray-gloss pattern), **or** (b) `lang="zh"` attribute is present. TTS does not read these elements, and click handlers are not attached to bolded text inside them.

### 8.10 `editAgain()` and `clearDraft()`

- `editAgain()`: hides `#draft-markup`, hides `#edit-again-btn`, clears `#polished-output`, shows `#student-draft` with its previous content, focuses it. Updates localStorage to clear `polished` + `markupHtml`.
- `clearDraft()`: as above plus empties `#student-draft` value and deletes localStorage entry.

### 8.12 Lined-paper overlay and scrolling

The pastel-green Draft and Polished Rewrite boxes have a fixed visible height (the existing flex layout). Student input or AI output that exceeds this height must scroll **inside** the box, not push the box taller, and must keep its line alignment intact while scrolling.

**Layout model.**

```
┌── pastel-green box (fixed height, never grows) ──┐
│  Draft:                  [count] [Correct] [Clear]│  ← labels & buttons absolute, top-right
│  ┌─ .lines-overlay-host (position: relative) ─┐  │
│  │  <div class="lines">  ← still in HTML,     │  │  display:none via CSS;
│  │                          covered visually   │  │  retained for script anchoring
│  │  <textarea> OR <div.draft-markup>           │  │  ← absolute, fills host
│  │    own lined background, scroll-aware       │  │
│  │  </…>                                       │  │
│  └─────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

**CSS:**

```css
/* Inserted CSS block adds these rules */

/* Hide the original .lines divs only inside .draft-page; they remain
   in HTML so make_interactive.py can anchor to them, and other .lines
   on spider-pages etc. are unaffected. */
.draft-page .lines { display: none; }

/* The wrapper sibling becomes the positioning context. */
.draft-page .lines-overlay-host {
  position: relative;
  flex-grow: 1;
  min-height: 0;             /* allow flex parent to constrain height */
  overflow: hidden;          /* clip overlay children to box bounds */
}

/* The three overlay elements share base layout. */
.writing-draft,
.draft-markup,
.writing-output {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  margin: 0;
  padding: 0 4px;            /* small horizontal breathing room */
  border: none;
  outline: none;
  resize: none;              /* applies to textarea */
  white-space: pre-wrap;
  overflow-y: auto;          /* SCROLL — fixed height, content overflows vertically */
  overflow-x: hidden;
  word-wrap: break-word;
  /* Lined background that scrolls WITH content. */
  background: repeating-linear-gradient(transparent, transparent 23px, #e0e0e0 24px);
  background-attachment: local;
  line-height: 24px;         /* MATCH the gradient stride so baselines sit on rules */
}

/* Caveat handwriting for student input, marked-up draft, AND polished output —
   identical font, size, and ink color so both boxes feel like the same notebook. */
.writing-draft,
.draft-markup,
.writing-output {
  font-family: 'Caveat', 'Bradley Hand', 'Comic Sans MS', cursive;
  font-size: 22px;            /* visually tuned so baseline sits on the rule */
  color: #1a4d80;             /* dark blue handwriting ink */
}
.writing-output.empty::before {
  content: "AI 修改后的版本会显示在这里 / The AI-corrected version will appear here.";
  color: #95a5a6;
  font-style: italic;
  font-family: 'Lato', sans-serif;   /* placeholder reads as printed prompt */
  font-size: 14px;
}

/* Buttons live in a single absolute-positioned row so they never overlap. */
.draft-page .button-row {
  position: absolute;
  top: 4px;
  right: 8px;
  z-index: 2;
  display: flex;
  flex-direction: row;
  gap: 6px;
  align-items: center;
}
.draft-page .ai-status {
  position: absolute;
  bottom: 4px;
  right: 8px;
  z-index: 2;
  font-size: 0.85em;
}

/* Defensive: ensure the pastel-green parent box is a column flex container.
   The originals already use this pattern (verified across all 40 files), but
   we re-assert it so the overlay model is robust against future template
   edits. */
.draft-page > div > div {
  display: flex;
  flex-direction: column;
}
```

The Draft section's button row contains, in order: `<span id="word-count">`, `<button id="correct-btn">`, then later (after correction) `<button id="edit-again-btn">`, `<button id="clear-draft-btn">` (with `#correct-btn` hiding when `#edit-again-btn` shows). The Polished section's `.button-row` contains the four `[🇬🇧][🇺🇸][🐢][⏹]` buttons.

**Scroll behavior:**

| Element | Behavior |
|---|---|
| `<textarea class="writing-draft">` | Browser-native textarea scroll. As the student types past the visible bottom, the textarea auto-scrolls to keep the caret in view. Scrollbar appears only when content overflows. |
| `<div class="draft-markup">` | Standard div scroll via `overflow-y: auto`. Student can scroll up/down through the marked-up draft after correction. |
| `<div class="writing-output">` | Same. The polished AI output scrolls if longer than the visible Polished Rewrite box. |

In all three cases, `background-attachment: local` ensures the gray rule lines scroll with the content — text always sits on a rule, never between rules due to scroll offset.

**Why the original `.lines` div stays in HTML even though it's hidden:** `make_interactive.py` pattern-matches against the existing structure. Hiding via CSS rather than removing keeps the regex anchors stable and makes the script trivially reversible. If a future change wants to fall back to the original (non-scrolling) lines, deleting our `display: none` rule restores the original visual.

### 8.13 Font embedding (no CDN dependency)

**Why embed:** Google Fonts (`fonts.googleapis.com`) is unreachable from mainland China without VPN. The interactive HTMLs are served to Chinese students from an Aliyun bucket; relying on Google's CDN would silently degrade to system fallbacks for the entire target audience. The handwriting visual is core to the pedagogy, so we embed.

**Mechanism:** two `@font-face` rules at the top of the inserted CSS block. Each `src:` is a `data:font/woff2;base64,...` URL containing the full woff2 file. No external HTTP request for fonts.

**CSS shape (truncated for spec):**

```css
@font-face {
  font-family: 'Caveat';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(data:font/woff2;base64,d09GMgABAAAAA...AAA==) format('woff2');
}
@font-face {
  font-family: 'Indie Flower';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(data:font/woff2;base64,d09GMgABAAAAA...AAA==) format('woff2');
}
```

**Font files** (committed to the repo at `scripts/fonts/`, fetched once from Google Fonts and stored as woff2):

| File | Source | Size (approx) |
|---|---|---|
| `Caveat-400.woff2` | https://fonts.gstatic.com/s/caveat/v18/Wnz6HAc5bAfYB2QRah7pcpNvOx-pjcB-tzJ7e3.woff2 | ~30 KB |
| `IndieFlower-400.woff2` | https://fonts.gstatic.com/s/indieflower/v22/m8JVjfNVeKWVnh3QMuKkFcZlbkGG1dKEDw.woff2 | ~26 KB |

**License:** SIL Open Font License (OFL). Free to embed and redistribute.

**Per-HTML size impact:** ~75 KB base64 inflation per file (Caveat ~40 KB + Indie Flower ~35 KB after base64 encoding). Acceptable for a 40-file static site; total bucket footprint ≈ 3 MB.

**make_interactive.py role:** at runtime, the script reads the two woff2 files from `scripts/fonts/`, base64-encodes them, and substitutes the `data:` URLs into the `@font-face` template. Output HTMLs are fully self-contained — they will render correctly with full handwriting fonts even on a network with zero external connectivity. The script raises a clear error if the font files are missing.

**Fallback chain in `font-family` declarations** (still used, defensively, in case the @font-face fails to parse for any reason):
- Caveat: `'Caveat', 'Bradley Hand', 'Comic Sans MS', cursive`
- Indie Flower: `'Indie Flower', 'Comic Sans MS', cursive`

### 8.11 Print suppression

```css
@media print {
  .ai-only,
  .tts-btn,
  .correct-btn,
  .word-count,
  .ai-status,
  #ai-status,
  #word-count,
  #correct-btn,
  #draft-markup,
  #polished-output,
  .listen-row {
    display: none !important;
  }
  .writing-draft {
    border: none;
    /* fall back to the original 8-hr writing space appearance */
  }
}
```

The original 8-line writing space is the canonical print path. Interactive HTML accidentally printed degrades gracefully.

## 9. Pedagogical features map

| # | Feature | Component |
|---|---|---|
| 1 | Red-pen markup over handwriting-style draft | §8.5 |
| 2 | Word-count traffic light | §8.3 |
| 3 | Karaoke highlighting during TTS | §8.2 |
| 4 | Print-friendly mode | §8.11 |
| 5 | localStorage draft + polished persistence | §8.6 |
| 6 | Slow-speech 🐢 button | §8.1 (rate=0.7) |
| 7 | Health-check badge | §8.8 |
| 8 | Click-word IPA tooltip | §8.7 |
| 9 | Edit again button | §8.10 |
| 10 | Clear draft button | §8.10 |

## 10. Testing strategy

### 10.1 Phase A — endpoint smoke test

After deploy:
```bash
# Valid request
curl -X POST "<URL>" -H "Content-Type: application/json" \
  -d '{"draft":"... a 50-word draft ..."}' | jq .

# Too-short rejection
curl -X POST "<URL>" -H "Content-Type: application/json" \
  -d '{"draft":"too short"}' | jq .

# OPTIONS preflight
curl -X OPTIONS "<URL>" -i

# Health check
curl "<URL>/health" | jq .
```

Expected: 200 with `{corrected}`, 400 with bilingual error, 204 OPTIONS, 200 health.

### 10.2 Phase B — single-file diff review

After running `make_interactive.py` against `Week_1_Lesson_Plan.html` only:
- Open the resulting `Interactive/Week_1_Lesson_Plan.html` in a browser.
- Visual: textarea, Correct button, Listen buttons positioned in `.model-box` corners without layout shift.
- Diff against original: only the three insertion points changed.
- Idempotency: re-run script, verify byte-identical output.

User signs off before propagating to other 39 files.

### 10.3 Phase C — end-to-end browser test

1. Open `https://<bucket-url>/Week_1_Lesson_Plan.html` (live).
2. Type a 50-word draft → click Correct → confirm red-pen markup over draft and clean polished version on right.
3. Type 5 words → click Correct → expect bilingual error.
4. Click 🇬🇧 then 🇺🇸 on a model answer — confirm karaoke highlighting tracks.
5. Click a bolded vocabulary word — confirm pronunciation + IPA tooltip.
6. Refresh page → confirm draft repopulates from localStorage.
7. Print preview → confirm AI elements hide.
8. WeChat browser test (manual, mobile) → confirm bilingual fallback alert.

## 11. Out of scope

- IGCSE port (separate repo, future).
- Server-side TTS (DashScope CosyVoice).
- Auth, accounts, server-side progress tracking.
- Cross-device draft sync.
- Speech recognition / shadow-and-compare.
- Editing original 40 HTMLs in place.
- Modifying `intro_packet.html`.
- Multi-turn conversation with the AI.

## 12. Open questions

1. **`Microsoft Sonia` etc. voice availability.** Voice names in the waterfall are matched at runtime; if a device lacks named neural voices, the waterfall falls through to "any en-GB" / "any en-US" cleanly. No pre-deploy verification needed.
2. **`pronunciations.json` size.** Final size depends on vocabulary breadth across 40 lessons. Target <500 KB. If it exceeds 1 MB, gzip the bucket file or ship a smaller core set + on-demand fetch. **Verify before Phase C.**
3. **Caveat font-size visual tuning.** The 22px starting value in §8.12 may need adjustment to put text baselines exactly on the 24px gray rules — verified visually on Week_1 in Phase B before propagation.

## 13. Required secrets, gating

| Phase gate | Secrets needed (lookup in `aliyun-handoff-secrets.md`) |
|---|---|
| Before Phase A deploy | Aliyun RAM AccessKey/SecretKey for `claude-mcp-user`; Zhipu API key |
| Before Phase C upload | Supabase service role key for `ra-supabase-eer8m96pab9mh2` |

Dev never asks for these until the gate.

## 14. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Zhipu free tier rate-limited per day | Medium | In-product bilingual quota error; instruct students to retry tomorrow |
| Web Speech voice availability poor on low-end Android | Medium | Voice waterfall falls through to any voice in locale; acceptable |
| Pattern-match in `make_interactive.py` fails on a file | Low (all 40 verified consistent) | Script logs skipped files in summary; user can fix the original and re-run |
| FC cold start adds 1–2 s to first correction | Certain | Acceptable for educational use; warm-up via health check on page load |
| WeChat in-app browser blocks Web Speech API | Certain (it does block) | Bilingual fallback alert directs students to Safari/Chrome |
| Bucket bandwidth quota | Low at 40 students | Existing AI School plan has headroom; monitor |
| FC concurrency cap at 100 | Low at 40 students | Default cap is enough; can bump if needed |
| Mixed-content warning if bucket only serves HTTP and pages embed external HTTPS resources (e.g. Google Fonts) | Medium | Verify Aliyun Supabase Storage exposes HTTPS for the public bucket before Phase C upload. If only HTTP available, host fonts locally or use a self-hosted CDN at the same scheme. |

## 15. Branch and merge strategy

- All work for this feature lives on `feat/ai-correction-and-tts` until Phase C green.
- Squash-merge to `main` after Phase C user sign-off.
- The `Interactive/`, `function-compute/`, `scripts/`, `docs/superpowers/specs/` folders enter `main` together.
- Originals on `main` remain untouched.

---

*End of spec.*
