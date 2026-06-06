# Hemolysis Prediction — Implementation Notes

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

Scores how likely a candidate peptide is to lyse human red blood cells
(hemolytic probability). Used as a toxicity filter in the
generation → filtering → ranking pipeline.

## Real model information

| Field         | Value                                                      |
|---------------|------------------------------------------------------------|
| Model name    | HemoPI2                                                    |
| Architecture  | Classical ML (sklearn / XGBoost) on amino-acid descriptors |
| Paper         | Kumar *et al.*, *Briefings in Bioinformatics*, 2022        |
| Upstream code | `<TO_BE_PROVIDED_BEFORE_RELEASE>`                          |
| Weights       | `hemopi2_ml_clf.sav` + descriptor pickle                   |
| Licence       | Academic / check upstream before redistribution            |

## Expected API contract (when re-deployed)

| Route       | Method | Purpose                                        |
|-------------|--------|------------------------------------------------|
| `/predict`  | POST   | Batch hemolytic-probability scoring            |
| `/health`   | GET    | Service liveness                               |

Service port (host → container): **8004 → 8000**.
Response schema keys (prediction): `predictions`,
`predictions[].hemolytic_probability`,
`predictions[].is_hemolytic`, `model`, `time_cost`.

## How to deploy the full service

1. Clone the upstream repository into `services/05-hemolysis/`
   (overwriting this placeholder).
2. Download the sklearn classifier weights into
   `./data/models/hemolysis/` (mount path referenced by the restored
   `docker-compose.yml` block).
3. Provide a FastAPI `app.py` that loads the classifier and computes
   descriptors on the fly.
4. Un-comment the `hemolysis:` block in `docker-compose.yml`
   (see the *Minimal Release Mode* section in `QUICKSTART.md`).
5. Rebuild: `docker compose build hemolysis && docker compose up -d hemolysis`.

## Why only a placeholder is shipped

The HemoPI2 weights and descriptor tables are distributed under the
upstream project's own terms. To keep the release licence-unambiguous
they are not bundled — deployers fetch them from the upstream source.
