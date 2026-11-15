"""API REST de órdenes de venta (Flask + SQL Server).

Único servicio que se conecta a la base de datos. Todas las respuestas son JSON.
Códigos usados: 200, 201, 400 (datos inválidos), 404 (no existe), 500/503 (error interno).
"""
import os
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

import pymssql
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
app.json.ensure_ascii = False

ESTADOS = ("Pendiente", "Pagada", "Anulada")
MAX_CANTIDAD = 10_000
MAX_PRECIO = Decimal("1000000")


# ---------------------------------------------------------------- conexión
def get_conn():
    """Datos de conexión desde variables de entorno (servidor = nombre del servicio)."""
    return pymssql.connect(
        server=os.environ.get("DB_HOST", "db"),
        user=os.environ.get("DB_USER", "sa"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "OrdenesDB"),
        login_timeout=10,
        timeout=15,
    )


@contextmanager
def cursor():
    """Cursor con commit automático; rollback si algo falla; siempre cierra."""
    conn = get_conn()
    try:
        cur = conn.cursor(as_dict=True)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ----------------------------------------------------------------- errores
class ApiError(Exception):
    def __init__(self, mensaje, status=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status


@app.errorhandler(ApiError)
def _api_error(e):
    return jsonify({"error": e.mensaje}), e.status


@app.errorhandler(HTTPException)
def _http_error(e):
    textos = {404: "Ruta no encontrada", 405: "Método no permitido", 415: "Content-Type debe ser application/json"}
    return jsonify({"error": textos.get(e.code, e.description)}), e.code


@app.errorhandler(pymssql.Error)
def _db_error(e):
    app.logger.exception("Error de base de datos")
    return jsonify({"error": "Error de base de datos"}), 500


@app.errorhandler(Exception)
def _unexpected(e):
    app.logger.exception("Error inesperado")
    return jsonify({"error": "Error interno del servidor"}), 500


# ------------------------------------------------------------- validaciones
def cuerpo_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Se requiere un cuerpo JSON válido (objeto)")
    return data


def v_cliente(v):
    if not isinstance(v, str) or not v.strip():
        raise ApiError("cliente es requerido (texto no vacío)")
    v = v.strip()
    if len(v) > 100:
        raise ApiError("cliente no puede superar 100 caracteres")
    return v


def v_estado(v):
    if v not in ESTADOS:
        raise ApiError("estado inválido; use: " + ", ".join(ESTADOS))
    return v


def v_producto(v):
    if not isinstance(v, str) or not v.strip():
        raise ApiError("producto es requerido (texto no vacío)")
    v = v.strip()
    if len(v) > 100:
        raise ApiError("producto no puede superar 100 caracteres")
    return v


def v_cantidad(v):
    msg = f"cantidad debe ser un entero entre 1 y {MAX_CANTIDAD}"
    try:
        if isinstance(v, bool):
            raise ValueError
        n = int(v)
        if isinstance(v, float) and v != n:
            raise ValueError
    except (TypeError, ValueError):
        raise ApiError(msg)
    if not 1 <= n <= MAX_CANTIDAD:
        raise ApiError(msg)
    return n


def v_precio(v):
    msg = f"precio_unitario debe ser un número entre 0 y {MAX_PRECIO}"
    try:
        if isinstance(v, bool):
            raise ValueError
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise ApiError(msg)
    if not d.is_finite() or d < 0 or d > MAX_PRECIO:
        raise ApiError(msg)
    return d.quantize(Decimal("0.01"))


# ------------------------------------------------------------ serialización
def _dinero(v):
    return float(v or 0)


def orden_json(r):
    return {
        "id": r["id"],
        "cliente": r["cliente"],
        "fecha": r["fecha"].strftime("%Y-%m-%d %H:%M:%S"),
        "estado": r["estado"],
        "total": _dinero(r["total"]),
    }


def detalle_json(r):
    return {
        "id": r["id"],
        "orden_id": r["orden_id"],
        "producto": r["producto"],
        "cantidad": r["cantidad"],
        "precio_unitario": _dinero(r["precio_unitario"]),
        "subtotal": _dinero(r["subtotal"]),
    }


# ----------------------------------------------------------------- helpers BD
def obtener_orden(cur, oid):
    cur.execute(
        "SELECT id, cliente, fecha, estado, total FROM dbo.ordenes WHERE id = %s", (oid,)
    )
    r = cur.fetchone()
    if not r:
        raise ApiError("Orden no encontrada", 404)
    return r


def obtener_detalle(cur, did):
    cur.execute(
        "SELECT id, orden_id, producto, cantidad, precio_unitario, subtotal "
        "FROM dbo.orden_detalle WHERE id = %s",
        (did,),
    )
    r = cur.fetchone()
    if not r:
        raise ApiError("Detalle no encontrado", 404)
    return r


def listar_detalles_de(cur, oid):
    cur.execute(
        "SELECT id, orden_id, producto, cantidad, precio_unitario, subtotal "
        "FROM dbo.orden_detalle WHERE orden_id = %s ORDER BY id",
        (oid,),
    )
    return [detalle_json(r) for r in cur.fetchall()]


def recalcular_total(cur, oid):
    """El total de la orden = suma de subtotales de sus detalles."""
    cur.execute(
        "UPDATE dbo.ordenes SET total = "
        "COALESCE((SELECT SUM(subtotal) FROM dbo.orden_detalle WHERE orden_id = %s), 0) "
        "WHERE id = %s",
        (oid, oid),
    )


# ------------------------------------------------------------------- health
@app.get("/health")
def health():
    try:
        with cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        return jsonify({"status": "ok", "db": "up"}), 200
    except Exception:
        app.logger.exception("Health check fallido")
        return jsonify({"status": "error", "db": "down"}), 503


# ------------------------------------------------------------------ órdenes
@app.get("/api/ordenes")
def listar_ordenes():
    with cursor() as cur:
        cur.execute("SELECT id, cliente, fecha, estado, total FROM dbo.ordenes ORDER BY id")
        data = [orden_json(r) for r in cur.fetchall()]
    return jsonify(data), 200


@app.get("/api/ordenes/<int:oid>")
def ver_orden(oid):
    with cursor() as cur:
        orden = orden_json(obtener_orden(cur, oid))
        orden["detalles"] = listar_detalles_de(cur, oid)
    return jsonify(orden), 200


@app.post("/api/ordenes")
def crear_orden():
    d = cuerpo_json()
    cliente = v_cliente(d.get("cliente"))
    estado = v_estado(d.get("estado", "Pendiente"))
    with cursor() as cur:
        cur.execute(
            "INSERT INTO dbo.ordenes (cliente, estado, total) OUTPUT INSERTED.id VALUES (%s, %s, 0)",
            (cliente, estado),
        )
        nuevo_id = cur.fetchone()["id"]
        orden = orden_json(obtener_orden(cur, nuevo_id))
    return jsonify(orden), 201


@app.put("/api/ordenes/<int:oid>")
def actualizar_orden(oid):
    d = cuerpo_json()
    sets, params = [], []
    if "cliente" in d:
        sets.append("cliente = %s")
        params.append(v_cliente(d["cliente"]))
    if "estado" in d:
        sets.append("estado = %s")
        params.append(v_estado(d["estado"]))
    if not sets:
        raise ApiError("Envíe cliente y/o estado para actualizar")
    with cursor() as cur:
        obtener_orden(cur, oid)
        cur.execute(f"UPDATE dbo.ordenes SET {', '.join(sets)} WHERE id = %s", (*params, oid))
        orden = orden_json(obtener_orden(cur, oid))
    return jsonify(orden), 200


@app.delete("/api/ordenes/<int:oid>")
def eliminar_orden(oid):
    with cursor() as cur:
        obtener_orden(cur, oid)
        cur.execute("DELETE FROM dbo.orden_detalle WHERE orden_id = %s", (oid,))
        cur.execute("DELETE FROM dbo.ordenes WHERE id = %s", (oid,))
    return jsonify({"mensaje": f"Orden {oid} y sus detalles eliminados"}), 200


# ----------------------------------------------------------------- detalles
@app.get("/api/ordenes/<int:oid>/detalles")
def listar_detalles(oid):
    with cursor() as cur:
        obtener_orden(cur, oid)
        data = listar_detalles_de(cur, oid)
    return jsonify(data), 200


@app.post("/api/ordenes/<int:oid>/detalles")
def crear_detalle(oid):
    d = cuerpo_json()
    producto = v_producto(d.get("producto"))
    cantidad = v_cantidad(d.get("cantidad"))
    precio = v_precio(d.get("precio_unitario"))
    with cursor() as cur:
        obtener_orden(cur, oid)
        cur.execute(
            "INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) "
            "OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)",
            (oid, producto, cantidad, precio),
        )
        nuevo_id = cur.fetchone()["id"]
        recalcular_total(cur, oid)
        detalle = detalle_json(obtener_detalle(cur, nuevo_id))
    return jsonify(detalle), 201


@app.put("/api/detalles/<int:did>")
def actualizar_detalle(did):
    d = cuerpo_json()
    if not any(k in d for k in ("producto", "cantidad", "precio_unitario")):
        raise ApiError("Envíe producto, cantidad y/o precio_unitario para actualizar")
    with cursor() as cur:
        actual = obtener_detalle(cur, did)
        producto = v_producto(d["producto"]) if "producto" in d else actual["producto"]
        cantidad = v_cantidad(d["cantidad"]) if "cantidad" in d else actual["cantidad"]
        precio = v_precio(d["precio_unitario"]) if "precio_unitario" in d else actual["precio_unitario"]
        cur.execute(
            "UPDATE dbo.orden_detalle SET producto = %s, cantidad = %s, precio_unitario = %s "
            "WHERE id = %s",
            (producto, cantidad, precio, did),
        )
        recalcular_total(cur, actual["orden_id"])
        detalle = detalle_json(obtener_detalle(cur, did))
    return jsonify(detalle), 200


@app.delete("/api/detalles/<int:did>")
def eliminar_detalle(did):
    with cursor() as cur:
        actual = obtener_detalle(cur, did)
        cur.execute("DELETE FROM dbo.orden_detalle WHERE id = %s", (did,))
        recalcular_total(cur, actual["orden_id"])
    return jsonify({"mensaje": f"Detalle {did} eliminado"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
