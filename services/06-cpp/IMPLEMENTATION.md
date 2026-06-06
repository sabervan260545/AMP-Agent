# Cell-Penetrating Peptide (CPP) Prediction — Implementation Notes

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

Predicts whether a candidate peptide is cell-penetrating (CPP) —
used as a permeability filter for intracellular-target AMPs.

## Real model information

| Field         | Value                                                      |
|---------------|------------------------------------------------------------|
| Model name    | CPPpred (TPC / CTD feature family)                         |
| Architecture  | Classical ML (sklearn) on tri-peptide composition          |
| Paper         | Manavalan *et al.*, *Briefings in Bioinformatics*          |
| Upstream code | `<TO_BE_PROVIDED_BEFORE_RELEASE>`                          |
| Weights       | `model_cat1_TPC.pkl` + feature transformer pickle          |
| Licence       | Academic / check upstream before redistribution            |

## Expected API contract (when re-deployed)

| Route       | Method | Purpose                                        |
|-------------|--------|------------------------------------------------|
| `/predict`  | POST   | Batch CPP-probability scoring                  |
| `/health`   | GET    | Service liveness                               |

Service port (host → container): **8005 → 8000**.
Response schema keys (prediction): `predictions`,
`predictions[].cpp_probability`, `predictions[].is_cpp`,
`model`, `time_cost`.

## How to deploy the full service

1. Clone the upstream repository into `services/06-cpp/`
   (overwriting this placeholder).
2. Download the classifier weights into
   `./data/models/cpp/` (mount path referenced by the restored
   `docker-compose.yml` block).
3. Provide a FastAPI `app.py` that loads the classifier and the
   TPC / CTD feature extractors.
4. Un-comment the `cpp:` block in `docker-compose.yml`
   (see the *Minimal Release Mode* section in `QUICKSTART.md`).
5. Rebuild: `docker compose build cpp && docker compose up -d cpp`.

## Why only a placeholder is shipped

The upstream classifier and its feature tables ship under their own
academic licence. To keep the release licence-unambiguous they are
not bundled — deployers fetch them from the upstream source.
