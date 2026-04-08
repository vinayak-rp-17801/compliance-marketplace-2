"""
file_processor.py
-----------------
Helper module for extracting text from various file formats and performing
in-place text replacements where possible.

Supported formats (read + replace):
  .txt  .md  .html  .htm  .csv  .json  .xml  .yaml  .yml

Supported formats (read-only, replacement skipped with a warning):
  .docx  .xlsx  .pptx  .pdf

All other formats are skipped.
"""

import os
import re
import logging
import zipfile
import shutil

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports – only used when the matching file types are present.
# ---------------------------------------------------------------------------

def _try_import(module_name):
    try:
        import importlib
        return importlib.import_module(module_name)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Regex that matches "Log360" NOT followed by " Cloud" (case-sensitive).
# A negative look-ahead ensures we don't double-replace.
LOG360_PATTERN = re.compile(r"Log360(?! Cloud)")

TOOLS = [
    "Nessus",
    "Nexpose",
    "Qualys",
    "NMAP",
    "OpenVAS",
    "Malwarebytes",
    "vCenter",
    "PAM360",
]

# ---------------------------------------------------------------------------
# Zip extraction
# ---------------------------------------------------------------------------


def extract_zip(zip_path: str, dest_dir: str) -> list[str]:
    """Extract *zip_path* into *dest_dir* and return list of extracted paths."""
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            zf.extract(member, dest_dir)
            extracted.append(os.path.join(dest_dir, member))
    logger.info("Extracted %d files from %s", len(extracted), zip_path)
    return extracted


# ---------------------------------------------------------------------------
# Text-based file helpers
# ---------------------------------------------------------------------------


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _write_text(path: str, content: str) -> None:
    try:
        with open(path, "w", encoding="utf-8", errors="strict") as fh:
            fh.write(content)
    except UnicodeEncodeError:
        # Fall back to surrogateescape so the file can still be written
        # without silently replacing characters.
        with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(content)
        logger.warning(
            "Surrogate characters encountered while writing %s; "
            "some characters may be represented as escape sequences.",
            path,
        )


def _replace_in_text(content: str) -> tuple[str, list[dict]]:
    """
    Replace every standalone 'Log360' (not already 'Log360 Cloud') with
    'Log360 Cloud'.  Returns (new_content, list_of_replacement_records).

    Each record: {"line": int, "before": str, "after": str}
    """
    records = []
    lines = content.split("\n")
    new_lines = []
    for lineno, line in enumerate(lines, start=1):
        new_line, count = LOG360_PATTERN.subn("Log360 Cloud", line)
        if count:
            records.append({"line": lineno, "before": line, "after": new_line})
        new_lines.append(new_line)
    return "\n".join(new_lines), records


# ---------------------------------------------------------------------------
# DOCX support
# ---------------------------------------------------------------------------


def _process_docx(path: str) -> tuple[str, list[dict], list[dict]]:
    """
    Process a .docx file.
    Returns (full_text, replacement_records, tool_mention_records).
    Replacements ARE written back to the file.
    """
    docx = _try_import("docx")
    if docx is None:
        logger.warning("python-docx not installed – skipping %s", path)
        return "", [], []

    doc = docx.Document(path)
    replacement_records = []
    full_text_parts = []

    for para in doc.paragraphs:
        full_text_parts.append(para.text)
        for run in para.runs:
            if LOG360_PATTERN.search(run.text):
                old = run.text
                new = LOG360_PATTERN.sub("Log360 Cloud", run.text)
                run.text = new
                replacement_records.append({"paragraph": para.text[:80], "before": old, "after": new})

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                full_text_parts.append(cell.text)
                for para in cell.paragraphs:
                    for run in para.runs:
                        if LOG360_PATTERN.search(run.text):
                            old = run.text
                            new = LOG360_PATTERN.sub("Log360 Cloud", run.text)
                            run.text = new
                            replacement_records.append(
                                {"paragraph": para.text[:80], "before": old, "after": new}
                            )

    if replacement_records:
        doc.save(path)

    full_text = "\n".join(full_text_parts)
    tool_records = find_tool_mentions(full_text)
    return full_text, replacement_records, tool_records


# ---------------------------------------------------------------------------
# XLSX support
# ---------------------------------------------------------------------------


def _process_xlsx(path: str) -> tuple[str, list[dict], list[dict]]:
    """Process a .xlsx file (replacements written back)."""
    openpyxl = _try_import("openpyxl")
    if openpyxl is None:
        logger.warning("openpyxl not installed – skipping %s", path)
        return "", [], []

    wb = openpyxl.load_workbook(path)
    replacement_records = []
    full_text_parts = []

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    full_text_parts.append(cell.value)
                    if LOG360_PATTERN.search(cell.value):
                        old = cell.value
                        cell.value = LOG360_PATTERN.sub("Log360 Cloud", cell.value)
                        replacement_records.append(
                            {
                                "sheet": ws.title,
                                "cell": cell.coordinate,
                                "before": old,
                                "after": cell.value,
                            }
                        )

    if replacement_records:
        wb.save(path)

    full_text = "\n".join(full_text_parts)
    tool_records = find_tool_mentions(full_text)
    return full_text, replacement_records, tool_records


# ---------------------------------------------------------------------------
# PPTX support
# ---------------------------------------------------------------------------


def _process_pptx(path: str) -> tuple[str, list[dict], list[dict]]:
    """Process a .pptx file (replacements written back)."""
    pptx = _try_import("pptx")
    if pptx is None:
        logger.warning("python-pptx not installed – skipping %s", path)
        return "", [], []

    prs = pptx.Presentation(path)
    replacement_records = []
    full_text_parts = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                full_text_parts.append(para.text)
                for run in para.runs:
                    if LOG360_PATTERN.search(run.text):
                        old = run.text
                        run.text = LOG360_PATTERN.sub("Log360 Cloud", run.text)
                        replacement_records.append(
                            {"slide": slide_num, "before": old, "after": run.text}
                        )

    if replacement_records:
        prs.save(path)

    full_text = "\n".join(full_text_parts)
    tool_records = find_tool_mentions(full_text)
    return full_text, replacement_records, tool_records


# ---------------------------------------------------------------------------
# PDF support (read-only – PDFs are not modified)
# ---------------------------------------------------------------------------


def _read_pdf(path: str) -> str:
    """Extract text from a PDF (read-only; replacements are not written back)."""
    pdfplumber = _try_import("pdfplumber")
    if pdfplumber is not None:
        try:
            with pdfplumber.open(path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            logger.warning("pdfplumber failed on %s: %s", path, exc)

    pypdf = _try_import("pypdf")
    if pypdf is not None:
        try:
            reader = pypdf.PdfReader(path)
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception as exc:
            logger.warning("pypdf failed on %s: %s", path, exc)

    logger.warning("No PDF library available – cannot read %s", path)
    return ""


# ---------------------------------------------------------------------------
# Tool-mention scanning
# ---------------------------------------------------------------------------

# Build a case-insensitive pattern that matches each tool as a whole word.
_TOOL_PATTERNS = {
    tool: re.compile(r"\b" + re.escape(tool) + r"\b", re.IGNORECASE)
    for tool in TOOLS
}

CONTEXT_CHARS = 120  # characters of context around each mention


def find_tool_mentions(text: str) -> list[dict]:
    """
    Return a list of records for every tool mention found in *text*.
    Each record: {"tool": str, "context": str, "pos": int}
    """
    records = []
    for tool, pattern in _TOOL_PATTERNS.items():
        for match in pattern.finditer(text):
            start = max(0, match.start() - CONTEXT_CHARS // 2)
            end = min(len(text), match.end() + CONTEXT_CHARS // 2)
            records.append(
                {
                    "tool": tool,
                    "context": text[start:end].replace("\n", " "),
                    "pos": match.start(),
                }
            )
    return records


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

TEXT_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".csv", ".json", ".xml", ".yaml", ".yml"}


def process_file(src_path: str, dest_path: str) -> dict:
    """
    Process a single file:
      - Copy to *dest_path* (preserving directory structure).
      - Perform Log360 → Log360 Cloud replacements where possible.
      - Scan for tool mentions.

    Returns a result dict:
      {
        "src": str,
        "dest": str,
        "ext": str,
        "replacements": list[dict],
        "tool_mentions": list[dict],
        "skipped": bool,
        "skip_reason": str | None,
      }
    """
    result = {
        "src": src_path,
        "dest": dest_path,
        "ext": os.path.splitext(src_path)[1].lower(),
        "replacements": [],
        "tool_mentions": [],
        "skipped": False,
        "skip_reason": None,
    }

    # Ensure destination directory exists.
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    ext = result["ext"]

    try:
        if ext in TEXT_EXTENSIONS:
            shutil.copy2(src_path, dest_path)
            content = _read_text(dest_path)
            new_content, replacements = _replace_in_text(content)
            if replacements:
                _write_text(dest_path, new_content)
            result["replacements"] = replacements
            result["tool_mentions"] = find_tool_mentions(new_content)

        elif ext == ".docx":
            shutil.copy2(src_path, dest_path)
            _, replacements, tool_mentions = _process_docx(dest_path)
            result["replacements"] = replacements
            result["tool_mentions"] = tool_mentions

        elif ext == ".xlsx":
            shutil.copy2(src_path, dest_path)
            _, replacements, tool_mentions = _process_xlsx(dest_path)
            result["replacements"] = replacements
            result["tool_mentions"] = tool_mentions

        elif ext == ".pptx":
            shutil.copy2(src_path, dest_path)
            _, replacements, tool_mentions = _process_pptx(dest_path)
            result["replacements"] = replacements
            result["tool_mentions"] = tool_mentions

        elif ext == ".pdf":
            shutil.copy2(src_path, dest_path)
            text = _read_pdf(dest_path)
            result["tool_mentions"] = find_tool_mentions(text)
            if LOG360_PATTERN.search(text):
                result["skip_reason"] = (
                    "PDF contains 'Log360' but in-place replacement is not "
                    "supported for PDF files."
                )
            result["skipped"] = bool(result["skip_reason"])

        elif ext in (".doc",):
            shutil.copy2(src_path, dest_path)
            result["skipped"] = True
            result["skip_reason"] = (
                ".doc (legacy Word) format is not supported. "
                "Please convert to .docx first."
            )

        else:
            shutil.copy2(src_path, dest_path)
            result["skipped"] = True
            result["skip_reason"] = f"Unsupported file type: {ext!r}"

    except Exception as exc:
        logger.error("Error processing %s: %s", src_path, exc, exc_info=True)
        result["skipped"] = True
        result["skip_reason"] = str(exc)

    return result
