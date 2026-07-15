"""Regenerate all test result markdown reports with per-test details."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTEST = [sys.executable, "-m", "pytest"]

SUITES: list[tuple[str, list[str]]] = [
    ("testresults_stap2_models.md", ["tests/unit/test_models.py"]),
    ("testresults_stap3_database.md", ["tests/unit/test_database.py"]),
    ("testresults_stap4_import.md", ["tests/unit/test_csv_import.py"]),
    ("testresults_all.md", []),
]


def main() -> int:
    for md_file, tests in SUITES:
        cmd = [*PYTEST, *tests, "-v", f"--md={md_file}", "--emoji", "--tb=short"]
        print(f"\n=== Generating {md_file} ===")
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            print(f"FAILED: {md_file}", file=sys.stderr)
            return result.returncode
        print(f"OK: {md_file}")
    print("\nAll test reports updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
