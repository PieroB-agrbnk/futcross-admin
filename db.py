"""
FUTCROSS | Capa de datos sobre Supabase (PostgREST).

Todas las consultas pasan por aca. Ninguna pantalla arma queries por su cuenta.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone

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
# Cache
#
# Streamlit vuelve a ejecutar el script entero en cada clic y en cada
# tecla. Sin cache, abrir el Panel disparaba una decena de consultas a
# Supabase por interaccion. Se guardan las lecturas por unos segundos y
# se tira todo el cache apenas se escribe algo, para que el usuario
# nunca vea un dato viejo despues de guardar.
#
# Lo que decide si alguien entra a entrenar (paquete vigente, si ya
# marco hoy) queda deliberadamente FUERA del cache: ahi un dato de hace
# 30 segundos podria regalar una sesion.
# ---------------------------------------------------------------------
CACHE_CORTO = 30     # movimiento del dia: asistencias, paquetes, alumnos
CACHE_LARGO = 300    # catalogos que casi no cambian: planes, grupos, sedes


def _cache(ttl: int, entradas: int = 64):
    return st.cache_data(ttl=ttl, show_spinner=False, max_entries=entradas)


def invalidar_cache() -> None:
    """Se llama despues de cada escritura. Sin esto, vender un paquete no
    se veria reflejado en las listas hasta que venciera el TTL."""
    try:
        st.cache_data.clear()
    except Exception:
        pass


def _escapar_filtro(texto: str) -> str:
    """Limpia el texto que va dentro de un `or_()` de PostgREST.

    La coma separa condiciones y el parentesis las agrupa: un alumno que
    busca "Perez, Juan" partia el filtro en dos y PostgREST devolvia un
    error 400 en vez de resultados. El punto y el asterisco tambien
    tienen significado, asi que se van.
    """
    return re.sub(r'[,()."*\\]', " ", texto or "").strip()


# ---------------------------------------------------------------------
# Planes
# ---------------------------------------------------------------------
@_cache(CACHE_LARGO)
def listar_planes(solo_activos: bool = True) -> pd.DataFrame:
    q = _tabla("planes").select("*").order("sesiones")
    if solo_activos:
        q = q.eq("activo", True)
    return _df(q.execute().data)


def crear_plan(nombre, sesiones, vigencia_dias, precio, descripcion=None):
    r = _tabla("planes").insert({
        "nombre": nombre.strip().upper(),
        "sesiones": int(sesiones),
        "vigencia_dias": int(vigencia_dias),
        "precio": float(precio),
        "descripcion": descripcion,
    }).execute().data
    invalidar_cache()
    return r


def plan(plan_id: str) -> dict | None:
    r = _tabla("planes").select("*").eq("id", plan_id).limit(1).execute().data
    return r[0] if r else None


def eliminar_plan(plan_id: str) -> None:
    """Borra el plan del catalogo.

    Solo si nunca se vendio. Si ya tiene pedidos, borrarlo dejaria esos
    pedidos apuntando a un plan que no existe, asi que en ese caso se
    desactiva: desaparece al vender pero el historial queda intacto.
    """
    usos = paquetes_con_plan(plan_id)
    if usos:
        raise ValueError(
            f"Este plan ya se vendio {usos} {'vez' if usos == 1 else 'veces'}. "
            "No se puede borrar sin romper esos pedidos. Usa 'Ocultar del catalogo'."
        )
    _tabla("planes").delete().eq("id", plan_id).execute()
    invalidar_cache()


@_cache(CACHE_LARGO)
def paquetes_con_plan(plan_id: str) -> int:
    """Cuantas ventas usan este plan. Sirve para avisar antes de editarlo.

    Se pide `count="exact"` con head: PostgREST devuelve solo el numero,
    sin traer las filas. Antes bajaba todos los ids para contarlos.
    """
    r = (_tabla("paquetes").select("id", count="exact")
         .eq("plan_id", plan_id).limit(1).execute())
    return r.count or 0


def actualizar_plan(plan_id: str, cambios: dict):
    r = _tabla("planes").update(cambios).eq("id", plan_id).execute().data
    invalidar_cache()
    return r


# ---------------------------------------------------------------------
# Precios por sede
#
# El mismo plan cuesta distinto segun la sede, y cada precio tiene su
# normal (el tachado del flyer) y el de promocion. Al vender se proponen
# los dos: el normal como precio de lista y el otro como cobrado.
# ---------------------------------------------------------------------
@_cache(CACHE_LARGO)
def precios_sede() -> pd.DataFrame:
    try:
        return _df(_tabla("precios_sede").select("*").execute().data)
    except Exception:
        # La migracion 025 todavia no se corrio
        return pd.DataFrame()


def precio_plan(plan: dict, sede: str | None) -> tuple[float, float]:
    """(precio de lista, precio actual) de un plan en una sede.

    Si esa sede no tiene precio propio, se usa el del catalogo para los dos.
    """
    base = float(plan.get("precio") or 0)
    tabla = precios_sede()
    if sede and not tabla.empty:
        fila = tabla[(tabla["plan_id"] == plan.get("id")) & (tabla["sede"] == sede)]
        if not fila.empty:
            return float(fila.iloc[0]["precio_lista"]), float(fila.iloc[0]["precio"])
    return base, base


def guardar_precio(plan_id: str, sede: str, precio_lista: float, precio: float):
    r = _tabla("precios_sede").upsert({
        "plan_id": plan_id,
        "sede": sede,
        "precio_lista": float(precio_lista),
        "precio": float(precio),
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="plan_id,sede").execute().data
    invalidar_cache()
    return r


def quitar_precio(plan_id: str, sede: str):
    _tabla("precios_sede").delete().eq("plan_id", plan_id).eq("sede", sede).execute()
    invalidar_cache()


def sede_de_grupo(grupo_id: str | None) -> str | None:
    if not grupo_id:
        return None
    grupos = listar_grupos()
    if grupos.empty:
        return None
    fila = grupos[grupos["id"] == grupo_id]
    return None if fila.empty else fila.iloc[0]["sede"]


# ---------------------------------------------------------------------
# Configuracion (claves de acceso)
#
# Sin cache a proposito: si se cambia un PIN, tiene que valer al
# instante en todas las pestanas abiertas.
# ---------------------------------------------------------------------
def leer_config(clave: str) -> str | None:
    try:
        r = (_tabla("config").select("valor")
             .eq("clave", clave).limit(1).execute().data)
        return r[0]["valor"] if r else None
    except Exception:
        # La migracion 019 todavia no se corrio: se cae a los secretos
        return None


def guardar_config(clave: str, valor: str, quien: str = "admin") -> None:
    _tabla("config").upsert({
        "clave": clave,
        "valor": valor,
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
        "actualizado_por": quien,
    }, on_conflict="clave").execute()
    invalidar_cache()


def config_actualizada(clave: str) -> dict | None:
    """Cuando y quien cambio esta clave por ultima vez."""
    try:
        r = (_tabla("config").select("actualizado_en,actualizado_por")
             .eq("clave", clave).limit(1).execute().data)
        return r[0] if r else None
    except Exception:
        return None


# ---------------------------------------------------------------------
# Grupos (sede + horario + genero + dias de entrenamiento)
# ---------------------------------------------------------------------
@_cache(CACHE_LARGO)
def listar_grupos(solo_activos: bool = True) -> pd.DataFrame:
    try:
        q = _tabla("grupos").select("*").order("sede")
        if solo_activos:
            q = q.eq("activo", True)
        return _df(q.execute().data)
    except Exception:
        # Si la migracion 009 todavia no se corrio, no romper la pantalla
        return pd.DataFrame()


def grupo(grupo_id: str) -> dict | None:
    r = _tabla("grupos").select("*").eq("id", grupo_id).limit(1).execute().data
    return r[0] if r else None


def crear_grupo(nombre, sede, genero, hora, dias):
    r = _tabla("grupos").insert({
        "nombre": nombre.strip().upper(),
        "sede": sede.strip().upper(),
        "genero": genero,
        "hora": hora,
        "dias": dias,
        "dias_por_semana": len(dias.split()),
    }).execute().data
    invalidar_cache()
    return r


def actualizar_grupo(grupo_id: str, cambios: dict):
    r = _tabla("grupos").update(cambios).eq("id", grupo_id).execute().data
    invalidar_cache()
    return r


# ---------------------------------------------------------------------
# Alumnos
# ---------------------------------------------------------------------
def crear_alumno(datos: dict):
    limpio = {k: _iso(v) for k, v in datos.items() if v not in (None, "")}
    r = _tabla("alumnos").insert(limpio).execute().data
    invalidar_cache()
    return r


def actualizar_alumno(alumno_id: str, cambios: dict):
    limpio = {k: _iso(v) for k, v in cambios.items()}
    r = _tabla("alumnos").update(limpio).eq("id", alumno_id).execute().data
    invalidar_cache()
    return r


@_cache(CACHE_CORTO, entradas=128)
def alumno(alumno_id: str) -> dict | None:
    r = _tabla("alumnos").select("*").eq("id", alumno_id).limit(1).execute().data
    return r[0] if r else None


@_cache(CACHE_CORTO)
def panel_alumnos(solo_activos: bool = True) -> pd.DataFrame:
    """Una fila por alumno con su paquete mas relevante (vista v_alumnos_estado)."""
    q = _tabla("v_alumnos_estado").select("*").order("apellidos")
    if solo_activos:
        q = q.eq("activo", True)
    return _df(q.execute().data)


@_cache(CACHE_CORTO)
def dnis_registrados() -> dict:
    """{dni: alumno_id} de todo el padron.

    Lo usa la carga masiva para no duplicar a quien ya esta: si el DNI
    existe, se le agrega el pedido al alumno que ya hay.
    """
    rows = (_tabla("alumnos").select("id,dni").limit(5000).execute().data) or []
    return {r["dni"]: r["id"] for r in rows if r.get("dni")}


def importar_fila(fila: dict) -> str:
    """Crea (o reutiliza) el alumno y le registra su pedido.

    Devuelve el codigo del alumno. Se llama una fila a la vez para que,
    si algo falla a mitad, se sepa exactamente donde quedo.
    """
    alumno_id = fila.get("_alumno_existente")
    grupo = fila.get("_grupo") or {}

    if not alumno_id:
        creado = _tabla("alumnos").insert({
            "nombres": fila["nombres"].strip().title(),
            "apellidos": fila["apellidos"].strip().title(),
            "dni": fila.get("dni"),
            "telefono": fila.get("telefono"),
            "grupo_id": grupo.get("id"),
            "dias_asiste": fila.get("dias_asiste"),
            "fecha_inscripcion": (fila.get("_inicio") or logic.hoy()).isoformat(),
        }).execute().data[0]
        alumno_id = creado["id"]
        codigo = creado.get("codigo", "")
    else:
        codigo = ""

    plan = fila.get("_plan")
    if plan and fila.get("_inicio"):
        crear_paquete(
            alumno_id, plan, fila["_inicio"],
            float(fila.get("_cobrado") or 0), "IMPORTADO", True, "Carga masiva",
            fecha_pedido=fila["_inicio"], sede=None,
            dias_asiste=fila.get("dias_asiste"),
            vendedor=fila.get("vendedor"),
            tipo="NUEVO", grupo_id=grupo.get("id"),
            precio_lista=float(fila.get("_lista") or fila.get("_cobrado") or 0),
            monto_entregado=float(fila.get("_entregado") or 0))
    return codigo


def buscar_alumnos(texto: str, limite: int = 25) -> pd.DataFrame:
    """Busca por nombre, apellido, codigo, DNI o telefono.

    Busca cada palabra por separado y se queda con los alumnos que
    cumplen todas: escribir "juan perez" encuentra a Juan Perez aunque
    el nombre y el apellido esten en columnas distintas.
    """
    limpio = _escapar_filtro(texto)
    if not limpio:
        return panel_alumnos().head(limite)

    encontrados: dict = {}
    resultado: set | None = None
    for palabra in limpio.split()[:4]:
        patron = f"%{palabra}%"
        filtro = ",".join([
            f"nombres.ilike.{patron}",
            f"apellidos.ilike.{patron}",
            f"codigo.ilike.{patron}",
            f"dni.ilike.{patron}",
            f"telefono.ilike.{patron}",
        ])
        rows = (_tabla("v_alumnos_estado").select("*")
                .or_(filtro).limit(200).execute().data) or []
        encontrados.update({r["alumno_id"]: r for r in rows})
        ids = set(r["alumno_id"] for r in rows)
        resultado = ids if resultado is None else (resultado & ids)
        if not resultado:
            return pd.DataFrame()
    return _df([encontrados[i] for i in sorted(resultado or ())][:limite])


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

    limpio = _escapar_filtro(texto)
    if not limpio:
        return []
    patron = f"%{limpio}%"
    return _tabla("v_alumnos_estado").select("*").or_(
        f"nombres.ilike.{patron},apellidos.ilike.{patron},codigo.ilike.{patron}"
    ).limit(8).execute().data


# ---------------------------------------------------------------------
# Paquetes
# ---------------------------------------------------------------------
@_cache(CACHE_CORTO, entradas=128)
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


@_cache(CACHE_CORTO)
def listar_paquetes(estados: list[str] | None = None,
                    desde: date | None = None,
                    hasta: date | None = None) -> pd.DataFrame:
    """Pedidos, opcionalmente filtrados por estado y por fecha de inicio.

    El filtro de fechas lo resuelve Postgres. Reportes lo usa para no
    bajar el historico completo de la academia cada vez que se mueve el
    rango: con dos anios de ventas eso eran miles de filas para mostrar
    las de un mes.
    """
    q = _tabla("v_paquetes").select("*").order("fecha_fin", desc=True)
    if estados:
        q = q.in_("estado_real", estados)
    if desde:
        q = q.gte("fecha_inicio", desde.isoformat())
    if hasta:
        q = q.lte("fecha_inicio", hasta.isoformat())
    return _df(q.execute().data)


@_cache(CACHE_CORTO)
def paquetes_por_cobrar() -> pd.DataFrame:
    """Pedidos registrados como pendientes de pago.

    Al vender se puede marcar "Pendiente", pero despues ese pedido no
    aparecia en ninguna pantalla: la plata quedaba sin cobrar y sin
    rastro. Esta consulta es la que alimenta el aviso del Panel.
    """
    try:
        rows = (_tabla("v_paquetes").select("*")
                .eq("pagado", False)
                .neq("estado_real", "CANCELADO")
                .order("fecha_limite_pago", desc=False).execute().data)
    except Exception:
        # Antes de la migracion 019 no existe fecha_limite_pago
        try:
            rows = (_tabla("v_paquetes").select("*")
                    .eq("pagado", False)
                    .neq("estado_real", "CANCELADO")
                    .order("fecha_pedido", desc=True).execute().data)
        except Exception:
            return pd.DataFrame()
    return _df(rows)


def registrar_abono(paquete_id: str, monto: float, total: bool = False):
    """Anota lo que el cliente entrego.

    `pagado` no se toca aca: lo calcula un trigger en la base a partir
    del monto entregado. Asi no puede quedar un pedido marcado como
    pagado con saldo pendiente.
    """
    pq = paquete(paquete_id) or {}
    precio = float(pq.get("precio") or 0)
    entregado = float(pq.get("monto_entregado") or 0)
    nuevo = precio if total else min(precio, entregado + float(monto))

    r = (_tabla("paquetes").update({"monto_entregado": nuevo})
         .eq("id", paquete_id).execute().data)
    invalidar_cache()
    return r


def marcar_pagado(paquete_id: str):
    """Salda el pedido completo. Se conserva por compatibilidad."""
    return registrar_abono(paquete_id, 0, total=True)


def crear_paquete(alumno_id, plan: dict, fecha_inicio: date, precio: float,
                  medio_pago: str, pagado: bool = True, observacion: str | None = None,
                  fecha_pedido: date | None = None, sede: str | None = None,
                  dias_asiste: str | None = None, vendedor: str | None = None,
                  tipo: str = "NUEVO", sesiones: int | None = None,
                  vigencia_dias: int | None = None, grupo_id: str | None = None,
                  precio_lista: float | None = None,
                  monto_entregado: float | None = None,
                  fecha_limite_pago: date | None = None):
    """Registra la venta con todos los datos del pedido.

    sesiones y vigencia_dias permiten ajustar el plan para una venta puntual
    (por ejemplo, regalar dos sesiones) sin tocar el catalogo.
    """
    total = int(sesiones or plan["sesiones"])
    dias = int(vigencia_dias or plan["vigencia_dias"])
    # El plan termina cuando se acaban las sesiones, contando solo los dias
    # que entrena ese grupo. Si no hay dias, cae al metodo de dias corridos.
    fecha_fin = logic.fecha_fin_por_calendario(fecha_inicio, total,
                                               dias_asiste, dias)

    r = _tabla("paquetes").insert({
        "alumno_id": alumno_id,
        "plan_id": plan.get("id"),
        "plan_nombre": plan["nombre"],
        "sesiones_totales": total,
        "fecha_pedido": (fecha_pedido or fecha_inicio).isoformat(),
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
        "precio_lista": float(precio_lista if precio_lista is not None else precio),
        "precio": float(precio),
        # Si no se dice cuanto entrego, se asume que pago todo o nada,
        # como funcionaba antes de que existieran los pagos parciales.
        "monto_entregado": float(
            monto_entregado if monto_entregado is not None
            else (precio if pagado else 0)),
        "fecha_limite_pago": (fecha_limite_pago.isoformat()
                              if fecha_limite_pago else None),
        "medio_pago": medio_pago,
        "pagado": bool(pagado),
        "sede": sede,
        "dias_asiste": dias_asiste,
        "grupo_id": grupo_id,
        "vendedor": vendedor,
        "tipo": tipo,
        "observacion": observacion,
    }).execute().data
    invalidar_cache()
    return r


def actualizar_paquete(paquete_id: str, cambios: dict):
    limpio = {k: _iso(v) for k, v in cambios.items()}
    r = _tabla("paquetes").update(limpio).eq("id", paquete_id).execute().data
    invalidar_cache()
    return r


def editar_pedido(paquete_id: str, plan: dict | None, fecha_inicio: date,
                  sesiones: int, dias_asiste: str, grupo_id: str | None,
                  precio_lista: float, precio: float, monto_entregado: float,
                  fecha_limite_pago: date | None, vendedor: str | None,
                  tipo: str, medio_pago: str, fecha_pedido: date,
                  observacion: str | None, quien: str = "admin",
                  fin_manual: date | None = None, motivo_fin: str | None = None):
    """Corrige un pedido ya registrado y recalcula lo que dependa de eso.

    Mover la fecha de inicio corre todo el calendario del alumno, asi que
    la fecha de fin se vuelve a calcular aca y no se pide a mano: si se
    escribiera, quedaria una fecha que no corresponde a ninguna sesion.

    El numero de pedido y la fecha en que se cerro la venta no se tocan
    desde la pantalla: son el rastro de la operacion original.
    """
    anterior = paquete(paquete_id) or {}
    # La fecha que se manda es solo la estimada: la base la recalcula con
    # sus feriados y pausas (trigger de la migracion 024). Si se fija a
    # mano, se guarda tal cual y la base ya no la toca.
    fecha_fin = fin_manual or logic.fecha_fin_por_calendario(
        fecha_inicio, int(sesiones), dias_asiste,
        int((plan or {}).get("vigencia_dias") or 30),
        excluir=fechas_sin_entrenar(grupo_id))

    cambios = {
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
        "fecha_pedido": fecha_pedido.isoformat(),
        "sesiones_totales": int(sesiones),
        "dias_asiste": dias_asiste,
        "grupo_id": grupo_id,
        "precio_lista": float(precio_lista),
        "precio": float(precio),
        "monto_entregado": float(monto_entregado),
        "fecha_limite_pago": (fecha_limite_pago.isoformat()
                              if fecha_limite_pago else None),
        "vendedor": vendedor,
        "tipo": tipo,
        "medio_pago": medio_pago,
        "observacion": observacion,
    }
    # Solo si la migracion 024 ya se corrio (la vista trae la columna) o
    # si de verdad se pidio fijarla: asi editar no se rompe si falta.
    if fin_manual or "fin_manual" in anterior:
        cambios["fin_manual"] = bool(fin_manual)
        cambios["fin_manual_motivo"] = (motivo_fin or None) if fin_manual else None
    if plan:
        cambios["plan_id"] = plan.get("id")
        cambios["plan_nombre"] = plan["nombre"]

    r = _tabla("paquetes").update(cambios).eq("id", paquete_id).execute().data

    # Queda constancia de que se toco un pedido: es dinero y fechas que el
    # cliente ya acordo, asi que tiene que poder rastrearse despues.
    try:
        detalle = []
        for campo, etiqueta in (("fecha_inicio", "inicio"), ("precio", "precio"),
                                ("sesiones_totales", "sesiones"),
                                ("plan_nombre", "plan"), ("dias_asiste", "dias"),
                                ("fecha_fin", "fin")):
            antes = anterior.get(campo)
            ahora = cambios.get(campo)
            if ahora is not None and str(antes) != str(ahora):
                detalle.append(f"{etiqueta}: {antes} -> {ahora}")
        if fin_manual:
            detalle.append(f"fin fijado a mano ({motivo_fin or 'sin motivo'})")
        if detalle:
            registrar_bloqueo(
                anterior.get("alumno_id"),
                f"Pedido {anterior.get('nro_pedido')} editado por {quien}. "
                + "; ".join(detalle),
                "PEDIDO_EDITADO")
    except Exception:
        pass

    invalidar_cache()
    return r


def siguiente_pedido() -> int:
    """Solo para mostrarlo antes de guardar; el numero real lo pone la base."""
    r = (_tabla("paquetes").select("nro_pedido")
         .order("nro_pedido", desc=True).limit(1).execute().data)
    return (r[0]["nro_pedido"] or 0) + 1 if r else 1


@_cache(CACHE_LARGO)
def vendedores() -> list:
    """Los vendedores que ya se usaron, para no escribirlos de nuevo.

    Se piden solo los ultimos 500 pedidos: los nombres se repiten y no
    hace falta recorrer el historico entero para armar la lista.
    """
    r = (_tabla("paquetes").select("vendedor")
         .order("creado_en", desc=True).limit(500).execute().data) or []
    return sorted({(x.get("vendedor") or "").strip() for x in r if x.get("vendedor")})


@_cache(CACHE_LARGO)
def sedes() -> list:
    r = (_tabla("alumnos").select("sede").limit(1000).execute().data) or []
    vistas = {(x.get("sede") or "").strip() for x in r if x.get("sede")}
    return sorted(vistas | {"SURQUILLO"})


def cancelar_paquete(paquete_id: str, motivo: str):
    r = _tabla("paquetes").update({
        "estado": "CANCELADO",
        "observacion": motivo,
    }).eq("id", paquete_id).execute().data
    invalidar_cache()
    return r


# ---------------------------------------------------------------------
# Congelamientos
# ---------------------------------------------------------------------
def congelar(paquete_id: str, alumno_id: str, motivo: str, detalle: str,
             desde: date, alta_prevista: date | None = None):
    """Pausa el paquete.

    alta_prevista es cuando se espera que vuelva. Es solo una estimacion:
    la fecha real se confirma al reactivar, y es esa la que manda.
    """
    _tabla("congelamientos").insert({
        "paquete_id": paquete_id,
        "alumno_id": alumno_id,
        "motivo": motivo,
        "detalle": detalle,
        "fecha_inicio": desde.isoformat(),
        "fecha_alta_prevista": alta_prevista.isoformat() if alta_prevista else None,
    }).execute()

    # Un viaje que empieza en dos semanas no puede pausar el plan hoy: la
    # persona todavia entrena. La pausa se activa sola al llegar la fecha
    # (fc_activar_congelamientos, que corre de noche y al abrir el panel).
    if desde <= logic.hoy():
        _tabla("paquetes").update({"estado": "CONGELADO"}).eq("id", paquete_id).execute()
    invalidar_cache()


def reactivar(congelamiento_id: str, hasta: date) -> int:
    """Cierra el congelamiento y le devuelve al alumno los dias perdidos."""
    cong = _tabla("congelamientos").select("*").eq("id", congelamiento_id).limit(1).execute().data
    if not cong:
        raise ValueError("No se encontro el congelamiento.")
    cong = cong[0]

    inicio = logic.a_fecha(cong["fecha_inicio"])
    dias = logic.dias_congelamiento(inicio, hasta)

    vista = paquete(cong["paquete_id"])
    pq = _tabla("paquetes").select("*").eq("id", cong["paquete_id"]).limit(1).execute().data[0]

    # La nueva fecha de fin es la de su ultima sesion contando desde el alta.
    # Sumar dias corridos podria dejarla en un dia que su grupo no entrena.
    restantes = int(vista["sesiones_restantes"]) if vista else 0
    dias_grupo = (vista or {}).get("dias_asiste")
    nueva_fin = None
    if restantes > 0 and dias_grupo:
        nueva_fin = logic.fecha_de_sesion(hasta, restantes, dias_grupo)
    if not nueva_fin:
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

    invalidar_cache()
    return dias


@_cache(CACHE_CORTO)
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


def activar_congelamientos() -> int:
    """Pone en pausa los congelamientos programados cuya fecha ya llego."""
    try:
        r = cliente().rpc("fc_activar_congelamientos", {}).execute()
        n = int(r.data or 0)
    except Exception:
        return 0
    if n:
        invalidar_cache()
    return n


def reactivar_automaticos() -> int:
    """Da de alta los congelamientos cuya fecha prevista ya llego.

    La misma funcion corre sola en la base todas las noches (pg_cron). Esto
    la ejecuta ademas al abrir el panel, para que el efecto se vea al
    instante y no haya que esperar al dia siguiente.
    """
    try:
        # Era `supabase()`, que no existe en este modulo: el NameError
        # caia en el except de abajo y las altas automaticas nunca
        # corrian desde la app, solo de madrugada por pg_cron.
        r = cliente().rpc("fc_reactivar_previstos", {}).execute()
        n = int(r.data or 0)
    except Exception:
        # Si la migracion 014 aun no se corrio, no pasa nada
        return 0
    if n:
        invalidar_cache()
    return n


@_cache(CACHE_CORTO)
def congelados_que_vuelven(hasta: date) -> pd.DataFrame:
    """Congelamientos cuya fecha prevista de alta ya llego o esta por llegar."""
    try:
        rows = (_tabla("congelamientos")
                .select("*, alumnos(codigo,nombres,apellidos,telefono)")
                .eq("activo", True)
                .lte("fecha_alta_prevista", hasta.isoformat())
                .order("fecha_alta_prevista").execute().data) or []
    except Exception:
        return pd.DataFrame()
    for r in rows:
        a = r.pop("alumnos", None) or {}
        r["codigo"] = a.get("codigo")
        r["alumno"] = f"{a.get('nombres','')} {a.get('apellidos','')}".strip()
        r["telefono"] = a.get("telefono")
    return _df(rows)


def pausas_de(paquete_id: str) -> list:
    """Las pausas de un paquete como pares (inicio, dia de vuelta).

    Sirve para no registrar una pausa encima de otra. La vuelta es la real
    si ya se reactivo, la prevista si no, o None si sigue abierta sin fecha.
    """
    rows = (_tabla("congelamientos").select("fecha_inicio,fecha_fin,fecha_alta_prevista")
            .eq("paquete_id", paquete_id).execute().data) or []
    return [(logic.a_fecha(r["fecha_inicio"]),
             logic.a_fecha(r.get("fecha_fin")) or logic.a_fecha(r.get("fecha_alta_prevista")))
            for r in rows]


def cambiar_vuelta(congelamiento_id: str, vuelta: date) -> None:
    """Cambia el dia en que el alumno vuelve, sin reactivarlo hoy.

    La base recalcula su fecha de fin con la nueva vuelta, y ese dia lo
    reactiva sola (de noche, o al abrir el panel).
    """
    _tabla("congelamientos").update({
        "fecha_alta_prevista": vuelta.isoformat(),
    }).eq("id", congelamiento_id).execute()
    invalidar_cache()


def quitar_pausa(congelamiento_id: str) -> None:
    """Borra una pausa programada que todavia no empezo. La base vuelve a
    calcular la fecha de fin sin ella."""
    _tabla("congelamientos").delete().eq("id", congelamiento_id).execute()
    invalidar_cache()


def congelamiento_abierto(paquete_id: str) -> dict | None:
    r = (_tabla("congelamientos").select("*")
         .eq("paquete_id", paquete_id).eq("activo", True).limit(1).execute().data)
    return r[0] if r else None


# ---------------------------------------------------------------------
# Dias que la academia no abrio
#
# Esas sesiones no se le cuentan a nadie: el plan se corre solo, porque
# `sesiones_usadas` sale del calendario y estos dias se descuentan ahi.
# ---------------------------------------------------------------------
@_cache(CACHE_CORTO)
def dias_no_laborables(desde: date | None = None) -> pd.DataFrame:
    try:
        q = _tabla("dias_no_laborables").select("*, grupos(nombre)")
        if desde:
            q = q.gte("fecha", desde.isoformat())
        rows = q.order("fecha", desc=True).execute().data or []
    except Exception:
        return pd.DataFrame()
    for r in rows:
        g = r.pop("grupos", None) or {}
        r["grupo"] = g.get("nombre") or "Todos los grupos"
    return _df(rows)


@_cache(CACHE_CORTO, entradas=16)
def fechas_sin_entrenar(grupo_id: str | None = None) -> set:
    """Dias sin entrenamiento que le tocan a un grupo: los de todos los
    grupos (feriados) mas los propios. Solo para calcular vistas previas;
    la fecha que se guarda la calcula la base con la misma regla."""
    try:
        rows = (_tabla("dias_no_laborables").select("fecha,grupo_id")
                .execute().data) or []
    except Exception:
        return set()
    return {logic.a_fecha(r["fecha"]) for r in rows
            if not r.get("grupo_id") or r.get("grupo_id") == grupo_id}


def marcar_no_laborable(fecha: date, grupo_id: str | None, motivo: str):
    r = _tabla("dias_no_laborables").insert({
        "fecha": fecha.isoformat(),
        "grupo_id": grupo_id,
        "motivo": motivo,
    }).execute().data
    invalidar_cache()
    return r


def quitar_no_laborable(registro_id: str):
    _tabla("dias_no_laborables").delete().eq("id", registro_id).execute()
    invalidar_cache()


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
    r = _tabla("asistencias").insert(payload).execute().data
    invalidar_cache()
    return r


def anular_asistencia(asistencia_id: str, quien: str = "admin"):
    """Al anular, la sesion vuelve automaticamente al saldo del alumno."""
    r = _tabla("asistencias").update({
        "anulada": True, "anulada_por": quien,
    }).eq("id", asistencia_id).execute().data
    invalidar_cache()
    return r


@_cache(CACHE_CORTO)
def asistencias(desde: date, hasta: date, incluir_anuladas: bool = False) -> pd.DataFrame:
    q = (_tabla("v_asistencias").select("*")
         .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat()))
    if not incluir_anuladas:
        q = q.eq("anulada", False)
    return _df(q.order("fecha", desc=True).order("hora", desc=True).execute().data)


@_cache(CACHE_CORTO, entradas=128)
def asistencias_de(alumno_id: str, desde: date, hasta: date) -> pd.DataFrame:
    """Las asistencias de UN alumno.

    La ficha usaba `asistencias(desde, hasta)` y filtraba en pandas:
    bajaba seis meses de asistencias de toda la academia para dibujar el
    mapa de calor de una sola persona. Ahora filtra Postgres.
    """
    rows = (_tabla("v_asistencias").select("*")
            .eq("alumno_id", alumno_id).eq("anulada", False)
            .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat())
            .order("fecha", desc=True).order("hora", desc=True).execute().data)
    return _df(rows)


def registrar_bloqueo(alumno_id: str | None, texto: str, motivo: str):
    """Deja constancia de quien quiso entrenar sin paquete valido."""
    r = _tabla("bloqueos").insert({
        "alumno_id": alumno_id, "texto": texto, "motivo": motivo,
    }).execute().data
    invalidar_cache()
    return r


def intentos_fallidos_recientes(minutos: int = 15) -> int:
    """Cuantos PIN fallidos hubo en los ultimos minutos, en toda la instalacion.

    El contador de intentos vivia en `st.session_state`, o sea en la
    pestana del navegador: abrir una ventana nueva lo reiniciaba y el
    bloqueo no servia de nada. Este cuenta contra la base, que es la
    misma para todos.
    """
    try:
        desde = datetime.now(timezone.utc) - timedelta(minutes=minutos)
        r = (_tabla("bloqueos").select("id", count="exact")
             .eq("motivo", "PIN_FALLIDO")
             .gte("creado_en", desde.isoformat()).limit(1).execute())
        return int(r.count or 0)
    except Exception:
        return 0


# ---------------------------------------------------------------------
# Otros ingresos
#
# Plata que entra sin alumno asociado: el partido amistoso del domingo,
# un alquiler de cancha. Se guarda el total del dia.
# ---------------------------------------------------------------------
@_cache(CACHE_CORTO)
def ingresos_extra(desde: date, hasta: date) -> pd.DataFrame:
    try:
        rows = (_tabla("ingresos_extra").select("*")
                .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat())
                .order("fecha", desc=True).execute().data)
    except Exception:
        # Si la migracion 023 todavia no se corrio, no romper la pantalla
        return pd.DataFrame()
    return _df(rows)


def registrar_ingreso_extra(fecha: date, concepto: str, monto: float,
                            personas: int | None = None,
                            medio_pago: str | None = None,
                            notas: str | None = None):
    r = _tabla("ingresos_extra").insert({
        "fecha": fecha.isoformat(),
        "concepto": concepto,
        "monto": float(monto),
        "personas": personas,
        "medio_pago": medio_pago,
        "notas": notas,
    }).execute().data
    invalidar_cache()
    return r


def eliminar_ingreso_extra(ingreso_id: str) -> None:
    _tabla("ingresos_extra").delete().eq("id", ingreso_id).execute()
    invalidar_cache()


@_cache(CACHE_CORTO)
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
