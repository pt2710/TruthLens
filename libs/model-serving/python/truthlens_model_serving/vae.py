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


PACKAGING_VAE_FEATURE_NAMES = [
    "thumbnail_brightness",
    "thumbnail_saturation",
    "thumbnail_contrast",
    "thumbnail_text_density",
    "thumbnail_entropy",
    "thumbnail_aspect_ratio",
    "thumbnail_face_emphasis",
    "thumbnail_shock_indicator",
    "transcript_mismatch_score",
    "thumbnail_byte_size",
    "prior_flags",
    "estimated_risk_seed",
    "title_length",
    "uppercase_ratio",
    "token_hits",
    "channel_risk_mean",
    "duration_seconds",
    "view_count_log",
    "like_ratio",
    "transcript_mismatch_score_metadata",
]


def vae_available() -> bool:
    return torch is not None and nn is not None


class PackagingVAE(nn.Module):  # type: ignore[misc]
    def __init__(self, input_dim: int, hidden_dim: int = 24, latent_dim: int = 4) -> None:
        super().__init__()
        self.encoder = nn.Sequential(  # type: ignore[union-attr]
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
        )
        self.mu = nn.Linear(hidden_dim // 2, latent_dim)
        self.logvar = nn.Linear(hidden_dim // 2, latent_dim)
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim),
        )

    def encode(self, x: Any) -> tuple[Any, Any]:
        hidden = self.encoder(x)
        return self.mu(hidden), self.logvar(hidden)

    def reparameterize(self, mu: Any, logvar: Any) -> Any:
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def forward(self, x: Any) -> tuple[Any, Any, Any]:
        mu, logvar = self.encode(x)
        latent = self.reparameterize(mu, logvar)
        reconstruction = self.decoder(latent)
        return reconstruction, mu, logvar


@dataclass(slots=True)
class PackagingVAEArtifacts:
    model_state: dict[str, Any]
    scaler_mean: list[float]
    scaler_std: list[float]
    error_mean: float
    error_std: float
    hidden_dim: int
    latent_dim: int
    feature_names: list[str]
    training_sample_count: int


def _normalize_matrix(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std = np.where(std < 1e-6, 1.0, std)
    normalized = (matrix - mean) / std
    return normalized.astype(np.float32), mean.astype(float), std.astype(float)


def _sigmoid(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-value)))


def train_packaging_vae(
    matrix: np.ndarray,
    *,
    hidden_dim: int = 24,
    latent_dim: int = 4,
    epochs: int = 80,
    learning_rate: float = 0.01,
) -> PackagingVAEArtifacts:
    if not vae_available():
        raise RuntimeError("Torch is not available, so the packaging VAE cannot be trained.")
    if matrix.size == 0:
        raise ValueError("Packaging VAE received an empty feature matrix.")

    normalized, mean, std = _normalize_matrix(matrix)
    device = torch.device("cpu")
    torch.manual_seed(42)
    model = PackagingVAE(normalized.shape[1], hidden_dim=hidden_dim, latent_dim=latent_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    tensor = torch.from_numpy(normalized).to(device)

    for _ in range(epochs):
        model.train()
        optimizer.zero_grad()
        reconstruction, mu, logvar = model(tensor)
        reconstruction_loss = torch.mean((reconstruction - tensor) ** 2)
        kl_loss = torch.mean(-0.5 * (1 + logvar - mu.pow(2) - logvar.exp()))
        loss = reconstruction_loss + 0.02 * kl_loss
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        reconstruction, _, _ = model(tensor)
        errors = torch.mean((reconstruction - tensor) ** 2, dim=1).cpu().numpy().astype(float)

    return PackagingVAEArtifacts(
        model_state=model.state_dict(),
        scaler_mean=mean.tolist(),
        scaler_std=std.tolist(),
        error_mean=float(errors.mean()),
        error_std=float(max(errors.std(), 1e-6)),
        hidden_dim=hidden_dim,
        latent_dim=latent_dim,
        feature_names=PACKAGING_VAE_FEATURE_NAMES.copy(),
        training_sample_count=int(matrix.shape[0]),
    )


def packaging_anomaly_from_artifacts(
    matrix: np.ndarray,
    artifacts: PackagingVAEArtifacts,
) -> tuple[np.ndarray, np.ndarray]:
    if not vae_available():
        raise RuntimeError("Torch is not available, so the packaging VAE cannot score anomalies.")

    mean = np.asarray(artifacts.scaler_mean, dtype=np.float32)
    std = np.asarray(artifacts.scaler_std, dtype=np.float32)
    normalized = ((matrix.astype(np.float32) - mean) / np.where(std < 1e-6, 1.0, std)).astype(np.float32)

    device = torch.device("cpu")
    model = PackagingVAE(
        normalized.shape[1],
        hidden_dim=artifacts.hidden_dim,
        latent_dim=artifacts.latent_dim,
    ).to(device)
    model.load_state_dict(artifacts.model_state)
    model.eval()

    tensor = torch.from_numpy(normalized).to(device)
    with torch.no_grad():
        reconstruction, _, _ = model(tensor)
        reconstruction_np = reconstruction.cpu().numpy().astype(float)

    feature_errors = np.square(reconstruction_np - normalized.astype(float))
    total_errors = feature_errors.mean(axis=1)
    z_scores = (total_errors - artifacts.error_mean) / max(artifacts.error_std, 1e-6)
    anomaly_scores = np.asarray([_sigmoid(float(score)) for score in z_scores], dtype=float)
    return anomaly_scores, feature_errors


def artifacts_to_payload(artifacts: PackagingVAEArtifacts) -> dict[str, Any]:
    return {
        "model_state": artifacts.model_state,
        "scaler_mean": artifacts.scaler_mean,
        "scaler_std": artifacts.scaler_std,
        "error_mean": artifacts.error_mean,
        "error_std": artifacts.error_std,
        "hidden_dim": artifacts.hidden_dim,
        "latent_dim": artifacts.latent_dim,
        "feature_names": artifacts.feature_names,
        "training_sample_count": artifacts.training_sample_count,
    }


def artifacts_from_payload(payload: dict[str, Any]) -> PackagingVAEArtifacts:
    return PackagingVAEArtifacts(
        model_state=dict(payload["model_state"]),
        scaler_mean=[float(value) for value in payload["scaler_mean"]],
        scaler_std=[float(value) for value in payload["scaler_std"]],
        error_mean=float(payload["error_mean"]),
        error_std=float(payload["error_std"]),
        hidden_dim=int(payload["hidden_dim"]),
        latent_dim=int(payload["latent_dim"]),
        feature_names=[str(value) for value in payload["feature_names"]],
        training_sample_count=int(payload["training_sample_count"]),
    )
