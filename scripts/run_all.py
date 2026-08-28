from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

COMMANDS = [
    [sys.executable, str(ROOT / "scripts" / "check_rdf.py")],
    [sys.executable, str(ROOT / "scripts" / "validate_shacl.py")],
    [sys.executable, str(ROOT / "scripts" / "reason.py")],
    [sys.executable, str(ROOT / "scripts" / "run_queries.py")],
    [sys.executable, "-m", "pytest", "-q"],
]


def main() -> int:
    for command in COMMANDS:
        print("\n$", " ".join(command))
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
