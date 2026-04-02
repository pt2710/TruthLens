from truthlens_feature_extractors import resolve_vision_encoder, vision_stack_available


def test_vision_encoder_resolution_falls_back_when_torch_or_pillow_is_missing() -> None:
    resolution = resolve_vision_encoder()

    if vision_stack_available():
        assert resolution.actual_encoder == "tiny-cnn-thumbnail"
        assert resolution.fallback_used is False
    else:
        assert resolution.requested_encoder == "tiny-cnn-thumbnail"
        assert resolution.actual_encoder == "vision-v2"
        assert resolution.fallback_used is True
        assert resolution.fallback_reason is not None
