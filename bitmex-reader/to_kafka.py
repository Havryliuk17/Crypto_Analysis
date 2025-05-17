import json, threading, time
import websocket, redis
from kafka import KafkaProducer, errors as kerr

producer = None
rds       = None

def init_clients():
    global producer, rds
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers="kafka:9092",
                value_serializer=lambda v: json.dumps(v).encode())
            break
        except kerr.NoBrokersAvailable:
            print("Kafka not ready – waiting 5 s …")
            time.sleep(5)

    rds = redis.Redis(host="redis", port=6379, db=0)
    while True:
        try:
            rds.ping(); break
        except redis.exceptions.ConnectionError:
            print("Redis not ready – waiting 5 s …")
            time.sleep(5)

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"Connection closed: {close_msg}")

def on_message(ws, message):
    try:
        d = json.loads(message)
    except json.JSONDecodeError:
        return
    if d.get("table") != "trade":
        return

    for t in d["data"]:
        payload = {
            "timestamp": t["timestamp"],
            "symbol":   t["symbol"],
            "side":     t["side"],
            "size":     t["size"],
            "price":    t["price"]
        }
        producer.send("transactions", value=payload)
        rds.set(f"{t['symbol']}_{t['side']}", t["price"])
        print("→", payload)

def on_open(ws):
    sub = {"op": "subscribe",
           "args": ["trade:ETHUSD", "trade:ADAUSD", "trade:DOGEUSD", "trade:SOLUSD", "trade:BTCUSD", "trade: BNBUSD", "trade: XRPUSD" ]}
    ws.send(json.dumps(sub))


def main():
    init_clients()
    websocket_url = "wss://www.bitmex.com/realtime"
    while True:
        ws = websocket.WebSocketApp(websocket_url,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
        ws.on_open = on_open
        ws.run_forever()
        time.sleep(1)


if __name__ == "__main__":
    main()
