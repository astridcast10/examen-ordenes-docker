"""Vistas del frontend. TODAS las operaciones pasan por la API REST (no hay acceso a la BD)."""
import os

import requests
from django.contrib import messages
from django.shortcuts import redirect, render

API = os.getenv("API_URL", "http://api:5000").rstrip("/") + "/api"
ESTADOS = ["Pendiente", "Pagada", "Anulada"]


# ------------------------------------------------------------------ helpers
def _error_api(r):
    """Texto claro a partir de una respuesta de error de la API."""
    try:
        detalle = r.json().get("error", r.text)
    except (ValueError, AttributeError):
        detalle = (r.text or r.reason)[:200]
    return f"Error {r.status_code}: {detalle}"


def _api(request, metodo, ruta, **kwargs):
    """Llama a la API. Si no hay conexión, muestra el error y devuelve None."""
    try:
        return requests.request(metodo, f"{API}{ruta}", timeout=5, **kwargs)
    except requests.RequestException as e:
        messages.error(request, f"No se pudo conectar con la API: {e}")
        return None


def _obtener(request, ruta):
    """GET que devuelve el JSON, o None (con mensaje de error) si falla."""
    r = _api(request, "GET", ruta)
    if r is None:
        return None
    if not r.ok:
        messages.error(request, _error_api(r))
        return None
    return r.json()


def _resultado(request, r, ok_msg):
    """Muestra el mensaje de éxito/error. Devuelve True si la operación salió bien."""
    if r is None:
        return False
    if r.ok:
        messages.success(request, ok_msg)
        return True
    messages.error(request, _error_api(r))
    return False


def _convertir_detalle(campos):
    """Convierte el formulario en el JSON que espera la API. Devuelve (payload, error)."""
    try:
        return {
            "producto": campos["producto"].strip(),
            "cantidad": int(campos["cantidad"]),
            "precio_unitario": float(campos["precio_unitario"]),
        }, None
    except (ValueError, TypeError):
        return None, "La cantidad debe ser un entero y el precio un número válido."


def _campos_detalle(request):
    return {k: request.POST.get(k, "") for k in ("producto", "cantidad", "precio_unitario")}


# ------------------------------------------------------------------ órdenes
def lista_ordenes(request):
    ordenes = _obtener(request, "/ordenes") or []
    return render(request, "tienda/lista.html", {"ordenes": ordenes})


def crear_orden(request):
    orden = {"cliente": "", "estado": "Pendiente"}
    if request.method == "POST":
        orden = {
            "cliente": request.POST.get("cliente", "").strip(),
            "estado": request.POST.get("estado", "Pendiente"),
        }
        r = _api(request, "POST", "/ordenes", json=orden)
        if _resultado(request, r, "Orden creada"):
            return redirect("lista_ordenes")
    return render(request, "tienda/form_orden.html",
                  {"accion": "Crear", "orden": orden, "estados": ESTADOS})


def editar_orden(request, oid):
    if request.method == "POST":
        orden = {
            "id": oid,
            "cliente": request.POST.get("cliente", "").strip(),
            "estado": request.POST.get("estado", "Pendiente"),
        }
        r = _api(request, "PUT", f"/ordenes/{oid}",
                 json={"cliente": orden["cliente"], "estado": orden["estado"]})
        if _resultado(request, r, "Orden actualizada"):
            return redirect("lista_ordenes")
    else:
        orden = _obtener(request, f"/ordenes/{oid}")
        if orden is None:
            return redirect("lista_ordenes")
    return render(request, "tienda/form_orden.html",
                  {"accion": "Editar", "orden": orden, "estados": ESTADOS})


def eliminar_orden(request, oid):
    if request.method == "POST":
        r = _api(request, "DELETE", f"/ordenes/{oid}")
        _resultado(request, r, "Orden eliminada")
        return redirect("lista_ordenes")
    return render(request, "tienda/confirmar.html", {"tipo": "orden", "id": oid})


# ----------------------------------------------------------------- detalles
def lista_detalles(request, oid):
    orden = _obtener(request, f"/ordenes/{oid}")
    if orden is None:
        return redirect("lista_ordenes")
    return render(request, "tienda/lista_detalles.html",
                  {"orden": orden, "detalles": orden.get("detalles", [])})


def crear_detalle(request, oid):
    detalle = {"producto": "", "cantidad": 1, "precio_unitario": ""}
    if request.method == "POST":
        detalle = _campos_detalle(request)
        payload, error = _convertir_detalle(detalle)
        if error:
            messages.error(request, error)
        else:
            r = _api(request, "POST", f"/ordenes/{oid}/detalles", json=payload)
            if _resultado(request, r, "Detalle agregado"):
                return redirect("lista_detalles", oid=oid)
    return render(request, "tienda/form_detalle.html",
                  {"accion": "Crear", "oid": oid, "detalle": detalle})


def editar_detalle(request, oid, did):
    if request.method == "POST":
        detalle = _campos_detalle(request)
        payload, error = _convertir_detalle(detalle)
        if error:
            messages.error(request, error)
        else:
            r = _api(request, "PUT", f"/detalles/{did}", json=payload)
            if _resultado(request, r, "Detalle actualizado"):
                return redirect("lista_detalles", oid=oid)
    else:
        orden = _obtener(request, f"/ordenes/{oid}")
        if orden is None:
            return redirect("lista_ordenes")
        detalle = next((d for d in orden.get("detalles", []) if d["id"] == did), None)
        if detalle is None:
            messages.error(request, f"El detalle #{did} no existe en la orden #{oid}")
            return redirect("lista_detalles", oid=oid)
    return render(request, "tienda/form_detalle.html",
                  {"accion": "Editar", "oid": oid, "did": did, "detalle": detalle})


def eliminar_detalle(request, oid, did):
    if request.method == "POST":
        r = _api(request, "DELETE", f"/detalles/{did}")
        _resultado(request, r, "Detalle eliminado")
        return redirect("lista_detalles", oid=oid)
    return render(request, "tienda/confirmar.html", {"tipo": "detalle", "id": did, "oid": oid})
