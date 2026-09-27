#!/usr/bin/env bash
# Download the two whisper.cpp models transcribe.py / qa_reel.py use, and verify their SHA-1 (whisper.cpp models README).
set -euo pipefail
DIR="${PICH_MODELS_DIR:-$HOME/.local/share/whisper-models}"
mkdir -p "$DIR"
fetch() {  # name sha1
  local f="$DIR/$1"
  if [ -f "$f" ] && [ "$(shasum -a 1 "$f" | cut -d' ' -f1)" = "$2" ]; then echo "ok   $1"; return; fi
  echo "get  $1"
  curl -L --fail --progress-bar -o "$f.part" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$1"
  [ "$(shasum -a 1 "$f.part" | cut -d' ' -f1)" = "$2" ] || { echo "SHA-1 mismatch for $1" >&2; rm -f "$f.part"; exit 1; }
  mv "$f.part" "$f"
}
fetch ggml-large-v3-turbo-q5_0.bin e050f7970618a659205450ad97eb95a18d69c9ee   # ~574 MB, primary
fetch ggml-medium.bin               fd9727b6e1217c2f614f9b698455c4ffd82463b4   # ~1.5 GB, cross-check
echo "models in $DIR"
