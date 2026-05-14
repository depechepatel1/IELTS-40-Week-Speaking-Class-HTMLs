#!/usr/bin/env python3
"""Single-command publisher for IELTS course.

Runs the full pipeline in order:
  1. parse_data.py                 — canonical PDF base + master Curiculum.json
                                      → lessons/Week_*.html × 40 (separate D+P)
  2. cp lessons/* . + cleanup      — promote regenerated weeks to repo root
  3. make_interactive.py           — root Week_*.html → Interactive/Week_*.html
                                      with AI overlay on separate Draft +
                                      Polished Rewrite boxes
  4. post_merge_draft_polished.py  — combine D+P → single "AI corrected" box
                                      in root Week_*.html (PDF base printable
                                      only — Interactive keeps separate D+P).
                                      Asymmetric merge, same pattern as IGCSE's
                                      post_merge_section_7_8.py.
  5. build_landing_page.py         — refresh index.html
  6. upload_to_oss.py              — push everything to aischool-ielts-bj
                                      with cache headers + skip-unchanged
  7. check_cert_expiry.py          — non-fatal: warn if SSL cert <30 days
  8. verify_no_drift.py            — non-fatal: confirm Week_05 / 22 / 38
                                      share canonical Week_01's static blocks
                                      (cover CSS, fonts, footer, page numbers)

Stops on first error in steps 1-6. Steps 7-8 are warn-only. Verbose
by default; pass --quiet to silence non-error output.

Usage:
  python scripts/publish.py
  python scripts/publish.py --quiet
  python scripts/publish.py --skip-fanout    # only upload (no regen)
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Windows console defaults to cp1252; force UTF-8 so Unicode arrows/dashes
# in our step labels don't blow up.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

# Configuration — would normally live in pipeline.yaml; loading the
# YAML adds a dependency, so we mirror the bucket/endpoint values here.
# Keep in sync with pipeline.yaml's `cdn.bucket_base` + `function_compute.endpoint`.
BUCKET_BASE = "https://ielts.aischool.studio"
FC_ENDPOINT = "https://ielts-arrection-nafrghqpzj.cn-beijing.fcapp.run"


def _step(label: str, cmd: list, *, quiet: bool, cwd: Path = REPO) -> None:
    print(f"\n{'-' * 60}")
    print(f">> {label}")
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    print(f"{'-' * 60}")
    t0 = time.time()
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=quiet,
        text=True,
    )
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"\n[FAIL] after {elapsed:.1f}s")
        if quiet and result.stdout:
            print("--- stdout ---")
            print(result.stdout[-2000:])
        if quiet and result.stderr:
            print("--- stderr ---")
            print(result.stderr[-2000:])
        sys.exit(result.returncode)
    print(f"\n[ok] done in {elapsed:.1f}s")


def _commit_and_push(*, quiet: bool) -> None:
    """Round 52 — post-publish guardrail: commit the just-published state
    and push it, so git history + GitHub never drift behind what's live
    (before Round 51 the repo had ~13 rounds of uncommitted, already-live
    work). Runs AFTER the fan-out, so it captures the regenerated
    Week_*.html / Interactive/Week_*.html output — the actual deployed
    bytes. `.claude/` is excluded: machine-local tooling, and it holds an
    embedded worktree git repo. Commit is skipped when the tree is already
    clean. Push failure is a loud WARNING, not fatal — the deploy already
    succeeded and the local commit is the safety net; the next publish
    retries the push.
    """
    print(f"\n{'-' * 60}")
    print(f">> Post-publish: commit + push (keeps git + GitHub in sync with live)")
    print(f"{'-' * 60}")
    try:
        # Stage everything, then unstage machine-local tooling.
        subprocess.run(["git", "add", "-A"], cwd=str(REPO), check=True)
        subprocess.run(["git", "reset", "-q", "--", ".claude"], cwd=str(REPO))
        has_staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=str(REPO)
        ).returncode != 0
        if has_staged:
            stamp = time.strftime("%Y-%m-%d %H:%M")
            msg = f"Publish fan-out — regenerated output ({stamp})"
            subprocess.run(["git", "commit", "-m", msg], cwd=str(REPO), check=True)
            print(f"  committed: {msg}")
        else:
            print("  working tree clean — nothing new to commit")
        push = subprocess.run(
            ["git", "push"], cwd=str(REPO), capture_output=True, text=True
        )
        if push.returncode == 0:
            print("  pushed to origin")
        else:
            print("  [WARN] git push failed (NON-FATAL — the local commit is the "
                  "safety net; the next publish will retry the push):")
            for line in (push.stderr or push.stdout or "").strip().splitlines():
                print(f"    {line}")
    except Exception as e:
        print(f"  [WARN] commit/push step error (non-fatal): {type(e).__name__}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true",
                    help="Suppress sub-command stdout (still prints on failure)")
    ap.add_argument("--skip-fanout", action="store_true",
                    help="Skip parse_data + make_interactive; only upload existing files")
    args = ap.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  IELTS PUBLISH — full deploy to {BUCKET_BASE}")
    print(f"{'=' * 60}")

    # Round 52 — friendly notice if the tree is dirty going in. The
    # post-publish commit+push step captures everything regardless, but a
    # descriptive source commit BEFORE publishing keeps history readable.
    _dirty = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO),
                            capture_output=True, text=True)
    _dirty_lines = [ln for ln in _dirty.stdout.splitlines()
                    if ln.strip() and ".claude/" not in ln]
    if _dirty_lines:
        print(f"\n  note: {len(_dirty_lines)} uncommitted change(s) present — they'll be")
        print(f"        captured by the post-publish commit+push step. For cleaner")
        print(f"        history, commit source changes with a descriptive message first.")

    if not args.skip_fanout:
        # 0. Preflight: validate homework_plan.json shape (warn-only).
        #    Catches data drift like a stray 6th grammar item that pushes
        #    the answer-key footer off the homework page (Week 2 bug
        #    discovered 2026-05-03). Non-fatal — publish still proceeds.
        print(f"\n{'-' * 60}")
        print(f">> Preflight: verify_homework_data.py")
        print(f"{'-' * 60}")
        prevf = subprocess.run(
            [sys.executable, str(SCRIPTS / "verify_homework_data.py")],
            cwd=str(REPO),
        )
        if prevf.returncode != 0:
            print(f"  (non-fatal: data validation returned {prevf.returncode}; "
                  f"fan-out will use the data as-is)")

        # 1. Regenerate Weeks 2-40 from canonical
        _step("1/5  parse_data.py — fan out canonical → Weeks 2-40",
              [sys.executable, "parse_data.py"], quiet=args.quiet)

        # 2. Promote lessons/ → root + cleanup
        lessons_dir = REPO / "lessons"
        if lessons_dir.is_dir():
            print(f"\n{'-' * 60}")
            print(f"▶ 2/5  Promote lessons/ → repo root")
            for f in sorted(lessons_dir.glob("Week_*.html")):
                shutil.copy2(f, REPO / f.name)
            # Round 28b (2026-05-03): on Windows + OneDrive the directory
            # often holds a file-system lock for a few seconds after the
            # last file inside it is copied/moved, causing
            # `shutil.rmtree` to raise PermissionError [WinError 5] even
            # though the directory is empty. Don't let that abort the
            # publish — the empty dir is harmless and the next parse_data
            # run will repopulate it. ignore_errors=True swallows the
            # transient lock; if it's a real issue (read-only mount),
            # the next step will surface it.
            shutil.rmtree(lessons_dir, ignore_errors=True)
            print(f"  Copied {len(list(REPO.glob('Week_*.html')))} weeks; "
                  f"lessons/ removed={'no (file lock)' if lessons_dir.exists() else 'yes'}")
            print(f"✓ done")

        # 3. Build Interactive layer
        _step("3/6  make_interactive.py — bake Interactive/Week_*.html",
              [sys.executable, str(SCRIPTS / "make_interactive.py"),
               "--in", ".", "--out", "Interactive",
               "--endpoint", FC_ENDPOINT,
               "--bucket-base", BUCKET_BASE],
              quiet=args.quiet)

        # 4. Asymmetric merge: combine Draft + Polished Rewrite into a single
        #    "AI corrected" box on the printable PDF base files (root Week_*.html).
        #    Runs AFTER make_interactive.py so the Interactive layer keeps the
        #    separate Draft + Polished structure (with AI overlay). Same pattern
        #    as IGCSE's post_merge_section_7_8.py.
        _step("4/6  post_merge_draft_polished.py — combine D+P boxes in PDF base",
              [sys.executable, str(SCRIPTS / "post_merge_draft_polished.py")],
              quiet=args.quiet)

        # 5. Build landing page
        _step("5/6  build_landing_page.py — refresh index.html",
              [sys.executable, str(SCRIPTS / "build_landing_page.py")],
              quiet=args.quiet)
    else:
        print("\n[--skip-fanout] Skipping regeneration; uploading existing files.")

    # 6. Upload to OSS
    _step("6/6  upload_to_oss.py — push to aischool-ielts-bj",
          [sys.executable, str(SCRIPTS / "upload_to_oss.py")],
          quiet=args.quiet)

    # 6. Cert expiry sanity check — non-fatal, warn-only.
    print(f"\n{'-' * 60}")
    print(f">> Post-publish: cert expiry check")
    print(f"{'-' * 60}")
    cert_result = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_cert_expiry.py")],
        cwd=str(REPO),
    )
    if cert_result.returncode != 0:
        print(f"  (non-fatal: cert check returned {cert_result.returncode})")

    # 7. Drift verification — non-fatal, warn-only. Confirms parse_data.py
    #    didn't accidentally regenerate static blocks (cover CSS, fonts, footer,
    #    page-numbering) in any of the sampled fan-out weeks.
    print(f"\n{'-' * 60}")
    print(f">> Post-publish: drift verification (Week_05 / 22 / 38 vs canonical)")
    print(f"{'-' * 60}")
    drift_result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_no_drift.py")],
        cwd=str(REPO),
    )
    if drift_result.returncode != 0:
        print(f"  (non-fatal: drift check returned {drift_result.returncode})")

    # Round 52 — commit + push the just-published state (git stays in sync
    # with live; see CLAUDE.md "Commit & publish discipline").
    _commit_and_push(quiet=args.quiet)

    print(f"\n{'=' * 60}")
    print(f"  PUBLISH COMPLETE — students can hit {BUCKET_BASE}/")
    print(f"{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
