from __future__ import annotations

import argparse

import uvicorn

from truthlens_paths import configure_repo_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TruthLens API with repo-local import paths.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    repo_root = configure_repo_paths()
    uvicorn.run(
        "truthlens_api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(repo_root)],
    )


if __name__ == "__main__":
    main()
