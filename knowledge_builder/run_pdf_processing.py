# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP literature batch-processing script (Docker edition)
=======================================================
Walks the `raw_literature/` directory, extracts structured knowledge
from each document via AMPLiteratureProcessor, and writes the consolidated
output to `integrated_knowledge_base/01_literature_knowledge/`.
"""

import os
import json
import glob
import pdfplumber
from pathlib import Path
from tqdm import tqdm
from literature_processor import AMPLiteratureProcessor


def extract_text_from_pdf(pdf_path):
    """Extract plain text from a PDF file."""
    text_content = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
        return "\n".join(text_content)
    except Exception as e:
        print(f"❌ PDF parsing failed {pdf_path}: {e}")
        return ""


def load_raw_json(json_path):
    """Load a raw JSON file and return (text, source_name)."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, dict):
            text = data.get("content") or data.get("text") or data.get("body") or str(data)
            source = data.get("source", json_path.name)
            return text, source
        else:
            return str(data), json_path.name
    except Exception as e:
        print(f"❌ JSON read failed {json_path}: {e}")
        return "", ""


def main():
    # ==========================================
    # 🔧 Path configuration (tuned for in-container paths)
    # ==========================================
    # The Docker container's WORKDIR is /app; volumes are mounted under
    # /app/<subdir> — so a relative base_dir (`.`) resolves correctly both
    # inside the container and when invoked from the host workspace root.
    base_dir = Path(".")

    raw_dir = base_dir / "raw_literature"
    output_file = base_dir / "integrated_knowledge_base" / "01_literature_knowledge" / "literature_knowledge.json"

    print(f"📂 CWD         : {os.getcwd()}")
    print(f"📂 Scanning dir: {raw_dir.absolute()}")

    # Ensure the output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Initialise the processor
    processor = AMPLiteratureProcessor()

    # Collect input files
    if not raw_dir.exists():
        print(f"❌ Error: directory does not exist {raw_dir}")
        print("💡 Verify that docker-compose.yml mounts ./knowledge_builder/raw_literature to /app/raw_literature")
        return

    json_files = list(raw_dir.glob("*.json"))
    pdf_files = list(raw_dir.glob("*.pdf"))
    txt_files = list(raw_dir.glob("*.txt"))

    all_files = json_files + pdf_files + txt_files

    print(f"📚 Found {len(all_files)} raw file(s):")
    print(f"   - JSON (raw): {len(json_files)}")
    print(f"   - PDF       : {len(pdf_files)}")
    print(f"   - TXT       : {len(txt_files)}")

    processed_docs = []

    # Run the extractor
    print("\n🚀 Starting conversion + extraction...")
    for file_path in tqdm(all_files):
        try:
            filename = file_path.name
            text = ""
            source_name = filename

            # A. Handle JSON
            if file_path.suffix.lower() == '.json':
                text, src = load_raw_json(file_path)
                if src:
                    source_name = src

            # B. Handle PDF
            elif file_path.suffix.lower() == '.pdf':
                text = extract_text_from_pdf(file_path)
                if len(text) < 100:
                    print(f"   ⚠️ [skip] {filename} — content too small")
                    continue

            # C. Handle TXT (try UTF-8, fall back to GBK)
            elif file_path.suffix.lower() == '.txt':
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                except UnicodeDecodeError:
                    with open(file_path, 'r', encoding='gbk') as f:
                        text = f.read()

            # D. Dispatch to the processor
            if text:
                doc = processor.process_literature(text, source_name)
                has_knowledge = (
                    doc["knowledge_core"]["design_principles"] or
                    doc["knowledge_core"]["action_mechanisms"] or
                    doc["evidence_bank"]["extracted_sequences"]
                )

                if has_knowledge:
                    processed_docs.append(doc)

        except Exception as e:
            print(f"   ❌ processing failed {filename}: {e}")

    # Persist results
    if processed_docs:
        print(f"\n💾 Saving {len(processed_docs)} structured document(s)...")
        processor.save_structured_data(processed_docs, str(output_file))
        print(f"✅ Done. Output path: {output_file}")
    else:
        print("\n⚠️ No valid data was extracted.")


if __name__ == "__main__":
    main()
