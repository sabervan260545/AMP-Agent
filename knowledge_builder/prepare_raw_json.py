# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Raw-data pre-processing script (PDF/TXT -> cleaned JSON)
========================================================
Pipeline:
1. Scan the `raw_documents/` folder for original PDF / TXT files.
2. Extract plain text from each file.
3. Apply basic cleaning (strip garbage bytes, collapse whitespace, etc.).
4. Wrap every document into a standard JSON envelope.
5. Emit the result into `raw_literature/` for downstream processors.
"""

import os
import json
import re
import pdfplumber
from pathlib import Path
from tqdm import tqdm

# ================= Configuration =================
INPUT_DIR = Path("raw_documents")     # Original PDF/TXT sources
OUTPUT_DIR = Path("raw_literature")   # Cleaned JSON destination
# ==================================================


def clean_text(text: str) -> str:
    """
    Core text-cleaning routine.

    Customise the rules below to match the quality of your raw corpus.
    """
    if not text:
        return ""

    # 1. Normalise line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 2. Drop invisible characters (keep newlines).
    #    Uncomment the next line to restrict to pure ASCII:
    # text = re.sub(r'[^\x20-\x7E\n]', '', text)

    # 3. Collapse consecutive spaces / tabs
    text = re.sub(r'[ \t]+', ' ', text)

    # 4. Collapse runs of blank lines (keep at most one blank line)
    text = re.sub(r'\n\s*\n', '\n\n', text)

    return text.strip()


def extract_from_pdf(pdf_path):
    """Extract plain text from a PDF using pdfplumber."""
    full_text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
        return "\n".join(full_text)
    except Exception as e:
        print(f"❌ PDF parsing failed: {pdf_path.name} - {e}")
        return ""


def process_file(file_path):
    """Process a single input file (PDF or TXT)."""
    filename = file_path.name
    text = ""

    # Read file content
    if file_path.suffix.lower() == '.pdf':
        text = extract_from_pdf(file_path)
    elif file_path.suffix.lower() == '.txt':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            # Fallback for legacy GBK-encoded files
            with open(file_path, 'r', encoding='gbk') as f:
                text = f.read()

    if not text:
        return

    # Clean
    cleaned_content = clean_text(text)

    # Wrap into a JSON envelope
    json_data = {
        "source": filename,
        "title": file_path.stem,  # Defaults to the file stem; edit manually if needed.
        "content": cleaned_content,
        "metadata": {
            "file_type": file_path.suffix,
            "original_size": file_path.stat().st_size,
            "processed_by": "prepare_raw_json.py"
        }
    }

    # Persist
    output_path = OUTPUT_DIR / f"{file_path.stem}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)


def main():
    # 1. Ensure I/O directories exist
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 2. Discover input files
    all_files = list(INPUT_DIR.glob("*.pdf")) + list(INPUT_DIR.glob("*.txt"))

    print(f"🚀 Pre-processing start: found {len(all_files)} raw file(s)")
    print(f"📂 Input  dir: {INPUT_DIR}")
    print(f"📂 Output dir: {OUTPUT_DIR}")

    # 3. Batch conversion
    for f in tqdm(all_files):
        process_file(f)

    print(f"\n✅ Conversion finished. Inspect the JSON files under {OUTPUT_DIR}.")
    print("💡 Tip: you can hand-edit the generated JSONs to fine-tune the `content` field before indexing.")


if __name__ == "__main__":
    main()
