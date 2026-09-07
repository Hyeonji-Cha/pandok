# Türkiye Gateway v2 AWS export

This directory contains the deployable v2 Gateway/export implementation.

Authoritative schema: `../../contracts/telemetry-event-v2.schema.json`.

`reference_exporter.py` is legacy/secondary aggregate-export-v1 reconciliation reference code.
It is not the primary AWS-bound v2 path.

Before production deployment:
1. run repository tests;
2. configure endpoint/token only on the server;
3. run `deploy_v2_aws_export.sh`;
4. run a sanitized non-production AWS E2E;
5. capture deployed hashes with `post_deploy_capture.sh`.
