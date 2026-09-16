"""
ML Insights - Backend Flask
Token de usuario via OAuth con httpbin como redirect (sin necesitar HTTPS propio).
"""
from flask import Flask, render_template, jsonify, request, redirect
import requests, os, time, json, re, random, sqlite3, unicodedata, statistics
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
# Sin esto, Flask compila templates/index.html una sola vez y lo cachea en memoria
# mientras el proceso viva (con debug=False, que es el modo normal de uso). Los
# archivos de /static SI se releen del disco en cada request sin necesitar esto,
# asi que un cambio de HTML sin reiniciar el proceso podia quedar desincronizado
# del JS/CSS ya actualizados -> errores como "elemento no encontrado" en el navegador
# aunque los 3 archivos on disco fueran consistentes entre si. Verificado 2026-09-16:
# el proceso llevaba corriendo desde el dia anterior con templates/index.html viejo.
app.jinja_env.auto_reload = True

# --- Credenciales ML ------------------------------------------------
CLIENT_ID     = os.environ.get("ML_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET", "")
REDIRECT_URI  = "https://httpbin.org/get"   # ML redirige aca; el codigo queda visible en JSON

ML_AUTH_URL  = "https://auth.mercadolibre.com.ar/authorization"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ML_API       = "https://api.mercadolibre.com"
TOKEN_FILE   = Path(".ml_token.json")

# El debugger de Werkzeug (activado por debug=True) expone una consola interactiva
# con ejecucion de codigo remoto ante un traceback -- default apagado, se prende
# a proposito con FLASK_DEBUG=1 (ver checklist de seguridad del DPP de ML).
DEBUG = os.environ.get("FLASK_DEBUG", "") == "1"

def _safe_int(raw, default: int, lo: int | None = None, hi: int | None = None) -> int:
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

# --- Cache en memoria -----------------------------------------------
_cache: dict = {}

def cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < entry["ttl"]:
        return entry["val"]
    return None

def cache_set(key: str, val, ttl: int = 180):
    _cache[key] = {"val": val, "ts": time.time(), "ttl": ttl}

# --- Historial de precios (SQLite local) -----------------------------
# Guarda una foto por producto cada vez que se corre un analisis de rubro, para
# poder mostrar tendencia de precio/competencia en el tiempo. No agrega ninguna
# llamada extra a la API de ML: reusa datos que /api/analysis ya trajo.
# NO incluye sold_quantity: ese dato no esta disponible para publicaciones de
# terceros via API (solo scrapeando el HTML publico, algo que este proyecto
# descarta explicitamente por riesgo a la cuenta y a los Terminos de Servicio).
DB_PATH = Path("data/mercadata.db")

def ensure_schema():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        product_id TEXT NOT NULL,
        name TEXT,
        brand TEXT,
        ts_utc TEXT NOT NULL,
        sellers_count INTEGER,
        min_price REAL,
        avg_price REAL,
        max_price REAL,
        UNIQUE(product_id, ts_utc)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_snapshots_product_ts ON snapshots(product_id, ts_utc)")

    # Quien ofrecia cada producto y a que precio en cada corrida. No es un dato nuevo
    # de ML: es la misma info de /products/{id}/items que /api/analysis ya trae, pero
    # persistida con identidad de vendedor para poder calcular despues "cuantas veces
    # este vendedor aparecio como el mas barato" a lo largo del tiempo -el unico proxy
    # de fortaleza de un competidor que la API permite sin certificacion DPP, ya que
    # sold_quantity de publicaciones de terceros esta bloqueado (ver PROJECT_SPEC.md 7.6)-.
    conn.execute("""CREATE TABLE IF NOT EXISTS seller_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        product_id TEXT NOT NULL,
        ts_utc TEXT NOT NULL,
        nickname TEXT NOT NULL,
        price REAL,
        rank INTEGER,
        is_leader INTEGER,
        reputation TEXT,
        UNIQUE(product_id, ts_utc, nickname)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_seller_snapshots_nick_ts ON seller_snapshots(nickname, ts_utc)")
    conn.commit()
    conn.close()

def _snapshot_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def save_snapshots(query: str, rows: list, ts: str):
    """Inserta una fila de historial por producto. Nunca debe tirar abajo /api/analysis."""
    if not rows:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.executemany(
            """INSERT OR IGNORE INTO snapshots
               (query, product_id, name, brand, ts_utc, sellers_count, min_price, avg_price, max_price)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [(query, r["id"], r.get("name"), r.get("brand"), ts,
              r.get("sellers"), r.get("min_price"), r.get("avg_price"), r.get("max_price")) for r in rows],
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[snapshots] no se pudo guardar historial: {e}")

def save_seller_snapshots(query: str, detailed_rows: list, ts: str):
    """Inserta, por producto, el ranking de vendedores por precio de esa corrida."""
    entries = []
    for row in detailed_rows:
        ranked = sorted(
            (s for s in (row.get("sellers_detail") or []) if s.get("nickname")),
            key=lambda s: s["price"] if s.get("price") is not None else float("inf"),
        )
        for rank, s in enumerate(ranked, start=1):
            entries.append((
                query, row["id"], ts, s["nickname"], s.get("price"),
                rank, 1 if rank == 1 else 0, s.get("reputation"),
            ))
    if not entries:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.executemany(
            """INSERT OR IGNORE INTO seller_snapshots
               (query, product_id, ts_utc, nickname, price, rank, is_leader, reputation)
               VALUES (?,?,?,?,?,?,?,?)""",
            entries,
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[seller_snapshots] no se pudo guardar historial: {e}")

def get_product_timeseries(product_id: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT ts_utc, sellers_count, min_price, avg_price, max_price FROM snapshots "
        "WHERE product_id = ? ORDER BY ts_utc ASC", (product_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_seller_timeseries(nickname: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """SELECT ts_utc, COUNT(*) as appearances, SUM(is_leader) as wins
           FROM seller_snapshots WHERE nickname = ? GROUP BY ts_utc ORDER BY ts_utc ASC""",
        (nickname,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_price_alerts(query: str, limit: int = 30) -> list:
    """Compara, por producto, el ultimo snapshot guardado contra el anterior y
    devuelve los que se movieron de precio minimo. Es historial propio (no un dato
    nuevo de ML): se arma con lo que /api/analysis ya vino guardando con el tiempo,
    asi que recien tiene datos utiles despues de correr el mismo rubro 2+ veces."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    sql = "SELECT product_id, name, brand, ts_utc, min_price, sellers_count FROM snapshots"
    params: tuple = ()
    if query:
        sql += " WHERE query = ?"
        params = (query,)
    sql += " ORDER BY product_id, ts_utc DESC"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()

    by_product: dict[str, list] = {}
    for r in rows:
        by_product.setdefault(r["product_id"], []).append(r)

    alerts = []
    for pid, snaps in by_product.items():
        if len(snaps) < 2:
            continue
        latest, prev = snaps[0], snaps[1]
        if not latest["min_price"] or not prev["min_price"] or latest["ts_utc"] == prev["ts_utc"]:
            continue
        pct = round(((latest["min_price"] - prev["min_price"]) / prev["min_price"]) * 100, 1)
        if abs(pct) < 1:  # variacion menor a redondeo/ruido, no vale la pena mostrarla
            continue
        alerts.append({
            "product_id": pid, "name": latest["name"], "brand": latest["brand"],
            "old_price": prev["min_price"], "new_price": latest["min_price"],
            "pct_change": pct, "ts_utc": latest["ts_utc"], "sellers_count": latest["sellers_count"],
        })
    alerts.sort(key=lambda a: a["pct_change"])  # caidas de precio (mas negativo) primero
    return alerts[:limit]

# --- Token de usuario (persistido en archivo) -----------------------
def load_token() -> dict:
    try:
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_token(data: dict):
    TOKEN_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

PORT = int(os.environ.get("PORT", 5050))

def get_user_token() -> str | None:
    """Retorna el access token valido; lo refresca automaticamente si expiro."""
    data       = load_token()
    token      = data.get("access_token")
    expires_at = data.get("expires_at", 0)

    if token and time.time() < expires_at - 300:
        return token

    refresh = data.get("refresh_token")
    if not refresh or not CLIENT_ID:
        return None

    try:
        r = requests.post(ML_TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
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

def ml_get(path: str, params: dict | None = None) -> dict:
    """
    GET autenticado a la API de ML con reintentos ante 429/5xx (backoff exponencial
    + jitter, respeta Retry-After si ML lo manda). Antes de esto, un 429 durante un
    analisis grande (cientos de llamadas en paralelo) tiraba abajo todo el request.
    """
    token = get_user_token()
    if not token:
        raise RuntimeError(f"Sin token. Autorizate primero en http://localhost:{PORT}/auth/setup")

    max_attempts = 4
    for attempt in range(max_attempts):
        r = requests.get(
            f"{ML_API}{path}",
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

# --- Rutas ----------------------------------------------------------
@app.route("/")
def index():
    token = get_user_token()
    return render_template(
        "index.html",
        configured = bool(CLIENT_ID),
        token_ok   = bool(token),
        nickname   = get_nickname(),
    )

# --- Setup / Auth ---------------------------------------------------
@app.route("/auth/setup")
def auth_setup():
    """Pagina de configuracion: genera el link de auth y acepta el codigo."""
    auth_url = ""
    if CLIENT_ID:
        params = {
            "response_type": "code",
            "client_id":     CLIENT_ID,
            "redirect_uri":  REDIRECT_URI,
        }
        auth_url = f"{ML_AUTH_URL}?{urlencode(params)}"

    token_data = load_token()
    error      = request.args.get("error", "")
    return render_template(
        "setup.html",
        configured   = bool(CLIENT_ID),
        auth_url     = auth_url,
        already_auth = bool(token_data.get("access_token")),
        nickname     = token_data.get("nickname", ""),
        error        = error,
    )

@app.route("/auth/exchange", methods=["POST"])
def auth_exchange():
    """Recibe el codigo (pegado por el usuario) y lo intercambia por un token."""
    raw  = request.form.get("code", "").strip()
    code = raw

    # Acepta la URL completa de httpbin
    if raw.startswith("http"):
        try:
            qs   = parse_qs(urlparse(raw).query)
            code = qs.get("code", [raw])[0]
        except Exception:
            pass

    # Acepta el JSON de httpbin pegado directamente
    if raw.startswith("{"):
        try:
            j    = json.loads(raw)
            code = j.get("args", {}).get("code", raw)
        except Exception:
            pass

    if not code or not CLIENT_ID:
        return redirect("/auth/setup?error=Falto+el+codigo")

    try:
        r = requests.post(ML_TOKEN_URL, data={
            "grant_type":    "authorization_code",
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
        }, timeout=10)
        d = r.json()
    except Exception as e:
        return redirect(f"/auth/setup?error={e}")

    if "access_token" not in d:
        msg = d.get("message", d.get("error", "unknown"))
        return redirect(f"/auth/setup?error={msg}")

    # Obtener nickname
    nickname = ""
    try:
        u = requests.get(
            f"{ML_API}/users/{d['user_id']}",
            headers={"Authorization": f"Bearer {d['access_token']}"},
            timeout=10,
        ).json()
        nickname = u.get("nickname", str(d.get("user_id", "")))
    except Exception:
        nickname = str(d.get("user_id", ""))

    save_token({
        "access_token":  d["access_token"],
        "refresh_token": d.get("refresh_token", ""),
        "expires_at":    time.time() + d.get("expires_in", 21600),
        "user_id":       d.get("user_id", ""),
        "nickname":      nickname,
    })
    print(f"[ML] Token guardado para {nickname}")
    return redirect("/")

@app.route("/auth/logout")
def auth_logout():
    TOKEN_FILE.unlink(missing_ok=True)
    _cache.clear()
    return redirect("/auth/setup")

# --- API endpoints --------------------------------------------------
@app.route("/api/status")
def api_status():
    token = get_user_token()
    return jsonify({
        "connected":  bool(token),
        "configured": bool(CLIENT_ID),
        "nickname":   get_nickname(),
    })

@app.route("/api/products")
def api_products():
    """
    Busca productos en el catalogo oficial de ML.
    Reemplaza a /sites/MLA/search, que esta bloqueado para apps no certificadas.

    ?category=MLA... : IMPORTANTE. Sin esto, "q" es una busqueda de texto libre
    sobre TODO el catalogo de Mercado Libre, y terminos de 1-2 palabras (incluso
    especificos como "transformador" o "motor electrico") matchean productos de
    rubros totalmente ajenos (juguetes, papeleria, herramientas mecanicas) que
    contienen esas palabras en su titulo/descripcion por casualidad. Pasar la
    categoria de ML restringe la busqueda a ese rubro y elimina ese ruido.

    ?domain=MLA-CIRCUIT_BREAKERS : opcional, mas preciso todavia que category.
    Verificado empiricamente (2026-09-15): algunas categorias de ML agrupan
    dominios de producto muy distintos (ej. MLA411423 "Tableros" trae tanto
    gabinetes electricos reales como "tableros para vehiculos" bajo el mismo
    texto de busqueda). El dominio filtra por el tipo de producto que ML ya
    clasifico internamente, no por texto, asi que elimina ese cruce.

    limit/offset: ML valida esto del lado del servidor. Verificado 2026-09-16:
    'limit' maximo es 100 y 'offset' maximo es 100 (antes se media un techo de
    offset ~1000, medido 2026-09-15 -ML lo bajo desde entonces-). Pedir mas de
    eso tira 400 Bad Request, no importa cuanto se espere. Con ambos al maximo,
    200 productos de catalogo es el techo real por busqueda (ver PROJECT_SPEC.md
    5.8). hi=100 aca refleja ese limite real, no una eleccion arbitraria nuestra.
    """
    q        = request.args.get("q", "").strip() or "material electrico"
    category = request.args.get("category", "").strip()
    domain   = request.args.get("domain", "").strip()
    limit    = _safe_int(request.args.get("limit"), 30, lo=1, hi=100)
    offset   = _safe_int(request.args.get("offset"), 0, lo=0, hi=100)

    key    = f"products:{q}:{category}:{domain}:{limit}:{offset}"
    cached = cache_get(key)
    if cached:
        return jsonify(cached)

    try:
        params = {"status": "active", "site_id": "MLA", "q": q, "limit": limit, "offset": offset}
        if category:
            params["category"] = category
        if domain:
            params["domain_id"] = domain
        data = ml_get("/products/search", params)
        raw_results = sorted(data.get("results", []), key=_offer_likelihood, reverse=True)
        result = {
            "total":   data.get("paging", {}).get("total", 0),
            "results": [_slim_product(p) for p in raw_results],
        }
        cache_set(key, result, ttl=300)
        return jsonify(result)
    except requests.HTTPError as e:
        code = e.response.status_code
        if code in (401, 403):
            return jsonify({"error": "Sesion expirada. Ir a /auth/setup para reautorizarte.", "results": []}), code
        if code == 429:
            return jsonify({"error": "Limite de la API alcanzado. Espera unos segundos.", "results": []}), 429
        return jsonify({"error": f"Error HTTP {code}", "results": []}), code
    except RuntimeError as e:
        return jsonify({"error": str(e), "results": []}), 401
    except requests.Timeout:
        return jsonify({"error": "La API de ML no respondio a tiempo.", "results": []}), 504
    except Exception as e:
        return jsonify({"error": str(e), "results": []}), 500

def _attr(product, attr_id):
    for a in product.get("attributes", []) or []:
        if a.get("id") == attr_id:
            return a.get("value_name")
    return None

def _offer_likelihood(p) -> int:
    """
    El catalogo de ML Argentina esta lleno de fichas importadas de otros sitios
    (Brasil, Mexico, Chile) que nadie vende aca. Verificado 2026-09-16 sobre 120
    productos reales: con parent_id, 64% tenia vendedores (vs 8% sin); con
    authority_types COMMUNITY, 34% (vs 3% solo INTERNAL). Ordenar cada pagina por
    esto hace que el filtro de "productos con vendedores" encuentre resultados en
    muchas menos llamadas. Es solo un orden: no descarta nada.
    """
    return (2 if p.get("parent_id") else 0) + (1 if "COMMUNITY" in (p.get("authority_types") or []) else 0)

def _slim_product(p):
    """Reduce el payload de un producto de catalogo a lo que consume el frontend."""
    return {
        "id":        p.get("id"),
        "name":      p.get("name"),
        "domain_id": p.get("domain_id"),
        "brand":     _attr(p, "BRAND"),
        "model":     _attr(p, "MODEL"),
        "thumbnail": (p.get("pictures") or [{}])[0].get("url") if p.get("pictures") else None,
    }

def _offer_summary(product_id: str, max_items: int = 50) -> dict:
    """
    Resumen barato de las ofertas de un producto (sin consultar /users de cada
    vendedor): cantidad, rango de precio e item_ids. Sirve para ranquear muchos
    candidatos rapido y para reconocer una publicacion puntual por su item_id.
    """
    key = f"offsum:{product_id}:{max_items}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    try:
        items, total = ml_get_pages(f"/products/{product_id}/items", {}, page_size=50, max_records=max_items)
    except requests.HTTPError:
        items, total = [], 0
    prices = [i.get("price") for i in items if i.get("price")]
    result = {
        "total":     total or 0,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "item_ids":  [i.get("item_id") for i in items if i.get("item_id")],
        "free_shipping": sum(1 for i in items if (i.get("shipping") or {}).get("free_shipping")),
        "official_stores": sum(1 for i in items if i.get("official_store_id")),
        "sampled":   len(items),
    }
    cache_set(key, result, ttl=300)
    return result

def _offers_for_product(product_id: str, light: bool = False) -> dict:
    """
    Nucleo del analisis de competencia: todos los vendedores que ofrecen un
    producto de catalogo, con precio y reputacion. Usado tanto por
    /api/products/<id>/offers como por /api/lookup (analizar una publicacion).

    ?light=1 : se salta unicamente la consulta de buy_box_winner (un llamado extra
    a /products/{id} que solo se usa para marcar el ganador de la pagina en el
    panel de detalle). Nickname y reputacion de vendedores SIEMPRE se calculan,
    porque la tabla principal los muestra (vendedor lider, reputacion).
    """
    key    = f"offers:{product_id}:{'light' if light else 'full'}"
    cached = cache_get(key)
    if cached:
        return cached

    # Hasta 200 ofertas (no solo la primera pagina de 50): los productos mas
    # disputados superan los 50 vendedores y la publicacion analizada podia quedar afuera.
    items, total_offers = ml_get_pages(f"/products/{product_id}/items", {}, page_size=50, max_records=200)

    # buy_box_winner: quien gana la pagina segun el algoritmo de ML (no siempre
    # coincide con el precio mas bajo: pesa tambien reputacion y logistica)
    buy_box_item_id = None
    if not light:
        try:
            detail = ml_get(f"/products/{product_id}")
            buy_box_item_id = detail.get("buy_box_winner")
        except Exception:
            pass

    # Enriquecer con datos del vendedor (nickname, reputacion, ventas historicas), en paralelo
    unique_seller_ids = list({it.get("seller_id") for it in items if it.get("seller_id")})
    seller_infos = map_parallel(lambda sid: (sid, _get_seller(sid)), unique_seller_ids, max_workers=8)
    sellers = dict(seller_infos)

    offers = []
    for it in items:
        s = sellers.get(it.get("seller_id"), {})
        offers.append({
            "item_id":      it.get("item_id"),
            "seller_id":    it.get("seller_id"),
            "nickname":     s.get("nickname"),
            "reputation":   s.get("reputation"),
            "seller_sales": s.get("sales"),
            "price":         it.get("price"),
            "original_price": it.get("original_price"),
            "listing_type":  it.get("listing_type_id"),
            "free_shipping": (it.get("shipping") or {}).get("free_shipping"),
            "official_store": bool(it.get("official_store_id")),
            "city":          ((it.get("seller_address") or {}).get("city") or {}).get("name"),
            "state":         ((it.get("seller_address") or {}).get("state") or {}).get("name"),
            "permalink":     f"https://articulo.mercadolibre.com.ar/{str(it.get('item_id','')).replace('MLA', 'MLA-')}",
            "buy_box_winner": it.get("item_id") == buy_box_item_id,
        })

    offers.sort(key=lambda o: o.get("price") or float("inf"))
    result = {
        "total": total_offers or len(offers),
        "offers": offers,
        "buy_box_winner_item": buy_box_item_id,
    }
    cache_set(key, result, ttl=300)
    return result

@app.route("/api/products/<product_id>/offers")
def api_product_offers(product_id):
    light = request.args.get("light", "").lower() in ("1", "true")
    try:
        return jsonify(_offers_for_product(product_id, light=light))
    except requests.HTTPError as e:
        return jsonify({"error": f"Error HTTP {e.response.status_code}", "offers": []}), e.response.status_code
    except RuntimeError as e:
        return jsonify({"error": str(e), "offers": []}), 401
    except Exception as e:
        return jsonify({"error": str(e), "offers": []}), 500

def _get_seller(seller_id):
    key    = f"seller:{seller_id}"
    cached = cache_get(key)
    if cached:
        return cached
    try:
        u   = ml_get(f"/users/{seller_id}")
        rep = u.get("seller_reputation") or {}
        info = {
            "nickname":   u.get("nickname"),
            "reputation": rep.get("level_id"),
            "sales":      (rep.get("transactions") or {}).get("total"),
        }
        cache_set(key, info, ttl=1800)
        return info
    except Exception:
        return {}

@app.route("/api/seller/<int:seller_id>")
def api_seller(seller_id):
    return jsonify(_get_seller(seller_id))

_ITEM_ID_RE    = re.compile(r"(MLA-?\d{6,})", re.IGNORECASE)
_PRODUCT_PAGE_RE = re.compile(r"/p/(MLA\d{6,})", re.IGNORECASE)
_ITEM_PARAM_RE   = re.compile(r"item_id[:=](MLA\d{6,})", re.IGNORECASE)
_MLA_PREFIX_RE   = re.compile(r"^MLA-?\d+-?", re.IGNORECASE)
_MLA_ONLY_RE     = re.compile(r"MLA[A-Z]?-?\d+", re.IGNORECASE)

def _parse_item_id(raw: str) -> str | None:
    """Acepta un link de articulo.mercadolibre.com.ar o el codigo pelado (MLA123456789)."""
    m = _ITEM_ID_RE.search((raw or "").strip())
    if not m:
        return None
    return m.group(1).upper().replace("-", "")

def _parse_slug_text(raw: str) -> str | None:
    """
    Extrae las palabras del titulo desde la URL de una publicacion. ML usa varios
    formatos de link, el slug del titulo puede ir DESPUES del codigo
    (articulo.mercadolibre.../MLA-2072848515-taladro-percutor-daewoo-_JM) o ANTES
    (mercadolibre.com.ar/protector-tension-digital-.../up/MLAU.../?item_id=...).
    En vez de asumir un orden fijo, se toma el segmento del path con mas palabras
    separadas por guion (descartando los que son solo un codigo MLA/MLAU), que en
    la practica siempre resulta ser el titulo. Sirve para identificar publicaciones
    de OTROS vendedores, cuyo detalle no podemos consultar por API (ver mas abajo).
    """
    path = re.split(r"[?#]", (raw or "").strip(), maxsplit=1)[0]
    best_words: list = []
    for seg in path.split("/"):
        seg = _MLA_PREFIX_RE.sub("", seg)  # saca un "MLA-2072848515-" pegado adelante, si esta
        if not seg or _MLA_ONLY_RE.fullmatch(seg):
            continue
        words = [w for w in seg.split("-") if w and not w.startswith("_")]
        if len(words) > len(best_words):
            best_words = words
    if len(best_words) < 3:
        return None
    return " ".join(best_words).strip() or None

def _parse_catalog_product_id(raw: str) -> str | None:
    """
    Detecta links a la PAGINA DE PRODUCTO de catalogo (.../p/MLA50685109), distinta
    de una publicacion puntual. Es ambigua con _parse_item_id: un link de pagina de
    producto suele traer ADEMAS un item_id de oferta puntual en query params
    (?...item_id:MLA...), y ese SI es una publicacion real - por eso se resuelven
    por separado en vez de asumir que el primer codigo MLA que aparece es el item.
    """
    m = _PRODUCT_PAGE_RE.search((raw or "").strip())
    return m.group(1).upper() if m else None

def _parse_item_id_param(raw: str) -> str | None:
    """Extrae el item_id de oferta puntual de una URL de pagina de producto de catalogo."""
    m = _ITEM_PARAM_RE.search((raw or "").strip())
    return m.group(1).upper() if m else None

_GENERIC_STOPWORDS = {
    "de", "para", "con", "sin", "la", "el", "los", "las", "un", "una", "unos", "unas",
    "y", "o", "en", "por", "del", "al", "the", "and", "or", "mas", "jm", "mla", "color",
}

def _norm(text: str) -> str:
    """Minusculas y sin acentos: 'Térmica' y 'termica' tienen que ser la misma palabra."""
    return "".join(c for c in unicodedata.normalize("NFD", (text or "").lower()) if unicodedata.category(c) != "Mn")

def _tokenize(text: str) -> list:
    # Tokens con digitos se conservan aunque sean cortos ("9w", "25a", "2x25"): son
    # justamente los que distinguen un producto de otro del mismo tipo.
    # El punto decimal se conserva ("2.5mm" no puede partirse en "2" + "5mm", que matchearia "1.5mm").
    words = (w.strip(".") for w in re.split(r"[^a-z0-9.]+", _norm(text).replace(",", ".")))
    return [w for w in words
            if w not in _GENERIC_STOPWORDS and (len(w) > 2 or (len(w) == 2 and any(c.isdigit() for c in w)))]

def _code_tokens(tokens) -> set:
    """Codigos de modelo tipo 'a9r91225' o 'lc1d18': letras+digitos y largos. Un match es casi definitivo."""
    return {t for t in tokens if len(t) >= 5 and any(c.isdigit() for c in t) and any(c.isalpha() for c in t)}

def _rank_by_similarity(query_text: str, candidates_raw: list) -> list:
    """
    Similitud ponderada por rareza de palabra (mini tf-idf) en vez de simple overlap:
    palabras genericas del rubro que aparecen en casi todos los resultados (ej.
    "electricidad", "electrico") pesan poco; palabras que distinguen un producto
    puntual (marca, modelo, tipo especifico) pesan mucho. A diferencia de una lista
    de stopwords fija, esto generaliza solo a cualquier categoria sin mantenimiento.
    """
    docs = [_tokenize(query_text)] + [_tokenize(p.get("name")) for p in candidates_raw]
    doc_freq: dict = {}
    for doc in docs:
        for w in set(doc):
            doc_freq[w] = doc_freq.get(w, 0) + 1

    def weight(w):
        return 1.0 / (1 + doc_freq.get(w, 0))

    q_tokens = set(docs[0])
    scored = []
    for p, cand_tokens in zip(candidates_raw, docs[1:]):
        c_tokens = set(cand_tokens)
        shared = q_tokens & c_tokens
        if not shared:
            score = 0.0
        else:
            union = q_tokens | c_tokens
            score = sum(weight(w) for w in shared) / (sum(weight(w) for w in union) or 1.0)
        scored.append((p, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored

def _similarity_with_coverage(query_text: str, candidates_raw: list) -> list:
    """(producto, similitud simetrica ponderada, cobertura del query ponderada) para cada candidato."""
    docs = [_tokenize(query_text)] + [_tokenize(p.get("name")) for p in candidates_raw]
    doc_freq: dict = {}
    for doc in docs:
        for w in set(doc):
            doc_freq[w] = doc_freq.get(w, 0) + 1
    weight = lambda w: 1.0 / (1 + doc_freq.get(w, 0))
    q = set(docs[0])
    q_w = sum(weight(w) for w in q) or 1.0
    out = []
    for p, cand in zip(candidates_raw, docs[1:]):
        c = set(cand)
        shared_w = sum(weight(w) for w in q & c)
        union_w = sum(weight(w) for w in q | c) or 1.0
        out.append((p, shared_w / union_w, shared_w / q_w))
    return out

def _discover_domains(text: str) -> tuple[list, str | None]:
    """Dominios de producto probables para un texto (y la marca, si ML la reconoce)."""
    try:
        suggestions = ml_get("/sites/MLA/domain_discovery/search", {"q": text, "limit": 3})
    except Exception:
        return [], None
    domains, brand = [], None
    for s in suggestions if isinstance(suggestions, list) else []:
        if s.get("domain_id") and s["domain_id"] not in domains:
            domains.append(s["domain_id"])
        if brand is None:
            brand = next((a.get("value_name") for a in s.get("attributes") or [] if a.get("id") == "BRAND"), None)
    return domains, brand

def _find_catalog_matches(text: str, domain_hint: str | None = None, item_id: str | None = None, limit: int = 10) -> dict:
    """
    Identifica a que producto de catalogo corresponde una publicacion a partir de
    su titulo (o del texto de su link). Antes se hacia UNA busqueda de 20 resultados
    sobre todo el catalogo y se rankeaba por texto: con titulos genericos traia
    productos de otro rubro, y con 6 candidatos como maximo a veces no aparecia el
    correcto. Ahora:

    1. domain_discovery sugiere el tipo de producto (ej. MLA-CIRCUIT_BREAKERS) y la marca.
    2. Se busca dentro de los 2 dominios mas probables + una busqueda libre de respaldo.
    3. Se rankea por texto (tf-idf), marca y codigo de modelo.
    4. Se consultan las ofertas de los mejores: si el item_id de la publicacion
       pegada aparece entre los vendedores de un candidato, ES ese producto (match
       exacto, no una estimacion). Candidatos sin ningun vendedor pierden peso.
    """
    key = f"match:{_norm(text)}:{domain_hint}:{item_id}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    domains, dd_brand = _discover_domains(text)
    # Dominios "cajon de sastre" (MLA-ELECTRICAL_SUPPLIES, MLA-OTHER_...) no describen el producto
    generic = lambda d: d.endswith("_SUPPLIES") or "OTHER" in d
    domains = [d for d in domains if not generic(d)]
    if domain_hint and not generic(domain_hint):
        domains = [domain_hint] + [d for d in domains if d != domain_hint]

    searches = [{"domain_id": d} for d in domains[:2]] + [{}]

    def run(extra):
        try:
            return ml_get("/products/search", {"status": "active", "site_id": "MLA", "q": text, "limit": 50, **extra}).get("results") or []
        except Exception:
            return []

    pool: dict = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        for results in ex.map(run, searches):
            for p in results:
                pool.setdefault(p["id"], p)
    candidates = list(pool.values())
    if not candidates:
        result = {"matches": [], "exact": None, "domains": domains}
        cache_set(key, result, ttl=300)
        return result

    q_tokens = _tokenize(text)
    q_codes  = _code_tokens(q_tokens)
    q_nums   = {t for t in q_tokens if any(c.isdigit() for c in t)} - q_codes
    q_dims   = _dim_tokens(text)
    q_norm   = f" {' '.join(q_tokens)} "
    scored = []
    for p, sim, coverage in _similarity_with_coverage(text, candidates):
        # Cobertura = cuanto del titulo pegado aparece en el candidato. La similitud
        # simetrica sola castigaba a los productos con nombres largos aunque fueran el correcto.
        score = 0.7 * coverage + 0.3 * sim
        cand_tokens = set(_tokenize(p.get("name")))
        if q_nums:
            shared_nums = q_nums & cand_tokens
            score += 0.1 * len(shared_nums) / len(q_nums)
            # Titulo con medidas/amperaje y candidato con OTRAS medidas (ej. pide 2x40, candidato 63a)
            if not shared_nums and any(any(c.isdigit() for c in t) for t in cand_tokens):
                score -= 0.15
        cand_dims = _dim_tokens(p.get("name"))
        if q_dims and cand_dims and not (q_dims & cand_dims):
            score -= 0.2
        brand = _attr(p, "BRAND")
        if brand:
            brand_norm = " ".join(_tokenize(brand))
            if brand_norm and (f" {brand_norm} " in q_norm or (dd_brand and _norm(dd_brand) == _norm(brand))):
                score += 0.15
        if q_codes and q_codes & set(_tokenize(f"{p.get('name')} {_attr(p, 'MODEL') or ''}")):
            score += 0.35
        if domains:
            if p.get("domain_id") == domains[0]:
                score += 0.15
            elif p.get("domain_id") not in domains:
                score -= 0.1
        scored.append((p, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    top = scored[:15]

    # Top 3 con hasta 200 ofertas (para encontrar el item_id aunque haya muchos vendedores)
    jobs = [(p["id"], 200 if (i < 3 and item_id) else 50) for i, (p, _) in enumerate(top)]
    summaries = dict(map_parallel(lambda j: (j[0], _offer_summary(j[0], max_items=j[1])), jobs, max_workers=8))

    exact, matches = None, []
    for p, score in top:
        s = summaries.get(p["id"]) or {"total": 0}
        if item_id and item_id in (s.get("item_ids") or []):
            exact = p["id"]
            score += 1.0
        if not s.get("total"):
            score *= 0.7
        matches.append({
            **_slim_product(p),
            "score":     round(min(score, 1.0), 2),
            "sellers":   s.get("total", 0),
            "min_price": s.get("min_price"),
            "max_price": s.get("max_price"),
            "exact":     p["id"] == exact,
        })
    matches.sort(key=lambda m: (m["exact"], m["score"], m["sellers"]), reverse=True)

    best = matches[0] if matches else None
    confident = bool(best) and (best["exact"] or (best["score"] >= 0.75 and best["sellers"] > 0
                                and (len(matches) < 2 or best["score"] - matches[1]["score"] >= 0.15)))
    result = {"matches": matches[:limit], "exact": exact, "confident": confident, "domains": domains}
    cache_set(key, result, ttl=600)
    return result

# Atributos que describen la ficha y no la funcion del producto: no sirven para
# decidir si otro producto es un reemplazo equivalente.
_NON_SPEC_ATTRS = {
    "BRAND", "MODEL", "LINE", "GTIN", "MPN", "SALE_FORMAT", "UNITS_PER_PACK", "LENGTH", "WIDTH",
    "HEIGHT", "DEPTH", "WEIGHT", "ALPHANUMERIC_MODEL", "DETAILED_MODEL", "PACKAGE_LENGTH",
    "PACKAGE_WIDTH", "PACKAGE_HEIGHT", "PACKAGE_WEIGHT", "COLOR", "MAIN_COLOR", "ITEM_CONDITION",
    "WARRANTY_TYPE", "WARRANTY_TIME", "SELLER_SKU", "MANUFACTURER", "ORIGIN", "COMPATIBLE_BRANDS",
    "COMPATIBLE_MODELS", "IS_KIT", "RELEASE_YEAR", "KIT_COMPONENTS", "CERTIFICATIONS",
}

def _specs(p) -> dict:
    out = {}
    for a in p.get("attributes") or []:
        aid, val = a.get("id"), a.get("value_name")
        if not aid or not val or aid in _NON_SPEC_ATTRS or len(val) > 40:
            continue
        out[aid] = (a.get("name") or aid, val)
    return out

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")

_DIM_RE = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?(?:x\d+(?:[.,]\d+)?)+(?![\d.,])")

def _dim_tokens(text: str) -> set:
    return set(_DIM_RE.findall(_norm(text).replace(" x ", "x")))

def _spec_weight(val: str) -> float:
    return 2.0 if any(c.isdigit() for c in val) else 1.0

def _spec_equal(a: str, b: str) -> bool:
    """Igualdad tolerante: '25 A' == '25A'; valores numericos con la misma unidad y <=10% de diferencia (220V/230V/240V)."""
    na, nb = _norm(a).replace(" ", ""), _norm(b).replace(" ", "")
    if na == nb:
        return True
    xa, xb = _NUM_RE.findall(na), _NUM_RE.findall(nb)
    if len(xa) == 1 and len(xb) == 1 and _NUM_RE.sub("", na) == _NUM_RE.sub("", nb):
        fa, fb = float(xa[0].replace(",", ".")), float(xb[0].replace(",", "."))
        return max(fa, fb) > 0 and abs(fa - fb) / max(fa, fb) <= 0.10
    return False

def _value_in_text(val: str, text_norm: str) -> bool:
    """Un valor numerico de 2+ digitos aparece como numero suelto en el nombre (evita que '2' matchee cualquier cosa)."""
    nums = _NUM_RE.findall(_norm(val))
    return len(nums) == 1 and len(nums[0]) >= 2 and re.search(rf"(?<![\d.,]){re.escape(nums[0])}(?![\d.,])", text_norm) is not None

def _related_products(product_id: str, limit: int = 12) -> dict:
    """
    Productos EQUIVALENTES (sustitutos) de otras marcas/modelos: mismo dominio de
    producto y las mismas especificaciones tecnicas (polos, amperaje, potencia,
    tension...), que ML ya tiene estructuradas en el catalogo. Es la respuesta a
    "contra que mas compite este producto", que el listado de vendedores del mismo
    producto no muestra. Solo se devuelven productos con vendedores activos hoy.
    """
    key = f"related:{product_id}:{limit}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    product = ml_get(f"/products/{product_id}")
    domain  = product.get("domain_id")
    specs   = _specs(product)

    # Texto de busqueda: el nombre sin marca, modelo, linea ni codigos (ej.
    # "Schneider A9r91225 Disyuntor Diferencial 2x25 30ma Acti9" -> "disyuntor diferencial 2x25 30ma")
    drop = set()
    for aid in ("BRAND", "MODEL", "LINE", "COLOR", "MAIN_COLOR"):
        drop |= set(_tokenize(_attr(product, aid) or ""))
    name_tokens = _tokenize(product.get("name"))
    words = [t for t in dict.fromkeys(name_tokens) if t not in drop and t not in _code_tokens([t])]
    query_full  = " ".join(words[:6]) or _norm(_attr(product, "PRODUCT_TYPE") or product.get("name") or "")
    query_short = " ".join(words[:2]) or query_full

    def run(q):
        params = {"status": "active", "site_id": "MLA", "q": q, "limit": 50}
        if domain:
            params["domain_id"] = domain
        try:
            return ml_get("/products/search", params).get("results") or []
        except Exception:
            return []

    pool: dict = {}
    queries = [query_full] if query_full == query_short else [query_full, query_short]
    with ThreadPoolExecutor(max_workers=2) as ex:
        for results in ex.map(run, queries):
            for p in results:
                if p.get("id") != product_id:
                    pool.setdefault(p["id"], p)
    candidates = list(pool.values())

    total_w = sum(_spec_weight(v) for _, v in specs.values()) or 0.0
    numeric_ids = [aid for aid, (_, v) in specs.items() if any(c.isdigit() for c in v)]
    text_sim = dict((p["id"], s) for p, s in _rank_by_similarity(product.get("name") or "", candidates))
    scored = []
    for p in candidates:
        cs = _specs(p)
        cand_name = _norm(p.get("name"))
        matched, diffs = [], []
        got, numeric_ok, numeric_diff = 0.0, 0, False
        for aid, (name, val) in specs.items():
            if aid in cs:
                if _spec_equal(val, cs[aid][1]):
                    got += _spec_weight(val)
                    matched.append(name)
                    numeric_ok += aid in numeric_ids
                else:
                    diffs.append({"name": name, "value": cs[aid][1], "source": val})
                    numeric_diff = numeric_diff or aid in numeric_ids
            elif _value_in_text(val, cand_name):
                # Fichas incompletas: el dato no esta cargado como atributo pero si en el nombre ("2x25 30ma")
                got += 0.75 * _spec_weight(val)
                matched.append(name)
                numeric_ok += aid in numeric_ids
        spec_score = (got / total_w) if total_w else text_sim.get(p["id"], 0)
        score = 0.8 * spec_score + 0.2 * text_sim.get(p["id"], 0)
        # Medidas escritas en el nombre ("2x25", "300x300x150"): si ambos las tienen y difieren, no es equivalente
        src_dims, cand_dims = _dim_tokens(product.get("name")), _dim_tokens(p.get("name"))
        if src_dims and cand_dims and not (src_dims & cand_dims):
            numeric_diff = True
            score -= 0.15
        same = score >= 0.6 and ((not numeric_diff and numeric_ok == len(numeric_ids)) if numeric_ids else not diffs)
        scored.append((p, score, matched, diffs, same))
    scored.sort(key=lambda t: (t[4], t[1]), reverse=True)
    top = [t for t in scored if t[1] >= 0.3][:30]

    summaries = dict(map_parallel(lambda t: (t[0]["id"], _offer_summary(t[0]["id"])), top, max_workers=8))
    related = []
    for p, score, matched, diffs, same in top:
        s = summaries.get(p["id"]) or {}
        if not s.get("total"):
            continue
        related.append({
            **_slim_product(p),
            "score":        round(score, 2),
            "sellers":      s["total"],
            "min_price":    s.get("min_price"),
            "max_price":    s.get("max_price"),
            "matched_specs": matched,
            "diff_specs":   diffs[:3],
            "same_specs":   bool(specs) and same,
        })
    related.sort(key=lambda r: (r["same_specs"], r["score"], r["sellers"]), reverse=True)
    related = related[:limit]

    source = _offer_summary(product_id)
    same = [r["min_price"] for r in related if r["same_specs"] and r["min_price"]]
    result = {
        "product_id": product_id,
        "domain_id":  domain,
        "specs":      [{"name": n, "value": v} for n, v in specs.values()],
        "source":     {"sellers": source.get("total"), "min_price": source.get("min_price"), "brand": _attr(product, "BRAND")},
        "related":    related,
        "same_spec_stats": {
            "count":  len(same),
            "min":    min(same) if same else None,
            "median": round(statistics.median(same)) if same else None,
        },
        "query": query_full,
    }
    cache_set(key, result, ttl=1800)
    return result

@app.route("/api/products/<product_id>/related")
def api_product_related(product_id):
    if not re.fullmatch(r"MLA\d{4,}", product_id or ""):
        return jsonify({"error": "Codigo de producto invalido"}), 400
    try:
        return jsonify(_related_products(product_id))
    except requests.HTTPError as e:
        return jsonify({"error": f"Error HTTP {e.response.status_code}", "related": []}), e.response.status_code
    except RuntimeError as e:
        return jsonify({"error": str(e), "related": []}), 401
    except Exception as e:
        return jsonify({"error": str(e), "related": []}), 500

def _raw_orders_for_period(owner_id, days: int) -> list:
    """Ordenes reales del vendedor en el periodo, paginadas completas y cacheadas
    (compartido entre /api/my-business y el analisis por item de /api/lookup)."""
    key    = f"orders_raw:{owner_id}:{days}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    date_to   = time.strftime("%Y-%m-%d", time.gmtime())
    date_from = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))
    orders_params = {
        "seller": owner_id,
        "order.date_created.from": f"{date_from}T00:00:00.000-00:00",
        "order.date_created.to":   f"{date_to}T23:59:59.000-00:00",
    }
    order_results, _ = ml_get_pages("/orders/search", orders_params, page_size=50, max_records=20000, max_offset=20000)
    cache_set(key, order_results, ttl=600)
    return order_results

def _business_for_item(item_id: str, days: int) -> dict:
    """
    Ventas y visitas REALES de una publicacion propia puntual. Solo tiene sentido
    si la publicacion es del dueno del token: ML no expone esta informacion para
    publicaciones de terceros (misma restriccion de ownership que /api/my-business).
    """
    owner_id  = get_owner_id()
    date_to   = time.strftime("%Y-%m-%d", time.gmtime())
    date_from = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))

    visits_total_data, visits_series_data = {}, {}
    try:
        visits_total_data = ml_get(f"/items/{item_id}/visits", {"date_from": date_from, "date_to": date_to})
    except Exception:
        pass
    try:
        visits_series_data = ml_get(f"/items/{item_id}/visits/time_window", {"last": days, "unit": "day"})
    except Exception:
        pass

    orders_count, revenue = 0, 0.0
    try:
        for o in _raw_orders_for_period(owner_id, days):
            for oi in (o.get("order_items") or []):
                if (oi.get("item") or {}).get("id") == item_id:
                    qty = oi.get("quantity") or 1
                    orders_count += qty
                    revenue += (oi.get("unit_price") or 0) * qty
    except Exception:
        pass

    price_to_win = None
    try:
        ptw = ml_get(f"/items/{item_id}/price_to_win", {"version": "v2"})
        price_to_win = {
            "status": ptw.get("status"), "price_to_win": ptw.get("price_to_win"),
            "current_price": ptw.get("current_price"),
            "competitors_sharing_first_place": ptw.get("competitors_sharing_first_place"),
            "visit_share": ptw.get("visit_share"),
            "reason": (ptw.get("reason") or [None])[0],
            "boosts": [{"id": b.get("id"), "status": b.get("status"), "description": b.get("description")} for b in (ptw.get("boosts") or [])],
        }
    except Exception:
        pass

    visits_total = visits_total_data.get("total_visits", 0)
    conversion   = round((orders_count / visits_total) * 100, 2) if visits_total else None

    return {
        "period_days":   days,
        "visits_total":  visits_total,
        "visits_series": [{"date": r.get("date"), "total": r.get("total")} for r in visits_series_data.get("results", [])],
        "orders_count":  orders_count,
        "revenue":       round(revenue, 2),
        "conversion_pct": conversion,
        "price_to_win":  price_to_win,
    }

def _item_info_from_offer(offer: dict, title: str | None, thumbnail: str | None) -> dict:
    """
    Datos de una publicacion de OTRO vendedor sin usar /items/{id} (bloqueado):
    salen de la lista publica de vendedores del producto de catalogo, que si
    trae precio, vendedor y reputacion de cada publicacion.
    """
    owner_id = get_owner_id()
    return {
        "id":                offer.get("item_id"),
        "title":             title,
        "price":             offer.get("price"),
        "thumbnail":         thumbnail,
        "permalink":         offer.get("permalink"),
        "condition":         None,
        "sold_quantity":     None,
        "seller_nickname":   offer.get("nickname"),
        "seller_reputation": offer.get("reputation"),
        "is_mine":           bool(owner_id) and str(offer.get("seller_id")) == str(owner_id),
        "blocked":           False,
    }

def _lookup_catalog_product_page(product_id: str, raw: str, days: int):
    """
    Camino directo cuando el link pegado es una pagina de producto de catalogo
    (.../p/MLA...): ahi ML ya nos da el product_id sin ambiguedad, no hace falta
    buscar candidatos. Si la URL trae ademas un item_id de oferta puntual
    (?...item_id:MLA...) se intenta traer ese item para pinearlo en la comparacion
    y sumar ventas/visitas si es propio; si no esta disponible (403/404) no es grave,
    se sigue mostrando el producto igual.
    """
    try:
        product = ml_get(f"/products/{product_id}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return jsonify({"error": f"Mercado Libre no tiene ningun producto de catalogo con el codigo {product_id}."}), 404
        return jsonify({"error": f"Error HTTP {e.response.status_code}"}), e.response.status_code

    offers_result = _offers_for_product(product_id)
    product_thumb = (product.get("pictures") or [{}])[0].get("url") if product.get("pictures") else None

    pinned_item_id = _parse_item_id_param(raw)
    item_info = None
    if pinned_item_id:
        try:
            pinned = ml_get(f"/items/{pinned_item_id}")
            seller_info = _get_seller(pinned.get("seller_id"))
            owner_id = get_owner_id()
            item_info = {
                "id":                pinned.get("id"),
                "title":             pinned.get("title"),
                "price":             pinned.get("price"),
                "thumbnail":         (pinned.get("pictures") or [{}])[0].get("secure_url") if pinned.get("pictures") else product_thumb,
                "permalink":         pinned.get("permalink"),
                "condition":         pinned.get("condition"),
                "sold_quantity":     pinned.get("sold_quantity"),
                "seller_nickname":   seller_info.get("nickname"),
                "seller_reputation": seller_info.get("reputation"),
                "is_mine":           bool(owner_id) and str(pinned.get("seller_id")) == str(owner_id),
                "blocked":           False,
            }
        except Exception:
            # Publicacion de un tercero (403): igual la encontramos en la lista de vendedores del producto
            offer = next((o for o in offers_result.get("offers", []) if o.get("item_id") == pinned_item_id), None)
            if offer:
                item_info = _item_info_from_offer(offer, product.get("name"), product_thumb)

    if item_info is None:
        item_info = {
            "id": product_id, "title": product.get("name"), "price": None,
            "thumbnail": product_thumb, "permalink": None, "condition": None,
            "sold_quantity": None, "seller_nickname": None, "seller_reputation": None,
            "is_mine": False, "blocked": False,
        }

    business = _business_for_item(item_info["id"], days) if item_info.get("is_mine") else None

    return jsonify({
        "mode": "catalog",
        "item": item_info,
        "business": business,
        "product": {"id": product_id, "name": product.get("name"), "thumbnail": product_thumb},
        **offers_result,
    })

@app.route("/api/lookup")
def api_lookup():
    """
    Punto de entrada de 'Analizar publicacion'. Delega en _api_lookup_impl y
    homogeneiza los errores no capturados a JSON: antes esta ruta era la unica
    sin un try/except general, asi que una excepcion (token vencido a mitad de
    camino, un 500 transitorio de ML en una llamada sin try propio) devolvia la
    pagina de error HTML de Flask, y el frontend fallaba al hacer r.json() sobre
    eso en vez de mostrar un mensaje entendible.
    """
    raw  = request.args.get("input", "")
    days = _safe_int(request.args.get("days"), 30, lo=1, hi=90)
    try:
        return _api_lookup_impl(raw, days)
    except requests.HTTPError as e:
        return jsonify({"error": f"Error HTTP {e.response.status_code}"}), e.response.status_code
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _api_lookup_impl(raw: str, days: int):
    """
    El usuario pega un link o codigo de una publicacion real de ML y el sistema
    arma la comparacion contra el resto de los vendedores que ofrecen ese mismo
    producto. Si la publicacion es propia, ademas suma ventas/visitas/conversion
    reales (mismo dato que "Mi Negocio" pero enfocado en un solo item).

    Restriccion real de ML (verificada empiricamente, no documentada): /items/{id}
    devuelve 403 "access_denied" para publicaciones de OTROS vendedores en apps
    no certificadas (misma familia de bloqueo que /sites/MLA/search). Solo
    funciona para publicaciones propias. Por eso:

    - Si el item es propio (o por algun motivo el detalle esta disponible):
      camino ideal, con titulo/precio reales. Si esta agrupado en un producto
      de catalogo (catalog_product_id) la comparacion es exacta.
    - Si el item es de un tercero (403): no hay forma de leer su detalle via
      API. Se recurre al TEXTO DE LA URL (el slug con el titulo que ML pone en
      el link) para buscar candidatos de catalogo parecidos - no se inventa
      ni se adivina nada mas alla de texto que el propio usuario pego.
    """
    catalog_page_id = _parse_catalog_product_id(raw)
    if catalog_page_id:
        return _lookup_catalog_product_page(catalog_page_id, raw, days)

    item_id = _parse_item_id(raw)
    if not item_id:
        return jsonify({"error": "No se reconoce un codigo de publicacion valido (ej: MLA1234567890) ni un link de ML."}), 400

    item = None
    try:
        item = ml_get(f"/items/{item_id}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return jsonify({"error": (
                f"Mercado Libre no tiene ninguna publicacion con el codigo {item_id}. "
                "Puede ser un error de tipeo, un link recortado, o una publicacion vieja ya "
                "finalizada y eliminada del catalogo. Volve a copiar el link completo desde el navegador."
            )}), 404
        if e.response.status_code != 403:
            return jsonify({"error": f"Error HTTP {e.response.status_code}"}), e.response.status_code
        # 403 = publicacion de otro vendedor, seguimos con el camino de texto de URL

    if item is not None:
        seller_info = _get_seller(item.get("seller_id"))
        owner_id  = get_owner_id()
        is_mine   = bool(owner_id) and str(item.get("seller_id")) == str(owner_id)
        item_info = {
            "id":                 item.get("id"),
            "title":              item.get("title"),
            "price":              item.get("price"),
            "thumbnail":          (item.get("pictures") or [{}])[0].get("secure_url") if item.get("pictures") else None,
            "permalink":          item.get("permalink"),
            "condition":          item.get("condition"),
            "sold_quantity":      item.get("sold_quantity"),
            "seller_nickname":    seller_info.get("nickname"),
            "seller_reputation":  seller_info.get("reputation"),
            "is_mine":            is_mine,
            "blocked":            False,
        }
        business = _business_for_item(item_id, days) if is_mine else None

        catalog_product_id = item.get("catalog_product_id")
        if catalog_product_id:
            try:
                product = ml_get(f"/products/{catalog_product_id}")
            except Exception:
                product = {}
            offers_result = _offers_for_product(catalog_product_id)
            return jsonify({
                "mode": "catalog",
                "item": item_info,
                "business": business,
                "product": {
                    "id":        catalog_product_id,
                    "name":      product.get("name") or item.get("title"),
                    "thumbnail": (product.get("pictures") or [{}])[0].get("url") if product.get("pictures") else item_info["thumbnail"],
                },
                **offers_result,
            })

        match = _find_catalog_matches(item.get("title", ""), domain_hint=item.get("domain_id"))
        return jsonify({"mode": "manual_match", "item": item_info, "business": business, "item_id": item_id,
                        "candidates": match["matches"], "confident": match["confident"]})

    # Publicacion de un tercero: ML bloquea su detalle, identificamos por el texto de la URL
    slug_text = _parse_slug_text(raw)
    if not slug_text:
        return jsonify({
            "error": ("Mercado Libre no permite consultar el detalle de publicaciones de otros "
                      "vendedores por su sola ID (restriccion de apps no certificadas). Pegá el "
                      "link COMPLETO de la publicación (con el título en la URL, tal cual aparece "
                      "en tu navegador) para poder identificar el producto igual."),
        }), 403

    match = _find_catalog_matches(slug_text, item_id=item_id)
    if match["exact"]:
        # El item_id pegado figura entre los vendedores de este producto: identificacion exacta.
        pid = match["exact"]
        offers_result = _offers_for_product(pid)
        try:
            product = ml_get(f"/products/{pid}")
        except Exception:
            product = {}
        thumb = (product.get("pictures") or [{}])[0].get("url") if product.get("pictures") else None
        offer = next((o for o in offers_result.get("offers", []) if o.get("item_id") == item_id), None)
        item_info = _item_info_from_offer(offer, product.get("name") or slug_text, thumb) if offer else {
            "id": item_id, "title": product.get("name") or slug_text, "price": None, "thumbnail": thumb,
            "permalink": None, "seller_nickname": None, "seller_reputation": None, "is_mine": False, "blocked": False,
        }
        return jsonify({
            "mode": "catalog",
            "match": "exact",
            "item": item_info,
            "business": None,
            "product": {"id": pid, "name": product.get("name") or slug_text, "thumbnail": thumb},
            "other_candidates": [m for m in match["matches"] if m["id"] != pid][:6],
            **offers_result,
        })

    return jsonify({
        "mode": "manual_match",
        "item": {
            "id": item_id, "title": slug_text, "price": None, "thumbnail": None,
            "permalink": f"https://articulo.mercadolibre.com.ar/{item_id[:3]}-{item_id[3:]}",
            "seller_nickname": None, "seller_reputation": None, "blocked": True,
        },
        "item_id": item_id,
        "candidates": match["matches"],
        "confident": match["confident"],
    })

@app.route("/api/trends")
def api_trends():
    """Tendencias de busqueda MLA, opcionalmente por categoria."""
    category = request.args.get("category", "").strip()
    path = f"/trends/MLA/{category}" if category else "/trends/MLA"
    key  = f"trends:{category}"
    cached = cache_get(key)
    if cached:
        return jsonify(cached)
    try:
        data = ml_get(path)
        result = {"items": data if isinstance(data, list) else []}
        cache_set(key, result, ttl=3600)
        return jsonify(result)
    except requests.HTTPError as e:
        return jsonify({"error": f"Error HTTP {e.response.status_code}", "items": []}), e.response.status_code
    except RuntimeError as e:
        return jsonify({"error": str(e), "items": []}), 401
    except Exception as e:
        return jsonify({"error": str(e), "items": []}), 500

def _subcat_snapshot(sub: dict, sample: int = 25) -> dict:
    """Foto rapida de una subcategoria: tamano de catalogo, competencia y precios sobre una muestra."""
    params = {"status": "active", "site_id": "MLA", "q": sub["q"], "limit": 100}
    if sub.get("domain"):
        params["domain_id"] = sub["domain"]
    elif sub.get("cat"):
        params["category"] = sub["cat"]
    data = ml_get("/products/search", params)
    products = sorted(data.get("results") or [], key=_offer_likelihood, reverse=True)[:sample]
    summaries = map_parallel(lambda p: (p, _offer_summary(p["id"])), products, max_workers=6)
    active = [(p, s) for p, s in summaries if s.get("total")]
    sellers = [s["total"] for _, s in active]
    prices  = [s["min_price"] for _, s in active if s.get("min_price")]
    sampled_offers = sum(s.get("sampled", 0) for _, s in active) or 0
    brands: dict = {}
    for p, s in active:
        b = _attr(p, "BRAND") or "Sin marca"
        brands[b] = brands.get(b, 0) + s["total"]
    top_brand = max(brands.items(), key=lambda kv: kv[1])[0] if brands else None
    low_competition = sum(1 for n in sellers if n <= 3)
    return {
        "label":          sub.get("label"),
        "group":          sub.get("group"),
        "q":              sub["q"],
        "catalog_total":  (data.get("paging") or {}).get("total", 0),
        "sampled":        len(products),
        "with_sellers":   len(active),
        "avg_sellers":    round(sum(sellers) / len(sellers), 1) if sellers else 0,
        "max_sellers":    max(sellers) if sellers else 0,
        "median_price":   round(statistics.median(prices)) if prices else None,
        "low_competition_products": low_competition,
        "free_shipping_pct":  round(100 * sum(s.get("free_shipping", 0) for _, s in active) / sampled_offers) if sampled_offers else None,
        "official_store_pct": round(100 * sum(s.get("official_stores", 0) for _, s in active) / sampled_offers) if sampled_offers else None,
        "top_brand":      top_brand,
    }

@app.route("/api/overview", methods=["POST"])
def api_overview():
    """
    Mapa del rubro: compara todas las subcategorias entre si (cuanta competencia hay
    por producto, precio tipico, cuantos productos tienen pocos vendedores) para
    detectar donde conviene entrar. Usa una muestra de 25 productos por subcategoria
    -los mas probables de tener vendedores- y una sola pagina de busqueda: no es un
    barrido del catalogo, es una foto comparativa.
    """
    body = request.get_json(silent=True) or {}
    subs = [s for s in (body.get("subcats") or []) if isinstance(s, dict) and isinstance(s.get("q"), str) and s["q"].strip()][:60]
    subs = [{k: str(s.get(k, ""))[:80] for k in ("q", "domain", "cat", "label", "group")} for s in subs]
    if not subs:
        return jsonify({"error": "Faltan subcategorias"}), 400

    key = "overview:" + json.dumps(subs, sort_keys=True)
    cached = cache_get(key)
    if cached:
        return jsonify(cached)
    try:
        rows = map_parallel(_subcat_snapshot, subs, max_workers=4)
        order = {s["label"]: i for i, s in enumerate(subs)}
        rows.sort(key=lambda r: order.get(r["label"], 999))
        result = {"rows": rows, "generated_at": _snapshot_ts()}
        cache_set(key, result, ttl=3600)
        return jsonify(result)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/analysis")
def api_analysis():
    """
    Analisis agregado de un rubro para alimentar los graficos. 

    Mercado Libre limita /products/search a un maximo de 200 resultados por
    query (limit<=100 y offset<=100, ambos validados por el servidor -offset>100
    tira 400 "The maximum allowed value for 'offset' is 100", sin importar que
    tan grande sea el catalogo real-). Verificado empiricamente 2026-09-16.

    OJO: hasta el 2026-09-15 este mismo limite se habia medido en ~1000 (offset
    hasta 950-1000). ML lo bajo a 100 en algun momento entre esa fecha y esta
    -no es un cambio nuestro-. El codigo viejo pedia page_size=50 y asumia
    max_offset=1000, así que a partir de la 3ra pagina (offset=150) cada
    pedido fallaba con 400 y "ml_get_pages" lo tragaba en silencio devolviendo
    una lista vacia para esa pagina: el resultado final quedaba truncado a los
    primeros ~150 productos sin que nada lo avisara, y "analyzed" mostraba un
    numero mucho mas chico del que hoy es alcanzable. Con page_size=100 y
    max_offset=100 se llega de forma honesta al techo real (200), en 2 pedidos
    en vez de fallar en 18.

    Este endpoint SIEMPRE trae el maximo posible (hasta ese techo) y analiza el
    100% de lo que trae. Si el catalogo real es mayor a ese techo,
    "full_coverage" queda en False y el front debe avisar que no es el 100% del
    catalogo (limite externo de la API, no una eleccion nuestra). No hay forma
    de superar los 200 por busqueda sin fragmentarla en sub-busquedas -algo que
    se decidio no hacer, ver PROJECT_SPEC.md 7.5-.

    ?category=MLA... : restringe la busqueda a esa categoria de ML. CRITICO para
    la calidad de "marcas del rubro": sin esto, "q" es texto libre sobre TODO el
    catalogo de Mercado Libre, y hasta terminos que suenan especificos (ej.
    "transformador", "motor electrico", "electricidad") matchean productos de
    rubros completamente ajenos (juguetes, papeleria, ferreteria mecanica) que
    mencionan esa palabra de casualidad, ensuciando el ranking de marcas con
    nombres que no tienen nada que ver.

    ?domain=MLA-CIRCUIT_BREAKERS : opcional, ver docstring de /api/products.
    """
    q        = request.args.get("q", "").strip() or "electricidad"
    category = request.args.get("category", "").strip()
    domain   = request.args.get("domain", "").strip()
    key      = f"analysis:{q}:{category}:{domain}"
    cached   = cache_get(key)
    if cached:
        return jsonify(cached)

    try:
        # Trae el maximo reachable del catalogo (techo real de ML: limit<=100, offset<=100)
        search_params = {"status": "active", "site_id": "MLA", "q": q}
        if category:
            search_params["category"] = category
        if domain:
            search_params["domain_id"] = domain
        catalog_sample, total_catalog = ml_get_pages(
            "/products/search", search_params,
            page_size=100, max_records=200, max_offset=100,
        )

        brand_full_counts: dict[str, int] = {}
        for p in catalog_sample:
            b = _attr(p, "BRAND") or "Sin marca"
            brand_full_counts[b] = brand_full_counts.get(b, 0) + 1

        # Analisis caro (vendedores/precios/reputacion) sobre TODO lo que se pudo traer,
        # no sobre un subconjunto mas chico.
        detail_pool = catalog_sample

        def analyze_one(p):
            brand = _attr(p, "BRAND") or "Sin marca"
            offers_data = ml_get(f"/products/{p['id']}/items", {"limit": 50})
            items  = offers_data.get("results", []) or []
            n_sell = offers_data.get("paging", {}).get("total", len(items))
            prices = [i.get("price") for i in items if i.get("price")]
            if not prices:
                return None
            pmin, pmax = min(prices), max(prices)

            sellers_here = []
            for it in items:
                sid = it.get("seller_id")
                if not sid:
                    continue
                info = _get_seller(sid)
                sellers_here.append({
                    "nickname": info.get("nickname") or str(sid),
                    "reputation": info.get("reputation"),
                    "price": it.get("price"),
                    "is_min_price": it.get("price") == pmin,
                    "free_shipping": bool((it.get("shipping") or {}).get("free_shipping")),
                })

            return {
                "id": p.get("id"), "name": p.get("name"), "brand": brand,
                "sellers": n_sell, "min_price": pmin, "max_price": pmax,
                "avg_price": round(sum(prices) / len(prices)),
                "spread_pct": round(((pmax - pmin) / pmin) * 100, 1) if pmin else 0,
                "sellers_detail": sellers_here,
            }

        detailed = map_parallel(analyze_one, detail_pool, max_workers=10)

        brands: dict[str, dict] = {}
        sellers, reputation, logistics = {}, {}, {"free": 0, "paid": 0}
        all_prices, product_rows = [], []

        for row in detailed:
            brand = row["brand"]
            b = brands.setdefault(brand, {"sellers": 0, "price_sum": 0.0, "price_n": 0})
            b["sellers"]   += row["sellers"]
            b["price_sum"] += row["min_price"]
            b["price_n"]   += 1
            all_prices.extend([row["min_price"], row["max_price"]])

            for s in row["sellers_detail"]:
                sr = sellers.setdefault(s["nickname"], {"appearances": 0, "wins": 0, "reputation": s["reputation"]})
                sr["appearances"] += 1
                if s["is_min_price"]:
                    sr["wins"] += 1
                lvl = s["reputation"] or "sin_datos"
                reputation[lvl] = reputation.get(lvl, 0) + 1
                logistics["free" if s["free_shipping"] else "paid"] += 1

            product_rows.append({
                "id": row["id"], "name": row["name"], "brand": brand,
                "sellers": row["sellers"], "min_price": row["min_price"], "max_price": row["max_price"],
                "avg_price": row["avg_price"], "spread_pct": row["spread_pct"],
            })

        ts = _snapshot_ts()
        save_snapshots(q, product_rows, ts)
        save_seller_snapshots(q, detailed, ts)

        brand_rows = sorted(
            ({
                "brand": name,
                "products": brand_full_counts.get(name, 0),
                "avg_sellers": round(v["sellers"] / v["price_n"], 1) if v["price_n"] else 0,
                "avg_price": round(v["price_sum"] / v["price_n"]) if v["price_n"] else 0,
                "total_sellers": v["sellers"],
            } for name, v in brands.items()),
            key=lambda x: x["products"], reverse=True,
        )
        # Marcas que aparecieron en la muestra amplia pero no cayeron en el detalle:
        # igual se listan con su conteo real de productos, aunque sin precio/vendedores.
        seen = {b["brand"] for b in brand_rows}
        for name, count in brand_full_counts.items():
            if name not in seen:
                brand_rows.append({"brand": name, "products": count, "avg_sellers": 0, "avg_price": 0, "total_sellers": 0})
        brand_rows.sort(key=lambda x: x["products"], reverse=True)

        seller_rows = sorted(
            ({"nickname": n, **v} for n, v in sellers.items()),
            key=lambda x: x["appearances"], reverse=True,
        )[:12]

        result = {
            "query":          q,
            "analyzed":       len(product_rows),
            "catalog_sample": len(catalog_sample),
            "total_catalog":  total_catalog,
            "full_coverage":  len(catalog_sample) >= total_catalog,
            "brands":         brand_rows[:20],
            "sellers":        seller_rows,
            "reputation":     reputation,
            "logistics":      logistics,
            "products":       sorted(product_rows, key=lambda x: x["sellers"], reverse=True),
            "price_stats": {
                "min": min(all_prices) if all_prices else None,
                "max": max(all_prices) if all_prices else None,
                "avg": round(sum(all_prices) / len(all_prices)) if all_prices else None,
            },
        }
        cache_set(key, result, ttl=900)
        return jsonify(result)
    except requests.HTTPError as e:
        return jsonify({"error": f"Error HTTP {e.response.status_code}"}), e.response.status_code
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/reports/product-timeseries")
def api_product_timeseries():
    """
    Historial propio de precio/competencia de un producto de catalogo, acumulado
    a partir de cada vez que se corrio un analisis de rubro que lo incluyo. No es
    un dato de ML: es la foto que fuimos guardando nosotros con el tiempo.
    """
    product_id = request.args.get("product_id", "").strip()
    if not product_id:
        return jsonify({"error": "Falta product_id"}), 400
    return jsonify({"product_id": product_id, "history": get_product_timeseries(product_id)})

@app.route("/api/reports/seller-timeseries")
def api_seller_timeseries():
    """
    Evolucion de un vendedor en el tiempo: en cuantos productos aparecio y cuantas
    veces fue el mas barato, por cada corrida de analisis guardada. Es el proxy
    honesto de "que tan fuerte es este competidor" que la API permite sin
    certificacion DPP -Mercado Libre no expone sold_quantity de publicaciones de
    terceros a apps no certificadas (ver PROJECT_SPEC.md 7.6)-. No es un numero de
    ventas real: es presencia y frecuencia de ganar por precio, medido por nosotros
    mismos con el tiempo.
    """
    nickname = request.args.get("nickname", "").strip()
    if not nickname:
        return jsonify({"error": "Falta nickname"}), 400
    return jsonify({"nickname": nickname, "history": get_seller_timeseries(nickname)})

@app.route("/api/reports/price-alerts")
def api_price_alerts():
    """
    Productos cuyo precio minimo cambio desde la ultima vez que se corrio un
    analisis del mismo rubro. Recien tiene datos utiles despues de correr el mismo
    rubro 2 veces o mas (necesita 2 fotos para comparar).
    """
    q = request.args.get("q", "").strip()
    return jsonify({"query": q, "alerts": get_price_alerts(q)})

@app.route("/api/my-business")
def api_my_business():
    """
    Datos REALES del propio vendedor: ventas por periodo, visitas, conversion y
    precio recomendado para ganar. A diferencia del analisis de competencia (que
    corre sobre el catalogo publico), esto usa endpoints que solo devuelven datos
    del dueno del token (ownership), pero con eso resuelven lo que sold_quantity
    acumulado no puede: ventas reales filtrables por fecha.
    """
    days = _safe_int(request.args.get("days"), 30, lo=1, hi=90)
    owner_id = get_owner_id()
    if not owner_id:
        return jsonify({"error": "Sin sesion activa"}), 401

    key    = f"mybiz:{owner_id}:{days}"
    cached = cache_get(key)
    if cached:
        return jsonify(cached)

    try:
        # 1. Listado de publicaciones propias (paginado real, no solo la primera pagina)
        item_ids, total_listings = ml_get_pages(
            f"/users/{owner_id}/items/search", {}, page_size=100, max_records=300,
        )

        # 2. Detalle en lotes de 20 (multiget), en paralelo -> precio, sold_quantity, stock
        batches = [item_ids[i:i + 20] for i in range(0, len(item_ids), 20)]

        def fetch_batch(batch):
            bulk = ml_get("/items", {"ids": ",".join(batch)})
            out = []
            for entry in bulk:
                if entry.get("code") == 200:
                    b = entry["body"]
                    out.append({
                        "id": b.get("id"), "title": b.get("title"),
                        "price": b.get("price"), "sold_quantity": b.get("sold_quantity"),
                        "available_quantity": b.get("available_quantity"),
                        "permalink": b.get("permalink"), "status": b.get("status"),
                        "thumbnail": (b.get("pictures") or [{}])[0].get("secure_url") if b.get("pictures") else None,
                    })
            return out

        items_detail = [it for batch_result in map_parallel(fetch_batch, batches, max_workers=8) for it in batch_result]
        items_detail.sort(key=lambda x: x.get("sold_quantity") or 0, reverse=True)

        # 3. Visitas: acumulado del periodo + serie diaria
        date_to   = time.strftime("%Y-%m-%d", time.gmtime())
        date_from = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))
        visits_total = ml_get(f"/users/{owner_id}/items_visits", {"date_from": date_from, "date_to": date_to})
        visits_series = ml_get(f"/users/{owner_id}/items_visits/time_window", {"last": days, "unit": "day"})

        # 4. Ordenes reales del periodo, paginadas COMPLETAS en paralelo (no solo 50).
        #    Esto es lo que resuelve la limitacion original: ventas reales filtrables
        #    por fecha, con el conteo y la facturacion exactos, no una muestra.
        orders_params = {
            "seller": owner_id,
            "order.date_created.from": f"{date_from}T00:00:00.000-00:00",
            "order.date_created.to":   f"{date_to}T23:59:59.000-00:00",
        }
        order_results, orders_total = ml_get_pages(
            "/orders/search", orders_params, page_size=50, max_records=20000, max_offset=20000,
        )
        revenue = sum((o.get("total_amount") or 0) for o in order_results)

        # 5. Precio para ganar, solo en el top 6 por ventas (evita saturar de requests)
        def fetch_ptw(it):
            ptw = ml_get(f"/items/{it['id']}/price_to_win", {"version": "v2"})
            return {
                "item_id": it["id"], "title": it["title"],
                "status": ptw.get("status"), "price_to_win": ptw.get("price_to_win"),
                "current_price": ptw.get("current_price"),
                "competitors_sharing_first_place": ptw.get("competitors_sharing_first_place"),
                "visit_share": ptw.get("visit_share"),
                "reason": (ptw.get("reason") or [None])[0],
                "boosts": [{"id": b.get("id"), "status": b.get("status"), "description": b.get("description")} for b in (ptw.get("boosts") or [])],
            }
        price_to_win = map_parallel(fetch_ptw, items_detail[:6], max_workers=6)

        total_visits = visits_total.get("total_visits", 0)
        conversion = round((orders_total / total_visits) * 100, 2) if total_visits else None

        result = {
            "period_days":      days,
            "total_listings":   total_listings,
            "items":            items_detail[:20],
            "items_sample_size": len(items_detail),
            "total_sold_sample": sum((it.get("sold_quantity") or 0) for it in items_detail),
            "visits_total":     total_visits,
            "visits_series":    [{"date": r.get("date"), "total": r.get("total")} for r in visits_series.get("results", [])],
            "orders_count":     orders_total,
            "revenue":          revenue,
            "conversion_pct":  conversion,
            "price_to_win":    price_to_win,
        }
        cache_set(key, result, ttl=600)
        return jsonify(result)
    except requests.HTTPError as e:
        return jsonify({"error": f"Error HTTP {e.response.status_code}"}), e.response.status_code
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    if not CLIENT_ID:
        print("\nFalta ML_CLIENT_ID en .env")
    ensure_schema()
    token = get_user_token()
    if token:
        print(f"\nToken activo para: {get_nickname()}")
        print(f"Servidor listo en http://localhost:{PORT}\n")
    else:
        print("\nSin token de usuario.")
        print(f"Abri http://localhost:{PORT}/auth/setup para autorizarte.\n")
    # host explicito en 127.0.0.1 (no 0.0.0.0): el checklist de buenas practicas de ML
    # recomienda limitar que IPs pueden usar el token de acceso de la app. Al no
    # escuchar en la red, ningun otro dispositivo puede llegar a este proceso y
    # usar el token, aunque comparta la misma red que esta PC.
    app.run(host="127.0.0.1", debug=DEBUG, port=PORT, use_reloader=False, threaded=True)
