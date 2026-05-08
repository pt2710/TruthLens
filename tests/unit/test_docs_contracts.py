from __future__ import annotations

import json

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
    assert "hosted render api" in blueprint.lower()
    assert "ad / non-video guard" in blueprint.lower()
    assert "adaptive semantic evidence router" in blueprint.lower()
    assert "bseo downstream policy layer" in blueprint.lower()
    assert "feedback / observation / score events" in blueprint.lower()
    assert "positive-bias preservation" in blueprint.lower()


def test_benchmark_docs_point_to_generated_truth_surface() -> None:
    readme = _read("README.md")
    landing_page = _read("docs/index.html")
    landing_css = _read("docs/assets/landing.css")
    benchmark_readme = _read("docs/benchmarks/README.md")
    benchmark_summary = json.loads(_read("docs/benchmarks/latest/benchmark_summary.json"))
    privacy_dataflow = _read("docs/privacy-dataflow.md")
    verify_summary = _read("docs/benchmarks/latest/verify_summary.md")
    beta_install = _read("docs/beta-install.md")
    deployment_guide = _read("docs/deployment/render-beta.md")
    hosted_verification = _read("docs/deployment/hosted-beta-verification.md")
    hardening_audit = _read("docs/decision-records/wave1-public-hardening-audit.md")
    render_blueprint = _read("render.yaml")
    pages_workflow = _read(".github/workflows/pages.yml")
    security = _read("SECURITY.md")
    conduct = _read("CODE_OF_CONDUCT.md")
    env_example = _read(".env.example")
    codeowners = _read(".github/CODEOWNERS")

    assert "## first 60 seconds" in readme.lower()
    assert "## public surfaces" in readme.lower()
    assert "## repo layout" in readme.lower()
    assert "## quick start: hosted beta extension test" in readme.lower()
    assert "## developer setup" in readme.lower()
    assert "## architecture overview" in readme.lower()
    assert "## benchmark truth" in readme.lower()
    assert "docs/index.html" in readme
    assert "git clone https://github.com/pt2710/TruthLens.git" in readme
    assert "pnpm --filter @truthlens/extension build" in readme
    assert "Select: apps/extension/dist" in readme
    assert "py -m uv sync" in readme
    assert "pyproject.toml` and `uv.lock`" in readme
    assert "There is no canonical `requirements.txt`" in readme
    assert "docs/architecture/truthlens-architecture-blueprint.png" in readme
    assert "docs/beta-install.md" in readme
    assert "docs/deployment/render-beta.md" in readme
    assert "docs/deployment/hosted-beta-verification.md" in readme
    assert "docs/privacy-dataflow.md" in readme
    assert "docs/decision-records/wave1-public-hardening-audit.md" in readme
    assert "docs/benchmarks/latest/benchmark_summary.json" in readme
    assert "docs/benchmarks/latest/verify_summary.json" in readme
    assert "benchmark_freshness_gate.py" in readme
    assert "in-page report flow" in readme.lower()
    assert "local reranking is a browser-side ordering layer only" in readme.lower()
    assert "human-assisted manual submission" in readme.lower()
    assert "what truthlens is" in landing_page.lower()
    assert "what truthlens is not" in landing_page.lower()
    assert "an honesty layer for misleading video feeds" in landing_page.lower()
    assert "free-to-use and open-source philosophy" in landing_page.lower()
    assert "truthlens uses ai against the misuse of ai" in landing_page.lower()
    assert (
        "why it exists" in landing_page.lower()
        or "the philosophy behind truthlens" in landing_page.lower()
    )
    assert "human-assisted manual submission" in landing_page.lower()
    assert "does not claim autonomous mass reporting" in landing_page.lower()
    assert "music, art, satire, gaming" in landing_page.lower()
    assert "bias structured evolutionary optimization was developed specifically for truthlens" in landing_page.lower()
    assert "positive bias preservation" in landing_page.lower()
    assert "negative bias penalty" in landing_page.lower()
    assert "manual report and verification from the feed" in landing_page.lower()
    assert "./assets/tutorial/manual-review/report-02-right-click-menu.png" in landing_page
    assert "./assets/tutorial/manual-review/verify-08-after-gemini-optimize.png" in landing_page
    assert "./privacy-dataflow.md" in landing_page
    assert "./architecture/truthlens-architecture-blueprint.png" in landing_page
    assert "TruthLens---Browser-plugin" not in landing_page
    assert "gemini assists drafting or wording" in landing_page.lower()
    assert "landing.css" in landing_page
    assert "--page-bg" in landing_css
    assert "upload-pages-artifact@v3" in pages_workflow.lower()
    assert "deploy-pages@v4" in pages_workflow.lower()
    assert "path: docs" in pages_workflow.lower()
    assert "hosted api plus an unpacked chromium extension" in beta_install.lower()
    assert "committed hosted beta origin" in beta_install.lower()
    assert "beta testers do not need local gemini, youtube, render, postgres, or api secrets" in beta_install.lower()
    assert "render web service" in deployment_guide.lower()
    assert "postgres" in deployment_guide.lower()
    assert "runtime event database" in deployment_guide.lower()
    assert "feedback events" in deployment_guide.lower()
    assert "browser observations" in deployment_guide.lower()
    assert "score audit" in deployment_guide.lower()
    assert "live service confirmed" in hosted_verification.lower()
    assert "hosted write-path proof green" in hosted_verification.lower()
    assert "extension-to-live-host proof closed" in hosted_verification.lower()
    assert "restart-survivability after hosted writes closed" in hosted_verification.lower()
    assert "release_hygiene_audit.py" in hardening_audit
    assert "returned no commits" in hardening_audit.lower()
    assert "truthlens-beta-api" in render_blueprint
    assert "truthlens-beta-db" in render_blueprint
    assert "TRUTHLENS_DATABASE_URL" in render_blueprint
    assert "/ready" in render_blueprint
    assert "apache license" in _read("LICENSE").lower()
    assert "contributor covenant" in conduct.lower()
    assert "do not open public github issues" in security.lower()
    assert "security advisories" in security.lower()
    assert "what the extension sends" in privacy_dataflow.lower()
    assert "ordinary public/test-user feedback is not automatically promoted into global benchmark truth" in privacy_dataflow.lower()
    assert "human-assisted/manual" in privacy_dataflow.lower()
    assert "C:\\Users\\" not in verify_summary
    assert "Desktop" not in verify_summary
    assert "TRUTHLENS_DATABASE_URL" in env_example
    assert "@pt2710" in codeowners
    assert "benchmark_freshness_gate.py" in benchmark_readme
    assert "freshness gate" in benchmark_readme.lower()
    assert "pnpm docs:render-benchmarks" in benchmark_readme
    assert "pnpm docs:render-verify" in benchmark_readme
    assert "visible warning-state" in benchmark_readme.lower()
    assert "docs/benchmarks/latest/artifacts/" in benchmark_readme
    for artifact_name in (
        "semantic_routing_eval",
        "semantic_routing_baseline_eval",
        "calibration_decision",
        "creative_fpr_before_eval",
        "creative_fpr_diagnostic",
    ):
        assert benchmark_summary["artifact_paths"][artifact_name].startswith(
            "docs/benchmarks/latest/artifacts/"
        )
