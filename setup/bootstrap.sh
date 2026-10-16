#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

exec /usr/bin/python3 "$SCRIPT_DIR/bootstrap.py" --repo "$REPO_DIR" "$@"
