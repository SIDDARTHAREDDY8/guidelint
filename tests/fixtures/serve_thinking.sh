#!/bin/bash
# enable_thinking=false silently bypasses xgrammar constrained decoding.
vllm serve Qwen/Qwen3-8B \
  --enable-thinking false \
  --guided-decoding-backend xgrammar \
  --reasoning-parser qwen3
