from __future__ import annotations

from truthlens_data_pipeline.paths import repo_root


def _read(path: str) -> str:
    return (repo_root() / path).read_text(encoding="utf-8")


def test_architecture_docs_surface_selective_verification_and_bseo_boundaries() -> None:
    architecture = _read("ARCHITECTURE.md")
    reference = _read("docs/architecture/REFERENCE_ARCHITECTURE.md")
    architecture_assets = _read("docs/architecture/README.md")
    blueprint = _read("docs/architecture/truthlens-architecture-blueprint.mmd")

    assert "selective deep verification" in architecture.lower()
    assert "supplemental browser/feedback intake" in architecture.lower()
    assert "manual review tags must remain separate" in architecture.lower()
    assert "bseo is not the core classifier" in reference.lower()
    assert "positive-bias preservation mechanism" in reference.lower()
    assert "negative-bias penalty mechanism" in reference.lower()
    assert "browser observation capture must work from dom-derived context" in reference.lower()
    assert "default toward `clickbait`" in reference.lower()
    assert "extension ui keeps thumbnails visible" in reference.lower()
    assert "runtime decision flow source" in architecture_assets.lower()
    assert "governance feedback loop source" in architecture_assets.lower()
    assert "three png renders" in architecture_assets.lower()
    assert "bseo wording should reflect truthlens' positive-bias preservation" in architecture_assets.lower()
    assert "runtime core" in blueprint.lower()
    assert "bseo interpretation / search / artifacts" in blueprint.lower()
    assert "observation / feedback intake" in blueprint.lower()
    assert "positive-bias preservation" in blueprint.lower()


def test_benchmark_docs_point_to_generated_truth_surface() -> None:
    readme = _read("README.md")
    benchmark_readme = _read("docs/benchmarks/README.md")
    beta_install = _read("docs/beta-install.md")
    deployment_guide = _read("docs/deployment/render-beta.md")
    hosted_verification = _read("docs/deployment/hosted-beta-verification.md")
    hardening_audit = _read("docs/decision-records/wave1-public-hardening-audit.md")
    render_blueprint = _read("render.yaml")
    security = _read("SECURITY.md")
    conduct = _read("CODE_OF_CONDUCT.md")
    env_example = _read(".env.example")
    codeowners = _read(".github/CODEOWNERS")

    assert "docs/architecture/truthlens-architecture-blueprint.png" in readme
    assert "docs/architecture/truthlens-runtime-decision-flow.png" in readme
    assert "docs/architecture/truthlens-governance-feedback-loop.png" in readme
    assert "## public beta positioning" in readme.lower()
    assert "## first 60 seconds" in readme.lower()
    assert "## extension beta quick start" in readme.lower()
    assert "docs/beta-install.md" in readme
    assert "docs/deployment/render-beta.md" in readme
    assert "docs/deployment/hosted-beta-verification.md" in readme
    assert "docs/decision-records/wave1-public-hardening-audit.md" in readme
    assert "docs/benchmarks/latest/benchmark_summary.json" in readme
    assert "docs/benchmarks/latest/verify_summary.json" in readme
    assert "docs/benchmarks/latest/assets/observation_feedback_intake.svg" in readme
    assert "## bseo" in readme.lower()
    assert "bias structured evolutionary optimization" in readme.lower()
    assert "positive bias preservation" in readme.lower()
    assert "negative bias penalty" in readme.lower()
    assert "thumbnails visible" in readme.lower()
    assert "collection preview" in readme.lower()
    assert "in-page report flow" in readme.lower()
    assert "runtime governance" in readme.lower()
    assert "runtime-governance-latest.json" in readme
    assert "hosted api plus unpacked chromium extension" in beta_install.lower()
    assert "there is no committed live default hostname" in beta_install.lower()
    assert "render web service" in deployment_guide.lower()
    assert "postgres" in deployment_guide.lower()
    assert "not a live hosted beta proof" in hosted_verification.lower()
    assert "x-render-routing: no-server" in hosted_verification.lower()
    assert "release_hygiene_audit.py" in hardening_audit
    assert "returned no commits" in hardening_audit.lower()
    assert "truthlens-beta-api" in render_blueprint
    assert "truthlens-beta-db" in render_blueprint
    assert "TRUTHLENS_DATABASE_URL" in render_blueprint
    assert "/ready" in render_blueprint
    assert "apache license" in _read("LICENSE").lower()
    assert "contributor covenant" in conduct.lower()
    assert "security@truthlens.dev" in security.lower()
    assert "TRUTHLENS_DATABASE_URL" in env_example
    assert "@pt2710" in codeowners
    assert "pnpm docs:render-benchmarks" in benchmark_readme
    assert "pnpm docs:render-verify" in benchmark_readme
    assert "visible warning-state" in benchmark_readme.lower()
