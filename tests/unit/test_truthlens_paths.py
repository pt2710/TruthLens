import os
import sys
import importlib.util
from pathlib import Path


def _load_truthlens_paths_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "truthlens_paths.py"
    spec = importlib.util.spec_from_file_location("truthlens_paths", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load truthlens_paths module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configure_repo_paths_adds_expected_entries(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    module = _load_truthlens_paths_module()
    monkeypatch.setenv("PYTHONPATH", "")

    module.configure_repo_paths(repo_root)

    expected_entries = [str((repo_root / relative_path).resolve()) for relative_path in module.SOURCE_PATHS]
    for entry in expected_entries:
        assert entry in sys.path
    assert os.environ["PYTHONPATH"].split(os.pathsep)[: len(expected_entries)] == expected_entries
