"""Vérifie la disponibilité réelle .com/.net via RDAP Verisign (404 = libre).
N'imprime que nom + statut + statut d'état du domaine si enregistré."""
import json
import urllib.request
import threading

NAMES = [
    "apimaster", "apicheap", "apigem", "apimint", "apiprime", "apitop",
    "apiace", "apiboss", "apipower", "apivault", "apibaron", "apiknight",
    "apilord", "apiwise", "apipeak", "apipulse", "apispark", "apibest",
    "apicrown", "apihero", "apidiamond", "apisilver", "apibolt", "apipack",
    "apicore", "apiking", "apigold", "apipure", "apismart", "apifast",
    "apinew", "apipremium", "apipilot", "apigroup", "apihomes", "apicraft",
    "apimarvel", "apipro", "apihub", "apiport", "apirocket", "apivip",
    "apiqueen", "apititan", "apiforce", "apipoint", "apilink", "apikeep",
    "apiguard", "apicentra", "apifirst",
]

def check(name, tld):
    url = f"https://rdap.verisign.com/{tld}/v1/domain/{name}.{tld}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "domain-check/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            if r.status == 200:
                data = json.loads(r.read().decode())
                st = data.get("status", [])
                # chercher la date d'expiration si présente
                exp = ""
                for e in data.get("events", []):
                    if e.get("eventAction") == "expiration":
                        exp = e.get("eventDate", "")[:10]
                return (name, tld, "PRIS", exp, ",".join(st)[:50])
            return (name, tld, "HTTPS_CODE", r.status, "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (name, tld, "LIBRE", "", "")
        return (name, tld, f"ERR{e.code}", "", "")
    except Exception as e:
        return (name, tld, "TIMEOUT", "", "")

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

free = [r for r in results if r[2] == "LIBRE"]
taken = [r for r in results if r[2] == "PRIS"]
print(f"== LIBRES ({len(free)}) ==")
for n, t, *_ in sorted(free):
    print(f"{n}.{t}")
print(f"== PRIS ({len(taken)}) ==")
for n, t, _, exp, st in sorted(taken):
    print(f"{n}.{t} (exp {exp})")
errs = [r for r in results if r[2] not in ("LIBRE", "PRIS")]
print(f"== ERR ({len(errs)}) ==", errs[:8])