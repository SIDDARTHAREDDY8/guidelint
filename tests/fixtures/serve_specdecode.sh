#!/bin/bash
# xgrammar + speculative decoding: deterministic failures.
vllm serve meta-llama/Llama-3.1-8B-Instruct \
  --guided-decoding-backend xgrammar \
  --speculative-model meta-llama/Llama-3.1-8B-Instruct \
  --num-speculative-tokens 5
