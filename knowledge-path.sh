#!/usr/bin/env bash
# Print the absolute path to the configured knowledge base.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/config.sh
. "$DIR/lib/config.sh"

knowledge_path
