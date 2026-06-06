# MIC Prediction — Implementation Notes

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

Regresses the minimum inhibitory concentration (MIC, in µg/mL) of a
candidate peptide against a specified strain. Internally it was a
three-head ensemble fused with fixed weights:

- **BiLSTM head** (context-aware sequence encoder) — weight 0.4
- **CNN head** (k-mer convolutional features) — weight 0.3
- **MBM head** (motif-based descriptor) — weight 0.3

## Real model information

| Field         | Value                                                      |
|---------------|------------------------------------------------------------|
| Model name    | AMP-MIC-3Ensemble (internal)                               |
| Architecture  | CNN + BiLSTM + MBM fused via fixed convex weights          |
| Paper         | `<TO_BE_PROVIDED_BEFORE_RELEASE>`                          |
| Upstream code | `<TO_BE_PROVIDED_BEFORE_RELEASE>`                          |
| Weights       | `T5_Three_CNN_40.h5`, `T5_Three_Bi_40.h5`, `T5_Three_MB_40.h5` |
| Training data | Curated subset of DBAASP v3                                |
| Licence       | MIT (weights kept out of this release for size)            |

## Expected API contract (when re-deployed)

| Route       | Method | Purpose                                           |
|-------------|--------|---------------------------------------------------|
| `/predict`  | POST   | Batch MIC regression (log10 MIC µM)               |
| `/health`   | GET    | Service liveness + sub-model availability flags   |

Service port (host → container): **8003 → 8000**.
Response schema keys (prediction): `predictions`,
`predictions[].mic_value`, `predictions[].log_mic`,
`predictions[].sub_model_scores`, `model`, `time_cost`.

## How to deploy the full service

1. Clone the upstream repository into `services/04-mic/`
   (overwriting this placeholder).
2. Download the three `.h5` weight files into
   `./data/models/mic/` (mount path referenced by the restored
   `docker-compose.yml` block).
3. Provide a FastAPI `app.py` that loads the three sub-models and
   fuses their outputs with the 0.4 / 0.3 / 0.3 weights.
4. Un-comment the `mic:` block in `docker-compose.yml`
   (see the *Minimal Release Mode* section in `QUICKSTART.md`).
5. Rebuild: `docker compose build mic && docker compose up -d mic`.

## Why only a placeholder is shipped

The trained weights depend on curated DBAASP-derived training data
whose redistribution terms are under review. Shipping only the
deployment contract keeps the release licence-clean while letting
the deployer wire in either the original weights or a drop-in
replacement regressor.
