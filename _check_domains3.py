"""3e batterie : noms ANGLAIS forts en .com/.net via RDAP Verisign (404 = libre)."""
import json
import urllib.request
import threading

NAMES = [
    "apisharp", "apishield", "apihaven", "apibeacon", "apitrove", "apismith",
    "apifalcon", "apihawk", "apibear", "apiwolf", "apibull", "apistorm",
    "apiflame", "apispeed", "apiturbo", "apiglide", "apiglow", "apishine",
    "apibay", "apigrove", "apiview", "apimist", "apilantern", "apitorch",
    "apivalue", "apisail", "apinest", "apiseed", "apiridge", "apipine",
    "apipod", "apiease", "apitrust", "apiwave", "apibeam", "apistream",
    "apiroute", "apibranch", "apifridge", "apicook", "apify", "apiquiet",
    "apimercy", "apimuth", "apifuse", "apibolt", "apicore", "apiblaze",
]

def check(name, tld):
    url = f"https://rdap.verisign.com/{tld}/v1/domain/{name}.{tld}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "domain-check/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            if r.status == 200:
                data = json.loads(r.read().decode())
                exp = ""
                for e in data.get("events", []):
                    if e.get("eventAction") == "expiration":
                        exp = e.get("eventDate", "")[:10]
                return (name, tld, "PRIS", exp)
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
print("== PRIS (dispo nulle part) ==")
for n in sorted(set(x[0] for x in taken)):
    print(n)
errs = [r for r in results if r[2] not in ("LIBRE", "PRIS")]
print("== ERR ==", errs[:10])