# Gateway → AWS server-to-server authentication interface (sanitized)

No real credentials or production endpoint are included.

Configuration:
- `PANDOK_AWS_EXPORT_ENABLED=1`
- `PANDOK_AWS_EXPORT_URL=https://<AWS-INGEST-ENDPOINT>/...`
- `PANDOK_AWS_EXPORT_TOKEN_PATH=/etc/pandok-gateway/aws-export-token`
- optional timeout/retry variables documented in README

Outbound request:

```http
POST <PANDOK_AWS_EXPORT_URL>
Content-Type: application/json
Authorization: Bearer <SERVER_TO_SERVER_TOKEN>
X-Pandok-Contract: telemetry-event-v2
X-Pandok-Contract-Blob-SHA: 4336417ea4107e4e9597ecddbcf989f38a240f7f
Idempotency-Key: <event_id UUID>

<exact validated telemetry-event-v2 JSON object>
```

The AWS receiver should authenticate the bearer credential over TLS and treat `Idempotency-Key`/`event_id` as idempotent for retry safety. Do not log the Authorization header.
