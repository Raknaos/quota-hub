# Routeur Smart API Cheap — V3 : mode auto multi-utilisateurs

> Vision Baptiste (11-09) : « le routeur chez moi, sur Curley/Sandra/Victor/Hugo —
> si un tombe, les autres fonctionnent. Les prix vérifiés par le routeur toutes
> les 20 min et partagés à tous les clients. Maximum d'effort pour garder le
> cache : rester sur le même modèle tant que le cache chaud vaut plus que le
> gain d'une bascule ; une nouvelle conversation part au moins cher. Capable de
> 100 → 10 000 utilisateurs. Page Journaux sur le site. »

## État de l'existant (audit 11-09)

| Brique | Existant | Manque |
|---|---|---|
| Calcul des prix | Worker `quota-market` (.66:8891, loopback) + TTL 1200 s (20 min) + `market_get`/`market30_all` **non bloquants** (refresh en thread) | Boucle de refresh périodique explicite dans `main()` |
| Pin cache-aware | `pick_model` cache-first MAIS **pin GLOBAL** (une seule variable `PIN` partagée par TOUS les clients) | Pin **par clé API + par conversation** (V3, en cours) |
| Anti-503 | `wait_or_last_resort` + cooldowns + crise plateforme | — |
| Facturation | `usage_logs` complet (tokens, cache, coût amont, modèle, supplier) à chaque requête | Endpoint API pour les clients (`/api/usage`) |
| Site | Onglets catalogue/console/portefeuille/playground | Page **Journaux** (historique requêtes façon UnoRouter) |
| Flotte | Gateway sur Sandra (.66) uniquement | Réplique Curley/Victor/Hugo + bascule |

## Brique 1 — Pin par conversation (V3) ✅ implémenté

- `conv_signature(payload)` : empreinte stable du début de conversation (system tronqué + premiers messages) → une conv qui s'allonge garde la même empreinte.
- `CONV[(key_id, sig)]` : état `{model, supplier, ts, tin, tout, cached}` — **par clé API**, donc par client.
- Décision dans `pick_model(models, ctx)` :
  1. Conv chaude (< `CONV_TTL` 2 h) → **garder** le modèle sauf si `switcher < rester × (1 − 15 %)` où
     - `rester` = (tin−cachés)×in + cachés×cache_read + tout×out (le cache chaud ne se paie pas plein tarif)
     - `switcher` = tin×in_nouveau + tout×out_nouveau (cache froid chez le nouveau)
  2. Bascule justifiée → préférer un modèle du **même fournisseur** (≤ +25 %) avant de changer de supplier.
  3. Conv neuve / froide → le moins cher espéré (coût30/success).
- Repli : appels sans contexte → ancien pin global conservé (compat interne).
- Mémoire bornée : `CONV_MAX` 20 000, prune TTL + LRU.

## Brique 2 — Marché rafraîchi toutes les 20 min par le routeur

- `refresh_loop()` : boucle daemon dans `main()` — re-warm du marché toutes les `MARKET_TTL` (1200 s).
- Aucune requête client ne déclenche de fetch synchrone (déjà garanti : `market_get`/`market30_all` répondent le cache et rafraîchissent en thread).
- Multi-nœuds (phase 4) : **un seul calculateur** (le sondeur du .66) publie le snapshot ; les autres nœuds le lisent — les prix restent identiques pour tous.

## Brique 3 — Journaux clients

- `GET /api/usage` (session) : 50 dernières requêtes (modèle, tokens in/out facturés, cache, coût amont, date) + totaux 30 j par jour et par modèle + totaux globaux.
- Front : nouvel onglet « Journaux » sur smartapi.cheap (table façon UnoRouter, totaux, graphe par jour).
- Jamais de nom de canal amont exposé (règle produit).

## Brique 4 — Flotte + bascule (Curley / Sandra / Victor / Hugo)

- Déployer la passerelle + worker sur les 4 VPS (même code, même .env, systemd).
- **Base partagée** (users/clés/souscriptions/usage + snapshot marché) : prérequis de la bascule — un client doit marcher sur n'importe quel nœud. Piste : Postgres managé (Supabase déjà au repo, tâche 28) ou DB maîtresse + réplica.
- Bascule : health-check + réécriture DNS (TTL court) ou proxy à health-checks vers le nœud sain.
- Le calculateur (sondeur) reste UNIQUE — les nœuds ne sondent pas chacun leur tour.

## Phases

1. **V3 routeur** (ce commit) : pin par conv + refresh 20 min + `/api/usage`.
2. **Journaux front** : onglet + branchement session.
3. **Multi-nœuds** : 2ᵉ réplique + bascule DNS ; puis 4 nœuds.
4. **Base partagée** : migration (prérequis bascule complète).
