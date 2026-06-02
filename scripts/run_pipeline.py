from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    "01_collect_urls.py",
    "02_parse_books.py",
    "03_apply_overrides.py",
    "04_generate_yml.py",
    "05_validate_feed.py",
]


def main() -> None:
    for script in SCRIPTS:
        print(f"\n=== Running {script} ===")
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT)
        if result.returncode != 0:
            sys.exit(result.returncode)


if __name__ == "__main__":
    main()
