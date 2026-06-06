# Structure Prediction (ESMFold) — Implementation Notes

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

Predicts a 3D PDB structure from a single peptide sequence and
returns per-residue confidence (pLDDT). Used by downstream
structural-filter and visualisation modules.

## Real model information

| Field         | Value                                                      |
|---------------|------------------------------------------------------------|
| Model name    | ESMFold (v1)                                               |
| Architecture  | ESM-2 (3B) encoder + folding head                          |
| Paper         | Lin *et al.*, *Science*, 2023                              |
| Upstream code | https://github.com/facebookresearch/esm                    |
| Weights       | https://huggingface.co/facebook/esmfold_v1                 |
| Licence       | MIT (check HuggingFace model card before redistribution)   |

## Expected API contract (when re-deployed)

| Route         | Method | Purpose                                    |
|---------------|--------|--------------------------------------------|
| `/fold`       | POST   | Returns PDB text and per-residue pLDDT     |
| `/health`     | GET    | Service liveness + GPU availability flag   |

Service port (host → container): **8006 → 8000**.
Response schema keys (fold): `pdb`, `plddt`, `mean_plddt`, `model`,
`time_cost`.

## How to deploy the full service

1. Clone the upstream repository into `services/07-structure/`
   (overwriting this placeholder).
2. Pre-download the `facebook/esmfold_v1` weights into the shared
   HuggingFace cache (`~/.cache/huggingface/hub`).
3. Provide a FastAPI `app.py` that calls `EsmForProteinFolding`
   or the HuggingFace pipeline equivalent.
4. Un-comment the `structure:` block in `docker-compose.yml`
   (see the *Minimal Release Mode* section in `QUICKSTART.md`).
5. Rebuild: `docker compose build structure && docker compose up -d structure`.

## Why only a placeholder is shipped

ESMFold requires ~10 GB VRAM and >4 GB of weights — bundling them
in a release tarball is impractical and unnecessary because the
weights are directly available on HuggingFace under the original
MIT licence.
