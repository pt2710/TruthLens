from __future__ import annotations

import numpy as np

from truthlens_model_serving.temporal import (
    CHANNEL_SEQUENCE_FEATURE_NAMES,
    temporal_available,
    temporal_history_scores_from_artifacts,
    train_temporal_history_encoder,
)


def test_temporal_history_encoder_scores_positive_sequence_higher() -> None:
    if not temporal_available():
        return

    rng = np.random.default_rng(42)
    sequence_length = 4
    feature_dim = len(CHANNEL_SEQUENCE_FEATURE_NAMES)
    negative_sequences = rng.normal(
        loc=0.15,
        scale=0.08,
        size=(24, sequence_length, feature_dim),
    ).astype(float)
    positive_sequences = rng.normal(
        loc=0.85,
        scale=0.12,
        size=(24, sequence_length, feature_dim),
    ).astype(float)
    train_sequences = np.concatenate([negative_sequences, positive_sequences], axis=0)
    train_labels = [0] * len(negative_sequences) + [1] * len(positive_sequences)

    artifacts = train_temporal_history_encoder(
        train_sequences,
        train_labels,
        hidden_dim=12,
        epochs=40,
        learning_rate=0.01,
    )

    low_score = temporal_history_scores_from_artifacts(negative_sequences[:1], artifacts)
    high_score = temporal_history_scores_from_artifacts(positive_sequences[:1], artifacts)

    assert low_score.shape == (1,)
    assert high_score.shape == (1,)
    assert float(high_score[0]) > float(low_score[0])
