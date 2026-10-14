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
#
# The install scope: KIT_SCOPE (user, the default, or project) and, for project,
# KIT_PROJECT, the clone the install belongs to. A caller sets both from --scope and
# --project, then calls resolve_scope. A project-scope install is recorded in the
# home's installed_plugins.json with scope "project" and the clone as projectPath;
# `claude plugin install|update --scope project` acts on the clone it is run from.

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

KIT_SCOPE=user
KIT_PROJECT=""
LOG=""
FAILED=0

# resolve_scope <tool-name> — validate KIT_SCOPE; for project, resolve KIT_PROJECT
# (default: the git top level of the cwd) to a physical path. Exits 2 on a usage error.
resolve_scope() {
	local named="$KIT_PROJECT"
	case "$KIT_SCOPE" in
	user)
		if [[ -n "$named" ]]; then
			echo "$1: --project applies to --scope project only (see --help)" >&2
			exit 2
		fi
		;;
	project)
		[[ -n "$named" ]] || named="$(git rev-parse --show-toplevel 2>/dev/null || true)"
		if [[ -z "$named" ]]; then
			echo "$1: --scope project needs --project DIR, or a cwd inside the clone's git work tree (see --help)" >&2
			exit 2
		fi
		if ! KIT_PROJECT="$(cd "$named" 2>/dev/null && pwd -P)"; then
			echo "$1: --project $named is not a directory" >&2
			exit 2
		fi
		;;
	*)
		echo "$1: --scope must be user or project, not '$KIT_SCOPE' (see --help)" >&2
		exit 2
		;;
	esac
}

# scope_label — `user-scope`, or `project-scope (<clone>)`, for a row.
scope_label() {
	if [[ "$KIT_SCOPE" == project ]]; then
		printf 'project-scope (%s)' "$KIT_PROJECT"
	else
		printf 'user-scope'
	fi
}

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

# claude_scoped <args...> — claude_in_home, run from KIT_PROJECT when the scope is
# project: `plugin install|update --scope project` acts on the clone it runs in.
claude_scoped() {
	if [[ "$KIT_SCOPE" == project ]]; then
		(cd "$KIT_PROJECT" && claude_in_home "$@")
	else
		claude_in_home "$@"
	fi
}

# json_get <file> <python-expr> [arg...] — prints the value, empty when absent. The
# expression sees `d` (the parsed file), `a` (the args, a list of str) and `os`; pass
# a value as an arg, never spliced into the expression.
json_get() {
	[[ -f "$1" ]] || return 0
	python3 - "$@" <<'PY' 2>/dev/null || true
import json, os, sys
try:
    d = json.load(open(sys.argv[1]))
    v = eval(sys.argv[2], {"d": d, "a": sys.argv[3:], "os": os})
except Exception:
    v = None
print("" if v is None else v)
PY
}

has_marketplace() {
	[[ -n "$(json_get "$CONFIG_HOME/plugins/known_marketplaces.json" "'yes' if a[0] in d else None" "$KIT_NAME")" ]]
}

# installed_field <version|installPath> [scope] [project-root] — the field of the
# install of that scope (default user), empty when there is none. A project-scope
# install matches only when realpath(projectPath) == realpath(project-root).
installed_field() {
	json_get "$CONFIG_HOME/plugins/installed_plugins.json" \
		"next((e.get(a[0]) for e in d.get('plugins', {}).get(a[1], []) if e.get('scope') == a[2] and (a[2] != 'project' or (a[3] and e.get('projectPath') and os.path.realpath(e['projectPath']) == os.path.realpath(a[3])))), None)" \
		"$1" "$KIT_PLUGIN" "${2:-user}" "${3:-}"
}

# Point KIT_LINK at the installed plugin of KIT_SCOPE, else at the kit that is
# running this script (a clone used without the plugin).
repoint_link() { # repoint_link <running-kit-root>
	local target
	target="$(installed_field installPath "$KIT_SCOPE" "$KIT_PROJECT")"
	[[ -n "$target" && -d "$target" ]] || target="$1"
	mkdir -p "$KIT_STATE"
	# A real directory there (a kit cloned to bootstrap setup) would take the link
	# inside it, and the PATH would keep running the clone.
	if [[ -d "$KIT_LINK" && ! -L "$KIT_LINK" ]]; then
		fail_row "$(pad "stable link")" "$KIT_LINK is a directory, not a link: move it aside (mv $KIT_LINK $KIT_LINK.bootstrap) and re-run"
		return 0
	fi
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
