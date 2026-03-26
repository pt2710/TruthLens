from __future__ import annotations

import runpy
import sys
from pathlib import Path


SOURCE_PATHS = [
    "apps/api/src",
    "apps/trainer/src",
    "libs/shared-schemas/python",
    "libs/feature-extractors/src",
    "libs/data-pipeline/src",
    "libs/dataset-governance/src",
    "libs/policy-engine/python",
    "libs/explanation-engine/python",
    "libs/evaluation/src",
    "libs/model-serving/python",
]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/run_truthlens_module.py <module> [args...]")

    repo_root = Path(__file__).resolve().parents[1]
    for relative_path in reversed(SOURCE_PATHS):
        sys.path.insert(0, str(repo_root / relative_path))

    module = sys.argv[1]
    sys.argv = [module, *sys.argv[2:]]
    runpy.run_module(module, run_name="__main__")


if __name__ == "__main__":
    main()
