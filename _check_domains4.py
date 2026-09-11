"""4e batterie : noms anglais .com/.net non encore testés (RDAP Verisign)."""
import json
import urllib.request
import threading

NAMES = [
    "apigear", "apimuse", "apimelody", "apipiano", "apisummit", "apifrontier",
    "apibeach", "apidune", "apishore", "apioasis", "apidelta", "apicanyon",
    "apivalley", "apicrest", "apidriver", "apithrottle", "apithrift",
    "apifair", "apidash", "apisprint", "apiventure", "apimotion",
    "apihorizon", "apilagoon", "apirealm", "apistory", "apipoet",
    "apilight", "apicurve", "apisphere", "apissimo", "apiwave2",
    "apiway", "apimap", "apiquest", "apislate", "apiswift",
    "apicrest", "apibase", "apinode", "apikingom", "apiqueendom",
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
errs = [r for r in results if r[2] not in ("LIBRE", "PRIS")]
print("== ERR ==", errs[:10])