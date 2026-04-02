from __future__ import annotations

import numpy as np

from truthlens_model_serving.vision import (
    thumbnail_scores_from_artifacts,
    train_vision_transformer_encoder,
    vision_transformer_available,
)


def _make_thumbnail_batch(
    *,
    sample_count: int,
    highlight: bool,
    image_size: int = 32,
) -> np.ndarray:
    batch = np.full((sample_count, 3, image_size, image_size), 0.08, dtype=np.float32)
    if highlight:
        batch[:, 0, 4:28, 4:28] = 0.95
        batch[:, 1, 8:24, 8:24] = 0.45
        batch[:, 2, 10:22, 10:22] = 0.22
    else:
        batch[:, :, 10:22, 10:22] = 0.16
    return batch


def test_thumbnail_vit_scores_highlighted_packaging_higher() -> None:
    if not vision_transformer_available():
        return

    negative_images = _make_thumbnail_batch(sample_count=12, highlight=False)
    positive_images = _make_thumbnail_batch(sample_count=12, highlight=True)
    train_images = np.concatenate([negative_images, positive_images], axis=0)
    train_labels = [0] * len(negative_images) + [1] * len(positive_images)

    artifacts = train_vision_transformer_encoder(
        train_images,
        train_labels,
        patch_size=8,
        transformer_hidden_size=48,
        transformer_num_hidden_layers=2,
        transformer_num_attention_heads=4,
        transformer_intermediate_size=96,
        hidden_dim=24,
        pooling="cls",
        epochs=12,
        learning_rate=0.003,
    )

    low_score = thumbnail_scores_from_artifacts(negative_images[:1], artifacts)
    high_score = thumbnail_scores_from_artifacts(positive_images[:1], artifacts)

    assert artifacts.encoder_kind == "vision-transformer"
    assert low_score.shape == (1,)
    assert high_score.shape == (1,)
    assert float(high_score[0]) > float(low_score[0])
