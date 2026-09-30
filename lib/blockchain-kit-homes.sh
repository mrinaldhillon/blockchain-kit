# shellcheck shell=bash
# blockchain-kit-homes.sh — sourced by blockchain-kit-setup and blockchain-kit-update;
# not executable.
#
# The Claude Code config home, and the CLI that owns it. A plugin and a marketplace
# are recorded per home:
#   $CLAUDE_CONFIG_DIR when it is set, else ~/.claude, driven by the `claude` on PATH
#
# The default home runs with CLAUDE_CONFIG_DIR UNSET, never set to ~/.claude:
# setting it moves the global config from ~/.claude.json to ~/.claude/.claude.json,
# which is a different MCP server list.

KIT_NAME=blockchain-kit
KIT_PLUGIN="blockchain-kit@blockchain-kit"
# shellcheck disable=SC2034  # read by blockchain-kit-setup
KIT_MARKETPLACE_SOURCE="${BLOCKCHAIN_KIT_MARKETPLACE_SOURCE:-mrinaldhillon/blockchain-kit}"
KIT_STATE="${XDG_DATA_HOME:-$HOME/.local/share}/blockchain-kit"
# Stable path to the installed kit, for a shell profile's PATH; re-pointed at each
# install so it survives a version bump (the plugin cache path carries the version).
KIT_LINK="$KIT_STATE/kit"

if [[ -n "${CLAUDE_CONFIG_DIR:-}" ]]; then
	CONFIG_HOME="${CLAUDE_CONFIG_DIR%/}"
	CONFIG_HOME_EXPLICIT=1
else
	CONFIG_HOME="$HOME/.claude"
	CONFIG_HOME_EXPLICIT=0
fi

LOG=""
FAILED=0

open_log() { # open_log <tool-name>
	LOG="$(mktemp -t "$1.XXXXXX")"
}

say() { printf '%s\n' "$*" | tee -a "$LOG"; }
pad() { printf '%-22s' "$1"; } # a row label, column-aligned
note() { printf '%s\n' "$*" >>"$LOG"; }
fail_row() { # fail_row <label> <output>
	FAILED=1
	say "  FAIL   $1"
	printf '%s\n' "$2" | sed 's/^/         /' | tee -a "$LOG"
}

# claude_in_home <args...> — the CLI, with the config home selected.
claude_in_home() {
	if [[ "$CONFIG_HOME_EXPLICIT" == 1 ]]; then
		CLAUDE_CONFIG_DIR="$CONFIG_HOME" claude "$@"
	else
		env -u CLAUDE_CONFIG_DIR claude "$@"
	fi
}

# json_get <file> <python-expr over `d`> — prints the value, empty when absent.
json_get() {
	[[ -f "$1" ]] || return 0
	python3 - "$1" "$2" <<'PY' 2>/dev/null || true
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    v = eval(sys.argv[2], {"d": d})
except Exception:
    v = None
print("" if v is None else v)
PY
}

has_marketplace() {
	[[ -n "$(json_get "$CONFIG_HOME/plugins/known_marketplaces.json" "'yes' if '$KIT_NAME' in d else None")" ]]
}

# The user-scope install's version / installPath, empty when not installed.
installed_field() { # installed_field <version|installPath>
	json_get "$CONFIG_HOME/plugins/installed_plugins.json" \
		"next((e.get('$1') for e in d.get('plugins', {}).get('$KIT_PLUGIN', []) if e.get('scope') == 'user'), None)"
}

# Point KIT_LINK at the installed plugin, else at the kit that is running this
# script (a clone used without the plugin).
repoint_link() { # repoint_link <running-kit-root>
	local target
	target="$(installed_field installPath)"
	[[ -n "$target" && -d "$target" ]] || target="$1"
	mkdir -p "$KIT_STATE"
	ln -sfn "$target" "$KIT_LINK"
	say "  ok     $(pad "stable link") $KIT_LINK -> $target"
}

finish() { # finish <tool-name>
	if [[ "$FAILED" == 1 ]]; then
		echo "$1: FAILED — full log: $LOG"
		exit 1
	fi
	echo "log: $LOG"
	exit 0
}
