# guidelint

**shellcheck for your structured-output / constrained-decoding config.**

Constrained decoding is the #1 silent-failure surface in LLM serving. Removed API
fields get *silently ignored*, `enable_thinking=false` *silently bypasses* the
grammar, "lenient" modes *silently drop* unsupported schema keywords, and the same
schema is strict on one backend and permissive on another. Engineers discover each
of these in production.

`guidelint` is a zero-dependency Python CLI that lints your vLLM / llama.cpp /
Ollama serve configs, request bodies, and JSON Schemas against a version-aware
rule database — every rule cites the real GitHub issue or writeup it came from.

## Install

```bash
pip install git+https://github.com/SIDDARTHAREDDY8/guidelint
```

No dependencies. Python 3.9+.

## 60-second example

```bash
# your serve script still passes the removed guided_json flag
$ cat serve.sh
vllm serve Qwen/Qwen3-8B --guided-json '{"type":"object"}'

$ guidelint check serve.sh --engine vllm --engine-version 0.27.1 --backend xgrammar

guidelint: serve.sh

[ERROR] vllm-guided-removed (serve flag --guided-json)
  The legacy request/serve fields guided_json, guided_regex, guided_choice and
  guided_grammar were removed in vLLM v0.12.0. Against a current vLLM server they
  do not raise an error — they are simply ignored — so the failure mode is a
  silently unconstrained completion, not a clean exception.
  fix: Use structured_outputs instead, e.g. structured_outputs={"json": <schema>}
  or structured_outputs={"regex": "..."}. Remove every guided_* field/flag.
  evidence: https://github.com/mattniedelman/dotfiles/blob/HEAD/dot_claude/skills/inference-structured-decoding/SKILL.md

summary: 1 error(s), 0 warning(s), 0 info note(s)
```

Exit codes are CI-friendly: `0` = clean, `1` = errors found, `2` = warnings only.

## Commands

```bash
# lint a serve command or shell script (+ optional request body and schema)
guidelint check serve.sh --engine vllm --engine-version 0.27.1 \
    --backend xgrammar --schema tool.json --request-body body.json

# lint a JSON Schema alone against a backend's keyword matrix
guidelint schema --backend ollama tool.json
guidelint schema --backend xgrammar tool.json --strict   # enforce strict-mode rules

# rewrite a schema to satisfy strict mode (all props required, no default)
guidelint schema --backend xgrammar tool.json --normalize-strict > strict_tool.json

# print the backend keyword-support matrix
guidelint matrix
guidelint matrix --backend llama.cpp --json

# list every rule with its evidence link
guidelint rules

# machine-readable output for CI
guidelint check serve.sh --engine-version 0.27.1 --json
```

## What it catches

23 rules across five families — serve-flag footguns (removed `guided_*` fields,
xgrammar + speculative decoding, `enable_thinking=false` bypass), request-body
footguns (unknown body fields, lenient mode, `json_object` vs `json_schema`
confusion), schema/backend mismatches (oneOf/additionalProperties support gaps,
schema-to-grammar drift), strict-mode violations, and informational notes
(accuracy cliffs, field-order leakage). Full catalog: [docs/rules.md](docs/rules.md).

## The keyword matrix

`guidelint matrix` shows, per backend (xgrammar, outlines, guidance, llguidance,
llama.cpp, ollama), which JSON-Schema keywords are **honored**, **ignored**,
**error**, or **unknown**. The matrix is deliberately conservative: anything
unverified is `unknown`, never invented. The compiled grammar is the real
contract — your schema is not.

## CI

```yaml
- run: pip install git+https://github.com/SIDDARTHAREDDY8/guidelint
- run: guidelint check serve.sh --engine vllm --engine-version 0.27.1 --backend xgrammar
```

## Development

```bash
git clone https://github.com/SIDDARTHAREDDY8/guidelint && cd guidelint
PYTHONPATH=src python -m unittest discover -s tests   # 46 tests, stdlib only
```

## License

MIT.
