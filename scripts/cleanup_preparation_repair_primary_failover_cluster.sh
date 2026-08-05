#!/usr/bin/env bash
set -euo pipefail

for variable_name in \
  FAILOVER_PRIMARY_CONTAINER \
  FAILOVER_STANDBY_CONTAINER \
  FAILOVER_NETWORK \
  FAILOVER_PRIMARY_VOLUME \
  FAILOVER_STANDBY_VOLUME; do
  if [[ -z "${!variable_name:-}" ]]; then
    echo "missing cleanup variable: $variable_name" >&2
    exit 1
  fi
done

for container_name in "$FAILOVER_PRIMARY_CONTAINER" "$FAILOVER_STANDBY_CONTAINER"; do
  docker rm -f "$container_name" >/dev/null 2>&1 || true
done

docker network rm "$FAILOVER_NETWORK" >/dev/null 2>&1 || true
docker volume rm "$FAILOVER_PRIMARY_VOLUME" >/dev/null 2>&1 || true
docker volume rm "$FAILOVER_STANDBY_VOLUME" >/dev/null 2>&1 || true

printf 'failover_cluster_cleanup=complete\n'
