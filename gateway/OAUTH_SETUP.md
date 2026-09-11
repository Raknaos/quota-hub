# Connexion Google / GitHub — configuration (aucun secret ici)

Le code est déployé. Tant que les identifiants OAuth ne sont pas renseignés,
les boutons affichent « connexion Google/GitHub non configurée » (503). Parcours :

## 1. Google (5 min)
1. https://console.cloud.google.com/apis/credentials
2. (Si première fois) **Écran de consentement** : type *Externe*, nom « Quota.Hub »,
   e-mail d'assistance, enregistrer. Laisser en mode test ou publier — les deux marchent.
3. **Créer des identifiants → ID client OAuth → Application Web**
   - Origine JavaScript autorisée : `https://smartapi.cheap`
   - **URI de redirection autorisé** : `https://smartapi.cheap/gw/api/auth/oauth/callback/google`
4. Récupérer **Client ID** + **Client secret**.

## 2. GitHub (2 min)
1. https://github.com/settings/developers → **New OAuth App**
   - Homepage URL : `https://smartapi.cheap`
   - **Authorization callback URL** : `https://smartapi.cheap/gw/api/auth/oauth/callback/github`
2. Récupérer **Client ID** + **Client secret**.

## 3. Renseigner sur la passerelle (.66) — saisie locale, jamais dans un chat
Ajouter dans `/opt/quota-hub/.env` :
```
QH_GOOGLE_CLIENT_ID=...
QH_GOOGLE_CLIENT_SECRET=...
QH_GITHUB_CLIENT_ID=...
QH_GITHUB_CLIENT_SECRET=...
```
puis `systemctl restart quota-hub`.

Optionnel (domaine custom plus tard) :
`QH_FRONT_URL=https://smartapi.cheap` et
`QH_OAUTH_CB_BASE=https://smartapi.cheap/gw/api/auth/oauth/callback/`.

## Comportement
- `GET /api/auth/oauth/start?provider=google|github` → `{url}` (state anti-CSRF, TTL 10 min, usage unique).
- `GET /api/auth/oauth/callback/<provider>?code=…&state=…` → 302 vers `/?oauth_session=…` ;
  le front stocke la session (sessionStorage) puis nettoie l'URL.
- Liaison : compte (provider, sub) existant → connecté ; sinon compte email existant
  (email **vérifié** du fournisseur) → **lié** ; sinon créé. Google exige `email_verified`.
- GitHub : scope `user:email`, email primaire vérifié requis (`/user/emails` sinon).
