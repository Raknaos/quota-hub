# Quota.Hub — Abonnement IA à routage automatique

**Produit : $10 = 1 milliard de tokens (30 jours).** Le client ne choisit jamais
de modèle : la passerelle sert toujours le canal le moins cher vivant
(fiabilité ≥ 80 %, hystérésis 15 % pour préserver le cache de prompts,
cooldowns automatiques, failover instantané). API compatible OpenAI SDK.

## Architecture
- `gateway/gateway.py` — passerelle (VPS, systemd, user qh, loopback+secret HMAC) :
  comptes (scrypt), clés API (sha256, jamais réaffichées), abonnements par code
  d'activation (1 Md tokens), metering à l'usage réel, rate-limit 60 rpm/clé.
- `api/gw/[[...path]].js` — proxy Vercel : injecte X-QH-TS/X-QH-SIG (secret côté
  serveur uniquement, jamais dans le JS public) et relaie /gw/* + /v1/*.
- `index.html` + `app.js` — front Glass : plan, console, activation de code,
  playground réel. Zéro donnée simulée.

## Endpoints clients
- `POST https://quota-hub.vercel.app/v1/chat/completions` (Bearer sk-qh-…)
  → 200 + `quota_hub.tokens_remaining`. Le champ `model` est ignoré.
- Back-office via SSH (loopback) : `/admin/codes`, `/admin/stats` (X-Admin-Token).

## Sécurité
- Mots de passe scrypt ; clés hachées ; sessions HMAC 30 j ; throttle login.
- Signature HMAC front→gateway (fenêtre 300 s) ; /admin* jamais exposé.
- Aucune réponse simulée : amont KO = 502 typé, 0 token décompté.
