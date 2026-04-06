from __future__ import annotations

import argparse
import json

from truthlens_paths import configure_repo_paths

configure_repo_paths()


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote TruthLens runtime policy from committed governance artifacts.")
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "threshold-default", "bseo-shadow", "bseo-live"],
        help="Target runtime mode. 'auto' applies the current governance recommendation.",
    )
    args = parser.parse_args()

    from truthlens_evaluation import apply_runtime_promotion

    summary = apply_runtime_promotion(mode=args.mode)
    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
