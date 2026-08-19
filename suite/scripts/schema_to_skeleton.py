"""Generate a compact, schema-conformant SKELETON from a JSON Schema, for pasting
into an agent's system prompt so the model emits the exact required structure
(the fix for the "prompt under-specifies -> model improvises" bug class).

Each leaf becomes a typed placeholder; enums are shown as "a|b|c"; required keys
are always present; one example element is emitted per array; $ref is resolved.
Not a data generator — a STRUCTURE guide.
"""
from __future__ import annotations
import json, sys, pathlib

def resolve(node, root):
    if isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        assert ref.startswith("#/"), ref
        cur = root
        for part in ref[2:].split("/"):
            cur = cur[part]
        # merge sibling keys (e.g. description) over the ref target
        merged = dict(cur)
        for k, v in node.items():
            if k != "$ref":
                merged.setdefault(k, v)
        return merged
    return node

def types_of(node):
    t = node.get("type")
    if isinstance(t, list):
        return t
    if t:
        return [t]
    return []

def skel(node, root, depth=0):
    node = resolve(node, root)
    # combinators
    if "oneOf" in node or "anyOf" in node:
        opts = node.get("oneOf") or node.get("anyOf")
        # prefer the first non-null option for a clearer skeleton
        non_null = [o for o in opts if resolve(o, root).get("type") != "null"]
        return skel((non_null or opts)[0], root, depth)
    if "enum" in node:
        vals = node["enum"]
        return "|".join("null" if v is None else str(v) for v in vals)
    ts = types_of(node)
    if "object" in ts or "properties" in node:
        props = node.get("properties", {})
        req = set(node.get("required", []))
        out = {}
        for k, v in props.items():
            # include all required keys + a representative set of optionals
            out[k] = skel(v, root, depth + 1)
        if not props and node.get("additionalProperties"):
            return {"<key>": skel(node["additionalProperties"], root, depth + 1)} if isinstance(node["additionalProperties"], dict) else {"<key>": "<value>"}
        return out
    if "array" in ts:
        items = node.get("items", {})
        return [skel(items, root, depth + 1)] if items else []
    if "string" in ts:
        hint = ""
        if node.get("format"): hint = f"<{node['format']}>"
        elif node.get("pattern"): hint = f"<str matching {node['pattern']}>"
        else: hint = "<str>"
        if "null" in ts: hint += "|null"
        return hint
    if "number" in ts or "integer" in ts:
        base = "<int>" if "integer" in ts else "<num>"
        rng = []
        if "minimum" in node: rng.append(f">={node['minimum']}")
        if "maximum" in node: rng.append(f"<={node['maximum']}")
        if rng: base = base[:-1] + " " + " ".join(rng) + ">"
        if "null" in ts: base += "|null"
        return base
    if "boolean" in ts:
        return "<bool>" + ("|null" if "null" in ts else "")
    if "null" in ts:
        return None
    return "<value>"

def main():
    path = pathlib.Path(sys.argv[1])
    root = json.loads(path.read_text(encoding="utf-8"))
    sk = skel(root, root)
    print(json.dumps(sk, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
