"""Token de usuario de Mercado Libre: persistencia en archivo y refresh automatico."""
import json
import time
import requests

import config


def load_token() -> dict:
    try:
        return json.loads(config.TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_token(data: dict):
    config.TOKEN_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_user_token() -> str | None:
    """Retorna el access token valido; lo refresca automaticamente si expiro."""
    data       = load_token()
    token      = data.get("access_token")
    expires_at = data.get("expires_at", 0)

    if token and time.time() < expires_at - 300:
        return token

    refresh = data.get("refresh_token")
    if not refresh or not config.CLIENT_ID:
        return None

    try:
        r = requests.post(config.ML_TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "client_id":     config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "refresh_token": refresh,
        }, timeout=10)
        d = r.json()
        if "access_token" in d:
            data.update({
                "access_token":  d["access_token"],
                "refresh_token": d.get("refresh_token", refresh),
                "expires_at":    time.time() + d.get("expires_in", 21600),
            })
            save_token(data)
            print(f"[ML] Token renovado para {data.get('nickname', data.get('user_id', ''))}")
            return d["access_token"]
        else:
            print(f"[ML] Error al refrescar: {d}")
    except Exception as e:
        print(f"[ML] Excepcion al refrescar token: {e}")

    return None


def get_nickname() -> str:
    return load_token().get("nickname", "")


def get_owner_id():
    return load_token().get("user_id")
