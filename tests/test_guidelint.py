"""Tests for guidelint. stdlib unittest only."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from guidelint import backends, parsers, strict
from guidelint import check as checker
from guidelint import report as report_mod
from guidelint.rules import RULES, RULE_INDEX

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def rule_ids(findings):
    return {f.rule_id for f in findings}


class TestParsers(unittest.TestCase):
    def test_parse_serve_command_flags(self):
        cmd = parsers.parse_serve_command(
            "vllm serve meta-llama/Llama-3.1-8B --guided-json '{\"type\": \"object\"}' "
            "--enable-thinking false --port 8000")
        self.assertEqual(cmd["engine"], "vllm")
        self.assertEqual(cmd["model"], "meta-llama/Llama-3.1-8B")
        self.assertEqual(cmd["flags"]["--guided-json"], '{"type": "object"}')
        self.assertEqual(cmd["flags"]["--enable-thinking"], "false")
        self.assertEqual(cmd["flags"]["--port"], "8000")

    def test_parse_serve_command_eq_syntax(self):
        cmd = parsers.parse_serve_command("vllm serve m --guided-decoding-backend=xgrammar")
        self.assertEqual(cmd["flags"]["--guided-decoding-backend"], "xgrammar")

    def test_parse_serve_script_continuations_and_comments(self):
        cmds = parsers.parse_serve_script(fixture("serve_legacy.sh"))
        self.assertEqual(len(cmds), 1)
        self.assertIn("--guided-json", cmds[0]["flags"])

    def test_parse_serve_script_skips_comments(self):
        cmds = parsers.parse_serve_script("# vllm serve fake-model\n\necho hi\n")
        self.assertEqual(cmds, [])

    def test_parse_request_body_surface(self):
        parsed = parsers.parse_request_body(fixture("body_legacy.json"))
        self.assertTrue(parsed["ok"])
        self.assertIn("guided_json", parsed["surface"]["legacy_guided"])
        self.assertEqual(parsed["surface"]["response_format"],
                         {"type": "json_object"})

    def test_parse_request_body_invalid(self):
        parsed = parsers.parse_request_body("{not json")
        self.assertFalse(parsed["ok"])

    def test_parse_request_body_unknown_fields(self):
        parsed = parsers.parse_request_body(fixture("body_unknown_fields.json"))
        self.assertTrue(parsed["ok"])
        self.assertIn("mystery_field", parsed["surface"]["unknown_fields"])

    def test_parse_schema_ok(self):
        parsed = parsers.parse_schema(fixture("schema_oneof.json"))
        self.assertTrue(parsed["ok"])
        self.assertIn("oneOf", backends.keywords_used(parsed["schema"]))


class TestRuleCatalog(unittest.TestCase):
    def test_minimum_rule_count(self):
        self.assertGreaterEqual(len(RULES), 20)

    def test_every_rule_has_required_fields(self):
        for rule in RULES:
            for field in ("id", "severity", "message", "evidence_url",
                          "affected", "fix"):
                self.assertIn(field, rule, "rule %s missing %s" % (rule.get("id"), field))
            self.assertIn(rule["severity"], ("error", "warn", "info"))
            self.assertTrue(rule["evidence_url"].startswith("http"))

    def test_rule_ids_unique(self):
        ids = [r["id"] for r in RULES]
        self.assertEqual(len(ids), len(set(ids)))


class TestServeChecks(unittest.TestCase):
    def test_guided_json_flag_fires_removal_error_on_new_vllm(self):
        cmds = parsers.parse_serve_script(fixture("serve_legacy.sh"))
        findings = checker.check_serve(cmds[0], engine="vllm",
                                       engine_version="0.27.1", backend="xgrammar")
        self.assertIn("vllm-guided-removed", rule_ids(findings))
        sev = {f.rule_id: f.severity for f in findings}
        self.assertEqual(sev["vllm-guided-removed"], "error")

    def test_guided_json_flag_no_error_on_old_vllm(self):
        cmds = parsers.parse_serve_script(fixture("serve_legacy.sh"))
        findings = checker.check_serve(cmds[0], engine="vllm",
                                       engine_version="0.11.0", backend="xgrammar")
        # still flags a migration note, but no silent-ignore error
        self.assertNotIn("vllm-guided-removed",
                         {f.rule_id for f in findings if f.severity == "error"})

    def test_enable_thinking_false_bypasses_xgrammar(self):
        cmds = parsers.parse_serve_script(fixture("serve_thinking.sh"))
        findings = checker.check_serve(cmds[0], engine="vllm",
                                       engine_version="0.27.1", backend="xgrammar")
        self.assertIn("vllm-thinking-xgrammar-bypass", rule_ids(findings))

    def test_specdecode_plus_xgrammar_errors(self):
        cmds = parsers.parse_serve_script(fixture("serve_specdecode.sh"))
        findings = checker.check_serve(cmds[0], engine="vllm",
                                       engine_version="0.27.1", backend="xgrammar")
        self.assertIn("xgrammar-specdecode", rule_ids(findings))
        sev = {f.rule_id: f.severity for f in findings}
        self.assertEqual(sev["xgrammar-specdecode"], "error")

    def test_clean_serve_command_has_no_errors(self):
        cmd = parsers.parse_serve_command(
            "vllm serve Qwen/Qwen3-8B --guided-decoding-backend xgrammar")
        findings = checker.check_serve(cmd, engine="vllm",
                                       engine_version="0.27.1", backend="xgrammar")
        self.assertFalse([f for f in findings if f.severity == "error"])

    def test_missing_engine_version_is_info(self):
        cmd = parsers.parse_serve_command("vllm serve Qwen/Qwen3-8B")
        findings = checker.check_serve(cmd, engine="vllm", engine_version=None,
                                       backend="xgrammar")
        self.assertIn("engine-version-unknown", rule_ids(findings))

    def test_unknown_backend_warns(self):
        cmd = parsers.parse_serve_command("vllm serve m --guided-decoding-backend frobnicate")
        findings = checker.check_serve(cmd, engine="vllm",
                                       engine_version="0.27.1", backend="frobnicate")
        self.assertIn("backend-unknown", rule_ids(findings))

    def test_invalid_regex_errors(self):
        cmd = parsers.parse_serve_command("vllm serve m --guided-regex '([a-z'")
        findings = checker.check_serve(cmd, engine="vllm",
                                       engine_version="0.27.1", backend="xgrammar")
        self.assertIn("regex-invalid", rule_ids(findings))

    def test_missing_grammar_file_errors(self):
        cmd = parsers.parse_serve_command("vllm serve m --guided-grammar /nope/missing.lark")
        findings = checker.check_serve(cmd, engine="vllm",
                                       engine_version="0.27.1", backend="xgrammar",
                                       workdir="/tmp")
        self.assertIn("grammar-file-missing", rule_ids(findings))


class TestBodyChecks(unittest.TestCase):
    def test_legacy_guided_field_in_body_errors_on_new_vllm(self):
        parsed = parsers.parse_request_body(fixture("body_legacy.json"))
        findings = checker.check_body(parsed["surface"], engine="vllm",
                                      engine_version="0.27.1", backend="xgrammar")
        self.assertIn("vllm-guided-removed", rule_ids(findings))

    def test_unknown_body_fields_warn(self):
        parsed = parsers.parse_request_body(fixture("body_unknown_fields.json"))
        findings = checker.check_body(parsed["surface"], engine="vllm",
                                      engine_version="0.27.1", backend="xgrammar")
        self.assertIn("unknown-body-fields", rule_ids(findings))

    def test_lenient_mode_warns(self):
        parsed = parsers.parse_request_body(fixture("body_lenient.json"))
        findings = checker.check_body(parsed["surface"], engine="vllm",
                                      engine_version="0.27.1", backend="xgrammar")
        self.assertIn("lenient-drop", rule_ids(findings))

    def test_json_object_response_format_warns(self):
        parsed = parsers.parse_request_body(fixture("body_legacy.json"))
        findings = checker.check_body(parsed["surface"], engine="vllm",
                                      engine_version="0.27.1", backend="xgrammar")
        self.assertIn("response-format-confusion", rule_ids(findings))

    def test_strict_schema_violations_flagged(self):
        parsed = parsers.parse_request_body(fixture("body_strict_bad.json"))
        findings = checker.check_body(parsed["surface"], engine="vllm",
                                      engine_version="0.27.1", backend="xgrammar")
        self.assertIn("strict-requirements", rule_ids(findings))
        details = " ".join(f.detail or "" for f in findings
                            if f.rule_id == "strict-requirements")
        self.assertIn("required", details)
        self.assertIn("default", details)

    def test_schema_not_wired_errors(self):
        parsed = parsers.parse_request_body(fixture("body_plain.json"))
        findings = checker.check_schema_wiring(parsed["surface"], schema_provided=True)
        self.assertIn("schema-not-wired", rule_ids(findings))

    def test_schema_wired_ok(self):
        parsed = parsers.parse_request_body(fixture("body_structured_outputs.json"))
        findings = checker.check_schema_wiring(parsed["surface"], schema_provided=True)
        self.assertNotIn("schema-not-wired", rule_ids(findings))


class TestSchemaChecks(unittest.TestCase):
    def test_oneof_on_unknown_backend_warns(self):
        parsed = parsers.parse_schema(fixture("schema_oneof.json"))
        findings = checker.check_schema(parsed["schema"], backend="ollama")
        self.assertIn("oneof-support", rule_ids(findings))

    def test_additional_properties_inconsistency(self):
        parsed = parsers.parse_schema(fixture("schema_strict_ok.json"))
        findings = checker.check_schema(parsed["schema"], backend="llama.cpp")
        self.assertIn("additional-properties-inconsistent", rule_ids(findings))

    def test_strict_mode_missing_required(self):
        parsed = parsers.parse_schema(fixture("schema_strict_bad.json"))
        violations = strict.check_strict(parsed["schema"])
        self.assertTrue(any("required" in v for v in violations))
        self.assertTrue(any("default" in v for v in violations))

    def test_normalize_strict_fixes_schema(self):
        parsed = parsers.parse_schema(fixture("schema_strict_bad.json"))
        fixed = strict.normalize_strict(parsed["schema"])
        self.assertEqual(strict.check_strict(fixed), [])
        self.assertEqual(sorted(fixed["required"]),
                         sorted(fixed["properties"].keys()))
        self.assertFalse(fixed["additionalProperties"])

    def test_keyword_support_gap_for_ignored_format(self):
        parsed = parsers.parse_schema(fixture("schema_format.json"))
        findings = checker.check_schema(parsed["schema"], backend="xgrammar")
        self.assertIn("keyword-support-gap", rule_ids(findings))


class TestBackends(unittest.TestCase):
    def test_matrix_has_all_backends(self):
        for b in ("xgrammar", "outlines", "guidance", "llguidance",
                  "llama.cpp", "ollama"):
            self.assertIn(b, backends.MATRIX)

    def test_support_values_valid(self):
        for b, kws in backends.MATRIX.items():
            for kw, level in kws.items():
                self.assertIn(level, backends.SUPPORT, (b, kw))

    def test_unknown_backend_is_unknown(self):
        self.assertEqual(backends.support("nope", "enum"), "unknown")

    def test_keywords_used_recursive(self):
        parsed = parsers.parse_schema(fixture("schema_oneof.json"))
        used = backends.keywords_used(parsed["schema"])
        self.assertIn("oneOf", used)
        self.assertIn("pattern", used)


class TestReport(unittest.TestCase):
    def test_exit_codes(self):
        self.assertEqual(report_mod.exit_code([]), 0)
        err = checker._finding("vllm-guided-removed")
        warn = checker._finding("unknown-body-fields")
        info = checker._finding("accuracy-cliffs")
        self.assertEqual(report_mod.exit_code([err, warn]), 1)
        self.assertEqual(report_mod.exit_code([warn]), 2)
        self.assertEqual(report_mod.exit_code([info]), 0)

    def test_json_report_has_evidence(self):
        f = checker._finding("vllm-guided-removed")
        data = json.loads(report_mod.json_report([f], "target"))
        self.assertEqual(data["findings"][0]["evidence"], f.evidence_url)
        self.assertIn("summary", data)

    def test_text_report_cites_evidence(self):
        f = checker._finding("xgrammar-specdecode")
        text = report_mod.text_report([f], "target")
        self.assertIn(f.evidence_url, text)
        self.assertIn("xgrammar-specdecode", text)


class TestCLI(unittest.TestCase):
    def run_cli(self, *argv):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "src"))
        return subprocess.run(
            [sys.executable, "-m", "guidelint"] + list(argv),
            capture_output=True, text=True, env=env, cwd="/tmp")

    def test_check_serve_script_exit_1(self):
        r = self.run_cli("check", os.path.join(FIXTURES, "serve_legacy.sh"),
                         "--engine-version", "0.27.1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("vllm-guided-removed", r.stdout)

    def test_check_clean_exit_0(self):
        r = self.run_cli("check", "vllm serve Qwen/Qwen3-8B",
                         "--engine-version", "0.27.1")
        self.assertEqual(r.returncode, 0)

    def test_check_json_output(self):
        r = self.run_cli("check", os.path.join(FIXTURES, "serve_legacy.sh"),
                         "--engine-version", "0.27.1", "--json")
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual(data["summary"]["errors"], 1)

    def test_schema_subcommand(self):
        r = self.run_cli("schema", os.path.join(FIXTURES, "schema_oneof.json"),
                         "--backend", "ollama")
        self.assertIn("oneof-support", r.stdout)

    def test_matrix_subcommand(self):
        r = self.run_cli("matrix")
        self.assertEqual(r.returncode, 0)
        self.assertIn("xgrammar", r.stdout)
        self.assertIn("additionalProperties", r.stdout)

    def test_rules_subcommand(self):
        r = self.run_cli("rules")
        self.assertEqual(r.returncode, 0)
        self.assertIn("vllm-guided-removed", r.stdout)

    def test_check_with_body_and_schema(self):
        r = self.run_cli("check", "vllm serve m", "--engine-version", "0.27.1",
                         "--request-body", os.path.join(FIXTURES, "body_legacy.json"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("vllm-guided-removed", r.stdout)


if __name__ == "__main__":
    unittest.main()
