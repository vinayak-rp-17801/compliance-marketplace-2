"""
generate_report.py
------------------
Reporting module: turns the per-file result dicts produced by
file_processor.process_file() into human-readable report files.

Public API
----------
write_replacement_report(results, output_path)
write_tool_audit_report(results, output_path)
"""

import os
import datetime
from collections import defaultdict

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SEP_MAJOR = "=" * 80
_SEP_MINOR = "-" * 80


def _header(title: str) -> str:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"{_SEP_MAJOR}\n{title}\nGenerated: {ts}\n{_SEP_MAJOR}\n"


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


# ---------------------------------------------------------------------------
# Replacement report
# ---------------------------------------------------------------------------


def write_replacement_report(results: list[dict], output_path: str) -> None:
    """
    Write a plain-text replacement report to *output_path*.

    Parameters
    ----------
    results : list[dict]
        List of result dicts as returned by file_processor.process_file().
    output_path : str
        Destination file path (parent directories are created automatically).
    """
    _ensure_dir(output_path)

    total_replacements = sum(len(r["replacements"]) for r in results)
    files_changed = [r for r in results if r["replacements"]]
    files_skipped = [r for r in results if r["skipped"]]

    lines = [_header("Log360 → Log360 Cloud  |  Replacement Report")]
    lines.append(f"Total files processed : {len(results)}")
    lines.append(f"Files with changes    : {len(files_changed)}")
    lines.append(f"Total replacements    : {total_replacements}")
    lines.append(f"Files skipped         : {len(files_skipped)}")
    lines.append("")

    # ---- Files with replacements ----------------------------------------
    if files_changed:
        lines.append(_SEP_MINOR)
        lines.append("REPLACEMENTS MADE")
        lines.append(_SEP_MINOR)
        for result in files_changed:
            rel = os.path.relpath(result["src"])
            lines.append(f"\nFile : {rel}")
            lines.append(f"  Replacements: {len(result['replacements'])}")
            for rec in result["replacements"]:
                # Plain-text replacement records may have different keys
                # depending on file type.
                if "line" in rec:
                    lines.append(f"  Line {rec['line']}:")
                    lines.append(f"    BEFORE: {rec['before'].strip()}")
                    lines.append(f"    AFTER : {rec['after'].strip()}")
                elif "cell" in rec:
                    lines.append(
                        f"  Sheet '{rec['sheet']}', Cell {rec['cell']}:"
                    )
                    lines.append(f"    BEFORE: {rec['before'].strip()}")
                    lines.append(f"    AFTER : {rec['after'].strip()}")
                elif "slide" in rec:
                    lines.append(f"  Slide {rec['slide']}:")
                    lines.append(f"    BEFORE: {rec['before'].strip()}")
                    lines.append(f"    AFTER : {rec['after'].strip()}")
                else:
                    lines.append(f"    BEFORE: {rec.get('before', '').strip()}")
                    lines.append(f"    AFTER : {rec.get('after', '').strip()}")
    else:
        lines.append("No replacements were made.")

    # ---- Skipped files --------------------------------------------------
    if files_skipped:
        lines.append("")
        lines.append(_SEP_MINOR)
        lines.append("SKIPPED FILES")
        lines.append(_SEP_MINOR)
        for result in files_skipped:
            rel = os.path.relpath(result["src"])
            lines.append(f"  {rel}")
            lines.append(f"    Reason: {result['skip_reason']}")

    lines.append("")
    lines.append(_SEP_MAJOR)
    lines.append("END OF REPORT")
    lines.append(_SEP_MAJOR)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"[report] Replacement report written to: {output_path}")


# ---------------------------------------------------------------------------
# Tool audit report
# ---------------------------------------------------------------------------


def write_tool_audit_report(results: list[dict], output_path: str) -> None:
    """
    Write a plain-text tool audit report to *output_path*.

    Parameters
    ----------
    results : list[dict]
        List of result dicts as returned by file_processor.process_file().
    output_path : str
        Destination file path (parent directories are created automatically).
    """
    _ensure_dir(output_path)

    # Aggregate: tool -> {filename -> [context, ...]}
    tool_index: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for result in results:
        rel = os.path.relpath(result["src"])
        for mention in result["tool_mentions"]:
            tool_index[mention["tool"]][rel].append(mention["context"])

    lines = [_header("Tool Mention Audit Report")]
    lines.append("Tools scanned:")
    from file_processor import TOOLS  # noqa: PLC0415
    for t in TOOLS:
        lines.append(f"  • {t}")
    lines.append("")

    # ---- Per-tool summary -----------------------------------------------
    lines.append(_SEP_MINOR)
    lines.append("SUMMARY")
    lines.append(_SEP_MINOR)
    for tool in TOOLS:
        file_count = len(tool_index.get(tool, {}))
        total = sum(len(v) for v in tool_index.get(tool, {}).values())
        lines.append(f"  {tool:<20}  {file_count:>3} file(s)   {total:>4} mention(s)")

    lines.append("")

    # ---- Per-tool details -----------------------------------------------
    for tool in TOOLS:
        files = tool_index.get(tool, {})
        lines.append(_SEP_MINOR)
        total = sum(len(v) for v in files.values())
        lines.append(f"TOOL: {tool}  ({len(files)} file(s), {total} mention(s))")
        lines.append(_SEP_MINOR)
        if not files:
            lines.append("  (not found in any file)")
        else:
            for filename, contexts in sorted(files.items()):
                lines.append(f"\n  File: {filename}")
                lines.append(f"  Occurrences: {len(contexts)}")
                for idx, ctx in enumerate(contexts, start=1):
                    lines.append(f"    [{idx}] ...{ctx.strip()}...")
        lines.append("")

    lines.append(_SEP_MAJOR)
    lines.append("END OF REPORT")
    lines.append(_SEP_MAJOR)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"[report] Tool audit report written to: {output_path}")
