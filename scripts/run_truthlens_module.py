from __future__ import annotations

import runpy
import sys

from truthlens_paths import configure_repo_paths


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/run_truthlens_module.py <module> [args...]")

    configure_repo_paths()
    module = sys.argv[1]
    sys.argv = [module, *sys.argv[2:]]
    runpy.run_module(module, run_name="__main__")


if __name__ == "__main__":
    main()
