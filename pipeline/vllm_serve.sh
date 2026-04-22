#!/usr/bin/env bash
# vllm_serve.sh — launch vLLM OpenAI-compatible server for gpt-oss-120b on a RunPod 2xH200 box.
# Usage: ./vllm_serve.sh gptoss120b
set -euo pipefail

PROFILE="${1:-gptoss120b}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.92}"
HF_HOME="${HF_HOME:-/workspace/hf_cache}"
export HF_HOME
mkdir -p "$HF_HOME"

if [[ -n "${HUGGING_FACE_HUB_TOKEN:-}" ]]; then
  export HF_TOKEN="$HUGGING_FACE_HUB_TOKEN"
fi

case "$PROFILE" in
  gptoss120b)
    MODEL="${MODEL:-openai/gpt-oss-120b}"
    DTYPE="${DTYPE:-auto}"
    TP="${TP:-2}"
    ;;
  *)
    echo "Unknown profile: $PROFILE"; exit 1;;
esac

echo "==============================================================="
echo " vLLM profile:        $PROFILE"
echo " Model:               $MODEL"
echo " Tensor parallel:     $TP"
echo " Max model length:    $MAX_MODEL_LEN"
echo " GPU mem utilization: $GPU_MEM_UTIL"
echo " Port:                $PORT"
echo " HF cache:            $HF_HOME"
echo "==============================================================="

exec python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" \
  --served-model-name "$PROFILE" \
  --tensor-parallel-size "$TP" \
  --dtype "$DTYPE" \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-num-seqs 64 \
  --gpu-memory-utilization "$GPU_MEM_UTIL" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --structured-outputs-config '{"backend": "xgrammar"}' \
  --trust-remote-code
