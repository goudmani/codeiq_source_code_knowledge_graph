#!/usr/bin/env python3
"""
app.py

CodeIQ -- a Shiny chat UI over the qa_agent (src/qa_agent/agent.py).
Every question is answered by ask(), and the UI surfaces every field ask()
returns: answer, a deterministic confidence tag (with hover/click rationale),
a "more info" popover (model/latency/tool_calls), tabbed sources with
expandable code (loaded live from data/raw/<tag>/<file>, syntax-highlighted,
breadcrumbed, and openable full-file in a modal), and a per-answer .md export.

Run with:
  conda activate codeiq
  shiny run app/app.py --reload
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
from shiny import App, reactive, render, ui  # noqa: E402

import render_utils  # noqa: E402
from src.clone_raw.clone_raw import BRANCH, REPO_NAME, REPO_OWNER, TAG  # noqa: E402
from src.qa_agent.agent import DEFAULT_MODEL, MODELS, ask  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

HAS_API_KEY = bool(os.environ.get("GROQ_API_KEY"))

# Indexed repos the qa_agent can be pointed at (data/processed/<tag>/, data/raw/<tag>/).
# Keyed by the same `tag` ask() takes/returns, so a chat entry's "tag" field
# is enough to know which repo an answer -- and its sources -- came from.
DEFAULT_TAG = TAG
REPOS: dict[str, dict[str, str]] = {
    TAG: {"owner": REPO_OWNER, "name": REPO_NAME, "branch": BRANCH},
    "raysk4ever_Simple-React-Native-App_main": {
        "owner": "raysk4ever",
        "name": "Simple-React-Native-App",
        "branch": "main",
    },
}
REPO_CHOICES = {tag: f"{info['owner']}/{info['name']}" for tag, info in REPOS.items()}


def _repo_info(tag: str | None) -> dict[str, str]:
    return REPOS.get(tag or DEFAULT_TAG, REPOS[DEFAULT_TAG])


EXAMPLE_PROMPTS = [
    "Which hook manages session state?",
    "What renders the bookmarks screen?",
    "What breaks if BookmarksScreen changes?",
    "Where is the login flow implemented?",
]

PRISM_VERSION = "1.29.0"
PRISM_BASE = f"https://cdnjs.cloudflare.com/ajax/libs/prism/{PRISM_VERSION}"

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
head = ui.tags.head(
    ui.tags.meta(charset="utf-8"),
    ui.tags.meta(name="viewport", content="width=device-width, initial-scale=1"),
    ui.tags.meta(
        name="description",
        content="CodeIQ — ask questions about your codebase and get sourced, confidence-rated answers.",
    ),
    ui.tags.meta(name="theme-color", content="#19162b"),

    ui.tags.title("CodeIQ"), 

    # Browser favicon
    ui.tags.link(
        rel="icon",
        type="image/svg+xml",
        href="img/confused-cat.svg",
    ),

    # Apple devices / home screen icon
    ui.tags.link(
        rel="apple-touch-icon",
        href="img/confused-cat.svg",
    ),

    # Optional: manifest support for installable/PWA-style behavior
    ui.tags.link(
        rel="manifest",
        href="manifest.json",
    ),

    ui.tags.link(rel="preconnect", href="https://fonts.googleapis.com"),
    ui.tags.link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),

    ui.tags.link(
        rel="stylesheet",
        # Montserrat carries headings/brand/body for the notebook feel;
        # Cascadia Code stays for code and metadata.
        href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&family=Cascadia+Code:wght@400;500;600&display=swap",
    ),

    ui.tags.link(rel="stylesheet", href=f"{PRISM_BASE}/themes/prism-tomorrow.min.css"),
    ui.tags.link(rel="stylesheet", href=f"{PRISM_BASE}/plugins/line-numbers/prism-line-numbers.min.css"),
    ui.tags.link(rel="stylesheet", href=f"{PRISM_BASE}/plugins/line-highlight/prism-line-highlight.min.css"),
    ui.tags.link(rel="stylesheet", href="style.css"),

    ui.tags.script(src=f"{PRISM_BASE}/components/prism-core.min.js"),
    ui.tags.script(src=f"{PRISM_BASE}/components/prism-clike.min.js"),
    ui.tags.script(src=f"{PRISM_BASE}/components/prism-markup.min.js"),
    ui.tags.script(src=f"{PRISM_BASE}/components/prism-css.min.js"),
    ui.tags.script(src=f"{PRISM_BASE}/components/prism-javascript.min.js"),
    ui.tags.script(src=f"{PRISM_BASE}/components/prism-typescript.min.js"),
    ui.tags.script(src=f"{PRISM_BASE}/components/prism-jsx.min.js"),
    ui.tags.script(src=f"{PRISM_BASE}/components/prism-tsx.min.js"),
    ui.tags.script(src=f"{PRISM_BASE}/plugins/line-numbers/prism-line-numbers.min.js"),
    ui.tags.script(src=f"{PRISM_BASE}/plugins/line-highlight/prism-line-highlight.min.js"),
    ui.tags.script(src="app.js"),
)

header = ui.div(
    ui.HTML("""
<div class="brand">
  <div class="brand-mark">
    <img src="/img/confused-cat.svg" alt="No results">
  </div>
  <div>
    <div class="brand-title">CodeIQ</div>
    <div class="brand-sub">Source Knowledge Graph</div>
  </div>
</div>
"""),
    ui.div(
        ui.div(
            ui.HTML('<span class="status-dot"></span><span class="pill-label">Exploring</span>'),
            ui.input_select("repo", None, choices=REPO_CHOICES, selected=DEFAULT_TAG),
            ui.output_ui("repo_meta", inline=True),
            class_="repo-pill",
        ),
        ui.HTML("""
<div class="header-links">
  <a class="header-link" href="/reports/codeiq_presentation.html" target="_blank" rel="noopener"
     title="Docs &amp; presentation" aria-label="Docs and presentation">
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none"
         stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="9"/>
      <path d="M12 11v5"/>
      <path d="M12 8h.01"/>
    </svg>
  </a>
  <a class="header-link" href="https://github.com/goudmani/codeiq_source_code_knowledge_graph"
     target="_blank" rel="noopener" title="GitHub repository" aria-label="GitHub repository">
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12 22 6.477 17.523 2 12 2z"/>
    </svg>
  </a>
</div>
"""),
        class_="header-right",
    ),
    class_="app-header",
)

key_banner = (
    ui.HTML(
        '<div class="key-banner">&#9888; GROQ_API_KEY is not set -- add it to .env to enable CodeIQ.</div>'
    )
    if not HAS_API_KEY
    else None
)

example_chips_html = "".join(
    f'<button type="button" class="example-chip" data-prompt="{render_utils.esc(p)}">{render_utils.esc(p)}</button>'
    for p in EXAMPLE_PROMPTS
)

empty_state = ui.HTML(f"""
<div class="empty-state">
  <div class="empty-glyph"> <img src="/img/code-cat.svg" alt="CodeIQ confused-cat"></div>
  <h2>Ask CodeIQ about the codebase</h2>
  <p>Questions are answered by tracing the {render_utils.esc(REPO_NAME)} knowledge graph &mdash;
     semantic search plus exact entity &amp; relationship lookups &mdash; not by guessing.</p>
  <div class="example-chips">{example_chips_html}</div>
</div>
""")

model_choices = {key: key for key in MODELS}

composer = ui.div(
    ui.div(
        ui.input_text_area(
            "question",
            None,
            placeholder="Ask about a hook, component, screen, or file...",
            rows=1,
            autoresize=True,
            width="100%",
        ),
        ui.div(ui.input_select("model", None, choices=model_choices, selected=DEFAULT_MODEL), class_="model-select"),
        ui.input_action_button("send", "Send", disabled=not HAS_API_KEY),
        class_="composer-inner",
    ),
    ui.HTML('<div class="composer-hint">Enter to send &middot; Shift+Enter for a new line</div>'),
    class_="composer",
)

# ui.output_ui renders into a plain <div>; we want that div to be #chat-panel
# so app.js/CSS can target its scroll behavior directly.
app_ui = ui.page_fluid(
    head,
    ui.div(
        key_banner,
        header,
        ui.div(
            ui.div(ui.output_ui("chat_output"), id="chat-panel"),
            composer,
            class_="main-area",
        ),
        class_="app-shell",
    ),
)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------


def server(input, output, session):  # noqa: A002 - shiny convention
    chat_history: reactive.Value[list[dict]] = reactive.Value([])
    pending_question: reactive.Value[str | None] = reactive.Value(None)
    busy: reactive.Value[bool] = reactive.Value(False)

    @reactive.extended_task
    async def run_ask(question: str, model: str, tag: str) -> dict:
        return await asyncio.to_thread(ask, question, model=model, tag=tag)

    @reactive.effect
    @reactive.event(input.send)
    def _on_send():
        question = (input.question() or "").strip()
        if not question or busy.get():
            return
        pending_question.set(question)
        busy.set(True)
        ui.update_text_area("question", value="")
        ui.update_action_button("send", label="Thinking...", disabled=True)
        run_ask(question, input.model(), input.repo())

    @output
    @render.ui
    def repo_meta():
        info = _repo_info(input.repo())
        return ui.HTML(
            f'<span class="repo-branch">{render_utils.esc(info["branch"])}</span>'
            f'<a class="repo-clear" href="https://github.com/{info["owner"]}/{info["name"]}/tree/{info["branch"]}" '
            f'target="_blank" rel="noopener" title="Open on GitHub">&#8599;</a>'
        )

    @reactive.effect
    @reactive.event(run_ask.status)
    def _on_task_settled():
        # @reactive.event isolates all reads below from becoming reactive
        # dependencies -- this effect should only ever re-run when
        # run_ask.status changes, not when chat_history/pending_question
        # (which it also writes) change.
        status = run_ask.status()
        if status not in ("success", "error"):
            return

        question = pending_question.get() or ""
        busy.set(False)
        pending_question.set(None)
        ui.update_action_button("send", label="Send", disabled=False)

        if status == "success":
            result = run_ask.result()
            entry = dict(result)
            entry["id"] = uuid.uuid4().hex[:10]
            entry["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            chat_history.set(chat_history.get() + [entry])
        else:
            try:
                run_ask.result()
                err_text = "Unknown error."
            except Exception as exc:  # noqa: BLE001 - surfacing any agent failure to the user
                err_text = str(exc) or exc.__class__.__name__
            chat_history.set(
                chat_history.get()
                + [{"kind": "error", "question": question, "error": err_text, "id": uuid.uuid4().hex[:10]}]
            )

    @output
    @render.ui
    def chat_output():
        entries = chat_history.get()
        pending = pending_question.get()

        if not entries and not pending:
            return empty_state

        pieces: list[str] = []
        for entry in entries:
            if entry.get("kind") == "error":
                pieces.append(render_utils.render_error_bubble(entry["question"], entry["error"]))
            else:
                info = _repo_info(entry.get("tag"))
                pieces.append(render_utils.render_exchange(entry, info["owner"], info["name"], info["branch"]))

        if pending:
            pieces.append(render_utils.render_pending(pending))

        pieces.append(
            "<script>"
            "if(window.codeiqHighlight){codeiqHighlight(document.getElementById('chat-panel'));}"
            "if(window.codeiqScrollToBottom){codeiqScrollToBottom();}"
            "</script>"
        )
        return ui.HTML("\n".join(pieces))

    @reactive.effect
    @reactive.event(input.codeiq_view_file)
    def _on_view_file():
        payload = input.codeiq_view_file() or {}
        file = payload.get("file")
        start = payload.get("start")
        end = payload.get("end")
        tag = payload.get("tag") or DEFAULT_TAG
        info = _repo_info(tag)
        title, body_html = render_utils.render_modal_body(
            file, start, end, info["owner"], info["name"], info["branch"], tag
        )
        script = (
            "<script>"
            "if(window.codeiqHighlight){codeiqHighlight(document.querySelector('.modal-code-scroll'));}"
            "setTimeout(function(){"
            "window.dispatchEvent(new Event('resize'));"  # forces Prism's line-highlight plugin to recompute now that the modal is laid out
            "var hl=document.querySelector('.modal-code-scroll .line-highlight');"
            "if(hl&&hl.scrollIntoView){hl.scrollIntoView({block:'center'});}"
            "},200);"
            "</script>"
        )
        ui.modal_show(
            ui.modal(
                ui.HTML(body_html + script),
                title=title,
                easy_close=True,
                size="xl",
                footer=ui.modal_button("Close"),
            )
        )


# "/" serves app/www (CSS/JS/img); "/reports" serves the presentation deck
# so the header docs link works without copying the HTML into www.
app = App(
    app_ui,
    server,
    static_assets={
        "/": str(APP_DIR / "www"),
        "/reports": str(PROJECT_ROOT / "reports"),
    },
)
