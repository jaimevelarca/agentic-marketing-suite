"""Gemini provider (google-genai on Vertex) — offline tests with a fake client."""
from __future__ import annotations

import sys
import pathlib
from dataclasses import replace

SUITE = pathlib.Path(__file__).resolve().parents[2] / "suite"
sys.path.insert(0, str(SUITE))

import pytest  # noqa: E402
from infra import clients  # noqa: E402
from infra.config import settings  # noqa: E402


class FakeUsage:
    prompt_token_count = 100
    candidates_token_count = 50
    total_token_count = 150


class FakeResponse:
    text = "## OUTPUT 1\n```json\n{}\n```"
    usage_metadata = FakeUsage()


class FakeModels:
    def __init__(self, fail_times=0, error=None):
        self.calls = []
        self.fail_times = fail_times
        self.error = error

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.error
        return FakeResponse()


class FakeGenaiClient:
    def __init__(self, models):
        self.models = models


class TransientError(Exception):
    code = 429


class FatalError(Exception):
    code = 400


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(clients, "settings", replace(settings, llm_provider="gemini"))

    def make(fail_times=0, error=None):
        fake = FakeModels(fail_times=fail_times, error=error)
        monkeypatch.setattr(clients, "_genai_client", lambda: FakeGenaiClient(fake))
        monkeypatch.setattr(clients, "_RETRY_BASE_SLEEP", 0)  # no real sleeping in tests
        return fake
    return make


def test_tier_mapping():
    assert clients._gemini_model_for(settings.model_primary) == settings.gemini_model_primary
    assert clients._gemini_model_for(settings.model_routing) == settings.gemini_model_routing
    assert clients._gemini_model_for(settings.model_deep) == settings.gemini_model_deep
    assert clients._gemini_model_for("some-unknown-id") == settings.gemini_model_primary


def test_gemini_call_passes_system_and_limits(gemini):
    fake = gemini()
    out = clients.llm_complete(model=settings.model_routing, system="SYS", user_turn="hello",
                               max_tokens=1234, agent_id="1.1")
    assert out.startswith("## OUTPUT 1")
    call = fake.calls[0]
    assert call["model"] == settings.gemini_model_routing
    assert call["contents"] == "hello"
    assert call["config"]["system_instruction"] == "SYS"
    assert call["config"]["max_output_tokens"] == 1234


def test_transient_error_is_retried(gemini):
    fake = gemini(fail_times=2, error=TransientError("quota"))
    out = clients.llm_complete(model=settings.model_primary, system="s", user_turn="u",
                               max_tokens=10, agent_id="1.1")
    assert out.startswith("## OUTPUT 1")
    assert len(fake.calls) == 3  # two failures + success


def test_fatal_error_raises_immediately(gemini):
    fake = gemini(fail_times=5, error=FatalError("bad request"))
    with pytest.raises(FatalError):
        clients.llm_complete(model=settings.model_primary, system="s", user_turn="u",
                             max_tokens=10, agent_id="1.1")
    assert len(fake.calls) == 1


def test_retries_exhausted_reraises(gemini):
    fake = gemini(fail_times=5, error=TransientError("quota"))
    with pytest.raises(TransientError):
        clients.llm_complete(model=settings.model_primary, system="s", user_turn="u",
                             max_tokens=10, agent_id="1.1")
    assert len(fake.calls) == 3


def test_usage_is_logged(gemini, caplog):
    import logging
    gemini()
    with caplog.at_level(logging.INFO, logger="suite.llm"):
        clients.llm_complete(model=settings.model_primary, system="s", user_turn="u",
                             max_tokens=10, agent_id="2.2")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "2.2" in joined and "150" in joined
