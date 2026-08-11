#!/usr/bin/env python3
"""
ensure_memory_mcp.py — Prism-managed bootstrapping for Codex config.

Idempotent: safe to run on every container start.
- Creates required directories and files under /data/sevis-memory
- Ensures /data/home/workspace exists
- Manages two independent Prism blocks in /data/home/.codex/config.toml:
  (a) Top-level reasoning keys (model_reasoning_effort, …) at file start
  (b) [mcp_servers.memory] section for Latent Memory MCP
- If a non-Prism-managed version of either block exists, exits with an
  error and asks for manual resolution.
"""

import os
import sys
import tempfile
import tomllib
from pathlib import Path

# ---------- constants ----------

PRISM_MARKER_START = "# >>> Prism managed: mcp_servers.memory (do not edit by hand) >>>"
PRISM_MARKER_END = "# <<< Prism managed: mcp_servers.memory <<<"

# ---- Prism-managed Codex reasoning top-level keys ----

PRISM_REASONING_START = "# >>> Prism managed: codex reasoning (do not edit by hand) >>>"
PRISM_REASONING_END = "# <<< Prism managed: codex reasoning <<<"

REASONING_BLOCK = """\
model_reasoning_effort = "high"
model_reasoning_summary = "detailed"
model_supports_reasoning_summaries = true
hide_agent_reasoning = false
show_raw_agent_reasoning = true
"""

_REASONING_KEYS = {
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_supports_reasoning_summaries",
    "hide_agent_reasoning",
    "show_raw_agent_reasoning",
}

MEMORY_BLOCK = """\
[mcp_servers.memory]
command = "/opt/venv/bin/python"
args = [
  "/app/vendor/latent-memory/src/mcp_server.py",
  "--corpus",
  "/data/sevis-memory/memory",
  "--threads",
  "/data/sevis-memory/threads.jsonl",
  "--timezone",
  "Asia/Shanghai"
]
cwd = "/app/vendor/latent-memory/src"
enabled = true
required = true
startup_timeout_sec = 15
tool_timeout_sec = 60
"""

SEVIS_DIR = Path("/data/sevis-memory")
MEMORY_DIR = SEVIS_DIR / "memory"
THREADS_FILE = SEVIS_DIR / "threads.jsonl"
WORKSPACE_DIR = Path("/data/home/workspace")
CODEX_CONFIG = Path("/data/home/.codex/config.toml")


# ---------- helpers ----------

def ensure_dir(path: Path, mode: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(mode)


def ensure_file(path: Path, mode: int) -> None:
    """Create the file if missing; always enforce *mode* (e.g. 0600)."""
    if not path.exists():
        path.touch()
    path.chmod(mode)


def read_config() -> str:
    if CODEX_CONFIG.exists():
        return CODEX_CONFIG.read_text(encoding="utf-8")
    return ""


def write_config_atomic(text: str) -> None:
    """Atomically write *text* to CODEX_CONFIG via a temp file + os.replace."""
    cfg_dir = CODEX_CONFIG.parent
    cfg_dir.mkdir(parents=True, exist_ok=True)

    tmp_fd = -1
    tmp_path = ""
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".toml", prefix=".config-", dir=str(cfg_dir), text=True
        )
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, str(CODEX_CONFIG))
    except Exception:
        # Clean up temp file, leave original unchanged
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


# ---------- TOML-aware block stripping & validation ----------

def _strip_block(config: str, start_marker: str, end_marker: str) -> str:
    """Remove the Prism block delimited by *start_marker* / *end_marker*
    from *config*.  No-op when the markers are absent."""
    if start_marker in config and end_marker in config:
        s = config.index(start_marker)
        e = config.index(end_marker) + len(end_marker)
        return config[:s] + config[e:]
    return config


def _parse_toml_safe(text: str):
    """Parse *text* with tomllib.  Returns the parsed dict on success,
    or ``None`` when the text is not valid TOML."""
    try:
        return tomllib.loads(text)
    except Exception:
        return None


# ---------- marker validation ----------

def _validate_markers(config: str) -> int:
    """Return 0 if markers are valid, 1 with error on stderr otherwise.

    Valid states:
      - both markers absent  (return 0 → append)
      - each appears exactly once and START before END  (return 0 → update)

    Invalid → return 1, don't touch config.
    """
    start_count = config.count(PRISM_MARKER_START)
    end_count = config.count(PRISM_MARKER_END)

    if start_count == 0 and end_count == 0:
        return 0  # append

    if start_count == 1 and end_count == 1:
        start_pos = config.index(PRISM_MARKER_START)
        end_pos = config.index(PRISM_MARKER_END)
        if start_pos < end_pos:
            return 0  # update
        else:
            print(
                "[ensure_memory_mcp] ERROR: Prism markers are reversed "
                "(END before START).  Fix manually in "
                f"{CODEX_CONFIG}.",
                file=sys.stderr,
            )
            return 1

    # Anything else is invalid
    detail = []
    if start_count > 1:
        detail.append(f"START×{start_count}")
    if end_count > 1:
        detail.append(f"END×{end_count}")
    if start_count == 0 and end_count > 0:
        detail.append("missing START")
    if end_count == 0 and start_count > 0:
        detail.append("missing END")

    print(
        "[ensure_memory_mcp] ERROR: Prism marker integrity broken — "
        + ", ".join(detail)
        + f".  Fix manually in {CODEX_CONFIG}.",
        file=sys.stderr,
    )
    return 1


def _check_markers(config: str, start_marker: str, end_marker: str,
                   label: str) -> int:
    """Generic marker validation.  Returns:
      0 — both absent (append)
      0 — 1/1 and START before END (update)
      1 — invalid (error printed to stderr)
    """
    sc = config.count(start_marker)
    ec = config.count(end_marker)
    if sc == 0 and ec == 0:
        return 0
    if sc == 1 and ec == 1:
        if config.index(start_marker) < config.index(end_marker):
            return 0
    # build detail
    detail = []
    if sc > 1:
        detail.append(f"START×{sc}")
    if ec > 1:
        detail.append(f"END×{ec}")
    if sc == 0 and ec > 0:
        detail.append("missing START")
    if ec == 0 and sc > 0:
        detail.append("missing END")
    if sc == 1 and ec == 1:
        detail.append("END before START")
    print(
        f"[ensure_memory_mcp] ERROR: {label} marker integrity broken — "
        + ", ".join(detail)
        + f".  Fix manually in {CODEX_CONFIG}.",
        file=sys.stderr,
    )
    return 1


# ---------- reasoning config management ----------

def _manage_reasoning(config: str) -> tuple[str, bool]:
    """Ensure the Prism reasoning block is at the very top of the file.

    Returns (config_text, changed).  Raises SystemExit(1) on conflict
    or marker corruption.
    """
    # 1. Validate marker integrity
    if _check_markers(config, PRISM_REASONING_START, PRISM_REASONING_END,
                      "codex-reasoning") != 0:
        raise SystemExit(1)

    # 2. Strip the old reasoning block (wherever it is) → base
    base = _strip_block(config, PRISM_REASONING_START, PRISM_REASONING_END)

    # 3. TOML-parse the remainder to detect conflicts
    parsed = _parse_toml_safe(base)
    if parsed is None:
        print(
            "[ensure_memory_mcp] ERROR: "
            f"{CODEX_CONFIG} is not valid TOML after removing "
            "the Prism reasoning block.  Fix the config manually.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    conflict_keys = [k for k in _REASONING_KEYS if k in parsed]
    if conflict_keys:
        print(
            "[ensure_memory_mcp] ERROR: One or more top-level reasoning "
            f"keys ({', '.join(sorted(conflict_keys))}) already exist "
            "outside the Prism-managed reasoning block in "
            f"{CODEX_CONFIG}.",
            file=sys.stderr,
        )
        print(
            "[ensure_memory_mcp] Remove them manually before letting "
            "Prism manage them.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # 4. Build the managed block and prepend at file top
    block = f"{PRISM_REASONING_START}\n{REASONING_BLOCK}{PRISM_REASONING_END}\n"

    changed = PRISM_REASONING_START in config
    if changed:
        print("[ensure_memory_mcp] Removing old codex-reasoning block; "
              "re-inserting at top.")

    if base:
        new_config = block + "\n" + base.lstrip("\n")
    else:
        new_config = block + "\n"

    if not changed:
        print("[ensure_memory_mcp] Inserted codex-reasoning block at top.")

    return new_config, True


# ---------- main ----------

def main() -> int:
    # 1. Directories & files
    print("[ensure_memory_mcp] Creating directories …")
    ensure_dir(SEVIS_DIR, 0o700)
    ensure_dir(MEMORY_DIR, 0o700)
    ensure_dir(WORKSPACE_DIR, 0o755)
    ensure_file(THREADS_FILE, 0o600)
    print(f"[ensure_memory_mcp]   {MEMORY_DIR}")
    print(f"[ensure_memory_mcp]   {THREADS_FILE}")
    print(f"[ensure_memory_mcp]   {WORKSPACE_DIR}")

    # 2. Read config
    config = read_config()
    print(f"[ensure_memory_mcp] Reading {CODEX_CONFIG} …")

    # 3. Reasoning top-level keys (validates + strips old block + prepends)
    try:
        config, _rc = _manage_reasoning(config)
    except SystemExit as e:
        return e.code if e.code is not None else 1

    # 4. Memory MCP section
    if _validate_markers(config) != 0:
        return 1

    # Strip the old memory block, then TOML-parse the remainder
    base = _strip_block(config, PRISM_MARKER_START, PRISM_MARKER_END)
    parsed = _parse_toml_safe(base)
    if parsed is None:
        print(
            "[ensure_memory_mcp] ERROR: "
            f"{CODEX_CONFIG} is not valid TOML after removing "
            "the Prism memory block.  Fix the config manually.",
            file=sys.stderr,
        )
        return 1

    # Check for mcp_servers.memory in parsed (any quoting variant lands
    # under the same dict key after tomllib parsing)
    if ("mcp_servers" in parsed
            and isinstance(parsed["mcp_servers"], dict)
            and "memory" in parsed["mcp_servers"]):
        print(
            "[ensure_memory_mcp] ERROR: A non-Prism-managed "
            "[mcp_servers.memory] (or quoted variant) section "
            f"already exists in {CODEX_CONFIG}.",
            file=sys.stderr,
        )
        print(
            "[ensure_memory_mcp] Remove or rename it manually "
            "before letting Prism manage it.",
            file=sys.stderr,
        )
        return 1

    block = f"{PRISM_MARKER_START}\n{MEMORY_BLOCK}{PRISM_MARKER_END}\n"

    if PRISM_MARKER_START in config:
        print("[ensure_memory_mcp] Updating existing Prism-managed "
              "memory block.")
    else:
        print("[ensure_memory_mcp] Appending Prism-managed memory block.")

    if base.strip():
        config = base.rstrip("\n") + "\n\n" + block
    else:
        config = block + "\n"

    write_config_atomic(config)
    print(f"[ensure_memory_mcp] Wrote {CODEX_CONFIG}")
    print("[ensure_memory_mcp] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
