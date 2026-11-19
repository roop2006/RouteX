# Contributing to RouteX

Preserve the route context shared by dashboard views and the existing PostGIS corridor queries. Provider outages must remain visible; missing measurements must not become invented vehicle counts or predictions. Do not train or replace model artifacts as a side effect of tests.

Use Python 3.12 and Node 24 for native development, or the Docker runtime described in the README. Use a disposable database for tests: some older API integration tests intentionally persist fixtures.

Before opening a change:

1. Run the backend regression suite against a disposable PostGIS database, with external transport fixtures for CI.
2. Run frontend lint/build and dependency audits.
3. Run `python deploy/check_repository.py` after staging. Review the staged diff yourself as well.
4. Document configuration, schema or artifact changes. Schema migrations must preserve existing rows.

Never commit `.env`, uploaded videos, database backups, private credentials, or generated observations. Do not load untrusted joblib/pickle files. Release artifacts are verified against `deploy/assets.json`.

The repository currently has no project-wide software license grant. Ask the owner before redistributing project code under a new license; third-party licenses still apply.
