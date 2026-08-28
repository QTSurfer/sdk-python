#!/usr/bin/env bash
# Build the browsable high-level SDK docs (pdoc) into docs/.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv run pdoc -o docs qtsurfer_sdk
