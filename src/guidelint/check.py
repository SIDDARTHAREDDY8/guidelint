"""The lint engine: runs rules against parsed configs and returns Findings."""

import os
import re

from . import backends, strict
from .parsers import LEGACY_GUIDED_FIELDS
from .rules import RULE_INDEX


class Finding:
    def __init__(self, rule_id, severity, message, evidence_url, fix,
                 location=None, detail=None):
        self.rule_id = rule_id
        self.severity = severity
        self.message = message
        self.evidence_url = evidence_url
        self.fix = fix
        self.location = location
        self.detail = detail

    def to_dict(self):
        return {
            "rule": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence_url,
            "fix": self.fix,
            "location": self.location,
            "detail": self.detail,
        }


def _finding(rule_id, location=None, detail=None, message=None, severity=None):
    rule = RULE_INDEX[rule_id]
    return Finding(
        rule_id=rule_id,
        severity=severity or rule["severity"],
        message=message or rule["message"],
        evidence_url=rule["evidence_url"],
        fix=rule["fix"],
        location=location,
        detail=detail,
    )


def _version_tuple(version):
    try:
        return tuple(int(p) for p in str(version).split(".")[:3])
    except ValueError:
        return None


def _version_gte(version, minimum):
    vt, mt = _version_tuple(version), _version_tuple(minimum)
    if vt is None or mt is None:
        return None
    return vt >= mt


# ---- serve-command checks ---------------------------------------------------


def check_serve(cmd, engine="vllm", engine_version=None, backend="xgrammar",
                workdir=None):
    """Lint one parsed serve command. Returns a list of Findings."""
    findings = []
    flags = cmd.get("flags", {})

    if engine_version is None:
        findings.append(_finding("engine-version-unknown",
                                 location="serve command"))

    legacy_flags = [
        f for f in flags
        if f.lstrip("-").replace("-", "_") in LEGACY_GUIDED_FIELDS
    ]
    removed = engine == "vllm" and (
        engine_version is None or _version_gte(engine_version, "0.12.0"))
    for flag in legacy_flags:
        if removed:
            findings.append(_finding(
                "vllm-guided-removed",
                location="serve flag %s" % flag,
                detail="flag present on vllm%s" % (
                    " %s" % engine_version if engine_version else "")))
        else:
            findings.append(_finding(
                "vllm-guided-removed",
                location="serve flag %s" % flag,
                severity="info",
                message="guided_* flags work on this vLLM version but were removed "
                        "in v0.12.0 — migrate to structured_outputs before upgrading."))

    # enable_thinking=false + xgrammar bypass
    thinking = flags.get("--enable-thinking")
    if str(thinking).lower() == "false" and backend == "xgrammar":
        findings.append(_finding("vllm-thinking-xgrammar-bypass",
                                 location="--enable-thinking=false"))

    # xgrammar + speculative decoding
    if backend == "xgrammar" and any(
            f in flags for f in ("--speculative-model", "--speculative-config")):
        findings.append(_finding("xgrammar-specdecode",
                                 location="speculative decoding flags"))

    # grammar file existence
    grammar_flag = flags.get("--guided-grammar") or flags.get("--structured-outputs")
    if isinstance(grammar_flag, str) and grammar_flag.endswith(
            (".gbnf", ".lark", ".json")):
        path = grammar_flag
        if workdir and not os.path.isabs(path):
            path = os.path.join(workdir, path)
        if not os.path.exists(path):
            findings.append(_finding("grammar-file-missing",
                                     location="--guided-grammar %s" % grammar_flag))

    # guided_choice empty
    choice = flags.get("--guided-choice")
    if isinstance(choice, str) and not choice.strip():
        findings.append(_finding("choice-empty", location="--guided-choice"))

    # regex validity
    regex = flags.get("--guided-regex")
    if isinstance(regex, str):
        try:
            re.compile(regex)
        except re.error as exc:
            findings.append(_finding("regex-invalid",
                                     location="--guided-regex",
                                     detail=str(exc)))

    # backend known?
    if backend not in backends.BACKENDS:
        findings.append(_finding("backend-unknown",
                                 location="--guided-decoding-backend %s" % backend))

    return findings


# ---- request-body checks ----------------------------------------------------


def check_body(surface, engine="vllm", engine_version=None, backend="xgrammar"):
    """Lint the parsed request-body surface. Returns a list of Findings."""
    findings = []

    removed = engine == "vllm" and (
        engine_version is None or _version_gte(engine_version, "0.12.0"))
    for field in sorted(surface["legacy_guided"]):
        if removed:
            findings.append(_finding("vllm-guided-removed",
                                     location="request body field `%s`" % field))
        else:
            findings.append(_finding(
                "vllm-guided-removed",
                location="request body field `%s`" % field,
                severity="info",
                message="guided_* request fields work on this vLLM version but were "
                        "removed in v0.12.0 — migrate to structured_outputs."))

    for field in surface["unknown_fields"]:
        findings.append(_finding("unknown-body-fields",
                                 location="request body field `%s`" % field,
                                 detail="not a recognized OpenAI-compatible field"))

    rf = surface["response_format"]
    if isinstance(rf, dict) and rf.get("type") == "json_object":
        findings.append(_finding("response-format-confusion",
                                 location="response_format"))

    so = surface["structured_outputs"]
    if isinstance(so, dict):
        if so.get("lenient") in (True, "true", "True"):
            findings.append(_finding("lenient-drop",
                                     location="structured_outputs.lenient"))
        regex = so.get("regex")
        if isinstance(regex, str):
            try:
                re.compile(regex)
            except re.error as exc:
                findings.append(_finding("regex-invalid",
                                         location="structured_outputs.regex",
                                         detail=str(exc)))
        choices = so.get("choice")
        if isinstance(choices, list) and not choices:
            findings.append(_finding("choice-empty",
                                     location="structured_outputs.choice"))

    if str(surface.get("enable_thinking")).lower() == "false" and backend == "xgrammar":
        findings.append(_finding("vllm-thinking-xgrammar-bypass",
                                 location="request body enable_thinking=false"))

    # strict mode violations
    is_strict, schema = _strict_in_body(surface)
    if is_strict and isinstance(schema, dict):
        for violation in strict.check_strict(schema):
            findings.append(_finding("strict-requirements",
                                     location="response_format.json_schema",
                                     detail=violation))
    elif is_strict:
        findings.append(_finding("strict-docs-best-practice",
                                 location="response_format.json_schema"))

    return findings


def _strict_in_body(surface):
    rf = surface.get("response_format") or {}
    if isinstance(rf, dict) and rf.get("type") == "json_schema":
        js = rf.get("json_schema") or {}
        if js.get("strict"):
            return True, js.get("schema")
    return False, None


# ---- schema checks ----------------------------------------------------------


def check_schema(schema, backend="xgrammar", engine="vllm",
                 strict_mode=False, location="schema"):
    """Lint a JSON Schema against a backend's keyword matrix."""
    findings = []
    if backend not in backends.BACKENDS:
        findings.append(_finding("backend-unknown", location="backend %s" % backend))
        return findings

    used = backends.keywords_used(schema)
    ignored = sorted(k for k in used if backends.support(backend, k) == "ignored")
    unknown = {k for k in used if backends.support(backend, k) == "unknown"}

    if ignored:
        findings.append(_finding(
            "keyword-support-gap",
            location=location,
            detail="backend %s silently ignores: %s" % (backend, ", ".join(ignored))))

    drift_keywords = {"oneOf", "anyOf", "additionalProperties", "pattern",
                      "minLength", "maxLength"}
    risky_unknown = sorted(unknown & drift_keywords)
    if risky_unknown:
        findings.append(_finding(
            "oneof-support" if ({"oneOf", "anyOf"} & set(risky_unknown))
            else "keyword-support-gap",
            location=location,
            detail="backend %s support unknown for: %s — verify the compiled "
                   "grammar actually constrains them" % (backend, ", ".join(risky_unknown))))

    if backend in ("ollama", "llama.cpp") and used & drift_keywords:
        findings.append(_finding("schema-grammar-drift", location=location))

    if "additionalProperties" in used and schema.get("additionalProperties") is False:
        # additionalProperties:false honored by some compilers, ignored by others
        inconsistent = [b for b in ("guidance", "llama.cpp", "ollama")
                        if backends.support(b, "additionalProperties") != "honored"]
        if inconsistent:
            findings.append(_finding(
                "additional-properties-inconsistent",
                location=location,
                detail="additionalProperties:false not reliably honored by: %s"
                       % ", ".join(inconsistent)))

    if strict_mode:
        for violation in strict.check_strict(schema):
            findings.append(_finding("strict-requirements",
                                     location=location, detail=violation))

    # informational: accuracy cliffs + field order apply to any constrained schema
    findings.append(_finding("accuracy-cliffs", location=location))
    findings.append(_finding("field-order-leak", location=location))
    return findings


def check_schema_wiring(body_surface, schema_provided):
    """The schema-not-wired rule: --schema given but body never references it."""
    findings = []
    if schema_provided:
        has_ref = (
            (body_surface.get("structured_outputs") not in (None, {}))
            or _strict_in_body(body_surface)[0]
            or (isinstance(body_surface.get("response_format"), dict)
                and body_surface["response_format"].get("type") == "json_schema")
        )
        if not has_ref:
            findings.append(_finding("schema-not-wired",
                                     location="request body"))
    return findings
