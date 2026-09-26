"""Strict-mode normalizer / checker.

Strict mode (OpenAI-compatible `strict:true`) requires:
  * every property listed in `required`
  * no `default` keyword anywhere
  * `additionalProperties: false` at the object level

`check_strict(schema)` returns a list of human-readable violations.
`normalize_strict(schema)` returns a copy rewritten to satisfy strict mode
(best-effort; nested objects are handled recursively).
"""

import copy


def check_strict(schema, path="$"):
    """Return a list of violation strings for strict-mode requirements."""
    violations = []
    if not isinstance(schema, dict):
        return violations
    if "default" in schema:
        violations.append(
            "%s uses the `default` keyword, which strict mode forbids" % path
        )
    if schema.get("type") == "object" or "properties" in schema:
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        for name in properties:
            if name not in required:
                violations.append(
                    "%s.properties.%s is not listed in required "
                    "(strict mode requires every property in required)" % (path, name)
                )
        for name, subschema in properties.items():
            violations.extend(
                check_strict(subschema, "%s.properties.%s" % (path, name))
            )
    if isinstance(schema.get("items"), dict):
        violations.extend(check_strict(schema["items"], "%s.items" % path))
    for kw in ("oneOf", "anyOf", "allOf"):
        for idx, branch in enumerate(schema.get(kw) or []):
            violations.extend(
                check_strict(branch, "%s.%s[%d]" % (path, kw, idx))
            )
    if "$defs" in schema and isinstance(schema["$defs"], dict):
        for name, subschema in schema["$defs"].items():
            violations.extend(
                check_strict(subschema, "%s.$defs.%s" % (path, name))
            )
    return violations


def normalize_strict(schema):
    """Return a strict-mode-conformant deep copy of the schema."""
    schema = copy.deepcopy(schema)

    def _fix(node):
        if not isinstance(node, dict):
            return node
        node.pop("default", None)
        if node.get("type") == "object" or "properties" in node:
            properties = node.get("properties") or {}
            node["required"] = sorted(properties.keys())
            node["additionalProperties"] = False
            for name in properties:
                node["properties"][name] = _fix(properties[name])
        if isinstance(node.get("items"), dict):
            node["items"] = _fix(node["items"])
        for kw in ("oneOf", "anyOf", "allOf"):
            if isinstance(node.get(kw), list):
                node[kw] = [_fix(b) for b in node[kw]]
        if isinstance(node.get("$defs"), dict):
            node["$defs"] = {k: _fix(v) for k, v in node["$defs"].items()}
        return node

    return _fix(schema)
