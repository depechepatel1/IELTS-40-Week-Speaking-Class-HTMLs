#!/usr/bin/env python3
"""Extract Part 2 content from the 40 IELTS PDFs (Mar 30 2026 set) into a
curriculum JSON matching `master Curiculum.json`'s schema for
`lesson_1_part_2`.

Why this exists:
    The 'Latest IELTS Course PDFs 30th March 2026/' folder contains a
    40-PDF set that was generated from a curriculum source DIFFERENT from
    the current `master Curiculum.json`. Specifically: PDF Week 1 q2 is
    "Describe a teacher who has helped you learn..." (about a teacher),
    but `master Curiculum.json` Week 1 q2 is "Describe a family member who
    has achieved something great..." (about a family member). The user
    confirmed this drift when they said the PDFs have "new questions".

    Git archaeology (Phase A of Plan E) failed: NEITHER the current Apr 24
    `master Curiculum.json` NOR the historical Mar 5 version matches the
    PDFs. The source curriculum used to generate the Mar 30 PDFs was a
    local-only / unsaved file — genuinely lost.

    This script extracts Part 2 content directly from the PDFs using
    Claude Opus 4.7 with native PDF input + cache_control on the system
    prompt + forced tool use for structured output.

Pipeline:
    1. python extract_pdfs_to_curriculum.py
       -> writes per-week JSON files under .recovered_curriculum/per_week/
          AND a merged file curriculum_from_pdfs_2026-03-30.json
    2. Phase C of Plan E:
        cp "master Curiculum.json" "master Curiculum.json.backup_pre_pdf_sync"
        # Manual review of diff between current and extracted
        # then either replace lesson_1_part_2 keys OR replace whole file
    3. python parse_data.py  (regenerates 40 HTMLs)

Output schema per week (matches master Curiculum.json structure):
    {
        "week": int,
        "theme": str,
        "topic": str,
        "lesson_1_part_2": {
            "q1": {"html": <full HTML>, "spider_diagram_hints": [4 strs]},
            "q2": {"html": <full HTML>, "spider_diagram_hints": [4 strs]},
            "q3": {"html": <full HTML>, "spider_diagram_hints": [4 strs]}
        }
    }

Resumable: per-week files are saved as we go. Re-running skips already-
extracted weeks. Force re-extraction by deleting `.recovered_curriculum/
per_week/week_NN.json`.

Cost: ~$3-4 for 40 PDFs at Opus 4.7 (with prompt caching ~75% off after
first call).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("anthropic SDK not installed. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent
PDF_DIR = REPO_ROOT / "Latest IELTS Course PDFs 30th March 2026"
OUT_DIR = REPO_ROOT / ".recovered_curriculum"
PER_WEEK_DIR = OUT_DIR / "per_week"
MERGED_OUTPUT = OUT_DIR / "curriculum_from_pdfs_2026-03-30.json"

MODEL = "claude-opus-4-7"
RETRY_BACKOFF_S = (4, 10, 20)


# ---------------------------------------------------------------------------
# System prompt — cached. Describes the IELTS PDF structure, the target
# JSON schema, and the markup conventions Claude should reproduce in q1.html.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an IELTS Speaking course content extraction expert. You will be given a PDF for one week of a 40-week IELTS Speaking masterclass. Your job is to extract the Part 2 content — the cue cards, model answers, and brainstorming spider-diagram hints for the three Part 2 questions (q1, q2, q3) — and submit them via the `submit_curriculum` tool.

# PDF structure for one week (10 pages typical)

- **Page 1**: Cover (Week number + theme + topic).
- **Page 2**: Teacher Lesson Plan for Lesson 1 (NOT what we need).
- **Page 3**: STUDENT HANDOUT — PART 2 — has the **Cue Card** for q1 + the **Band 6.5 Model Answer** for q1, plus a Target Vocabulary table.
- **Page 4**: STUDENT HANDOUT — SPEAKING PRACTICE CIRCUIT — has the **Brainstorming Map** for q1 (with 4 spider-hint quadrants) + the **cue cards for q2 and q3** (with their 4 spider hints each). NO model answers for q2/q3 on this page.
- **Pages 5-10**: Lesson 2 Teacher Plan + Part 3 Discussion content (NOT what we need).

# Fields to extract per question

For each of q1, q2, q3:

**`cue_card_prompt`**: the imperative sentence ending in a period. Example for week 1 q1: "Describe a family member who you are proud of." For q2 it's typically "Describe a [person] who [action]." Drop the trailing question marks (cue cards end in `.` not `?`).

**`cue_card_bullets`**: exactly 4 bullets the candidate should cover, given after "You should say:". Example for q1: ["Who this person is", "When this happened", "What this person did", "And explain why you felt proud."]. The 4th always starts with "And explain". Each bullet is short (under 12 words).

**`model_answer_html`**: a single `<p>...</p>` paragraph (not multiple paragraphs) containing the Band 6.5 model answer. ALL THREE Qs need a model answer:
    - For q1: extract the visible Band 6.5 Model Answer from page 3 of the PDF AND reproduce its visual markup (see "Markup conventions" below).
    - For q2/q3: the PDF does NOT contain a model answer for these. GENERATE a Band 6.0–6.5 model answer (~80–110 words) in plain prose (no markup). Use a natural conversational register, simple-but-rich vocab, with transition phrases ("Honestly,", "To begin with,", "Actually,", "In the end,"). Topic must match the q2/q3 cue card.

**`spider_diagram_hints`**: exactly 4 strings — the brainstorming examples that visually appear in the 4 quadrants of the spider/mind-map. Each is short (1–4 words). Example for week 1 q1: ["Older sister", "Last month", "Graduated college", "Felt inspired"]. The order must match the cue card bullets order: bullet 1 → hint 1, bullet 2 → hint 2, etc.

# Markup conventions — for q1 model_answer_html ONLY

Reproduce the visual highlighting that the PDF page 3's Band 6.5 Model Answer shows. The model answer paragraph uses these inline tags:

1. **`<mark class="highlight-yellow">...</mark>`** wraps the FIRST sentence of the answer (typically the opening 3-clause complex sentence — e.g., "To begin with, I want to talk about my uncle, who is an accomplished doctor, because I truly look up to him."). In the PDF this sentence appears with a yellow background highlight.

2. **`<span class="highlight-transition">...</span>`** wraps EACH transition phrase. These are visible in the PDF as colored (often blue) words at the start of clauses. Examples: "To begin with,", "Actually,", "Whenever his patients need help,", "In fact,", "For example,", "I think,", "To be honest,", "However,", "In the end,". The trailing comma IS part of the wrapped span.

3. **`<strong>vocab (中文)</strong>`** wraps each highlighted vocabulary word PLUS its inline Chinese gloss in parentheses. Example: `<strong>accomplished (有造诣的 / 成功的)</strong>`. The PDF shows these vocab words in bold; the Chinese gloss in parentheses is part of the strong-tagged span. Multiple words per paragraph (typically 6–8).

4. Plain text is unwrapped. Use spaces normally (no HTML entities like `&nbsp;`).

Concrete EXAMPLE of correct q1 model_answer_html for Week 1:
```
<p><mark class="highlight-yellow"><span class="highlight-transition">To begin with,</span> I want to talk about my uncle, who is an <strong>accomplished (有造诣的 / 成功的)</strong> doctor, because I truly <strong>look up to (敬仰)</strong> him.</mark> <span class="highlight-transition">Actually,</span> he is a very <strong>diligent (勤奋的)</strong> person who always puts others first. <span class="highlight-transition">Whenever his patients need help,</span> he is <strong>considerate (体贴的)</strong> and completely <strong>selfless (无私的)</strong>. <span class="highlight-transition">In fact,</span> he has a <strong>generous (慷慨的)</strong> nature and essentially has <strong>a heart of gold (心地善良)</strong>. <span class="highlight-transition">For example,</span> he will always <strong>go the extra mile (加倍努力)</strong> to ensure (确保) everyone is safe. <span class="highlight-transition">I think,</span> seeing his <strong>devoted (挚爱的 / 忠诚的)</strong> attitude is highly <strong>inspiring (鼓舞人心的)</strong> to me. <span class="highlight-transition">To be honest,</span> I felt so proud when he saved a life last year.</p>
```

For q2 / q3: write `<p>...</p>` with PLAIN prose (no marks/spans/strongs), since these don't appear in the PDF and we're filling them in ourselves. Example for q2:
```
<p>Honestly, I want to talk about my older cousin and her amazing achievements. Last year, she managed to start her own successful coffee shop in our city. To make this happen, she worked day and night to save enough money. ...</p>
```

# Theme + topic + week number

These appear on the cover (Page 1):
- **`week`**: integer 1–40
- **`theme`**: ALL-CAPS theme on the cover (e.g., "PEOPLE", "PLACES", "OBJECTS"). Convert to title case in your output (e.g., "People").
- **`topic`**: the descriptive subtitle, in the format "A Family Member You Are Proud Of" (Title Case).

# What to do

Submit ONE call to the `submit_curriculum` tool with all 4 top-level fields populated. Do not include preamble or commentary in your response — just the tool call."""


# ---------------------------------------------------------------------------
# Tool schema (forced tool use). Mirrors the structure submitted at runtime.
# ---------------------------------------------------------------------------
def _q_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "cue_card_prompt": {
                "type": "string",
                "description": "Imperative sentence ending in '.', e.g. 'Describe a person who...'"
            },
            "cue_card_bullets": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 4, "maxItems": 4,
                "description": "Exactly 4 bullets that follow 'You should say:'. 4th starts with 'And explain'."
            },
            "model_answer_html": {
                "type": "string",
                "description": "Single <p>...</p>. For q1: rich markup (mark/span/strong). For q2/q3: plain prose, ~80-110 words, generated."
            },
            "spider_diagram_hints": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 4, "maxItems": 4,
                "description": "4 short brainstorming examples matching the bullets order."
            }
        },
        "required": ["cue_card_prompt", "cue_card_bullets", "model_answer_html", "spider_diagram_hints"],
        "additionalProperties": False,
    }


TOOL = {
    "name": "submit_curriculum",
    "description": "Submit the extracted Part 2 curriculum for one week.",
    "input_schema": {
        "type": "object",
        "properties": {
            "week": {"type": "integer", "minimum": 1, "maximum": 40},
            "theme": {"type": "string", "description": "Title-case theme, e.g. 'People'."},
            "topic": {"type": "string", "description": "Descriptive subtitle in Title Case."},
            "lesson_1_part_2": {
                "type": "object",
                "properties": {
                    "q1": _q_schema(),
                    "q2": _q_schema(),
                    "q3": _q_schema(),
                },
                "required": ["q1", "q2", "q3"],
                "additionalProperties": False,
            },
        },
        "required": ["week", "theme", "topic", "lesson_1_part_2"],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def encode_pdf(pdf_path: Path) -> str:
    return base64.b64encode(pdf_path.read_bytes()).decode("ascii")


def assemble_q_html(q: dict) -> dict:
    """Convert tool output (with cue_card_prompt + bullets + model_answer_html
    fields) into the schema master Curiculum.json uses (single `html` field)."""
    bullets_html = "<br>".join(b.strip() for b in q["cue_card_bullets"])
    cue_p = f"<p>{q['cue_card_prompt'].strip()} You should say:<br>{bullets_html}</p>"
    # model_answer_html should already be a <p>...</p> from the model.
    answer = q["model_answer_html"].strip()
    if not answer.startswith("<p"):
        answer = f"<p>{answer}</p>"
    return {
        "html": f"{cue_p}\n{answer}",
        "spider_diagram_hints": q["spider_diagram_hints"],
    }


def call_claude(client, week_num: int, pdf_path: Path):
    """One API call per PDF. Returns (week_dict, usage_dict)."""
    pdf_b64 = encode_pdf(pdf_path)
    user_content = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_b64,
            },
        },
        {
            "type": "text",
            "text": (
                f"Extract the Part 2 content from this PDF for Week {week_num}. "
                f"Submit your answer via the submit_curriculum tool. Remember: "
                f"q1 model_answer_html should mirror the rich-markup model answer "
                f"on page 3 of the PDF; q2 and q3 model_answer_html should be "
                f"GENERATED in plain prose (~80-110 words) since they are not in "
                f"the PDF. All three need 4 spider_diagram_hints from page 4."
            ),
        },
    ]

    last_err = None
    for backoff_s in RETRY_BACKOFF_S:
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[TOOL],
                tool_choice={"type": "tool", "name": "submit_curriculum"},
                messages=[{"role": "user", "content": user_content}],
            )
            tool_block = next(
                (b for b in resp.content if getattr(b, "type", None) == "tool_use"),
                None,
            )
            if tool_block is None:
                raise ValueError("no tool_use block in response")
            data = tool_block.input  # already a dict
            usage = {
                "input": getattr(resp.usage, "input_tokens", 0),
                "output": getattr(resp.usage, "output_tokens", 0),
                "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
                "cache_write": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
            }
            return data, usage
        except (anthropic.RateLimitError, anthropic.APIConnectionError) as e:
            last_err = e
            print(f"  transient error ({type(e).__name__}); sleeping {backoff_s}s",
                  file=sys.stderr)
            time.sleep(backoff_s)
        except (ValueError, KeyError) as e:
            last_err = e
            print(f"  schema error: {e}; sleeping {backoff_s}s", file=sys.stderr)
            time.sleep(backoff_s)
    raise RuntimeError(f"failed after {len(RETRY_BACKOFF_S)} retries: {last_err}")


def normalise_to_master_schema(raw: dict) -> dict:
    """Convert the tool output to the master Curiculum.json schema (with
    assembled `html` fields per question instead of separate cue_card / answer
    fields)."""
    p2 = raw["lesson_1_part_2"]
    return {
        "week": raw["week"],
        "theme": raw["theme"],
        "topic": raw["topic"],
        "lesson_1_part_2": {
            "q1": assemble_q_html(p2["q1"]),
            "q2": assemble_q_html(p2["q2"]),
            "q3": assemble_q_html(p2["q3"]),
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", default="1-40",
                    help="Week range (e.g. '1-40', '5,10', '21'). Default: all 40.")
    ap.add_argument("--force", action="store_true",
                    help="Re-extract even if per-week file already exists.")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not in env.", file=sys.stderr)
        return 2
    if not PDF_DIR.is_dir():
        print(f"ERROR: PDF dir not found: {PDF_DIR}", file=sys.stderr)
        return 2

    PER_WEEK_DIR.mkdir(parents=True, exist_ok=True)

    # Parse week range.
    target_weeks = set()
    for tok in args.weeks.split(","):
        tok = tok.strip()
        if "-" in tok:
            a, b = tok.split("-", 1)
            target_weeks.update(range(int(a), int(b) + 1))
        elif tok:
            target_weeks.add(int(tok))

    client = anthropic.Anthropic()
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    failures = []
    successes = []
    skipped = []

    for week in sorted(target_weeks):
        per_week_path = PER_WEEK_DIR / f"week_{week:02d}.json"
        if per_week_path.exists() and not args.force:
            skipped.append(week)
            continue
        pdf_path = PDF_DIR / f"Week_{week}_Lesson_Plan.pdf"
        if not pdf_path.exists():
            print(f"  Week {week:>2}: PDF NOT FOUND at {pdf_path}", file=sys.stderr)
            failures.append(week)
            continue

        print(f"  Week {week:>2}: extracting from {pdf_path.name}...", end=" ", flush=True)
        try:
            raw, usage = call_claude(client, week, pdf_path)
            normalised = normalise_to_master_schema(raw)
            with per_week_path.open("w", encoding="utf-8") as f:
                json.dump(normalised, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"FAILED — {e}")
            failures.append(week)
            continue

        for k in totals:
            totals[k] += usage[k]
        cache_marker = (
            "HIT" if usage["cache_read"] > 0
            else ("WRITE" if usage["cache_write"] > 0 else "MISS")
        )
        print(
            f"in={usage['input']:>5} out={usage['output']:>4} "
            f"cache={cache_marker:5s} (read={usage['cache_read']}, write={usage['cache_write']})"
        )
        successes.append(week)

    # Merge all per-week files into the master output.
    merged = []
    for w in range(1, 41):
        p = PER_WEEK_DIR / f"week_{w:02d}.json"
        if p.exists():
            merged.append(json.loads(p.read_text(encoding="utf-8")))
    with MERGED_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\nProcessed: {len(successes)} | Skipped (already done): {len(skipped)} | Failed: {len(failures)}")
    print(f"Merged file: {MERGED_OUTPUT} ({len(merged)} weeks)")
    print("\nUsage totals:")
    print(f"  Input tokens:        {totals['input']:>7}")
    print(f"  Output tokens:       {totals['output']:>7}")
    print(f"  Cache reads (~10%):  {totals['cache_read']:>7}")
    print(f"  Cache writes (125%): {totals['cache_write']:>7}")

    if failures:
        print(f"\nFAILED weeks: {failures}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
