#!/usr/bin/env python3
"""
process_files.py
----------------
Main orchestrator script.

Usage
-----
    python process_files.py [OPTIONS]

Options
-------
  --zip-dir   DIR   Directory that contains 1.zip … 5.zip
                    (default: current working directory)
  --output    DIR   Root directory for extracted & processed files
                    (default: output/)
  --reports   DIR   Directory where reports are written
                    (default: reports/)
  --zips      NAMES Comma-separated list of zip file names to process
                    (default: 1.zip,2.zip,3.zip,4.zip,5.zip)

Example
-------
    python process_files.py
    python process_files.py --zip-dir /path/to/zips --output out --reports rpts
"""

import argparse
import logging
import os
import sys
import tempfile

import file_processor
import generate_report

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_files(directory: str) -> list[str]:
    """Walk *directory* and return all regular file paths (sorted)."""
    paths = []
    for root, _dirs, files in os.walk(directory):
        for name in files:
            paths.append(os.path.join(root, name))
    return sorted(paths)


def _dest_path(src: str, extract_root: str, output_root: str) -> str:
    """
    Map an extracted file path to its output destination.

    Example
    -------
    src          = /tmp/xyz/1.zip_contents/subdir/file.txt
    extract_root = /tmp/xyz
    output_root  = output/
    dest         = output/1.zip_contents/subdir/file.txt
    """
    rel = os.path.relpath(src, extract_root)
    return os.path.join(output_root, rel)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Process zip files: replace 'Log360' and audit tool mentions."
    )
    parser.add_argument(
        "--zip-dir",
        default=".",
        metavar="DIR",
        help="Directory containing the zip files (default: current directory).",
    )
    parser.add_argument(
        "--output",
        default="output",
        metavar="DIR",
        help="Root output directory for processed files (default: output/).",
    )
    parser.add_argument(
        "--reports",
        default="reports",
        metavar="DIR",
        help="Directory for generated reports (default: reports/).",
    )
    parser.add_argument(
        "--zips",
        default="1.zip,2.zip,3.zip,4.zip,5.zip",
        metavar="NAMES",
        help="Comma-separated zip file names to process.",
    )
    args = parser.parse_args(argv)

    zip_names = [z.strip() for z in args.zips.split(",") if z.strip()]
    zip_paths = []
    for name in zip_names:
        full = os.path.join(args.zip_dir, name)
        if not os.path.isfile(full):
            logger.warning("Zip file not found, skipping: %s", full)
        else:
            zip_paths.append(full)

    if not zip_paths:
        logger.error("No zip files found in '%s'. Aborting.", args.zip_dir)
        return 1

    os.makedirs(args.output, exist_ok=True)
    os.makedirs(args.reports, exist_ok=True)

    all_results: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="file_processor_") as tmp_dir:
        for zip_path in zip_paths:
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            extract_dir = os.path.join(tmp_dir, zip_name)
            os.makedirs(extract_dir, exist_ok=True)

            logger.info("Extracting %s …", zip_path)
            try:
                file_processor.extract_zip(zip_path, extract_dir)
            except Exception as exc:
                logger.error("Failed to extract %s: %s", zip_path, exc)
                continue

            extracted_files = _collect_files(extract_dir)
            logger.info(
                "Processing %d file(s) from %s …", len(extracted_files), zip_path
            )

            for src in extracted_files:
                dest = _dest_path(src, tmp_dir, args.output)
                result = file_processor.process_file(src, dest)
                all_results.append(result)

                n_rep = len(result["replacements"])
                n_tool = len(result["tool_mentions"])
                skipped = f"  [SKIPPED: {result['skip_reason']}]" if result["skipped"] else ""
                logger.info(
                    "  %-60s  replacements=%-4d  tool_mentions=%-4d%s",
                    os.path.relpath(src),
                    n_rep,
                    n_tool,
                    skipped,
                )

    # ---- Summary --------------------------------------------------------
    total_files = len(all_results)
    total_rep = sum(len(r["replacements"]) for r in all_results)
    total_mentions = sum(len(r["tool_mentions"]) for r in all_results)

    logger.info("─" * 60)
    logger.info("Files processed   : %d", total_files)
    logger.info("Total replacements: %d", total_rep)
    logger.info("Total tool mentions: %d", total_mentions)
    logger.info("─" * 60)

    # ---- Reports --------------------------------------------------------
    replacement_report_path = os.path.join(args.reports, "replacement_report.txt")
    tool_audit_report_path = os.path.join(args.reports, "tool_audit_report.txt")

    generate_report.write_replacement_report(all_results, replacement_report_path)
    generate_report.write_tool_audit_report(all_results, tool_audit_report_path)

    logger.info("Done.  Reports saved to '%s/'.", args.reports)
    return 0


if __name__ == "__main__":
    sys.exit(main())
