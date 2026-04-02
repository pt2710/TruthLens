from __future__ import annotations

import numpy as np

from truthlens_model_serving.vae import (
    PACKAGING_VAE_FEATURE_NAMES,
    packaging_anomaly_from_artifacts,
    train_packaging_vae,
    vae_available,
)


def test_packaging_vae_scores_outlier_higher_than_baseline() -> None:
    if not vae_available():
        return

    rng = np.random.default_rng(42)
    train_matrix = rng.normal(loc=0.0, scale=0.55, size=(96, len(PACKAGING_VAE_FEATURE_NAMES))).astype(float)
    artifacts = train_packaging_vae(train_matrix, epochs=40, learning_rate=0.008)

    baseline_sample = train_matrix[:1]
    outlier_sample = np.full((1, len(PACKAGING_VAE_FEATURE_NAMES)), 4.5, dtype=float)

    baseline_score, baseline_feature_errors = packaging_anomaly_from_artifacts(baseline_sample, artifacts)
    outlier_score, outlier_feature_errors = packaging_anomaly_from_artifacts(outlier_sample, artifacts)

    assert baseline_score.shape == (1,)
    assert baseline_feature_errors.shape == baseline_sample.shape
    assert outlier_feature_errors.shape == outlier_sample.shape
    assert float(outlier_score[0]) > float(baseline_score[0])
    assert float(outlier_score[0]) > 0.6
