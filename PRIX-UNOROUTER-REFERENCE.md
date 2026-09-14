# Prix UnoRouter → site smartapi.cheap

Référence unique des prix de vente. Relevé du **14 septembre 2026**.

## ⚠️ Méthode de relevé — à lire avant toute mise à jour

**Le prix qui fait foi est le JSON-LD de la fiche, pas le prix affiché sur la page.**
La fiche UnoRouter affiche un prix « tarification par groupe » qui peut être **très
différent** de celui de la liste : pour `glm-5.3` la page affichait `$2.80` alors que
le prix réel (liste + JSON-LD) est `$0.05`. S'y fier a produit 3 prix faux sur le site.

Bon relevé (sur `https://unorouter.com/fr/modeles/<éditeur>/<modèle>`) :

```bash
curl -s -A "<UA navigateur>" "https://unorouter.com/fr/modeles/zhipu/glm-5.3" \
  | grep -oE '"price":[0-9.]+,"priceCurrency":"USD","description":"[^"]+"'
# {"price":0.048,...,"description":"USD per 1M input tokens, pay as you go"}
# {"price":0.1508544,...,"description":"USD per 1M output tokens, pay as you go"}
```

C'est cette valeur qui apparaît dans la **liste** (`/fr/modeles`) — celle que voit
l'utilisateur. Un script de contrôle est dans `_prod/_uno_releve.py`.

## Tableau des prix

| modèle | barré entrée | NOTRE entrée | barré sortie | NOTRE sortie |
|---|---|---|---|---|
| qwen3.8-flash        | $0.16  | $0.0024 | $0.47   | $0.0070 |
| glm-5.3-flash        | $0.15  | $0.06   | $0.50   | $0.20   |
| glm-5.3              | $2.80  | $0.05   | $8.96   | $0.15   |
| grok-4.6             | $2.00  | $0.05   | $6.00   | $0.15   |
| gemini-3.8-flash     | $0.75  | $0.08   | $3.75   | $0.39   |
| gemini-3.7-flash     | $0.75  | $0.09   | $3.75   | $0.47   |
| deepseek-v4.1-flash  | $0.09  | $0.09   | $0.27   | $0.27   |
| deepseek-v4-pro      | $1.74  | $0.04   | $3.48   | $0.07   |
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
| kimi-k3              | $4.90  | $0.05   | $24.50  | $0.24   |
| gpt-image-2.5-flare  | —      | —       | $0.04/img | $0.01/img |

*(kimi-k3 : sortie = $0.24. Corrigé ici pour lisibilité, la valeur appliquée sur le
site est bien $0.05 / $0.24.)*

## Points de vigilance

- **qwen3.8-flash n'existe pas dans le catalogue UnoRouter** (seuls `qwen3.8-max`
  et `qwen3.8-27b` y figurent). Sa ligne est conservée telle quelle.
- Quand UnoRouter n'affiche **aucune réduction**, ne pas inventer de prix barré.
- L'API `https://unorouter.com/v1/models` répond **401** (clé requise) et
  `/api/v1/models` **404** : pas d'endpoint public, il faut passer par les pages.
- Lightpanda est bloqué par Cloudflare sur ce site ; `web_extract` ou
  `curl -A "<UA navigateur>"` passent.
