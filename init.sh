#!/usr/bin/env bash
# Set up a new knowledge base for this wiki system.
#
# Usage:
#   ./init.sh [path]
#
#   path   Where to create the knowledge base. Absolute, or relative to the
#          system repo root. Defaults to ../knowledge (a sibling of system/).
#
# Creates the knowledge base directory structure (sources/, wiki/), its config
# and .gitignore, and writes the system `config` pointing at it. When system
# and knowledge sit side by side the cross-references are relative (../system,
# ../knowledge); otherwise they are absolute.
set -euo pipefail

SYSTEM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/config.sh
. "$SYSTEM_ROOT/lib/config.sh"

RAW_KNOWLEDGE="${1:-../knowledge}"
KNOWLEDGE_ABS="$(resolve_path "$RAW_KNOWLEDGE" "$SYSTEM_ROOT")"

echo "Setting up knowledge base"
echo "  system:    $SYSTEM_ROOT"
echo "  knowledge: $KNOWLEDGE_ABS"
echo

# 1. Directory structure.
mkdir -p "$KNOWLEDGE_ABS/sources" "$KNOWLEDGE_ABS/wiki"
KNOWLEDGE_ABS="$(cd "$KNOWLEDGE_ABS" && pwd)"   # canonicalize now it exists
touch "$KNOWLEDGE_ABS/sources/.gitkeep" "$KNOWLEDGE_ABS/wiki/.gitkeep"

# 2. Use relative cross-references when the two repos are siblings, else absolute.
if [ "$(dirname "$SYSTEM_ROOT")" = "$(dirname "$KNOWLEDGE_ABS")" ]; then
  KNOWLEDGE_REF="../$(basename "$KNOWLEDGE_ABS")"
  SYSTEM_REF="../$(basename "$SYSTEM_ROOT")"
else
  KNOWLEDGE_REF="$KNOWLEDGE_ABS"
  SYSTEM_REF="$SYSTEM_ROOT"
fi

# write_if_absent <path> <description> -> returns 0 if it wrote (caller fills it),
# 1 if the file already existed and was left untouched.
write_if_absent() {
  if [ -e "$1" ]; then
    echo "  - $2 already exists, leaving it untouched"
    return 1
  fi
  return 0
}

# 3. Knowledge config.example (committed template) + config (gitignored).
cat > "$KNOWLEDGE_ABS/config.example" <<'EOF'
# Path back to the system repository (the public tooling repo).
#
# May be absolute (e.g. /Users/you/personal-wiki-system/system) or relative to
# this knowledge base's root (e.g. ../system when it sits beside system/).
SYSTEM_PATH=../system
EOF

if write_if_absent "$KNOWLEDGE_ABS/config" "knowledge config"; then
  cat > "$KNOWLEDGE_ABS/config" <<EOF
# Path back to the system repository (the public tooling repo).
SYSTEM_PATH=$SYSTEM_REF
EOF
  echo "  - wrote knowledge config (SYSTEM_PATH=$SYSTEM_REF)"
fi

# 4. Knowledge .gitignore.
cat > "$KNOWLEDGE_ABS/.gitignore" <<'EOF'
# Machine-specific config (use config.example as the template)
/config

# macOS
.DS_Store
._*
EOF

# 5. System config (gitignored) pointing at the knowledge base.
if write_if_absent "$SYSTEM_ROOT/config" "system config"; then
  cat > "$SYSTEM_ROOT/config" <<EOF
# Path to the knowledge base (the private data repo).
KNOWLEDGE_PATH=$KNOWLEDGE_REF
EOF
  echo "  - wrote system config (KNOWLEDGE_PATH=$KNOWLEDGE_REF)"
fi

echo
echo "Done. Knowledge base ready at:"
echo "  $KNOWLEDGE_ABS"
echo "    sources/   put source material here"
echo "    wiki/      Obsidian-style knowledge base"
echo
echo "To version it as a private repository:"
echo "  cd \"$KNOWLEDGE_ABS\" && git init && git add . && git commit -m 'Initial knowledge base'"
