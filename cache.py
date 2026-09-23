"""Cache en memoria con TTL, compartida por todos los modulos que llaman a la API de ML."""
import time

_cache: dict = {}

def cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < entry["ttl"]:
        return entry["val"]
    return None

def cache_set(key: str, val, ttl: int = 180):
    _cache[key] = {"val": val, "ts": time.time(), "ttl": ttl}

def clear():
    _cache.clear()
