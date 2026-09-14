#!/usr/bin/env python3
"""
Quota.Hub — Worker marché 30 j (partagé).

Calcule pour chaque modèle du pool :
  - le PRIX MOYEN 30 J PONDÉRÉ PAR LE TEMPS (pas le prix instantané, qui piège)
  - la FIABILITÉ (pire heure sur 24 h, taux de succès 24 h, volume)
  - le COÛT EFFECTIF 30 j cache-aware (75 % entrée / 25 % sortie)
  - le TOP 5 fournisseurs robustes

Expose GET /api/prices sur 127.0.0.1:8891 (loopback) — consommé par la
passerelle Quota.Hub sur la même machine. Ne sort JAMAIS de la machine :
les noms de chaînes amont ne doivent jamais atteindre un client.

Aucune donnée simulée : si la place de marché ne répond pas, on sert le
dernier instantané réel et on le marque `stale: true`.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import statistics as st
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("QH_DB", os.path.join(DIR, "hub.db"))
PORT = int(os.environ.get("QH_MARKET_PORT", "8891"))
INTERVAL = int(os.environ.get("QH_MARKET_INTERVAL", "120"))     # s
MKT_URL = os.environ.get("QH_MKT_URL", "https://a6api.com/api/marketplace/public/channels/search")
WINDOW_D = 30
WORKERS = int(os.environ.get("QH_MARKET_WORKERS", "6"))
FLOOR_WORST = 90.0      # pire heure minimale
MIN_SAMPLES_24H = 200   # volume minimal sur 24 h (mêmes seuils que le rapport 30 j)
# Un bucket horaire ne pèse sur la fiabilité que s'il porte assez de trafic.
# Sans ce garde-fou, le bucket EN COURS (quelques dizaines d'échantillons sur
# des dizaines de milliers) fait chuter la "pire heure" et écarte le meilleur
# canal à tort (constaté : tokentrans ch4134, 55/49 572 échantillons → 60 %).
BUCKET_MIN_SHARE = 0.02  # part minimale du volume 24 h pour compter
TOP_N = 5

MODELS = [m.strip() for m in os.environ.get(
    "QH_MARKET_MODELS",
    # union des pools : passerelle Quota.Hub (8 + gemini) et routeur a6 (4)
    "qwen3.8-flash,glm-5.3-flash,grok-4.6,deepseek-v4-pro,deepseek-v4-flash,"
    "deepseek-v4.1-flash,deepseek-v4-flash-vision,deepseek-v4-vision,"
    "deepseek-v4-flash-vision-exp,gemini-3.8-flash"
).split(",") if m.strip()]

# ── SONDEUR UNIQUE DE LA FLOTTE (10-09) ─────────────────────────────────────
# Un SEUL test réel par modèle, toutes les 20 min, fait ICI (VPS .66), publié
# dans /api/prices → tous les routeurs de la flotte le réutilisent (pull SSH).
# Résultat : le volume de tests ne dépend plus du nombre de nœuds ni du nombre
# d'utilisateurs — un test sert tout le monde, et on garde le même canal pour
# ne pas casser le cache de prompts (voir pin/hystérésis côté routeur).
PROBE_INTERVAL = int(os.environ.get("QH_PROBE_INTERVAL", "1800"))   # s (30 min)   # s (20 min)
PROBE_MODELS = [m.strip() for m in os.environ.get(
    "QH_PROBE_MODELS",
    "qwen3.8-flash,glm-5.3-flash,grok-4.6,deepseek-v4.1-flash,deepseek-v4-flash-vision-exp"
).split(",") if m.strip()]
API_BASE = os.environ.get("QH_API_BASE", "https://api.a6api.com")
KEY_FILE = os.environ.get("A6API_KEY_PATH", os.path.join(DIR, "key.json"))
PROBE_TIMEOUT = int(os.environ.get("QH_PROBE_TIMEOUT", "20"))

PROBES: dict = {"generated_at": 0, "passes": 0, "models": {}, "last_error": None}


def _load_key():
    """Clé amont, lue localement. Jamais journalisée, jamais renvoyée."""
    try:
        k = (json.load(open(KEY_FILE, encoding="utf-8")) or {}).get("api_key", "")
        if isinstance(k, str) and k.startswith("sk-"):
            return k
    except Exception:  # noqa: BLE001
        pass
    k = os.environ.get("A6API_KEY", "")
    return k if isinstance(k, str) and k.startswith("sk-") else None

COMP = [("输入价", "in"), ("输出价", "out"), ("缓存读价", "cache_r"),
        ("缓存写价", "cache_w"), ("按次价", "per_req")]
NUM = re.compile(r"\$([0-9]*\.?[0-9]+)")

LOCK = threading.Lock()
SNAP: dict = {"generated_at": 0, "passes": 0, "models": {}, "last_error": None,
              "last_pass_s": 0.0, "stale": True}

LOG_LOCK = threading.Lock()


def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S") + " " + str(msg)
    with LOG_LOCK:
        print(line, flush=True)


# ─────────────────────────── calculs (méthode validée) ─────────────────────
def parse_summary(s: str | None) -> dict:
    """'输入价/1M $old -> $new; 输出价/1M $old -> $new' -> {'in': (old, new)}"""
    out = {}
    if not s:
        return out
    for part in str(s).split(";"):
        part = part.strip()
        for label, key in COMP:
            if label in part:
                v = NUM.findall(part)
                if v:
                    old = float(v[0])
                    new = float(v[1]) if len(v) > 1 else None
                    out[key] = (old, new)
                break
    return out


def avg30(cur_micros, chg, age_days: float) -> tuple[float, float, float]:
    """Prix moyen $/M sur 30 j pondéré par le temps (segment précédent + courant)."""
    cur = (cur_micros or 0) / 1e6
    if not chg:
        return cur, cur, 0.0
    old, new = chg
    if new is not None and cur > 0 and abs(new - cur) > max(1e-9, 0.02 * max(new, cur)):
        new = cur                      # résumé incohérent -> le prix courant fait foi
    if new is None:
        new = cur
    age = max(0.0, min(float(WINDOW_D), age_days))
    return (old * (WINDOW_D - age) + new * age) / WINDOW_D, old, age


def reliability(L: dict) -> dict:
    sr24 = (L.get("success_rate_24h") or 0) / 100.0
    b24 = L.get("b24") or []
    n24 = sum((b.get("s") or 0) for b in b24)
    min_s = max(20, BUCKET_MIN_SHARE * n24)
    hours = [(b.get("s") or 0, (b.get("r") or 0) / 100.0, b.get("k") or 0)
             for b in b24 if (b.get("s") or 0) >= min_s and b.get("r") is not None]
    worst = min((h[1] for h in hours), default=sr24)
    ttft = L.get("p50_ttft_ms") or 0
    fr = [b.get("f") for b in b24 if b.get("f") and (b.get("s") or 0) >= min_s]
    if fr:
        ttft = int(st.median(fr))
    return {"sr24": round(sr24, 1), "worst": round(worst, 1), "n24": n24,
            "hours_ok": len(hours), "hours_total": len(b24), "ttft_ms": ttft,
            "cache": round((L.get("cache_hit_rate_24h") or 0) / 100.0, 1)}


def effective_cost(a_in, a_out, a_cache, cache_pct) -> float:
    """Coût effectif 30 j cache-aware, $ par 1M tokens (75 % entrée / 25 % sortie)."""
    h = (cache_pct or 0) / 100.0
    eff_in = a_in * (1 - h) + a_cache * h
    return 0.75 * eff_in + 0.25 * a_out


def analyse_listing(L: dict, now: float) -> dict | None:
    if not isinstance(L, dict):
        return None
    chg_at = L.get("last_price_change_at") or 0
    age = (now - chg_at) / 86400.0 if chg_at else 0.0
    if age < 0 or age > WINDOW_D:
        age = 0.0                      # changement hors fenêtre -> pas de pondération
    S = parse_summary(L.get("last_price_change_summary"))
    a_in, old_in, age_used = avg30(L.get("input_price_micros"), S.get("in"), age)
    a_out, _, _ = avg30(L.get("output_price_micros"), S.get("out"), age)
    a_cache, _, _ = avg30(L.get("cache_read_price_micros"), S.get("cache_r"), age)
    r = reliability(L)
    c = effective_cost(a_in, a_out, a_cache, r["cache"])
    return {
        "listing_id": L.get("listing_id"), "channel_id": L.get("channel_id"),
        "supplier": L.get("supplier_nickname") or L.get("supplier_name"),
        "supplier_id": L.get("supplier_id"),
        "available": L.get("listing_availability") == 1,
        "disabled": bool(L.get("supplier_channel_disabled")) or bool(L.get("user_channel_disabled")),
        "in_now": (L.get("input_price_micros") or 0) / 1e6,
        "out_now": (L.get("output_price_micros") or 0) / 1e6,
        "cache_now": (L.get("cache_read_price_micros") or 0) / 1e6,
        "in_30": round(a_in, 8), "out_30": round(a_out, 8), "cache_30": round(a_cache, 8),
        "in_old": round(old_in, 8), "cost30": round(c, 8),
        "days_since_change": round(age_used, 1),
        "direction": L.get("price_change_direction") or "",
        **r,
    }


def fetch_model(model_id: str) -> list[dict]:
    url = (MKT_URL + "?page=1&page_size=100&model=" + urllib.parse.quote(model_id)
           + "&sort=input_asc")
    req = urllib.request.Request(url, headers={"User-Agent": "QuotaHub-Market/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        d = json.loads(resp.read().decode())
    return (d.get("data") or {}).get("items") or []


def analyse_model(model_id: str, now: float) -> dict:
    items = fetch_model(model_id)
    recs = [x for x in (analyse_listing(L, now) for L in items) if x]
    recs.sort(key=lambda x: x["cost30"])
    robust = [x for x in recs
              if x["worst"] >= FLOOR_WORST and x["n24"] >= MIN_SAMPLES_24H
              and not x["disabled"] and x["available"]]
    top = robust[:TOP_N]
    return {
        "model": model_id, "n_listings": len(recs), "n_robust": len(robust),
        "n_changed_30d": sum(1 for x in recs if x["days_since_change"] and x["direction"]),
        "top": top,
        "best": top[0] if top else None,
        "cheapest_instant": min(recs, key=lambda x: x["in_now"]) if recs else None,
    }


def run_pass() -> None:
    t0 = time.time()
    now = t0
    results, errors = {}, []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(analyse_model, m, now): m for m in MODELS}
        for f in futs:
            m = futs[f]
            try:
                results[m] = f.result()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{m}: {type(exc).__name__}: {str(exc)[:80]}")
    dur = time.time() - t0
    ok = {m: r for m, r in results.items() if r["n_listings"]}
    with LOCK:
        merged = dict(SNAP["models"])
        merged.update(ok)                  # on ne perd jamais un modèle déjà connu
        for m, r in results.items():
            if not r["n_listings"]:
                merged[m] = r              # modèle interrogé, aucun canal vivant
        SNAP.update({"models": merged, "generated_at": time.time(), "passes": SNAP["passes"] + 1,
                     "last_pass_s": round(dur, 1), "last_error": ("; ".join(errors) or None),
                     "stale": not ok})
    log(f"passe #{SNAP['passes']} : {len(ok)}/{len(MODELS)} modèles en {dur:.1f}s"
        + (f" | erreurs: {'; '.join(errors)[:200]}" if errors else ""))
    try:
        save_db(ok)
    except Exception as exc:  # noqa: BLE001
        log(f"sqlite: {type(exc).__name__}: {str(exc)[:80]}")


def save_db(models: dict) -> None:
    c = sqlite3.connect(DB_PATH, timeout=10)
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS market30(
            model TEXT, rank INTEGER, listing_id INTEGER, channel_id INTEGER,
            supplier TEXT, in_30 REAL, out_30 REAL, cache_30 REAL, cost30 REAL,
            worst REAL, sr24 REAL, n24 INTEGER, cache_pct REAL, days_chg REAL,
            direction TEXT, generated_at REAL,
            PRIMARY KEY(model, rank))""")
        now = time.time()
        for m, r in models.items():
            c.execute("DELETE FROM market30 WHERE model=?", (m,))
            for i, x in enumerate(r["top"], 1):
                c.execute("INSERT OR REPLACE INTO market30 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (m, i, x["listing_id"], x["channel_id"], x["supplier"],
                           x["in_30"], x["out_30"], x["cache_30"], x["cost30"],
                           x["worst"], x["sr24"], x["n24"], x["cache"], x["days_since_change"],
                           x["direction"], now))
        c.commit()
    finally:
        c.close()


def worker_loop() -> None:
    while True:
        t0 = time.time()
        try:
            run_pass()
        except Exception as exc:  # noqa: BLE001
            with LOCK:
                SNAP["last_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
            log(f"passe globale en echec: {type(exc).__name__}: {str(exc)[:120]}")
        wait = max(5.0, INTERVAL - (time.time() - t0))
        time.sleep(wait)


# ───────────────────── sonde réelle partagée (payante, minuscule) ───────────
# Document de test calibré à ~2200 tokens (seuil universel où tous les providers activent le cache KV)
PROBE_CONTEXT = ("Contrôle de performance et de fidélité du routeur intelligent QuotaHub. "
                 "Vérification de la latence, de la disponibilité réelle et du hit de prompt caching. ") * 75

def probe_model(model_id: str) -> dict:
    """Sonde ACTIVE DE CACHE en 2 passes successives (toutes les 20 min).
    Mesure empirique réelle : vérifie si le canal mémorise le contexte et quel % est en cache.
    Partagé à toute la flotte sans bannir aucun fournisseur."""
    key = _load_key()
    if not key:
        return {"ok": False, "error": "clé A6API absente", "ts": time.time(), "by": "market-worker"}
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    
    # ── PASSE 1 : Amorçage du cache (1050 tokens) ───────────────────────────
    p1 = {"model": model_id,
          "messages": [{"role": "user", "content": PROBE_CONTEXT + "\nRéponds: 1"}],
          "max_tokens": 16, "stream": False}
    try:
        r1 = urllib.request.Request(API_BASE + "/v1/chat/completions", data=json.dumps(p1).encode(), headers=headers)
        with urllib.request.urlopen(r1, timeout=PROBE_TIMEOUT) as resp1:
            pass
    except Exception as e:
        return {"ok": False, "error": f"amorce: {str(e)[:80]}", "ts": time.time(), "by": "market-worker"}

    time.sleep(0.8) # Délai de propagation du cache amont

    # ── PASSE 2 : Mesure de la persistance de cache et latence ───────────────
    p2 = {"model": model_id,
          "messages": [{"role": "user", "content": PROBE_CONTEXT + "\nRéponds: 2"}],
          "max_tokens": 16, "stream": False}
    t0 = time.time()
    try:
        r2 = urllib.request.Request(API_BASE + "/v1/chat/completions", data=json.dumps(p2).encode(), headers=headers)
        with urllib.request.urlopen(r2, timeout=PROBE_TIMEOUT) as resp2:
            d = json.loads(resp2.read().decode())
            dt = time.time() - t0
        u = d.get("usage", {})
        tin = u.get("prompt_tokens") or 0
        tout = u.get("completion_tokens") or 0
        det = u.get("prompt_tokens_details") or {}
        cac = det.get("cached_tokens") or 0
        cache_pct = round(100.0 * cac / max(1, tin), 1) if tin else 0.0
        return {"ok": True, "latency_s": round(dt, 2), "tin": tin, "tout": tout,
                "cached_tokens": cac, "cache_pct": cache_pct, "ts": time.time(), "by": "market-worker"}
    except Exception as e:
        return {"ok": False, "error": f"mesure: {str(e)[:80]}", "ts": time.time(), "by": "market-worker"}


def run_probes_once():
    t0 = time.time()
    res: dict = {}
    for m in PROBE_MODELS:
        try:
            res[m] = probe_model(m)
        except Exception as e:
            res[m] = {"ok": False, "error": str(e)[:60]}
        time.sleep(0.3)
    with LOCK:
        PROBES.update({"models": res, "generated_at": time.time(),
                       "passes": PROBES["passes"] + 1})
    ok = sum(1 for v in res.values() if v.get("ok"))
    log(f"sonde partagee #{PROBES['passes']} : {ok}/{len(res)} modeles OK (duree {round(time.time()-t0, 1)}s)")
    return res

def probe_loop() -> None:
    """Une fournée de sondes toutes les PROBE_INTERVAL (30 min par défaut)."""
    while True:
        t0 = time.time()
        run_probes_once()
        wait = max(5.0, PROBE_INTERVAL - (time.time() - t0))
        time.sleep(wait)


# ─────────────────────────────── HTTP loopback ─────────────────────────────
class H(BaseHTTPRequestHandler):
    server_version = "QuotaHubMarket/1.0"

    def log_message(self, *a):  # silence
        return

    def _json(self, status: int, obj) -> None:
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        q = urllib.parse.urlparse(self.path)
        if q.path == "/health":
            with LOCK:
                return self._json(200, {"ok": True, "service": "quota-hub-market",
                                        "passes": SNAP["passes"],
                                        "generated_at": SNAP["generated_at"],
                                        "age_s": round(time.time() - SNAP["generated_at"], 1)
                                        if SNAP["generated_at"] else None})
        if q.path in ("/api/prices", "/api/prices/"):
            params = urllib.parse.parse_qs(q.query)
            with LOCK:
                snap = json.loads(json.dumps(SNAP))
                probes = json.loads(json.dumps(PROBES))
            models = snap["models"]
            want = params.get("model", [None])[0]
            if want:
                models = {want: models[want]} if want in models else {}
            out = {
                "ok": True,
                "service": "quota-hub-market",
                "generated_at": snap["generated_at"],
                "age_s": round(time.time() - snap["generated_at"], 1) if snap["generated_at"] else None,
                "passes": snap["passes"],
                "window_days": WINDOW_D,
                "method": "moyenne 30j pondérée par le temps + fiabilité pire-heure",
                "stale": snap["stale"],
                "models": models,
                # sondes RÉELLES partagées (une seule fournée pour toute la flotte)
                "probes": probes,
            }
            return self._json(200, out)
        if q.path in ("/api/probes", "/api/probes/"):
            with LOCK:
                probes = json.loads(json.dumps(PROBES))
            out = {"ok": True, "service": "quota-hub-market", **probes,
                   "age_s": round(time.time() - probes["generated_at"], 1)
                   if probes["generated_at"] else None}
            return self._json(200, out)
        return self._json(404, {"error": "not found"})


def main() -> None:
    log(f"worker marché : {len(MODELS)} modèles, passe toutes les {INTERVAL}s, "
        f"{WORKERS} requêtes en parallèle, HTTP 127.0.0.1:{PORT}")
    log(f"sondeur partagé : {len(PROBE_MODELS)} modèles toutes les {PROBE_INTERVAL}s "
        f"(un seul test pour toute la flotte)")
    threading.Thread(target=worker_loop, daemon=True).start()
    threading.Thread(target=probe_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
