import json
import urllib.request
import urllib.error
import os

# Configuration upstream vers A6API
A6API_BASE_URL = "https://a6api.com/v1"
A6API_KEY = os.environ.get("HERMES_CUSTOM_A6API_API_KEY", "")

# Mapping et coefficients de majoration (marge brute Quota.Hub)
# 1 Token d'entrée = 0.00000008 $ (~0.08$ / 1M)
# 1 Token de sortie = 0.00000035 $ (~0.35$ / 1M)
RATES = {
    "gpt-5.6-luna": {"in": 0.00000008, "out": 0.00000035},
    "gpt-6-astra": {"in": 0.00000120, "out": 0.00000450},
    "gpt-5.6-sol": {"in": 0.00000060, "out": 0.00000220},
    "deepseek-v4-flash": {"in": 0.00000007, "out": 0.00000020},
    "glm-5.3": {"in": 0.00000090, "out": 0.00000280},
    "glm-5.3-flash": {"in": 0.00000006, "out": 0.00000018},
    "default": {"in": 0.00000050, "out": 0.00000150}
}

class handler:
    def __init__(self):
        pass

def calculate_cost(model, prompt_tokens, completion_tokens):
    rate = RATES.get(model, RATES["default"])
    return round((prompt_tokens * rate["in"]) + (completion_tokens * rate["out"]), 6)

def proxy_chat_completion(payload, user_api_key):
    if not A6API_KEY:
        return {
            "error": {
                "message": "Erreur serveur : Clé grossiste amont A6API non configurée.",
                "type": "configuration_error"
            }
        }, 500

    model = payload.get("model", "gpt-5.6-luna")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {A6API_KEY}"
    }

    req = urllib.request.Request(
        f"{A6API_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            usage = data.get("usage", {})
            p_toks = usage.get("prompt_tokens", 0)
            c_toks = usage.get("completion_tokens", 0)
            cost = calculate_cost(model, p_toks, c_toks)
            
            # Injection des métadonnées de facturation Quota.Hub dans la réponse
            data["quota_billing"] = {
                "billed_usd": cost,
                "model_rate": model,
                "provider": "a6api_wholesale"
            }
            return data, 200
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
            return err_json, e.code
        except Exception:
            return {"error": {"message": err_body, "type": "upstream_error"}}, e.code
    except Exception as e:
        return {"error": {"message": str(e), "type": "gateway_timeout"}}, 504
