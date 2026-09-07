from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app)


def test_security_headers_present_on_every_response():
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_ai_route_rate_limit_returns_429_after_limit_exceeded():
    main._rate_limit_hits.clear()
    try:
        with patch.object(main, "RATE_LIMIT_MAX_REQUESTS", 2):
            payload = {"job_description": "  "}  # invalid, but still consumes the bucket
            first = client.post("/api/extract-keywords", json=payload)
            second = client.post("/api/extract-keywords", json=payload)
            third = client.post("/api/extract-keywords", json=payload)

        assert first.status_code == 422
        assert second.status_code == 422
        assert third.status_code == 429
    finally:
        main._rate_limit_hits.clear()


def test_rate_limit_does_not_apply_to_unrelated_routes():
    main._rate_limit_hits.clear()
    try:
        with patch.object(main, "RATE_LIMIT_MAX_REQUESTS", 1):
            client.post("/api/extract-keywords", json={"job_description": "  "})
            response = client.get("/api/resumes")

        assert response.status_code != 429
    finally:
        main._rate_limit_hits.clear()
