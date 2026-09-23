"""
Cliente HTTP autenticado contra la API de Mercado Libre: reintentos con backoff,
paginacion paralela y utilidades de concurrencia compartidas por el resto del backend.
"""
import random
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from ml_auth import get_user_token


def safe_int(raw, default: int, lo: int | None = None, hi: int | None = None) -> int:
    """Convierte un query param a int sin tirar 500 si el usuario manda basura."""
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return default
    if lo is not None:
        val = max(lo, val)
    if hi is not None:
        val = min(hi, val)
    return val


def ml_get(path: str, params: dict | None = None) -> dict:
    """
    GET autenticado a la API de ML con reintentos ante 429/5xx (backoff exponencial
    + jitter, respeta Retry-After si ML lo manda). Antes de esto, un 429 durante un
    analisis grande (cientos de llamadas en paralelo) tiraba abajo todo el request.
    """
    token = get_user_token()
    if not token:
        raise RuntimeError(f"Sin token. Autorizate primero en http://localhost:{config.PORT}/auth/setup")

    max_attempts = 4
    for attempt in range(max_attempts):
        r = requests.get(
            f"{config.ML_API}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code == 429 or r.status_code >= 500:
            if attempt == max_attempts - 1:
                r.raise_for_status()
            retry_after = r.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else (2 ** attempt)
            time.sleep(delay * (0.8 + random.random() * 0.4))  # jitter, evita reintentos sincronizados
            continue
        r.raise_for_status()
        return r.json()


def ml_get_pages(path: str, base_params: dict, page_size: int, max_records: int, max_offset: int = 950) -> list:
    """
    Pagina un endpoint de ML en paralelo (offset independientes = requests independientes).
    Primero pide la pagina 0 para conocer el total real, despues dispara el resto
    de las paginas necesarias con un pool de threads (las llamadas son I/O-bound,
    el GIL se libera durante el request, asi que el paralelismo si ayuda).
    """
    first = ml_get(path, {**base_params, "limit": page_size, "offset": 0})
    results = list(first.get("results", []))
    total   = first.get("paging", {}).get("total", len(results))

    target = min(total, max_records, max_offset + page_size)
    offsets = list(range(page_size, target, page_size))
    if not offsets:
        return results, total

    def fetch(offset):
        try:
            d = ml_get(path, {**base_params, "limit": page_size, "offset": offset})
            return d.get("results", [])
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, off) for off in offsets]
        for f in as_completed(futures):
            results.extend(f.result())

    return results, total


def map_parallel(fn, items, max_workers=8):
    """Aplica fn a cada item en paralelo y devuelve los resultados (descarta fallos individuales)."""
    out = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fn, it): it for it in items}
        for f in as_completed(futures):
            try:
                r = f.result()
                if r is not None:
                    out.append(r)
            except Exception:
                continue
    return out
