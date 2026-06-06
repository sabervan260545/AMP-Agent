# Scripts Directory

Auxiliary one-shot scripts that live **outside** the runtime codebase.

## Layout

```
scripts/
└── setup/
    ├── check_env.py              # Sanity-check the local Python / Docker env
    ├── build_amp_rag.py          # Build the amp_knowledge_base/ pickle corpus
    └── build_simple_amp_rag.py   # Lightweight variant (no sentence-transformers)
```

## Usage

```bash
# Verify the local environment
python scripts/setup/check_env.py

# (Optional) rebuild the pickle-based knowledge bundle under amp_knowledge_base/
python scripts/setup/build_amp_rag.py
```

> ℹ️ The **vector store** used by the Agent at runtime is a separate
> ChromaDB index managed by `knowledge_builder/rebuild_index.py`.
> The scripts in this directory only (re)generate the static pickle
> corpus under `amp_knowledge_base/`.
