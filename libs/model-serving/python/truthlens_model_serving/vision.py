from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import torch
    from torch import nn
except ImportError:  # pragma: no cover - optional dependency fallback
    torch = None
    nn = None

try:
    from transformers import ViTConfig, ViTModel
except ImportError:  # pragma: no cover - optional dependency fallback
    ViTConfig = None
    ViTModel = None


def vision_available() -> bool:
    return torch is not None and nn is not None


def vision_transformer_available() -> bool:
    return vision_available() and ViTConfig is not None and ViTModel is not None


_VisionModuleBase = nn.Module if nn is not None else object


class TinyThumbnailCNN(_VisionModuleBase):  # type: ignore[misc]
    def __init__(
        self,
        image_size: int,
        *,
        conv_channels: tuple[int, int] = (8, 16),
        hidden_dim: int = 32,
    ) -> None:
        super().__init__()
        first_channel, second_channel = conv_channels
        self.features = nn.Sequential(  # type: ignore[union-attr]
            nn.Conv2d(3, first_channel, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(first_channel, second_channel, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        with torch.no_grad():
            dummy = torch.zeros((1, 3, image_size, image_size), dtype=torch.float32)
            flattened_dim = int(self.features(dummy).reshape(1, -1).shape[1])
        self.classifier = nn.Sequential(
            nn.Linear(flattened_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: Any) -> Any:
        features = self.features(x)
        return self.classifier(features.reshape(features.shape[0], -1))


if nn is not None and ViTConfig is not None and ViTModel is not None:

    class TinyThumbnailViT(nn.Module):  # type: ignore[misc]
        def __init__(
            self,
            image_size: int,
            *,
            patch_size: int,
            transformer_hidden_size: int,
            transformer_num_hidden_layers: int,
            transformer_num_attention_heads: int,
            transformer_intermediate_size: int,
            classifier_hidden_dim: int,
            pooling: str,
        ) -> None:
            super().__init__()
            self.pooling = pooling
            config = ViTConfig(
                image_size=image_size,
                patch_size=patch_size,
                num_channels=3,
                hidden_size=transformer_hidden_size,
                num_hidden_layers=transformer_num_hidden_layers,
                num_attention_heads=transformer_num_attention_heads,
                intermediate_size=transformer_intermediate_size,
                hidden_dropout_prob=0.1,
                attention_probs_dropout_prob=0.1,
                qkv_bias=True,
            )
            self.vit = ViTModel(config, add_pooling_layer=False)
            self.classifier = nn.Sequential(
                nn.Linear(transformer_hidden_size, classifier_hidden_dim),
                nn.GELU(),
                nn.Linear(classifier_hidden_dim, 1),
            )

        def forward(self, x: Any) -> Any:
            outputs = self.vit(pixel_values=x)
            hidden_state = outputs.last_hidden_state
            if self.pooling == "mean":
                pooled = hidden_state[:, 1:, :].mean(dim=1)
            else:
                pooled = hidden_state[:, 0, :]
            return self.classifier(pooled)

else:

    class TinyThumbnailViT:  # pragma: no cover - instantiated only when transformers is available
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            msg = "Transformers-backed ViT support is not available in this environment."
            raise RuntimeError(msg)


@dataclass(slots=True)
class VisionEncoderArtifacts:
    encoder_kind: str
    model_state: dict[str, Any]
    image_size: int
    conv_channels: list[int]
    hidden_dim: int
    training_sample_count: int
    patch_size: int = 0
    transformer_hidden_size: int = 0
    transformer_num_hidden_layers: int = 0
    transformer_num_attention_heads: int = 0
    transformer_intermediate_size: int = 0
    transformer_pooling: str = "cls"


def train_tiny_thumbnail_encoder(
    images: np.ndarray,
    labels: list[int],
    *,
    conv_channels: tuple[int, int] = (8, 16),
    hidden_dim: int = 32,
    epochs: int = 18,
    learning_rate: float = 0.003,
) -> VisionEncoderArtifacts:
    if not vision_available():
        raise RuntimeError("Torch is not available, so the thumbnail CNN cannot be trained.")
    if images.ndim != 4 or images.size == 0:
        raise ValueError("Thumbnail CNN received an empty image tensor.")

    device = torch.device("cpu")
    torch.manual_seed(42)
    model = TinyThumbnailCNN(
        int(images.shape[2]),
        conv_channels=conv_channels,
        hidden_dim=hidden_dim,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    image_tensor = torch.from_numpy(images.astype(np.float32)).to(device)
    label_tensor = torch.from_numpy(np.asarray(labels, dtype=np.float32).reshape(-1, 1)).to(device)
    positive_count = max(float(np.sum(labels)), 1.0)
    negative_count = max(float(len(labels) - np.sum(labels)), 1.0)
    pos_weight = torch.tensor([negative_count / positive_count], dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    for _ in range(epochs):
        model.train()
        optimizer.zero_grad()
        logits = model(image_tensor)
        loss = loss_fn(logits, label_tensor)
        loss.backward()
        optimizer.step()

    return VisionEncoderArtifacts(
        encoder_kind="tiny-cnn-thumbnail",
        model_state=model.state_dict(),
        image_size=int(images.shape[2]),
        conv_channels=[int(value) for value in conv_channels],
        hidden_dim=hidden_dim,
        training_sample_count=int(images.shape[0]),
    )


def train_vision_transformer_encoder(
    images: np.ndarray,
    labels: list[int],
    *,
    patch_size: int,
    transformer_hidden_size: int,
    transformer_num_hidden_layers: int,
    transformer_num_attention_heads: int,
    transformer_intermediate_size: int,
    hidden_dim: int = 32,
    pooling: str = "cls",
    epochs: int = 16,
    learning_rate: float = 0.002,
) -> VisionEncoderArtifacts:
    if not vision_transformer_available():
        raise RuntimeError("Torch/transformers are not available, so the thumbnail ViT cannot be trained.")
    if images.ndim != 4 or images.size == 0:
        raise ValueError("Thumbnail ViT received an empty image tensor.")

    device = torch.device("cpu")
    torch.manual_seed(42)
    model = TinyThumbnailViT(
        int(images.shape[2]),
        patch_size=patch_size,
        transformer_hidden_size=transformer_hidden_size,
        transformer_num_hidden_layers=transformer_num_hidden_layers,
        transformer_num_attention_heads=transformer_num_attention_heads,
        transformer_intermediate_size=transformer_intermediate_size,
        classifier_hidden_dim=hidden_dim,
        pooling=pooling,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    image_tensor = torch.from_numpy(images.astype(np.float32)).to(device)
    label_tensor = torch.from_numpy(np.asarray(labels, dtype=np.float32).reshape(-1, 1)).to(device)
    positive_count = max(float(np.sum(labels)), 1.0)
    negative_count = max(float(len(labels) - np.sum(labels)), 1.0)
    pos_weight = torch.tensor([negative_count / positive_count], dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    for _ in range(epochs):
        model.train()
        optimizer.zero_grad()
        logits = model(image_tensor)
        loss = loss_fn(logits, label_tensor)
        loss.backward()
        optimizer.step()

    return VisionEncoderArtifacts(
        encoder_kind="vision-transformer",
        model_state=model.state_dict(),
        image_size=int(images.shape[2]),
        conv_channels=[],
        hidden_dim=hidden_dim,
        training_sample_count=int(images.shape[0]),
        patch_size=patch_size,
        transformer_hidden_size=transformer_hidden_size,
        transformer_num_hidden_layers=transformer_num_hidden_layers,
        transformer_num_attention_heads=transformer_num_attention_heads,
        transformer_intermediate_size=transformer_intermediate_size,
        transformer_pooling=pooling,
    )


def thumbnail_scores_from_artifacts(
    images: np.ndarray,
    artifacts: VisionEncoderArtifacts,
) -> np.ndarray:
    if not vision_available():
        raise RuntimeError("Torch is not available, so the thumbnail CNN cannot score images.")
    if images.ndim != 4 or images.size == 0:
        raise ValueError("Thumbnail CNN received an empty image tensor.")

    device = torch.device("cpu")
    if artifacts.encoder_kind == "vision-transformer":
        if not vision_transformer_available():
            raise RuntimeError("Torch/transformers are not available, so the thumbnail ViT cannot score images.")
        model = TinyThumbnailViT(
            artifacts.image_size,
            patch_size=artifacts.patch_size,
            transformer_hidden_size=artifacts.transformer_hidden_size,
            transformer_num_hidden_layers=artifacts.transformer_num_hidden_layers,
            transformer_num_attention_heads=artifacts.transformer_num_attention_heads,
            transformer_intermediate_size=artifacts.transformer_intermediate_size,
            classifier_hidden_dim=artifacts.hidden_dim,
            pooling=artifacts.transformer_pooling,
        ).to(device)
    else:
        model = TinyThumbnailCNN(
            artifacts.image_size,
            conv_channels=tuple(artifacts.conv_channels or [8, 16]),
            hidden_dim=artifacts.hidden_dim,
        ).to(device)
    model.load_state_dict(artifacts.model_state)
    model.eval()
    image_tensor = torch.from_numpy(images.astype(np.float32)).to(device)
    with torch.no_grad():
        logits = model(image_tensor)
        return torch.sigmoid(logits).cpu().numpy().astype(float).reshape(-1)


def vision_artifacts_to_payload(artifacts: VisionEncoderArtifacts) -> dict[str, Any]:
    return {
        "encoder_kind": artifacts.encoder_kind,
        "model_state": artifacts.model_state,
        "image_size": artifacts.image_size,
        "conv_channels": artifacts.conv_channels,
        "hidden_dim": artifacts.hidden_dim,
        "training_sample_count": artifacts.training_sample_count,
        "patch_size": artifacts.patch_size,
        "transformer_hidden_size": artifacts.transformer_hidden_size,
        "transformer_num_hidden_layers": artifacts.transformer_num_hidden_layers,
        "transformer_num_attention_heads": artifacts.transformer_num_attention_heads,
        "transformer_intermediate_size": artifacts.transformer_intermediate_size,
        "transformer_pooling": artifacts.transformer_pooling,
    }


def vision_artifacts_from_payload(payload: dict[str, Any]) -> VisionEncoderArtifacts:
    return VisionEncoderArtifacts(
        encoder_kind=str(payload.get("encoder_kind", "tiny-cnn-thumbnail")),
        model_state=dict(payload["model_state"]),
        image_size=int(payload["image_size"]),
        conv_channels=[int(value) for value in payload.get("conv_channels", [])],
        hidden_dim=int(payload["hidden_dim"]),
        training_sample_count=int(payload["training_sample_count"]),
        patch_size=int(payload.get("patch_size", 0)),
        transformer_hidden_size=int(payload.get("transformer_hidden_size", 0)),
        transformer_num_hidden_layers=int(payload.get("transformer_num_hidden_layers", 0)),
        transformer_num_attention_heads=int(payload.get("transformer_num_attention_heads", 0)),
        transformer_intermediate_size=int(payload.get("transformer_intermediate_size", 0)),
        transformer_pooling=str(payload.get("transformer_pooling", "cls")),
    )
