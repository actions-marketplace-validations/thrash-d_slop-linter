#!/usr/bin/env bash
# pre-commit runs this from the consumer's repo, so the config is found next to
# this script, not in the working directory.
exec vale --config="$(dirname "$0")/../.vale.ini" "$@"
