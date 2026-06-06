# ESM-2 — Implementation Notes

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

Exposes Meta AI's ESM-2 protein language model as an HTTP microservice
for on-demand residue-level and sequence-level embeddings consumed by
the downstream ranker and the structure microservice.

## Real model information

| Field         | Value                                                      |
|---------------|------------------------------------------------------------|
| Model name    | ESM-2 (`esm2_t33_650M_UR50D` and related checkpoints)      |
| Architecture  | Transformer encoder language model (~650 M params)         |
| Paper         | Lin *et al.*, *Science*, 2023                              |
| Upstream code | `<TO_BE_PROVIDED_BEFORE_RELEASE>`                          |
| Weights       | https://huggingface.co/facebook/esm2_t33_650M_UR50D        |
| Licence       | MIT (check HuggingFace model card before redistribution)   |

## Expected API contract (when re-deployed)

| Route       | Method | Purpose                                        |
|-------------|--------|------------------------------------------------|
| `/embed`    | POST   | Per-sequence or per-residue embedding vectors  |
| `/health`   | GET    | Service liveness                               |

This service is **not exposed as a dedicated port** in the current
`docker-compose.yml` (embeddings are consumed in-process by
`07-structure/` or `01-amp-designer/`). If redeployed as a standalone
service, choose an unused internal port and add a new compose block.

## How to deploy the full service

1. Clone the upstream repository into `services/02-esm2/`
   (overwriting this placeholder).
2. Pre-download the HuggingFace weights into the shared cache
   (`~/.cache/huggingface/hub`) so the container picks them up
   offline.
3. Provide a FastAPI `app.py` exposing `/embed` and `/health`.
4. Add a `esm2:` block to `docker-compose.yml` on an unused port.

## Why only a placeholder is shipped

The release does not bundle large third-party transformer weights
(the ESM-2 650 M checkpoint alone is >2 GB). Redistributing them is
unnecessary — users can fetch them directly from HuggingFace.
