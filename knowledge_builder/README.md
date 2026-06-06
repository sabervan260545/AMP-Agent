# AMP Knowledge Base Builder

> **Goal**: turn a collection of AMP literature (PDF / TXT) into a
> structured, vectorised knowledge base consumable by the Agent.
> **Stack**: Python · pdfplumber · sentence-transformers · ChromaDB
> **Typical effort**: 2–3 days for an initial corpus

---

## ⚠️ Notice — Proprietary literature is NOT shipped

The `raw_documents/` and `raw_literature/` folders in this release **do
not contain the real literature corpus**. The upstream papers used to
seed the internal knowledge base are under publisher copyright and/or
project NDA, and therefore:

- they have been **removed from this public release**;
- they are listed in `.gitignore` so an accidental `git add .` will not
  republish them;
- only `example.txt` (raw) and `example.json` (processed) remain as
  **format specimens** — they are intentionally tiny and synthetic.

If you are a project member who needs the original corpus, obtain it
from the internal share (see the private handover doc), drop the files
into `raw_documents/`, and run the pipeline in [§ Usage workflow](#-usage-workflow).

---

## 📚 Literature manifest *(placeholder — to be filled later)*

The canonical list of papers consumed by the knowledge base will be
maintained in this section once the team finalises the citation audit.

| # | Citation | DOI / URL | Notes |
|---|----------|-----------|-------|
| 1 | *(pending)* | *(pending)* | *(pending)* |
| … | …           | …           | …           |

> **TODO**: replace this table with the full literature list. Keep the
> papers themselves outside the repository; only metadata (title / DOI /
> year / licence) goes here.

---

## 🧱 Overall architecture

```
AMP Knowledge Base
│
├── [1] Raw literature
│       ├── PDF files
│       ├── TXT files
│       └── Web content
│
├── [2] Structured data
│       ├── sequences
│       ├── design_patterns
│       ├── mechanisms
│       └── bacterial_targets
│
├── [3] Vectorised index (ChromaDB)
│       ├── literature collection
│       ├── MIC collection
│       ├── CPP collection
│       └── hemolysis collection
│
└── [4] Retrieval API  →  consumed by agent/knowledge_retriever.py
```

Three scripts glue the stages together — all live in this directory:

| Script | Role |
|--------|------|
| `prepare_raw_json.py`     | Stage 1 → 2 raw pre-processing (PDF/TXT → JSON envelope) |
| `run_pdf_processing.py`   | Stage 2 knowledge extraction (JSON → structured `literature_knowledge.json`) |
| `literature_processor.py` | Library module used by the two scripts above |
| `rebuild_index.py`        | Stage 3 vectorisation (ChromaDB index rebuild) |

---

## 🚀 Usage workflow

### 0. Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | local run |
| Docker 24+   | container run (recommended) |
| `pip install -r requirements.txt` | pdfplumber · tqdm · pandas · sentence-transformers · chromadb |
| ≥ 4 GB free RAM | `all-MiniLM-L6-v2` embeddings |
| Disk: ~1 GB per 100 papers | raw + processed + vector cache |

### 1. Drop your literature into `raw_documents/`

```bash
cd knowledge_builder

# Accepted formats:
#   - TXT  (plain text, UTF-8 preferred, GBK tolerated)
#   - PDF  (parsed via pdfplumber)
cp /path/to/*.txt /path/to/*.pdf raw_documents/
```

If your sources are PDFs, you can either let `prepare_raw_json.py` do
the extraction directly (it supports PDFs) or pre-convert them with
any external tool of your choice.

### 2. Pre-process raw → JSON

```bash
python prepare_raw_json.py
# ⇢ writes one JSON envelope per file into raw_literature/
```

Each output JSON has the shape:

```json
{
  "source":  "AMP_review.txt",
  "title":   "AMP_review",
  "content": "<cleaned full text>",
  "metadata": { "file_type": ".txt", "original_size": 123456, "processed_by": "prepare_raw_json.py" }
}
```

At this point you may **hand-edit** the JSONs to fix OCR artefacts,
trim boiler-plate, or stitch multi-column PDFs together. Quality in =
quality out.

### 3. Extract structured knowledge

```bash
python run_pdf_processing.py
# ⇢ writes integrated_knowledge_base/01_literature_knowledge/literature_knowledge.json
# ⇢ also emits a flat CSV preview alongside the JSON
```

Behind the scenes, `AMPLiteratureProcessor` (in `literature_processor.py`)
extracts:

- peptide sequences (6-50 canonical AA, filtered by heuristic)
- MIC values with unit normalisation (→ µM)
- **design_principles**, **action_mechanisms**, **target_organisms**
  via a bilingual keyword dictionary (EN + ZH, so Chinese reviews
  contribute too)

### 4. Rebuild the ChromaDB vector index

```bash
python rebuild_index.py
# ⇢ populates agent/vector_store/  (or /app/agent/vector_store in Docker)
# ⇢ four collections: literature / mic / cpp / hemolysis
```

The script imports `KnowledgeRetriever` from the `agent/` package and
calls `index_literature_knowledge() / index_mic_data() /
index_cpp_data() / index_hemolysis_data()` in sequence.

### 🐳 Alternative — run the whole pipeline in Docker

A minimal `dockerfile` is provided in this directory:

```bash
# From the repository root
docker build -t amp-knowledge-builder ./knowledge_builder
docker run --rm \
  -v "$PWD/knowledge_builder/raw_documents:/app/raw_documents" \
  -v "$PWD/knowledge_builder/raw_literature:/app/raw_literature" \
  -v "$PWD/knowledge_builder/integrated_knowledge_base:/app/integrated_knowledge_base" \
  amp-knowledge-builder
```

The default `CMD` runs `run_pdf_processing.py`. Override it with
`python rebuild_index.py` for the vectorisation step.

---

## 📦 Output layout

After a full pipeline run the directory looks like:

```
knowledge_builder/
├── raw_documents/                          # your PDF / TXT inputs (git-ignored)
├── raw_literature/                         # cleaned JSON envelopes (git-ignored)
└── integrated_knowledge_base/
    ├── 01_literature_knowledge/
    │   ├── literature_knowledge.json       # canonical structured corpus
    │   └── literature_knowledge.csv        # flat preview for humans
    ├── 02_cpp_data/                        # curated CPP dataset
    ├── 03_mic_data/                        # curated MIC dataset
    ├── 04_hemolysis_data/                  # curated hemolysis dataset
    ├── 05_statistics/                      # build-time stats
    ├── 06_motif_patterns/                  # positive/negative motif libraries
    └── vector_store/                       # ChromaDB index (git-ignored)
```

`vector_store/` is always rebuilt from the structured JSONs and is
therefore **not committed**.

---

## 🔌 Consuming the knowledge base

Once the index exists, the Agent retrieves from it via
`agent/knowledge_retriever.py`:

```python
from knowledge_retriever import KnowledgeRetriever

kr = KnowledgeRetriever()

# Semantic query across all collections
hits = kr.query(
    "amphipathic helical peptides effective against E. coli",
    top_k=5,
)

for h in hits:
    print(h["collection"], h["score"], h["metadata"]["source"])
```

Typical consumers:

- **Agent planning**: retrieve design principles matching the user's goal
- **Structure discrimination**: pull reference MIC / hemolysis values
- **Closed-loop optimisation**: fetch similar peptides for in-context learning

---

## 🔄 Extending the knowledge base

To add new papers:

1. Drop the PDF/TXT into `raw_documents/`
2. Re-run `prepare_raw_json.py` — only *new* files will be (re)emitted
3. Re-run `run_pdf_processing.py` — merges into the existing corpus
4. Re-run `rebuild_index.py` — refreshes ChromaDB

Version the `integrated_knowledge_base/` directory alongside the code
(minus `vector_store/`), so downstream services get a reproducible
snapshot.

---

## 📝 Notes & best practices

### Literature quality control

- Prefer **open-access full-text** over abstracts (richer signal).
- Prefer papers that publish **actual sequences + MIC numbers**, not
  just qualitative claims.
- Blacklist noisy OCR dumps — a single bad file can poison extraction.

### Data cleaning

```python
# Drop duplicate sequences
df = df.drop_duplicates("sequence")

# Reject implausible rows
df = df[(df.length.between(6, 100)) & (df.mic > 0)]
```

### Scaling beyond ~1000 papers

- Switch `prepare_raw_json.py` to a multiprocessing pool.
- Move the `ChromaDB` persistence dir onto an SSD volume.
- Consider sharding `literature_knowledge.json` by publication year.

### Copyright & redistribution

- The **code** in this directory is released under the repository's
  top-level MIT licence.
- The **literature corpus** you feed into this directory is **not** —
  respect each paper's publisher terms before redistributing the
  processed JSONs, and never commit the raw PDFs to a public repo.

---

## 🔗 Reference resources

### AMP databases

- APD3 — <https://aps.unmc.edu/>
- DBAASP — <https://dbaasp.org/>
- DRAMP — <http://dramp.cpu-bioinfor.org/>

### Literature sources

- PubMed — <https://pubmed.ncbi.nlm.nih.gov/>
- bioRxiv — <https://www.biorxiv.org/>
- Google Scholar — <https://scholar.google.com/>

---

## ✅ Checklist

- [ ] Copyright / NDA review of every new paper before ingestion
- [ ] `raw_documents/` and `raw_literature/` remain git-ignored
- [ ] `example.txt` / `example.json` kept as format specimens only
- [ ] Literature manifest table populated with title + DOI + licence
- [ ] `integrated_knowledge_base/` committed; `vector_store/` not
- [ ] `rebuild_index.py` re-run after any corpus change
