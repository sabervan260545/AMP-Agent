# HydrAMP — Implementation Notes

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

HydrAMP is a conditional VAE that performs:

- **Unconstrained generation** — sample sequences from the learned
  prior to explore novel helical-AMP space.
- **Analog generation** — mutate a seed sequence with a given
  temperature to produce bio-analogs for SAR studies.

Exposes both endpoints as HTTP so the Agent can alternate between
HydrAMP and the main generator (`01-amp-designer`) depending on the
task profile.

## Real model information

| Field         | Value                                                      |
|---------------|------------------------------------------------------------|
| Model name    | HydrAMP                                                    |
| Architecture  | Conditional Variational Autoencoder (CVAE)                 |
| Paper         | Szymczak *et al.*, *Nature Communications*, 2023           |
| Upstream code | https://github.com/szczurek-lab/hydramp                    |
| Weights       | `models/HydrAMP/37/` + `pca_decomposer.joblib`             |
| Licence       | MIT (HydrAMP upstream) — verify before redistribution      |

## Expected API contract (when re-deployed)

| Route                 | Method | Purpose                                 |
|-----------------------|--------|-----------------------------------------|
| `/generate`           | POST   | Unconstrained sampling                  |
| `/generate_analogs`   | POST   | Mutation around a seed sequence         |
| `/health`             | GET    | Service liveness                        |

Service port (host → container): **8008 → 8000**.
Response schema keys (generate): `sequences`, `model`, `time_cost`,
`generated_count`, `conditions`.

## How to deploy the full service

1. Clone `https://github.com/szczurek-lab/hydramp` into
   `services/09-hydramp/` (overwriting this placeholder).
2. `dvc pull` to fetch model weights (or download directly from the
   upstream releases page) into `./data/models/hydramp/`.
3. Provide a FastAPI `app.py` that wraps
   `amp.inference.sampling.unconstrained_generation(...)` and
   `...analog_generation(...)`.
4. Un-comment the `hydramp:` block in `docker-compose.yml`
   (see the *Minimal Release Mode* section in `QUICKSTART.md`).
5. Rebuild: `docker compose build hydramp && docker compose up -d hydramp`.

## Why only a placeholder is shipped

HydrAMP's weights are managed via DVC pointing to an external remote.
Rather than mirroring the large binary blobs here, this release keeps
only the integration contract and defers weight retrieval to the
upstream DVC workflow at deploy time.
