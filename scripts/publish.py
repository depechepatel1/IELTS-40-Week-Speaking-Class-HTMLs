#!/usr/bin/env python3
"""Single-command publisher for IELTS course.

Runs the full pipeline in order:
  1. parse_data.py            — canonical PDF base + master Curiculum.json
                                 → lessons/Week_*.html × 40
  2. cp lessons/* . + cleanup — promote regenerated weeks to repo root
  3. make_interactive.py      — root Week_*.html → Interactive/Week_*.html
                                 + sync images/
  4. build_landing_page.py    — refresh index.html (auto-runs inside step 5
                                 if stale, but pre-running here lets us
                                 catch errors earlier with better logging)
  5. upload_to_oss.py         — push everything to aischool-ielts-bj
                                 with cache headers + skip-unchanged

Stops on first error. Verbose by default; pass --quiet to silence
non-error output.

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

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

# Configuration — would normally live in pipeline.yaml; loading the
# YAML adds a dependency, so we mirror the bucket/endpoint values here.
# Keep in sync with pipeline.yaml's `cdn.bucket_base` + `function_compute.endpoint`.
BUCKET_BASE = "https://lessons.aischool.studio"
FC_ENDPOINT = "https://ielts-arrection-nafrghqpzj.cn-beijing.fcapp.run"


def _step(label: str, cmd: list, *, quiet: bool, cwd: Path = REPO) -> None:
    print(f"\n{'─' * 60}")
    print(f"▶ {label}")
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    print(f"{'─' * 60}")
    t0 = time.time()
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=quiet,
        text=True,
    )
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"\n✗ FAILED after {elapsed:.1f}s")
        if quiet and result.stdout:
            print("--- stdout ---")
            print(result.stdout[-2000:])
        if quiet and result.stderr:
            print("--- stderr ---")
            print(result.stderr[-2000:])
        sys.exit(result.returncode)
    print(f"\n✓ done in {elapsed:.1f}s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true",
                    help="Suppress sub-command stdout (still prints on failure)")
    ap.add_argument("--skip-fanout", action="store_true",
                    help="Skip parse_data + make_interactive; only upload existing files")
    args = ap.parse_args()

    print(f"\n{'━' * 60}")
    print(f"  IELTS PUBLISH — full deploy to {BUCKET_BASE}")
    print(f"{'━' * 60}")

    if not args.skip_fanout:
        # 1. Regenerate Weeks 2-40 from canonical
        _step("1/5  parse_data.py — fan out canonical → Weeks 2-40",
              [sys.executable, "parse_data.py"], quiet=args.quiet)

        # 2. Promote lessons/ → root + cleanup
        lessons_dir = REPO / "lessons"
        if lessons_dir.is_dir():
            print(f"\n{'─' * 60}")
            print(f"▶ 2/5  Promote lessons/ → repo root")
            for f in sorted(lessons_dir.glob("Week_*.html")):
                shutil.copy2(f, REPO / f.name)
            shutil.rmtree(lessons_dir)
            print(f"  Copied {len(list(REPO.glob('Week_*.html')))} weeks; removed lessons/")
            print(f"✓ done")

        # 3. Build Interactive layer
        _step("3/5  make_interactive.py — bake Interactive/Week_*.html",
              [sys.executable, str(SCRIPTS / "make_interactive.py"),
               "--in", ".", "--out", "Interactive",
               "--endpoint", FC_ENDPOINT,
               "--bucket-base", BUCKET_BASE],
              quiet=args.quiet)

        # 4. Build landing page
        _step("4/5  build_landing_page.py — refresh index.html",
              [sys.executable, str(SCRIPTS / "build_landing_page.py")],
              quiet=args.quiet)
    else:
        print("\n[--skip-fanout] Skipping regeneration; uploading existing files.")

    # 5. Upload to OSS
    _step("5/5  upload_to_oss.py — push to aischool-ielts-bj",
          [sys.executable, str(SCRIPTS / "upload_to_oss.py")],
          quiet=args.quiet)

    print(f"\n{'━' * 60}")
    print(f"  PUBLISH COMPLETE — students can hit {BUCKET_BASE}/")
    print(f"{'━' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
