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


CHANNEL_SEQUENCE_FEATURE_NAMES = [
    "risk_seed",
    "transcript_mismatch_score",
    "sensational_count",
    "repeat_template_rate",
    "recent_upload_velocity",
    "engagement_anomaly",
    "like_ratio",
]


def temporal_available() -> bool:
    return torch is not None and nn is not None


_TemporalModuleBase = nn.Module if nn is not None else object


class TemporalHistoryLSTM(_TemporalModuleBase):  # type: ignore[misc]
    def __init__(self, input_dim: int, hidden_dim: int = 16, num_layers: int = 1) -> None:
        super().__init__()
        self.lstm = nn.LSTM(  # type: ignore[union-attr]
            input_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
        )
        self.classifier = nn.Linear(hidden_dim, 1)

    def forward(self, x: Any) -> Any:
        _, (hidden, _) = self.lstm(x)
        return self.classifier(hidden[-1])


@dataclass(slots=True)
class HistorySequenceArtifacts:
    model_state: dict[str, Any]
    sequence_length: int
    input_dim: int
    hidden_dim: int
    num_layers: int
    feature_names: list[str]
    training_sample_count: int


def train_temporal_history_encoder(
    sequences: np.ndarray,
    labels: list[int],
    *,
    hidden_dim: int = 16,
    num_layers: int = 1,
    epochs: int = 60,
    learning_rate: float = 0.01,
) -> HistorySequenceArtifacts:
    if not temporal_available():
        raise RuntimeError("Torch is not available, so the temporal history encoder cannot be trained.")
    if sequences.size == 0:
        raise ValueError("Temporal history encoder received an empty sequence tensor.")

    device = torch.device("cpu")
    torch.manual_seed(42)
    model = TemporalHistoryLSTM(
        sequences.shape[2],
        hidden_dim=hidden_dim,
        num_layers=num_layers,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    tensor = torch.from_numpy(sequences.astype(np.float32)).to(device)
    target_tensor = torch.from_numpy(np.asarray(labels, dtype=np.float32).reshape(-1, 1)).to(device)
    positive_count = max(float(np.sum(labels)), 1.0)
    negative_count = max(float(len(labels) - np.sum(labels)), 1.0)
    pos_weight = torch.tensor([negative_count / positive_count], dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    for _ in range(epochs):
        model.train()
        optimizer.zero_grad()
        logits = model(tensor)
        loss = loss_fn(logits, target_tensor)
        loss.backward()
        optimizer.step()

    return HistorySequenceArtifacts(
        model_state=model.state_dict(),
        sequence_length=int(sequences.shape[1]),
        input_dim=int(sequences.shape[2]),
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        feature_names=CHANNEL_SEQUENCE_FEATURE_NAMES.copy(),
        training_sample_count=int(sequences.shape[0]),
    )


def temporal_history_scores_from_artifacts(
    sequences: np.ndarray,
    artifacts: HistorySequenceArtifacts,
) -> np.ndarray:
    if not temporal_available():
        raise RuntimeError("Torch is not available, so the temporal history encoder cannot score sequences.")

    device = torch.device("cpu")
    model = TemporalHistoryLSTM(
        artifacts.input_dim,
        hidden_dim=artifacts.hidden_dim,
        num_layers=artifacts.num_layers,
    ).to(device)
    model.load_state_dict(artifacts.model_state)
    model.eval()
    tensor = torch.from_numpy(sequences.astype(np.float32)).to(device)
    with torch.no_grad():
        logits = model(tensor)
        return torch.sigmoid(logits).cpu().numpy().astype(float).reshape(-1)


def temporal_artifacts_to_payload(artifacts: HistorySequenceArtifacts) -> dict[str, Any]:
    return {
        "model_state": artifacts.model_state,
        "sequence_length": artifacts.sequence_length,
        "input_dim": artifacts.input_dim,
        "hidden_dim": artifacts.hidden_dim,
        "num_layers": artifacts.num_layers,
        "feature_names": artifacts.feature_names,
        "training_sample_count": artifacts.training_sample_count,
    }


def temporal_artifacts_from_payload(payload: dict[str, Any]) -> HistorySequenceArtifacts:
    return HistorySequenceArtifacts(
        model_state=dict(payload["model_state"]),
        sequence_length=int(payload["sequence_length"]),
        input_dim=int(payload["input_dim"]),
        hidden_dim=int(payload["hidden_dim"]),
        num_layers=int(payload["num_layers"]),
        feature_names=[str(value) for value in payload["feature_names"]],
        training_sample_count=int(payload["training_sample_count"]),
    )
