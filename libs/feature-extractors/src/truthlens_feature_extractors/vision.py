from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    from PIL import Image  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency fallback
    Image = None

DEFAULT_VISION_ENCODER_CONFIG = {
    "requested_encoder": "tiny-cnn-thumbnail",
    "fallback_encoder": "vision-v2",
    "image_size": 32,
    "conv_channels": [8, 16],
    "hidden_dim": 32,
    "epochs": 18,
    "learning_rate": 0.003,
    "patch_size": 8,
    "transformer_hidden_size": 64,
    "transformer_num_hidden_layers": 2,
    "transformer_num_attention_heads": 4,
    "transformer_intermediate_size": 128,
    "transformer_pooling": "cls",
}


def _repo_root() -> Path:
    override = os.getenv("TRUTHLENS_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[4]


def _source_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _vision_encoder_config_path() -> Path:
    override_path = _repo_root() / "configs" / "models" / "vision_encoder.json"
    if override_path.exists():
        return override_path
    return _source_repo_root() / "configs" / "models" / "vision_encoder.json"


@dataclass(slots=True)
class VisionEncoderResolution:
    requested_encoder: str
    actual_encoder: str
    fallback_used: bool
    image_size: int
    conv_channels: list[int]
    hidden_dim: int
    epochs: int
    learning_rate: float
    patch_size: int
    transformer_hidden_size: int
    transformer_num_hidden_layers: int
    transformer_num_attention_heads: int
    transformer_intermediate_size: int
    transformer_pooling: str
    fallback_reason: str | None = None


def load_vision_encoder_config() -> dict[str, Any]:
    path = _vision_encoder_config_path()
    if not path.exists():
        return DEFAULT_VISION_ENCODER_CONFIG.copy()
    payload = json.loads(path.read_text(encoding="utf-8"))
    merged = DEFAULT_VISION_ENCODER_CONFIG.copy()
    if isinstance(payload, dict):
        merged.update({key: value for key, value in payload.items() if value is not None})
    return merged


def vision_stack_available() -> bool:
    return importlib.util.find_spec("torch") is not None and Image is not None


def vision_transformer_available() -> bool:
    return vision_stack_available() and importlib.util.find_spec("transformers") is not None


def resolve_vision_encoder() -> VisionEncoderResolution:
    config = load_vision_encoder_config()
    requested_encoder = str(config.get("requested_encoder", "vision-v2")).strip()
    fallback_encoder = str(config.get("fallback_encoder", "vision-v2")).strip()
    image_size = int(config.get("image_size", 32))
    conv_channels = [int(value) for value in config.get("conv_channels", [8, 16])]
    hidden_dim = int(config.get("hidden_dim", 32))
    epochs = int(config.get("epochs", 18))
    learning_rate = float(config.get("learning_rate", 0.003))
    patch_size = int(config.get("patch_size", 8))
    transformer_hidden_size = int(config.get("transformer_hidden_size", 64))
    transformer_num_hidden_layers = int(config.get("transformer_num_hidden_layers", 2))
    transformer_num_attention_heads = int(config.get("transformer_num_attention_heads", 4))
    transformer_intermediate_size = int(config.get("transformer_intermediate_size", 128))
    transformer_pooling = str(config.get("transformer_pooling", "cls")).strip() or "cls"

    resolution = VisionEncoderResolution(
        requested_encoder=requested_encoder,
        actual_encoder=requested_encoder,
        fallback_used=False,
        image_size=image_size,
        conv_channels=conv_channels,
        hidden_dim=hidden_dim,
        epochs=epochs,
        learning_rate=learning_rate,
        patch_size=patch_size,
        transformer_hidden_size=transformer_hidden_size,
        transformer_num_hidden_layers=transformer_num_hidden_layers,
        transformer_num_attention_heads=transformer_num_attention_heads,
        transformer_intermediate_size=transformer_intermediate_size,
        transformer_pooling=transformer_pooling,
    )

    if requested_encoder == "vision-transformer":
        if vision_transformer_available():
            return resolution
        if vision_stack_available():
            return fallback_vision_encoder_resolution(
                resolution,
                reason="transformers is not installed in the active environment",
                fallback_encoder="tiny-cnn-thumbnail",
            )
        return fallback_vision_encoder_resolution(
            resolution,
            reason="torch, transformers, or Pillow is not installed in the active environment",
            fallback_encoder=fallback_encoder,
        )

    if requested_encoder == "tiny-cnn-thumbnail":
        if vision_stack_available():
            return resolution
        return fallback_vision_encoder_resolution(
            resolution,
            reason="torch or Pillow is not installed in the active environment",
            fallback_encoder=fallback_encoder,
        )

    return resolution


def fallback_vision_encoder_resolution(
    resolution: VisionEncoderResolution,
    *,
    reason: str,
    fallback_encoder: str = "vision-v2",
) -> VisionEncoderResolution:
    return VisionEncoderResolution(
        requested_encoder=resolution.requested_encoder,
        actual_encoder=fallback_encoder,
        fallback_used=True,
        image_size=resolution.image_size,
        conv_channels=resolution.conv_channels,
        hidden_dim=resolution.hidden_dim,
        epochs=resolution.epochs,
        learning_rate=resolution.learning_rate,
        patch_size=resolution.patch_size,
        transformer_hidden_size=resolution.transformer_hidden_size,
        transformer_num_hidden_layers=resolution.transformer_num_hidden_layers,
        transformer_num_attention_heads=resolution.transformer_num_attention_heads,
        transformer_intermediate_size=resolution.transformer_intermediate_size,
        transformer_pooling=resolution.transformer_pooling,
        fallback_reason=reason,
    )


def vision_encoder_resolution_payload(resolution: VisionEncoderResolution) -> dict[str, Any]:
    return asdict(resolution)


def thumbnail_array_from_path(
    thumbnail_path: str | Path,
    *,
    image_size: int,
) -> np.ndarray | None:
    if Image is None:
        return None
    path = Path(thumbnail_path)
    if not path.exists() or path.suffix.lower() == ".json":
        return None
    try:
        with Image.open(path) as image:
            rgb_image = image.convert("RGB").resize((image_size, image_size))
            array = np.asarray(rgb_image, dtype=np.float32) / 255.0
    except (OSError, ValueError):
        return None
    return np.transpose(array, (2, 0, 1)).astype(np.float32)


def thumbnail_array_batch(
    thumbnail_paths: list[str | Path],
    *,
    image_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    arrays: list[np.ndarray] = []
    mask: list[bool] = []
    empty = np.zeros((3, image_size, image_size), dtype=np.float32)
    for thumbnail_path in thumbnail_paths:
        image_array = thumbnail_array_from_path(thumbnail_path, image_size=image_size)
        if image_array is None:
            arrays.append(empty.copy())
            mask.append(False)
            continue
        arrays.append(image_array)
        mask.append(True)
    return np.asarray(arrays, dtype=np.float32), np.asarray(mask, dtype=bool)
