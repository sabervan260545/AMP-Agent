# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Literature Processor (Level-4 Enhanced Edition)
====================================================
Responsibilities:
1. Extract content from PDF / TXT literature files.
2. Emit a knowledge-graph-friendly standardised JSON envelope.
3. Normalise every tag to a canonical English key, even when the source
   text is written in Chinese (keyword dictionaries below contain both
   English and Chinese triggers on purpose — do not strip the Chinese
   entries unless you also remove Chinese PDFs from the corpus).
4. Retain theoretical papers that contain design principles but no
   explicit peptide sequences.
"""

import json
import re
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
import pandas as pd
from datetime import datetime


class AMPLiteratureProcessor:
    """AMP literature processor tailored for Agent consumption."""

    def __init__(self, literature_dir: str = "raw_literature"):
        self.literature_dir = Path(literature_dir)
        self.literature_dir.mkdir(exist_ok=True)

        # Sequence pattern: 6..50 canonical amino acids
        self.sequence_pattern = re.compile(r'\b([ACDEFGHIKLMNPQRSTVWY]{6,50})\b')

        # MIC pattern (supports multiple unit spellings)
        self.mic_pattern = re.compile(
            r'MIC[^\d]*([\d.]+)\s*(μM|uM|µM|μg/ml|ug/ml)',
            re.IGNORECASE
        )

    def process_literature(self, text: str, source: str) -> Dict[str, Any]:
        """Process a single paper and return a JSON-ready structured object."""
        # 1. Base extractions
        sequences = self.extract_sequences(text)
        mic_data = self.extract_mic_data(text)

        # 2. Normalised tag extractions
        patterns = self.extract_design_patterns(text)
        targets = self.extract_bacterial_targets(text)
        mechanisms = self.extract_mechanisms(text)

        # 3. Assemble the Knowledge Document envelope.
        #    A nested structure is preferred over a flat CSV because it maps
        #    cleanly onto both RAG retrieval and a knowledge-graph schema.
        doc_structure = {
            "metadata": {
                "source": source,
                "file_type": "literature",
                "processed_date": datetime.now().isoformat(),
                "has_sequences": len(sequences) > 0,
                "has_experimental_data": len(mic_data) > 0
            },
            "knowledge_core": {
                # Core principles (Level-4 focus: still valuable even without
                # experimental sequences).
                "design_principles": patterns,
                "action_mechanisms": [m["mechanism"] for m in mechanisms],
                "target_organisms": targets,
            },
            "evidence_bank": {
                # Experimental evidence (ground truth)
                "extracted_sequences": sequences,   # Includes surrounding context
                "experimental_values": mic_data,
                "mechanism_details": mechanisms     # Includes descriptive snippet
            }
        }

        return doc_structure

    def extract_sequences(self, text: str) -> List[Dict]:
        """Extract candidate peptide sequences with their context."""
        sequences = []
        matches = self.sequence_pattern.findall(text)

        # De-duplicate
        unique_matches = set(matches)

        for seq in unique_matches:
            # Simple sanity filter: plain uppercase English words often
            # match the AA regex by accident; require at least one common
            # AMP residue (K/L/A/R/G) to cut down on false positives.
            if any(aa in seq for aa in 'KLARG'):
                sequences.append({
                    "sequence": seq,
                    "length": len(seq),
                    # A surrounding snippet helps downstream consumers judge
                    # whether the match is really an AMP.
                    "context_snippet": self._get_context(text, seq, window=50)
                })

        return sequences

    def extract_mic_data(self, text: str) -> List[Dict]:
        """Extract MIC values and attempt unit normalisation."""
        mic_data = []
        matches = self.mic_pattern.finditer(text)

        for match in matches:
            try:
                raw_value = float(match.group(1))
                unit = match.group(2).lower()
                normalized_value = raw_value

                # Rough unit conversion assuming an average MW of ~1500 Da:
                #   1 ug/ml == 1000 mg/L / 1500 g/mol ≈ 0.67 uM
                # The result is stored as `normalized_value_uM` for a
                # uniform comparison basis.
                if 'g/ml' in unit:
                    normalized_value = raw_value / 1.5

                mic_data.append({
                    "original_value": raw_value,
                    "original_unit": unit,
                    "normalized_value_uM": round(normalized_value, 2),
                    "context": self._get_context(text, match.group(0), window=100)
                })
            except ValueError:
                continue

        return mic_data

    def extract_design_patterns(self, text: str) -> List[str]:
        """Extract design patterns (normalised into canonical English keys)."""
        patterns = []

        # Mapping: canonical English key -> [English triggers, Chinese triggers]
        # The Chinese triggers are intentional: they let us harvest knowledge
        # from Chinese PDFs without relying on an upstream translation step.
        pattern_keywords = {
            "amphipathic_helix": ["amphipathic helix", "α-helix", "helical structure", "两亲性螺旋", "α螺旋"],
            "cationic_enhancement": ["cationic", "positive charge", "net charge", "阳离子", "正电荷"],
            "hydrophobic_balance": ["hydrophobicity", "hydrophobic moment", "疏水性", "疏水力矩"],
            "cyclization_stability": ["cyclic", "cyclization", "disulfide bond", "环状", "二硫键", "成环"],
            "tryptophan_anchoring": ["tryptophan", "trp-rich", "membrane interface", "色氨酸"],
            "arginine_rich": ["arginine-rich", "poly-arginine", "cell penetration", "富精氨酸"],
        }

        text_lower = text.lower()

        for std_name, keywords in pattern_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    patterns.append(std_name)
                    # One hit is enough — break out of the inner loop.
                    break

        return list(set(patterns))

    def extract_bacterial_targets(self, text: str) -> List[str]:
        """Extract target bacteria (normalised into canonical English keys)."""
        targets = []

        bacteria_keywords = {
            "Gram-negative": ["gram-negative", "g-", "革兰氏阴性"],
            "Gram-positive": ["gram-positive", "g+", "革兰氏阳性"],
            "E.coli": ["e.coli", "escherichia coli", "大肠杆菌"],
            "S.aureus": ["s.aureus", "staphylococcus aureus", "金黄色葡萄球菌"],
            "P.aeruginosa": ["p.aeruginosa", "pseudomonas aeruginosa", "铜绿假单胞菌"],
            "K.pneumoniae": ["k.pneumoniae", "klebsiella pneumoniae", "肺炎克雷伯菌"],
            "A.baumannii": ["a.baumannii", "acinetobacter baumannii", "鲍曼不动杆菌"]
        }

        text_lower = text.lower()

        for std_name, keywords in bacteria_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    targets.append(std_name)
                    break

        return list(set(targets))

    def extract_mechanisms(self, text: str) -> List[Dict]:
        """Extract mechanisms with context (normalised into canonical English keys)."""
        mechanisms = []

        mechanism_keywords = {
            "membrane_disruption": ["membrane disruption", "permeabilization", "leakage", "膜破坏", "膜通透"],
            "pore_formation": ["pore formation", "toroidal", "barrel-stave", "carpet model", "成孔", "孔道"],
            "intracellular_targeting": ["dna binding", "ribosome", "metabolic", "inhibit synthesis", "胞内靶点"],
            "immune_modulation": ["immune", "cytokine", "chemokine", "inflammation", "免疫调节", "抗炎"]
        }

        text_lower = text.lower()

        for std_name, keywords in mechanism_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # Capture the sentence in which the trigger appears.
                    context = self._get_context(text, keyword, window=200)
                    mechanisms.append({
                        "mechanism": std_name,
                        "description_snippet": context
                    })
                    break

        return mechanisms

    def _get_context(self, text: str, keyword: str, window: int = 100) -> str:
        """Return a cleaned-up context window around `keyword` inside `text`."""
        pos = text.lower().find(keyword.lower())
        if pos == -1:
            return ""

        start = max(0, pos - window)
        end = min(len(text), pos + len(keyword) + window)

        raw_snippet = text[start:end]
        # Collapse whitespace so the snippet stays JSON-friendly.
        clean_snippet = re.sub(r'\s+', ' ', raw_snippet).strip()
        return f"...{clean_snippet}..."

    def batch_process(self, file_list: List[str]) -> List[Dict]:
        """
        Process a list of literature files in batch.

        Selection policy: a paper is kept if it yields at least one of
        {design_principle, action_mechanism, sequence}. Everything else
        is treated as noise and discarded.
        """
        all_docs = []
        print(f"🔄 Batch processing {len(file_list)} file(s)...")

        for filepath in file_list:
            try:
                # Tolerate either UTF-8 or legacy GBK sources
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        text = f.read()
                except UnicodeDecodeError:
                    with open(filepath, 'r', encoding='gbk') as f:
                        text = f.read()

                # Extract the structured Knowledge Document
                doc = self.process_literature(text, os.path.basename(filepath))

                # 🌟 Level-4 gating rule:
                # Drop a paper only if it contributes *nothing* —
                # no sequence, no principle, no mechanism. Any one of the
                # three is enough to keep the document.
                has_knowledge = (
                    len(doc["knowledge_core"]["design_principles"]) > 0 or
                    len(doc["knowledge_core"]["action_mechanisms"]) > 0 or
                    len(doc["evidence_bank"]["extracted_sequences"]) > 0
                )

                if has_knowledge:
                    all_docs.append(doc)
                    print(f"  ✅ [kept]  {os.path.basename(filepath)} — knowledge extracted")
                else:
                    print(f"  ⚠️ [skip]  {os.path.basename(filepath)} — no AMP knowledge recovered")

            except Exception as e:
                print(f"  ❌ [error] {filepath}: {e}")

        return all_docs

    def save_structured_data(self, data: List[Dict], output_path: str):
        """
        Persist the structured corpus.

        Writes a canonical JSON file plus a flattened CSV preview for humans.
        """
        # 1. Canonical JSON (primary artefact, full hierarchy preserved)
        json_path = output_path if output_path.endswith('.json') else output_path + '.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Saved structured knowledge to: {json_path} (JSON)")

        # 2. Flat CSV preview (one row per sequence for easy spreadsheet review)
        try:
            csv_rows = []
            for doc in data:
                # Base columns shared across all rows for this paper
                base_info = {
                    "source": doc["metadata"]["source"],
                    "principles": ",".join(doc["knowledge_core"]["design_principles"]),
                    "mechanisms": ",".join(doc["knowledge_core"]["action_mechanisms"]),
                    "targets": ",".join(doc["knowledge_core"]["target_organisms"])
                }

                # One CSV row per extracted sequence
                sequences = doc["evidence_bank"]["extracted_sequences"]
                if sequences:
                    for s in sequences:
                        row = base_info.copy()
                        row["sequence"] = s["sequence"]
                        row["seq_length"] = s["length"]
                        csv_rows.append(row)
                else:
                    # Theory-only paper: keep a single placeholder row
                    row = base_info.copy()
                    row["sequence"] = "N/A (Theory Only)"
                    csv_rows.append(row)

            csv_path = json_path.replace('.json', '.csv')
            pd.DataFrame(csv_rows).to_csv(csv_path, index=False)
            print(f"📄 CSV preview written to: {csv_path}")

        except Exception as e:
            print(f"⚠️ CSV preview generation failed (non-fatal): {e}")


# ==================== Self-test ====================

if __name__ == "__main__":
    # A synthetic paragraph that deliberately mixes English and Chinese
    # triggers so both keyword families get exercised in CI.
    sample_text = """
    We proposed a new strategy called 'hydrophobic balance' to design AMPs.
    The peptide KLLKLLKKLLKLLK showed high activity against E.coli.
    MIC was determined to be 4.5 μM.
    The mechanism implies membrane disruption via pore formation.
    Additionally, we avoided tryptophan anchoring to reduce hemolysis.
    我们还发现，增加阳离子电荷（cationic enhancement）能提高对革兰氏阴性菌的杀伤力。
    """

    processor = AMPLiteratureProcessor()
    result = processor.process_literature(sample_text, "test_paper_v4.txt")

    print("\n🔍 Level-4 extraction self-test result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
