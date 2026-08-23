"""Tests validating A2A Agent Card manifest and OpenAPI specs for Gemini Enterprise."""
import json
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
A2A_DIR = REPO_ROOT / "deploy" / "a2a"


def test_agent_card_exists_and_valid():
    card_path = A2A_DIR / "marketing_suite_agent_card.json"
    assert card_path.exists(), "marketing_suite_agent_card.json missing"

    data = json.loads(card_path.read_text(encoding="utf-8"))
    assert data["agent_id"] == "qhhe-marketing-suite"
    assert data["language"] == "es-MX"
    assert data["runtime"]["platform"] == "vertex_ai_reasoning_engine"
    assert data["runtime"]["model"] == "gemini-3.7-flash"

    # Validate capabilities
    capabilities = {c["id"] for c in data["capabilities"]}
    expected_capabilities = {
        "get_client_summary",
        "get_audience_and_competition",
        "get_marketing_strategy",
        "get_content_and_campaigns",
        "get_creative_deliverables",
        "get_run_execution_status",
    }
    assert capabilities == expected_capabilities


def test_openapi_spec_exists_and_valid_yaml():
    spec_path = A2A_DIR / "openapi_spec.yaml"
    assert spec_path.exists(), "openapi_spec.yaml missing"

    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert spec["openapi"].startswith("3.")
    assert "paths" in spec
    assert "/:query" in spec["paths"]
    post_op = spec["paths"]["/:query"]["post"]
    assert post_op["operationId"] == "queryReasoningEngine"
