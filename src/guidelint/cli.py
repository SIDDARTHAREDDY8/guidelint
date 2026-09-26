"""guidelint CLI — shellcheck for your structured-output / constrained-decoding config."""

import argparse
import json
import os
import sys

from . import __version__, backends, parsers, strict
from . import check as checker
from . import report as report_mod


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def cmd_check(args):
    target = args.target
    workdir = os.path.dirname(os.path.abspath(target)) \
        if os.path.isfile(target) else os.getcwd()
    findings = []

    # 1. serve command / shell script
    if os.path.isfile(target):
        text = _read(target)
        commands = parsers.parse_serve_script(text)
        if not commands and "vllm" not in text:
            print("guidelint: no vllm serve invocation found in %s" % target,
                  file=sys.stderr)
        for cmd in commands:
            findings += checker.check_serve(
                cmd, engine=args.engine, engine_version=args.engine_version,
                backend=args.backend, workdir=workdir)
    else:
        cmd = parsers.parse_serve_command(target)
        findings += checker.check_serve(
            cmd, engine=args.engine, engine_version=args.engine_version,
            backend=args.backend, workdir=workdir)

    # 2. request body
    body_surface = None
    if args.request_body:
        parsed = parsers.parse_request_body(_read(args.request_body))
        if not parsed["ok"]:
            print("guidelint: %s: %s" % (args.request_body, parsed["error"]),
                  file=sys.stderr)
            return 1
        body_surface = parsed["surface"]
        findings += checker.check_body(
            body_surface, engine=args.engine,
            engine_version=args.engine_version, backend=args.backend)

    # 3. schema
    schema = None
    if args.schema:
        parsed = parsers.parse_schema(_read(args.schema))
        if not parsed["ok"]:
            print("guidelint: %s: %s" % (args.schema, parsed["error"]),
                  file=sys.stderr)
            return 1
        schema = parsed["schema"]
        findings += checker.check_schema(
            schema, backend=args.backend, engine=args.engine,
            location=args.schema)
        findings += checker.check_schema_wiring(body_surface or {}, True)

    if args.json:
        print(report_mod.json_report(
            findings, target, engine=args.engine,
            engine_version=args.engine_version, backend=args.backend))
    else:
        print(report_mod.text_report(findings, target))
    return report_mod.exit_code(findings)


def cmd_schema(args):
    parsed = parsers.parse_schema(_read(args.schema))
    if not parsed["ok"]:
        print("guidelint: %s: %s" % (args.schema, parsed["error"]),
              file=sys.stderr)
        return 1
    findings = checker.check_schema(
        parsed["schema"], backend=args.backend, engine=args.engine,
        strict_mode=args.strict, location=args.schema)
    if args.normalize_strict:
        print(json.dumps(strict.normalize_strict(parsed["schema"]), indent=2))
        return 0
    if args.json:
        print(report_mod.json_report(
            findings, args.schema, engine=args.engine, backend=args.backend))
    else:
        print(report_mod.text_report(findings, args.schema))
    return report_mod.exit_code(findings)


def cmd_matrix(args):
    if args.json:
        print(json.dumps(backends.MATRIX, indent=2))
        return 0
    backend_filter = args.backend
    names = [backend_filter] if backend_filter else backends.BACKENDS
    header = ["keyword"] + names
    rows = [header]
    for kw in backends.KEYWORDS:
        rows.append([kw] + [backends.support(b, kw) for b in names])
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    for row in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    print()
    print("honored = enforced in the compiled grammar; ignored = silently dropped;")
    print("error = backend rejects the schema; unknown = unverified (treated conservatively).")
    return 0


def cmd_rules(args):
    from .rules import RULES
    if args.json:
        print(json.dumps(RULES, indent=2))
        return 0
    for rule in RULES:
        print("[%s] %s" % (rule["severity"].upper(), rule["id"]))
        print("  %s" % rule["title"])
        print("  affected: %s" % rule["affected"])
        print("  evidence: %s" % rule["evidence_url"])
        if rule.get("also"):
            print("  also: %s" % rule["also"])
        print()
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="guidelint",
        description="Preflight linter for structured-output / constrained-decoding configs.")
    parser.add_argument("--version", action="version", version="guidelint " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Lint a serve command or shell script.")
    p_check.add_argument("target", help="Shell script file or serve command string.")
    p_check.add_argument("--engine", default="vllm")
    p_check.add_argument("--engine-version", default=None,
                         help="e.g. 0.27.1 (enables version-scoped rules)")
    p_check.add_argument("--backend", default="xgrammar",
                         choices=backends.BACKENDS + ["unknown-backend"])
    p_check.add_argument("--schema", default=None, help="JSON Schema file to lint.")
    p_check.add_argument("--request-body", default=None,
                         help="JSON request-body file to lint.")
    p_check.add_argument("--json", action="store_true", help="Machine-readable output.")
    p_check.set_defaults(func=cmd_check)

    p_schema = sub.add_parser("schema", help="Lint a JSON Schema file alone.")
    p_schema.add_argument("schema", help="JSON Schema file.")
    p_schema.add_argument("--backend", default="xgrammar",
                          choices=backends.BACKENDS + ["unknown-backend"])
    p_schema.add_argument("--engine", default="vllm")
    p_schema.add_argument("--strict", action="store_true",
                          help="Also enforce strict-mode requirements.")
    p_schema.add_argument("--normalize-strict", action="store_true",
                          help="Print a strict-mode-conformant copy of the schema.")
    p_schema.add_argument("--json", action="store_true")
    p_schema.set_defaults(func=cmd_schema)

    p_matrix = sub.add_parser("matrix", help="Print the backend keyword-support matrix.")
    p_matrix.add_argument("--backend", default=None, choices=backends.BACKENDS)
    p_matrix.add_argument("--json", action="store_true")
    p_matrix.set_defaults(func=cmd_matrix)

    p_rules = sub.add_parser("rules", help="List the rule catalog.")
    p_rules.add_argument("--json", action="store_true")
    p_rules.set_defaults(func=cmd_rules)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
