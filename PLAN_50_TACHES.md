# Plan Directeur d'Exécution & Backlog des 50 Tâches — Quota.Hub (Hub API IA)

Date de référence : 07 Septembre 2026.
Projet : Création, fiabilisation et déploiement du hub de routage/revente API IA (thème Glass Quota/CutBG, catalogue économique, conformité et automatisation).

---

## 🏗️ Phase 1 : Architecture Frontend & Expérience Glass (Tâches 1 à 10)
- [x] **Tâche 1** : Créer l'architecture de fichiers du projet dans `C:\Users\bapti\Documents\Projets_Hermes\HubAPI_Quota\`. *(Terminé)*
- [x] **Tâche 2** : Définir la palette CSS exacte héritée de Quota Glass (dégradé 140° lilas/cyan, `--glass-alpha: 0.85`, glow orbs et Space Grotesk / DM Sans). *(Terminé)*
- [x] **Tâche 3** : Coder l'interface HTML complète avec 4 onglets : Catalogue Marché, Console de Clés, Portefeuille/Recharge, Playground interactif. *(Terminé)*
- [x] **Tâche 4** : Implémenter le bandeau défilant « Offres Vedettes » (Hot Deals) avec les remises instantanées calculées vs tarifs officiels. *(Terminé)*
- [x] **Tâche 5** : Développer le système de filtrage temps-réel (recherche plein texte, filtre par fournisseur OpenAI/DeepSeek/Anthropic/Google/Zhipu/Tencent/Alibaba). *(Terminé)*
- [x] **Tâche 6** : Implémenter le sélecteur de niveau de canal de routage (S-Grade, Éco Arbitrage, Direct Cloud). *(Terminé)*
- [x] **Tâche 7** : Intégrer le contrôleur d'opacité du verre en direct (slider 55% - 98% persistant dans le footer). *(Terminé)*
- [x] **Tâche 8** : Coder le modal de création de clé API avec génération cryptographique aléatoire (`sk-quota-live-...`). *(Terminé)*
- [x] **Tâche 9** : Concevoir le module de recharge à paliers avec remises dégressives (-2.5%, -5.34%, -7.5%, -10%). *(Terminé)*
- [x] **Tâche 10** : Créer le Playground live avec bascule de snippets cURL / Python / Node.js. *(Terminé)*

---

## ⚡ Phase 2 : Données Modèles & Normalisation Marché (Tâches 11 à 18)
- [x] **Tâche 11** : Intégrer le dataset exact des 12 modèles audités (GPT-6 Astra, GPT-5.6 Sol, GPT-5.6 Luna, DeepSeek V4 Flash, GLM-5.3, Gemini 3.8 Flash, Kimi K3, HY4, Qwen 3.8 Flash...). *(Terminé)*
- [ ] **Tâche 12** : Normaliser la tarification officielle par million de tokens (Input / Output) pour chaque modèle.
- [ ] **Tâche 13** : Paramétrer les coefficients de marge brute par famille (ex: 65-80% sur Luna/Astra, 25-35% sur Claude/Gemini).
- [ ] **Tâche 14** : Établir la matrice de latence P50 et taux de succès historique issue des benchmarks apiranking.
- [ ] **Tâche 15** : Documenter la politique de bascule automatique (Failover : Canal Principal S-Grade -> Canal Spot -> Canal Direct).
- [ ] **Tâche 16** : Ajouter un avertissement de transparence pour les modèles en canal Éco (pas de données personnelles EU).
- [ ] **Tâche 17** : Créer la table de correspondance des modèles de vision (DeepSeek Vision Exp, GPT-5.6 multimodal).
- [ ] **Tâche 18** : Mettre en place un script de validation du catalogue pour détecter les hausses de prix amont.

---

## 🛡️ Phase 3 : Conformité Juridique, RGPD & Démarches (Tâches 19 à 26)
- [ ] **Tâche 19** : Rédiger les Conditions Générales de Vente (CGV) adaptées à la vente de quota numérique prépayé en France.
- [ ] **Tâche 20** : Établir la Politique de Confidentialité RGPD distinguant l'offre Pro (hébergement EU) et l'offre Éco.
- [ ] **Tâche 21** : Rédiger la clause de renonciation expresse au droit de rétractation de 14 jours dès la première consommation API.
- [ ] **Tâche 22** : Préparer la notice de conformité de licence AGPL-3.0 pour la distribution du code source de la passerelle.
- [ ] **Tâche 23** : Documenter la procédure d'enregistrement micro-entreprise (Code APE 6201Z, franchise en base de TVA art. 293 B du CGI).
- [ ] **Tâche 24** : Mettre en place la clause d'exonération relative aux indisponibilités des fournisseurs de modèles sous-jacents.
- [ ] **Tâche 25** : Rédiger le contrat d'accord de traitement des données (DPA) standard pour les clients professionnels B2B.
- [ ] **Tâche 26** : Préparer la liste des exclusions territoriales (zones sous sanctions internationales OFAC/UE).

---

## ⚙️ Phase 4 : Passerelle Technique & Déploiement Backend (Tâches 27 à 36)
- [ ] **Tâche 27** : Cloner et auditer le dépôt New-API (QuantumNous) pour la passerelle de routage Go.
- [ ] **Tâche 28** : Configurer l'environnement Docker / Docker-Compose avec PostgreSQL et Redis pour la mise en cache.
- [ ] **Tâche 29** : Déployer une instance de test sur le VPS Lab (Victor .67 ou instance dédiée OVH).
- [ ] **Tâche 30** : Configurer Nginx en reverse-proxy HTTPS avec certificat SSL Let's Encrypt / Cloudflare.
- [ ] **Tâche 31** : Paramétrer le rate-limiting par IP et par clé d'accès (protection contre le déni de service et scraping).
- [ ] **Tâche 32** : Implémenter le middleware de vérification d'authenticité de modèle (canary test pour contrer la substitution).
- [ ] **Tâche 33** : Configurer la connexion aux canaux d'approvisionnement amont (LinkAI, UU API, Sail, Azure, Vertex).
- [ ] **Tâche 34** : Mettre en place le moteur de répartition de charge (Round-Robin pondéré par latence).
- [ ] **Tâche 35** : Implémenter le streaming SSE (Server-Sent Events) sans buffering pour un affichage fluide mot à mot.
- [ ] **Tâche 36** : Tester la compatibilité complète avec les SDK officiels `openai` (Python) et `openai` (Node.js/npm).

---

## 💳 Phase 5 : Rails de Paiement & Facturation Automatisée (Tâches 37 à 42)
- [ ] **Tâche 37** : Configurer un compte Stripe en mode Checkout avec produits de crédits prépayés ($10, $30, $50, $100, $300).
- [ ] **Tâche 38** : Activer Stripe Tax pour la gestion automatique de la TVA intracommunautaire et internationale.
- [ ] **Tâche 39** : Développer le webhook Stripe pour créditer instantanément le solde de l'utilisateur après confirmation bancaire.
- [ ] **Tâche 40** : Créer le module de génération automatique de reçus et factures conformes en PDF.
- [ ] **Tâche 41** : Intégrer une passerelle de paiement USDT/USDC (TRC20/Arbitrum) pour les développeurs hors-UE.
- [ ] **Tâche 42** : Mettre en place des alertes automatiques en cas de tentative de chargeback ou fraude bancaire.

---

## 📈 Phase 6 : Affiliation, Parrainage & Outils Croissance (Tâches 43 à 47)
- [ ] **Tâche 43** : Implémenter le système de liens de parrainage avec tracking de cookie 30 jours (`?ref=...`).
- [ ] **Tâche 44** : Développer le calcul automatique de commission (5.00% à vie sur toutes les recharges du filleul).
- [ ] **Tâche 45** : Créer le mécanisme de conversion en 1 clic des commissions vers le solde de tirage API.
- [ ] **Tâche 46** : Développer le système de coupons promotionnels (codes d'échange à usage unique ou partagé).
- [ ] **Tâche 47** : Concevoir l'extension Chrome (Manifest V3) pour monitorer son solde et tester ses prompts depuis le navigateur.

---

## 🚀 Phase 7 : Assurance Qualité, Tests Réels & Lancement (Tâches 48 à 50)
- [ ] **Tâche 48** : Exécuter un test de charge synthétique (100 requêtes parallèles sur GPT-5.6 Luna et DeepSeek Flash).
- [ ] **Tâche 49** : Valider le fonctionnement en conditions réelles avec Claude Code et Cursor sur un projet local.
- [ ] **Tâche 50** : Rédiger la documentation d'intégration complète et publier le portail en production.
