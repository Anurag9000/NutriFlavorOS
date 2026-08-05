#!/usr/bin/env bash
set -euo pipefail

: "${FAILOVER_NETWORK:?FAILOVER_NETWORK is required}"
: "${FAILOVER_PRIMARY_CONTAINER:?FAILOVER_PRIMARY_CONTAINER is required}"
: "${FAILOVER_STANDBY_CONTAINER:?FAILOVER_STANDBY_CONTAINER is required}"
: "${FAILOVER_PRIMARY_VOLUME:?FAILOVER_PRIMARY_VOLUME is required}"
: "${FAILOVER_STANDBY_VOLUME:?FAILOVER_STANDBY_VOLUME is required}"
: "${FAILOVER_PRIMARY_PORT:?FAILOVER_PRIMARY_PORT is required}"
: "${FAILOVER_STANDBY_PORT:?FAILOVER_STANDBY_PORT is required}"

POSTGRES_IMAGE="${FAILOVER_POSTGRES_IMAGE:-postgres:16}"

wait_for_container() {
  local container_name="$1"
  local deadline=$((SECONDS + 90))
  until docker exec "$container_name" pg_isready -U postgres -d nutriflavor_test >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      docker logs "$container_name" >&2 || true
      echo "PostgreSQL container did not become ready: $container_name" >&2
      return 1
    fi
    sleep 1
  done
}

wait_for_streaming_replication() {
  local deadline=$((SECONDS + 90))
  local primary_streaming_count="0"
  local standby_receiver_status=""

  while (( SECONDS < deadline )); do
    primary_streaming_count="$(
      docker exec "$FAILOVER_PRIMARY_CONTAINER" \
        gosu postgres psql -At -U postgres -d nutriflavor_test \
        -c "SELECT count(*) FROM pg_stat_replication WHERE state = 'streaming'"
    )"
    standby_receiver_status="$(
      docker exec "$FAILOVER_STANDBY_CONTAINER" \
        gosu postgres psql -At -U postgres -d nutriflavor_test \
        -c "SELECT COALESCE(status, '') FROM pg_stat_wal_receiver"
    )"
    if [[ "$primary_streaming_count" == "1" && "$standby_receiver_status" == "streaming" ]]; then
      printf 'primary_streaming_replica_count=%s\n' "$primary_streaming_count"
      printf 'standby_wal_receiver_status=%s\n' "$standby_receiver_status"
      return 0
    fi
    sleep 1
  done

  docker logs "$FAILOVER_PRIMARY_CONTAINER" >&2 || true
  docker logs "$FAILOVER_STANDBY_CONTAINER" >&2 || true
  echo "physical standby did not enter streaming state" >&2
  echo "primary_streaming_count=$primary_streaming_count" >&2
  echo "standby_receiver_status=$standby_receiver_status" >&2
  return 1
}

for container_name in "$FAILOVER_PRIMARY_CONTAINER" "$FAILOVER_STANDBY_CONTAINER"; do
  docker rm -f "$container_name" >/dev/null 2>&1 || true
done
docker network rm "$FAILOVER_NETWORK" >/dev/null 2>&1 || true
docker volume rm "$FAILOVER_PRIMARY_VOLUME" >/dev/null 2>&1 || true
docker volume rm "$FAILOVER_STANDBY_VOLUME" >/dev/null 2>&1 || true

docker network create "$FAILOVER_NETWORK" >/dev/null
docker volume create "$FAILOVER_PRIMARY_VOLUME" >/dev/null
docker volume create "$FAILOVER_STANDBY_VOLUME" >/dev/null

docker run -d \
  --name "$FAILOVER_PRIMARY_CONTAINER" \
  --network "$FAILOVER_NETWORK" \
  -p "${FAILOVER_PRIMARY_PORT}:5432" \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=nutriflavor_test \
  -v "${FAILOVER_PRIMARY_VOLUME}:/var/lib/postgresql/data" \
  "$POSTGRES_IMAGE" \
  -c wal_level=replica \
  -c wal_log_hints=on \
  -c max_wal_senders=10 \
  -c max_replication_slots=10 \
  -c wal_keep_size=256MB \
  -c hot_standby=on \
  -c synchronous_commit=on \
  -c listen_addresses='*' >/dev/null

wait_for_container "$FAILOVER_PRIMARY_CONTAINER"

docker exec "$FAILOVER_PRIMARY_CONTAINER" bash -euc '
  printf "%s\n" "host replication replicator samenet trust" >> "$PGDATA/pg_hba.conf"
  gosu postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
    -c "CREATE ROLE replicator WITH REPLICATION LOGIN"
  gosu postgres pg_ctl reload -D "$PGDATA"
'

docker run --rm \
  --network "$FAILOVER_NETWORK" \
  -v "${FAILOVER_STANDBY_VOLUME}:/var/lib/postgresql/data" \
  --entrypoint bash \
  "$POSTGRES_IMAGE" -euc "
    rm -rf /var/lib/postgresql/data/*
    chown -R postgres:postgres /var/lib/postgresql/data
    exec gosu postgres pg_basebackup \
      -h '${FAILOVER_PRIMARY_CONTAINER}' \
      -U replicator \
      -D /var/lib/postgresql/data \
      -Fp -Xs -P -R
  "

docker run -d \
  --name "$FAILOVER_STANDBY_CONTAINER" \
  --network "$FAILOVER_NETWORK" \
  -p "${FAILOVER_STANDBY_PORT}:5432" \
  -v "${FAILOVER_STANDBY_VOLUME}:/var/lib/postgresql/data" \
  "$POSTGRES_IMAGE" \
  -c hot_standby=on \
  -c listen_addresses='*' >/dev/null

wait_for_container "$FAILOVER_STANDBY_CONTAINER"
wait_for_streaming_replication

primary_recovery="$(
  docker exec "$FAILOVER_PRIMARY_CONTAINER" \
    gosu postgres psql -At -U postgres -d nutriflavor_test \
    -c 'SELECT pg_is_in_recovery()'
)"
standby_recovery="$(
  docker exec "$FAILOVER_STANDBY_CONTAINER" \
    gosu postgres psql -At -U postgres -d nutriflavor_test \
    -c 'SELECT pg_is_in_recovery()'
)"
primary_system_identifier="$(
  docker exec "$FAILOVER_PRIMARY_CONTAINER" \
    gosu postgres psql -At -U postgres -d nutriflavor_test \
    -c 'SELECT system_identifier::text FROM pg_control_system()'
)"
standby_system_identifier="$(
  docker exec "$FAILOVER_STANDBY_CONTAINER" \
    gosu postgres psql -At -U postgres -d nutriflavor_test \
    -c 'SELECT system_identifier::text FROM pg_control_system()'
)"
wal_log_hints="$(
  docker exec "$FAILOVER_PRIMARY_CONTAINER" \
    gosu postgres psql -At -U postgres -d nutriflavor_test \
    -c 'SHOW wal_log_hints'
)"

[[ "$primary_recovery" == "f" ]]
[[ "$standby_recovery" == "t" ]]
[[ -n "$primary_system_identifier" ]]
[[ "$primary_system_identifier" == "$standby_system_identifier" ]]
[[ "$wal_log_hints" == "on" ]]

printf 'primary_container=%s\n' "$FAILOVER_PRIMARY_CONTAINER"
printf 'standby_container=%s\n' "$FAILOVER_STANDBY_CONTAINER"
printf 'primary_system_identifier=%s\n' "$primary_system_identifier"
printf 'standby_in_recovery=%s\n' "$standby_recovery"
printf 'wal_log_hints=%s\n' "$wal_log_hints"
