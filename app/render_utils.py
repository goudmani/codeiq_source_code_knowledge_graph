#!/usr/bin/env python3
"""
render_utils.py

Pure HTML/Markdown builders for the CodeIQ chat UI. Everything here returns
plain strings (escaped where needed) that app.py wraps in `ui.HTML(...)`.
Keeping this separate from app.py keeps the Shiny wiring (reactivity, i/o)
free of string-templating noise.

All interactivity driven by this markup (tabs, tooltips, expand/collapse,
downloads) is handled client-side in www/app.js via event delegation, so
none of it needs a Shiny round-trip -- except "view full file", which posts
to the `codeiq_view_file` input (see app.py) since it needs to read a file
from disk.
"""
from __future__ import annotations

import json
from html import escape as _esc

from markdown_it import MarkdownIt

import file_utils

# Re-exported so app.py doesn't need its own `html.escape` import for the
# handful of strings it embeds directly (header repo info, modal titles).
esc = _esc

TYPE_COLORS = {
    "File": "#38bdf8",
    "Component": "#a78bfa",
    "Hook": "#34d399",
    "Screen": "#fb923c",
    "External": "#94a3b8",
    "Unknown": "#94a3b8",
}

CONFIDENCE_META = {
    "High": {"cls": "conf-high", "icon": "\u25cf"},
    "Medium": {"cls": "conf-medium", "icon": "\u25cf"},
    "Low": {"cls": "conf-low", "icon": "\u25cf"},
}

PREVIEW_LINES = 4


def render_markdown(text: str) -> str:
    print("llm answer",text)
    _md = MarkdownIt("commonmark", {"breaks": True, "html": False}).enable("table")
    return _md.render(text)


def render_user_bubble(question: str) -> str:
    return f"""
<div class="turn turn-user">
  <div class="user-bubble">{_esc(question)}</div>
</div>"""


def render_pending(question: str) -> str:
    return f"""
<div class="turn turn-user">
  <div class="user-bubble">{_esc(question)}</div>
</div>
<div class="turn turn-assistant">
  <div class="assistant-bubble pending-bubble">
    <div class="thinking">
      <span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>
      <span class="thinking-label">CodeIQ is analyzing the graph&hellip;</span>
    </div>
  </div>
</div>"""


def render_error_bubble(question: str, error: str) -> str:
    return f"""
<div class="turn turn-user">
  <div class="user-bubble">{_esc(question)}</div>
</div>
<div class="turn turn-assistant">
  <div class="assistant-bubble error-bubble">
    <div class="error-title">&#9888; Something went wrong</div>
    <div class="error-detail">{_esc(error)}</div>
  </div>
</div>"""


def _confidence_tag(level: str, rationale: str) -> str:
    meta = CONFIDENCE_META.get(level, CONFIDENCE_META["Low"])
    return f"""
<span class="confidence-tag {meta['cls']}">
  <span class="conf-dot">{meta['icon']}</span>{_esc(level)} confidence
  <span class="info-dot" tabindex="0" role="button" aria-label="Why this confidence level?">i</span>
  <span class="tooltip-box">{_esc(rationale)}</span>
</span>"""


def _more_info_panel(msg_id: str, model: str, latency_s: float, tool_calls: list[dict]) -> str:
    if tool_calls:
        rows = "".join(
            f'<li><span class="tc-tool">{_esc(tc.get("tool", "?"))}</span>'
            f'<code class="tc-args">{_esc(json.dumps(tc.get("args", {}), separators=(", ", ": ")))}</code></li>'
            for tc in tool_calls
        )
        tc_html = f'<ul class="tool-call-list">{rows}</ul>'
    else:
        tc_html = '<div class="mi-empty">No tool calls recorded.</div>'

    return f"""
<div class="more-info-wrap">
  <button class="more-info-toggle" data-target="more-{msg_id}" type="button">&#9881; More info</button>
  <div class="more-info-panel" id="more-{msg_id}">
    <div class="mi-row"><span class="mi-label">Model</span><span class="mi-value mi-mono">{_esc(model)}</span></div>
    <div class="mi-row"><span class="mi-label">Latency</span><span class="mi-value">{latency_s:.2f}s</span></div>
    <div class="mi-row mi-row-block"><span class="mi-label">Tool calls ({len(tool_calls)})</span>{tc_html}</div>
  </div>
</div>"""


def _github_url(owner: str, name: str, branch: str, file: str, start: int, end: int) -> str:
    frag = f"#L{start}-L{end}" if start and end else ""
    return f"https://github.com/{owner}/{name}/blob/{branch}/{file}{frag}"


def _breadcrumb(owner: str, name: str, file: str) -> str:
    parts = [p for p in (file or "").split("/") if p]
    crumbs = [f'<span class="crumb-repo">{_esc(owner)}/{_esc(name)}</span>']
    for i, part in enumerate(parts):
        cls = "crumb-file" if i == len(parts) - 1 else "crumb-dir"
        crumbs.append(f'<span class="crumb-sep">/</span><span class="{cls}">{_esc(part)}</span>')
    return "".join(crumbs)


def _code_pre(code_text: str, start_line: int = 1, highlight_range: str | None = None) -> str:
    attrs = f'class="line-numbers" data-start="{start_line}"'
    if highlight_range:
        attrs += f' data-line="{_esc(highlight_range)}"'
    return f'<pre {attrs}><code class="language-tsx">{_esc(code_text)}</code></pre>'


def source_code_lines(source: dict) -> tuple[list[str], bool]:
    """Lines for a source's start-end range, preferring the live file on disk.

    Returns (lines, from_live_file). Falls back to the hit's embedded
    snippet (only present on search_code() results) if the file isn't
    available locally, and finally to an empty list for e.g. external deps.
    """
    file = source.get("file")
    start = source.get("start_line") or 1
    end = source.get("end_line") or start
    if file and file_utils.file_exists(file):
        lines = file_utils.read_range(file, start, end)
        if lines:
            return lines, True
    snippet = source.get("snippet")
    if snippet:
        return snippet.splitlines(), False
    return [], False


def _source_tab_button(idx: int, msg_id: str, source: dict, active: bool) -> str:
    dot_color = TYPE_COLORS.get(source.get("type", "Unknown"), TYPE_COLORS["Unknown"])
    label = source.get("name") or source.get("id") or f"source {idx}"
    active_cls = " active" if active else ""
    return f"""<button class="tab-btn{active_cls}" data-tab="src-{msg_id}-{idx}" type="button" title="{_esc(label)}">
  <span class="tab-dot" style="background:{dot_color}"></span>{_esc(source.get('type', ''))} &middot; {_esc(label)}
</button>"""


def _source_tab_panel(idx: int, msg_id: str, source: dict, active: bool, owner: str, name: str, branch: str) -> str:
    active_cls = " active" if active else ""
    file = source.get("file") or ""
    start = source.get("start_line") or 0
    end = source.get("end_line") or 0
    relevance = source.get("relevance")
    relation = source.get("relation")
    direction = source.get("direction")

    badges = [f'<span class="badge type-badge">{_esc(source.get("type", "Unknown"))}</span>']
    if relevance is not None:
        badges.append(f'<span class="badge relevance-badge">relevance {relevance:.2f}</span>')
    if relation:
        arrow = "&rarr;" if direction == "out" else "&larr;" if direction == "in" else "&harr;"
        badges.append(f'<span class="badge relation-badge">{arrow} {_esc(relation)}</span>')

    lines, from_live_file = source_code_lines(source)
    n_lines = len(lines)

    if not file:
        code_section = '<div class="code-unavailable">No source file for this entity (external dependency).</div>'
    elif not lines:
        code_section = '<div class="code-unavailable">Source file not available locally.</div>'
    else:
        newline = "\n"
        preview_text = newline.join(lines[:PREVIEW_LINES])
        if n_lines > PREVIEW_LINES:
            preview_text += newline + "\u22ef"
        note = "" if from_live_file else '<span class="live-note">from cached snippet</span>'
        full_code_text = newline.join(lines)
        code_section = f"""
<div class="code-block-wrap" data-msg="{msg_id}">
  <div class="code-preview" role="button" tabindex="0">
    <pre class="preview-pre">{_esc(preview_text)}</pre>
    <div class="expand-hint">&#9662; expand {n_lines} line{'s' if n_lines != 1 else ''} &middot; L{start}&ndash;L{end}</div>
  </div>
  <div class="code-full">
    <div class="code-breadcrumb">
      <a href="{_github_url(owner, name, branch, file, start, end)}" target="_blank" rel="noopener">{_breadcrumb(owner, name, file)}</a>
    </div>
    <div class="code-toolbar">
      <span class="range-pill">L{start}&ndash;L{end}</span>
      {note}
      <button class="copy-btn" type="button" title="Copy code">&#128203; Copy</button>
      <button class="view-full-file-btn" type="button" data-file="{_esc(file)}" data-start="{start}" data-end="{end}">&#10530; View full file</button>
      <button class="collapse-btn" type="button">&#9652; Collapse</button>
    </div>
    {_code_pre(full_code_text, start_line=start or 1)}
  </div>
</div>"""

    return f"""<div class="tab-panel{active_cls}" id="src-{msg_id}-{idx}">
  <div class="source-meta">{''.join(badges)}<span class="source-loc">{_esc(file)}{f':{start}-{end}' if file else ''}</span></div>
  {code_section}
</div>"""


def render_sources_block(sources: list[dict], msg_id: str, owner: str, name: str, branch: str) -> str:
    if not sources:
        return '<div class="no-sources">No sources were retrieved for this answer.</div>'

    buttons = "".join(_source_tab_button(i, msg_id, s, i == 0) for i, s in enumerate(sources))
    panels = "".join(_source_tab_panel(i, msg_id, s, i == 0, owner, name, branch) for i, s in enumerate(sources))
    return f"""
<div class="sources-block">
  <div class="sources-heading">Sources <span class="sources-count">({len(sources)})</span></div>
  <div class="tabs-nav">{buttons}</div>
  <div class="tabs-panels">{panels}</div>
</div>"""


def build_markdown_export(entry: dict, owner: str, name: str, branch: str) -> str:
    lines = [
        "# CodeIQ Q&A Export",
        "",
        f"**Repository:** {owner}/{name} (`{branch}`)",
        f"**Generated:** {entry.get('timestamp', '')}",
        "",
        "## Question",
        "",
        entry.get("question", ""),
        "",
        "## Answer",
        "",
        entry.get("answer", ""),
        "",
        f"## Confidence: {entry.get('confidence', '')}",
        "",
        entry.get("confidence_rationale", ""),
        "",
        "## Metadata",
        "",
        f"- Model: `{entry.get('model', '')}`",
        f"- Latency: {entry.get('latency_s', 0)}s",
        f"- Tool calls: {len(entry.get('tool_calls', []))}",
    ]
    for i, tc in enumerate(entry.get("tool_calls", []), 1):
        lines.append(f"  {i}. `{tc.get('tool')}({json.dumps(tc.get('args', {}))})`")
    lines += ["", "## Sources", ""]

    sources = entry.get("sources", [])
    if not sources:
        lines.append("_No sources were retrieved for this answer._")
    for i, s in enumerate(sources, 1):
        file = s.get("file") or ""
        loc = f"{file}:{s.get('start_line', '')}-{s.get('end_line', '')}" if file else s.get("id", "")
        lines.append(f"### {i}. {s.get('type', 'Unknown')} `{s.get('name', s.get('id', ''))}` &mdash; {loc}")
        lines.append("")
        code_lines, _ = source_code_lines(s)
        if code_lines:
            lines.append("```tsx")
            lines.extend(code_lines)
            lines.append("```")
        else:
            lines.append("_source not available_")
        lines.append("")

    return "\n".join(lines)


def render_exchange(entry: dict, owner: str, name: str, branch: str) -> str:
    msg_id = entry["id"]
    md_export = build_markdown_export(entry, owner, name, branch)
    md_export_escaped = _esc(md_export)
    filename = f"codeiq-{msg_id}.md"

    return f"""
<div class="turn turn-user">
  <div class="user-bubble">{_esc(entry['question'])}</div>
</div>
<div class="turn turn-assistant" id="turn-{msg_id}">
  <div class="badge-row">
    {_confidence_tag(entry['confidence'], entry['confidence_rationale'])}
    {_more_info_panel(msg_id, entry['model'], entry['latency_s'], entry.get('tool_calls', []))}
  </div>
  <div class="assistant-bubble">
    <div class="answer-text">Answer: {render_markdown(entry['answer'])}</div>
    {render_sources_block(entry.get('sources', []), msg_id, owner, name, branch)}
    <div class="bubble-footer">
      <span class="footer-meta">{_esc(entry['model'])} &middot; {entry['latency_s']:.2f}s &middot; {len(entry.get('sources', []))} source(s)</span>
      <button class="dl-btn" type="button" data-target="md-{msg_id}" data-filename="{filename}">&#11015; Export .md</button>
    </div>
  </div>
</div>
<textarea class="md-export-data" id="md-{msg_id}" hidden readonly>{md_export_escaped}</textarea>"""


def render_modal_body(file: str, start: int | None, end: int | None, owner: str, name: str, branch: str) -> tuple[str, str]:
    """Returns (title, body_html) for the 'view full file' modal."""
    lines, truncated = file_utils.read_full_file(file)
    if not lines:
        return file, '<div class="code-unavailable">This file is not available locally.</div>'

    highlight = f"{start}-{end}" if start and end else None
    url = _github_url(owner, name, branch, file, start or 0, end or 0)
    body = f'<div class="modal-breadcrumb"><a href="{url}" target="_blank" rel="noopener">{_breadcrumb(owner, name, file)}</a></div>'
    if truncated:
        body += f'<div class="modal-truncated-note">Showing first {len(lines)} lines (file truncated for display).</div>'
    body += f'<div class="modal-code-scroll">{_code_pre(chr(10).join(lines), start_line=1, highlight_range=highlight)}</div>'
    return file, body
