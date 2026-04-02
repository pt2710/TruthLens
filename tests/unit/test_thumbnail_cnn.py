from __future__ import annotations

import numpy as np

from truthlens_model_serving.vision import (
    thumbnail_scores_from_artifacts,
    train_tiny_thumbnail_encoder,
    vision_available,
)


def _make_thumbnail_batch(
    *,
    sample_count: int,
    highlight: bool,
    image_size: int = 32,
) -> np.ndarray:
    batch = np.full((sample_count, 3, image_size, image_size), 0.1, dtype=np.float32)
    if highlight:
        batch[:, 0, 6:26, 6:26] = 0.95
        batch[:, 1, 12:20, 12:20] = 0.55
    else:
        batch[:, :, 10:22, 10:22] = 0.18
    return batch


def test_tiny_thumbnail_encoder_scores_highlighted_packaging_higher() -> None:
    if not vision_available():
        return

    negative_images = _make_thumbnail_batch(sample_count=20, highlight=False)
    positive_images = _make_thumbnail_batch(sample_count=20, highlight=True)
    train_images = np.concatenate([negative_images, positive_images], axis=0)
    train_labels = [0] * len(negative_images) + [1] * len(positive_images)

    artifacts = train_tiny_thumbnail_encoder(
        train_images,
        train_labels,
        hidden_dim=24,
        epochs=30,
        learning_rate=0.005,
    )

    low_score = thumbnail_scores_from_artifacts(negative_images[:1], artifacts)
    high_score = thumbnail_scores_from_artifacts(positive_images[:1], artifacts)

    assert low_score.shape == (1,)
    assert high_score.shape == (1,)
    assert float(high_score[0]) > float(low_score[0])
