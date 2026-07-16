#!/usr/bin/env bash
# Deploy container entrypoint (docker/Dockerfile.deploy): for each repo the
# app serves (kept in sync with REPOS in app/app.py), clone its raw source
# and rebuild the ChromaDB vector index from the entities/edges already
# committed to data/processed/ -- then start the Shiny app.
#
# No `make all`: extract/graph/describe never run here, so no Node.js and no
# LLM calls at deploy time. Runs on every container start, since a fresh
# image-backed deploy (and Render's free-plan disk) doesn't persist
# data/raw or data/processed/*/chroma between runs.
set -euo pipefail

clone_and_index() {
    local owner="$1" name="$2" branch="$3"
    local tag="${owner}_${name}_${branch}"

    echo "--- ${tag}: cloning raw source ---"
    REPO_OWNER="$owner" REPO_NAME="$name" BRANCH="$branch" \
        python src/clone_raw/clone_raw.py

    echo "--- ${tag}: building vector index ---"
    python src/vector_index/build_index.py --tag "$tag"
}

# Default repo is configurable via REPO_OWNER/REPO_NAME/BRANCH (matches
# src/clone_raw/clone_raw.py's own defaults); the second repo is the one
# hardcoded in REPOS in app/app.py.
clone_and_index "${REPO_OWNER:-bluesky-social}" "${REPO_NAME:-social-app}" "${BRANCH:-main}"
clone_and_index "raysk4ever" "Simple-React-Native-App" "main"

exec shiny run --host 0.0.0.0 --port "${PORT:-8000}" app/app.py
