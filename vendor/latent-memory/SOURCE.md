# Latent Memory — Upstream Source

- **Repository**: https://github.com/lxin73699-Claude/Latent-memory.git
- **Commit**: `2bc89a13ba0178663de2c1a0ca341401deab4405`
- **Date**: 2026-08-09 16:21:12 +0000
- **Subject**: 并入 main：第二十四批同步（--append 终端写入口 ＋ 三份随包文档说明）

This directory is a frozen snapshot of `src/` and `LICENSE` from the upstream
repository.  Do not modify these files in place; contribute changes upstream
and update the vendored snapshot as a whole.

The Docker build copies this directory into `/app/vendor/latent-memory/` and
the MCP server is launched from there.  No dynamic `git clone` of `main` is
performed at build time or run time.
