"""Regression test suite for ensure_memory_mcp.py — portable across OS.

Uses tempfile.TemporaryDirectory under the repo root so all scratch data
stays on the same disk.  No hard-coded absolute paths, no shutil.rmtree on
fixed locations.  Safe to commit.
"""

import os
import re
import subprocess
import sys
import tempfile
import platform
from pathlib import Path

# ---- locate repo & scripts ----
_THIS_FILE = Path(__file__).resolve()
_SCRIPTS_DIR = _THIS_FILE.parent
_REPO_ROOT = _SCRIPTS_DIR.parent
sys.path.insert(0, str(_SCRIPTS_DIR))

import ensure_memory_mcp as m

ON_WINDOWS = platform.system() == "Windows"
_passed = 0
_failed = 0
_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        _failures.append(label)
        print(f"  FAIL  {label}")


def _perms(p: Path) -> str:
    return oct(os.stat(str(p)).st_mode)[-4:]


def _bits_ok(p: Path, expected: str) -> bool:
    if not p.exists():
        return False
    if ON_WINDOWS:
        return True  # chmod syscall was invoked; trust it
    return _perms(p) == expected


# ---------- test helpers using a fresh TemporaryDirectory ----------

def _fresh_env():
    """Create a fresh isolated env inside a TemporaryDirectory under repo root.
    Returns (td, home, data).  Caller must use `with td:` or `td.cleanup()`."""
    td = tempfile.TemporaryDirectory(dir=str(_REPO_ROOT), prefix=".mcp-test-")
    home = Path(td.name) / "home"
    data = Path(td.name) / "data"
    (home / ".codex").mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    return td, home, data


def _set_paths(home: Path, data: Path) -> None:
    m.SEVIS_DIR = data / "sevis-memory"
    m.MEMORY_DIR = m.SEVIS_DIR / "memory"
    m.THREADS_FILE = m.SEVIS_DIR / "threads.jsonl"
    m.WORKSPACE_DIR = home / "workspace"
    m.CODEX_CONFIG = home / ".codex" / "config.toml"


def _read_cfg() -> str:
    if m.CODEX_CONFIG.exists():
        return m.CODEX_CONFIG.read_text(encoding="utf-8")
    return ""


def _write_cfg(text: str) -> None:
    m.CODEX_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    m.CODEX_CONFIG.write_text(text, encoding="utf-8")


# ================================================================
# 1. Permissions: fresh run
# ================================================================
print("=" * 60)
print("1. Permissions: fresh run")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    rc = m.main()
    check("exit 0", rc == 0)
    check("sevis-memory 0700", _bits_ok(m.SEVIS_DIR, "0700"))
    check("memory dir 0700", _bits_ok(m.MEMORY_DIR, "0700"))
    check("workspace 0755", _bits_ok(m.WORKSPACE_DIR, "0755"))
    check("threads.jsonl 0600", _bits_ok(m.THREADS_FILE, "0600"))
    check("config.toml 0600", _bits_ok(m.CODEX_CONFIG, "0600"))

# ================================================================
# 2. existing threads.jsonl fixed to 0600
# ================================================================
print("=" * 60)
print("2. existing threads.jsonl fixed to 0600")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    m.SEVIS_DIR.mkdir(parents=True)
    m.THREADS_FILE.touch()
    os.chmod(str(m.THREADS_FILE), 0o644)
    rc = m.main()
    check("exit 0", rc == 0)
    check("corrected to 0600", _bits_ok(m.THREADS_FILE, "0600"))

# ================================================================
# 3. Idempotent re-run
# ================================================================
print("=" * 60)
print("3. Idempotent re-run")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    m.main()
    rc2 = m.main()
    check("exit 0 on re-run", rc2 == 0)
    c = _read_cfg()
    check("only one [mcp_servers.memory]", c.count("[mcp_servers.memory]") == 1)
    check("memory MCP required", "required = true" in c)
    check(
        "memory timezone explicit",
        '"--timezone"' in c and '"Asia/Shanghai"' in c,
    )
    check(
        "memory tools approved by default",
        'default_tools_approval_mode = "approve"' in c,
    )

# ================================================================
# 4. Marker integrity
# ================================================================
print("=" * 60)
print("4. Marker integrity")

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("line1\n" + m.PRISM_MARKER_START + "\nline3\n")
    orig = _read_cfg()
    rc = m.main()
    check("4a exit!=0 (missing END)", rc != 0)
    check("4a config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("line1\n" + m.PRISM_MARKER_END + "\nline3\n")
    orig = _read_cfg()
    rc = m.main()
    check("4b exit!=0 (missing START)", rc != 0)
    check("4b config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_MARKER_START + "\nfoo\n"
               + m.PRISM_MARKER_START + "\nbar\n"
               + m.PRISM_MARKER_END + "\n")
    orig = _read_cfg()
    rc = m.main()
    check("4c exit!=0 (STARTx2)", rc != 0)
    check("4c config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_MARKER_END + "\nfoo\n" + m.PRISM_MARKER_START + "\n")
    orig = _read_cfg()
    rc = m.main()
    check("4d exit!=0 (reversed)", rc != 0)
    check("4d config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_MARKER_START + "\nfoo\n"
               + m.PRISM_MARKER_END + "\nbar\n"
               + m.PRISM_MARKER_END + "\n")
    orig = _read_cfg()
    rc = m.main()
    check("4e exit!=0 (ENDx2)", rc != 0)
    check("4e config unchanged", _read_cfg() == orig)

# ================================================================
# 5. Conflict detection — standalone (no markers)
# ================================================================
print("=" * 60)
print("5. Conflict detection — standalone")

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg('[mcp_servers.memory]\ncommand = "x"\n')
    orig = _read_cfg()
    rc = m.main()
    check("5a exit!=0 (bare conflict)", rc != 0)
    check("5a config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg('[mcp_servers."memory"]\ncommand = "x"\n')
    orig = _read_cfg()
    rc = m.main()
    check("5b exit!=0 (quoted conflict)", rc != 0)
    check("5b config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_MARKER_START + "\n[mcp_servers.memory]\ncommand=\"x\"\n"
               + m.PRISM_MARKER_END + "\n")
    rc = m.main()
    check("5c exit 0 (Prism-managed OK)", rc == 0)

# ================================================================
# 6. Conflict — section OUTSIDE a valid Prism managed block
# ================================================================
print("=" * 60)
print("6. Conflict — memory section outside managed block")

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[mcp_servers.memory]\ncmd=\"bad\"\n"
               + m.PRISM_MARKER_START + "\n[mcp_servers.memory]\ncmd=\"ok\"\n"
               + m.PRISM_MARKER_END + "\n")
    orig = _read_cfg()
    rc = m.main()
    check("6a exit!=0 (bare BEFORE block)", rc != 0)
    check("6a config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_MARKER_START + "\n[mcp_servers.memory]\ncmd=\"ok\"\n"
               + m.PRISM_MARKER_END + "\n"
               + "[mcp_servers.memory]\ncmd=\"bad\"\n")
    orig = _read_cfg()
    rc = m.main()
    check("6b exit!=0 (bare AFTER block)", rc != 0)
    check("6b config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg('[mcp_servers."memory"]\ncmd="bad"\n'
               + m.PRISM_MARKER_START + "\n[mcp_servers.memory]\ncmd=\"ok\"\n"
               + m.PRISM_MARKER_END + "\n")
    orig = _read_cfg()
    rc = m.main()
    check("6c exit!=0 (quoted BEFORE block)", rc != 0)
    check("6c config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_MARKER_START + "\n[mcp_servers.memory]\ncmd=\"ok\"\n"
               + m.PRISM_MARKER_END + "\n"
               + '[mcp_servers."memory"]\ncmd="bad"\n')
    orig = _read_cfg()
    rc = m.main()
    check("6d exit!=0 (quoted AFTER block)", rc != 0)
    check("6d config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_MARKER_START + "\n[mcp_servers.memory]\ncmd=\"x\"\n"
               + m.PRISM_MARKER_END + "\n")
    rc = m.main()
    check("6e exit 0 (single managed block idempotent)", rc == 0)
    c = _read_cfg()
    check("6e still only one [mcp_servers.memory]",
          c.count("[mcp_servers.memory]") == 1)

# ================================================================
# 7. Atomic write — simulated failure
# ================================================================
print("=" * 60)
print("7. Atomic write — simulated failure")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[other]\nkey = 42\n")
    orig = _read_cfg()
    _original_replace = os.replace

    def _failing_replace(src: str, dst: str) -> None:
        raise OSError("Simulated disk full")

    os.replace = _failing_replace  # type: ignore[assignment]
    try:
        rc = m.main()
        check("7 OSError propagated", False)
    except OSError:
        check("7 OSError raised", True)
    finally:
        os.replace = _original_replace  # type: ignore[assignment]

    check("7 config unchanged", _read_cfg() == orig)
    cfg_dir = m.CODEX_CONFIG.parent
    temp_left = list(cfg_dir.glob(".config-*.toml"))
    check("7 no stale temp files", len(temp_left) == 0)

# ================================================================
# 8. Existing config preserved
# ================================================================
print("=" * 60)
print("8. Existing config preserved")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[some_setting]\nvalue = 42\n\n"
               "[mcp_servers.other]\ncommand = \"other-tool\"\n"
               "args = [\"--flag\"]\n")
    rc = m.main()
    check("8 exit 0", rc == 0)
    c = _read_cfg()
    check("8 [some_setting] preserved", "[some_setting]" in c)
    check("8 [mcp_servers.other] preserved", "[mcp_servers.other]" in c)
    parsed = m._parse_toml_safe(c)
    check(
        "8 existing MCP gets approval default",
        parsed["mcp_servers"]["other"]["default_tools_approval_mode"]
        == "approve",
    )
    check("8 Prism block appended", m.PRISM_MARKER_START in c)

# ================================================================
# 9. Entrypoint non-fatal guard structure + shell syntax
# ================================================================
print("=" * 60)
print("9. Entrypoint guard structure & shell syntax")

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[mcp_servers.memory]\ncommand=\"bad\"\n")
    rc = m.main()
    check("9a conflict exits non-zero (entrypoint WARNING branch)", rc != 0)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    rc2 = m.main()
    check("9b normal exits 0 (entrypoint passes through)", rc2 == 0)

entrypoint_path = _REPO_ROOT / "docker-entrypoint.sh"
ep_text = entrypoint_path.read_text(encoding="utf-8")

check("9c init wrapped in 'if !' guard",
      "if ! /opt/venv/bin/python /app/scripts/ensure_memory_mcp.py" in ep_text)

# Verify no 'exit' command after the WARNING message inside the fi block
warn_idx = ep_text.find("Codex configuration bootstrap failed")
after_warn = ep_text[warn_idx:] if warn_idx != -1 else ""
fi_idx = after_warn.find("fi") if after_warn else -1
between = after_warn[:fi_idx] if fi_idx != -1 else ""
check("9c no 'exit' after WARNING in guard block",
      "exit" not in between)

# bash -n syntax check
try:
    result = subprocess.run(
        ["bash", "-n", str(entrypoint_path)],
        capture_output=True, text=True, timeout=10,
    )
    check("9d bash -n docker-entrypoint.sh passed",
          result.returncode == 0 and result.stderr == "")
except FileNotFoundError:
    print("  SKIP  bash not found on this host (OK)")
except Exception as exc:
    check(f"9d bash -n error: {exc}", False)

# ================================================================
# 10. No temp dirs leaked in repo root
# ================================================================
print("=" * 60)
print("10. No temp dirs leaked in repo root")
leftover = list(_REPO_ROOT.glob(".mcp-test-*"))
check("10 no .mcp-test-* dirs remaining", len(leftover) == 0)

# ================================================================
# 11. Reasoning config management
# ================================================================
print("=" * 60)
print("11. Reasoning — fresh run: block at top, both blocks present")

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    rc = m.main()
    check("11a exit 0", rc == 0)
    c = _read_cfg()
    check("11a reasoning block present", m.PRISM_REASONING_START in c)
    check("11a memory block present", m.PRISM_MARKER_START in c)
    # Reasoning block must come first (before memory block)
    rpos = c.index(m.PRISM_REASONING_START)
    mpos = c.index(m.PRISM_MARKER_START)
    check("11a reasoning before memory", rpos < mpos)
    # All 5 keys present
    for k in m._REASONING_KEYS:
        check(f"11a key {k} present", k in c)

# ================================================================
print("=" * 60)
print("12. Reasoning — idempotent re-run")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    m.main()
    rc2 = m.main()
    check("12 exit 0 on re-run", rc2 == 0)
    c = _read_cfg()
    check("12 only one reasoning START", c.count(m.PRISM_REASONING_START) == 1)
    check("12 only one reasoning END", c.count(m.PRISM_REASONING_END) == 1)
    check("12 only one memory START", c.count(m.PRISM_MARKER_START) == 1)

# ================================================================
print("=" * 60)
print("13. Reasoning — marker integrity")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_REASONING_START + "\nfoo\n")
    orig = _read_cfg()
    rc = m.main()
    check("13a exit!=0 (missing END)", rc != 0)
    check("13a config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_REASONING_END + "\nbar\n")
    orig = _read_cfg()
    rc = m.main()
    check("13b exit!=0 (missing START)", rc != 0)
    check("13b config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_REASONING_START + "\nA\n"
               + m.PRISM_REASONING_START + "\nB\n"
               + m.PRISM_REASONING_END + "\n")
    orig = _read_cfg()
    rc = m.main()
    check("13c exit!=0 (STARTx2)", rc != 0)
    check("13c config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_REASONING_END + "\nfoo\n" + m.PRISM_REASONING_START + "\n")
    orig = _read_cfg()
    rc = m.main()
    check("13d exit!=0 (reversed)", rc != 0)
    check("13d config unchanged", _read_cfg() == orig)

# ================================================================
print("=" * 60)
print("14. Reasoning — conflict: key outside managed block")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg('model_reasoning_effort = "low"\n')
    orig = _read_cfg()
    rc = m.main()
    check("14a exit!=0 (key outside block)", rc != 0)
    check("14a config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg('# comment\nmodel_reasoning_summary = "short"\n')
    orig = _read_cfg()
    rc = m.main()
    check("14b exit!=0 (key outside block, with comment)", rc != 0)
    check("14b config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_REASONING_START + "\nmodel_reasoning_effort=\"high\"\n"
               + m.PRISM_REASONING_END + "\n"
               + "model_reasoning_effort = \"low\"\n")
    orig = _read_cfg()
    rc = m.main()
    check("14c exit!=0 (key AFTER managed block)", rc != 0)
    check("14c config unchanged", _read_cfg() == orig)

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("model_reasoning_effort = \"low\"\n"
               + m.PRISM_REASONING_START + "\nmodel_reasoning_effort=\"high\"\n"
               + m.PRISM_REASONING_END + "\n")
    orig = _read_cfg()
    rc = m.main()
    check("14d exit!=0 (key BEFORE managed block)", rc != 0)
    check("14d config unchanged", _read_cfg() == orig)

# ================================================================
print("=" * 60)
print("15. Reasoning — key inside managed block is OK (idempotent)")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_REASONING_START + "\n"
               + "model_reasoning_effort = \"high\"\n"
               + "model_reasoning_summary = \"detailed\"\n"
               + m.PRISM_REASONING_END + "\n")
    rc = m.main()
    check("15 exit 0 (keys inside block OK)", rc == 0)
    c = _read_cfg()
    check("15 reasoning marker still present",
          m.PRISM_REASONING_START in c)
    check("15 memory block also present",
          m.PRISM_MARKER_START in c)

# ================================================================
print("=" * 60)
print("16. Reasoning — both blocks coexist with existing config")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[some_setting]\nvalue = 42\n\n"
               "[mcp_servers.other]\ncommand = \"other-tool\"\n")
    rc = m.main()
    check("16 exit 0", rc == 0)
    c = _read_cfg()
    check("16 reasoning block present", m.PRISM_REASONING_START in c)
    check("16 memory block present", m.PRISM_MARKER_START in c)
    check("16 [some_setting] preserved", "[some_setting]" in c)
    check("16 [mcp_servers.other] preserved", "[mcp_servers.other]" in c)

# ================================================================
print("=" * 60)
print("17. Reasoning — output is valid TOML (tomllib parseable)")
try:
    import tomllib as _toml
except ImportError:
    import tomli as _toml  # type: ignore[no-redef]

td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[table_a]\nkey_a = 1\n[table_b]\nkey_b = 2\n")
    m.main()
    c = _read_cfg()
    try:
        _toml.loads(c)
        check("17 tomllib.loads success", True)
    except Exception as e:
        check(f"17 tomllib.loads failed: {e}", False)

# ================================================================
print("=" * 60)
print("18. Reasoning — update existing block replaces content")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(m.PRISM_REASONING_START + "\nmodel_reasoning_effort=\"medium\"\n"
               + m.PRISM_REASONING_END + "\n"
               + "[table]\nkey = 1\n")
    rc = m.main()
    check("18 exit 0", rc == 0)
    c = _read_cfg()
    check("18 updated to high", 'model_reasoning_effort = "high"' in c)
    check("18 old medium gone", '"medium"' not in c)

# ================================================================
print("=" * 60)
print("19. Reasoning — conflict: key inside [table] (not top-level) is OK")
# In TOML, a key after a [table] header belongs to that table, not root.
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[some_table]\nmodel_reasoning_effort = \"low\"\n")
    rc = m.main()
    check("19 exit 0 (key inside [table] is not top-level)", rc == 0)
    c = _read_cfg()
    check("19 reasoning block inserted at top",
          m.PRISM_REASONING_START in c)

# ================================================================
print("=" * 60)
print("20. Reasoning — empty config gets both blocks")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    rc = m.main()
    check("20 exit 0", rc == 0)
    c = _read_cfg()
    check("20 reasoning block present", m.PRISM_REASONING_START in c)
    check("20 memory block present", m.PRISM_MARKER_START in c)
    check("20 reasoning at top", c.startswith(m.PRISM_REASONING_START))

# ================================================================
print("=" * 60)
print("21. Reasoning — block relocated from middle to top")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[some_table]\nkey = 1\n"
               + m.PRISM_REASONING_START + "\n"
               + "model_reasoning_effort = \"high\"\n"
               + m.PRISM_REASONING_END + "\n")
    rc = m.main()
    check("21 exit 0", rc == 0)
    c = _read_cfg()
    check("21 reasoning at top", c.startswith(m.PRISM_REASONING_START))
    # tomllib verify: reasoning keys in root, not in some_table
    import tomllib as _t2
    parsed = _t2.loads(c)
    check("21 model_reasoning_effort in root",
          "model_reasoning_effort" in parsed)
    check("21 model_reasoning_effort NOT in some_table",
          "model_reasoning_effort" not in parsed.get("some_table", {}))

# ================================================================
print("=" * 60)
print("22. Reasoning — multi-line array with conflict key rejected")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg('my_array = [\n  1,\n  2\n]\nmodel_reasoning_effort = "low"\n')
    orig = _read_cfg()
    rc = m.main()
    check("22 exit!=0 (conflict key after multi-line array)", rc != 0)
    check("22 config unchanged", _read_cfg() == orig)

# ================================================================
print("=" * 60)
print("23. Memory — leading whitespace + trailing comment detected")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg('  [mcp_servers.memory] # my memory config\ncommand = "x"\n')
    orig = _read_cfg()
    rc = m.main()
    check("23 exit!=0 (ws+comment variant)", rc != 0)
    check("23 config unchanged", _read_cfg() == orig)

# ================================================================
print("=" * 60)
print("24. Memory — single-quoted variant detected")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[mcp_servers.'memory']\ncommand = \"x\"\n")
    orig = _read_cfg()
    rc = m.main()
    check("24 exit!=0 (single-quoted)", rc != 0)
    check("24 config unchanged", _read_cfg() == orig)

# ================================================================
print("=" * 60)
print("25. Invalid TOML rejected, config unchanged")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg("[table\nkey = \"unclosed table header\"\n")
    orig = _read_cfg()
    rc = m.main()
    check("25 exit!=0 (invalid TOML)", rc != 0)
    check("25 config unchanged", _read_cfg() == orig)

# ================================================================
print("=" * 60)
print("26. Entrypoint WARNING text updated")
entrypoint_path2 = _REPO_ROOT / "docker-entrypoint.sh"
ep2 = entrypoint_path2.read_text(encoding="utf-8")
check("26 says 'Codex configuration bootstrap failed'",
      "Codex configuration bootstrap failed" in ep2)
check("26 old 'Latent Memory MCP' text gone",
      "Latent Memory MCP bootstrap failed" not in ep2)

# ================================================================
print("=" * 60)
print("27. MCP approval defaults — quoted and plugin-scoped servers")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(
        '[mcp_servers."remote.docs"]\n'
        'url = "https://example.test/mcp"\n\n'
        '[plugins."sample@test".mcp_servers.browser]\n'
        'enabled = true\n'
    )
    rc = m.main()
    check("27 exit 0", rc == 0)
    c = _read_cfg()
    parsed = m._parse_toml_safe(c)
    check(
        "27 quoted top-level server approved",
        parsed["mcp_servers"]["remote.docs"]["default_tools_approval_mode"]
        == "approve",
    )
    check(
        "27 plugin server approved",
        parsed["plugins"]["sample@test"]["mcp_servers"]["browser"]
        ["default_tools_approval_mode"] == "approve",
    )

# ================================================================
print("=" * 60)
print("28. MCP approval defaults — explicit choices and tools preserved")
td, home, data = _fresh_env()
with td:
    _set_paths(home, data)
    _write_cfg(
        '[mcp_servers.sensitive]\n'
        'command = "sensitive-tool"\n'
        'default_tools_approval_mode = "prompt"\n\n'
        '[mcp_servers.sensitive.tools.read]\n'
        'approval_mode = "approve"\n\n'
        '[mcp_servers.ordinary]\n'
        'command = "ordinary-tool"\n\n'
        '[mcp_servers.ordinary.tools.delete]\n'
        'approval_mode = "prompt"\n'
    )
    rc = m.main()
    check("28 exit 0", rc == 0)
    first = _read_cfg()
    rc2 = m.main()
    second = _read_cfg()
    parsed = m._parse_toml_safe(second)
    check("28 idempotent re-run exits 0", rc2 == 0)
    check("28 output stable across re-run", first == second)
    check(
        "28 explicit prompt preserved",
        parsed["mcp_servers"]["sensitive"]["default_tools_approval_mode"]
        == "prompt",
    )
    check(
        "28 missing server default added",
        parsed["mcp_servers"]["ordinary"]["default_tools_approval_mode"]
        == "approve",
    )
    check(
        "28 per-tool prompt preserved",
        parsed["mcp_servers"]["ordinary"]["tools"]["delete"]["approval_mode"]
        == "prompt",
    )

# ================================================================
print()
print("=" * 60)
print(f"RESULTS: {_passed} passed, {_failed} failed")
if _failures:
    print("FAILURES:")
    for f in _failures:
        print(f"  - {f}")
print("=" * 60)
raise SystemExit(0 if _failed == 0 else 1)
