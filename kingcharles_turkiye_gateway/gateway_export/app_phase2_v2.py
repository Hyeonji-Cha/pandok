import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import hashlib as _blob_hashlib

from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from jsonschema import Draft202012Validator, FormatChecker


THIS_DIR = Path(__file__).resolve().parent

MAX_BODY_BYTES = 64 * 1024
DEDUPE_TTL_SECONDS = 48 * 60 * 60

DB_PATH = Path(os.environ.get(
    "PANDOK_DB_PATH",
    "/var/lib/pandok-gateway/aggregate.sqlite3",
))
TEST_TOKEN_PATH = Path(os.environ.get(
    "PANDOK_TEST_TOKEN_PATH",
    "/etc/pandok-gateway/test-token",
))
INGEST_KEY_PATH = Path(os.environ.get(
    "PANDOK_INGEST_KEY_PATH",
    "/etc/pandok-gateway/ingest-key",
))
DEDUPE_KEY_PATH = Path(os.environ.get(
    "PANDOK_DEDUPE_KEY_PATH",
    "/etc/pandok-gateway/dedupe-key",
))
SCHEMA_PATH = Path(os.environ.get(
    "PANDOK_SCHEMA_PATH",
    str(THIS_DIR / "telemetry-event-v2.schema.json"),
))

EXPORT_ENABLED = os.environ.get("PANDOK_AWS_EXPORT_ENABLED", "0") == "1"
EXPORT_URL = os.environ.get("PANDOK_AWS_EXPORT_URL", "").strip()
EXPORT_TOKEN_PATH = Path(os.environ.get(
    "PANDOK_AWS_EXPORT_TOKEN_PATH",
    "/etc/pandok-gateway/aws-export-token",
))
EXPORT_TIMEOUT_SECONDS = float(os.environ.get("PANDOK_AWS_EXPORT_TIMEOUT_SECONDS", "3"))
EXPORT_MAX_ATTEMPTS = int(os.environ.get("PANDOK_AWS_EXPORT_MAX_ATTEMPTS", "3"))
EXPORT_BACKOFF_SECONDS = float(os.environ.get("PANDOK_AWS_EXPORT_BACKOFF_SECONDS", "0.25"))
ALLOW_INSECURE_EXPORT_FOR_TEST = (
    os.environ.get("PANDOK_ALLOW_INSECURE_EXPORT_FOR_TEST", "0") == "1"
)

EXPECTED_CONTRACT_GIT_BLOB_SHA = "4336417ea4107e4e9597ecddbcf989f38a240f7f"


app = FastAPI(
    title="PANDOK Türkiye Privacy Gateway",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


FORBIDDEN_KEYS = {
    "ip",
    "ip_address",
    "client_ip",
    "source_ip",
    "remote_ip",
    "x_forwarded_for",
    "x_real_ip",
    "forwarded",
    "steam_id",
    "steamid",
    "steam_user_id",
    "nickname",
    "username",
    "email",
    "device_id",
    "hardware_id",
    "installation_id",
    "install_id",
    "advertising_id",
    "ad_id",
    "auth_token",
    "access_token",
    "refresh_token",
    "password",
    "precise_location",
    "latitude",
    "longitude",
}


def normalized_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def reject_forbidden_fields(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if normalized_key(str(key)) in FORBIDDEN_KEYS:
                raise HTTPException(
                    status_code=422,
                    detail="forbidden_privacy_field",
                )
            reject_forbidden_fields(child)
    elif isinstance(value, list):
        for child in value:
            reject_forbidden_fields(child)


def _load_text_secret(path: Path, label: str) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 32:
        raise RuntimeError(f"{label} is invalid.")
    return value


def load_test_token() -> str:
    return _load_text_secret(TEST_TOKEN_PATH, "Controlled-test token")


def load_ingest_key() -> str:
    return _load_text_secret(INGEST_KEY_PATH, "Ingest key")


def load_dedupe_key() -> bytes:
    value = DEDUPE_KEY_PATH.read_text(encoding="utf-8").strip()
    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise RuntimeError("Dedupe key is invalid.") from exc
    if len(key) != 32:
        raise RuntimeError("Dedupe key is invalid.")
    return key


TEST_TOKEN = load_test_token()
INGEST_KEY = load_ingest_key()
DEDUPE_KEY = load_dedupe_key()


def _validate_export_configuration():
    if not EXPORT_ENABLED:
        return
    if not EXPORT_URL:
        raise RuntimeError("AWS export is enabled but PANDOK_AWS_EXPORT_URL is empty.")
    parsed = urllib.parse.urlparse(EXPORT_URL)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise RuntimeError("PANDOK_AWS_EXPORT_URL is invalid.")
    if parsed.scheme != "https" and not ALLOW_INSECURE_EXPORT_FOR_TEST:
        raise RuntimeError("AWS export URL must use HTTPS outside synthetic tests.")
    if EXPORT_MAX_ATTEMPTS < 1 or EXPORT_MAX_ATTEMPTS > 10:
        raise RuntimeError("PANDOK_AWS_EXPORT_MAX_ATTEMPTS must be between 1 and 10.")
    if EXPORT_TIMEOUT_SECONDS <= 0 or EXPORT_TIMEOUT_SECONDS > 30:
        raise RuntimeError("PANDOK_AWS_EXPORT_TIMEOUT_SECONDS is invalid.")
    if EXPORT_BACKOFF_SECONDS < 0 or EXPORT_BACKOFF_SECONDS > 10:
        raise RuntimeError("PANDOK_AWS_EXPORT_BACKOFF_SECONDS is invalid.")


_validate_export_configuration()
AWS_EXPORT_TOKEN = (
    _load_text_secret(EXPORT_TOKEN_PATH, "AWS export token")
    if EXPORT_ENABLED
    else ""
)


CONTRACT_BYTES = SCHEMA_PATH.read_bytes()

# Git stores repository text blobs with LF line endings.
# Windows Git checkouts may transparently materialize the exact same
# canonical contract with CRLF. Normalize CRLF -> LF only for the
# pinned Git-blob identity check; schema content is otherwise unchanged.
CONTRACT_GIT_BYTES = CONTRACT_BYTES.replace(b"\r\n", b"\n")

_contract_git_blob_sha = _blob_hashlib.sha1(
    f"blob {len(CONTRACT_GIT_BYTES)}\0".encode("ascii")
    + CONTRACT_GIT_BYTES
).hexdigest()
if (
    os.environ.get("PANDOK_ALLOW_NONCANONICAL_SCHEMA", "0") != "1"
    and _contract_git_blob_sha != EXPECTED_CONTRACT_GIT_BLOB_SHA
):
    raise RuntimeError(
        "telemetry-event-v2.schema.json does not match the pinned canonical GitHub blob "
        + EXPECTED_CONTRACT_GIT_BLOB_SHA
    )
CONTRACT = json.loads(CONTRACT_BYTES.decode("utf-8"))
Draft202012Validator.check_schema(CONTRACT)
CONTRACT_VALIDATOR = Draft202012Validator(
    CONTRACT,
    format_checker=FormatChecker(),
)


ALLOWED_EVENTS = {
    "run_started",
    "upgrade_options_shown",
    "upgrade_selected",
    "run_checkpoint",
    "run_ended",
}


def _validation_error_detail(error):
    path = ".".join(str(part) for part in error.absolute_path)
    return {
        "code": "telemetry_event_v2_contract_violation",
        "path": path,
        "message": error.message,
    }


def validate_client_event(payload):
    errors = sorted(
        CONTRACT_VALIDATOR.iter_errors(payload),
        key=lambda e: (tuple(str(part) for part in e.absolute_path), e.message),
    )
    if errors:
        raise HTTPException(
            status_code=422,
            detail=_validation_error_detail(errors[0]),
        )


def normalize_event_id(payload) -> str:
    # The JSON Schema format checker already verifies UUID syntax.
    # Normalization is used only to make dedupe deterministic.
    return payload["event_id"].lower()


def open_db():
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_v2_db():
    with closing(open_db()) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS event_counts (
                bucket_date TEXT NOT NULL,
                event_name TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                PRIMARY KEY (bucket_date, event_name)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS dedupe_events (
                event_hash BLOB NOT NULL PRIMARY KEY,
                expires_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_dedupe_events_expires_at
            ON dedupe_events(expires_at)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS run_started_counts_v2 (
                bucket_date TEXT NOT NULL,
                map_id TEXT NOT NULL,
                starting_weapon_id TEXT NOT NULL,
                run_count INTEGER NOT NULL,
                starting_max_hp_sum REAL NOT NULL,
                starting_max_hp_present_count INTEGER NOT NULL,
                PRIMARY KEY (
                    bucket_date,
                    map_id,
                    starting_weapon_id
                )
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS upgrade_option_counts_v2 (
                bucket_date TEXT NOT NULL,
                choice_source TEXT NOT NULL,
                item_id TEXT NOT NULL,
                rarity TEXT NOT NULL,
                slot INTEGER NOT NULL,
                effect_type TEXT NOT NULL,
                effect_value_before_json TEXT NOT NULL,
                shown_count INTEGER NOT NULL,
                acquisition_count_before_sum INTEGER NOT NULL,
                acquisition_count_before_present_count INTEGER NOT NULL,
                PRIMARY KEY (
                    bucket_date,
                    choice_source,
                    item_id,
                    rarity,
                    slot,
                    effect_type,
                    effect_value_before_json
                )
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS upgrade_selected_counts_v2 (
                bucket_date TEXT NOT NULL,
                choice_source TEXT NOT NULL,
                item_id TEXT NOT NULL,
                rarity TEXT NOT NULL,
                slot INTEGER NOT NULL,
                effect_type TEXT NOT NULL,
                effect_value_before_json TEXT NOT NULL,
                effect_value_after_json TEXT NOT NULL,
                selected_count INTEGER NOT NULL,
                acquisition_count_before_sum INTEGER NOT NULL,
                acquisition_count_before_present_count INTEGER NOT NULL,
                acquisition_count_after_sum INTEGER NOT NULL,
                acquisition_count_after_present_count INTEGER NOT NULL,
                PRIMARY KEY (
                    bucket_date,
                    choice_source,
                    item_id,
                    rarity,
                    slot,
                    effect_type,
                    effect_value_before_json,
                    effect_value_after_json
                )
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS run_checkpoint_counts_v2 (
                bucket_date TEXT NOT NULL,
                checkpoint_number INTEGER NOT NULL,
                checkpoint_count INTEGER NOT NULL,
                run_elapsed_seconds_sum REAL NOT NULL,
                player_level_sum INTEGER NOT NULL,
                current_xp_sum REAL NOT NULL,
                xp_to_next_level_sum REAL NOT NULL,
                hp_percent_sum REAL NOT NULL,
                total_kills_sum INTEGER NOT NULL,
                current_gold_sum REAL NOT NULL,
                total_xp_collected_sum REAL NOT NULL,
                total_xp_collected_present_count INTEGER NOT NULL,
                total_gold_collected_sum REAL NOT NULL,
                total_gold_collected_present_count INTEGER NOT NULL,
                hearts_collected_sum INTEGER NOT NULL,
                hearts_collected_present_count INTEGER NOT NULL,
                total_healing_received_sum REAL NOT NULL,
                total_healing_received_present_count INTEGER NOT NULL,
                magnets_collected_sum INTEGER NOT NULL,
                magnets_collected_present_count INTEGER NOT NULL,
                miniboss_waves_cleared_sum INTEGER NOT NULL,
                miniboss_waves_cleared_present_count INTEGER NOT NULL,
                PRIMARY KEY (bucket_date, checkpoint_number)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoint_upgrade_state_counts_v2 (
                bucket_date TEXT NOT NULL,
                checkpoint_number INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                acquisition_count INTEGER NOT NULL,
                effect_type TEXT NOT NULL,
                effect_value_json TEXT NOT NULL,
                state_count INTEGER NOT NULL,
                PRIMARY KEY (
                    bucket_date,
                    checkpoint_number,
                    item_id,
                    acquisition_count,
                    effect_type,
                    effect_value_json
                )
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS run_end_counts_v2 (
                bucket_date TEXT NOT NULL,
                end_reason TEXT NOT NULL,
                end_count INTEGER NOT NULL,
                run_elapsed_seconds_sum REAL NOT NULL,
                final_level_sum INTEGER NOT NULL,
                total_kills_sum INTEGER NOT NULL,
                current_gold_sum REAL NOT NULL,
                total_xp_collected_sum REAL NOT NULL,
                total_xp_collected_present_count INTEGER NOT NULL,
                total_gold_collected_sum REAL NOT NULL,
                total_gold_collected_present_count INTEGER NOT NULL,
                hearts_collected_sum INTEGER NOT NULL,
                hearts_collected_present_count INTEGER NOT NULL,
                total_healing_received_sum REAL NOT NULL,
                total_healing_received_present_count INTEGER NOT NULL,
                magnets_collected_sum INTEGER NOT NULL,
                magnets_collected_present_count INTEGER NOT NULL,
                miniboss_waves_reached_sum INTEGER NOT NULL,
                miniboss_waves_reached_present_count INTEGER NOT NULL,
                miniboss_waves_cleared_sum INTEGER NOT NULL,
                miniboss_waves_cleared_present_count INTEGER NOT NULL,
                PRIMARY KEY (bucket_date, end_reason)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS final_upgrade_state_counts_v2 (
                bucket_date TEXT NOT NULL,
                end_reason TEXT NOT NULL,
                item_id TEXT NOT NULL,
                acquisition_count INTEGER NOT NULL,
                effect_type TEXT NOT NULL,
                effect_value_json TEXT NOT NULL,
                state_count INTEGER NOT NULL,
                PRIMARY KEY (
                    bucket_date,
                    end_reason,
                    item_id,
                    acquisition_count,
                    effect_type,
                    effect_value_json
                )
            )
            """
        )


class ExportRetryableError(RuntimeError):
    pass


class ExportPermanentError(RuntimeError):
    pass


RETRYABLE_EXPORT_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _export_request_headers(payload):
    return {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + AWS_EXPORT_TOKEN,
        "X-Pandok-Contract": "telemetry-event-v2",
        "X-Pandok-Contract-Blob-SHA": EXPECTED_CONTRACT_GIT_BLOB_SHA,
        "Idempotency-Key": payload["event_id"],
    }


def _export_once(payload):
    body = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    request = urllib.request.Request(
        EXPORT_URL,
        data=body,
        headers=_export_request_headers(payload),
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=EXPORT_TIMEOUT_SECONDS,
        ) as response:
            status = int(getattr(response, "status", 200))
            if 200 <= status < 300:
                return status
            if status in RETRYABLE_EXPORT_STATUS:
                raise ExportRetryableError(
                    f"AWS export returned retryable HTTP {status}"
                )
            raise ExportPermanentError(
                f"AWS export returned non-retryable HTTP {status}"
            )
    except urllib.error.HTTPError as exc:
        if exc.code in RETRYABLE_EXPORT_STATUS:
            raise ExportRetryableError(
                f"AWS export returned retryable HTTP {exc.code}"
            ) from exc
        raise ExportPermanentError(
            f"AWS export returned non-retryable HTTP {exc.code}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ExportRetryableError("AWS export network failure") from exc


def export_to_aws(payload):
    if not EXPORT_ENABLED:
        return 0

    last_error = None
    for attempt in range(1, EXPORT_MAX_ATTEMPTS + 1):
        try:
            _export_once(payload)
            return attempt
        except ExportPermanentError:
            raise
        except ExportRetryableError as exc:
            last_error = exc
            if attempt >= EXPORT_MAX_ATTEMPTS:
                break
            delay = EXPORT_BACKOFF_SECONDS * (2 ** (attempt - 1))
            if delay > 0:
                time.sleep(delay)

    raise ExportRetryableError(
        "AWS export failed after retry budget was exhausted"
    ) from last_error


def _event_hash(payload):
    event_id = normalize_event_id(payload)
    return hmac.new(
        DEDUPE_KEY,
        event_id.encode("ascii"),
        hashlib.sha256,
    ).digest()


def event_already_processed(payload):
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    event_hash = _event_hash(payload)
    with closing(open_db()) as connection, connection:
        row = connection.execute(
            "SELECT 1 FROM dedupe_events WHERE event_hash = ? AND expires_at > ?",
            (event_hash, now_epoch),
        ).fetchone()
    return row is not None


def _json_scalar(value):
    if value is None:
        return ""
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _number_pair(payload, key):
    if key not in payload:
        return 0, 0
    return payload[key], 1


def _dedupe_insert(connection, payload, now_epoch):
    event_hash = _event_hash(payload)
    expires_at = now_epoch + DEDUPE_TTL_SECONDS

    connection.execute(
        "DELETE FROM dedupe_events WHERE expires_at <= ?",
        (now_epoch,),
    )
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO dedupe_events (event_hash, expires_at)
        VALUES (?, ?)
        """,
        (event_hash, expires_at),
    )
    return cursor.rowcount != 0


def aggregate_event(payload):
    now = datetime.now(timezone.utc)
    bucket_date = now.date().isoformat()
    now_epoch = int(now.timestamp())
    event_name = payload["event_name"]

    with closing(open_db()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        if not _dedupe_insert(connection, payload, now_epoch):
            return False

        connection.execute(
            """
            INSERT INTO event_counts (bucket_date, event_name, event_count)
            VALUES (?, ?, 1)
            ON CONFLICT(bucket_date, event_name)
            DO UPDATE SET event_count = event_count + 1
            """,
            (bucket_date, event_name),
        )

        if event_name == "run_started":
            max_hp = payload.get("starting_max_hp")
            connection.execute(
                """
                INSERT INTO run_started_counts_v2 (
                    bucket_date, map_id, starting_weapon_id, run_count,
                    starting_max_hp_sum, starting_max_hp_present_count
                )
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(bucket_date, map_id, starting_weapon_id)
                DO UPDATE SET
                    run_count = run_count + 1,
                    starting_max_hp_sum = starting_max_hp_sum + excluded.starting_max_hp_sum,
                    starting_max_hp_present_count = starting_max_hp_present_count + excluded.starting_max_hp_present_count
                """,
                (
                    bucket_date,
                    payload.get("map_id", ""),
                    payload.get("starting_weapon_id", ""),
                    float(max_hp) if max_hp is not None else 0.0,
                    1 if max_hp is not None else 0,
                ),
            )

        elif event_name == "upgrade_options_shown":
            for option in payload["options"]:
                acquisition = option.get("acquisition_count_before")
                connection.execute(
                    """
                    INSERT INTO upgrade_option_counts_v2 (
                        bucket_date, choice_source, item_id, rarity, slot,
                        effect_type, effect_value_before_json, shown_count,
                        acquisition_count_before_sum,
                        acquisition_count_before_present_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(
                        bucket_date, choice_source, item_id, rarity, slot,
                        effect_type, effect_value_before_json
                    )
                    DO UPDATE SET
                        shown_count = shown_count + 1,
                        acquisition_count_before_sum = acquisition_count_before_sum + excluded.acquisition_count_before_sum,
                        acquisition_count_before_present_count = acquisition_count_before_present_count + excluded.acquisition_count_before_present_count
                    """,
                    (
                        bucket_date,
                        payload["choice_source"],
                        option["item_id"],
                        option["rarity"],
                        option["slot"],
                        option.get("effect_type", ""),
                        _json_scalar(option.get("effect_value_before")),
                        acquisition if acquisition is not None else 0,
                        1 if acquisition is not None else 0,
                    ),
                )

        elif event_name == "upgrade_selected":
            before = payload.get("acquisition_count_before")
            after = payload.get("acquisition_count_after")
            connection.execute(
                """
                INSERT INTO upgrade_selected_counts_v2 (
                    bucket_date, choice_source, item_id, rarity, slot,
                    effect_type, effect_value_before_json, effect_value_after_json,
                    selected_count,
                    acquisition_count_before_sum, acquisition_count_before_present_count,
                    acquisition_count_after_sum, acquisition_count_after_present_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(
                    bucket_date, choice_source, item_id, rarity, slot,
                    effect_type, effect_value_before_json, effect_value_after_json
                )
                DO UPDATE SET
                    selected_count = selected_count + 1,
                    acquisition_count_before_sum = acquisition_count_before_sum + excluded.acquisition_count_before_sum,
                    acquisition_count_before_present_count = acquisition_count_before_present_count + excluded.acquisition_count_before_present_count,
                    acquisition_count_after_sum = acquisition_count_after_sum + excluded.acquisition_count_after_sum,
                    acquisition_count_after_present_count = acquisition_count_after_present_count + excluded.acquisition_count_after_present_count
                """,
                (
                    bucket_date,
                    payload["choice_source"],
                    payload["selected_item_id"],
                    payload["selected_rarity"],
                    payload["selected_slot"],
                    payload.get("effect_type", ""),
                    _json_scalar(payload.get("effect_value_before")),
                    _json_scalar(payload.get("effect_value_after")),
                    before if before is not None else 0,
                    1 if before is not None else 0,
                    after if after is not None else 0,
                    1 if after is not None else 0,
                ),
            )

        elif event_name == "run_checkpoint":
            optional_keys = [
                "total_xp_collected",
                "total_gold_collected",
                "hearts_collected",
                "total_healing_received",
                "magnets_collected",
                "miniboss_waves_cleared",
            ]
            vals = {key: _number_pair(payload, key) for key in optional_keys}
            connection.execute(
                """
                INSERT INTO run_checkpoint_counts_v2 (
                    bucket_date, checkpoint_number, checkpoint_count,
                    run_elapsed_seconds_sum, player_level_sum, current_xp_sum,
                    xp_to_next_level_sum, hp_percent_sum, total_kills_sum,
                    current_gold_sum,
                    total_xp_collected_sum, total_xp_collected_present_count,
                    total_gold_collected_sum, total_gold_collected_present_count,
                    hearts_collected_sum, hearts_collected_present_count,
                    total_healing_received_sum, total_healing_received_present_count,
                    magnets_collected_sum, magnets_collected_present_count,
                    miniboss_waves_cleared_sum, miniboss_waves_cleared_present_count
                )
                VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bucket_date, checkpoint_number)
                DO UPDATE SET
                    checkpoint_count = checkpoint_count + 1,
                    run_elapsed_seconds_sum = run_elapsed_seconds_sum + excluded.run_elapsed_seconds_sum,
                    player_level_sum = player_level_sum + excluded.player_level_sum,
                    current_xp_sum = current_xp_sum + excluded.current_xp_sum,
                    xp_to_next_level_sum = xp_to_next_level_sum + excluded.xp_to_next_level_sum,
                    hp_percent_sum = hp_percent_sum + excluded.hp_percent_sum,
                    total_kills_sum = total_kills_sum + excluded.total_kills_sum,
                    current_gold_sum = current_gold_sum + excluded.current_gold_sum,
                    total_xp_collected_sum = total_xp_collected_sum + excluded.total_xp_collected_sum,
                    total_xp_collected_present_count = total_xp_collected_present_count + excluded.total_xp_collected_present_count,
                    total_gold_collected_sum = total_gold_collected_sum + excluded.total_gold_collected_sum,
                    total_gold_collected_present_count = total_gold_collected_present_count + excluded.total_gold_collected_present_count,
                    hearts_collected_sum = hearts_collected_sum + excluded.hearts_collected_sum,
                    hearts_collected_present_count = hearts_collected_present_count + excluded.hearts_collected_present_count,
                    total_healing_received_sum = total_healing_received_sum + excluded.total_healing_received_sum,
                    total_healing_received_present_count = total_healing_received_present_count + excluded.total_healing_received_present_count,
                    magnets_collected_sum = magnets_collected_sum + excluded.magnets_collected_sum,
                    magnets_collected_present_count = magnets_collected_present_count + excluded.magnets_collected_present_count,
                    miniboss_waves_cleared_sum = miniboss_waves_cleared_sum + excluded.miniboss_waves_cleared_sum,
                    miniboss_waves_cleared_present_count = miniboss_waves_cleared_present_count + excluded.miniboss_waves_cleared_present_count
                """,
                (
                    bucket_date,
                    payload["checkpoint_number"],
                    float(payload["run_elapsed_seconds"]),
                    payload["player_level"],
                    float(payload["current_xp"]),
                    float(payload["xp_to_next_level"]),
                    float(payload["hp_percent"]),
                    payload["total_kills"],
                    float(payload["current_gold"]),
                    vals["total_xp_collected"][0], vals["total_xp_collected"][1],
                    vals["total_gold_collected"][0], vals["total_gold_collected"][1],
                    vals["hearts_collected"][0], vals["hearts_collected"][1],
                    vals["total_healing_received"][0], vals["total_healing_received"][1],
                    vals["magnets_collected"][0], vals["magnets_collected"][1],
                    vals["miniboss_waves_cleared"][0], vals["miniboss_waves_cleared"][1],
                ),
            )
            for state in payload.get("active_upgrades", []):
                connection.execute(
                    """
                    INSERT INTO checkpoint_upgrade_state_counts_v2 (
                        bucket_date, checkpoint_number, item_id, acquisition_count,
                        effect_type, effect_value_json, state_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(
                        bucket_date, checkpoint_number, item_id, acquisition_count,
                        effect_type, effect_value_json
                    )
                    DO UPDATE SET state_count = state_count + 1
                    """,
                    (
                        bucket_date,
                        payload["checkpoint_number"],
                        state["item_id"],
                        state["acquisition_count"],
                        state.get("effect_type", ""),
                        _json_scalar(state.get("effect_value")),
                    ),
                )

        elif event_name == "run_ended":
            optional_keys = [
                "total_xp_collected",
                "total_gold_collected",
                "hearts_collected",
                "total_healing_received",
                "magnets_collected",
                "miniboss_waves_reached",
                "miniboss_waves_cleared",
            ]
            vals = {key: _number_pair(payload, key) for key in optional_keys}
            connection.execute(
                """
                INSERT INTO run_end_counts_v2 (
                    bucket_date, end_reason, end_count,
                    run_elapsed_seconds_sum, final_level_sum, total_kills_sum,
                    current_gold_sum,
                    total_xp_collected_sum, total_xp_collected_present_count,
                    total_gold_collected_sum, total_gold_collected_present_count,
                    hearts_collected_sum, hearts_collected_present_count,
                    total_healing_received_sum, total_healing_received_present_count,
                    magnets_collected_sum, magnets_collected_present_count,
                    miniboss_waves_reached_sum, miniboss_waves_reached_present_count,
                    miniboss_waves_cleared_sum, miniboss_waves_cleared_present_count
                )
                VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bucket_date, end_reason)
                DO UPDATE SET
                    end_count = end_count + 1,
                    run_elapsed_seconds_sum = run_elapsed_seconds_sum + excluded.run_elapsed_seconds_sum,
                    final_level_sum = final_level_sum + excluded.final_level_sum,
                    total_kills_sum = total_kills_sum + excluded.total_kills_sum,
                    current_gold_sum = current_gold_sum + excluded.current_gold_sum,
                    total_xp_collected_sum = total_xp_collected_sum + excluded.total_xp_collected_sum,
                    total_xp_collected_present_count = total_xp_collected_present_count + excluded.total_xp_collected_present_count,
                    total_gold_collected_sum = total_gold_collected_sum + excluded.total_gold_collected_sum,
                    total_gold_collected_present_count = total_gold_collected_present_count + excluded.total_gold_collected_present_count,
                    hearts_collected_sum = hearts_collected_sum + excluded.hearts_collected_sum,
                    hearts_collected_present_count = hearts_collected_present_count + excluded.hearts_collected_present_count,
                    total_healing_received_sum = total_healing_received_sum + excluded.total_healing_received_sum,
                    total_healing_received_present_count = total_healing_received_present_count + excluded.total_healing_received_present_count,
                    magnets_collected_sum = magnets_collected_sum + excluded.magnets_collected_sum,
                    magnets_collected_present_count = magnets_collected_present_count + excluded.magnets_collected_present_count,
                    miniboss_waves_reached_sum = miniboss_waves_reached_sum + excluded.miniboss_waves_reached_sum,
                    miniboss_waves_reached_present_count = miniboss_waves_reached_present_count + excluded.miniboss_waves_reached_present_count,
                    miniboss_waves_cleared_sum = miniboss_waves_cleared_sum + excluded.miniboss_waves_cleared_sum,
                    miniboss_waves_cleared_present_count = miniboss_waves_cleared_present_count + excluded.miniboss_waves_cleared_present_count
                """,
                (
                    bucket_date,
                    payload["end_reason"],
                    float(payload["run_elapsed_seconds"]),
                    payload["final_level"],
                    payload["total_kills"],
                    float(payload["current_gold"]),
                    vals["total_xp_collected"][0], vals["total_xp_collected"][1],
                    vals["total_gold_collected"][0], vals["total_gold_collected"][1],
                    vals["hearts_collected"][0], vals["hearts_collected"][1],
                    vals["total_healing_received"][0], vals["total_healing_received"][1],
                    vals["magnets_collected"][0], vals["magnets_collected"][1],
                    vals["miniboss_waves_reached"][0], vals["miniboss_waves_reached"][1],
                    vals["miniboss_waves_cleared"][0], vals["miniboss_waves_cleared"][1],
                ),
            )
            for state in payload.get("final_upgrades", []):
                connection.execute(
                    """
                    INSERT INTO final_upgrade_state_counts_v2 (
                        bucket_date, end_reason, item_id, acquisition_count,
                        effect_type, effect_value_json, state_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(
                        bucket_date, end_reason, item_id, acquisition_count,
                        effect_type, effect_value_json
                    )
                    DO UPDATE SET state_count = state_count + 1
                    """,
                    (
                        bucket_date,
                        payload["end_reason"],
                        state["item_id"],
                        state["acquisition_count"],
                        state.get("effect_type", ""),
                        _json_scalar(state.get("effect_value")),
                    ),
                )

    return True


def _authorized(request: Request, payload) -> bool:
    source_type = payload.get("source_type")

    if source_type == "CONSENTED_PROD_PLAY":
        supplied = request.headers.get("x-pandok-ingest-key", "")
        return hmac.compare_digest(supplied, INGEST_KEY)

    if source_type in {"CONTROLLED_SCENARIO", "LOAD_TEST"}:
        supplied = request.headers.get("x-pandok-test-token", "")
        return (
            request.headers.get("x-pandok-controlled-test") == "1"
            and hmac.compare_digest(supplied, TEST_TOKEN)
        )

    return False


initialize_v2_db()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gateway": "pandok-turkiye",
        "telemetry_contract": "2.0",
        "contract_id": CONTRACT.get("$id"),
        "local_aggregation": True,
        "raw_event_storage": False,
        "real_aws_export": EXPORT_ENABLED,
        "aws_export_configured": bool(EXPORT_URL) if EXPORT_ENABLED else False,
        "aws_export_retry_attempts": EXPORT_MAX_ATTEMPTS if EXPORT_ENABLED else 0,
    }


@app.get("/internal/aggregate-summary")
async def aggregate_summary():
    with closing(open_db()) as connection, connection:
        event_rows = connection.execute(
            """
            SELECT bucket_date, event_name, event_count
            FROM event_counts
            ORDER BY bucket_date, event_name
            """
        ).fetchall()
        table_counts = {}
        for table in (
            "run_started_counts_v2",
            "upgrade_option_counts_v2",
            "upgrade_selected_counts_v2",
            "run_checkpoint_counts_v2",
            "checkpoint_upgrade_state_counts_v2",
            "run_end_counts_v2",
            "final_upgrade_state_counts_v2",
        ):
            table_counts[table] = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]

    return {
        "real_aws_export": EXPORT_ENABLED,
        "telemetry_contract": "2.0",
        "event_counts": [
            {
                "bucket_date": row[0],
                "event_name": row[1],
                "count": row[2],
            }
            for row in event_rows
        ],
        "aggregate_table_row_counts": table_counts,
    }


@app.post("/v1/telemetry", status_code=204)
async def telemetry(request: Request):
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("application/json"):
        raise HTTPException(
            status_code=415,
            detail="application_json_required",
        )

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty_body")
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload_too_large")

    try:
        payload = json.loads(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="json_object_required")

    reject_forbidden_fields(payload)
    validate_client_event(payload)

    if payload.get("event_name") not in ALLOWED_EVENTS:
        # Normally unreachable because the canonical contract already rejects it.
        raise HTTPException(status_code=422, detail="unsupported_event_name")

    if not _authorized(request, payload):
        raise HTTPException(
            status_code=403,
            detail="telemetry_ingest_not_authorized",
        )

    # A successful event already recorded in the local dedupe window must not
    # be exported again on an ordinary client retry. Concurrent duplicate
    # exports are also protected by the event_id Idempotency-Key at AWS.
    if event_already_processed(payload):
        return Response(status_code=204)

    if EXPORT_ENABLED:
        try:
            await asyncio.to_thread(export_to_aws, payload)
        except ExportPermanentError as exc:
            raise HTTPException(
                status_code=502,
                detail="aws_export_rejected",
            ) from exc
        except ExportRetryableError as exc:
            raise HTTPException(
                status_code=503,
                detail="aws_export_temporarily_unavailable",
                headers={"Retry-After": "1"},
            ) from exc

    # Local dedupe/aggregation is committed only after AWS export succeeds.
    # If export exhausts its retry budget, the event remains retryable by the client.
    aggregate_event(payload)
    return Response(status_code=204)
