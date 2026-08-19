"""Schema -> compact structure SKELETON, injected into agent system prompts at
runtime so the model emits the EXACT structure its block schema requires.

This is the systemic fix for the "prompt under-specifies the output -> model
improvises a non-conforming shape" bug class (first seen on Agent 1.1). Because
the skeleton is regenerated from the schema on every run, the prompt and schema
can never drift apart. Enums are shown verbatim, patterns/formats as hints, and
nullability is marked — so it also suppresses enum/pattern/null-vs-value drift.
"""
from __future__ import annotations
import json
from functools import lru_cache


def _resolve(node, root):
    if isinstance(node, dict) and "$ref" in node:
        cur = root
        for part in node["$ref"][2:].split("/"):
            cur = cur[part]
        merged = dict(cur)
        for k, v in node.items():
            if k != "$ref":
                merged.setdefault(k, v)
        return merged
    return node


def _types(node):
    t = node.get("type")
    return t if isinstance(t, list) else ([t] if t else [])


def _skel(node, root):
    node = _resolve(node, root)
    if "oneOf" in node or "anyOf" in node:
        opts = node.get("oneOf") or node.get("anyOf")
        non_null = [o for o in opts if _resolve(o, root).get("type") != "null"]
        return _skel((non_null or opts)[0], root)
    if "enum" in node:
        return "|".join("null" if v is None else str(v) for v in node["enum"])
    ts = _types(node)
    if "object" in ts or "properties" in node:
        props = node.get("properties", {})
        if not props and isinstance(node.get("additionalProperties"), dict):
            return {"<key>": _skel(node["additionalProperties"], root)}
        return {k: _skel(v, root) for k, v in props.items()}
    if "array" in ts:
        items = node.get("items", {})
        return [_skel(items, root)] if items else []
    if "string" in ts:
        if node.get("format"):
            h = f"<{node['format']}>"
        elif node.get("pattern"):
            h = f"<str ~ {node['pattern']}>"
        else:
            h = "<str>"
        return h + ("|null" if "null" in ts else "")
    if "number" in ts or "integer" in ts:
        base = "int" if "integer" in ts else "num"
        rng = []
        if "minimum" in node:
            rng.append(f">={node['minimum']}")
        if "maximum" in node:
            rng.append(f"<={node['maximum']}")
        h = f"<{base}{(' ' + ' '.join(rng)) if rng else ''}>"
        return h + ("|null" if "null" in ts else "")
    if "boolean" in ts:
        return "<bool>" + ("|null" if "null" in ts else "")
    if "null" in ts:
        return None
    return "<value>"


@lru_cache(maxsize=64)
def skeleton_json(schema_json: str) -> str:
    """Return the indented skeleton string for a schema (passed as a JSON string
    so it is hashable for the cache)."""
    schema = json.loads(schema_json)
    return json.dumps(_skel(schema, schema), indent=2, ensure_ascii=False)


_RULES = (
    "STRUCTURE RULES — your `## OUTPUT 1` JSON must match the skeleton above EXACTLY:\n"
    "- Emit every key shown, with the same nesting. Do NOT add wrapper objects, rename keys, or invent keys.\n"
    "- `<str>`, `<int>`, `<num>`, `<date>`, `<date-time>`, `<bool>` are typed placeholders — replace with real values.\n"
    "- `a|b|c` is an enum: output exactly ONE of those literal values (correct case, verbatim).\n"
    "- `<... ~ ^regex$>` must match that pattern. `client_id` is supplied to you — echo it unchanged.\n"
    "- A value may be null ONLY where the skeleton shows `|null`. Everywhere else, never null: if data is "
    "missing, substitute a benchmark/estimate (tag it Tier D where the schema carries confidence metadata).\n"
    "- Arrays may contain as many elements as the content requires (the skeleton shows one example element).\n"
    "- Begin your reply DIRECTLY with `## OUTPUT 1` — no preamble, no restating this schema, no thinking aloud "
    "before the outputs (that wastes the token budget and can truncate the JSON)."
)


def output_structure_appendix(schema_json: str, schema_name: str) -> str:
    return (
        f"\n\n---\n## REQUIRED OUTPUT 1 STRUCTURE (schema: {schema_name})\n"
        f"Your `## OUTPUT 1` ```json block MUST conform to this exact structure:\n\n"
        f"```json\n{skeleton_json(schema_json)}\n```\n\n{_RULES}"
    )
