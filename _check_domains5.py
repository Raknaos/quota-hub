"""Batterie ROUTER : noms simples avec 'router/route' en .com/.net (RDAP Verisign)."""
import json
import urllib.request
import threading

NAMES = [
    "routerapi", "apirouter", "routerhub", "routero", "routr", "routely",
    "routerly", "routehub", "routerone", "routerplus", "routermax",
    "smartrouter", "easierrouter", "myrouter", "gorouter", "routerway",
    "routerpath", "routerlane", "routeon", "routex", "routerq", "routenow",
    "routerx", "routerio", "simplerouter", "routerpro", "routergo",
    "routerclub", "routerio", "routershop", "routefy",
]

def check(name, tld):
    url = f"https://rdap.verisign.com/{tld}/v1/domain/{name}.{tld}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "domain-check/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            if r.status == 200:
                return (name, tld, "PRIS", "")
            return (name, tld, "HTTPS_CODE", r.status)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (name, tld, "LIBRE", "")
        return (name, tld, f"ERR{e.code}", "")
    except Exception:
        return (name, tld, "TIMEOUT", "")

results = []
lock = threading.Lock()
def worker(n, t):
    r = check(n, t)
    with lock:
        results.append(r)

threads = []
for n in NAMES:
    for t in ("com", "net"):
        th = threading.Thread(target=worker, args=(n, t))
        th.start()
        threads.append(th)
for th in threads:
    th.join()

free = sorted([r for r in results if r[2] == "LIBRE"])
print("== LIBRES ==")
for n, t, _, _ in free:
    print(f"{n}.{t}")
taken = sorted([r for r in results if r[2] == "PRIS"])
print("== PRIS ==")
for n, t, _, _ in taken:
    print(f"{n}.{t}")
errs = [r for r in results if r[2] not in ("LIBRE", "PRIS")]
print("== ERR ==", errs[:10])