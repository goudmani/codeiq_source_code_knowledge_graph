#!/usr/bin/env python3
"""
app.py

CodeIQ -- a dark-mode Shiny chat UI over the qa_agent (src/qa_agent/agent.py).
Every question is answered by ask(), and the UI surfaces every field ask()
returns: answer, a deterministic confidence tag (with hover/click rationale),
a "more info" popover (model/latency/tool_calls), tabbed sources with
expandable code (loaded live from data/raw/<file>, syntax-highlighted,
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
from src.clone_raw.clone_raw import BRANCH, REPO_NAME, REPO_OWNER  # noqa: E402
from src.qa_agent.agent import DEFAULT_MODEL, MODELS, ask  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

HAS_API_KEY = bool(os.environ.get("GROQ_API_KEY"))

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

header = ui.HTML(f"""
<div class="app-header">
  <div class="brand">
    <div class="brand-mark">
      <img src="/img/confused-cat.svg" alt="No results">
    </div>
    <div>
      <div class="brand-title">CodeIQ</div>
      <div class="brand-sub">Source Knowledge Graph</div>
    </div>
  </div>
  <div class="repo-pill">
    <span class="status-dot"></span>
    <span>Exploring</span>
    <span class="repo-name">{render_utils.esc(REPO_OWNER)}/{render_utils.esc(REPO_NAME)}</span>
    <span class="repo-branch">{render_utils.esc(BRANCH)}</span>
    <a class="repo-clear" href="https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/{BRANCH}" target="_blank" rel="noopener" title="Open on GitHub">&#8599;</a>
  </div>
</div>
""")

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
    async def run_ask(question: str, model: str) -> dict:
        return await asyncio.to_thread(ask, question, model=model)

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
        run_ask(question, input.model())

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
                pieces.append(render_utils.render_exchange(entry, REPO_OWNER, REPO_NAME, BRANCH))

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
        title, body_html = render_utils.render_modal_body(file, start, end, REPO_OWNER, REPO_NAME, BRANCH)
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


app = App(app_ui, server, static_assets=str(APP_DIR / "www"))
