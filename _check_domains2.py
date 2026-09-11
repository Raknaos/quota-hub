"""2e batterie : noms plus conceptuels en .com/.net via RDAP Verisign (404 = libre)."""
import json
import urllib.request
import threading

NAMES = [
    "apione", "apiroute", "apipath", "apiciel", "apiprism", "apisage",
    "apivista", "apilume", "apiforge", "apiecho", "apiroot", "apibloom",
    "apifort", "apitrail", "apiorbit", "apiarc", "apibeam", "apiwave",
    "apitide", "apistream", "apiplume", "apilux", "apitempo", "apirhythm",
    "apisky", "apisolar", "apimar", "apipen", "apilane", "apipeakpro",
    "apicy", "apivet", "apivox", "apique", "apisoul", "apihalo",
    "apispire", "apicoast", "apibreeze", "apiflow", "apiqueen2",
    "apilion", "apivida", "apyra", "apyllo",
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
taken = sorted([r for r in results if r[2] == "PRIS"])
print("== LIBRES ==")
for n, t, _, _ in free:
    print(f"{n}.{t}")
print("== PRIS ==")
for n, t, _, exp in taken:
    print(f"{n}.{t} (exp {exp})")
errs = [r for r in results if r[2] not in ("LIBRE", "PRIS")]
print("== ERR ==", errs[:6])