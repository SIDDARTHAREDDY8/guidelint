"""Version-aware rule database.

Every rule carries: id, severity, message, evidence_url, affected (engines/versions),
and fix. Evidence URLs come from real issues/blog posts found during research —
never invented. Rules that encode best practice rather than an issue get severity
"info" and a docs link as evidence.
"""

EVIDENCE = {
    "aiclearinghouse": "https://github.com/smfworks/aiclearinghouse-site/blob/HEAD/content/blog/grammar-constrained-generation-local-agent-structured-output.md",
    "mattniedelman_skill": "https://github.com/mattniedelman/dotfiles/blob/HEAD/dot_claude/skills/inference-structured-decoding/SKILL.md",
    "kafkaexplorer_audit": "https://github.com/devdownin/kafkaexplorer/blob/HEAD/PROCESS-MINING-LLM-CALLS-AUDIT.md",
    "smlcode_doctor": "https://github.com/unicolab/smlcode/blob/HEAD/docs/decoding.md",
    "arbiter_82": "https://github.com/alisalman-et-al/arbiter/issues/82",
    "vllm_course_notes": "https://github.com/akgaur12/developer-notes/blob/HEAD/AI-ML/vllm-course/16-structured-outputs-and-tool-calling.md",
    "ji_ai_trap": "https://dev.to/ji_ai/json-mode-makes-your-llm-dumber-the-constrained-decoding-trap-cp",
    "vllm_49460": "https://github.com/vllm-project/vllm/issues/49460",
    "jscott_gotchas": "https://github.com/jscott3201/model-tuning/blob/HEAD/01_serve/vllm/README.md",
    "rtx3090_gotchas": "https://github.com/0x7067/rtx3090-llm-lab/blob/HEAD/vllm/syv-ai/docs/gotchas.md",
    "compasify_digest": "https://github.com/compasify/agents-radar/blob/HEAD/digests/2026-09-12/ai-infra-en.md",
    "openai_structured_outputs": "https://platform.openai.com/docs/guides/structured-outputs",
    "xgrammar_docs": "https://xgrammar.mlc.ai/docs/index.html",
    "ollama_api_docs": "https://github.com/ollama/ollama/blob/main/docs/api.md",
    "vllm_structured_outputs": "https://docs.vllm.ai/en/latest/features/structured_outputs/",
}

RULES = [
    {
        "id": "vllm-guided-removed",
        "severity": "error",
        "title": "guided_* fields removed in vLLM v0.12.0 — silently ignored",
        "message": "The legacy request/serve fields guided_json, guided_regex, guided_choice and "
                   "guided_grammar were removed in vLLM v0.12.0. Against a current vLLM server they "
                   "do not raise an error — they are simply ignored — so the failure mode is a "
                   "silently unconstrained completion, not a clean exception.",
        "evidence_url": EVIDENCE["mattniedelman_skill"],
        "also": EVIDENCE["vllm_course_notes"],
        "affected": "vllm >= 0.12.0",
        "fix": "Use structured_outputs instead, e.g. structured_outputs={\"json\": <schema>} or "
               "structured_outputs={\"regex\": \"...\"}. Remove every guided_* field/flag.",
    },
    {
        "id": "vllm-thinking-xgrammar-bypass",
        "severity": "warn",
        "title": "enable_thinking=false silently bypasses xgrammar",
        "message": "With enable_thinking=false, constrained decoding via xgrammar is silently "
                   "bypassed — the request completes without the schema being enforced.",
        "evidence_url": EVIDENCE["jscott_gotchas"],
        "affected": "vllm (thinking models) + xgrammar",
        "fix": "If you need constrained decoding, keep thinking enabled or verify the grammar "
               "actually constrains output with an invalid-value probe before relying on it.",
    },
    {
        "id": "lenient-drop",
        "severity": "warn",
        "title": "'lenient' mode silently drops unsupported schema keywords",
        "message": "In lenient/best-effort mode, an unsupported schema keyword does not error — "
                   "it is dropped silently, and the output is less constrained than you think.",
        "evidence_url": EVIDENCE["mattniedelman_skill"],
        "affected": "structured-output providers with lenient parsing",
        "fix": "Lint the schema with the target backend's keyword matrix first "
               "(guidelint schema --backend <name>), and prefer strict mode where supported.",
    },
    {
        "id": "strict-unhonored-proxy",
        "severity": "warn",
        "title": "strict:true sent to a server that cannot honor it — silent demotion to prompt_only",
        "message": "Common causes of a silent demotion to prompt_only: an OpenAI-compatible proxy "
                   "that returns 400 for unknown body fields, or a model whose server advertises "
                   "json_schema but rejects strict:true. Nothing in the response distinguishes "
                   "this from a run where the schema was in force.",
        "evidence_url": EVIDENCE["smlcode_doctor"],
        "also": EVIDENCE["kafkaexplorer_audit"],
        "affected": "any OpenAI-compatible server / proxy",
        "fix": "Probe the target server: send a schema with strict:true and confirm invalid "
               "values are rejected. If the proxy 400s on the field, strip it and pin the "
               "server version.",
    },
    {
        "id": "strict-requirements",
        "severity": "error",
        "title": "strict:true schema violates strict-mode requirements",
        "message": "Strict mode requires that every property be listed in required and forbids "
                   "the default keyword. An invalid strict schema may be silently accepted and "
                   "effectively ignored (best-effort JSON, no real constraint).",
        "evidence_url": EVIDENCE["arbiter_82"],
        "affected": "strict-mode structured outputs (OpenAI-compatible)",
        "fix": "Add every property to required, remove default, and set "
               "additionalProperties:false.",
    },
    {
        "id": "unknown-body-fields",
        "severity": "warn",
        "title": "Unknown fields in an OpenAI-compatible request body",
        "message": "Unknown body fields are silently ignored by most servers — but some "
                   "OpenAI-compatible proxies return 400 for them. Either way, the field you "
                   "think is doing work may not be.",
        "evidence_url": EVIDENCE["smlcode_doctor"],
        "affected": "any OpenAI-compatible server / proxy",
        "fix": "Remove unknown fields, or route through a proxy you control that forwards them.",
    },
    {
        "id": "response-format-confusion",
        "severity": "warn",
        "title": "response_format json_object does not enforce a schema",
        "message": "response_format {\"type\": \"json_object\"} asks for valid JSON but enforces "
                   "no schema — use json_schema with strict:true when you need a contract.",
        "evidence_url": EVIDENCE["openai_structured_outputs"],
        "affected": "OpenAI-compatible APIs",
        "fix": "Switch to response_format {\"type\": \"json_schema\", \"json_schema\": {...}}.",
    },
    {
        "id": "accuracy-cliffs",
        "severity": "info",
        "title": "JSON mode can create accuracy cliffs",
        "message": "Constrained decoding changes the token distribution; required fields can "
                   "manufacture hallucinations where the unconstrained model would have said "
                   "'I don't know'. Measure accuracy with and without the constraint.",
        "evidence_url": EVIDENCE["ji_ai_trap"],
        "affected": "any constrained-decoding setup",
        "fix": "Benchmark task accuracy with constraints on vs off; keep constraints minimal.",
    },
    {
        "id": "field-order-leak",
        "severity": "info",
        "title": "Schema field order is a prompt",
        "message": "Field order in the schema biases generation order and can leak prompt "
                   "content. Order fields deliberately; put low-sensitivity fields first.",
        "evidence_url": EVIDENCE["ji_ai_trap"],
        "affected": "any constrained-decoding setup",
        "fix": "Review the property order in your schema as you would review prompt wording.",
    },
    {
        "id": "additional-properties-inconsistent",
        "severity": "warn",
        "title": "additionalProperties:false honored by some grammar compilers, ignored by others",
        "message": "The same schema can be strict on one backend and permissive on another — "
                   "extra keys may pass on backends that ignore additionalProperties.",
        "evidence_url": EVIDENCE["aiclearinghouse"],
        "affected": "xgrammar, outlines, guidance, llguidance, llama.cpp, ollama (varies)",
        "fix": "Validate outputs against the schema in your application code regardless of "
               "backend; run guidelint matrix to see per-backend support.",
    },
    {
        "id": "oneof-support",
        "severity": "warn",
        "title": "oneOf/anyOf support varies by backend",
        "message": "oneOf/anyOf are enforced by some backends and silently weakened by others, "
                   "so union branches may not actually be constrained.",
        "evidence_url": EVIDENCE["aiclearinghouse"],
        "affected": "guidance, llama.cpp, ollama (conservative: unknown)",
        "fix": "Check guidelint matrix for your backend; prefer a single-shape schema or "
               "validate branches in application code.",
    },
    {
        "id": "schema-grammar-drift",
        "severity": "warn",
        "title": "Schema-to-grammar conversion is not 1:1",
        "message": "The compiled grammar is the real contract, not the schema. A backend update "
                   "can rewrite the schema-to-grammar path and silently stop constraining a "
                   "field you relied on.",
        "evidence_url": EVIDENCE["aiclearinghouse"],
        "affected": "ollama (documented drift), any grammar-compiling backend",
        "fix": "Pin the backend/engine version and re-probe constraints (invalid-value "
               "rejection) after every upgrade.",
    },
    {
        "id": "xgrammar-specdecode",
        "severity": "error",
        "title": "xgrammar + speculative decoding fails deterministically",
        "message": "Running xgrammar constrained decoding together with speculative decoding "
                   "(e.g. DFlash2-style draft models) kills valid requests — expect deterministic "
                   "failures until the underlying issue is resolved.",
        "evidence_url": EVIDENCE["rtx3090_gotchas"],
        "also": EVIDENCE["compasify_digest"],
        "affected": "vllm + xgrammar + speculative decoding",
        "fix": "Disable speculative decoding (--speculative-model) while using structured "
               "outputs with xgrammar.",
    },
    {
        "id": "threadpool-starvation",
        "severity": "warn",
        "title": "StructuredOutputManager thread pool is CPU-starved on K8s",
        "message": "vLLM's StructuredOutputManager thread pool is cgroup-unaware: under CPU "
                   "limits on Kubernetes, decode latency p99 can jump ~20x while the GPU idles — "
                   "pure CPU starvation in grammar compilation.",
        "evidence_url": EVIDENCE["vllm_49460"],
        "affected": "vllm structured outputs on CPU-limited K8s pods",
        "fix": "Raise the pod CPU limit/request, reduce concurrent structured-output requests, "
               "or precompile grammars; track upstream issue #49460 for the fix.",
    },
    {
        "id": "pad-token-leak",
        "severity": "warn",
        "title": "<pad> token leaks under concurrent tool calls",
        "message": "Under concurrent tool-calling load, <pad> tokens can leak into structured "
                   "outputs, corrupting JSON parses downstream.",
        "evidence_url": EVIDENCE["jscott_gotchas"],
        "affected": "vllm tool calling (concurrent)",
        "fix": "Strip <pad> tokens defensively before json.loads, and serialize or "
               "rate-limit concurrent tool-call batches.",
    },
    {
        "id": "schema-not-wired",
        "severity": "error",
        "title": "Schema provided but not referenced by the request",
        "message": "A --schema was given but the request body contains no structured_outputs / "
                   "response_format.json_schema field, so the schema is never sent to the server.",
        "evidence_url": EVIDENCE["kafkaexplorer_audit"],
        "affected": "any",
        "fix": "Wire the schema into the request: response_format {\"type\": \"json_schema\", "
               "\"json_schema\": {...}} or structured_outputs={\"json\": ...}.",
    },
    {
        "id": "grammar-file-missing",
        "severity": "error",
        "title": "Grammar file referenced but missing",
        "message": "The serve command references a grammar file that does not exist on disk — "
                   "the server will fail at startup or fall back silently depending on the engine.",
        "evidence_url": EVIDENCE["vllm_structured_outputs"],
        "affected": "vllm --guided-grammar / structured_outputs grammar paths",
        "fix": "Ship the grammar file alongside the serve script, or inline the grammar.",
    },
    {
        "id": "regex-invalid",
        "severity": "error",
        "title": "Invalid regex in structured-output config",
        "message": "The guided_regex / structured_outputs regex does not compile — the server "
                   "will reject the config or the constraint will never hold.",
        "evidence_url": EVIDENCE["vllm_structured_outputs"],
        "affected": "any regex-based constrained decoding",
        "fix": "Test the regex with a plain re.compile before deploying it.",
    },
    {
        "id": "choice-empty",
        "severity": "warn",
        "title": "Empty guided_choice list",
        "message": "guided_choice with an empty list constrains the model to produce nothing — "
                   "requests will fail or hang.",
        "evidence_url": EVIDENCE["vllm_structured_outputs"],
        "affected": "vllm guided_choice",
        "fix": "Provide at least one choice, or drop guided_choice.",
    },
    {
        "id": "keyword-support-gap",
        "severity": "warn",
        "title": "Schema uses keywords the backend ignores or may ignore",
        "message": "The schema uses JSON-Schema keywords that this backend ignores or whose "
                   "support is unknown — those constraints will not be enforced.",
        "evidence_url": EVIDENCE["aiclearinghouse"],
        "affected": "varies by backend (see guidelint matrix)",
        "fix": "Rewrite the schema using only honored keywords, or validate outputs in "
               "application code.",
    },
    {
        "id": "backend-unknown",
        "severity": "warn",
        "title": "Unknown guided-decoding backend",
        "message": "The configured backend is not in guidelint's keyword-support matrix, so "
                   "keyword enforcement cannot be verified.",
        "evidence_url": EVIDENCE["xgrammar_docs"],
        "affected": "any",
        "fix": "Use one of xgrammar, outlines, guidance, llguidance, llama.cpp, ollama — or "
               "verify keyword support against that backend's docs.",
    },
    {
        "id": "engine-version-unknown",
        "severity": "info",
        "title": "Engine version unknown — version-scoped rules skipped",
        "message": "No --engine-version was given, so rules scoped to engine versions (e.g. the "
                   "vLLM v0.12.0 guided_* removal) were not applied. Findings may be incomplete.",
        "evidence_url": EVIDENCE["vllm_course_notes"],
        "affected": "any",
        "fix": "Pass --engine-version, e.g. --engine-version 0.27.1.",
    },
    {
        "id": "strict-docs-best-practice",
        "severity": "info",
        "title": "Strict mode is only as good as the server's enforcement",
        "message": "Some endpoints silently accept invalid strict schemas and fall back to "
                   "best-effort JSON with no real constraint — strict:true in your request is a "
                   "hint, not a guarantee, until you probe the server.",
        "evidence_url": EVIDENCE["arbiter_82"],
        "affected": "strict-mode structured outputs",
        "fix": "Send an intentionally invalid value and confirm the server rejects it.",
    },
]

RULE_INDEX = {rule["id"]: rule for rule in RULES}
