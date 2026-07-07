"""Hit demo-app with realistic traffic so metrics look alive.

Loops forever: random sleep 0.05-0.3s, GET /products (70%), POST /checkout (30%),
prints a status line every 100 requests. Stop with Ctrl+C.
"""
import random
import time

import httpx

BASE_URL = "http://localhost:8001"

def main():
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)
    count = 0
    errors = 0

    while True:
        try:
            if random.random() < 0.7:
                resp = client.get("/products")
            else:
                resp = client.post("/checkout")
            if resp.status_code >= 400:
                errors += 1
        except httpx.HTTPError:
            errors += 1

        count += 1
        if count % 100 == 0:
            print(f"requests={count} errors={errors}")

        time.sleep(random.uniform(0.05, 0.3))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
