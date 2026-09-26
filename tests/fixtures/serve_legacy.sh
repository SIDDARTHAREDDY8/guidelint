#!/bin/bash
# Legacy serve script: guided_json was removed in vLLM v0.12.0.
vllm serve Qwen/Qwen3-8B \
  --host 0.0.0.0 --port 8000 \
  --guided-json '{"type": "object", "properties": {"city": {"type": "string"}}}' \
  --guided-decoding-backend xgrammar
