"""Shared agent runner for the Digital Marketing AI Suite.

Every product agent (Layers 1–6) is built on `BaseAgent` so the 18 remaining
agents are ~40 lines of contract-specific code instead of copy-pasting Agent
1.1's prompt-loading / caching / validation / routing (and its bugs) 19 times.

Design (per ADR-04 + D-07):
  - prompt loaded from a versioned ASSET file (not by grepping a markdown
    deliverable), resolved lazily so importing the module never touches disk;
  - one cached Claude call on Vertex (system prompt always cached);
  - output split + JSON-Schema validation;
  - routing to Cloud SQL / Pub-Sub / Firestore;
  - malformed model output is routed to the human review queue, never raised
    into the caller — a formatting drift must not crash a client's run;
  - every call is tagged with client_id + agent_id for cost attribution
    (feeds project/specs/AGENT_COST_MODEL.md monitoring).

Subclasses implement `build_user_turn(payload)` and declare class attributes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from infra.config import settings
from infra import clients
from infra import skeleton
from infra.log import get_logger

log = get_logger("agent")

_JSON_BLOCK = re.compile(r"```json\n([\s\S]+?)\n```")

# Repo root = three parents up from suite/agents/base.py
_ROOT = Path(__file__).resolve().parents[2]


def load_prompt(rel_path: str) -> str:
    """Load a versioned system-prompt asset, e.g.
    'agents/layer1/prompts/agent_1_1_system.txt'. Resolved under the suite/
    package first, then the repo root, so it works in-container and in-repo."""
    for base in (_ROOT / "suite", _ROOT):
        p = base / rel_path
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(
        f"prompt asset not found: {rel_path} (looked under suite/ and repo root)"
    )


@dataclass
class AgentResult:
    agent_id: str
    client_id: str | None
    outputs: dict[str, str]            # named raw output sections
    structured: dict[str, Any] | None  # the validated OUTPUT-1 object (if any)
    valid: bool
    error: str | None = None


@dataclass
class BaseAgent:
    """Base class for product agents. Subclass and set the fields below."""

    agent_id: str                         # e.g. "1.1"
    prompt_asset: str                     # e.g. "agents/layer1/prompts/agent_1_1_system.txt"
    model: str = settings.model_primary   # override with routing/deep per cost model
    max_tokens: int = 8000
    schema_name: str | None = None        # e.g. "DEL-17" / "audience_segments" → validate OUTPUT 1
    memory_block: str = "client_profile"  # the block this agent writes (per ARCHITECTURE.md)
    inject_client_id: bool = True         # every block schema in this suite requires a top-level
                                          # client_id; stamp the system-assigned id (the orchestrator
                                          # owns it) rather than trust the model to mint a pattern-valid one
    append_schema_skeleton: bool = True   # append a schema-derived OUTPUT-1 structure skeleton to the
                                          # system prompt so the model emits the exact required shape
                                          # (off for agents whose prompt already embeds a tuned skeleton)
    output_markers: tuple[str, ...] = ("## OUTPUT 1", "## OUTPUT 2", "## OUTPUT 3")
    review_collection: str = field(default_factory=lambda: settings.review_collection)

    # ---- subclass hook -----------------------------------------------------
    def build_user_turn(self, payload: dict) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    # ---- prompt (lazy, cached per instance) --------------------------------
    _system_prompt: str | None = field(default=None, init=False, repr=False)

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = load_prompt(self.prompt_asset)
        return self._system_prompt

    @property
    def effective_system_prompt(self) -> str:
        """System prompt actually sent to the model: the asset, plus a schema-
        derived OUTPUT-1 structure skeleton (so the model emits the exact shape
        the validator requires). The skeleton is regenerated from the schema, so
        prompt and schema can never drift apart."""
        prompt = self.system_prompt
        if self.append_schema_skeleton and self.schema_name:
            import json
            schema_json = json.dumps(clients.load_schema(self.schema_name), sort_keys=True)
            prompt += skeleton.output_structure_appendix(schema_json, self.schema_name)
        return prompt

    # ---- model call --------------------------------------------------------
    def call(self, user_turn: str) -> str:
        """One cached completion via the configured provider (Vertex in prod,
        canned fixtures offline). Provider choice lives in infra.clients so every
        agent is provider-agnostic; the system prompt is always cached."""
        return clients.llm_complete(
            model=self.model,
            system=self.effective_system_prompt,
            user_turn=user_turn,
            max_tokens=self.max_tokens,
            agent_id=self.agent_id,
        )

    # ---- output parsing ----------------------------------------------------
    def split_outputs(self, raw: str) -> dict[str, str]:
        """Split on the agent's ordered output markers. Tolerant: a missing
        marker yields an empty section rather than raising."""
        idxs = []
        for m in self.output_markers:
            i = raw.find(m)
            idxs.append(i)
        out: dict[str, str] = {}
        for n, (m, i) in enumerate(zip(self.output_markers, idxs), start=1):
            if i < 0:
                out[f"output_{n}"] = ""
                continue
            nxt = min((j for j in idxs[n:] if j > i), default=len(raw))
            out[f"output_{n}"] = raw[i:nxt].strip()
        return out

    @staticmethod
    def extract_json(section: str) -> dict | None:
        m = _JSON_BLOCK.search(section or "")
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None

    def validate(self, obj: dict | None) -> tuple[bool, str | None]:
        if self.schema_name is None:
            return True, None
        if obj is None:
            return False, "OUTPUT 1 did not contain a parseable JSON block"
        import jsonschema
        try:
            jsonschema.validate(obj, clients.load_schema(self.schema_name))
            return True, None
        except jsonschema.ValidationError as e:  # pragma: no cover - exercised via tests w/ stub
            loc = "/".join(str(p) for p in e.absolute_path) or "(root)"
            return False, f"schema validation failed at '{loc}': {e.message}"

    # ---- orchestration -----------------------------------------------------
    def run(self, payload: dict) -> AgentResult:
        """Synchronous end-to-end run. Vertex/Firestore/Pub-Sub clients are all
        synchronous; we keep the whole path sync to avoid the event-loop-blocking
        async/sync mix. Concurrency is achieved by running agents as separate
        Cloud Run Jobs / Agent Engine invocations, not in-process async."""
        client_id = payload.get("client_id")
        user_turn = self.build_user_turn(payload)
        # Robustness: when there's a schema to satisfy, retry ONCE on a parse/validate
        # failure. The model samples at temperature, so a second attempt usually clears
        # transient formatting drift (a null where an object is required, an unfenced
        # JSON block). Deterministic failures (e.g. a too-low max_tokens that truncates
        # every time) are unaffected and still route to the human review queue.
        max_attempts = 2 if self.schema_name else 1
        outputs: dict[str, str] = {}
        obj: dict | None = None
        valid, err = False, None
        for _attempt in range(max_attempts):
            # Feedback retry: the re-ask carries the exact validation error, so
            # the model can fix it (a blind re-ask does not fix enum/shape drift
            # — observed live with Gemini on tone_selected).
            turn = user_turn if not err else (
                f"{user_turn}\n\n## CORRECTION REQUIRED\n"
                f"Your previous response failed validation: {err}\n"
                f"Re-emit ALL outputs in full, fixing exactly this issue."
            )
            try:
                raw = self.call(turn)
            except Exception as e:  # network/model error — surface, don't crash a batch
                log.exception("agent %s: model call failed (client=%s)", self.agent_id, client_id)
                return AgentResult(self.agent_id, client_id, {}, None, False, f"model call failed: {e}")
            outputs = self.split_outputs(raw)
            obj = self.extract_json(outputs.get("output_1", ""))
            # client_id is a system-assigned key (the orchestrator owns it), not something
            # the model should mint — stamp it before validation when the schema needs it.
            if obj is not None and self.inject_client_id and client_id:
                obj["client_id"] = client_id
            valid, err = self.validate(obj)
            if valid:
                break

        if not valid:
            log.warning("agent %s: invalid output after %d attempt(s) (client=%s): %s",
                        self.agent_id, max_attempts, client_id, err)
        # Persist whatever we got; route to human review on any problem.
        self.route(client_id, obj, outputs, valid, err)
        return AgentResult(self.agent_id, client_id, outputs, obj if valid else None, valid, err)

    # ---- routing (override per agent as needed) ----------------------------
    def route(self, client_id, obj, outputs, valid, err) -> None:
        """Default routing: valid structured output → its memory block (Cloud SQL
        in prod, in-process store offline); human-readable summary + any error →
        review queue (priority escalates on invalid output or a 'blocked' gate)."""
        gate = (obj or {}).get("gate_status", "pending")
        if valid and obj is not None and client_id:
            clients.write_memory_block(client_id, self.memory_block, obj, gate)

        priority = "urgent" if (not valid or gate == "blocked") else "normal"
        clients.add_review_doc(self.review_collection, {
            "client_id": client_id,
            "agent": self.agent_id,
            "valid": valid,
            "error": err,
            "gate_summary": outputs.get("output_3", ""),
            "raw_preview": (outputs.get("output_1", "") or "")[:2000],
            "priority": priority,
        })


def split_named(raw: str, markers: dict[str, str]) -> dict[str, str]:
    """Utility for agents whose outputs aren't the default OUTPUT 1/2/3 — pass
    {name: marker}. Returns {name: section}."""
    found = [(name, raw.find(mk)) for name, mk in markers.items()]
    found.sort(key=lambda t: (t[1] < 0, t[1]))
    out = {}
    positions = [i for _, i in found if i >= 0]
    for k, (name, i) in enumerate(found):
        if i < 0:
            out[name] = ""
            continue
        nxt = min((j for j in positions if j > i), default=len(raw))
        out[name] = raw[i:nxt].strip()
    return out
