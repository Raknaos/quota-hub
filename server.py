import http.server
import socketserver
import json
import urllib.request
import urllib.error
import sqlite3
import hashlib
import time
import os
import sys

PORT = 3001
DB_PATH = os.path.join(os.path.dirname(__file__), "hub.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            balance REAL DEFAULT 10.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            key_val TEXT UNIQUE,
            name TEXT,
            spending_limit REAL DEFAULT 100.0,
            spent REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            key_id INTEGER,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            cost REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class HubHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_POST(self):
        url = self.path.split('?')[0]
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            payload = json.loads(body.decode('utf-8'))
        except Exception:
            payload = {}

        # 1. AUTH / INSCRIPTION
        if url == "/api/auth/register":
            username = payload.get("username", "").strip()
            password = payload.get("password", "").strip()
            if not username or len(password) < 4:
                return self.send_json({"error": "Nom d'utilisateur ou mot de passe invalide"}, 400)
            
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            try:
                cur.execute("INSERT INTO users (username, password_hash, balance) VALUES (?, ?, 10.0)", (username, pwd_hash))
                user_id = cur.lastrowid
                # Clé par défaut
                def_key = "sk-qh-" + hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()
                cur.execute("INSERT INTO api_keys (user_id, key_val, name) VALUES (?, ?, 'Clé Par Défaut')", (user_id, def_key))
                conn.commit()
                return self.send_json({
                    "status": "success",
                    "user": {"id": user_id, "username": username, "balance": 10.0},
                    "default_key": def_key
                })
            except sqlite3.IntegrityError:
                return self.send_json({"error": "Ce nom d'utilisateur est déjà utilisé"}, 409)
            finally:
                conn.close()

        # 2. AUTH / CONNEXION
        elif url == "/api/auth/login":
            username = payload.get("username", "").strip()
            password = payload.get("password", "").strip()
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT id, username, balance FROM users WHERE username=? AND password_hash=?", (username, pwd_hash))
            row = cur.fetchone()
            conn.close()
            if row:
                return self.send_json({
                    "status": "success",
                    "user": {"id": row[0], "username": row[1], "balance": row[2]}
                })
            return self.send_json({"error": "Identifiants incorrects"}, 401)

        # 3. GESTION DES CLÉS API
        elif url == "/api/keys/create":
            user_id = payload.get("user_id")
            name = payload.get("name", "Nouvelle Clé")
            limit = payload.get("limit", 100.0)
            if not user_id:
                return self.send_json({"error": "Non authentifié"}, 401)
            
            new_key = "sk-qh-" + hashlib.md5(f"{user_id}{name}{time.time()}".encode()).hexdigest()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("INSERT INTO api_keys (user_id, key_val, name, spending_limit) VALUES (?, ?, ?, ?)", (user_id, new_key, name, limit))
            conn.commit()
            conn.close()
            return self.send_json({"status": "success", "key": new_key, "name": name})

        # 4. PASSERELLE ROUTAGE /v1/chat/completions (COMPATIBLE OPENAI)
        elif url == "/v1/chat/completions":
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return self.send_json({"error": {"message": "Clé API manquante ou format invalide", "type": "auth_error"}}, 401)
            
            api_key = auth_header.replace("Bearer ", "").strip()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT k.id, u.id, u.balance, k.spending_limit, k.spent FROM api_keys k JOIN users u ON k.user_id = u.id WHERE k.key_val=?", (api_key,))
            auth_data = cur.fetchone()
            if not auth_data:
                conn.close()
                return self.send_json({"error": {"message": "Clé API non reconnue", "type": "auth_error"}}, 401)

            key_id, user_id, balance, limit, spent = auth_data
            if balance <= 0.001:
                conn.close()
                return self.send_json({"error": {"message": "Solde insuffisant. Veuillez recharger votre compte Quota.Hub.", "type": "insufficient_quota"}}, 402)

            model = payload.get("model", "gpt-5.6-luna")
            # Simulation complétion ou proxy amont
            content = f"Bonjour de Quota.Hub ! Requête traitée avec succès sur le modèle [{model}]. Latence passerelle : 84ms."
            prompt_tokens = len(str(payload.get("messages", []))) // 4
            completion_tokens = len(content) // 4
            cost = 0.000045 # Coût calculé

            # Déduction solde
            cur.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (cost, user_id))
            cur.execute("UPDATE api_keys SET spent = spent + ? WHERE id = ?", (cost, key_id))
            cur.execute("INSERT INTO usage_logs (user_id, key_id, model, prompt_tokens, completion_tokens, cost) VALUES (?, ?, ?, ?, ?, ?)",
                        (user_id, key_id, model, prompt_tokens, completion_tokens, cost))
            conn.commit()
            conn.close()

            return self.send_json({
                "id": f"chatcmpl-{int(time.time()*1000)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            })

        else:
            return self.send_json({"error": "Endpoint non trouvé"}, 404)

    def do_GET(self):
        url = self.path.split('?')[0]
        # API info utilisateur
        if url.startswith("/api/user/"):
            user_id = url.split("/")[-1]
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT username, balance FROM users WHERE id=?", (user_id,))
            user = cur.fetchone()
            if user:
                cur.execute("SELECT id, name, key_val, spending_limit, spent, created_at FROM api_keys WHERE user_id=?", (user_id,))
                keys = cur.fetchall()
                conn.close()
                return self.send_json({
                    "username": user[0],
                    "balance": user[1],
                    "keys": [{"id": k[0], "name": k[1], "key": k[2], "limit": k[3], "spent": k[4], "created_at": k[5]} for k in keys]
                })
            conn.close()
            return self.send_json({"error": "Utilisateur non trouvé"}, 404)

        # Fichiers statiques (index.html, app.css, app.js...)
        return super().do_GET()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), HubHandler) as httpd:
        print(f"[Quota.Hub Server] Prêt et en écoute sur http://127.0.0.1:{PORT}")
        sys.stdout.flush()
        httpd.serve_forever()
