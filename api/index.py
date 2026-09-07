import json
import urllib.request
import urllib.error
import os

A6API_BASE_URL = "https://a6api.com/v1"
A6API_KEY = os.environ.get("HERMES_CUSTOM_A6API_API_KEY", "")

RATES = {
    "gpt-5.6-luna": {"in": 0.00000008, "out": 0.00000035},
    "gpt-6-astra": {"in": 0.00000120, "out": 0.00000450},
    "gpt-5.6-sol": {"in": 0.00000060, "out": 0.00000220},
    "deepseek-v4-flash": {"in": 0.00000007, "out": 0.00000020},
    "glm-5.3": {"in": 0.00000090, "out": 0.00000280},
    "glm-5.3-flash": {"in": 0.00000006, "out": 0.00000018},
    "default": {"in": 0.00000050, "out": 0.00000150}
}

def calculate_cost(model, prompt_tokens, completion_tokens):
    rate = RATES.get(model, RATES["default"])
    return round((prompt_tokens * rate["in"]) + (completion_tokens * rate["out"]), 6)

def handler(event, context):
    method = event.get("httpMethod", "GET")
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            },
            "body": ""
        }

    headers_in = event.get("headers", {})
    auth_header = headers_in.get("authorization", "") or headers_in.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {
            "statusCode": 401,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": {"message": "Clé API Quota.Hub manquante (Authorization: Bearer sk-qh-...)", "type": "auth_error"}})
        }

    user_api_key = auth_header.replace("Bearer ", "").strip()
    try:
        body_str = event.get("body", "{}")
        payload = json.loads(body_str) if isinstance(body_str, str) else body_str
    except Exception:
        payload = {}

    model = payload.get("model", "gpt-5.6-luna")
    if not A6API_KEY:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": {"message": "Erreur serveur : Clé grossiste A6API non configurée.", "type": "configuration_error"}})
        }

    req = urllib.request.Request(
        f"{A6API_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {A6API_KEY}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            usage = data.get("usage", {})
            p_toks = usage.get("prompt_tokens", 0)
            c_toks = usage.get("completion_tokens", 0)
            cost = calculate_cost(model, p_toks, c_toks)
            
            data["quota_billing"] = {
                "billed_usd": cost,
                "model": model,
                "key_used": f"{user_api_key[:8]}...{user_api_key[-4:]}" if len(user_api_key) > 12 else "sk-qh-live"
            }

            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps(data)
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return {
            "statusCode": e.code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": err_body
        }
    except Exception as e:
        return {
            "statusCode": 504,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": {"message": str(e), "type": "gateway_timeout"}})
        }
