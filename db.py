"""
Historial de precios y vendedores (SQLite local). Guarda una foto por producto
cada vez que se corre un analisis de rubro, para poder mostrar tendencia de
precio/competencia en el tiempo. No agrega ninguna llamada extra a la API de ML:
reusa datos que /api/analysis ya trajo.

NO incluye sold_quantity: ese dato no esta disponible para publicaciones de
terceros via API (solo scrapeando el HTML publico, algo que este proyecto
descarta explicitamente por riesgo a la cuenta y a los Terminos de Servicio).
"""
import sqlite3
import time

import config


def ensure_schema():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
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


def snapshot_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def save_snapshots(query: str, rows: list, ts: str):
    """Inserta una fila de historial por producto. Nunca debe tirar abajo /api/analysis."""
    if not rows:
        return
    try:
        conn = sqlite3.connect(config.DB_PATH)
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
        conn = sqlite3.connect(config.DB_PATH)
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
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT ts_utc, sellers_count, min_price, avg_price, max_price FROM snapshots "
        "WHERE product_id = ? ORDER BY ts_utc ASC", (product_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_seller_timeseries(nickname: str) -> list:
    conn = sqlite3.connect(config.DB_PATH)
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
    conn = sqlite3.connect(config.DB_PATH)
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
