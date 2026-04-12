from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from truthlens_paths import configure_repo_paths


def _storage_root() -> Path:
    from truthlens_data_pipeline.paths import runtime_storage_root

    return runtime_storage_root()


def _default_model_info_path() -> Path:
    return Path("artifacts/trained_models/latest/model_info.json").resolve()


def _destination_dir() -> Path:
    return _storage_root() / "artifacts" / "trained_models" / "latest"


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    configure_repo_paths()

    parser = argparse.ArgumentParser(
        description="Provision a promoted TruthLens runtime model bundle into the active storage root."
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        required=True,
        help="Path to the promoted model_bundle.pkl to copy into the runtime storage root.",
    )
    parser.add_argument(
        "--model-info",
        type=Path,
        default=_default_model_info_path(),
        help="Path to the aligned model_info.json. Defaults to artifacts/trained_models/latest/model_info.json.",
    )
    args = parser.parse_args()

    bundle_path = args.bundle.resolve()
    model_info_path = args.model_info.resolve()
    if not bundle_path.exists():
        raise SystemExit(f"Bundle not found: {bundle_path}")
    if not model_info_path.exists():
        raise SystemExit(f"Model info not found: {model_info_path}")

    destination_dir = _destination_dir()
    destination_bundle = destination_dir / "model_bundle.pkl"
    destination_info = destination_dir / "model_info.json"
    _copy_file(bundle_path, destination_bundle)
    _copy_file(model_info_path, destination_info)

    print(
        json.dumps(
            {
                "storage_root": str(_storage_root()),
                "destination_dir": str(destination_dir),
                "copied": {
                    "model_bundle": str(destination_bundle),
                    "model_info": str(destination_info),
                },
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
