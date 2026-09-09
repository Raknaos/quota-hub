# Quota.Hub — Abonnements IA à routage automatique

Deux abonnements, même URL, API compatible OpenAI SDK :

| Plan | Prix | Quota | Modèle servi |
|---|---|---|---|
| **auto** | $10 / 30 j | 1 Md tokens | Toujours le moins cher vivant : qwen3.8-flash, glm-5.3-flash, deepseek-v4-flash (+ toute la famille deepseek v4 : v4.1, vision — inclusion automatique dès qu'un canal existe). Les images routent vers un canal vision si disponible. |
| **gemini** | $10 / 30 j | 100 M tokens | gemini-3.8-flash forcé (qualité constante). |

Le champ `model` est toujours ignoré : le client ne choisit jamais.

## Architecture
- `gateway/gateway.py` — passerelle (VPS, systemd non-root `qh`, HTTPS auto-signé
  épinglé, SQLite WAL) : comptes scrypt, clés hachées sha256, sessions HMAC 30 j,
  codes d'activation par plan, metering usage réel, rate-limit 60 rpm + burst,
  throttles register/login, failover ×3, cooldowns, amont toujours en stream:false
  (facturation exacte) puis re-sérialisation SSE si le client stream.
- `api/gw.js` — proxy Vercel : TLS + pin du certificat (anti-MITM), HMAC par
  requête (anti-rejeu, secret serveur uniquement), Content-Length explicite.
- `index.html` / `app.js` — front Glass, 2 plans, zéro donnée simulée.

## Endpoints clients
- `POST https://quota-hub.vercel.app/v1/chat/completions` (Bearer sk-qh-…)
  → 200 + `quota_hub` {plan, tokens_billed, tokens_remaining, served_model}.
- SDK OpenAI : base_url `https://quota-hub.vercel.app/v1`.

## Ops (SSH, loopback uniquement)
- Codes : `curl -sk -X POST https://127.0.0.1:8890/admin/codes -H 'X-Admin-Token: …' -d '{"plan":"auto"}'`
- Stats : `/admin/stats` (par plan, coût amont réel).
- Redeploy : `bash gateway/_hub_deploy.sh <ip>` (copie la clé amont en 600 qh).

## Sécurité (audit 2026-09-09)
TLS-only Vercel→VPS avec pin SPKI · HMAC 300 s anti-rejeu · /admin* loopback ·
scrypt + throttle 5/15 min (429 prouvé) · clés jamais réaffichées · codes à usage
unique hachés · quotas par plan server-side · rate-limit + burst · 401/403/402/413
sans cooldown (faute client ≠ panne canal) · zéro-mock (502 typé, 0 token débité).
