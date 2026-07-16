#!/usr/bin/env bash
# Container entrypoint: runs the full CodeIQ pipeline via `make all`
# (clone -> extract -> graph -> describe -> index), so Docker and local
# runs are guaranteed to do the same thing.
#
# Configure via environment variables (all optional except GROQ_API_KEY
# when LLM=remote, which is the default):
#   REPO_OWNER / REPO_NAME / BRANCH  target GitHub repo
#   LLM                              "remote" (Groq) or "local" (LM Studio)
#   DESC_ARGS                        extra flags for the describe step,
#                                    e.g. "--num-files 10 --max-workers 4"
set -euo pipefail

if [ "${LLM:-remote}" = "remote" ] && [ -z "${GROQ_API_KEY:-}" ]; then
    echo "ERROR: GROQ_API_KEY is not set (required for LLM=remote)." >&2
    echo "Put it in .env (echo \"GROQ_API_KEY=...\" > .env) and rerun." >&2
    exit 1
fi

exec make all
