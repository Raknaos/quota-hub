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
- [x] **Tâche 12** : Normaliser la tarification officielle par million de tokens (Input / Output) pour chaque modèle. *(Terminé)*
- [x] **Tâche 13** : Paramétrer les coefficients de marge brute par famille (ex: 65-80% sur Luna/Astra, 25-35% sur Claude/Gemini). *(Terminé)*
- [x] **Tâche 14** : Établir la matrice de latence P50 et taux de succès historique issue des benchmarks apiranking. *(Terminé)*
- [x] **Tâche 15** : Documenter la politique de bascule automatique (Failover : Canal Principal S-Grade -> Canal Spot -> Canal Direct). *(Terminé)*
- [x] **Tâche 16** : Ajouter un avertissement de transparence pour les modèles en canal Éco (pas de données personnelles EU). *(Terminé)*
- [x] **Tâche 17** : Créer la table de correspondance des modèles de vision (DeepSeek Vision Exp, GPT-5.6 multimodal). *(Terminé)*
- [x] **Tâche 18** : Mettre en place un script de validation du catalogue pour détecter les hausses de prix amont. *(Terminé)*

---

## 🛡️ Phase 3 : Conformité Juridique, RGPD & Démarches (Tâches 19 à 26)
- [x] **Tâche 19** : Rédiger les Conditions Générales de Vente (CGV) adaptées à la vente de quota numérique prépayé en France. *(Terminé)*
- [x] **Tâche 20** : Établir la Politique de Confidentialité RGPD distinguant l'offre Pro (hébergement EU) et l'offre Éco. *(Terminé)*
- [x] **Tâche 21** : Rédiger la clause de renonciation expresse au droit de rétractation de 14 jours dès la première consommation API. *(Terminé)*
- [x] **Tâche 22** : Préparer la notice de conformité de licence AGPL-3.0 pour la distribution du code source de la passerelle. *(Terminé)*
- [x] **Tâche 23** : Documenter la procédure d'enregistrement micro-entreprise (Code APE 6201Z, franchise en base de TVA art. 293 B du CGI). *(Terminé)*
- [x] **Tâche 24** : Mettre en place la clause d'exonération relative aux indisponibilités des fournisseurs de modèles sous-jacents. *(Terminé)*
- [x] **Tâche 25** : Rédiger le contrat d'accord de traitement des données (DPA) standard pour les clients professionnels B2B. *(Terminé)*
- [x] **Tâche 26** : Préparer la liste des exclusions territoriales (zones sous sanctions internationales OFAC/UE). *(Terminé)*

---

## ⚙️ Phase 4 : Passerelle Technique & Déploiement Backend (Tâches 27 à 36)
- [x] **Tâche 27** : Cloner et auditer le dépôt New-API (QuantumNous) pour la passerelle de routage Go / Python. *(Terminé)*
- [x] **Tâche 28** : Configurer l'environnement de base de données relationnelle SQLite / PostgreSQL Supabase. *(Terminé)*
- [x] **Tâche 29** : Déployer et vérifier le serveur de routage multi-nœuds en local et sur Vercel. *(Terminé)*
- [x] **Tâche 30** : Configurer la production HTTPS avec certificats SSL et distribution globale Edge. *(Terminé)*
- [x] **Tâche 31** : Paramétrer le rate-limiting par IP et par clé d'accès (protection contre le déni de service et scraping). *(Terminé)*
- [x] **Tâche 32** : Implémenter le middleware de vérification d'authenticité de modèle (canary test pour contrer la substitution). *(Terminé)*
- [x] **Tâche 33** : Configurer la connexion aux canaux d'approvisionnement amont (A6API, UnoRouter, LinkAI, Direct). *(Terminé)*
- [x] **Tâche 34** : Mettre en place le moteur de répartition de charge (Round-Robin pondéré par latence). *(Terminé)*
- [x] **Tâche 35** : Implémenter la compatibilité des complétions et des tokens de consommation. *(Terminé)*
- [x] **Tâche 36** : Tester la compatibilité complète avec les requêtes OpenAI SDK (Python et Node.js). *(Terminé)*

---

## 💳 Phase 5 : Rails de Paiement & Facturation Automatisée (Tâches 37 à 42)
- [x] **Tâche 37** : Configurer l'endpoint de Checkout `/api/pay/create-session` avec remises par palier ($10, $30, $50, $100, $300). *(Terminé)*
- [x] **Tâche 38** : Connecter la gestion des devises USD avec calcul de TVA et remises transparentes. *(Terminé)*
- [x] **Tâche 39** : Développer le système de validation et confirmation `/api/pay/confirm` pour créditer le solde sans rechargement de page. *(Terminé)*
- [x] **Tâche 40** : Créer le module de journalisation des paiements dans la table `payments`. *(Terminé)*
- [x] **Tâche 41** : Intégrer les options de paiement par Carte Bancaire, Crypto et Virement SEPA. *(Terminé)*
- [x] **Tâche 42** : Mettre en place la protection anti-double crédit sur les sessions de paiement. *(Terminé)*

---

## 📈 Phase 6 : Affiliation, Parrainage & Espace Membres (Tâches 43 à 47)
- [x] **Tâche 43** : Implémenter le système de liens de parrainage avec tracking de paramètre URL (`?ref=...`). *(Terminé)*
- [x] **Tâche 44** : Développer le calcul automatique de commission (5.00% à vie sur toutes les recharges du filleul). *(Terminé)*
- [x] **Tâche 45** : Créer le mécanisme de conversion en 1 clic des commissions vers le solde de tirage API. *(Terminé)*
- [x] **Tâche 46** : Développer le système de coupons promotionnels (codes d'échange à validation immédiate). *(Terminé)*
- [x] **Tâche 47** : Concevoir l'extension Chrome (Manifest V3) pour monitorer son solde et tester ses prompts depuis le navigateur. *(Terminé)*

---

## 🚀 Phase 7 : Assurance Qualité, Tests Réels & Lancement (Tâches 48 à 50)
- [x] **Tâche 48** : Exécuter des tests d'inscription, génération de clés et décompte de solde automatisés. *(Terminé)*
- [x] **Tâche 49** : Intégrer le système d'authentification complet (Inscription / Connexion) directement dans l'interface Glass. *(Terminé)*
- [x] **Tâche 50** : Déployer en continu sur GitHub et Vercel en production avec accès public immédiat. *(Terminé)*
