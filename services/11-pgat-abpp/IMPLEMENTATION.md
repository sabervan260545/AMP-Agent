# PGAT-ABPp — Implementation Notes

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

Scores candidate peptides with the PGAT-ABPp graph-attention
classifier, which operates on ProtT5 residue embeddings plus a
contact-map-derived graph. Provides a secondary opinion to the
`03-macrel` service and, for structure-ranking workflows, directly
consumes PDBs from `07-structure`.

## Real model information

| Field         | Value                                                      |
|---------------|------------------------------------------------------------|
| Model name    | PGAT-ABPp                                                  |
| Architecture  | Graph Attention Network over ProtT5 embeddings             |
| Paper         | `<TO_BE_PROVIDED_BEFORE_RELEASE>`                          |
| Upstream code | `<TO_BE_PROVIDED_BEFORE_RELEASE>`                          |
| Weights       | `PGAT-ABPp-main/predict/pgat_abpp.h5`                      |
| ProtT5 deps   | `Rostlab/prot_t5_xl_uniref50` (HuggingFace)                |
| Licence       | See original repository                                    |

## Expected API contract (when re-deployed)

| Route       | Method | Purpose                                        |
|-------------|--------|------------------------------------------------|
| `/predict`  | POST   | Batch PGAT scoring (CSV-of-sequences + PDBs)   |
| `/health`   | GET    | Service liveness                               |

Service port (host → container): **8010 → 8000**.
Response schema keys (predict): `predictions`,
`predictions[].sequence`, `predictions[].pgat_score`,
`predictions[].is_amp`, `model`, `time_cost`.

## How to deploy the full service

1. Clone the PGAT-ABPp upstream repository into
   `services/11-pgat-abpp/PGAT-ABPp-main/` (overwriting this
   placeholder).
2. Download `pgat_abpp.h5` into `PGAT-ABPp-main/predict/`
   and pre-cache the ProtT5 weights into `~/.cache/huggingface/hub`.
3. Provide a FastAPI `app.py` that exposes the API contract above
   and mounts PDBs from `./data/pgat_runs/<job_id>/`.
4. Un-comment the `amp-pgat-abpp:` block in `docker-compose.yml`
   (see the *Minimal Release Mode* section in `QUICKSTART.md`).
5. Rebuild: `docker compose build amp-pgat-abpp && docker compose up -d amp-pgat-abpp`.

## Why only a placeholder is shipped

The PGAT-ABPp codebase together with its datasets (~150 MB of zipped
training / independent test sets and a bundled Keras HDF5 weight file)
was the single largest third-party payload in the old release. It is
entirely governed by a separate upstream licence, so shipping it here
would create mixed-licence ambiguity. Deployers should fetch the
official upstream distribution on demand.
