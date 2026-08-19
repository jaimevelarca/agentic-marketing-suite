"""DEL-17 client_profile schema regression tests.

Guards: the schema is a valid JSON Schema; a top-level `required` exists and
enforces the core fields; there is NO stray property literally named "required"
(a misnesting that would silently disable enforcement); the schema is versioned;
empty/under-specified objects are rejected.
"""
from __future__ import annotations

import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "project/resources/schemas/DEL-17_client_profile_schema.json"


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text())


def test_schema_is_valid_jsonschema(schema):
    jsonschema = pytest.importorskip("jsonschema")
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)  # raises if the schema itself is malformed


def test_top_level_required_present_and_enforcing(schema):
    assert "required" in schema, "top-level `required` must exist (else nothing is enforced)"
    core = {"client_id", "lifecycle_stage", "name", "industry", "goals", "budget", "constraints"}
    missing = core - set(schema["required"])
    assert not missing, f"these core fields must be required: {missing}"


def test_no_stray_required_property(schema):
    # Guards the misnesting bug class: `required` placed INSIDE properties is
    # treated by draft-07 as a property named "required" and ignored.
    assert "required" not in schema["properties"]


def test_versioned(schema):
    assert schema.get("version") == "0.3.1"


def test_empty_object_is_rejected():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({}, schema)


def test_partial_object_missing_required_is_rejected():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"name": "Acme Co.", "industry": "technology_consulting"}, schema)
