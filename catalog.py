"""
Motor de catalogo: busqueda de ofertas por producto, identificacion de a que
producto de catalogo pertenece un texto/titulo (matching por similitud + marca +
codigo de modelo), y comparacion de especificaciones tecnicas para encontrar
productos equivalentes. Es el nucleo del pivot "al catalogo" descripto en
PROJECT_SPEC.md 5bis.
"""
import re
import statistics
import unicodedata
from concurrent.futures import ThreadPoolExecutor
import requests

from cache import cache_get, cache_set
from ml_client import ml_get, ml_get_pages, map_parallel


def attr(product, attr_id):
    for a in product.get("attributes", []) or []:
        if a.get("id") == attr_id:
            return a.get("value_name")
    return None


def offer_likelihood(p) -> int:
    """
    El catalogo de ML Argentina esta lleno de fichas importadas de otros sitios
    (Brasil, Mexico, Chile) que nadie vende aca. Verificado 2026-09-16 sobre 120
    productos reales: con parent_id, 64% tenia vendedores (vs 8% sin); con
    authority_types COMMUNITY, 34% (vs 3% solo INTERNAL). Ordenar cada pagina por
    esto hace que el filtro de "productos con vendedores" encuentre resultados en
    muchas menos llamadas. Es solo un orden: no descarta nada.
    """
    return (2 if p.get("parent_id") else 0) + (1 if "COMMUNITY" in (p.get("authority_types") or []) else 0)


def slim_product(p):
    """Reduce el payload de un producto de catalogo a lo que consume el frontend."""
    return {
        "id":        p.get("id"),
        "name":      p.get("name"),
        "domain_id": p.get("domain_id"),
        "brand":     attr(p, "BRAND"),
        "model":     attr(p, "MODEL"),
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


def offers_for_product(product_id: str, light: bool = False) -> dict:
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
    seller_infos = map_parallel(lambda sid: (sid, get_seller(sid)), unique_seller_ids, max_workers=8)
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


def get_seller(seller_id):
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


def find_catalog_matches(text: str, domain_hint: str | None = None, item_id: str | None = None, limit: int = 10) -> dict:
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
        brand = attr(p, "BRAND")
        if brand:
            brand_norm = " ".join(_tokenize(brand))
            if brand_norm and (f" {brand_norm} " in q_norm or (dd_brand and _norm(dd_brand) == _norm(brand))):
                score += 0.15
        if q_codes and q_codes & set(_tokenize(f"{p.get('name')} {attr(p, 'MODEL') or ''}")):
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
            **slim_product(p),
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


def related_products(product_id: str, limit: int = 12) -> dict:
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
        drop |= set(_tokenize(attr(product, aid) or ""))
    name_tokens = _tokenize(product.get("name"))
    words = [t for t in dict.fromkeys(name_tokens) if t not in drop and t not in _code_tokens([t])]
    query_full  = " ".join(words[:6]) or _norm(attr(product, "PRODUCT_TYPE") or product.get("name") or "")
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
            **slim_product(p),
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
        "source":     {"sellers": source.get("total"), "min_price": source.get("min_price"), "brand": attr(product, "BRAND")},
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


def subcat_snapshot(sub: dict, sample: int = 25) -> dict:
    """Foto rapida de una subcategoria: tamano de catalogo, competencia y precios sobre una muestra."""
    params = {"status": "active", "site_id": "MLA", "q": sub["q"], "limit": 100}
    if sub.get("domain"):
        params["domain_id"] = sub["domain"]
    elif sub.get("cat"):
        params["category"] = sub["cat"]
    data = ml_get("/products/search", params)
    products = sorted(data.get("results") or [], key=offer_likelihood, reverse=True)[:sample]
    summaries = map_parallel(lambda p: (p, _offer_summary(p["id"])), products, max_workers=6)
    active = [(p, s) for p, s in summaries if s.get("total")]
    sellers = [s["total"] for _, s in active]
    prices  = [s["min_price"] for _, s in active if s.get("min_price")]
    sampled_offers = sum(s.get("sampled", 0) for _, s in active) or 0
    brands: dict = {}
    for p, s in active:
        b = attr(p, "BRAND") or "Sin marca"
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
