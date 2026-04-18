from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

try:
    from PIL import Image as _ImageModule
    from PIL import ImageStat as _ImageStatModule
except ImportError:  # pragma: no cover - optional dependency fallback
    Image: Any | None = None
    ImageStat: Any | None = None
else:
    Image = _ImageModule
    ImageStat = _ImageStatModule


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _fallback_features(
    path: Path,
    fallback_signal: dict[str, float] | None = None,
) -> dict[str, float]:
    signal = fallback_signal or {}
    byte_size = path.stat().st_size if path.exists() else 0
    return {
        "thumbnail_brightness": _clamp(float(signal.get("brightness", 0.45))),
        "thumbnail_saturation": _clamp(float(signal.get("saturation", 0.35))),
        "thumbnail_contrast": _clamp(float(signal.get("contrast", 0.4))),
        "thumbnail_text_density": _clamp(float(signal.get("text_density", 0.25))),
        "thumbnail_face_emphasis": _clamp(float(signal.get("face_emphasis", 0.18))),
        "thumbnail_shock_indicator": _clamp(float(signal.get("shock_indicator", 0.2))),
        "thumbnail_entropy": _clamp(float(signal.get("entropy", 0.4))),
        "thumbnail_aspect_ratio": _clamp(float(signal.get("aspect_ratio", 16 / 9)) / 2.5),
        "thumbnail_byte_size": float(byte_size),
    }


def extract_thumbnail_features(
    thumbnail_path: str | Path,
    *,
    fallback_signal: dict[str, float] | None = None,
) -> dict[str, float]:
    path = Path(thumbnail_path)
    if not path.exists() or Image is None or ImageStat is None:
        return _fallback_features(path, fallback_signal)

    try:
        with Image.open(path) as image:
            rgb_image = image.convert("RGB")
            grayscale = rgb_image.convert("L")
            stat = ImageStat.Stat(rgb_image)
            grayscale_stat = ImageStat.Stat(grayscale)
            width, height = rgb_image.size
            brightness = grayscale_stat.mean[0] / 255.0
            contrast = grayscale_stat.stddev[0] / 128.0
            channel_mean = stat.mean
            saturation = (max(channel_mean) - min(channel_mean)) / 255.0
            entropy = grayscale.entropy() / 8.0
            aspect_ratio = width / max(height, 1)
            byte_size = float(path.stat().st_size)
            return {
                "thumbnail_brightness": _clamp(brightness),
                "thumbnail_saturation": _clamp(saturation),
                "thumbnail_contrast": _clamp(contrast),
                "thumbnail_text_density": _clamp(float(fallback_signal.get("text_density", 0.18)) if fallback_signal else 0.18),
                "thumbnail_face_emphasis": _clamp(float(fallback_signal.get("face_emphasis", 0.12)) if fallback_signal else 0.12),
                "thumbnail_shock_indicator": _clamp(float(fallback_signal.get("shock_indicator", 0.16)) if fallback_signal else 0.16),
                "thumbnail_entropy": _clamp(entropy),
                "thumbnail_aspect_ratio": _clamp(aspect_ratio / 2.5),
                "thumbnail_byte_size": byte_size,
            }
    except (OSError, ValueError):
        return _fallback_features(path, fallback_signal)


def make_test_png_bytes(
    color: tuple[int, int, int] = (240, 80, 60),
    *,
    width: int = 16,
    height: int = 9,
) -> bytes:
    if Image is None:
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )
    image = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
