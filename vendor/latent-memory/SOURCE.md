# Latent Memory — Upstream Source

- **Repository**: https://github.com/YXGE/Latent-memory.git
- **Commit**: `248d1accfd7424d228ef3e2523b40260db667e1d`
- **Date**: 2026-08-11 13:12:03 +0000
- **Subject**: Merge upstream main into YXGE main

This directory contains the zero-dependency stdio MCP runtime subset from
upstream `src/` plus `LICENSE`. Do not modify these files in place; contribute
changes upstream and update the vendored runtime subset as a whole.

ChatGPT Action bridge and standalone deployment files are intentionally
excluded: Prism talks to Latent Memory only through the Codex stdio MCP
connection.

The Docker build copies this directory into `/app/vendor/latent-memory/` and
the MCP server is launched from there.  No dynamic `git clone` of `main` is
performed at build time or run time.
