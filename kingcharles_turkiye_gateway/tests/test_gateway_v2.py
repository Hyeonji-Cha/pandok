import importlib.util
import os
import sqlite3
import tempfile
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
GATEWAY_DIR = TEST_DIR.parent / "gateway_export"
REPO_ROOT = TEST_DIR.parents[1]
CONTRACT_PATH = REPO_ROOT / "contracts" / "telemetry-event-v2.schema.json"


def uid(n):
    return f"00000000-0000-4000-8000-{n:012d}"


def common(event_name, event_sequence, elapsed, source_type="CONTROLLED_SCENARIO"):
    return {
        "event_id": uid(event_sequence),
        "event_name": event_name,
        "source_type": source_type,
        "run_id": uid(999),
        "event_sequence": event_sequence,
        "run_elapsed_seconds": elapsed,
        "game_version": "1.2.3",
        "schema_version": "2.0",
    }


def load_gateway(tmp):
    tmp = Path(tmp)
    (tmp / "test-token").write_text("t" * 64)
    (tmp / "ingest-key").write_text("i" * 64)
    (tmp / "dedupe-key").write_text("11" * 32)
    os.environ["PANDOK_DB_PATH"] = str(tmp / "aggregate.sqlite3")
    os.environ["PANDOK_TEST_TOKEN_PATH"] = str(tmp / "test-token")
    os.environ["PANDOK_INGEST_KEY_PATH"] = str(tmp / "ingest-key")
    os.environ["PANDOK_DEDUPE_KEY_PATH"] = str(tmp / "dedupe-key")
    exact_schema = os.environ.get("PANDOK_TEST_SCHEMA_PATH")
    if exact_schema:
        os.environ["PANDOK_SCHEMA_PATH"] = exact_schema
        os.environ.pop("PANDOK_ALLOW_NONCANONICAL_SCHEMA", None)
    else:
        os.environ["PANDOK_SCHEMA_PATH"] = str(CONTRACT_PATH)
        os.environ.pop("PANDOK_ALLOW_NONCANONICAL_SCHEMA", None)

    spec = importlib.util.spec_from_file_location("gateway_v2_tested", GATEWAY_DIR / "app_phase2_v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_invalid(gw, payload):
    try:
        gw.validate_client_event(payload)
    except gw.HTTPException as exc:
        assert exc.status_code == 422
        return
    raise AssertionError("payload unexpectedly validated")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        gw = load_gateway(tmp)

        run_started = common("run_started", 1, 0)
        run_started.update({
            "map_id": "forest",
            "starting_max_hp": 100,
            "starting_weapon_id": "bone",
        })

        shown = common("upgrade_options_shown", 2, 12.5)
        shown.update({
            "choice_id": uid(1002),
            "choice_sequence": 1,
            "choice_source": "level_up_upgrade",
            "player_level": 2,
            "options": [
                {"slot": 1, "item_id": "bone", "rarity": "uncommon", "acquisition_count_before": 0},
                {"slot": 2, "item_id": "fireball", "rarity": "rare", "effect_type": "damage", "effect_value_before": 1.25},
            ],
        })

        statue = common("upgrade_options_shown", 3, 20)
        statue.update({
            "choice_id": uid(1003),
            "choice_sequence": 2,
            "choice_source": "statue",
            "options": [
                {"slot": 1, "item_id": "horseshoe", "rarity": "common"},
                {"slot": 2, "item_id": "gold_ingot", "rarity": "epic"},
                {"slot": 3, "item_id": "hourglass", "rarity": "legendary"},
            ],
        })

        selected = common("upgrade_selected", 4, 21)
        selected.update({
            "choice_id": uid(1003),
            "choice_sequence": 2,
            "choice_source": "statue",
            "selected_slot": 3,
            "selected_item_id": "hourglass",
            "selected_rarity": "legendary",
            "acquisition_count_before": 0,
            "acquisition_count_after": 1,
            "effect_type": "cooldown",
            "effect_value_before": 0,
            "effect_value_after": 0.9,
        })

        checkpoint = common("run_checkpoint", 5, 60)
        checkpoint.update({
            "checkpoint_number": 1,
            "player_level": 3,
            "current_xp": 15.5,
            "xp_to_next_level": 20.5,
            "hp_percent": 72.5,
            "total_kills": 40,
            "total_xp_collected": 55.25,
            "current_gold": 12.5,
            "total_gold_collected": 30.5,
            "hearts_collected": 2,
            "total_healing_received": 15.0,
            "magnets_collected": 1,
            "miniboss_waves_cleared": 0,
            "active_upgrades": [
                {"item_id": "hourglass", "acquisition_count": 1, "effect_type": "cooldown", "effect_value": 0.9}
            ],
        })

        ended = common("run_ended", 6, 123.5, source_type="LOAD_TEST")
        ended.update({
            "end_reason": "player_quit",
            "final_level": 4,
            "total_kills": 57,
            "total_xp_collected": 88.5,
            "current_gold": 22.5,
            "total_gold_collected": 50,
            "hearts_collected": 2,
            "total_healing_received": 17.5,
            "magnets_collected": 1,
            "miniboss_waves_reached": 1,
            "miniboss_waves_cleared": 1,
            "final_upgrades": [
                {"item_id": "hourglass", "acquisition_count": 1, "effect_type": "cooldown", "effect_value": 0.9}
            ],
        })

        for payload in [run_started, shown, statue, selected, checkpoint, ended]:
            gw.validate_client_event(payload)
            assert gw.aggregate_event(payload) is True

        class FakeRequest:
            def __init__(self, headers):
                self.headers = headers

        assert gw._authorized(FakeRequest({
            "x-pandok-controlled-test": "1",
            "x-pandok-test-token": "t" * 64,
        }), ended) is True

        # Same event_id must dedupe.
        assert gw.aggregate_event(ended) is False

        # Old Phase 2.8 identity/wall-clock fields are forbidden by canonical v2 shape.
        old = dict(run_started)
        old["anonymous_user_id"] = uid(555)
        expect_invalid(gw, old)

        old2 = dict(run_started)
        old2["schema_version"] = "1.0"
        expect_invalid(gw, old2)

        session = common("session_started", 7, 0)
        expect_invalid(gw, session)

        bad_statue = dict(statue)
        bad_statue["event_id"] = uid(8)
        bad_statue["options"] = bad_statue["options"][:2]
        expect_invalid(gw, bad_statue)

        bad_chest = dict(selected)
        bad_chest["event_id"] = uid(9)
        bad_chest["selected_item_id"] = "bone"
        expect_invalid(gw, bad_chest)

        db = sqlite3.connect(Path(tmp) / "aggregate.sqlite3")
        event_count = db.execute("SELECT SUM(event_count) FROM event_counts").fetchone()[0]
        assert event_count == 6, event_count
        assert db.execute("SELECT COUNT(*) FROM run_end_counts_v2").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM checkpoint_upgrade_state_counts_v2").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM final_upgrade_state_counts_v2").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM upgrade_option_counts_v2").fetchone()[0] == 5
        db.close()

        print("PASS: canonical telemetry-event-v2 validation and v2 aggregation tests")


if __name__ == "__main__":
    main()
