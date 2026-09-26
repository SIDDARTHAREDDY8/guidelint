"""Text and JSON report rendering."""

import json

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


def sort_findings(findings):
    return sorted(findings,
                  key=lambda f: (SEVERITY_ORDER.get(f.severity, 3), f.rule_id))


def text_report(findings, target):
    findings = sort_findings(findings)
    lines = ["guidelint: %s" % target, ""]
    errors = sum(1 for f in findings if f.severity == "error")
    warns = sum(1 for f in findings if f.severity == "warn")
    infos = sum(1 for f in findings if f.severity == "info")
    if not findings:
        lines.append("OK — no structured-output footguns found.")
        return "\n".join(lines)
    for f in findings:
        lines.append("[%s] %s (%s)" % (f.severity.upper(), f.rule_id,
                                       f.location or "config"))
        lines.append("  %s" % f.message)
        if f.detail:
            lines.append("  detail: %s" % f.detail)
        lines.append("  fix: %s" % f.fix)
        lines.append("  evidence: %s" % f.evidence_url)
        lines.append("")
    lines.append("summary: %d error(s), %d warning(s), %d info note(s)"
                 % (errors, warns, infos))
    return "\n".join(lines)


def json_report(findings, target, engine=None, engine_version=None, backend=None):
    findings = sort_findings(findings)
    return json.dumps({
        "tool": "guidelint",
        "target": target,
        "engine": engine,
        "engine_version": engine_version,
        "backend": backend,
        "summary": {
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warn"),
            "info": sum(1 for f in findings if f.severity == "info"),
        },
        "findings": [f.to_dict() for f in findings],
    }, indent=2)


def exit_code(findings):
    if any(f.severity == "error" for f in findings):
        return 1
    if any(f.severity == "warn" for f in findings):
        return 2
    return 0
