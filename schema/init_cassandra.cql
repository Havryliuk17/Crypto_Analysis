CREATE KEYSPACE IF NOT EXISTS crypto_data
WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE crypto_data;

CREATE TABLE IF NOT EXISTS minute_aggregates_by_symbol (
symbol       text,
window_start timestamp,
num_trades   int,
total_volume int,
PRIMARY KEY ((symbol), window_start)
);

CREATE TABLE IF NOT EXISTS hourly_aggregates_by_symbol (
symbol       text,
window_start timestamp,
num_trades   int,
total_volume int,
PRIMARY KEY ((symbol), window_start)
);

CREATE TABLE IF NOT EXISTS hourly_volume_ranking (
window_start timestamp,
total_volume bigint,
symbol       text,
num_trades   bigint,
PRIMARY KEY ((window_start), total_volume, symbol)
) WITH CLUSTERING ORDER BY (total_volume DESC, symbol ASC);