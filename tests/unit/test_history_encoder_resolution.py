from truthlens_feature_extractors import resolve_history_encoder, temporal_torch_available


def test_history_encoder_resolution_falls_back_when_torch_is_missing() -> None:
    resolution = resolve_history_encoder()

    if temporal_torch_available():
        assert resolution.actual_encoder == "lstm-sequence"
        assert resolution.fallback_used is False
    else:
        assert resolution.requested_encoder == "lstm-sequence"
        assert resolution.actual_encoder == "sequence-summary-v1"
        assert resolution.fallback_used is True
        assert resolution.fallback_reason is not None
