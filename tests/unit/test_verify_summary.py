from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from truthlens_data_pipeline.paths import read_json
from truthlens_evaluation import render_verify_summary


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _completed_process(command: list[str], returncode: int, output: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout=output, stderr="")


def test_render_verify_summary_writes_truth_surface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))
    _write_json(
        tmp_path / "docs/benchmarks/latest/benchmark_summary.json",
        {
            "build_id": "build-test",
            "model_version": "baseline-v1-build-test",
            "sample_count": 4,
            "runtime_truth": {
                "configured_policy_mode": "threshold-default",
                "resolved_policy_mode": "threshold-default",
                "recommended_policy_mode": "threshold-default",
            },
        },
    )

    def runner(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        assert cwd == tmp_path
        return _completed_process(command, 0, f"ok from {tmp_path}: {' '.join(command)}")

    summary = render_verify_summary(
        commands=[
            {"name": "pytest", "command": [str(tmp_path / ".venv/Scripts/python.exe"), "-m", "pytest", "-q"]},
            {"name": "pnpm-test", "command": ["pnpm", "test"]},
        ],
        root=tmp_path,
        runner=runner,
    )

    verify_summary = read_json(tmp_path / "docs/benchmarks/latest/verify_summary.json")
    verify_markdown = (tmp_path / "docs/benchmarks/latest/verify_summary.md").read_text(encoding="utf-8")

    assert summary["overall_status"] == "passed"
    assert verify_summary["passed_count"] == 2
    assert verify_summary["benchmark_context"]["build_id"] == "build-test"
    assert (
        verify_summary["commands"][0]["command"][0].replace("\\", "/")
        == "<repo>/.venv/Scripts/python.exe"
    )
    assert str(tmp_path) not in verify_markdown
    assert "<repo>" in verify_markdown
    assert "| `pytest` | `passed` | 0 |" in verify_markdown
    assert "Command: `pnpm test`" in verify_markdown


def test_render_verify_summary_raises_after_writing_failed_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRUTHLENS_REPO_ROOT", str(tmp_path))

    def runner(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _completed_process(command, 1, "boom")

    with pytest.raises(SystemExit):
        render_verify_summary(
            commands=[{"name": "pytest", "command": ["py", "-m", "uv", "run", "pytest", "-q"]}],
            root=tmp_path,
            runner=runner,
        )

    verify_summary = read_json(tmp_path / "docs/benchmarks/latest/verify_summary.json")
    assert verify_summary["overall_status"] == "failed"
    assert verify_summary["failed_count"] == 1
