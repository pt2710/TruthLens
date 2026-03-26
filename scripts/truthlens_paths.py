from __future__ import annotations

import os
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


def configure_repo_paths(repo_root: Path | None = None) -> Path:
    resolved_root = repo_root or Path(__file__).resolve().parents[1]
    absolute_paths = [str((resolved_root / relative_path).resolve()) for relative_path in SOURCE_PATHS]

    for absolute_path in reversed(absolute_paths):
        if absolute_path not in sys.path:
            sys.path.insert(0, absolute_path)

    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    current_entries = [entry for entry in existing_pythonpath.split(os.pathsep) if entry]
    merged_entries = absolute_paths + [entry for entry in current_entries if entry not in absolute_paths]
    os.environ["PYTHONPATH"] = os.pathsep.join(merged_entries)
    return resolved_root
