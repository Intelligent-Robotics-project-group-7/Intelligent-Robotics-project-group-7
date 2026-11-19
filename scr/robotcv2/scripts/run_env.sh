#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/container_common.sh"
tb4_check_image
terminal_args=()
if [ -t 0 ] && [ -t 1 ]; then
  terminal_args=(-it)
fi
if [ "$#" -eq 0 ]; then
  set -- bash
fi
exec docker run "${tb4_docker_args[@]}" "${terminal_args[@]}" \
  --network none "$TB4_IMAGE" "$@"
