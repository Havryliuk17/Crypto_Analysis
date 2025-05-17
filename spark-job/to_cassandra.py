from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StructType, StringType, IntegerType, FloatType

spark = (
    SparkSession.builder
        .appName("Kafka→Spark→Cassandra crypto aggregates")
        .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

trade_schema = (
    StructType()
        .add("timestamp", StringType())
        .add("symbol",    StringType())
        .add("side",      StringType())
        .add("size",      IntegerType())
        .add("price",     FloatType())
)

kafka_source = (
    spark.readStream
         .format("kafka")
         .option("kafka.bootstrap.servers", "kafka:9092")
         .option("subscribe", "transactions")
         .option("startingOffsets", "latest")
         .load()
)

trades = (
    kafka_source
        .select(F.from_json(F.col("value").cast("string"), trade_schema).alias("d"))
        .select(
            F.to_timestamp("d.timestamp").alias("ts"),
            F.col("d.symbol").alias("symbol"),
            F.col("d.size").alias("size")
        )
        .where("ts IS NOT NULL AND symbol IS NOT NULL AND size IS NOT NULL")
)

minute_agg = (
    trades.withWatermark("ts", "1 minute")
          .groupBy("symbol", F.window("ts", "1 minute"))
          .agg(
              F.count("*").alias("num_trades_long"),
              F.sum("size").alias("total_volume_long")
          )
          .select(
              F.col("symbol"),
              F.col("window.start").alias("window_start"),
              "num_trades_long",
              "total_volume_long"
          )
)

hour_agg = (
    trades.withWatermark("ts", "1 hour")
          .groupBy("symbol", F.window("ts", "1 hour"))
          .agg(
              F.count("*").alias("num_trades_long"),
              F.sum("size").alias("total_volume_long")
          )
          .select(
              F.col("symbol"),
              F.col("window.start").alias("window_start"),
              "num_trades_long",
              "total_volume_long"
          )
)

def to_cassandra(df, table):
    (df.write
       .format("org.apache.spark.sql.cassandra")
       .mode("append")
       .options(keyspace="crypto_data", table=table)
       .save())

def minute_sink(df, _):
    (df
     .withColumnRenamed("total_volume_long", "total_volume_minute")
     .withColumnRenamed("num_trades_long",   "num_trades")
     .show(truncate=False))


    cast_df = (
        df.select(
            "symbol",
            "window_start",
            F.col("num_trades_long").cast("int").alias("num_trades"),
            F.col("total_volume_long").cast("int").alias("total_volume")
        )
    )
    to_cassandra(cast_df, "minute_aggregates_by_symbol")

minute_query = (
    minute_agg.writeStream
              .foreachBatch(minute_sink)
              .outputMode("update")
              .start()
)

def hour_sink(df, _):
    (df
     .withColumnRenamed("total_volume_long", "total_volume_hour")
     .withColumnRenamed("num_trades_long",   "num_trades")
     .show(truncate=False))

    to_cassandra(
        df.select(
            "symbol",
            "window_start",
            F.col("num_trades_long").cast("int").alias("num_trades"),
            F.col("total_volume_long").cast("int").alias("total_volume")
        ),
        "hourly_aggregates_by_symbol"
    )

    to_cassandra(
        df.select(
            "window_start",
            F.col("total_volume_long").alias("total_volume"),
            "symbol",
            F.col("num_trades_long").alias("num_trades")
        ),
        "hourly_volume_ranking"
    )

hour_query = (
    hour_agg.writeStream
             .foreachBatch(hour_sink)
             .outputMode("update")
             .start()
)

spark.streams.awaitAnyTermination()
