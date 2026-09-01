# Telemetry Privacy Threat Model

This document identifies how PANDOK gameplay telemetry could become linkable to a player and defines the
technical controls and tests required before production collection. It exists to prevent design assumptions
from being treated as proof of anonymity and is not a legal determination.

## Scope

The protected boundary begins when the Game Client creates a telemetry event and ends after validated Gold
metrics are supplied to the LLM. The review covers the Game Client, local queue, Türkiye VPS and provider,
Nginx, FastAPI Privacy Gateway, outbound request, AWS API Gateway, Lambda, CloudWatch, Kinesis, Flink,
Firehose, failed-record paths, S3 Bronze and Silver, Airflow, Gold metrics, backups, and LLM inputs.

## Privacy objectives

Using only data accessible in AWS Sydney, an operator or service must not be able to:

- identify a Steam account, person, device, installation, or player IP;
- determine that two Runs came from the same player;
- reconstruct original request headers or authentication data;
- use logs, failures, backups, or observability systems to bypass payload controls.

Run-internal linkage remains permitted only through identifiers that are freshly generated for that Run and
never mapped to a player or another Run.

## Trust assumptions that require evidence

- The Game Client never reads identity data for telemetry construction.
- The Türkiye VPS is physically located in Türkiye.
- The provider does not export request bodies, client IP logs, snapshots, or observability data abroad in a
  way that contradicts the approved configuration.
- Nginx and FastAPI do not record raw requests or player IPs.
- The Gateway creates a new outbound request and does not transparently proxy incoming headers.
- AWS receives the Gateway network identity, not the player's network identity.
- Future schema changes cannot bypass the field allow-list and forbidden-field guard.

These are testable or reviewable requirements, not facts until deployment evidence exists.

## Risk scale

| Rating | Meaning |
|---|---|
| `HIGH` | Can directly expose or reliably link a player, account, device, IP, or separate Runs |
| `MEDIUM` | Can increase singling-out or correlation risk when combined with other data |
| `LOW` | Limited identification value after required controls, but still requires regression testing |

## Threat analysis

| Risk | Path | Rating | Impact | Required control | Verification | Residual risk |
|---|---|---:|---|---|---|---|
| Direct Game-to-AWS connection | Client bypasses the Türkiye Gateway or uses AWS as a fallback | `HIGH` | AWS receives the player's source IP and request metadata | Ship only the Türkiye endpoint; store no AWS endpoint or credential in the client; disable direct fallback | Inspect the build and network traffic; block a Gateway request and confirm no AWS connection occurs | A hidden SDK or future configuration could reintroduce a direct endpoint |
| Persistent player identifier | `anonymous_user_id`, `session_id`, hashed Steam ID, device ID, or installation ID enters the payload | `HIGH` | AWS can link Runs or identify a player through another data source | Remove persistent identifiers; use only random per-Run and per-event IDs; forbid mapping tables | Contract rejection tests and repository search; inspect representative Unity payloads | A value with an innocent field name could still encode a persistent identifier |
| Reused `run_id` | Client cache, retry logic, or generator reuses an ID in a later Run | `HIGH` | Separate Runs become linkable | Generate at each Run start; never derive from player data; clear Run state at termination | Generate many consecutive Runs and assert uniqueness and absence of mappings | Random UUID collision is negligible, but implementation bugs remain possible |
| Identifier mapping outside the payload | Client, Gateway, or operator stores Steam-to-Run or device-to-Run mappings | `HIGH` | Anonymous AWS records become re-identifiable | Prohibit mappings in code, configuration, logs, databases, and support tooling | Repository and deployment review; automated tests confirming no mapping store or call | Undocumented manual operational practices require periodic review |
| Player IP forwarded in headers | Reverse proxy preserves `X-Forwarded-For`, `Forwarded`, `X-Real-IP`, or provider-specific headers | `HIGH` | AWS can identify or geographically profile the player | Terminate the request, discard incoming headers, and build a new allow-listed outbound header set | Capture outbound Gateway requests and assert all client-network headers are absent | The Gateway's fixed IP remains visible by design |
| Player IP stored in Türkiye logs | Default Nginx, application, firewall, provider, or security logging records source IP | `HIGH` | Türkiye-side data can be correlated with AWS event times | Disable access logs by default; avoid request/body logging; document any essential local security log and minimal retention | Inspect Nginx, FastAPI, OS, firewall, and provider settings; generate traffic and search resulting logs | The provider may retain infrastructure metadata outside customer-configurable logs |
| Precise wall-clock correlation | Client `event_time`, AWS `received_at`, or logs expose millisecond timestamps | `MEDIUM` | Gameplay can be matched to streaming, chat, support, or Türkiye-side activity | Remove client wall-clock time; use Run-relative sequence and elapsed values; minimize stored arrival precision and retention | Inspect schemas and stored Bronze records; confirm Gold and LLM inputs contain no precise operational time | AWS processing systems necessarily observe some operational timing temporarily |
| Rare Run fingerprint | Exact choices, timing, progression, and final upgrades form a unique pattern | `MEDIUM` | A person who publicly shares the same Run may be singled out | Prevent cross-Run identifiers; reduce unnecessary precision; bound arrays; aggregate before Gold and LLM use | Uniqueness analysis on approved fields before production; inspect Gold minimum group sizes where appropriate | Detailed Run analytics intentionally retains a unique gameplay sequence inside one Run |
| Free-form or open identifier value | A content ID, version, error message, query value, or new field carries a username or identifier | `HIGH` | Allow-listed keys become a tunnel for personal data | Replace open strings with enums or approved content-ID sets; limit length and pattern; reject unknown fields | Fuzz strings containing emails, paths, tokens, and identifier formats in every string field | New content versions require controlled allow-list updates |
| Original request forwarding | Nginx proxy or FastAPI client forwards the incoming request object unchanged | `HIGH` | Headers, cookies, query parameters, and unexpected body fields reach AWS | Parse and validate JSON; construct a new typed object and new outbound request from explicit fields | Mock the AWS receiver and compare inbound versus outbound requests | Framework middleware can add headers and must be reviewed after upgrades |
| Forbidden-field variant bypass | `steamId`, nested keys, mixed case, Unicode, or separators evade a simple deny list | `HIGH` | Direct identifiers reach AWS despite validation | Normalize key names, recurse through objects and arrays, reject unknown fields, and maintain both allow-list and deny-list checks | Parameterized nested, casing, separator, and Unicode-confusable tests | Semantic identifiers with unrelated names may evade keyword detection; allow-list is the primary control |
| Raw payload in error logs | Validation exception, debug log, trace, APM, or crash report records the body | `HIGH` | Rejected personal data persists even though it never reaches Kinesis | Never interpolate payloads or raw requests into logs; disable external APM by default; use stable error codes | Submit prohibited payloads and inspect Gateway, Lambda, CloudWatch, and provider logs | Platform-managed diagnostic data must be verified with the selected provider |
| AWS API Gateway access-log exposure | Access logs include source context, headers, authorization, or body-derived fields | `MEDIUM` | Gateway metadata or secrets persist in CloudWatch | Use an explicit minimal log format; omit body, headers, authorization, query strings, and `run_id`; set retention | Review deployed stage configuration and generated CloudWatch entries | AWS still observes the Türkiye Gateway's network identity |
| Lambda log exposure | Function logs raw API events, bodies, stack locals, or `run_id` | `HIGH` | Payloads or correlation identifiers persist in CloudWatch | Log only schema version, event type, result, stable error code, and processing duration | Static checks for raw logging plus valid/invalid request log inspection | Unhandled framework exceptions may require additional redaction |
| Invalid record reaches Kinesis | Gateway or Lambda validation fails open or catches an error incorrectly | `HIGH` | Personal or malformed data enters durable AWS storage | Apply independent fail-closed validation at Gateway and Lambda; grant Kinesis writes only after success | Mock Kinesis and assert zero writes for every privacy/schema failure | Validator version drift can create inconsistent decisions between layers |
| Failed-record or DLQ leakage | Firehose backup, Lambda destination, retry store, Quarantine, or DLQ stores rejected raw input | `HIGH` | Prohibited data persists outside the normal path | Do not persist pre-privacy requests; store only non-identifying reason metadata for privacy rejection; validate post-boundary failures independently | Force each failure path and inspect every destination | Managed-service internal retries require configuration review |
| Secret exposure | Gateway credential is embedded in Unity, repository, telemetry, or logs | `HIGH` | Attackers can inject false telemetry or extract operational secrets | Keep credentials server-side in an approved secret store or environment; never send them to the client | Secret scanning, build inspection, log inspection, and unauthorized-request tests | A compromised Türkiye VPS can still misuse its authorized credential |
| Public or weak AWS ingestion endpoint | API key alone or missing authorization permits arbitrary submissions | `MEDIUM` | Poisoned metrics, cost growth, and privacy-control bypass attempts | Authenticate the Gateway with a stronger server-to-server control; rate-limit and throttle; use least privilege | Reject unauthenticated and replayed requests; load-test configured limits | An authorized compromised Gateway remains a trusted-source risk |
| Unbounded payload or cardinality | Oversized arrays, identifiers, values, or request rates enter the pipeline | `MEDIUM` | Denial of service, unexpected cost, and high-cardinality fingerprints | Set request-size, array-length, string-length, numeric-range, rate, and concurrency bounds | Boundary tests and cost-aware load tests | Legitimate future content expansion requires reviewed limit changes |
| Overseas CDN, APM, backup, or provider subprocessors | Traffic or logs are copied outside Türkiye before anonymization | `HIGH` | Player IP or request data crosses the privacy boundary through a side channel | Do not use an overseas traffic proxy; disable external APM and unnecessary backups; review provider locations and subprocessors | Provider documentation, contract, control-panel, DNS, and traffic-path review | Provider behavior cannot be proven solely from repository configuration |
| Retention drift | S3, CloudWatch, Gateway, failed records, Airflow, or local buffers outlive the 30-day bound | `MEDIUM` | Correlation opportunity and cost continue to grow | Express retention in code/IaC; document exceptions; delete pending buffers after delivery or opt-out | Inspect lifecycle policies and create expiry tests or operational evidence | Deletion timing and managed-service backups may not be instantaneous |
| Future schema regression | A new field or service is added without privacy review | `HIGH` | The architecture silently begins carrying identifiable data | Require field classification, threat review, tests, and documentation for every schema or path change | CI privacy suite and review checklist block unassessed fields | Process bypass remains possible without repository protection and ownership discipline |
| LLM receives Run-level raw events | Report generation sends detailed events instead of approved Gold aggregates | `MEDIUM` | Detailed Run fingerprints spread to another processing layer | Permit only validated Gold metric schemas as LLM input | Contract-test the report payload and inspect invocation logs | Very small aggregate groups may still reveal unusual Runs |

## Required security and privacy tests

The implementation is not ready for production collection until evidence covers all of the following:

1. The Game Client has no direct AWS endpoint or credential.
2. A Gateway outage causes telemetry failure without affecting gameplay or triggering AWS fallback.
3. Every Run and event receives a fresh random identifier with no player-derived input.
4. Unknown, nested, mixed-case, separator-varied, and Unicode-confusable identifier fields are rejected.
5. Outbound Gateway requests contain only the approved body and header allow-lists.
6. Privacy-invalid and schema-invalid requests produce no Kinesis write and no raw error record.
7. Generated traffic leaves no client IP, request body, authorization value, or `run_id` in operational logs.
8. Every retry, DLQ, backup, Quarantine, and failure destination is inspected.
9. AWS stores only the Türkiye Gateway's network identity and validated anonymous telemetry.
10. Gold and LLM payloads contain aggregates only and cannot join separate Runs as one player.
11. Retention is explicitly bounded for every durable and logging location.
12. Provider location, managed logs, backups, and subprocessors are reviewed before the Türkiye VPS is used.

## Residual technical limitations

- A Türkiye network endpoint necessarily observes the client IP while the connection exists, even when it
  does not store or forward it.
- Detailed events can single out one unusual Run. The design prevents that Run from being linked to a person
  or another Run; it does not make all Runs statistically identical.
- AWS and framework components temporarily process operational timing and the Gateway's network identity.
- Provider behavior, administrator practices, and future configuration changes cannot be proven by schema
  validation alone.
- Removing persistent identity makes individual historical search, cross-Run retention analysis, and
  post-ingestion player-specific deletion technically unavailable.

## Design consequences

The anonymous schema must remove persistent user and session identifiers, replace client wall-clock ordering,
constrain string values, bound payload shape, and define the minimum operational timestamp precision. The
architecture must treat the Türkiye Gateway as a privacy transformer with fail-closed validation rather than
as a transparent proxy.

