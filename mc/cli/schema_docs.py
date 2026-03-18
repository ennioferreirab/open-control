"""Schema/docs command helpers for Mission Control CLI."""

from __future__ import annotations

import re

import typer


def _parse_schema_tables(schema_text: str) -> str:
    """Extract table definitions from a Convex schema.ts file."""
    lines = []
    table_matches = re.findall(r"(\w+):\s*defineTable\(\{(.*?)\}\)", schema_text, re.DOTALL)
    for table_name, body in table_matches:
        lines.append(f"### {table_name}\n")
        fields = re.findall(r"(\w+):\s*v\.(\w+)\(([^)]*)\)", body)
        if fields:
            lines.append("| Field | Type | Detail |")
            lines.append("|-------|------|--------|")
            for field_name, vtype, detail in fields:
                detail_clean = detail.strip().strip('"').strip("'")
                lines.append(f"| {field_name} | {vtype} | {detail_clean} |")
        lines.append("")

    index_matches = re.findall(r'\.index\("(\w+)",\s*\[([^\]]+)\]\)', schema_text)
    if index_matches:
        lines.append("### Indexes\n")
        for idx_name, idx_fields in index_matches:
            fields_clean = idx_fields.replace('"', "").strip()
            lines.append(f"- **{idx_name}**: [{fields_clean}]")
        lines.append("")

    return "\n".join(lines)


def _parse_convex_functions(file_text: str, module_name: str) -> str:
    """Extract exported query/mutation names from a Convex function file."""
    lines = []
    exports = re.findall(
        r"export\s+const\s+(\w+)\s*=\s*(query|mutation|internalQuery|internalMutation)",
        file_text,
    )
    if exports:
        for func_name, func_type in exports:
            lines.append(f"- `{module_name}:{func_name}` ({func_type})")
    else:
        lines.append("_No exported functions found._")
    return "\n".join(lines)


def register_docs_command(mc_app: typer.Typer) -> None:
    """Register the docs command on the main mc_app."""

    @mc_app.command()
    def docs():
        """Show auto-generated API documentation from Convex schema."""
        from rich.markdown import Markdown

        import mc.cli as _cli

        dashboard_dir = _cli._find_dashboard_dir()
        convex_dir = dashboard_dir / "convex"

        if not convex_dir.is_dir():
            _cli.console.print("[red]Convex directory not found.[/red]")
            raise typer.Exit(1)

        doc_lines = ["# Mission Control API Reference\n"]
        schema_file = convex_dir / "schema.ts"
        if schema_file.exists():
            doc_lines.append("## Tables\n")
            doc_lines.append(_parse_schema_tables(schema_file.read_text()))

        for ts_file in sorted(convex_dir.glob("*.ts")):
            if ts_file.name.startswith("_") or ts_file.name == "schema.ts":
                continue
            doc_lines.append(f"\n## {ts_file.stem}\n")
            doc_lines.append(_parse_convex_functions(ts_file.read_text(), ts_file.stem))

        _cli.console.print(Markdown("\n".join(doc_lines)))
