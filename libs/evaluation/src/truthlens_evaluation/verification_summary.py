from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, TypedDict

from truthlens_data_pipeline.paths import ensure_dir, read_json, repo_root, utc_now, write_json


class VerifyCommandSpec(TypedDict):
    name: str
    command: list[str]


class VerifyCommandResult(TypedDict):
    name: str
    command: list[str]
    exit_code: int
    status: str
    duration_seconds: float
    output_excerpt: str


class VerifySummary(TypedDict):
    generated_at: str
    overall_status: str
    command_count: int
    passed_count: int
    failed_count: int
    total_duration_seconds: float
    benchmark_context: dict[str, object]
    outputs: dict[str, str]
    commands: list[VerifyCommandResult]
    caveats: list[str]


CommandRunner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]


def _powershell_command(command: str) -> list[str]:
    return [
        "powershell",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        command,
    ]


def default_verify_commands() -> list[VerifyCommandSpec]:
    python_executable = sys.executable
    return [
        {"name": "pytest", "command": [python_executable, "-m", "pytest", "-q"]},
        {"name": "ruff", "command": [python_executable, "-m", "ruff", "check", "."]},
        {"name": "mypy", "command": [python_executable, "-m", "mypy", "."]},
        {"name": "pnpm-typecheck", "command": _powershell_command("pnpm typecheck")},
        {"name": "pnpm-test", "command": _powershell_command("pnpm test")},
        {"name": "pnpm-build", "command": _powershell_command("pnpm build")},
        {"name": "docs-render-architecture", "command": _powershell_command("pnpm docs:render-architecture")},
        {"name": "docs-render-benchmarks", "command": [python_executable, "scripts/render_benchmark_visualizations.py"]},
        {"name": "pnpm-test-e2e", "command": _powershell_command("pnpm test:e2e")},
    ]


def _default_runner(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _truncate_output(stdout: str, stderr: str, *, max_chars: int = 4000) -> str:
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    if not combined:
        return "(no output)"
    if len(combined) <= max_chars:
        return combined
    return f"{combined[:max_chars].rstrip()}\n... [truncated]"


def _sanitize_public_text(value: str, root: Path) -> str:
    sanitized = value
    root_variants = {
        str(root),
        str(root).replace("\\", "/"),
        root.as_posix(),
    }
    for root_value in sorted(root_variants, key=len, reverse=True):
        if root_value:
            sanitized = sanitized.replace(root_value, "<repo>")
    return sanitized


def _sanitize_public_command(command: list[str], root: Path) -> list[str]:
    return [_sanitize_public_text(part, root) for part in command]


def run_verify_commands(
    *,
    commands: list[VerifyCommandSpec] | None = None,
    root: Path | None = None,
    runner: CommandRunner | None = None,
) -> list[VerifyCommandResult]:
    resolved_root = root or repo_root()
    active_runner = runner or _default_runner
    results: list[VerifyCommandResult] = []
    for spec in commands or default_verify_commands():
        start = time.perf_counter()
        try:
            completed = active_runner(spec["command"], resolved_root)
            exit_code = int(completed.returncode)
            output_excerpt = _sanitize_public_text(
                _truncate_output(completed.stdout, completed.stderr),
                resolved_root,
            )
        except FileNotFoundError as exc:
            exit_code = 127
            output_excerpt = _sanitize_public_text(
                _truncate_output("", str(exc)),
                resolved_root,
            )
        duration_seconds = round(time.perf_counter() - start, 3)
        results.append(
            {
                "name": spec["name"],
                "command": _sanitize_public_command(list(spec["command"]), resolved_root),
                "exit_code": exit_code,
                "status": "passed" if exit_code == 0 else "failed",
                "duration_seconds": duration_seconds,
                "output_excerpt": output_excerpt,
            }
        )
    return results


def _load_benchmark_context(root: Path) -> dict[str, object]:
    benchmark_path = root / "docs/benchmarks/latest/benchmark_summary.json"
    if not benchmark_path.exists():
        return {
            "available": False,
            "path": "docs/benchmarks/latest/benchmark_summary.json",
        }

    benchmark_summary = read_json(benchmark_path)
    runtime_truth = benchmark_summary.get("runtime_truth", {})
    return {
        "available": True,
        "path": "docs/benchmarks/latest/benchmark_summary.json",
        "build_id": benchmark_summary.get("build_id"),
        "model_version": benchmark_summary.get("model_version"),
        "sample_count": benchmark_summary.get("sample_count"),
        "configured_policy_mode": runtime_truth.get("configured_policy_mode"),
        "resolved_policy_mode": runtime_truth.get("resolved_policy_mode"),
        "recommended_policy_mode": runtime_truth.get("recommended_policy_mode"),
    }


def build_verify_summary(
    command_results: list[VerifyCommandResult],
    *,
    root: Path | None = None,
) -> VerifySummary:
    resolved_root = root or repo_root()
    passed_count = sum(1 for result in command_results if result["status"] == "passed")
    failed_count = len(command_results) - passed_count
    caveats: list[str] = []
    benchmark_context = _load_benchmark_context(resolved_root)
    if not benchmark_context.get("available"):
        caveats.append("No committed benchmark summary was found while rendering the verify summary.")
    if failed_count:
        caveats.append("One or more verification commands failed. Inspect the command table and excerpts below.")

    return {
        "generated_at": utc_now(),
        "overall_status": "passed" if failed_count == 0 else "failed",
        "command_count": len(command_results),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "total_duration_seconds": round(sum(result["duration_seconds"] for result in command_results), 3),
        "benchmark_context": benchmark_context,
        "outputs": {
            "json": "docs/benchmarks/latest/verify_summary.json",
            "markdown": "docs/benchmarks/latest/verify_summary.md",
        },
        "commands": command_results,
        "caveats": caveats,
    }


def _render_markdown(summary: VerifySummary) -> str:
    lines = [
        "# TruthLens Verify Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Commands passed: `{summary['passed_count']}/{summary['command_count']}`",
        f"- Total duration (s): `{summary['total_duration_seconds']}`",
        "",
    ]

    benchmark_context = summary["benchmark_context"]
    if benchmark_context.get("available"):
        lines.extend(
            [
                "## Benchmark Context",
                "",
                f"- Build ID: `{benchmark_context.get('build_id')}`",
                f"- Model version: `{benchmark_context.get('model_version')}`",
                f"- Eval sample count: `{benchmark_context.get('sample_count')}`",
                f"- Configured runtime mode: `{benchmark_context.get('configured_policy_mode')}`",
                f"- Resolved runtime mode: `{benchmark_context.get('resolved_policy_mode')}`",
                f"- Recommended runtime mode: `{benchmark_context.get('recommended_policy_mode')}`",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Benchmark Context",
                "",
                "- No benchmark summary was available when this verify artifact was generated.",
                "",
            ]
        )

    if summary["caveats"]:
        lines.extend(["## Caveats", ""])
        for caveat in summary["caveats"]:
            lines.append(f"- {caveat}")
        lines.append("")

    lines.extend(
        [
            "## Command Table",
            "",
            "| Command | Status | Exit code | Duration (s) |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for result in summary["commands"]:
        lines.append(
            f"| `{result['name']}` | `{result['status']}` | {result['exit_code']} | {result['duration_seconds']} |"
        )
    lines.append("")

    lines.append("## Output Excerpts")
    lines.append("")
    for result in summary["commands"]:
        lines.extend(
            [
                f"### `{result['name']}`",
                "",
                f"Command: `{' '.join(result['command'])}`",
                "",
                "```text",
                result["output_excerpt"],
                "```",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def render_verify_summary(
    *,
    commands: list[VerifyCommandSpec] | None = None,
    root: Path | None = None,
    runner: CommandRunner | None = None,
) -> VerifySummary:
    resolved_root = root or repo_root()
    command_results = run_verify_commands(commands=commands, root=resolved_root, runner=runner)
    summary = build_verify_summary(command_results, root=resolved_root)
    output_root = ensure_dir(resolved_root / "docs/benchmarks/latest")
    write_json(output_root / "verify_summary.json", summary)
    (output_root / "verify_summary.md").write_text(_render_markdown(summary), encoding="utf-8")
    if summary["failed_count"]:
        raise SystemExit(1)
    return summary
