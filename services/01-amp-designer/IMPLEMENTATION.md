# AMP-Designer — Implementation Notes

## Status: 🧭 Directory Placeholder Only

This service directory is an **architectural placeholder**. No
implementation code is shipped in this release — not even a stub.
Only this `IMPLEMENTATION.md` file exists so the repository layout,
`docker-compose.yml` service topology and inter-service contracts
stay visible and documented.

To run the end-to-end platform, clone the upstream implementation
listed below into this directory (or point a compatible microservice
at the same port and API contract).

## What this service is supposed to do

Accepts an optional natural-language / property prompt and returns a
batch of antimicrobial-peptide (AMP) candidate sequences, plus an
optional per-residue embedding endpoint used by downstream ranking.

## Real model information

| Field         | Value                                                      |
|---------------|------------------------------------------------------------|
| Model name    | AMP-Designer / AMP-GPT                                     |
| Architecture  | GPT-2 + Soft-Prompt-Tuning                                 |
| Paper         | Wang *et al.*, *Science Advances*, 2025                    |
| Reported perf | 94.4 % success rate, *in vivo* mouse validation            |
| Upstream code | `<TO_BE_PROVIDED_BEFORE_RELEASE>`                          |
| Weights       | https://zenodo.org/records/17018363                        |
| Licence       | See original repository                                    |

## Expected API contract (when re-deployed)

| Route            | Method | Purpose                                |
|------------------|--------|----------------------------------------|
| `/generate`      | POST   | Batch AMP-sequence generation          |
| `/embedding`     | POST   | 1024-dim per-residue compat. embedding |
| `/health`        | GET    | Service liveness + model-type tag      |
| `/info`          | GET    | Static metadata for UI discovery       |

Service port (host → container): **8001 → 8001**.
Response schema keys (generation): `sequences`, `model`, `time_cost`,
`generated_count`, `conditions`.

## How to deploy the full service

1. Clone the upstream repository into `services/01-amp-designer/`
   (overwriting this placeholder).
2. Download the weights from the Zenodo record above into
   `./data/models/amp-prompt/prompt_model` (mount path referenced by
   the restored `docker-compose.yml` block).
3. Provide a FastAPI `app.py` that matches the contract above and
   exposes `/health`.
4. Un-comment the `generator:` block in `docker-compose.yml`
   (see the *Minimal Release Mode* section in `QUICKSTART.md`).
5. Rebuild: `docker compose build generator && docker compose up -d generator`.

## Why only a placeholder is shipped

The upstream model and training data are governed by a third-party
licence that differs from this release's MIT licence. To avoid
mixed-licence ambiguity, all model code, weights and training data
are distributed separately through the upstream links above.
