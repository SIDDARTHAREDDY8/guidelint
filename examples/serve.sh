#!/bin/bash
# Example serve script with two footguns for guidelint to find.
vllm serve Qwen/Qwen3-8B \
  --host 0.0.0.0 --port 8000 \
  --guided-json '{"type": "object", "properties": {"city": {"type": "string"}}}' \
  --enable-thinking false \
  --guided-decoding-backend xgrammar
