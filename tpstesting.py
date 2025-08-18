from locust import HttpUser, task, constant, events
import time
import gevent

# === GLOBAL STATE ===
RAW_TXS = []
total_sent = 0
MAX_TXS = 10000
start_time = None
stop_test = False

class BesuRawTxUser(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        global RAW_TXS
        if not RAW_TXS:
            with open("raw_tx_pool.txt", "r") as f:
                RAW_TXS = [line.strip() for line in f.readlines()]
            print(f"Loaded {len(RAW_TXS)} raw transactions.")

    @task
    def send_raw_transaction(self):
        global total_sent, start_time, stop_test

        if stop_test or total_sent >= MAX_TXS:
            self.environment.runner.quit()
            return

        raw_tx = RAW_TXS[total_sent % len(RAW_TXS)]  # cycle if fewer than 10k
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_sendRawTransaction",
            "params": [raw_tx],
            "id": total_sent
        }

        with self.client.post("/", json=payload, catch_response=True) as response:
            if response.status_code == 200 and 'result' in response.json():
                if total_sent == 0:
                    start_time = time.time()
                total_sent += 1
                response.success()
            else:
                response.failure(f"Error: {response.text}")

        if total_sent >= MAX_TXS:
            stop_test = True
            gevent.spawn_later(2, self.environment.runner.quit)

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    global start_time, total_sent
    if start_time:
        elapsed = time.time() - start_time
        tps = total_sent / elapsed
        print(f"\n🎯 Total TXs Sent: {total_sent}")
        print(f"⏱️ Time Elapsed: {elapsed:.2f}s")
        print(f"📈 TPS: {tps:.2f}")
