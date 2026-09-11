#!/usr/bin/env sh
# Smart API Cheap — configuration automatique de vos outils.
# Aucune clé n'est envoyée ni affichée : le script configure la base URL,
# vous collez votre clé (sk-sm-...) ensuite, dans le fichier de votre outil.
set -e

BASE="https://smartapi.cheap/v1"
MODEL="auto"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!  %s\033[0m\n' "$*"; }

say "Smart API Cheap — détection de vos outils"
echo "Base URL : $BASE   |   Modèle par défaut : $MODEL"

FOUND=0

# --- Claude Code -------------------------------------------------------------
if command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ]; then
  FOUND=1
  DIR="$HOME/.claude"
  mkdir -p "$DIR"
  SET="$DIR/settings.json"
  if [ -f "$SET" ]; then
    # injecte (ou remplace) ANTHROPIC_BASE_URL sans toucher au reste
    TMP="$SET.tmp"
    python3 - "$SET" "$BASE" <<'PY' 2>/dev/null || cp "$SET" "$TMP"
import json,sys
p,f=sys.argv[1],sys.argv[2]
try: d=json.load(open(p))
except Exception: d={}
d.setdefault("env",{})["ANTHROPIC_BASE_URL"]=f
json.dump(d,open(p,"w"),indent=2)
PY
    rm -f "$TMP"
  else
    printf '{ "env": { "ANTHROPIC_BASE_URL": "%s" } }\n' "$BASE" > "$SET"
  fi
  say "Claude Code : configuré ($SET)"
  warn "Ajoutez votre clé :  ANTHROPIC_AUTH_TOKEN : \"sk-sm-...\"  dans $SET"
fi

# --- Codex CLI ---------------------------------------------------------------
if command -v codex >/dev/null 2>&1 || [ -d "$HOME/.codex" ]; then
  FOUND=1
  mkdir -p "$HOME/.codex"
  CFG="$HOME/.codex/config.toml"
  touch "$CFG"
  if ! grep -q 'smartapi' "$CFG" 2>/dev/null; then
    cat >> "$CFG" <<EOF

[model_providers.smartapi]
name = "Smart API Cheap"
base_url = "$BASE"
env_key = "SMARTAPI_API_KEY"
wire_api = "chat"

[profiles.smartapi]
model = "$MODEL"
model_provider = "smartapi"
EOF
  fi
  say "Codex CLI : configuré ($CFG)"
  warn "Puis :  codex login --provider smartapi  et entrez votre clé sk-sm-..."
fi

# --- Cursor / OpenCode / OpenAI-compatibles ----------------------------------
if [ "$FOUND" -eq 0 ]; then
  say "Aucun outil détecté — configuration manuelle (compatible OpenAI) :"
  echo
  echo "  export OPENAI_BASE_URL=$BASE"
  echo "  export OPENAI_API_KEY=sk-sm-...   (votre clé)"
  echo "  export OPENAI_MODEL=$MODEL"
  echo
  echo "Ou dans .env :  OPENAI_BASE_URL=$BASE"
  warn "Votre clé se crée dans le tableau de bord Smart API Cheap."
else
  say "Terminé. Vérifiez : clé sk-sm-... + $BASE"
fi