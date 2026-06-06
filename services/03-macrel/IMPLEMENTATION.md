# Macrel — Implementation Notes

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

Classifies candidate peptide sequences as antimicrobial vs
non-antimicrobial and, internally, ensembles two signals:

1. **Macrel** (Santos-Júnior *et al.*) — classical feature-based
   classifier invoked via CLI.
2. **PGAT-ABPp** (optional secondary opinion) — graph-attention
   model with ProtT5 embeddings.

Returns a combined confidence score used as the first-stage filter in
the generation → filtering → ranking pipeline.

## Real model information

| Field         | Value                                                      |
|---------------|------------------------------------------------------------|
| Primary model | Macrel                                                     |
| Architecture  | Feature engineering + Random Forest / XGBoost classifier   |
| Paper         | Santos-Júnior *et al.*, *PeerJ*, 2020                      |
| Upstream code | `<TO_BE_PROVIDED_BEFORE_RELEASE>`                          |
| PyPI          | https://pypi.org/project/macrel/                           |
| Weights       | Bundled inside the Macrel PyPI package                     |
| Licence       | MIT (Macrel) — verify before redistribution                |
| Secondary     | PGAT-ABPp (see `services/11-pgat-abpp/IMPLEMENTATION.md`)  |

## Expected API contract (when re-deployed)

| Route         | Method | Purpose                                    |
|---------------|--------|--------------------------------------------|
| `/predict`    | POST   | Batch AMP / non-AMP classification         |
| `/health`     | GET    | Service liveness                           |

Service port (host → container): **8002 → 8000**.
Response schema keys (prediction): `predictions`, `model`,
`time_cost`, `total_sequences`.

## How to deploy the full service

1. Clone the upstream repository into `services/03-macrel/`
   (overwriting this placeholder).
2. `pip install macrel` inside the Docker image (see upstream
   Dockerfile for the full dependency list).
3. Provide a FastAPI `app.py` that shells out to `macrel peptides`
   and aggregates the output per request.
4. Un-comment the `macrel:` block in `docker-compose.yml`
   (see the *Minimal Release Mode* section in `QUICKSTART.md`).
5. Rebuild: `docker compose build macrel && docker compose up -d macrel`.

## Why only a placeholder is shipped

Macrel is third-party software with its own licence. Rather than
redistributing its binary and bundled classifier weights, this
release documents the integration contract and lets the deployer
install Macrel from its official channel. The PGAT-ABPp secondary
signal is similarly placeholder-only (see its own
`IMPLEMENTATION.md`).
