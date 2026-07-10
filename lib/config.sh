# Shared configuration helpers. Source this file; do not execute it.
#
#   . "$SYSTEM_ROOT/lib/config.sh"
#
# Defines SYSTEM_ROOT (absolute path to the system repo) and helpers for
# reading config values and resolving relative/absolute paths.

# Absolute path to the system repository root (the parent of lib/).
_PWS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEM_ROOT="$(cd "$_PWS_LIB_DIR/.." && pwd)"

# resolve_path <path> <base_dir>
# Print an absolute path. Absolute inputs are returned unchanged; relative
# inputs are resolved against <base_dir>.
resolve_path() {
  local p="$1" base="$2"
  case "$p" in
    /*) printf '%s\n' "$p" ;;
    *)  printf '%s\n' "$base/$p" ;;
  esac
}

# get_config_value <key> <config_file>
# Print the value of KEY=value, ignoring comments and blank lines. Prints
# nothing if the key or file is absent.
get_config_value() {
  local key="$1" file="$2"
  [ -f "$file" ] || return 0
  sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "$file" | tail -n1
}

# module_config_path <name>
# Print the path to a module's account config: the knowledge-repo settings
# home first (<knowledge>/settings/modules/<name>/config), then the legacy
# module-local location. Prints nothing and returns 1 if neither exists.
module_config_path() {
  local name="$1" kb new old
  kb="$(knowledge_path)" || return 1
  new="$kb/settings/modules/$name/config"
  old="$SYSTEM_ROOT/modules/$name/config"
  if [ -f "$new" ]; then
    printf '%s\n' "$new"
  elif [ -f "$old" ]; then
    printf '%s\n' "$old"
  else
    return 1
  fi
}

# knowledge_path
# Print the absolute path to the knowledge base, read from the system config.
# Canonicalizes the path if it already exists. Exits non-zero if unset.
knowledge_path() {
  local cfg="$SYSTEM_ROOT/config" raw abs
  raw="$(get_config_value KNOWLEDGE_PATH "$cfg")"
  if [ -z "$raw" ]; then
    echo "error: KNOWLEDGE_PATH not set in $cfg (run ./init.sh first)" >&2
    return 1
  fi
  abs="$(resolve_path "$raw" "$SYSTEM_ROOT")"
  if [ -d "$abs" ]; then
    (cd "$abs" && pwd)
  else
    printf '%s\n' "$abs"
  fi
}
