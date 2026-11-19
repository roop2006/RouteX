# Security, provenance and credits

## Deployment boundary

RouteX is a local single-operator application. There is no login or role enforcement. Alert rules, ingestion, predictions, evaluation and video cancellation are writable endpoints. Keep host listeners on loopback. Before exposing it to other users, add authentication/authorization, TLS, request quotas, upload retention, audit logging and a durable job system. Do not expose Kafka, Redis or PostgreSQL publicly.

Containers use non-root application and nginx users, restricted host bindings, bounded logs and resource limits. The one-shot Kafka volume initializer needs root only to set the data directory owner. PostgreSQL's container entrypoint initializes its database under the image's normal account model. The local single-node Kafka cluster uses plaintext only on the private Compose network; this is not a hardened multi-tenant deployment.

Secrets belong in ignored `.env.docker` files or an operator's secret manager. The backend image context excludes `.env*`; the frontend only receives the public `/api` base path. Do not paste full `docker compose config` or `docker inspect` environment output into logs—use `config --quiet`. Database passwords in URLs must be URL-safe or appropriately encoded. Rotate a password through PostgreSQL as well as configuration; an initialized volume does not change its password when the env file changes.

Uploads are sanitized, extension-checked, limited to 100 MB and decoded before processing. nginx enforces a 101 MB request limit to allow multipart overhead. Backend internal 500 responses are generic; HTTP client request logs are suppressed to avoid query-string credential exposure. Files are stored in a named volume. Job metadata is in memory; stop or finish jobs before backup/cleanup/restart. Cameras and uploaded recordings may contain personal data; obtain authorization and define retention appropriate to the deployment.

## Repository and dependency checks

`deploy/check_repository.py` checks tracked filenames, large files and high-confidence credential signatures, printing only paths. It complements manual review; it is not a proof that no secret exists. Phase 10 also compared configured secrets against changed files and reachable history without printing values. The historical tracked `.env` was empty. No credential rotation was identified as necessary from those checks.

Use `npm audit` and `pip-audit` as documented in CI. Advisory databases change; record scan dates and fix known findings before release. Check application and base-image updates regularly. Base-image tags currently select named runtime release families; record digests from a verified build when reproducing an exact deployment. No image vulnerability result should be inferred from a package audit alone. The final Python environment contains 91 packages: pip-audit audited 89 and skipped the two `+cpu` PyTorch distributions because PyPI does not list those local version suffixes. Separate checks of matching upstream releases torch 2.14.0 and torchvision 0.29.0 found no known advisories. CI currently reports those two skips; repeat the corresponding upstream-release check when updating CPU wheels. Neither check is a binary or operating-system vulnerability assessment.

### Advisory review (2026-11-19)

The earlier full npm audit reported [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) in development dependency picomatch. GitHub withdrew it at 2026-11-18 15:38:56 UTC, confirmed through the public advisory metadata. Fresh full and production-only npm audits on 2026-11-19 both report zero findings. The temporary exception was removed before publication; CI fails on high/critical advisories across the full dependency tree with no exceptions. These are scan-time results, not a guarantee against future advisories.

Model files use Python serialization and can execute code when loaded. Only use the trusted repository artifacts and the pinned upstream YOLO download. SHA-256 verification is in `deploy/assets.json`; never bypass it to load a model from an unknown source. Phase 10 does not train or modify the existing models. Compressed external model bytes expand to the exact original artifact hash.

## Licenses and attribution

The repository has no project-wide software license grant. Phase 10 does not assign one or change repository visibility. Public redistribution requires an owner decision and review of applicable third-party obligations.

| Source | Usage / credit |
|---|---|
| [Ultralytics YOLO11 documentation](https://docs.ultralytics.com/models/yolo11/) and [license](https://github.com/ultralytics/ultralytics/blob/main/LICENSE) | YOLO11n detection weights and runtime. AGPL-3.0; upstream also offers enterprise licensing. Weights download from the versioned `ultralytics/assets` v8.3.0 release and are checksum-verified. |
| [OpenStreetMap copyright and attribution](https://www.openstreetmap.org/copyright) | Map data under ODbL; existing Leaflet attribution must remain visible. Respect tile and geocoding service usage policies. |
| [OSRM project](https://github.com/Project-OSRM/osrm-backend) | External driving route engine. RouteX does not bundle OSM extracts or operate the public routing service. |
| [TomTom Developer Portal](https://developer.tomtom.com/) | Flow, incidents, tiles and optional routing fallback remain subject to the user's account, enabled products, quotas and provider terms. No API credential is redistributed. |
| [Metro Interstate Traffic Volume, UCI](https://archive.ics.uci.edu/dataset/492/metro+interstate+traffic+volume) | John Hogue's interstate traffic dataset, CC BY 4.0, DOI `10.24432/C5X60B`. Existing external-model metadata identifies the training period and evaluation; historical source rows are not bundled. |
| PyTorch, scikit-learn, FastAPI, React, PostgreSQL/PostGIS, Redis, Kafka and other dependencies | Each retains its upstream license. Dependency manifests identify installed versions; inspect distributions for complete license texts. |

No large traffic videos are redistributed. Acceptance tests used an existing local sample; users must supply footage they are permitted to process. CI's generated black-frame clip is explicitly a test fixture, not a real traffic dataset or detection result.
