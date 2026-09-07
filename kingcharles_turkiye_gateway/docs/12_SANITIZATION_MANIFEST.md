# Sanitization manifest

Excluded from this release/handoff ZIP:

- production API/ingest/export tokens and credentials
- `.env` files
- production endpoint values and server public IP addresses
- real player data
- actual SQLite database files
- TLS/SSH private keys
- production logs

Source/config documentation contains only secret **interface names/paths/placeholders**, never real secret values. Synthetic examples use intentionally fake credentials and RFC-style/synthetic UUIDs.
