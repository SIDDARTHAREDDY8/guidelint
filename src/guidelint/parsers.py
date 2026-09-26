"""Parsers: vLLM serve command lines / shell scripts, request bodies, JSON Schemas.

Everything is stdlib-only (shlex, json, re). The serve-flag parser understands
the vLLM OpenAI-compatible server's structured-output surface; unknown flags are
preserved verbatim so rules can see the whole picture.
"""

import json
import os
import re
import shlex


# ---- vLLM serve flag knowledge ---------------------------------------------

# Flags that configure structured / guided decoding on `vllm serve`.
STRUCTURED_FLAGS = {
    "--guided-json",
    "--guided-regex",
    "--guided-choice",
    "--guided-grammar",
    "--guided-decoding-backend",
    "--guided-whitespace-pattern",
    "--enable-thinking",
    "--reasoning-parser",
    "--structured-outputs",
    "--speculative-model",
    "--speculative-config",
    "--speculative-draft-tensor-parallel-size",
}

# Legacy request-body fields removed in vLLM v0.12.0 (silently ignored after).
# Note: --guided-decoding-backend is NOT legacy — it still selects the backend.
LEGACY_GUIDED_FIELDS = {
    "guided_json",
    "guided_regex",
    "guided_choice",
    "guided_grammar",
}

# Fields the OpenAI-compatible surface understands (top-level + chat completions).
KNOWN_BODY_FIELDS = {
    "model", "messages", "temperature", "top_p", "n", "stream", "stop",
    "max_tokens", "max_completion_tokens", "presence_penalty", "frequency_penalty",
    "logit_bias", "logprobs", "top_logprobs", "user", "seed", "tools",
    "tool_choice", "parallel_tool_calls", "response_format", "structured_outputs",
    "extra_body", "reasoning_effort", "metadata", "store", "service_tier",
    "enable_thinking",
} | LEGACY_GUIDED_FIELDS


def parse_serve_command(command):
    """Parse a single `vllm serve ...` command line into a dict.

    Returns {"engine": "vllm"|None, "model": str|None, "flags": {flag: value},
    "positional": [...], "raw": command}. Value flags consume the next token;
    boolean flags map to True. Quoted values are unquoted via shlex.
    """
    try:
        tokens = shlex.split(command, comments=True)
    except ValueError:
        tokens = command.split()
    flags = {}
    positional = []
    model = None
    engine = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "vllm" and i + 1 < len(tokens) and tokens[i + 1] == "serve":
            engine = "vllm"
            i += 2
            continue
        if tok.startswith("--"):
            name, eq, val = tok.partition("=")
            if eq:
                flags[name] = val
            elif i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                flags[name] = tokens[i + 1]
                i += 1
            else:
                flags[name] = True
        elif tok.startswith("-") and len(tok) == 2:
            # short flag, e.g. -tp 4
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                flags[tok] = tokens[i + 1]
                i += 1
            else:
                flags[tok] = True
        else:
            if engine == "vllm" and model is None and not positional:
                model = tok
            else:
                positional.append(tok)
        i += 1
    return {
        "engine": engine,
        "model": model,
        "flags": flags,
        "positional": positional,
        "raw": command,
    }


def parse_serve_script(text):
    """Extract every `vllm serve` invocation from a shell script.

    Handles line continuations (backslashes), comments, and env-var prefixes.
    Returns a list of parse_serve_command dicts.
    """
    # Join line continuations first.
    text = re.sub(r"\\\n", " ", text)
    commands = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Drop VAR=... prefixes so `FOO=1 vllm serve ...` still parses.
        cleaned = re.sub(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)+", "", stripped)
        if "vllm" in cleaned and "serve" in cleaned:
            commands.append(parse_serve_command(cleaned))
    return commands


# ---- request body parsing ---------------------------------------------------


def parse_request_body(text):
    """Parse a JSON request body. Returns {"ok": True, "body": dict, ...} or
    {"ok": False, "error": str}. Extracts the structured-output surface."""
    try:
        body = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": "invalid JSON: %s" % exc}
    if not isinstance(body, dict):
        return {"ok": False, "error": "request body must be a JSON object"}
    surface = {
        "legacy_guided": {k: body[k] for k in LEGACY_GUIDED_FIELDS if k in body},
        "response_format": body.get("response_format"),
        "structured_outputs": body.get("structured_outputs"),
        "extra_body": body.get("extra_body"),
        "enable_thinking": body.get("enable_thinking"),
        "unknown_fields": sorted(k for k in body if k not in KNOWN_BODY_FIELDS),
    }
    return {"ok": True, "body": body, "surface": surface}


# ---- JSON Schema parsing ----------------------------------------------------


def parse_schema(text):
    """Parse a JSON Schema document. Returns {"ok": True, "schema": dict} or
    {"ok": False, "error": str}."""
    try:
        schema = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": "invalid JSON: %s" % exc}
    if isinstance(schema, bool):
        schema = {}
    if not isinstance(schema, dict):
        return {"ok": False, "error": "schema must be a JSON object"}
    return {"ok": True, "schema": schema}


def is_strict_json_schema(body):
    """Detect response_format json_schema with strict:true in a request body."""
    rf = (body or {}).get("response_format") or {}
    if isinstance(rf, dict) and rf.get("type") == "json_schema":
        js = rf.get("json_schema") or {}
        return bool(js.get("strict")), js.get("schema")
    return False, None
