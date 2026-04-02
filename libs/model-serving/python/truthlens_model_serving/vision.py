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


def vision_available() -> bool:
    return torch is not None and nn is not None


class TinyThumbnailCNN(nn.Module):  # type: ignore[misc]
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


@dataclass(slots=True)
class VisionEncoderArtifacts:
    model_state: dict[str, Any]
    image_size: int
    conv_channels: list[int]
    hidden_dim: int
    training_sample_count: int


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
        model_state=model.state_dict(),
        image_size=int(images.shape[2]),
        conv_channels=[int(value) for value in conv_channels],
        hidden_dim=hidden_dim,
        training_sample_count=int(images.shape[0]),
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
    model = TinyThumbnailCNN(
        artifacts.image_size,
        conv_channels=tuple(artifacts.conv_channels),
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
        "model_state": artifacts.model_state,
        "image_size": artifacts.image_size,
        "conv_channels": artifacts.conv_channels,
        "hidden_dim": artifacts.hidden_dim,
        "training_sample_count": artifacts.training_sample_count,
    }


def vision_artifacts_from_payload(payload: dict[str, Any]) -> VisionEncoderArtifacts:
    return VisionEncoderArtifacts(
        model_state=dict(payload["model_state"]),
        image_size=int(payload["image_size"]),
        conv_channels=[int(value) for value in payload["conv_channels"]],
        hidden_dim=int(payload["hidden_dim"]),
        training_sample_count=int(payload["training_sample_count"]),
    )
