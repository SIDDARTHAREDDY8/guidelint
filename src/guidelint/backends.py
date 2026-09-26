"""Per-backend JSON-Schema keyword support matrix.

Support levels:
  "honored"  — the backend enforces the keyword in the compiled grammar/logit mask.
  "ignored"  — the keyword is silently dropped (the constraint is NOT enforced).
  "error"    — the backend raises / rejects the schema outright.
  "unknown"  — support could not be confirmed; guidelint treats this conservatively
               (rules may warn, never error, on "unknown").

The matrix is deliberately conservative: a keyword only counts as "honored" when
there is documented or issue-backed evidence. Anything uncertain is "unknown".
A compiled grammar is the real contract — "your schema is not your contract; the
compiled grammar is your contract" (aiclearinghouse, 2026-09).
"""

SUPPORT = ("honored", "ignored", "error", "unknown")

MATRIX = {
    "xgrammar": {
        "type": "honored",
        "properties": "honored",
        "required": "honored",
        "additionalProperties": "honored",
        "items": "honored",
        "enum": "honored",
        "const": "honored",
        "oneOf": "honored",
        "anyOf": "honored",
        "allOf": "unknown",
        "pattern": "honored",
        "minLength": "honored",
        "maxLength": "honored",
        "minimum": "honored",
        "maximum": "honored",
        "multipleOf": "unknown",
        "format": "ignored",
        "default": "ignored",
        "description": "ignored",
        "title": "ignored",
        "nullable": "honored",
        "$ref": "honored",
    },
    "outlines": {
        "type": "honored",
        "properties": "honored",
        "required": "honored",
        "additionalProperties": "honored",
        "items": "honored",
        "enum": "honored",
        "const": "honored",
        "oneOf": "honored",
        "anyOf": "honored",
        "allOf": "unknown",
        "pattern": "honored",
        "minLength": "honored",
        "maxLength": "honored",
        "minimum": "honored",
        "maximum": "honored",
        "multipleOf": "honored",
        "format": "honored",
        "default": "ignored",
        "description": "ignored",
        "title": "ignored",
        "nullable": "honored",
        "$ref": "honored",
    },
    "guidance": {
        "type": "honored",
        "properties": "honored",
        "required": "honored",
        "additionalProperties": "unknown",
        "items": "honored",
        "enum": "honored",
        "const": "honored",
        "oneOf": "unknown",
        "anyOf": "unknown",
        "allOf": "unknown",
        "pattern": "unknown",
        "minLength": "unknown",
        "maxLength": "unknown",
        "minimum": "unknown",
        "maximum": "unknown",
        "multipleOf": "unknown",
        "format": "unknown",
        "default": "ignored",
        "description": "ignored",
        "title": "ignored",
        "nullable": "unknown",
        "$ref": "unknown",
    },
    "llguidance": {
        "type": "honored",
        "properties": "honored",
        "required": "honored",
        "additionalProperties": "honored",
        "items": "honored",
        "enum": "honored",
        "const": "honored",
        "oneOf": "honored",
        "anyOf": "honored",
        "allOf": "unknown",
        "pattern": "honored",
        "minLength": "honored",
        "maxLength": "honored",
        "minimum": "honored",
        "maximum": "honored",
        "multipleOf": "unknown",
        "format": "unknown",
        "default": "ignored",
        "description": "ignored",
        "title": "ignored",
        "nullable": "honored",
        "$ref": "honored",
    },
    "llama.cpp": {
        "type": "honored",
        "properties": "honored",
        "required": "honored",
        "additionalProperties": "ignored",
        "items": "honored",
        "enum": "honored",
        "const": "honored",
        "oneOf": "unknown",
        "anyOf": "unknown",
        "allOf": "unknown",
        "pattern": "unknown",
        "minLength": "unknown",
        "maxLength": "unknown",
        "minimum": "unknown",
        "maximum": "unknown",
        "multipleOf": "unknown",
        "format": "ignored",
        "default": "ignored",
        "description": "ignored",
        "title": "ignored",
        "nullable": "unknown",
        "$ref": "honored",
    },
    "ollama": {
        # Ollama converts JSON Schema to a grammar at serve time; the conversion
        # path has been rewritten between releases, silently changing which
        # constraints hold. Conservative by design.
        "type": "honored",
        "properties": "honored",
        "required": "honored",
        "additionalProperties": "unknown",
        "items": "honored",
        "enum": "honored",
        "const": "unknown",
        "oneOf": "unknown",
        "anyOf": "unknown",
        "allOf": "unknown",
        "pattern": "unknown",
        "minLength": "unknown",
        "maxLength": "unknown",
        "minimum": "unknown",
        "maximum": "unknown",
        "multipleOf": "unknown",
        "format": "ignored",
        "default": "ignored",
        "description": "ignored",
        "title": "ignored",
        "nullable": "unknown",
        "$ref": "unknown",
    },
}

BACKENDS = sorted(MATRIX)
KEYWORDS = [
    "type", "properties", "required", "additionalProperties", "items", "enum",
    "const", "oneOf", "anyOf", "allOf", "pattern", "minLength", "maxLength",
    "minimum", "maximum", "multipleOf", "format", "default", "description",
    "title", "nullable", "$ref",
]


def support(backend, keyword):
    """Return the support level for backend/keyword, or 'unknown'."""
    return MATRIX.get(backend, {}).get(keyword, "unknown")


def keywords_used(schema, _seen=None):
    """Collect JSON-Schema keywords actually used in a schema (recursive)."""
    used = set()
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in KEYWORDS:
                used.add(key)
            if isinstance(value, (dict, list)):
                used |= keywords_used(value, None)
    elif isinstance(schema, list):
        for item in schema:
            used |= keywords_used(item, None)
    return used
