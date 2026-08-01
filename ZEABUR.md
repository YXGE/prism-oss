# Prism on Zeabur

This deployment runs the real Codex CLI in a persistent Linux container and
exposes Prism's mobile web UI. Treat dashboard access as root-equivalent access
to the container.

## 1. Create the service

Deploy this directory as a Git or Local Project service. Zeabur will detect the
`Dockerfile`. Bind an HTTPS domain after the first successful build.

## 2. Mount persistent storage before importing anything

Mount one Zeabur Volume at `/data`. The container uses:

- `/data/home/.codex` — Codex login and session JSONL files
- `/data/prism` — Prism tokens, SQLite search database, inbox, and metadata
- `/data/home/workspace` — repositories and files operated on by Codex

Mounting a new Volume clears the target directory. Mount it before signing in
to Codex or copying any project and memory data.

## 3. Environment variables

Required:

```text
DASHBOARD_PASSWORD=<at least 20 random characters>
```

Recommended explicit values:

```text
HOME=/data/home
PRISM_DATA_DIR=/data/prism
PRISM_INBOX_DIR=/data/prism/inbox
```

Optional deployment identity (shown under Settings -> System):

```text
PRISM_VERSION=<your release label>
PRISM_COMMIT=<git commit sha, only if Zeabur does not inject one>
PRISM_BUILD_TIME=<ISO-8601 timestamp>
```

The container pins the Codex CLI to the version declared by `CODEX_VERSION` in
the Dockerfile. Upgrade it intentionally and run the repository checks before
deploying instead of pulling an unreviewed `latest` release during every build.

Zeabur supplies `PORT`; do not hard-code it. Never place Codex credentials or
the dashboard password in Git.

## 4. Sign in to Codex from a phone

1. Open the Prism HTTPS URL and sign in with `DASHBOARD_PASSWORD`.
2. Create a new session with type `Codex` and cwd `/data/home/workspace`.
3. The first Codex launch shows an OpenAI sign-in URL. Open it on the phone and
   finish sign-in.
4. Credentials are written under `/data/home/.codex` and survive redeploys.

## 5. Security boundary

- Use a private, unique dashboard password and HTTPS only.
- Anyone holding a valid Prism token can operate the terminal and therefore can
  read every file available to the container, including Codex credentials.
- Prefer an additional access layer (for example a private network or an access
  proxy with MFA) before exposing the dashboard to the public internet.
- Back up `/data` regularly. Do not copy `auth.json` into source control.

## 6. License

The current repository commit is AGPL-3.0 even though older README text may say
MIT. Private personal use is straightforward; if other users access a modified
network deployment, review the AGPL source-offer obligations before sharing it.
