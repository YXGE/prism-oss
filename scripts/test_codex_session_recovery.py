"""Unit checks for persistent Codex chat recovery across container restarts."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
import atexit
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_IMPORT_RUNTIME = Path(tempfile.mkdtemp(prefix="prism-codex-recovery-"))
atexit.register(shutil.rmtree, _IMPORT_RUNTIME, True)
os.environ["PRISM_DATA_DIR"] = str(_IMPORT_RUNTIME / "data")

import terminal_manager as tm


SESSION_UUID = "12345678-1234-1234-1234-123456789abc"


class CodexSessionRecoveryTests(unittest.TestCase):
    def test_create_session_uses_codex_resume(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            captured = {}

            def fake_run(args, timeout=0, **_kwargs):
                captured["args"] = args
                return type("Result", (), {"returncode": 0, "stderr": ""})()

            with (
                patch.object(tm, "HOME", temp_dir),
                patch.object(tm, "_tmux_sessions_raw", return_value=[]),
                patch.object(tm, "_run", side_effect=fake_run),
                patch.object(tm, "ensure_pipe"),
            ):
                result = tm.create_session(
                    "memory-check",
                    temp_dir,
                    session_type="codex",
                    resume_sid="codex-" + SESSION_UUID,
                )

            self.assertTrue(result["ok"])
            wrapped = captured["args"][-1]
            self.assertIn(f"codex resume {SESSION_UUID}", wrapped)

    def test_old_snapshot_uses_persisted_codex_map(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rollout = root / f"rollout-2026-08-12T00-00-00-{SESSION_UUID}.jsonl"
            rollout.write_text("{}\n", encoding="utf-8")
            mapping = root / "codex_session_map.json"
            mapping.write_text(
                json.dumps({"memory-check": {"jsonl_path": str(rollout)}}),
                encoding="utf-8",
            )
            with patch.object(tm, "CODEX_SESSION_MAP_PATH", mapping):
                resume_id, jsonl_path = tm._codex_resume_data_from_snapshot(
                    "memory-check",
                    {"kind": "codex", "cwd": temp_dir},
                )

            self.assertEqual(resume_id, SESSION_UUID)
            self.assertEqual(jsonl_path, str(rollout))

    def test_restore_enriches_snapshot_and_resumes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rollout = root / f"rollout-2026-08-12T00-00-00-{SESSION_UUID}.jsonl"
            rollout.write_text("{}\n", encoding="utf-8")
            state_path = root / "live_sessions.json"
            state_path.write_text(
                json.dumps({
                    "memory-check": {
                        "name": "memory-check",
                        "kind": "codex",
                        "cwd": temp_dir,
                    }
                }),
                encoding="utf-8",
            )
            map_path = root / "codex_session_map.json"
            map_path.write_text(
                json.dumps({"memory-check": {"jsonl_path": str(rollout)}}),
                encoding="utf-8",
            )
            calls = []

            def fake_create(*args, **kwargs):
                calls.append((args, kwargs))
                return {"ok": True}

            with (
                patch.object(tm, "LIVE_STATE_PATH", state_path),
                patch.object(tm, "CODEX_SESSION_MAP_PATH", map_path),
                patch.object(tm, "_tmux_sessions_raw", return_value=[]),
                patch.object(tm, "create_session", side_effect=fake_create),
                patch.object(tm.time, "sleep"),
            ):
                restored = tm._restore_persisted_codex_sessions()

            self.assertEqual(restored, ["memory-check"])
            self.assertEqual(calls[0][1]["resume_sid"], SESSION_UUID)
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["memory-check"]["session_id"], "codex-" + SESSION_UUID)
            self.assertEqual(saved["memory-check"]["jsonl_path"], str(rollout))

    def test_empty_live_state_is_seeded_from_old_codex_map(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rollout = root / f"rollout-2026-08-12T00-00-00-{SESSION_UUID}.jsonl"
            rollout.write_text(
                json.dumps({
                    "type": "session_meta",
                    "payload": {"id": SESSION_UUID, "cwd": temp_dir},
                }) + "\n",
                encoding="utf-8",
            )
            state_path = root / "live_sessions.json"
            state_path.write_text("{}", encoding="utf-8")
            map_path = root / "codex_session_map.json"
            map_path.write_text(
                json.dumps({
                    "memory-check": {
                        "jsonl_path": str(rollout),
                        "updated_at": 123,
                    }
                }),
                encoding="utf-8",
            )

            with (
                patch.object(tm, "LIVE_STATE_PATH", state_path),
                patch.object(tm, "CODEX_SESSION_MAP_PATH", map_path),
                patch.object(tm, "_archive_duplicate_exists", return_value=False),
            ):
                seeded = tm._seed_live_state_from_codex_map()

            self.assertEqual(seeded["memory-check"]["resume_id"], SESSION_UUID)
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["memory-check"]["cwd"], temp_dir)
            self.assertTrue(saved["memory-check"]["migrated_from_codex_map"])

    def test_user_close_removes_stale_codex_map_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "live_sessions.json"
            state_path.write_text("{}", encoding="utf-8")
            map_path = root / "codex_session_map.json"
            map_path.write_text(
                json.dumps({"memory-check": {"jsonl_path": "unused"}}),
                encoding="utf-8",
            )
            with (
                patch.object(tm, "LIVE_STATE_PATH", state_path),
                patch.object(tm, "CODEX_SESSION_MAP_PATH", map_path),
            ):
                tm._drop_live_state("memory-check")

            self.assertEqual(json.loads(map_path.read_text(encoding="utf-8")), {})

    def test_empty_tmux_does_not_erase_failed_recovery_state(self):
        with (
            patch.object(tm, "_tmux_sessions_raw", return_value=[]),
            patch.object(tm, "_read_live_state", return_value={"memory-check": {"kind": "codex"}}),
            patch.object(tm, "_restore_persisted_codex_sessions", return_value=[]),
            patch.object(tm, "_write_live_state") as write_state,
        ):
            self.assertEqual(tm.list_sessions(), [])
        write_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
