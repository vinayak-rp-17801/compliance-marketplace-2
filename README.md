# Compliance File Processor

A set of Python scripts that process the five zip archives (`1.zip` – `5.zip`) to:

1. **Replace** every standalone occurrence of `"Log360"` (that is not already `"Log360 Cloud"`) with `"Log360 Cloud"`.
2. **Audit** all files for mentions of the following tools:
   - Nessus, Nexpose, Qualys, NMAP, OpenVAS, Malwarebytes, vCenter, PAM360
3. **Generate** two plain-text reports inside the `reports/` directory.

---

## Files

| File | Description |
|---|---|
| `process_files.py` | Main orchestrator – run this script |
| `file_processor.py` | File extraction, text replacement, and tool-mention detection |
| `generate_report.py` | Report-writing module |
| `README.md` | This file |

---

## Requirements

**Python 3.9+** is required.

The scripts use only the Python standard library for core functionality.  
The following *optional* third-party libraries unlock richer file-format support:

| Library | Purpose | Install |
|---|---|---|
| `python-docx` | Read/write `.docx` files | `pip install python-docx` |
| `openpyxl` | Read/write `.xlsx` files | `pip install openpyxl` |
| `python-pptx` | Read/write `.pptx` files | `pip install python-pptx` |
| `pdfplumber` or `pypdf` | Read `.pdf` files (read-only) | `pip install pdfplumber` or `pip install pypdf` |

To install all optional dependencies at once:

```bash
pip install python-docx openpyxl python-pptx pdfplumber
```

---

## Quick Start

```bash
# 1. Clone / navigate to the repository root
cd compliance-marketplace-2

# 2. (Optional) install optional dependencies
pip install python-docx openpyxl python-pptx pdfplumber

# 3. Run the main script (assumes zip files are in the current directory)
python process_files.py
```

Processed files are saved to `output/` and reports to `reports/`.

---

## Command-Line Options

```
python process_files.py [OPTIONS]

Options:
  --zip-dir   DIR    Directory that contains 1.zip … 5.zip
                     (default: current working directory)
  --output    DIR    Root directory for extracted & processed files
                     (default: output/)
  --reports   DIR    Directory where reports are written
                     (default: reports/)
  --zips      NAMES  Comma-separated list of zip file names to process
                     (default: 1.zip,2.zip,3.zip,4.zip,5.zip)
```

### Examples

```bash
# Use default paths (zip files in current dir, output → output/, reports → reports/)
python process_files.py

# Specify custom directories
python process_files.py --zip-dir /data/zips --output /data/processed --reports /data/reports

# Process only certain zips
python process_files.py --zips 1.zip,3.zip
```

---

## Output

### Processed files — `output/`

The directory mirrors the internal structure of each zip archive.  
All supported text-based formats are modified in place; original zip files are not changed.

### Reports — `reports/`

| File | Description |
|---|---|
| `replacement_report.txt` | Every `"Log360"` → `"Log360 Cloud"` substitution, with before/after context |
| `tool_audit_report.txt` | Every tool mention, organised by tool, with file name, occurrence count, and surrounding context |

---

## Supported File Formats

| Format | Replacement | Tool audit |
|---|---|---|
| `.txt`, `.md`, `.html`, `.htm`, `.csv`, `.json`, `.xml`, `.yaml`, `.yml` | ✅ | ✅ |
| `.docx` | ✅ (requires `python-docx`) | ✅ |
| `.xlsx` | ✅ (requires `openpyxl`) | ✅ |
| `.pptx` | ✅ (requires `python-pptx`) | ✅ |
| `.pdf` | ❌ read-only | ✅ (requires `pdfplumber` or `pypdf`) |
| `.doc` (legacy) | ❌ not supported | ❌ |
| Other formats | ❌ skipped | ❌ |

---

## Notes

- The replacement is **context-aware**: it uses a regular expression negative look-ahead (`Log360(?! Cloud)`) so that text already reading `"Log360 Cloud"` is never double-replaced.
- PDF files are scanned for tool mentions but **cannot** be modified in place; if `"Log360"` is found inside a PDF it will be noted in the replacement report under "Skipped Files".
- All errors are logged to `stderr` and noted in the reports, so a single problematic file will not halt the entire run.
