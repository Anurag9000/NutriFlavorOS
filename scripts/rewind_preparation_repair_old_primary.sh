#!/usr/bin/env bash
set -euo pipefail

: "${FAILOVER_POSTGRES_IMAGE:?FAILOVER_POSTGRES_IMAGE is required}"
: "${FAILOVER_NETWORK:?FAILOVER_NETWORK is required}"
: "${FAILOVER_PRIMARY_CONTAINER:?FAILOVER_PRIMARY_CONTAINER is required}"
: "${FAILOVER_STANDBY_CONTAINER:?FAILOVER_STANDBY_CONTAINER is required}"
: "${FAILOVER_PRIMARY_VOLUME:?FAILOVER_PRIMARY_VOLUME is required}"
: "${FAILOVER_REJOIN_CONTAINER:?FAILOVER_REJOIN_CONTAINER is required}"
: "${FAILOVER_REJOIN_PORT:?FAILOVER_REJOIN_PORT is required}"

if docker inspect "$FAILOVER_PRIMARY_CONTAINER" >/dev/null 2>&1; then
  echo "old primary container still exists; rewind authority is denied" >&2
  exit 1
fi

docker inspect "$FAILOVER_STANDBY_CONTAINER" >/dev/null
promoted_recovery="$(
  docker exec "$FAILOVER_STANDBY_CONTAINER" \
    gosu postgres psql -At -U postgres -d nutriflavor_test \
    -c 'SELECT pg_is_in_recovery()'
)"
[[ "$promoted_recovery" == "f" ]]

docker volume inspect "$FAILOVER_PRIMARY_VOLUME" >/dev/null
docker rm -f "$FAILOVER_REJOIN_CONTAINER" >/dev/null 2>&1 || true

# The old primary was stopped with zero grace. Recover it only in single-user
# mode on an isolated network, checkpoint it, and exit before pg_rewind. This
# cleans the target without making the stale primary reachable or writable by
# any application process.
docker run --rm \
  --network none \
  -v "${FAILOVER_PRIMARY_VOLUME}:/var/lib/postgresql/data" \
  --entrypoint bash \
  "$FAILOVER_POSTGRES_IMAGE" -euc '
    chown -R postgres:postgres /var/lib/postgresql/data
    rm -f /var/lib/postgresql/data/postmaster.pid
    printf "CHECKPOINT;\n" | \
      gosu postgres postgres --single \
        -D /var/lib/postgresql/data \
        -c listen_addresses= \
        template1
  '

docker run --rm \
  --network "$FAILOVER_NETWORK" \
  -e PGPASSWORD=postgres \
  -v "${FAILOVER_PRIMARY_VOLUME}:/var/lib/postgresql/data" \
  --entrypoint bash \
  "$FAILOVER_POSTGRES_IMAGE" -euc "
    chown -R postgres:postgres /var/lib/postgresql/data
    gosu postgres pg_rewind \\
      --target-pgdata=/var/lib/postgresql/data \\
      --source-server='host=${FAILOVER_STANDBY_CONTAINER} port=5432 user=postgres dbname=nutriflavor_test sslmode=disable' \\
      --progress
    rm -f \\
      /var/lib/postgresql/data/recovery.signal \\
      /var/lib/postgresql/data/postmaster.pid
    sed -i \\
      -e '/^[[:space:]]*primary_conninfo[[:space:]]*=/d' \\
      -e '/^[[:space:]]*primary_slot_name[[:space:]]*=/d' \\
      /var/lib/postgresql/data/postgresql.auto.conf
    touch /var/lib/postgresql/data/standby.signal
    printf \"%s\\n\" \\
      \"primary_conninfo = 'host=${FAILOVER_STANDBY_CONTAINER} port=5432 user=replicator application_name=rewound-old-primary sslmode=disable'\" \\
      >> /var/lib/postgresql/data/postgresql.auto.conf
    chown postgres:postgres \\
      /var/lib/postgresql/data/standby.signal \\
      /var/lib/postgresql/data/postgresql.auto.conf
  "

docker run -d \
  --name "$FAILOVER_REJOIN_CONTAINER" \
  --network "$FAILOVER_NETWORK" \
  -p "${FAILOVER_REJOIN_PORT}:5432" \
  -v "${FAILOVER_PRIMARY_VOLUME}:/var/lib/postgresql/data" \
  "$FAILOVER_POSTGRES_IMAGE" \
  -c hot_standby=on \
  -c listen_addresses='*' >/dev/null

ready_deadline=$((SECONDS + 90))
until docker exec "$FAILOVER_REJOIN_CONTAINER" \
  pg_isready -U postgres -d nutriflavor_test >/dev/null 2>&1; do
  if (( SECONDS >= ready_deadline )); then
    docker logs "$FAILOVER_REJOIN_CONTAINER" >&2 || true
    echo "rewound standby did not become ready" >&2
    exit 1
  fi
  sleep 1
done

stream_deadline=$((SECONDS + 90))
rejoin_recovery=""
receiver_status=""
source_streaming="0"
while (( SECONDS < stream_deadline )); do
  rejoin_recovery="$(
    docker exec "$FAILOVER_REJOIN_CONTAINER" \
      gosu postgres psql -At -U postgres -d nutriflavor_test \
      -c 'SELECT pg_is_in_recovery()'
  )"
  receiver_status="$(
    docker exec "$FAILOVER_REJOIN_CONTAINER" \
      gosu postgres psql -At -U postgres -d nutriflavor_test \
      -c "SELECT COALESCE(status, '') FROM pg_stat_wal_receiver"
  )"
  source_streaming="$(
    docker exec "$FAILOVER_STANDBY_CONTAINER" \
      gosu postgres psql -At -U postgres -d nutriflavor_test \
      -c "SELECT count(*) FROM pg_stat_replication WHERE state = 'streaming' AND application_name = 'rewound-old-primary'"
  )"
  if [[ "$rejoin_recovery" == "t" && "$receiver_status" == "streaming" && "$source_streaming" == "1" ]]; then
    break
  fi
  sleep 1
done

if [[ "$rejoin_recovery" != "t" || "$receiver_status" != "streaming" || "$source_streaming" != "1" ]]; then
  docker logs "$FAILOVER_REJOIN_CONTAINER" >&2 || true
  docker logs "$FAILOVER_STANDBY_CONTAINER" >&2 || true
  echo "rewound old primary did not join as a streaming standby" >&2
  echo "rejoin_recovery=$rejoin_recovery" >&2
  echo "receiver_status=$receiver_status" >&2
  echo "source_streaming=$source_streaming" >&2
  exit 1
fi

promoted_system_identifier="$(
  docker exec "$FAILOVER_STANDBY_CONTAINER" \
    gosu postgres psql -At -U postgres -d nutriflavor_test \
    -c 'SELECT system_identifier::text FROM pg_control_system()'
)"
rejoin_system_identifier="$(
  docker exec "$FAILOVER_REJOIN_CONTAINER" \
    gosu postgres psql -At -U postgres -d nutriflavor_test \
    -c 'SELECT system_identifier::text FROM pg_control_system()'
)"
[[ -n "$promoted_system_identifier" ]]
[[ "$promoted_system_identifier" == "$rejoin_system_identifier" ]]

printf 'isolated_target_crash_recovery=true\n'
printf 'stale_recovery_settings_normalized=true\n'
printf 'pg_rewind_completed=true\n'
printf 'rejoin_container=%s\n' "$FAILOVER_REJOIN_CONTAINER"
printf 'rejoin_in_recovery=%s\n' "$rejoin_recovery"
printf 'rejoin_receiver_status=%s\n' "$receiver_status"
printf 'promoted_sender_count=%s\n' "$source_streaming"
printf 'shared_system_identifier=true\n'
