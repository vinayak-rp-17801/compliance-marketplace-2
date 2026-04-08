"""
refine_tool_report.py

Reads tool_mentions.csv, consolidates rows so each (Tool, Filename) pair
appears exactly once, then writes:
  - tool_mentions_consolidated.csv
  - TOOL_AUDIT_SUMMARY.md
"""

import csv
import os
from collections import defaultdict, OrderedDict

INPUT_CSV = "tool_mentions.csv"
OUTPUT_CSV = "tool_mentions_consolidated.csv"
SUMMARY_MD = "TOOL_AUDIT_SUMMARY.md"


def load_csv(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def parse_line_numbers(raw):
    """Return a list of stripped line-number strings from a raw cell value."""
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def consolidate(rows):
    """
    Group rows by (Tool, Filename) and merge occurrences, line numbers,
    and context excerpts.

    Returns an OrderedDict keyed by tool name, each value being a list of
    consolidated record dicts in the order they were first seen.
    """
    # Preserve tool insertion order
    groups = OrderedDict()   # tool -> OrderedDict of filename -> record

    for row in rows:
        tool = row.get("Tool", "").strip()
        filename = row.get("Filename", "").strip()
        file_path = row.get("File_Path", "").strip()
        raw_occ = row.get("Occurrences", "0").strip()
        raw_lines = row.get("Line_Numbers", "").strip()
        context = row.get("First_Context_Excerpt", "").strip()

        # Handle "NOT FOUND" sentinel rows
        try:
            occurrences = int(raw_occ)
        except ValueError:
            occurrences = 0

        if tool not in groups:
            groups[tool] = OrderedDict()

        key = filename if filename else "(not found)"

        if key not in groups[tool]:
            groups[tool][key] = {
                "Tool": tool,
                "Filename": filename,
                "File_Path": file_path,
                "Total_Occurrences": 0,
                "line_numbers": [],
                "context_excerpts": [],
            }

        rec = groups[tool][key]
        rec["Total_Occurrences"] += occurrences

        for ln in parse_line_numbers(raw_lines):
            if ln and ln not in rec["line_numbers"]:
                rec["line_numbers"].append(ln)

        if context and context not in ("NOT FOUND",):
            rec["context_excerpts"].append(context)

    return groups


def build_output_rows(groups):
    output = []
    for tool, files in groups.items():
        for key, rec in files.items():
            line_str = ", ".join(rec["line_numbers"]) if rec["line_numbers"] else ""
            excerpts = rec["context_excerpts"]
            if excerpts:
                excerpt_str = " | ".join(
                    f"{i + 1}. {e}" for i, e in enumerate(excerpts)
                )
            elif rec["Total_Occurrences"] == 0:
                excerpt_str = "NOT FOUND"
            else:
                excerpt_str = ""

            output.append(
                {
                    "Tool": rec["Tool"],
                    "Filename": rec["Filename"],
                    "File_Path": rec["File_Path"],
                    "Total_Occurrences": rec["Total_Occurrences"],
                    "All_Line_Numbers": line_str,
                    "All_Context_Excerpts": excerpt_str,
                }
            )
    return output


def write_consolidated_csv(rows, path):
    fieldnames = [
        "Tool",
        "Filename",
        "File_Path",
        "Total_Occurrences",
        "All_Line_Numbers",
        "All_Context_Excerpts",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_md(groups, output_rows, path):
    lines = []
    lines.append("# Tool Audit Summary\n")
    lines.append(
        "Generated from `tool_mentions.csv` after consolidation by `refine_tool_report.py`.\n"
    )
    lines.append("")

    # --- Summary statistics table ---
    lines.append("## Summary by Tool\n")
    lines.append("| Tool | Files Found | Total Occurrences |")
    lines.append("|------|-------------|-------------------|")

    tool_stats = []
    for tool, files in groups.items():
        file_count = sum(
            1 for rec in files.values() if rec["Total_Occurrences"] > 0
        )
        total_occ = sum(rec["Total_Occurrences"] for rec in files.values())
        tool_stats.append((tool, file_count, total_occ))
        lines.append(f"| {tool} | {file_count} | {total_occ} |")

    lines.append("")

    # --- Per-tool file listings ---
    lines.append("## Consolidated File Listing per Tool\n")

    for tool, files in groups.items():
        found_files = [
            rec for rec in files.values() if rec["Total_Occurrences"] > 0
        ]
        lines.append(f"### {tool}")
        if not found_files:
            lines.append("- ❌ Not found in any file.")
        else:
            lines.append(
                f"**{len(found_files)} file(s) — "
                f"{sum(r['Total_Occurrences'] for r in found_files)} total occurrence(s)**\n"
            )
            for rec in found_files:
                ln_str = (
                    f"Line(s): {', '.join(rec['line_numbers'])}"
                    if rec["line_numbers"]
                    else "Line(s): —"
                )
                lines.append(f"- **{rec['Filename']}** ({ln_str})")
                for i, excerpt in enumerate(rec["context_excerpts"], 1):
                    lines.append(f"  {i}. {excerpt}")
        lines.append("")

    # --- Overall statistics ---
    lines.append("## Statistics\n")
    total_tools_found = sum(1 for t, fc, _ in tool_stats if fc > 0)
    total_tools = len(tool_stats)
    all_files = set()
    for tool, files in groups.items():
        for rec in files.values():
            if rec["Total_Occurrences"] > 0 and rec["Filename"]:
                all_files.add(rec["Filename"])
    grand_total = sum(occ for _, _, occ in tool_stats)

    lines.append(f"- **Tools scanned:** {total_tools}")
    lines.append(f"- **Tools found:** {total_tools_found}")
    lines.append(f"- **Unique files containing at least one tool mention:** {len(all_files)}")
    lines.append(f"- **Grand total occurrences:** {grand_total}")
    lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    print(f"Reading {INPUT_CSV} ...")
    rows = load_csv(INPUT_CSV)

    print("Consolidating records ...")
    groups = consolidate(rows)

    output_rows = build_output_rows(groups)

    print(f"Writing {OUTPUT_CSV} ...")
    write_consolidated_csv(output_rows, OUTPUT_CSV)

    print(f"Writing {SUMMARY_MD} ...")
    write_summary_md(groups, output_rows, SUMMARY_MD)

    print("Done.")
    print(f"  Consolidated CSV : {OUTPUT_CSV}")
    print(f"  Summary Markdown : {SUMMARY_MD}")


if __name__ == "__main__":
    main()
