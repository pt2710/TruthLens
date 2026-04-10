import httpx
import pytest

from truthlens_api.youtube_reporting import (
    _choose_best_reason,
    _list_video_report_reasons,
    probe_direct_reporting_capability,
)


class _MockResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)
        self.request = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/videoAbuseReportReasons")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "mock status error",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request, json=self._payload),
            )

    def json(self) -> dict[str, object]:
        return self._payload


def test_list_video_report_reasons_retries_without_language_on_400(
    monkeypatch,
) -> None:
    calls: list[dict[str, str]] = []

    def fake_get(url: str, **kwargs):
        params = kwargs.get("params", {})
        calls.append(params)
        if params.get("hl") == "en-US":
            return _MockResponse({"error": {"message": "unsupportedLanguageCode"}}, status_code=400)
        return _MockResponse(
            {
                "items": [
                    {
                        "id": "MISLEADING",
                        "snippet": {
                            "label": "Spam or misleading",
                            "secondaryReasons": [
                                {
                                    "id": "CLICKBAIT",
                                    "label": "Misleading metadata",
                                }
                            ],
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr("truthlens_api.youtube_reporting.httpx.get", fake_get)

    reasons = _list_video_report_reasons("test-access-token")

    assert len(calls) == 2
    assert calls[0]["hl"] == "en-US"
    assert "hl" not in calls[1]
    assert reasons[0]["id"] == "MISLEADING"


def test_choose_best_reason_prefers_spam_or_misleading_ids() -> None:
    selected_reason, selected_secondary_reason = _choose_best_reason(
        [
            {
                "id": "G",
                "snippet": {
                    "label": "Sex or nudity",
                    "secondaryReasons": [],
                },
            },
            {
                "id": "S",
                "snippet": {
                    "label": "Spam or misleading",
                    "secondaryReasons": [
                        {
                            "id": "28",
                            "label": "Misleading thumbnail",
                        },
                        {
                            "id": "31",
                            "label": "Other misleading info",
                        },
                    ],
                },
            },
        ],
        ["thumbnail", "title", "other"],
    )

    assert selected_reason["id"] == "S"
    assert selected_reason["label"] == "Spam or misleading"
    assert selected_secondary_reason is not None
    assert selected_secondary_reason["id"] == "31"


def test_choose_best_reason_refuses_unrelated_categories() -> None:
    with pytest.raises(RuntimeError, match="Spam or misleading"):
        _choose_best_reason(
            [
                {
                    "id": "G",
                    "snippet": {
                        "label": "Sex or nudity",
                        "secondaryReasons": [],
                    },
                }
            ],
            ["title"],
        )


def test_probe_direct_reporting_capability_returns_false_when_misleading_reason_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.youtube_reporting._list_video_report_reasons",
        lambda access_token: [
            {
                "id": "G",
                "snippet": {
                    "label": "Sex or nudity",
                    "secondaryReasons": [],
                },
            }
        ],
    )

    supported, detail = probe_direct_reporting_capability("test-access-token")

    assert supported is False
    assert detail is not None
    assert "spam or misleading" in detail.lower()


def test_probe_direct_reporting_capability_returns_true_when_reason_is_available(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "truthlens_api.youtube_reporting._list_video_report_reasons",
        lambda access_token: [
            {
                "id": "S",
                "snippet": {
                    "label": "Spam or misleading",
                    "secondaryReasons": [
                        {
                            "id": "31",
                            "label": "Other misleading info",
                        }
                    ],
                },
            }
        ],
    )

    supported, detail = probe_direct_reporting_capability("test-access-token")

    assert supported is True
    assert detail is not None
    assert "available" in detail.lower()
