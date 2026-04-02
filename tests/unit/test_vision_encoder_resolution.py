from truthlens_feature_extractors import (
    resolve_vision_encoder,
    vision_stack_available,
    vision_transformer_available,
)


def test_vision_encoder_resolution_prefers_vit_then_cnn_then_engineered_features() -> None:
    resolution = resolve_vision_encoder()

    if vision_transformer_available():
        assert resolution.requested_encoder == "vision-transformer"
        assert resolution.actual_encoder == "vision-transformer"
        assert resolution.fallback_used is False
    elif vision_stack_available():
        assert resolution.requested_encoder == "vision-transformer"
        assert resolution.actual_encoder == "tiny-cnn-thumbnail"
        assert resolution.fallback_used is True
        assert resolution.fallback_reason is not None
    else:
        assert resolution.requested_encoder == "vision-transformer"
        assert resolution.actual_encoder == "vision-v2"
        assert resolution.fallback_used is True
        assert resolution.fallback_reason is not None
