#!/usr/bin/env python3
"""
deploy_to_render.py

Syncs GROQ_API_KEY(s) to the Render web service's environment variables and
triggers a deploy. Run from the repo root by the "Build, Push & Deploy"
workflow (.github/workflows/publish.yml), after that workflow has already
built the Dockerfile itself and pushed the resulting image to GHCR.

The Render service is image-backed (see render.yaml), so Render never reads
the Dockerfile or builds anything — it only pulls a pre-built image from the
registry. When IMAGE_URL is set, this script pins the deploy to that exact
image digest so Render is guaranteed to run the image just pushed (rather
than whatever "latest" happens to resolve to at pull time).

Required environment variables:
  RENDER_API_KEY      Render API key (Account Settings -> API Keys).
  RENDER_SERVICE_ID   Render service id, e.g. "srv-xxxxxxxxxxxxxxxxxxxx".

Optional:
  IMAGE_URL            Image (with digest) to pin this deploy to, e.g.
                        "ghcr.io/owner/repo@sha256:...". Must match the
                        service's configured image host/repo. Falls back to
                        the service's currently configured image if unset.
  GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3
                        Synced to the service's env vars if set, used by the
                        Q&A agent.
"""
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.render.com/v1"
ENV_VAR_KEYS = ["GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY_4", "GROQ_API_KEY_5"]


def _request(method: str, path: str, token: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"Render API error {e.code} on {method} {path}: {e.read().decode()}")


def main() -> None:
    token = os.environ.get("RENDER_API_KEY")
    service_id = os.environ.get("RENDER_SERVICE_ID")
    if not token or not service_id:
        sys.exit("RENDER_API_KEY and RENDER_SERVICE_ID must both be set.")

    # The update-env-vars endpoint replaces the *entire* list, so every var
    # the service needs must be included here, not just changed ones.
    env_vars = [
        {"key": key, "value": os.environ[key]}
        for key in ENV_VAR_KEYS
        if os.environ.get(key)
    ]
    print(f"Updating {len(env_vars)} env var(s) on service {service_id}...")
    _request("PUT", f"/services/{service_id}/env-vars", token, env_vars)

    deploy_body = {}
    image_url = os.environ.get("IMAGE_URL")
    if image_url:
        deploy_body["imageUrl"] = image_url
        print(f"Triggering deploy pinned to {image_url}...")
    else:
        print("Triggering deploy (no IMAGE_URL set, using service's configured image)...")
    deploy = _request("POST", f"/services/{service_id}/deploys", token, deploy_body)
    print(f"Deploy triggered: {deploy.get('id', deploy)} (status: {deploy.get('status', 'unknown')})")


if __name__ == "__main__":
    main()
