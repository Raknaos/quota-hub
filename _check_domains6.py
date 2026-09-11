"""Batterie .cheap via RDAP Donuts (404 = libre)."""
import json
import urllib.request
import threading

NAMES = [
    "api", "ai", "model", "models", "llm", "token", "tokens", "router",
    "openapi", "smart", "simple", "easy", "best", "top", "go", "dev",
    "code", "chat", "ia", "unique", "uapi", "theapi", "oneapi", "smartapi",
    "easyapi", "quick", "quickapi", "super", "mega", "ultra", "apihero",
    "aiapi", "llmapi", "modelapi", "routerapi", "key", "keys", "usage",
    "prompt", "prompts", "conso", "rate", "prices", "price", "deal",
]

def check(name):
    url = f"https://rdap.donuts.co/domain/{name}.cheap"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "domain-check/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 200:
                return (name, "PRIS", "")
            return (name, "HTTPS_CODE", r.status)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (name, "LIBRE", "")
        return (name, f"ERR{e.code}", "")
    except Exception:
        return (name, "TIMEOUT", "")

results = []
lock = threading.Lock()
def worker(n):
    r = check(n)
    with lock:
        results.append(r)

threads = []
for n in NAMES:
    th = threading.Thread(target=worker, args=(n,))
    th.start()
    threads.append(th)
for th in threads:
    th.join()

free = sorted([r for r in results if r[1] == "LIBRE"])
print("== LIBRES ==")
for n, _, _ in free:
    print(f"{n}.cheap")
errs = [r for r in results if r[1] not in ("LIBRE", "PRIS")]
print("== ERR ==", errs[:10])