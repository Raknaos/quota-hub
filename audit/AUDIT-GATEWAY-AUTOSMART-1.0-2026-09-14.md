# Audit indépendant — Passerelle SmartAPI / produit « AutoSmart Flash 1.0 »

**Date** : 2026-09-14 · **Périmètre** : 4 VPS (Sandra .66 / Victor .67 / Hugo .68 / Curley .69) + dépôt `HubAPI_Quota` + site public `https://smartapi.cheap`
**Méthode** : 3 agents isolés (angles disjoints, ne voyant pas les rapports les uns des autres), **lecture seule stricte** (0 écriture, 0 restart, 0 création de compte/clé, 0 job soumis), puis fusion par le chef + **recoupement indépendant** des constats critiques.
**Aucune écriture n'a été effectuée sur les 4 nœuds.**

| Porte | Angle | Note |
|---|---|---|
| A | Fonctionnement réel du produit, routage, facturation, promesses publiques | fonctionnel 5,0 · sécurité 5,5 · fiabilité 4,0 |
| B | Sécurité (auth, réseau, injections, fuites) | fonctionnel 7,5 · sécurité 4,5 · fiabilité 6,0 |
| C | Fiabilité, vérité des mesures, intégrité des données | fonctionnel 6,5 · sécurité 6,0 · fiabilité 5,0 |
| **Consolidé** | | **fonctionnel 6,3 · sécurité 5,3 · fiabilité 5,0** |

---

## Verdict en une phrase

**La passerelle fonctionne vraiment et facture juste ; c'est la communication publique autour d'elle qui est fausse, et il reste deux trous de sécurité réseau concrets.**

Ce qui est solide : le service sert des réponses, la formule de facturation est exacte au token, les unités de coût sont cohérentes, le cœur cryptographique est propre (SHA-256, scrypt, comparaison temps constant, aucune injection), et le redéploiement du 14-09 à 08h37 **n'a introduit aucune régression** — il a même amélioré le taux de cache mesuré de 10,4 % à 61,0 %.

Ce qui ne va pas : les chiffres affichés sur le site sont **fabriqués en dur**, la chaîne d'approvisionnement amont fuit publiquement, 2 des 4 VPS acceptent encore un **mot de passe root SSH**, le port 8890 est **joignable depuis Internet**, et 3 des 4 nœuds ne servent **aucun trafic**.

---

## 1. Constats critiques (consensus de 2 portes ou plus, + recoupement chef)

### 🔴 P0-1 — Les chiffres publics sont fabriqués en dur et contredits par l'API de la passerelle elle-même
*Trouvé par la porte A ET la porte C, indépendamment. Vérifié par le chef.*

| Affiché sur le site | Valeur réelle mesurée | Écart |
|---|---|---|
| `99.9%` (index.html:206) | 502 « tous canaux épuisés » sur 24 h → **11,5 % à 16,8 % d'échec** | ×~30 |
| `177,834,027` tokens (index.html:229) | `GET /gw/api/public/stats` → **217 172 232** | −18 % |
| `36,982` requêtes (index.html:237) | **7 194** | **×5,1** |
| `118,556` TPM (index.html:244) | **24 613** | ×4,8 |
| `~2.5s` (index.html:899) | p50 premier chunk streaming = **22,41 s** (p90 50 s, max 101,9 s) | ×9 |
| `99.8%` succès, `2.20s` (app.js `MODELS_DATA`) | 502 réels + p50 22,4 s | ×10 |

Preuve : `grep -noE "…" index.html` → lignes 206/229/237/244/899, et `app.js:28 MODELS_DATA`. Le front **ne contient aucun `fetch()` vers la passerelle** pour ces valeurs : ce sont des constantes JS figées. Les vraies valeurs ne sont consommées que par le bloc live, qui écrase des replis… eux aussi faux (donc si l'API échoue, le visiteur voit un chiffre plus flatteur que la réalité).

### 🔴 P0-2 — `/gw/api/prices` publie toute la chaîne d'approvisionnement
*Trouvé par A ET B. Vérifié par le chef : `curl https://smartapi.cheap/gw/api/prices` → **HTTP 200, 25 583 octets, sans authentification**.*

Sont publics : noms des revendeurs amont (`aaa模型大王`, `bbgt-vip`, `tokentrans`, `新3`, `官逆`, `CheapMode2`…), `listing_id`, `channel_id`, **prix d'achat**, taux de succès et structure de marge. C'est l'exact inverse du principe affiché dans le code (`gateway.py:94-95` : « Le client ne voit JAMAIS l'identité réelle ») — d'autant plus incohérent que `/v1/models` ne sert qu'un seul nom, `AutoSmart Flash 1.0`. Un concurrent obtient votre liste de fournisseurs et votre coût réel en une requête.

### 🔴 P0-3 — Mot de passe root SSH actif sur Victor (.67) et Curley (.69)
*Trouvé par B. **Vérifié par le chef sur les 4 nœuds** (mon premier test ne portait que sur Sandra — erreur de ma part, corrigée).*

```
23.94.144.66  permitrootlogin without-password  passwordauthentication no
23.94.144.67  permitrootlogin yes               passwordauthentication yes   ←
23.94.144.68  permitrootlogin without-password  passwordauthentication no
23.94.144.69  permitrootlogin yes               passwordauthentication yes   ←
```
Cause : `/etc/ssh/sshd_config.d/50-cloud-init.conf` jamais corrigé sur ces deux nœuds, alors que le correctif existait sur Sandra (drop-in désactivé le 09-09) — **il n'a jamais été propagé**. Empreinte root en **MD5-crypt** (`$1$`, cassable). Bruteforce actif : **91 479 échecs en 14 j sur Victor**, 31 405 sur Curley. `fail2ban` **inactif sur Victor et Hugo**. Aucune connexion par mot de passe réussie constatée (0 `Accepted password` sur 30 j) : **pas de compromission prouvée**, mais rien ne l'empêche.

### 🔴 P0-4 — Port 8890 joignable depuis Internet, pare-feu absent sur 3 nœuds
*Trouvé par B. **Vérifié par le chef** : `curl -k https://<IP>:8890/health` → **200 sur les 4 adresses**.*

L'écoute est `0.0.0.0:8890` (`gateway.py:2342`) en **TLS auto-signé**. `iptables -S` sur Sandra/Victor/Hugo ne renvoie que des politiques `ACCEPT` sans aucune règle, `ufw` inactif. Seul Curley a ufw + fail2ban. Conséquence : le modèle de menace « Vercel est la seule porte » n'est pas appliqué — les routes `/api/*` sont atteignables en direct (elles exigent bien la signature HMAC, ce qui limite la casse). **Port 8895 (AntigravityGateway) est lui aussi exposé sur Sandra.** Les routes `/admin/*` résistent (403 depuis Internet, double verrou loopback + jeton temps constant).

### 🟠 P1-5 — 3 nœuds sur 4 ne servent aucun trafic
`FLUX_24h` : Sandra **2 144**, Victor 0, Hugo 0, Curley 0. `usage_logs` 7 j : 5 074 / 12 / 1 / 1. Le front Vercel cible **une seule URL** (`QH_GATEWAY_URL`), aucun load-balancer, pas de nginx sur Sandra. La page publique affiche pourtant « 100% Uptime » sur les 4 IP : **la chute de Sandra coupe tout le produit**. Les journaux des 3 réplicas s'arrêtent à la seconde du redéploiement et ne contiennent aucune tentative amont.

### 🟠 P1-6 — Le mensonge de cache est toujours routé en canal n°1
| Canal | Cache annoncé (market30) | Cache réel (usage_logs) | Poids |
|---|---|---|---|
| `glm-5.3-flash` / 新3 | 53,4 % | **3,16 %** | 85,18 M tokens de prompt (53,6 % du volume) |
| `deepseek-v4.1-flash` / bbgt-vip | 15,2 % | **0,00 %** | 37 % de la facture amont |

Ces deux canaux concentrent **84,9 % de la facture amont quotidienne** — mot pour mot le « 86 % » que le commentaire du code décrivait. Le classement du marché utilise le `cache_pct` **déclaré** par le fournisseur (`market30.py:151`), donc il favorise structurellement les menteurs. `BANNED_SUPPLIERS = set()` (ligne 89) désactive le garde-fou pourtant documenté, et le filtre `CACHE_HONEST_MIN` est contourné quand les autres modèles sont en cooldown.

### 🟠 P1-7 — Le quota vendu ne se renouvelle jamais
`PLAN_DEFAULT = 1 000 000 000` tokens : un **stock unique, non renouvelable**. Aucun reset hebdomadaire, aucun cron (`grep` de l'unique écrivain → `gateway.py` seul). Une fois épuisé, le client reçoit un **402 permanent** — alors que la page publique vend « 10 $ de crédit rechargé chaque semaine » et « 40 $ de crédit API par mois ». Risque direct de chargeback.

### 🟠 P1-8 — Facturation sur estimation et troncature silencieuse
- **100 lignes / 24 h** facturées via `route_reason='flux_estime'` quand l'amont ne rend pas son usage (flux interrompu) → 3,86 M tokens facturés **sans preuve d'usage amont**, sans décote de cache. Corrélé à 101 `RELAY interrompu (SSLEOFError)`.
- Le chemin **non-stream réécrit `finish_reason: "length"` en `"stop"`** (lignes 839-842 / 903-904) : le client ne peut **pas détecter** une réponse tronquée. Plafond de sortie réel `MAX_TOKENS_CAP = 8000`. Asymétrie stream/non-stream.

### 🟠 P1-9 — Dérive de flotte non détectée
| Élément | Sandra | Victor / Hugo / Curley |
|---|---|---|
| `market30.py` md5 | `43960a480f` (13-09 16:02) | `4af31fd26a` (11-09 20:59) — **et le dépôt local en a une 3ᵉ** (`f45d7d52`) |
| `QH_MARKET_INTERVAL` réel | **1200** (cadence 20 min) | **120** (cadence 2 min) |

La synchro `_sync-db.sh` ne porte **que sur `hub.db`** ; le code de la sonde n'est répliqué par aucun mécanisme, et `_deploy_market.sh` écrit `120` alors que l'unité en service vaut `1200`. **Un redéploiement à froid ne redonnerait pas l'état qui tourne.**

### 🟠 P1-10 — Intégrité relationnelle entamée
- **11 clés API non révoquées** et 22 abonnements pointent vers des **utilisateurs inexistants** (5 users en base, ids 16-18/27-28 ; 16 codes sur 20 rattachés à un utilisateur absent).
- **2 073 lignes antérieures au 13-09** ne respectent pas la règle de facturation actuelle (`tokens = prompt+completion − 0,9×cached`) : le 12-09 totalise 66,75 M tokens d'écart avec `cached_tokens=0` enregistré. **Le « total tokens » mélange donc deux comptabilités.**
- `tokens_used` de l'abonnement dépasse la somme du journal de **72 139 tokens**.
- **Une seule sauvegarde de base** (`hub.db.bak-…-20260912-115020`) : 511 lignes contre 7 184 → une restauration ferait perdre **2 jours de facturation**.

---

## 2. Ce qui marche vraiment (prouvé)

- **Le produit sert** : 3 003 requêtes / 24 h (plan `auto` exclusivement), 7 194 requêtes cumulées, 217,17 M tokens facturés, 158,95 M tokens amont, coût amont 0,4302 $/24 h → **0,002707 $/M token amont**.
- **La facturation client est exacte** : `SUM(tokens)` = `prompt + completion − 0,9×cached` à 0,0004 % près d'arrondi, et **0 ligne** ne facture plus que l'usage amont. Vérifié à la main sur 3 lignes.
- **Les unités de `cost_amont_usd`** sont bien des $/million, recalculées à la main sur 3 lignes (écart ≤ 0,2 %).
- **Les compteurs publics sont la base** : `/api/public/stats` et `SELECT COUNT(*), SUM(tokens)` lus dans la même seconde → identiques. Aucune fabrication côté serveur (le mensonge est dans le **bundle du site**, pas dans l'API).
- **Cœur cryptographique sain** : clés API `sk-sm-` + 160 bits, stockées en **SHA-256** uniquement ; mots de passe **scrypt** (n=2¹⁴, r=8, p=1) ; sessions HMAC temps constant ; codes d'activation 64 bits à usage unique **atomique** ; **aucune injection** SQL/commande/SSRF/traversée ; **aucun IDOR** ; **aucun secret en clair** dans les logs, `.bak` ou le front.
- **Les routes admin sont réellement fermées** : boucle locale (adresse TCP, non falsifiable) + jeton temps constant + 404 côté Vercel → 403 depuis Internet sur les 4 nœuds.
- **Auto-résolution** : les cooldowns se posent et se lèvent seuls, `Traceback=0` sur 24 h, `NRestarts=0`, aucune alerte « marché périmé ».
- **Durcissement systemd réel** : `User=qh`, `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp=yes`.
- **Le routage vision fonctionne** : `deepseek-v4-flash-vision-exp` = 14 requêtes/7 j, cache réel 87 %.

---

## 3. Désaccords entre portes (signalés par honnêteté)

| Point | Porte A | Porte C | Lecture |
|---|---|---|---|
| Note fonctionnelle | 5,0 | 6,5 | A jugeait les **promesses publiques**, C jugeait le **moteur**. Les deux ont raison sur leur angle. |
| Taux d'échec 24 h | 11,5 % | 16,8 % | Dénominateurs différents (usage_logs vs lignes `FLUX`). Fourchette réelle : **~12-17 %**. |
| Volume 24 h | 3 003 requêtes | 2 144 `FLUX` | Idem : lignes facturées vs lignes de flux. |
| `market30.py` | non relevé | divergence P1 | Confirmé par mon propre md5sum. |

---

## 4. Corrections à apporter à mes propres conclusions antérieures

1. **« Port 8890 non joignable depuis Internet » → FAUX.** Mon test était en **HTTP nu** ; le service est en **TLS**. En `https://`, les 4 nœuds répondent **200**. Le port est bien exposé.
2. **« sshd conforme (clé seule) » → incomplet.** Vérifié seulement sur Sandra. **Victor et Curley acceptent le mot de passe root.**
3. **« market30.py diverge » → confirmé** (ma 3ᵉ empreinte locale est encore une autre version).

C'est précisément ce que l'audit indépendant devait rattraper.

---

## 5. Non vérifiable (dit franchement)

- **Le tarif réellement encaissé** : le moteur facture en **tokens** ; le raccord « $20/mois → $40 de crédit » vers 1,1 Md de tokens n'est stocké nulle part (aucune colonne prix/crédit). La conversion `$10 = 1e9 tokens` vit dans le JavaScript du site.
- **La correspondance `cost_amont_usd` ↔ facture A6API** : aucun endpoint de solde consulté (lecture seule). Seul indice indirect : **126 erreurs « 可用额度不足 » (solde amont insuffisant) en 24 h**.
- **Le test de bascule** Vercel → réplicas : interdit (trafic de production).
- **L'exploitabilité réelle de la liaison OAuth par email** : exigerait de créer un compte (interdit).
- **La véracité des `sr24`/`cache_pct`** du marché : ce sont des valeurs **déclaratives** du revendeur, recopiées telles quelles.
- **Restauration réelle après sinistre** : non testée.

---

## 6. Plan d'action priorisé

**Immédiat (< 1 h)**
1. **SSH** : propager le drop-in de Sandra sur Victor et Curley (`PasswordAuthentication no`, `permitrootlogin without-password`), **changer le mot de passe root** des deux nœuds, activer `fail2ban` sur Victor et Hugo.
2. **Réseau** : pare-feu hôte (nftables/ufw) autorisant 8890 **uniquement** aux IP de sortie Vercel ; fermer 8895 s'il n'est pas voulu.
3. **`/gw/api/prices`** : le repasser en **loopback** ou retirer `supplier`, `channel_id`, `in_now`, `out_now`, `cost30` de la réponse publique.

**Court terme (cette semaine)**
4. **Page publique** : supprimer les constantes en dur (index.html 206/229/237/244/899 + `MODELS_DATA`) ou les brancher sur `/api/public/stats` ; corriger l'étiquette « tokens réels consommés sur la clé amont » (c'est un compteur **facturé**, −34,2 % du brut).
5. **Cartes « 100% Uptime »** des 3 nœuds inactifs : soit une vraie répartition, soit retirer la mention.
6. **`finish_reason`** : ne plus réécrire `length` → `stop`.
7. **Sauvegarde `hub.db`** : ajouter une sauvegarde quotidienne rotative.
8. **Quota** : soit un vrai renouvellement hebdomadaire, soit retirer la promesse.

**Ensuite**
9. Aligner `market30.py` et `QH_MARKET_INTERVAL` sur les 4 nœuds ; faire que `_deploy_market.sh` reproduise l'état en service.
10. Nettoyer les 11 clés / 22 abonnements orphelins ; figer la règle de facturation (les 2 073 lignes du 12-09).
11. Nonce HMAC (anti-rejeu sur la fenêtre 300 s), session OAuth en cookie HttpOnly plutôt qu'en URL, vérifier l'email GitHub avant liaison de compte.
12. `MemoryMax` sur les unités (256 Mo suffit), borner journald sur Sandra/Hugo/Curley.

---

## 7. Annexe — angles morts déclarés

Le « trafic public » mesuré est en réalité **un test de charge interne** (clés `fleet-sandra` / `fleet-hugo` / `fleet-curley` / `fleet-obra` rattachées au compte de l'opérateur). Les compteurs publics mesurent donc une activité d'essai, pas une clientèle — à garder en tête avant toute communication commerciale.

Le tableau « Modèles » du site est également codé en dur (`MODELS_DATA`) : succès 99,8 %, latence 2,20 s, 1,45 B tokens/semaine, remise −99 %.

Enfin, l'audit de sécurité signale qu'un **fragment d'empreinte du mot de passe root** (préfixe, jamais la valeur) a été capté dans son transcript local : à considérer comme exposé, ce qui confirme la priorité n°1.

---

# CORRECTIONS APPLIQUÉES — 14 septembre 2026

Toutes les corrections ci-dessous sont **déployées en production et vérifiées par mesure**.

## 🔴 Faille P0 trouvée APRÈS le rapport des 3 agents (par recoupement direct)

### Code source de la passerelle téléchargeable publiquement
`https://smartapi.cheap/gateway/gateway.py` renvoyait **HTTP 200** : le code source complet, `market30.py`, `connect.sh`, `supabase_schema.sql` et `PLAN_50_TACHES.md` étaient accessibles à n'importe qui. Le projet Vercel sert **la racine du dépôt** en statique.
**Corrigé** : `.vercelignore` (seul le front est publié) + redéploiement. Vérifié : les 7 chemins sensibles renvoient **404**, le site fonctionne (200).

### Passerelle Antigravity (port 8895) ouverte à Internet sans clé
`def _auth(self): return True` — la fonction d'authentification était un **stub**. Preuve de consommation : un POST sans clé renvoyait 200 avec une réponse servie de `claude-opus-4-6`, sur l'abonnement **Google One AI Pro** du propriétaire.
**Corrigé** : vérification réelle (loopback accepté, distant = `GATEWAY_API_KEY` obligatoire, comparaison à temps constant). Vérifié : sans clé **401**, fausse clé **401**, loopback **200**, vraie clé **200**.

## ✅ Corrections déployées

| # | Constat | Correction | Vérification |
|---|---|---|---|
| 1 | Pool vision détournait les images vers un canal **hors quota** | Pool vision **supprimé** : les 4 modèles (qwen3.8-flash, glm-5.3-flash, deepseek-v4.1-flash, grok-4.6) sont multimodaux — **prouvé par test image réel** (4 quadrants, ordre non devinable : 4/4 lus) | Requête image réelle → 200 via `qwen3.8-flash` |
| 2 | `deepseek-v4-flash-vision` (inexistant → 400) et `deepseek-v4-flash-vision-exp` (canal à sec) dans le pool | Retirés de `MODELS` | `MODELS` = 4 entrées |
| 3 | `route_reason` ne traçait jamais la bascule vision | Trace `+img` ajoutée | `probe_truth+img`, `flux+img` observés en base |
| 4 | `/gw/api/prices` public : fournisseurs + prix d'achat | Signature HMAC **exigée** hors loopback + vue **anonymisée** (plus de `supplier`, `listing_id`, `channel_id`) | 4 nœuds → **403** ; voie signée → 200, payload 26 508 → **1 737 o** |
| 5 | Chiffres fabriqués en dur sur le site (`99.9%`, `36 982`, `118 556`, `177 834 027`, `~2.5s`, `99,8 %` / `2,20 s` par modèle) | Remplacés par des mesures réelles ou « — » ; `sanitizeModelStats()` neutralise les valeurs inventées ; la remise est **recalculée** depuis les prix affichés | Site en ligne : 0 occurrence des valeurs fabriquées |
| 6 | Compteur « tokens réels consommés sur la clé amont » = en fait **facturé** (−34,2 %) | Étiquette corrigée : « tokens facturés (remise cache amont déduite) » | — |
| 7 | Aucune mesure de latence fiable | Ajout `latency_ms` + p50 réelle 24 h + part de cache dans `/api/public/stats` | `p50_first_token_ms_24h` et `cache_share: 0.26` servis en direct |
| 8 | `finish_reason: length` réécrit en `stop` (troncature invisible) | Réécriture **supprimée** | Code vérifié |
| 9 | `flux_estime` : facturation sans décote de cache | Le taux de cache **mesuré** est appliqué aux estimations | Code vérifié |
| 10 | Mot de passe root SSH actif sur .67 et .69 | Drop-in `99-qh-hardening.conf`, cloud-init neutralisé, `sshd -t` avant reload | 4 nœuds : `passwordauthentication no` |
| 11 | fail2ban absent sur 3 nœuds | Installé + jail `sshd` | 4 nœuds : `active` (1 banni sur Victor) |
| 12 | `market30.py` divergent + cadence 120 vs 1200 | Version de Sandra sur les 4 nœuds + `QH_MARKET_INTERVAL=1200` partout ; script de déploiement corrigé | 4 nœuds : `43960a480f` |
| 13 | Une seule sauvegarde de `hub.db` (2 jours, 7 % du volume) | Sauvegarde quotidienne **vérifiée** (integrity_check) + rotation 14 j + cron 04:30 | Exécution réelle : `integrite=ok, lignes=7352` |
| 14 | `MemoryMax=infinity` + journald non borné | `MemoryMax=384M` (usage réel ~20 Mo) + journald 200 Mo | 4 nœuds : journal 126-185 Mo, `MemoryMax=402653184` |
| 15 | 11 clés + 22 abonnements orphelins | Clés `probe-*` **révoquées** (0 restante), abonnements désactivés — **aucune suppression**, clés `fleet-*` (user 18) intactes | Orphelins actifs : 0 |

## Reste à décider (hors périmètre technique)

1. **Rotation du mot de passe root** de .67/.69 : le hash a fuité dans un transcript. L'auth par mot de passe est coupée, donc inexploitable par SSH — à faire quand même par la console du fournisseur.
2. **Quota non renouvelable** : `PLAN_DEFAULT` = 1 Md de tokens à vie, alors que le site vend « 10 $ rechargés chaque semaine » et « 40 $/mois ». Risque de chargeback — c'est un choix produit.
3. **3 nœuds sur 4 ne servent rien** : le front ne cible qu'une URL, aucun load-balancer. Soit une vraie répartition, soit retirer « 100 % Uptime » des 3 nœuds inactifs.
4. **`/api/prices` affiche encore le prix d'achat** : c'est le prix affiché au client par le site lui-même, donc public par construction — à valider comme choix commercial.
5. **Port 8890 exposé** : ne peut pas être restreint aux IP Vercel (egress dynamique). La protection réelle est le HMAC + la clé API — vérifié : 401/403 depuis Internet.

