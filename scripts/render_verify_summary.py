from __future__ import annotations

import json

from truthlens_paths import configure_repo_paths

configure_repo_paths()


def main() -> None:
    from truthlens_evaluation import render_verify_summary

    summary = render_verify_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
