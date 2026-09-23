"""
Datos que ML solo expone sobre la propia cuenta del vendedor (ownership): ventas y
visitas reales de una publicacion puntual, y el chequeo de "undercut" (alguien mas
barato que vos en un producto que vendes). No tiene relacion con el analisis de
competencia sobre el catalogo publico, que vive en catalog.py.
"""
import time

import config
from cache import cache_get, cache_set
from ml_client import ml_get, ml_get_pages, map_parallel
from ml_auth import get_owner_id
from catalog import offers_for_product


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


def business_for_item(item_id: str, days: int) -> dict:
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


def _my_own_items(owner_id) -> list:
    """
    Publicaciones propias activas con su catalog_product_id (si ML las agrupo en
    un producto de catalogo). Reusa el mismo patron de paginacion+multiget que
    /api/my-business, pero devuelve solo los campos que necesita el chequeo de
    undercut (no duplica la logica de ventas/visitas de ese endpoint).
    """
    key = f"myitems_catalog:{owner_id}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    item_ids, _ = ml_get_pages(f"/users/{owner_id}/items/search", {}, page_size=100, max_records=300)
    batches = [item_ids[i:i + 20] for i in range(0, len(item_ids), 20)]

    def fetch_batch(batch):
        bulk = ml_get("/items", {"ids": ",".join(batch)})
        out = []
        for entry in bulk:
            if entry.get("code") != 200:
                continue
            b = entry["body"]
            if b.get("status") != "active":
                continue
            out.append({
                "id":                 b.get("id"),
                "title":              b.get("title"),
                "price":              b.get("price"),
                "permalink":          b.get("permalink"),
                "catalog_product_id": b.get("catalog_product_id"),
            })
        return out

    items = [it for batch_result in map_parallel(fetch_batch, batches, max_workers=8) for it in batch_result]
    cache_set(key, items, ttl=300)
    return items


def undercut_alerts() -> dict:
    """
    Publicaciones propias donde, HOY, algun otro vendedor del mismo producto de
    catalogo tiene un precio mas bajo que el tuyo. A diferencia de
    db.get_price_alerts() (que compara el rubro entero contra la corrida anterior,
    sin importar de quien sea cada publicacion), esto compara especificamente
    TUS publicaciones contra el resto de los vendedores de ese mismo producto,
    en tiempo real (no depende de haber corrido un analisis antes).

    Solo puede chequear publicaciones que ML agrupo en un producto de catalogo
    (catalog_product_id): sin eso no hay forma de saber quienes mas venden lo
    mismo (ver PROJECT_SPEC.md 5.7 y 7.6 - /items/{id} de terceros da 403).
    """
    owner_id = get_owner_id()
    if not owner_id:
        raise RuntimeError(f"Sin token. Autorizate primero en http://localhost:{config.PORT}/auth/setup")

    items = _my_own_items(owner_id)
    with_catalog = [it for it in items if it.get("catalog_product_id")]

    def check(it):
        try:
            offers_data = offers_for_product(it["catalog_product_id"], light=True)
        except Exception:
            return None
        others = [o for o in offers_data.get("offers", [])
                  if str(o.get("seller_id")) != str(owner_id) and o.get("price") is not None]
        my_price = it.get("price")
        if not others or my_price is None:
            return None
        best = min(others, key=lambda o: o["price"])
        if best["price"] >= my_price:
            return None
        below = [o for o in others if o["price"] < my_price]
        return {
            "item_id":              it["id"],
            "title":                it["title"],
            "my_price":             my_price,
            "permalink":            it.get("permalink"),
            "product_id":           it["catalog_product_id"],
            "best_price":           best["price"],
            "diff_abs":             round(my_price - best["price"], 2),
            "diff_pct":             round(((my_price - best["price"]) / my_price) * 100, 1),
            "competitor_nickname":  best.get("nickname"),
            "competitor_reputation": best.get("reputation"),
            "competitor_permalink": best.get("permalink"),
            "competitors_below":   len(below),
        }

    alerts = map_parallel(check, with_catalog, max_workers=8)
    alerts.sort(key=lambda a: a["diff_pct"], reverse=True)
    return {
        "alerts":       alerts,
        "checked":      len(with_catalog),
        "no_catalog":   len(items) - len(with_catalog),
        "total_active": len(items),
    }
