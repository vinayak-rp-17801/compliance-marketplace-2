# Compliance Marketplace Document Processing

This repository contains scripts to process compliance documentation by
replacing "Log360" references with "Log360 Cloud" and auditing documents for
mentions of specific security tools.

---

## Files

| File | Description |
|------|-------------|
| `1.zip` – `5.zip` | Original source compliance documents (~95 `.docx` files) |
| `output-documents.zip` | Processed documents with "Log360" → "Log360 Cloud" replacements applied |
| `add_screenshots.py` | Script that performs the Log360 → Log360 Cloud replacement and packages `output-documents.zip` |
| `audit_tools.py` | Script that scans `output-documents.zip` and generates the tool audit report |
| `TOOL_AUDIT_REPORT.md` | Generated audit report listing where each security tool is mentioned |

---

## Log360 → Log360 Cloud Replacement

The replacement script (`add_screenshots.py`) extracts all `.docx` files from
the five source zip files, replaces every standalone "Log360" occurrence with
"Log360 Cloud" (skipping text already reading "Log360 Cloud"), and packages
the results into `output-documents.zip`.

```bash
# Prerequisites
pip install python-docx

# Run the replacement
python3 add_screenshots.py
```

---

## Tool Audit Report

The audit script (`audit_tools.py`) extracts `output-documents.zip`, scans
every document for mentions of the following eight security tools, and
generates `TOOL_AUDIT_REPORT.md`.

**Tools audited:**
1. Nessus
2. Nexpose
3. Qualys
4. NMAP
5. OpenVAS
6. Malwarebytes
7. vCenter
8. PAM360

### Running the Audit

```bash
# Prerequisites (python-docx must be installed)
pip install python-docx

# Run from the repository root (where output-documents.zip lives)
python3 audit_tools.py
```

The script will:
1. Extract all `.docx` files from `output-documents.zip` into a temporary
   directory.
2. Scan each document for whole-word matches of the eight tools above.
3. Write `TOOL_AUDIT_REPORT.md` to the repository root.
4. Print a concise summary to the terminal.

### Report Contents

`TOOL_AUDIT_REPORT.md` contains three sections:

- **Summary** – A table showing, for each tool, how many files mention it and
  the total number of occurrences.
- **Detailed Findings** – For each tool: a file-by-file occurrence count and
  up to three sample excerpts showing the surrounding context.
- **Cross-Reference** – A table of files that mention more than one of the
  audited tools.

> **Note:** Re-running the script regenerates `TOOL_AUDIT_REPORT.md` and
> updates the timestamp automatically.
