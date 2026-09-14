<!--
Sync Impact Report
==================
Version change: (scaffold) → 1.0.0
Bump rationale: ratification initiale — la constitution passe de gabarit vide à
  un document gouvernant, avec 5 principes et 3 sections. MAJOR non applicable
  (aucun principe antérieur), MINOR non applicable (première adoption).

Modified principles: aucun (gabarit → version initiale)

Added principles:
  - I. Prix de vente = liste UnoRouter à l'identique
  - II. Rien de visible côté client sans accord explicite
  - III. Vérité mesurée uniquement
  - IV. Secrets jamais exposés
  - V. Vérification après toute écriture externe

Added sections:
  - Contraintes techniques
  - Workflow de développement (Spec-Driven)
  - Gouvernance

Removed sections: aucun gabarit retiré (les exemples de commentaires ont été remplacés)

Follow-up TODOs: aucun placeholder différé. La ratification est datée du jour.
-->

# Constitution Quota.Hub

## Core Principles

### I. Prix de vente = liste UnoRouter à l'identique (NON NÉGOCIABLE)

Les prix affichés pour les modèles DOIVENT être identiques à ceux de la liste
UnoRouter (https://unorouter.com/fr/modeles), entrée et sortie, prix barré compris.

- La source de vérité est le **JSON-LD « pay as you go »** de chaque fiche modèle
  (`"description":"USD per 1M input tokens, pay as you go"`). Le prix mis en avant
  sur la page peut diverger fortement (écart constaté : 2,80 $ affiché contre
  0,05 $ réel) et NE DOIT PAS être utilisé comme référence.
- Un prix affiché NE DOIT JAMAIS être dérivé du coût d'achat amont. Le coût (canal
  A6API le moins cher) sert uniquement au calcul interne de marge.
- Le relevé de référence est `PRIX-UNOROUTER-REFERENCE.md` ; toute mise à jour de
  prix DOIT y être reportée dans le même changement.
- Quand UnoRouter n'affiche aucune réduction, il ne faut PAS inventer de prix barré.

Rationale : le tarif est un engagement commercial public. Un écart, même d'un seul
modèle, rompt la confiance et fausse la comparaison que l'utilisateur fait lui-même.

### II. Rien de visible côté client sans accord explicite

Aucune modification d'un élément visible pour le client — prix affichés, textes,
libellés, plans, promesses commerciales — ne peut être déployée sans accord explicite
de Baptiste.

- Séparer systématiquement la **valeur de référence** (table/DB/API) de la **valeur
  affichée** : une donnée peut alimenter un calcul interne sans être publiée.
- Toute proposition de changement visible DOIT être présentée sous forme de
  « avant → après » chiffré, modèle par modèle, avant déploiement.
- Une correction technique invisible (routage, cache, sécurité) n'exige pas d'accord
  préalable, mais DOIT être rapportée après coup avec sa preuve.

Rationale : un prix ou un texte public est vu par tous les clients ; l'agent n'est
pas le décideur commercial. Une correction techniquement juste reste un abus si elle
n'a pas été validée.

### III. Vérité mesurée uniquement (NON NÉGOCIABLE)

Tout chiffre publié — sur le site, dans un rapport ou dans une réponse — DOIT
provenir d'une mesure ou d'une sortie de commande réelle.

- Aucun chiffre « plausible », aucun ordre de grandeur inventé, aucune estimation
  présentée comme un fait. Une estimation DOIT être étiquetée comme telle.
- Les métriques affichées (fiabilité, latence, cache, marge) DOIVENT être alimentées
  par des colonnes réellement écrites en base, jamais par des constantes.
- Si une mesure est indisponible, la valeur affichée est « — » ou vide, jamais un
  substitut fabriqué.

Rationale : la crédibilité du produit repose sur l'exactitude de ses chiffres. Un
chiffre fabriqué détecté par un client détruit plus de valeur que son absence.

### IV. Secrets jamais exposés

Aucune clé, aucun jeton, aucun mot de passe ne doit transiter par le chat, un
prompt de modèle, un log, une capture, une URL ou un fichier de travail.

- Les secrets sont lus à l'exécution (variables d'environnement, `.env`, coffre) et
  utilisés sans jamais être imprimés ni recopiés dans une sortie.
- Une authentification interactive est réalisée par Baptiste dans une session dédiée ;
  jamais d'identifiant demandé ou transmis en clair.
- Un secret suspecté exposé DOIT être signalé et révoqué, même si la fuite est
  peu exploitable.

Rationale : une fuite est irréversible. Le coût de la rotation dépasse toujours le
gain de commodité d'un secret écrit quelque part.

### V. Vérification après toute écriture externe

Une modification n'est réputée faite qu'après relecture de l'état réel de la cible.

- Après un déploiement : relire la ressource servie (contenu en ligne, code HTTP,
  ligne en base), pas le journal du déploiement.
- Après une écriture en base ou une révocation : compter les lignes affectées et
  relire la valeur.
- Un déploiement multi-nœuds n'est terminé que lorsque TOUS les nœuds sont vérifiés
  individuellement (état du service + empreinte du fichier déployé).

Rationale : « la commande a réussi » n'est pas « le résultat est là ». Les écarts
entre intention et état réel sont la première source d'incidents silencieux.

## Contraintes techniques

- **Passerelle** : Python, bibliothèque standard uniquement ; pas de dépendance
  ajoutée sans justification écrite. Une seule base SQLite (`hub.db`) par nœud.
- **Flotte** : 4 nœuds VPS derrière une bascule automatique ; toute modification de
  code DOIT être déployée et vérifiée sur les 4, avec la même empreinte.
- **Front** : statique, servi par Vercel. Les données live (fiabilité, latence) se
  rafraîchissent ; les prix et textes commerciaux restent figés (principe I et II).
- **Langue** : le contenu destiné à l'utilisateur et les rapports sont en français.
- **Coût** : toute intégration payante exige un test à ~100 jetons avant lancement
  réel, et le coût facturé reporté est le coût réel, jamais une estimation.

## Workflow de développement (Spec-Driven)

Le projet suit Spec-Driven Development via Spec Kit.

- Séquence pour une fonctionnalité : `/speckit-constitution` → `/speckit-specify` →
  `/speckit-plan` → `/speckit-tasks` → `/speckit-implement` ; `/speckit-converge`
  pour aligner le code existant sur les artefacts.
- `/speckit-clarify`, `/speckit-analyze` et `/speckit-checklist` sont utilisés
  lorsque l'ambiguïté ou le risque le justifient.
- Un correctif de bug suit le cycle `assess → fix → test` plutôt qu'une correction
  directe non documentée.
- Cycle brownfield : les mises à jour de l'outillage (`.specify/`) restent séparées
  de l'évolution des artefacts de fonctionnalité (`specs/`).
- Avant tout commit : compilation/vérification syntaxique, puis vérification de
  l'état déployé (principe V). Le message de commit décrit le changement réel.

## Gouvernance

- La présente constitution prévaut sur toute autre pratique du projet.
- Amendement : proposition écrite (principe concerné, changement, justification),
  validation par Baptiste, puis mise à jour du fichier avec incrément de version.
- Versionnage sémantique : MAJOR pour un retrait ou une redéfinition incompatible
  de principe ; MINOR pour un principe ou une section ajouté ; PATCH pour une
  clarification sans changement de sens.
- Toute revue de code DOIT vérifier la conformité aux principes I à V ; une
  violation signalée DOIT être corrigée ou explicitement justifiée avant commit.
- La complexité ajoutée DOIT être justifiée ; la solution la plus simple qui
  respecte les principes est préférée.

**Version**: 1.0.0 | **Ratified**: 2026-09-14 | **Last Amended**: 2026-09-14
