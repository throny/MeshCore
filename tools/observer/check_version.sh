#!/usr/bin/env bash
# Succeeds only if FILE contains STRING as a complete NUL-terminated string,
# not merely as a substring of a longer one (v1.18.0-coc must not match
# v1.18.0-coc.2).
#
# Usage: tools/observer/check_version.sh FILE STRING
set -euo pipefail
file="${1:?usage: check_version.sh FILE STRING}"
string="${2:?usage: check_version.sh FILE STRING}"
grep -aqzxF -- "$string" "$file"
