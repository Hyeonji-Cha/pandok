# Unity to PANDOK v2 Integration Plan

## Ownership

| Work | Owner |
|---|---|
| Create gameplay events in Unity | Game developer |
| Send events only to the Türkiye Gateway | Game developer |
| Operate the Türkiye VPS and gateway | Game developer/operator |
| Validate and rebuild allow-listed v2 payloads | Türkiye Gateway |
| Receive v2 events in AWS Sydney | Data engineer |
| Build Bronze, Silver, and Gold | Data engineer |

## AWS-Bound Event Rules

- Supported events: `upgrade_options_shown`, `upgrade_selected`, `run_started`,
  `run_checkpoint`, and `run_ended`
- Required order fields: `event_sequence` and `run_elapsed_seconds`
- Required Run-scoped identities: `run_id`, `event_id`, and `choice_id` when applicable
- Forbidden: player, account, Session, installation, device, IP/header, exact
  client timestamp, and free-form text fields
- `session_started` remains outside the AWS contract

## Integration Order

1. Validate controlled v2 events locally.
2. Store validated events in local Bronze records.
3. Reconstruct Runs locally with `validate_anonymous_sequence()`.
4. Deploy the Sydney ingestion endpoint with production export disabled.
5. Send controlled v2 events through the Türkiye Gateway.
6. Verify Bronze, Silver, and Gold with synthetic data.
7. Enable consented testing on a password-protected Steam beta branch only after operational and
   privacy controls are confirmed.

## Required Evidence Before Production

- Unity never falls back to direct AWS transmission.
- Gateway logs do not store raw bodies or client IP headers.
- AWS rejects prohibited fields and unsupported event types.
- Retries keep the same logical event identity.
- Production, controlled-scenario, and load-test data remain separated through
  `source_type`.
