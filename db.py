"""
FUTCROSS | Capa de datos sobre Supabase (PostgREST).

Todas las consultas pasan por aca. Ninguna pantalla arma queries por su cuenta.
"""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
import streamlit as st
from supabase import Client, create_client

import logic


# ---------------------------------------------------------------------
# Conexion
# ---------------------------------------------------------------------
def secreto(clave: str, defecto=None):
    """Busca primero en .streamlit/secrets.toml y luego en variables de entorno.

    En local usamos secrets.toml; Hugging Face Spaces inyecta los secretos
    como variables de entorno. Asi el mismo codigo sirve en los dos lados.
    """
    try:
        if clave in st.secrets:
            return st.secrets[clave]
    except Exception:
        pass
    return os.environ.get(clave, defecto)


@st.cache_resource(show_spinner=False)
def cliente() -> Client:
    url = secreto("SUPABASE_URL")
    key = secreto("SUPABASE_KEY")
    if not url or not key:
        st.error(
            "Falta configurar la conexion a Supabase. "
            "Crea el archivo `.streamlit/secrets.toml` con SUPABASE_URL y SUPABASE_KEY "
            "(o cargalos en Settings > Secrets si ya desplegaste en la nube)."
        )
        st.stop()
    return create_client(url, key)


def _tabla(nombre: str):
    return cliente().table(nombre)


def _df(rows) -> pd.DataFrame:
    return pd.DataFrame(rows or [])


def _iso(valor):
    """Serializa fechas para PostgREST."""
    return valor.isoformat() if isinstance(valor, date) else valor


# ---------------------------------------------------------------------
# Planes
# ---------------------------------------------------------------------
def listar_planes(solo_activos: bool = True) -> pd.DataFrame:
    q = _tabla("planes").select("*").order("sesiones")
    if solo_activos:
        q = q.eq("activo", True)
    return _df(q.execute().data)


def crear_plan(nombre, sesiones, vigencia_dias, precio, descripcion=None):
    return _tabla("planes").insert({
        "nombre": nombre.strip().upper(),
        "sesiones": int(sesiones),
        "vigencia_dias": int(vigencia_dias),
        "precio": float(precio),
        "descripcion": descripcion,
    }).execute().data


def plan(plan_id: str) -> dict | None:
    r = _tabla("planes").select("*").eq("id", plan_id).limit(1).execute().data
    return r[0] if r else None


def paquetes_con_plan(plan_id: str) -> int:
    """Cuantas ventas usan este plan. Sirve para avisar antes de editarlo."""
    r = (_tabla("paquetes").select("id", count="exact")
         .eq("plan_id", plan_id).execute())
    return r.count or 0


def actualizar_plan(plan_id: str, cambios: dict):
    return _tabla("planes").update(cambios).eq("id", plan_id).execute().data


# ---------------------------------------------------------------------
# Alumnos
# ---------------------------------------------------------------------
def crear_alumno(datos: dict):
    limpio = {k: _iso(v) for k, v in datos.items() if v not in (None, "")}
    return _tabla("alumnos").insert(limpio).execute().data


def actualizar_alumno(alumno_id: str, cambios: dict):
    limpio = {k: _iso(v) for k, v in cambios.items()}
    return _tabla("alumnos").update(limpio).eq("id", alumno_id).execute().data


def alumno(alumno_id: str) -> dict | None:
    r = _tabla("alumnos").select("*").eq("id", alumno_id).limit(1).execute().data
    return r[0] if r else None


def panel_alumnos(solo_activos: bool = True) -> pd.DataFrame:
    """Una fila por alumno con su paquete mas relevante (vista v_alumnos_estado)."""
    q = _tabla("v_alumnos_estado").select("*").order("apellidos")
    if solo_activos:
        q = q.eq("activo", True)
    return _df(q.execute().data)


def buscar_alumnos(texto: str, limite: int = 25) -> pd.DataFrame:
    """Busca por nombre, apellido, codigo, DNI o telefono."""
    texto = (texto or "").strip()
    if not texto:
        return panel_alumnos().head(limite)
    patron = f"%{texto}%"
    filtro = ",".join([
        f"nombres.ilike.{patron}",
        f"apellidos.ilike.{patron}",
        f"codigo.ilike.{patron}",
        f"dni.ilike.{patron}",
        f"telefono.ilike.{patron}",
    ])
    rows = _tabla("v_alumnos_estado").select("*").or_(filtro).limit(limite).execute().data
    return _df(rows)


def identificar(texto: str) -> list[dict]:
    """Busqueda del kiosco: DNI o codigo exacto primero, luego nombre parcial."""
    texto = (texto or "").strip()
    if not texto:
        return []

    digitos = logic.solo_digitos(texto)
    if digitos and len(digitos) >= 8:
        exacto = _tabla("v_alumnos_estado").select("*").or_(
            f"dni.eq.{digitos},telefono.eq.{digitos}"
        ).execute().data
        if exacto:
            return exacto

    codigo = texto.upper()
    if codigo.startswith("FC-"):
        exacto = _tabla("v_alumnos_estado").select("*").eq("codigo", codigo).execute().data
        if exacto:
            return exacto

    patron = f"%{texto}%"
    return _tabla("v_alumnos_estado").select("*").or_(
        f"nombres.ilike.{patron},apellidos.ilike.{patron},codigo.ilike.{patron}"
    ).limit(8).execute().data


# ---------------------------------------------------------------------
# Paquetes
# ---------------------------------------------------------------------
def paquetes_de(alumno_id: str) -> pd.DataFrame:
    rows = (_tabla("v_paquetes").select("*")
            .eq("alumno_id", alumno_id).order("fecha_inicio", desc=True).execute().data)
    return _df(rows)


def paquete(paquete_id: str) -> dict | None:
    r = _tabla("v_paquetes").select("*").eq("id", paquete_id).limit(1).execute().data
    return r[0] if r else None


def paquete_vigente(alumno_id: str) -> dict | None:
    """El paquete que manda hoy: ACTIVO o CONGELADO, el que vence primero."""
    rows = (_tabla("v_paquetes").select("*")
            .eq("alumno_id", alumno_id)
            .in_("estado_real", ["ACTIVO", "CONGELADO"])
            .order("fecha_fin").execute().data)
    return rows[0] if rows else None


def ultimo_paquete(alumno_id: str) -> dict | None:
    rows = (_tabla("v_paquetes").select("*")
            .eq("alumno_id", alumno_id).order("fecha_fin", desc=True).limit(1).execute().data)
    return rows[0] if rows else None


def listar_paquetes(estados: list[str] | None = None) -> pd.DataFrame:
    q = _tabla("v_paquetes").select("*").order("fecha_fin", desc=True)
    if estados:
        q = q.in_("estado_real", estados)
    return _df(q.execute().data)


def crear_paquete(alumno_id, plan: dict, fecha_inicio: date, precio: float,
                  medio_pago: str, pagado: bool = True, observacion: str | None = None,
                  fecha_pedido: date | None = None, sede: str | None = None,
                  dias_asiste: str | None = None, vendedor: str | None = None,
                  tipo: str = "NUEVO", sesiones: int | None = None,
                  vigencia_dias: int | None = None):
    """Registra la venta con todos los datos del pedido.

    sesiones y vigencia_dias permiten ajustar el plan para una venta puntual
    (por ejemplo, regalar dos sesiones) sin tocar el catalogo.
    """
    total = int(sesiones or plan["sesiones"])
    dias = int(vigencia_dias or plan["vigencia_dias"])
    fecha_fin = logic.fecha_fin_plan(fecha_inicio, dias)

    return _tabla("paquetes").insert({
        "alumno_id": alumno_id,
        "plan_id": plan.get("id"),
        "plan_nombre": plan["nombre"],
        "sesiones_totales": total,
        "fecha_pedido": (fecha_pedido or fecha_inicio).isoformat(),
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
        "precio": float(precio),
        "medio_pago": medio_pago,
        "pagado": bool(pagado),
        "sede": sede,
        "dias_asiste": dias_asiste,
        "vendedor": vendedor,
        "tipo": tipo,
        "observacion": observacion,
    }).execute().data


def actualizar_paquete(paquete_id: str, cambios: dict):
    limpio = {k: _iso(v) for k, v in cambios.items()}
    return _tabla("paquetes").update(limpio).eq("id", paquete_id).execute().data


def siguiente_pedido() -> int:
    """Solo para mostrarlo antes de guardar; el numero real lo pone la base."""
    r = (_tabla("paquetes").select("nro_pedido")
         .order("nro_pedido", desc=True).limit(1).execute().data)
    return (r[0]["nro_pedido"] or 0) + 1 if r else 1


def vendedores() -> list:
    """Los vendedores que ya se usaron, para no escribirlos de nuevo."""
    r = _tabla("paquetes").select("vendedor").execute().data or []
    return sorted({(x.get("vendedor") or "").strip() for x in r if x.get("vendedor")})


def sedes() -> list:
    r = _tabla("alumnos").select("sede").execute().data or []
    vistas = {(x.get("sede") or "").strip() for x in r if x.get("sede")}
    return sorted(vistas | {"SURQUILLO"})


def cancelar_paquete(paquete_id: str, motivo: str):
    return _tabla("paquetes").update({
        "estado": "CANCELADO",
        "observacion": motivo,
    }).eq("id", paquete_id).execute().data


# ---------------------------------------------------------------------
# Congelamientos
# ---------------------------------------------------------------------
def congelar(paquete_id: str, alumno_id: str, motivo: str, detalle: str, desde: date):
    """Pausa el paquete. La vigencia se extiende recien al reactivar."""
    _tabla("congelamientos").insert({
        "paquete_id": paquete_id,
        "alumno_id": alumno_id,
        "motivo": motivo,
        "detalle": detalle,
        "fecha_inicio": desde.isoformat(),
    }).execute()
    _tabla("paquetes").update({"estado": "CONGELADO"}).eq("id", paquete_id).execute()


def reactivar(congelamiento_id: str, hasta: date) -> int:
    """Cierra el congelamiento y le devuelve al alumno los dias perdidos."""
    cong = _tabla("congelamientos").select("*").eq("id", congelamiento_id).limit(1).execute().data
    if not cong:
        raise ValueError("No se encontro el congelamiento.")
    cong = cong[0]

    inicio = logic.a_fecha(cong["fecha_inicio"])
    dias = logic.dias_congelamiento(inicio, hasta)

    pq = _tabla("paquetes").select("*").eq("id", cong["paquete_id"]).limit(1).execute().data[0]
    nueva_fin = logic.extender(logic.a_fecha(pq["fecha_fin"]), dias)

    _tabla("paquetes").update({
        "estado": "ACTIVO",
        "fecha_fin": nueva_fin.isoformat(),
        "dias_congelados": int(pq.get("dias_congelados") or 0) + dias,
    }).eq("id", pq["id"]).execute()

    _tabla("congelamientos").update({
        "fecha_fin": hasta.isoformat(),
        "dias_aplicados": dias,
        "activo": False,
    }).eq("id", congelamiento_id).execute()

    return dias


def congelamientos(activos: bool | None = True) -> pd.DataFrame:
    q = _tabla("congelamientos").select("*, alumnos(codigo,nombres,apellidos,telefono)")
    if activos is not None:
        q = q.eq("activo", activos)
    rows = q.order("fecha_inicio", desc=True).execute().data or []
    for r in rows:
        a = r.pop("alumnos", None) or {}
        r["codigo"] = a.get("codigo")
        r["alumno"] = f"{a.get('nombres','')} {a.get('apellidos','')}".strip()
        r["telefono"] = a.get("telefono")
    return _df(rows)


def congelamiento_abierto(paquete_id: str) -> dict | None:
    r = (_tabla("congelamientos").select("*")
         .eq("paquete_id", paquete_id).eq("activo", True).limit(1).execute().data)
    return r[0] if r else None


# ---------------------------------------------------------------------
# Asistencias
# ---------------------------------------------------------------------
def ya_marco_hoy(alumno_id: str, fecha: date | None = None) -> bool:
    fecha = fecha or logic.hoy()
    r = (_tabla("asistencias").select("id")
         .eq("alumno_id", alumno_id).eq("fecha", fecha.isoformat())
         .eq("anulada", False).limit(1).execute().data)
    return bool(r)


def marcar_asistencia(alumno_id: str, paquete_id: str, sede: str | None = None,
                      origen: str = "KIOSCO", fecha: date | None = None):
    payload = {
        "alumno_id": alumno_id,
        "paquete_id": paquete_id,
        "sede": sede,
        "origen": origen,
    }
    if fecha:
        payload["fecha"] = fecha.isoformat()
    return _tabla("asistencias").insert(payload).execute().data


def anular_asistencia(asistencia_id: str, quien: str = "admin"):
    """Al anular, la sesion vuelve automaticamente al saldo del alumno."""
    return _tabla("asistencias").update({
        "anulada": True, "anulada_por": quien,
    }).eq("id", asistencia_id).execute().data


def asistencias(desde: date, hasta: date, incluir_anuladas: bool = False) -> pd.DataFrame:
    q = (_tabla("v_asistencias").select("*")
         .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat()))
    if not incluir_anuladas:
        q = q.eq("anulada", False)
    return _df(q.order("fecha", desc=True).order("hora", desc=True).execute().data)


def registrar_bloqueo(alumno_id: str | None, texto: str, motivo: str):
    """Deja constancia de quien quiso entrenar sin paquete valido."""
    return _tabla("bloqueos").insert({
        "alumno_id": alumno_id, "texto": texto, "motivo": motivo,
    }).execute().data


def bloqueos(desde: date, hasta: date) -> pd.DataFrame:
    rows = (_tabla("bloqueos").select("*, alumnos(codigo,nombres,apellidos,telefono)")
            .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat())
            .order("fecha", desc=True).order("hora", desc=True).execute().data) or []
    for r in rows:
        a = r.pop("alumnos", None) or {}
        r["codigo"] = a.get("codigo")
        r["alumno"] = f"{a.get('nombres','')} {a.get('apellidos','')}".strip() or r.get("texto")
        r["telefono"] = a.get("telefono")
    return _df(rows)
