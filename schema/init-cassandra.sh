#!/usr/bin/env bash
set -e

echo "Waiting for Cassandra ..."
until cqlsh cassandra -e "DESCRIBE KEYSPACES" >/dev/null 2>&1; do
  sleep 5
done

echo "Applying schema ..."
cqlsh cassandra -f /schema/init_cassandra.cql
echo "✅  Cassandra schema ready."
