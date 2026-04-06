from __future__ import annotations

from truthlens_data_pipeline.paths import repo_root


def _read(path: str) -> str:
    return (repo_root() / path).read_text(encoding="utf-8")


def test_architecture_docs_surface_selective_verification_and_bseo_boundaries() -> None:
    architecture = _read("ARCHITECTURE.md")
    reference = _read("docs/architecture/REFERENCE_ARCHITECTURE.md")
    blueprint = _read("docs/architecture/truthlens-architecture-blueprint.mmd")

    assert "selective deep verification" in architecture.lower()
    assert "supplemental browser/feedback intake" in architecture.lower()
    assert "bseo is not the core classifier" in reference.lower()
    assert "browser observation capture must work from dom-derived context" in reference.lower()
    assert "selective deep verification" in blueprint.lower()
    assert "bseo interpretation / search / artifacts" in blueprint.lower()
    assert "observation / feedback intake" in blueprint.lower()


def test_benchmark_docs_point_to_generated_truth_surface() -> None:
    readme = _read("README.md")
    benchmark_readme = _read("docs/benchmarks/README.md")

    assert "docs/benchmarks/latest/benchmark_summary.json" in readme
    assert "docs/benchmarks/latest/verify_summary.json" in readme
    assert "docs/benchmarks/latest/assets/observation_feedback_intake.svg" in readme
    assert "runtime governance" in readme.lower()
    assert "runtime-governance-latest.json" in readme
    assert "pnpm docs:render-benchmarks" in benchmark_readme
    assert "pnpm docs:render-verify" in benchmark_readme
