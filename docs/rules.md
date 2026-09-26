# guidelint rule catalog

Every rule carries an evidence link — the real issue or writeup the rule
was built from. `affected` scopes the rule to engines/versions.

## grammar-file-missing  [ERROR]

Grammar file referenced but missing.

The serve command references a grammar file that does not exist on disk — the server will fail at startup or fall back silently depending on the engine.

- **Affected:** vllm --guided-grammar / structured_outputs grammar paths
- **Fix:** Ship the grammar file alongside the serve script, or inline the grammar.
- **Evidence:** https://docs.vllm.ai/en/latest/features/structured_outputs/

## regex-invalid  [ERROR]

Invalid regex in structured-output config.

The guided_regex / structured_outputs regex does not compile — the server will reject the config or the constraint will never hold.

- **Affected:** any regex-based constrained decoding
- **Fix:** Test the regex with a plain re.compile before deploying it.
- **Evidence:** https://docs.vllm.ai/en/latest/features/structured_outputs/

## schema-not-wired  [ERROR]

Schema provided but not referenced by the request.

A --schema was given but the request body contains no structured_outputs / response_format.json_schema field, so the schema is never sent to the server.

- **Affected:** any
- **Fix:** Wire the schema into the request: response_format {"type": "json_schema", "json_schema": {...}} or structured_outputs={"json": ...}.
- **Evidence:** https://github.com/devdownin/kafkaexplorer/blob/HEAD/PROCESS-MINING-LLM-CALLS-AUDIT.md

## strict-requirements  [ERROR]

strict:true schema violates strict-mode requirements.

Strict mode requires that every property be listed in required and forbids the default keyword. An invalid strict schema may be silently accepted and effectively ignored (best-effort JSON, no real constraint).

- **Affected:** strict-mode structured outputs (OpenAI-compatible)
- **Fix:** Add every property to required, remove default, and set additionalProperties:false.
- **Evidence:** https://github.com/alisalman-et-al/arbiter/issues/82

## vllm-guided-removed  [ERROR]

guided_* fields removed in vLLM v0.12.0 — silently ignored.

The legacy request/serve fields guided_json, guided_regex, guided_choice and guided_grammar were removed in vLLM v0.12.0. Against a current vLLM server they do not raise an error — they are simply ignored — so the failure mode is a silently unconstrained completion, not a clean exception.

- **Affected:** vllm >= 0.12.0
- **Fix:** Use structured_outputs instead, e.g. structured_outputs={"json": <schema>} or structured_outputs={"regex": "..."}. Remove every guided_* field/flag.
- **Evidence:** https://github.com/mattniedelman/dotfiles/blob/HEAD/dot_claude/skills/inference-structured-decoding/SKILL.md
- **Also:** https://github.com/akgaur12/developer-notes/blob/HEAD/AI-ML/vllm-course/16-structured-outputs-and-tool-calling.md

## xgrammar-specdecode  [ERROR]

xgrammar + speculative decoding fails deterministically.

Running xgrammar constrained decoding together with speculative decoding (e.g. DFlash2-style draft models) kills valid requests — expect deterministic failures until the underlying issue is resolved.

- **Affected:** vllm + xgrammar + speculative decoding
- **Fix:** Disable speculative decoding (--speculative-model) while using structured outputs with xgrammar.
- **Evidence:** https://github.com/0x7067/rtx3090-llm-lab/blob/HEAD/vllm/syv-ai/docs/gotchas.md
- **Also:** https://github.com/compasify/agents-radar/blob/HEAD/digests/2026-09-12/ai-infra-en.md

## additional-properties-inconsistent  [WARN]

additionalProperties:false honored by some grammar compilers, ignored by others.

The same schema can be strict on one backend and permissive on another — extra keys may pass on backends that ignore additionalProperties.

- **Affected:** xgrammar, outlines, guidance, llguidance, llama.cpp, ollama (varies)
- **Fix:** Validate outputs against the schema in your application code regardless of backend; run guidelint matrix to see per-backend support.
- **Evidence:** https://github.com/smfworks/aiclearinghouse-site/blob/HEAD/content/blog/grammar-constrained-generation-local-agent-structured-output.md

## backend-unknown  [WARN]

Unknown guided-decoding backend.

The configured backend is not in guidelint's keyword-support matrix, so keyword enforcement cannot be verified.

- **Affected:** any
- **Fix:** Use one of xgrammar, outlines, guidance, llguidance, llama.cpp, ollama — or verify keyword support against that backend's docs.
- **Evidence:** https://xgrammar.mlc.ai/docs/index.html

## choice-empty  [WARN]

Empty guided_choice list.

guided_choice with an empty list constrains the model to produce nothing — requests will fail or hang.

- **Affected:** vllm guided_choice
- **Fix:** Provide at least one choice, or drop guided_choice.
- **Evidence:** https://docs.vllm.ai/en/latest/features/structured_outputs/

## keyword-support-gap  [WARN]

Schema uses keywords the backend ignores or may ignore.

The schema uses JSON-Schema keywords that this backend ignores or whose support is unknown — those constraints will not be enforced.

- **Affected:** varies by backend (see guidelint matrix)
- **Fix:** Rewrite the schema using only honored keywords, or validate outputs in application code.
- **Evidence:** https://github.com/smfworks/aiclearinghouse-site/blob/HEAD/content/blog/grammar-constrained-generation-local-agent-structured-output.md

## lenient-drop  [WARN]

'lenient' mode silently drops unsupported schema keywords.

In lenient/best-effort mode, an unsupported schema keyword does not error — it is dropped silently, and the output is less constrained than you think.

- **Affected:** structured-output providers with lenient parsing
- **Fix:** Lint the schema with the target backend's keyword matrix first (guidelint schema --backend <name>), and prefer strict mode where supported.
- **Evidence:** https://github.com/mattniedelman/dotfiles/blob/HEAD/dot_claude/skills/inference-structured-decoding/SKILL.md

## oneof-support  [WARN]

oneOf/anyOf support varies by backend.

oneOf/anyOf are enforced by some backends and silently weakened by others, so union branches may not actually be constrained.

- **Affected:** guidance, llama.cpp, ollama (conservative: unknown)
- **Fix:** Check guidelint matrix for your backend; prefer a single-shape schema or validate branches in application code.
- **Evidence:** https://github.com/smfworks/aiclearinghouse-site/blob/HEAD/content/blog/grammar-constrained-generation-local-agent-structured-output.md

## pad-token-leak  [WARN]

<pad> token leaks under concurrent tool calls.

Under concurrent tool-calling load, <pad> tokens can leak into structured outputs, corrupting JSON parses downstream.

- **Affected:** vllm tool calling (concurrent)
- **Fix:** Strip <pad> tokens defensively before json.loads, and serialize or rate-limit concurrent tool-call batches.
- **Evidence:** https://github.com/jscott3201/model-tuning/blob/HEAD/01_serve/vllm/README.md

## response-format-confusion  [WARN]

response_format json_object does not enforce a schema.

response_format {"type": "json_object"} asks for valid JSON but enforces no schema — use json_schema with strict:true when you need a contract.

- **Affected:** OpenAI-compatible APIs
- **Fix:** Switch to response_format {"type": "json_schema", "json_schema": {...}}.
- **Evidence:** https://platform.openai.com/docs/guides/structured-outputs

## schema-grammar-drift  [WARN]

Schema-to-grammar conversion is not 1:1.

The compiled grammar is the real contract, not the schema. A backend update can rewrite the schema-to-grammar path and silently stop constraining a field you relied on.

- **Affected:** ollama (documented drift), any grammar-compiling backend
- **Fix:** Pin the backend/engine version and re-probe constraints (invalid-value rejection) after every upgrade.
- **Evidence:** https://github.com/smfworks/aiclearinghouse-site/blob/HEAD/content/blog/grammar-constrained-generation-local-agent-structured-output.md

## strict-unhonored-proxy  [WARN]

strict:true sent to a server that cannot honor it — silent demotion to prompt_only.

Common causes of a silent demotion to prompt_only: an OpenAI-compatible proxy that returns 400 for unknown body fields, or a model whose server advertises json_schema but rejects strict:true. Nothing in the response distinguishes this from a run where the schema was in force.

- **Affected:** any OpenAI-compatible server / proxy
- **Fix:** Probe the target server: send a schema with strict:true and confirm invalid values are rejected. If the proxy 400s on the field, strip it and pin the server version.
- **Evidence:** https://github.com/unicolab/smlcode/blob/HEAD/docs/decoding.md
- **Also:** https://github.com/devdownin/kafkaexplorer/blob/HEAD/PROCESS-MINING-LLM-CALLS-AUDIT.md

## threadpool-starvation  [WARN]

StructuredOutputManager thread pool is CPU-starved on K8s.

vLLM's StructuredOutputManager thread pool is cgroup-unaware: under CPU limits on Kubernetes, decode latency p99 can jump ~20x while the GPU idles — pure CPU starvation in grammar compilation.

- **Affected:** vllm structured outputs on CPU-limited K8s pods
- **Fix:** Raise the pod CPU limit/request, reduce concurrent structured-output requests, or precompile grammars; track upstream issue #49460 for the fix.
- **Evidence:** https://github.com/vllm-project/vllm/issues/49460

## unknown-body-fields  [WARN]

Unknown fields in an OpenAI-compatible request body.

Unknown body fields are silently ignored by most servers — but some OpenAI-compatible proxies return 400 for them. Either way, the field you think is doing work may not be.

- **Affected:** any OpenAI-compatible server / proxy
- **Fix:** Remove unknown fields, or route through a proxy you control that forwards them.
- **Evidence:** https://github.com/unicolab/smlcode/blob/HEAD/docs/decoding.md

## vllm-thinking-xgrammar-bypass  [WARN]

enable_thinking=false silently bypasses xgrammar.

With enable_thinking=false, constrained decoding via xgrammar is silently bypassed — the request completes without the schema being enforced.

- **Affected:** vllm (thinking models) + xgrammar
- **Fix:** If you need constrained decoding, keep thinking enabled or verify the grammar actually constrains output with an invalid-value probe before relying on it.
- **Evidence:** https://github.com/jscott3201/model-tuning/blob/HEAD/01_serve/vllm/README.md

## accuracy-cliffs  [INFO]

JSON mode can create accuracy cliffs.

Constrained decoding changes the token distribution; required fields can manufacture hallucinations where the unconstrained model would have said 'I don't know'. Measure accuracy with and without the constraint.

- **Affected:** any constrained-decoding setup
- **Fix:** Benchmark task accuracy with constraints on vs off; keep constraints minimal.
- **Evidence:** https://dev.to/ji_ai/json-mode-makes-your-llm-dumber-the-constrained-decoding-trap-cp

## engine-version-unknown  [INFO]

Engine version unknown — version-scoped rules skipped.

No --engine-version was given, so rules scoped to engine versions (e.g. the vLLM v0.12.0 guided_* removal) were not applied. Findings may be incomplete.

- **Affected:** any
- **Fix:** Pass --engine-version, e.g. --engine-version 0.27.1.
- **Evidence:** https://github.com/akgaur12/developer-notes/blob/HEAD/AI-ML/vllm-course/16-structured-outputs-and-tool-calling.md

## field-order-leak  [INFO]

Schema field order is a prompt.

Field order in the schema biases generation order and can leak prompt content. Order fields deliberately; put low-sensitivity fields first.

- **Affected:** any constrained-decoding setup
- **Fix:** Review the property order in your schema as you would review prompt wording.
- **Evidence:** https://dev.to/ji_ai/json-mode-makes-your-llm-dumber-the-constrained-decoding-trap-cp

## strict-docs-best-practice  [INFO]

Strict mode is only as good as the server's enforcement.

Some endpoints silently accept invalid strict schemas and fall back to best-effort JSON with no real constraint — strict:true in your request is a hint, not a guarantee, until you probe the server.

- **Affected:** strict-mode structured outputs
- **Fix:** Send an intentionally invalid value and confirm the server rejects it.
- **Evidence:** https://github.com/alisalman-et-al/arbiter/issues/82
