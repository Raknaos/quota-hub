# Quota.Hub — crédit IA à routage automatique

Un seul point d'accès, API compatible OpenAI SDK : `https://smartapi.cheap/v1`.
Le client recharge du **crédit** ; chaque requête tire dessus. Pas d'abonnement
forcé, pas de quota à vie : **le crédit s'ajoute au solde** à chaque recharge et
n'expire pas.

| Élément | Valeur |
|---|---|
| URL de base | `https://smartapi.cheap/v1` |
| Modèle | `AutoSmart Flash 1.0` |
| Facturation | au token, à l'usage, sur le crédit rechargé |

Le champ `model` est ignoré : le client ne choisit jamais le modèle servi.

## Modèle de coût

- Le routeur sert **toujours le modèle vivant le moins cher** : `qwen3.8-flash`,
  `glm-5.3-flash`, `deepseek-v4.1-flash`, `grok-4.6`. Un modèle à marge mesurée
  négative est écarté tant qu'une alternative rentable existe.
- Les quatre sont **multimodaux** : une image route comme du texte (il n'existe plus
  de « pool vision » séparé). Prouvé par test image réel (4/4 modèles).
- Les **prix de vente sont fixes** et identiques à la liste UnoRouter : voir
  [`PRIX-UNOROUTER-REFERENCE.md`](PRIX-UNOROUTER-REFERENCE.md). Ils ne sont **jamais**
  dérivés du coût d'achat ; le coût amont (canal A6API le moins cher) ne sert qu'au
  calcul interne de marge.

## Architecture

- `gateway/gateway.py` — passerelle (VPS, systemd non-root `qh`, HTTPS auto-signé
  épinglé, SQLite WAL) : comptes scrypt, clés hachées sha256, sessions HMAC 30 j,
  codes d'activation, metering usage réel, rate-limit 60 rpm + burst, throttles
  register/login, failover ×3, cooldowns, amont toujours en `stream:false`
  (facturation exacte) puis re-sérialisation SSE si le client stream.
- `api/gw.js` — proxy Vercel : TLS + pin du certificat (anti-MITM), HMAC par
  requête (anti-rejeu, secret serveur uniquement), bascule automatique vers les
  nœuds de secours (`QH_GATEWAY_NODES`) **uniquement** si le primaire est injoignable.
- `index.html` / `app.js` — front Glass, prix fixes, mesures live (fiabilité, latence),
  zéro donnée simulée.
- `specs/` + `.specify/` — artefacts Spec-Driven Development (Spec Kit). Voir la
  constitution du projet : [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## Endpoints clients

- `POST https://smartapi.cheap/v1/chat/completions` (Bearer `sk-qh-…`)
  → 200 + `quota_hub` {plan, tokens_billed, tokens_remaining, served_model}.
- SDK OpenAI : `base_url = "https://smartapi.cheap/v1"`.
- `GET /api/me` → solde, clés, consommation.

## Paiement (Stripe)

Le client paie sur **Stripe Checkout hébergé** (aucune donnée de carte ne touche le
site). Le crédit n'est accordé **que** par le webhook signé de Stripe — jamais par le
retour navigateur — et une session ne crédite qu'**une fois** (`payments.stripe_session`
UNIQUE, rejeu de webhook sans effet).

| Route | Rôle |
|---|---|
| `POST /api/pay/checkout` (session requise) | crée la session Stripe. `{pack:20}` = abonnement → **40 $** ; `{amount:10}` = recharge 1:1 → **10 $** |
| `POST /api/stripe/webhook` (public, signé Stripe) | `checkout.session.completed` → crédite `usd_total`, journalise dans `payments` |

Clés à poser **par l'ops, sur chaque nœud** (jamais au front, jamais dans un log) :

```bash
ssh -i <clé> root@<nœud> "bash /opt/quota-hub/_stripe_keys.sh"   # saisie masquée
```

Côté Stripe : endpoint `https://smartapi.cheap/api/stripe/webhook`, événement
`checkout.session.completed`, puis copier le *Signing secret* (`whsec_…`).
Tant que les clés sont absentes, le site répond « paiement non configuré » —
il n'invente jamais un encaissement.

## Ops (SSH, loopback uniquement)

- Codes : `curl -sk -X POST https://127.0.0.1:8890/admin/codes -H 'X-Admin-Token: …' -d '{"plan":"auto"}'`
- Stats : `/admin/stats` (par plan, coût amont réel).
- Prix : relever UnoRouter **via le JSON-LD** (`_prod/_uno_releve.py`), jamais via le
  prix affiché sur la fiche — écart constaté jusqu'à 56×.
- Sauvegarde : `hub.db` sauvegardée chaque jour avec rotation 14 j (`integrity_check`).
- Flotte : 4 nœuds, même empreinte de `gateway.py` exigée partout après déploiement.
- Redeploy : `bash _prod/_deploy_gw.sh <ip> gateway.prod.py`.

## Sécurité

TLS-only Vercel→VPS avec pin SPKI · HMAC 300 s anti-rejeu · `/admin*` loopback ·
scrypt + throttle 5/15 min · clés jamais réaffichées · codes à usage unique hachés ·
rate-limit + burst · 401/403/402/413 sans cooldown (faute client ≠ panne canal) ·
zéro-mock (502 typé, 0 token débité).

Durcissements du 2026-09-14 : authentification **réellement appliquée** sur la
passerelle Antigravity 8895 (elle acceptait tout le monde sans clé) · `/api/prices`
signé hors loopback et **plus aucun prix amont transmis au navigateur** · mot de
passe SSH root désactivé sur les nœuds exposés, fail2ban actif partout · journald
borné et `MemoryMax` posés par unité · clés et abonnements orphelins neutralisés
sans suppression.

## Crédit (règle appliquée depuis le 14-09)

**1 $ payé = 1 $ d'usage.** Le solde est un montant en **dollars**, plus un compteur
de tokens à vie (l'ancien « 1 Md de tokens » n'existe plus). Chaque requête débite le
coût réel de ce qu'elle a consommée, au **tarif fixe du modèle servi** :

```
coût = (tokens entrée − 90 % des tokens servis du cache) / 1M × prix_entrée
     + tokens sortie / 1M × prix_sortie
```

Les tokens restent journalisés (`usage_logs`) pour l'audit et les statistiques, mais
ne plafonnent plus rien : c'est `usd_used >= usd_total` qui déclenche le 402.

**Abonnements** (même principe qu'UnoRouter) : le crédit reçu est le **double** du
montant payé.

| Payé | Crédit reçu |
|---|---|
| 20 $ | **40 $** |
| 50 $ | **100 $** |
| 100 $ | **200 $** |
| 200 $ | **400 $** |

Côté ops, un pack se matérialise par un code d'activation :
`curl -sk -X POST https://127.0.0.1:8890/admin/codes -H 'X-Admin-Token: …' -d '{"pack":20}'`
→ code qui crédite 40 $. `{"usd":7.5}` crée un montant libre, `{}` le montant par
défaut du plan. Le solde **s'ajoute** à chaque recharge, il n'est jamais remis à zéro.

Reprise des soldes existants (faite une fois, marqueur `migrations.usd_credit_v1`) :
le reste à consommer est converti à l'ancienne règle affichée au client
(1 Md tokens = 10 $) — personne ne perd ni ne gagne de crédit au changement de base.
*13 abonnements repris le 14-09 sur le primaire.*
