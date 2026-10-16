#!/bin/bash
# cloud-setup-bsc-geth.sh — the Setup script of the `bsc-geth` cloud environment at
# claude.ai/code (README §Cloud sessions). The environment dialog holds a pasted copy;
# this file is the versioned one. It runs as root on a fresh Ubuntu 24.04 VM before Claude
# Code launches, once per environment cache: the filesystem is snapshotted after it and
# reused for about seven days, or until the script or the allowed hosts change. It must
# exit 0 and finish in about five minutes, or the environment is not cached. Whether the
# repository clone is present when it runs is not documented: nothing here depends on it.
#
#   kit      clones this repository (public for this purpose; operator, 2026-10-16) to
#            /opt/blockchain-kit and installs the plugin at user scope on the VM by both
#            routes it has: `claude plugin marketplace add` + `claude plugin install --scope
#            user` when the claude CLI is on the setup script's PATH, and, always, a
#            `directory` marketplace entry plus `enabledPlugins` merged into
#            /root/.claude/settings.json. A cloud session installs no plugin from the
#            repository's own settings. Whether either route loads is read off the
#            session-start context: a `blockchain-kit:` line means the kit loaded
#   go       warms the Go toolchain bsc-geth's go.mod names (go 1.27.1) through
#            proxy.golang.org, so the first `go` command of a session does not download it
#   gopls    the repo's .mcp.json names a bare `gopls`: built into /usr/local/bin, which is
#            on the session's PATH
#   linter   the golangci-lint archive build/ci.go would download, fetched into $CACHE for
#            bsc-geth's build/cloud-session-start.sh to verify against build/checksums.txt
#            and unpack into build/cache/ at each session start; `go install` of the same
#            version is the fallback when the GitHub release host is refused
#   modules  `go mod download` when the clone is at hand, time-capped
#
# Every step is `|| true`: a miss costs the session a download, never its start. The
# versions are bsc-geth's: go.mod `go` and build/checksums.txt `# version:golangci`; the
# session-start hook verifies the archive against checksums.txt, so a stale pin here
# costs one download and nothing else.
set -u
GO_VERSION=1.27.1
GOLANGCI=2.13.2
GOPLS=v0.23.0
CACHE=/root/.cache/bsc-geth
mkdir -p "$CACHE" /usr/local/bin
export GOTOOLCHAIN="go$GO_VERSION"
command -v go >/dev/null || export PATH="/usr/local/go/bin:$PATH"

step() { printf '[cloud-setup] %s\n' "$*"; }

# kit
KIT=/opt/blockchain-kit
step "blockchain-kit -> $KIT"
rm -rf "$KIT"
if GIT_TERMINAL_PROMPT=0 timeout 60 git clone -q --depth 1 https://github.com/mrinaldhillon/blockchain-kit "$KIT"; then
	if command -v claude >/dev/null; then
		step "claude plugin install blockchain-kit@blockchain-kit --scope user"
		timeout 60 claude plugin marketplace add "$KIT" || true
		timeout 60 claude plugin install blockchain-kit@blockchain-kit --scope user || true
	else
		step "no claude on the setup PATH; the settings route alone"
	fi
	step "/root/.claude/settings.json: blockchain-kit as a directory marketplace, enabled"
	mkdir -p /root/.claude
	KIT="$KIT" python3 - <<'PY' || true
import json, os
p = "/root/.claude/settings.json"
try:
    s = json.load(open(p))
except (OSError, ValueError):
    s = {}
s.setdefault("extraKnownMarketplaces", {})["blockchain-kit"] = {
    "source": {"source": "directory", "path": os.environ["KIT"]}}
s.setdefault("enabledPlugins", {})["blockchain-kit@blockchain-kit"] = True
with open(p, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
PY
else
	rm -rf "$KIT"
	step "blockchain-kit clone refused; the session runs without the kit"
fi

# go
step "toolchain go$GO_VERSION"
timeout 120 go version || true

# gopls, linter and modules run side by side: each is a download or a build on its own.
(
	step "gopls $GOPLS -> /usr/local/bin"
	GOBIN=/usr/local/bin timeout 240 go install "golang.org/x/tools/gopls@$GOPLS" || true
) &
(
	arch="$(uname -m)"
	case "$arch" in x86_64) arch=amd64 ;; aarch64) arch=arm64 ;; esac
	archive="golangci-lint-$GOLANGCI-linux-$arch.tar.gz"
	step "golangci-lint $GOLANGCI archive -> $CACHE/$archive"
	if ! curl -fsSL --max-time 120 -o "$CACHE/$archive" \
		"https://github.com/golangci/golangci-lint/releases/download/v$GOLANGCI/$archive"; then
		rm -f "$CACHE/$archive"
		step "archive refused; go install golangci-lint v$GOLANGCI -> /root/go/bin"
		timeout 240 go install "github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v$GOLANGCI" || true
	fi
) &
(
	repo="$(find "$PWD" /root /workspace /home /srv /opt -maxdepth 3 -name go.mod -print0 2>/dev/null |
		xargs -0 -r grep -l '^module github.com/ethereum/go-ethereum$' 2>/dev/null | head -1)"
	if [ -n "$repo" ]; then
		step "go mod download in $(dirname "$repo")"
		(cd "$(dirname "$repo")" && timeout 180 go mod download) || true
	else
		step "no bsc-geth clone in reach; modules download in the session"
	fi
) &
wait

step "done: kit $(git -C "$KIT" rev-parse --short=12 HEAD 2>/dev/null || echo absent) · $(go version 2>/dev/null || echo 'go: absent') · gopls $(/usr/local/bin/gopls version 2>/dev/null | head -1 || echo absent) · cached: $(find "$CACHE" -mindepth 1 -maxdepth 1 -printf '%f ' 2>/dev/null)"
exit 0
