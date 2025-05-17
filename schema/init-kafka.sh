#!/usr/bin/env bash
set -e

echo "Waiting for Kafka broker ..."
until /opt/bitnami/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list >/dev/null 2>&1; do
  sleep 5
done

echo "Creating 'transactions' topic ..."
/opt/bitnami/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create --if-not-exists \
  --topic transactions \
  --replication-factor 1 \
  --partitions 3

echo "✅  Kafka topic ready."
