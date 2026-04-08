import csv
import os
import re
import tempfile
import zipfile

from docx import Document

OUTPUT_ZIP = "output-documents.zip"
REPORT_TXT = "DETAILED_TOOL_FILES_REPORT.txt"
REPORT_CSV = "tool_mentions.csv"

TOOLS = ["Nessus", "Nexpose", "Qualys", "NMAP", "OpenVAS", "Malwarebytes", "vCenter", "PAM360"]

# Pre-compiled case-insensitive word-boundary patterns for each tool
TOOL_PATTERNS = {
    tool: re.compile(r"(?i)\b" + re.escape(tool) + r"\b") for tool in TOOLS
}

CONTEXT_CHARS = 25


def extract_text_lines(doc_path):
    """
    Extract all text from a DOCX file and return as a list of lines.
    Includes text from body paragraphs and table cells.
    """
    doc = Document(doc_path)
    lines = []

    for paragraph in doc.paragraphs:
        lines.append(paragraph.text)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    lines.append(paragraph.text)

    return lines


def find_tool_mentions(lines, tool):
    """
    Search for a tool name (case-insensitive word-boundary match) in a list of lines.
    Returns a list of dicts with: line_number, excerpt, raw_line.
    """
    pattern = TOOL_PATTERNS[tool]
    mentions = []

    for line_num, line in enumerate(lines, start=1):
        for match in pattern.finditer(line):
            start = max(0, match.start() - CONTEXT_CHARS)
            end = min(len(line), match.end() + CONTEXT_CHARS)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(line) else ""
            excerpt = prefix + line[start:end] + suffix
            mentions.append({
                "line_number": line_num,
                "excerpt": excerpt,
            })

    return mentions


def build_report(doc_files_dir):
    """
    Scan all DOCX files in doc_files_dir for each tool.
    Returns a dict keyed by tool name, each containing a list of file-match records.
    """
    results = {tool: [] for tool in TOOLS}

    doc_files = sorted(
        f for f in os.listdir(doc_files_dir) if f.endswith(".docx")
    )

    for doc_file in doc_files:
        doc_path = os.path.join(doc_files_dir, doc_file)
        try:
            lines = extract_text_lines(doc_path)
        except Exception as exc:
            print(f"  WARNING: Could not read {doc_file}: {exc}")
            continue

        for tool in TOOLS:
            mentions = find_tool_mentions(lines, tool)
            if mentions:
                results[tool].append({
                    "file_path": doc_path,
                    "filename": doc_file,
                    "occurrences": len(mentions),
                    "mentions": mentions,
                })

    return results


def write_txt_report(results, output_path):
    """Write the human-readable DETAILED_TOOL_FILES_REPORT.txt."""
    separator = "\u2500" * 45

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("DETAILED TOOL FILES REPORT\n")
        f.write("=" * 45 + "\n\n")

        for tool in TOOLS:
            file_records = results[tool]
            f.write(f"TOOL: {tool}\n")
            f.write(f"Files Found: {len(file_records)}\n")
            f.write(separator + "\n")

            if not file_records:
                f.write("  NOT FOUND in any document.\n")
            else:
                for idx, record in enumerate(file_records, start=1):
                    f.write(f"File {idx}: {record['file_path']}\n")
                    f.write(f"  Filename: {record['filename']}\n")
                    f.write(f"  Occurrences: {record['occurrences']}\n")
                    for mention in record["mentions"]:
                        f.write(f"  Line {mention['line_number']}: \"{mention['excerpt']}\"\n")
                    f.write("\n")

            f.write("\n")


def write_csv_report(results, output_path):
    """Write the tool_mentions.csv file."""
    fieldnames = ["Tool", "File_Path", "Filename", "Occurrences", "Line_Numbers", "First_Context_Excerpt"]

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for tool in TOOLS:
            file_records = results[tool]
            if not file_records:
                writer.writerow({
                    "Tool": tool,
                    "File_Path": "",
                    "Filename": "",
                    "Occurrences": 0,
                    "Line_Numbers": "",
                    "First_Context_Excerpt": "NOT FOUND",
                })
            else:
                for record in file_records:
                    line_numbers = ", ".join(
                        str(m["line_number"]) for m in record["mentions"]
                    )
                    first_excerpt = record["mentions"][0]["excerpt"] if record["mentions"] else ""
                    writer.writerow({
                        "Tool": tool,
                        "File_Path": record["file_path"],
                        "Filename": record["filename"],
                        "Occurrences": record["occurrences"],
                        "Line_Numbers": line_numbers,
                        "First_Context_Excerpt": first_excerpt,
                    })


def print_summary(results):
    """Print a summary table to stdout."""
    print("\n" + "=" * 55)
    print(f"{'Tool':<15} {'Files':>8} {'Occurrences':>12}")
    print("-" * 55)
    for tool in TOOLS:
        file_records = results[tool]
        total_occ = sum(r["occurrences"] for r in file_records)
        print(f"{tool:<15} {len(file_records):>8} {total_occ:>12}")
    print("=" * 55 + "\n")


def main():
    if not os.path.exists(OUTPUT_ZIP):
        print(f"ERROR: '{OUTPUT_ZIP}' not found. Please run add_screenshots.py first.")
        return

    print("=" * 55)
    print("Extracting output-documents.zip ...")
    print("=" * 55)

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs_dir = os.path.join(tmp_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)

        with zipfile.ZipFile(OUTPUT_ZIP, "r") as z:
            for item in z.namelist():
                if "__MACOSX" in item or item.split("/")[-1].startswith("._"):
                    continue
                if item.endswith(".docx"):
                    target = os.path.join(docs_dir, os.path.basename(item))
                    with z.open(item) as src, open(target, "wb") as dst:
                        dst.write(src.read())

        extracted = [f for f in os.listdir(docs_dir) if f.endswith(".docx")]
        print(f"Extracted {len(extracted)} documents.\n")

        print("Scanning documents for tool mentions ...")
        results = build_report(docs_dir)

        print_summary(results)

        write_txt_report(results, REPORT_TXT)
        print(f"Detailed text report written to: {REPORT_TXT}")

        write_csv_report(results, REPORT_CSV)
        print(f"CSV report written to:           {REPORT_CSV}")

    print("\nDone.")


if __name__ == "__main__":
    main()
