from truthlens_feature_extractors import resolve_text_encoder, sentence_transformers_available


def test_text_encoder_resolution_falls_back_when_sentence_transformers_is_missing() -> None:
    resolution = resolve_text_encoder()

    if sentence_transformers_available():
        assert resolution.actual_encoder == "sentence-transformer"
        assert resolution.fallback_used is False
    else:
        assert resolution.requested_encoder == "sentence-transformer"
        assert resolution.actual_encoder == "count-vectorizer-bigrams"
        assert resolution.fallback_used is True
        assert resolution.fallback_reason is not None
