# Prix UnoRouter → site smartapi.cheap

Relevé **page par page sur https://unorouter.com/fr/modeles** le **14 septembre 2026**.
C'est la **référence unique** des prix de vente : la table `MODELS_DATA` d'`app.js`
doit être identique à ce fichier. Le prix barré = prix constructeur, « NOTRE » = prix UnoRouter.

| modèle | barré entrée | NOTRE entrée | barré sortie | NOTRE sortie |
|---|---|---|---|---|
| qwen3.8-flash        | $0.16  | $0.0024 | $0.47   | $0.0070 |
| glm-5.3-flash        | $0.15  | $0.06   | $0.50   | $0.20   |
| glm-5.3              | $2.80  | $2.80   | $8.96   | $8.96   |
| grok-4.6             | $2.00  | $0.05   | $6.00   | $0.15   |
| gemini-3.8-flash     | $0.75  | $0.08   | $3.75   | $0.39   |
| gemini-3.7-flash     | $0.75  | $0.09   | $3.75   | $0.47   |
| deepseek-v4.1-flash  | $0.09  | $0.09   | $0.27   | $0.27   |
| deepseek-v4-pro      | $1.74  | $1.08   | $3.48   | $2.16   |
| claude-fable-5.1     | $10.00 | $2.60   | $50.00  | $13.00  |
| claude-fable-5       | $10.00 | $2.50   | $50.00  | $12.50  |
| claude-opus-5        | $5.00  | $1.25   | $25.00  | $6.25   |
| claude-sonnet-5      | $2.00  | $0.42   | $10.00  | $2.10   |
| gpt-6-astra          | $10.00 | $1.50   | $50.00  | $7.50   |
| gpt-5.6-sol          | $4.00  | $1.00   | $20.00  | $5.00   |
| gpt-5.6-terra        | $2.00  | $0.40   | $12.00  | $2.40   |
| gpt-5.6-luna         | $0.20  | $0.04   | $1.20   | $0.24   |
| qwen3.8-max          | $2.00  | $1.85   | $6.00   | $5.54   |
| hy4-preview          | $0.83  | $0.04   | $2.50   | $0.13   |
| kimi-k3              | $4.90  | $4.90   | $24.50  | $24.50  |
| gpt-image-2.5-flare  | —      | —       | $0.04/img | $0.01/img |

## Points de vigilance

- **qwen3.8-flash n'existe pas dans le catalogue UnoRouter** (seuls `qwen3.8-max`
  et `qwen3.8-27b` y figurent). Sa ligne est conservée telle quelle — à confirmer
  si UnoRouter l'ajoute, ou si la référence change.
- Quand UnoRouter n'affiche **aucune réduction** (glm-5.3, deepseek-v4.1-flash,
  kimi-k3), le prix barré est égal au prix de vente : ne pas « inventer » un barré.
- L'API `https://unorouter.com/v1/models` répond **401** (clé requise) et
  `/api/v1/models` **404** : il n'y a pas d'endpoint public pour automatiser le
  relevé, il faut passer par les pages `/fr/modeles/<éditeur>/<modèle>`.
- Lightpanda est bloqué par Cloudflare sur ce site ; `web_extract` ou
  `curl -A "<UA navigateur>"` passent.
