"""Single-traversal model exporter producing JSON, .dialog, DOT, and HTML."""

from __future__ import annotations

import html
import json
from typing import Any

from ontology_spider.model import OntologyModel


def to_json(model: OntologyModel, indent: int = 2) -> str:
    """Export model to standard JSON format."""
    return json.dumps(model.to_dict(), indent=indent)


def to_dialog(model: OntologyModel) -> str:
    """Export model to lossless .dialog authoring format."""
    lines: list[str] = [
        f"dialog {model.uri}",
        "",
        "# Entities and Schema",
    ]

    for ent in model.entities.values():
        if ent.attributes:
            attrs_str = ", ".join(f"{k}={v}" for k, v in ent.attributes.items())
            lines.append(f"# Entity {ent.id} [{attrs_str}]")

    lines.append("")
    lines.append("# Assertions")

    for asrt in model.assertions.values():
        rel = asrt.relation
        line = f"assert {rel.subject} {rel.predicate} {rel.object}"
        if asrt.attributes:
            attr_parts = [f"{k}={v}" for k, v in asrt.attributes.items()]
            line += f" [{', '.join(attr_parts)}]"
        lines.append(line)

    lines.append("")
    return "\n".join(lines)


def to_dot(model: OntologyModel) -> str:
    """Export model to Graphviz DOT diagram format."""
    lines: list[str] = [
        f'digraph "{model.uri}" {{',
        '  rankdir="LR";',
        '  node [shape=box, style="rounded,filled", fillcolor="#f0f4f8", fontname="sans-serif"];',
        '  edge [fontname="sans-serif", fontsize=10];',
    ]

    for ent in model.entities.values():
        label = ent.name or ent.id
        lines.append(f'  "{ent.id}" [label="{label}"];')

    for asrt in model.assertions.values():
        rel = asrt.relation
        style = 'style="dashed"' if rel.predicate == "subclass_of" else ""
        lines.append(
            f'  "{rel.subject}" -> "{rel.object}" [label="{rel.predicate}" {style}];'
        )

    lines.append("}")
    return "\n".join(lines)


def to_html(model: OntologyModel) -> str:
    """Export model to a self-contained, styled static HTML view."""
    e_rows = []
    for ent in model.entities.values():
        attrs = ", ".join(f"{k}: {v}" for k, v in ent.attributes.items()) or "—"
        e_rows.append(
            f"<tr><td><code>{html.escape(ent.id)}</code></td>"
            f"<td>{html.escape(ent.name or '—')}</td>"
            f"<td>{html.escape(attrs)}</td></tr>"
        )

    a_rows = []
    for asrt in model.assertions.values():
        rel = asrt.relation
        p = asrt.provenance
        prov_text = f"{p.source} (turn: {p.turn_id or '—'})"
        a_rows.append(
            f"<tr><td><code>{html.escape(asrt.assertion_id)}</code></td>"
            f"<td><code>{html.escape(rel.subject)}</code></td>"
            f"<td><strong>{html.escape(rel.predicate)}</strong></td>"
            f"<td><code>{html.escape(rel.object)}</code></td>"
            f"<td><small>{html.escape(prov_text)}</small></td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ontology: {html.escape(model.uri)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 2rem; color: #333; }}
    h1 {{ color: #1e3a8a; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }}
    .stats {{ display: flex; gap: 1.5rem; margin-bottom: 1.5rem; }}
    .badge {{ background: #eff6ff; color: #1d4ed8; padding: 0.5rem 1rem; border-radius: 6px; font-weight: bold; border: 1px solid #bfdbfe; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; margin-bottom: 2rem; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 0.5rem 0.75rem; text-align: left; }}
    th {{ background: #f8fafc; color: #475569; }}
    code {{ background: #f1f5f9; padding: 2px 4px; border-radius: 4px; font-size: 0.9em; }}
  </style>
</head>
<body>
  <h1>Ontology: {html.escape(model.uri)}</h1>
  <div class="stats">
    <div class="badge">Entities: {len(model.entities)}</div>
    <div class="badge">Assertions: {len(model.assertions)}</div>
  </div>

  <h2>Entities</h2>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Attributes</th></tr></thead>
    <tbody>
      {''.join(e_rows) if e_rows else '<tr><td colspan="3">No entities</td></tr>'}
    </tbody>
  </table>

  <h2>Assertions & Provenance</h2>
  <table>
    <thead><tr><th>Assertion ID</th><th>Subject</th><th>Predicate</th><th>Object</th><th>Provenance</th></tr></thead>
    <tbody>
      {''.join(a_rows) if a_rows else '<tr><td colspan="5">No assertions</td></tr>'}
    </tbody>
  </table>
</body>
</html>"""
