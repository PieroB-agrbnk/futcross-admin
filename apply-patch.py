"""
FUTCROSS | Patch 012 - Fecha prevista de alta al congelar

Requiere los parches 001 a 011 aplicados.

AL CONGELAR
  Ahora se registra cuando se espera que el alumno vuelva. Si el fisio
  dijo "un mes de reposo", esa fecha queda anotada desde el primer dia
  en vez de esperar a que alguien se acuerde.
  Propone 30 dias por defecto y se puede cambiar. Si no se sabe cuando
  vuelve, se desmarca la casilla y queda sin fecha.

AL REACTIVAR
  El campo de fecha de alta viene precargado con la fecha que se estimo
  al congelar. Sigue siendo editable: manda la fecha real, no la
  estimada.

AVISOS
  La tarjeta del congelado dice "vuelve en 12 dias", "vuelve hoy" o
  "debia volver hace 3 dias" en rojo.
  El Panel suma una seccion con quienes vuelven en los proximos 3 dias
  o ya debian haber vuelto, para que no se pase ninguno.
  El historial de congelamientos muestra la fecha prevista al lado de
  la real, para ver que tan bien se estima.

DE PASO
  Se corrige el texto de la pantalla, que seguia diciendo que el sistema
  "suma los dias perdidos al vencimiento". Desde el parche 009 la fecha
  se recalcula por el calendario del grupo, que no es lo mismo.

IMPORTANTE
  Necesita que ANTES corras migracion-012.sql en Supabase. El archivo se
  genera solo al aplicar el parche, en esta misma carpeta.
"""

import shutil
import sys
from pathlib import Path

PARCHE = "012-fecha-de-alta-prevista"
CARPETA_BACKUP = Path("respaldos") / PARCHE

# Si esta marca ya esta en app.py, el parche ya se aplico
MARCA_APLICADO = "Fecha prevista de alta"
MARCA_ORIGINAL = "Cuando arranca el plan, no cuando se inscribio"


CAMBIOS_APP = [
    (
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.1"\n\n',
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.2"\n\n',
    ),
    (
        '                       f"(promedio {prom} por dia).")\n\n',
        '                       f"(promedio {prom} por dia).")\n\n    # Quien tenia que volver de su congelamiento y todavia no lo reactivaron\n    vuelven = db.congelados_que_vuelven(hoy + timedelta(days=3))\n    if not vuelven.empty:\n        theme.seccion("Vuelven de congelamiento", "para reactivar su paquete")\n        for _, v in vuelven.iterrows():\n            prevista = logic.a_fecha(v.get("fecha_alta_prevista"))\n            faltan = (prevista - hoy).days if prevista else None\n            if faltan is None:\n                detalle, color = v.get("motivo", ""), theme.AZUL\n            elif faltan < 0:\n                detalle = f"Debia volver hace {abs(faltan)} dias"\n                color = theme.ROJO\n            elif faltan == 0:\n                detalle, color = "Vuelve hoy", theme.AMBAR\n            else:\n                detalle, color = f"Vuelve en {faltan} dias", theme.AZUL\n            theme.fila(v["alumno"], f\'{v.get("codigo", "")} \xb7 {detalle}\', color,\n                       theme.chip("CONGELADO"))\n        st.caption("Reactivalos en la pantalla Congelamientos para que su paquete "\n                   "vuelva a correr.")\n\n',
    ),
    (
        '    st.caption(\n        "Congelar detiene el reloj del paquete. Al dar de alta, el sistema suma "\n        "los dias perdidos a la fecha de vencimiento, asi el alumno no pierde lo que pago."\n    )\n',
        '    st.caption(\n        "Congelar detiene el reloj del paquete: mientras esta pausado no se le "\n        "descuentan sesiones. Al dar de alta, el sistema recalcula el vencimiento "\n        "contando sus sesiones restantes desde ese dia, en el calendario de su grupo."\n    )\n',
    ),
    (
        '                desde = c2.date_input("Congelar desde", value=logic.hoy(), format="DD/MM/YYYY")\n                detalle = st.text_input("Detalle",\n                                        placeholder="Ej. esguince de tobillo, 3 semanas de reposo")\n                if st.form_submit_button("Congelar paquete", type="primary"):\n',
        '                desde = c2.date_input("Congelar desde", value=logic.hoy(), format="DD/MM/YYYY")\n                detalle = st.text_input(\n                    "Detalle", placeholder="Ej. esguince de tobillo, 3 semanas de reposo")\n\n                d1, d2 = st.columns([1, 2])\n                sabe_cuando = d1.checkbox("Ya se cuando vuelve", value=True)\n                alta_prevista = d2.date_input(\n                    "Fecha prevista de alta", value=logic.hoy() + timedelta(days=30),\n                    format="DD/MM/YYYY", disabled=not sabe_cuando,\n                    help="Es una estimacion. La fecha real se confirma al reactivar.")\n\n                if st.form_submit_button("Congelar paquete", type="primary"):\n',
    ),
    (
        '                    try:\n                        db.congelar(paquete_id, alumno_id, motivo, detalle, desde)\n                        st.toast("Paquete congelado", icon="\u2744\ufe0f")\n',
        '                    try:\n                        db.congelar(paquete_id, alumno_id, motivo, detalle, desde,\n                                    alta_prevista if sabe_cuando else None)\n                        st.toast("Paquete congelado", icon="\u2744\ufe0f")\n',
    ),
    (
        '                        st.toast("Paquete congelado", icon="\u2744\ufe0f")\n                        st.success("Paquete congelado. No se le descontaran sesiones "\n                                   "hasta que lo reactives.")\n                        st.rerun()\n',
        '                        st.toast("Paquete congelado", icon="\u2744\ufe0f")\n                        aviso = ("Paquete congelado. No se le descontaran "\n                                 "sesiones hasta que lo reactives.")\n                        if sabe_cuando:\n                            aviso += (" Se espera su vuelta el "\n                                      f"{fecha_larga(alta_prevista)}.")\n                        st.success(aviso)\n                        st.rerun()\n',
    ),
    (
        '                dias = logic.dias_congelamiento(inicio, logic.hoy())\n                with st.container(border=True):\n',
        '                dias = logic.dias_congelamiento(inicio, logic.hoy())\n                prevista = logic.a_fecha(c.get("fecha_alta_prevista"))\n                with st.container(border=True):\n',
    ),
    (
        '                    c1.caption(f"{c[\'motivo\'].title()} \xb7 {c.get(\'detalle\') or \'sin detalle\'}")\n                    c2.metric("Congelado desde", inicio.strftime("%d/%m/%Y"), f"{dias} dias")\n',
        '                    c1.caption(f"{c[\'motivo\'].title()} \xb7 {c.get(\'detalle\') or \'sin detalle\'}")\n\n                    if prevista:\n                        faltan = (prevista - logic.hoy()).days\n                        if faltan > 0:\n                            c1.caption(f"Vuelve el {fecha_larga(prevista)} "\n                                       f"(faltan {faltan} dias)")\n                        elif faltan == 0:\n                            c1.markdown(f":orange[**Vuelve hoy**, {fecha_larga(prevista)}]")\n                        else:\n                            c1.markdown(f":red[Debia volver el {fecha_larga(prevista)}, "\n                                        f"hace {abs(faltan)} dias]")\n                    else:\n                        c1.caption("Sin fecha prevista de alta")\n\n                    c2.metric("Congelado desde", inicio.strftime("%d/%m/%Y"), f"{dias} dias")\n',
    ),
    (
        '                    c2.metric("Congelado desde", inicio.strftime("%d/%m/%Y"), f"{dias} dias")\n                    alta = c3.date_input("Fecha de alta", value=logic.hoy(),\n                                         min_value=inicio, format="DD/MM/YYYY",\n',
        '                    c2.metric("Congelado desde", inicio.strftime("%d/%m/%Y"), f"{dias} dias")\n                    # Se propone la fecha que se habia estimado al congelar\n                    por_defecto = prevista if prevista and prevista >= inicio else logic.hoy()\n                    alta = c3.date_input("Fecha de alta", value=por_defecto,\n                                         min_value=inicio, format="DD/MM/YYYY",\n',
    ),
    (
        '        else:\n            vista = hist[["codigo", "alumno", "motivo", "detalle", "fecha_inicio",\n                          "fecha_fin", "dias_aplicados", "activo"]].copy()\n            vista.columns = ["Codigo", "Alumno", "Motivo", "Detalle", "Desde",\n',
        '        else:\n            columnas = ["codigo", "alumno", "motivo", "detalle", "fecha_inicio",\n                        "fecha_alta_prevista", "fecha_fin", "dias_aplicados", "activo"]\n            for col in columnas:\n                if col not in hist.columns:\n                    hist[col] = None\n            vista = hist[columnas].copy()\n            vista.columns = ["Codigo", "Alumno", "Motivo", "Detalle", "Desde",\n',
    ),
    (
        '            vista.columns = ["Codigo", "Alumno", "Motivo", "Detalle", "Desde",\n                             "Hasta", "Dias devueltos", "Vigente"]\n            st.dataframe(vista, width="stretch", hide_index=True)\n',
        '            vista.columns = ["Codigo", "Alumno", "Motivo", "Detalle", "Desde",\n                             "Alta prevista", "Alta real", "Dias devueltos", "Vigente"]\n            st.dataframe(vista, width="stretch", hide_index=True)\n',
    ),
]


DB_NUEVO = '"""\nFUTCROSS | Capa de datos sobre Supabase (PostgREST).\n\nTodas las consultas pasan por aca. Ninguna pantalla arma queries por su cuenta.\n"""\n\nfrom __future__ import annotations\n\nimport os\nfrom datetime import date\n\nimport pandas as pd\nimport streamlit as st\nfrom supabase import Client, create_client\n\nimport logic\n\n\n# ---------------------------------------------------------------------\n# Conexion\n# ---------------------------------------------------------------------\ndef secreto(clave: str, defecto=None):\n    """Busca primero en .streamlit/secrets.toml y luego en variables de entorno.\n\n    En local usamos secrets.toml; Hugging Face Spaces inyecta los secretos\n    como variables de entorno. Asi el mismo codigo sirve en los dos lados.\n    """\n    try:\n        if clave in st.secrets:\n            return st.secrets[clave]\n    except Exception:\n        pass\n    return os.environ.get(clave, defecto)\n\n\n@st.cache_resource(show_spinner=False)\ndef cliente() -> Client:\n    url = secreto("SUPABASE_URL")\n    key = secreto("SUPABASE_KEY")\n    if not url or not key:\n        st.error(\n            "Falta configurar la conexion a Supabase. "\n            "Crea el archivo `.streamlit/secrets.toml` con SUPABASE_URL y SUPABASE_KEY "\n            "(o cargalos en Settings > Secrets si ya desplegaste en la nube)."\n        )\n        st.stop()\n    return create_client(url, key)\n\n\ndef _tabla(nombre: str):\n    return cliente().table(nombre)\n\n\ndef _df(rows) -> pd.DataFrame:\n    return pd.DataFrame(rows or [])\n\n\ndef _iso(valor):\n    """Serializa fechas para PostgREST."""\n    return valor.isoformat() if isinstance(valor, date) else valor\n\n\n# ---------------------------------------------------------------------\n# Planes\n# ---------------------------------------------------------------------\ndef listar_planes(solo_activos: bool = True) -> pd.DataFrame:\n    q = _tabla("planes").select("*").order("sesiones")\n    if solo_activos:\n        q = q.eq("activo", True)\n    return _df(q.execute().data)\n\n\ndef crear_plan(nombre, sesiones, vigencia_dias, precio, descripcion=None):\n    return _tabla("planes").insert({\n        "nombre": nombre.strip().upper(),\n        "sesiones": int(sesiones),\n        "vigencia_dias": int(vigencia_dias),\n        "precio": float(precio),\n        "descripcion": descripcion,\n    }).execute().data\n\n\ndef plan(plan_id: str) -> dict | None:\n    r = _tabla("planes").select("*").eq("id", plan_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef eliminar_plan(plan_id: str) -> None:\n    """Borra el plan del catalogo.\n\n    Solo si nunca se vendio. Si ya tiene pedidos, borrarlo dejaria esos\n    pedidos apuntando a un plan que no existe, asi que en ese caso se\n    desactiva: desaparece al vender pero el historial queda intacto.\n    """\n    usos = paquetes_con_plan(plan_id)\n    if usos:\n        raise ValueError(\n            f"Este plan ya se vendio {usos} {\'vez\' if usos == 1 else \'veces\'}. "\n            "No se puede borrar sin romper esos pedidos. Usa \'Ocultar del catalogo\'."\n        )\n    _tabla("planes").delete().eq("id", plan_id).execute()\n\n\ndef paquetes_con_plan(plan_id: str) -> int:\n    """Cuantas ventas usan este plan. Sirve para avisar antes de editarlo."""\n    r = (_tabla("paquetes").select("id", count="exact")\n         .eq("plan_id", plan_id).execute())\n    return r.count or 0\n\n\ndef actualizar_plan(plan_id: str, cambios: dict):\n    return _tabla("planes").update(cambios).eq("id", plan_id).execute().data\n\n\n# ---------------------------------------------------------------------\n# Grupos (sede + horario + genero + dias de entrenamiento)\n# ---------------------------------------------------------------------\ndef listar_grupos(solo_activos: bool = True) -> pd.DataFrame:\n    try:\n        q = _tabla("grupos").select("*").order("sede")\n        if solo_activos:\n            q = q.eq("activo", True)\n        return _df(q.execute().data)\n    except Exception:\n        # Si la migracion 009 todavia no se corrio, no romper la pantalla\n        return pd.DataFrame()\n\n\ndef grupo(grupo_id: str) -> dict | None:\n    r = _tabla("grupos").select("*").eq("id", grupo_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef crear_grupo(nombre, sede, genero, hora, dias):\n    return _tabla("grupos").insert({\n        "nombre": nombre.strip().upper(),\n        "sede": sede.strip().upper(),\n        "genero": genero,\n        "hora": hora,\n        "dias": dias,\n        "dias_por_semana": len(dias.split()),\n    }).execute().data\n\n\ndef actualizar_grupo(grupo_id: str, cambios: dict):\n    return _tabla("grupos").update(cambios).eq("id", grupo_id).execute().data\n\n\n# ---------------------------------------------------------------------\n# Alumnos\n# ---------------------------------------------------------------------\ndef crear_alumno(datos: dict):\n    limpio = {k: _iso(v) for k, v in datos.items() if v not in (None, "")}\n    return _tabla("alumnos").insert(limpio).execute().data\n\n\ndef actualizar_alumno(alumno_id: str, cambios: dict):\n    limpio = {k: _iso(v) for k, v in cambios.items()}\n    return _tabla("alumnos").update(limpio).eq("id", alumno_id).execute().data\n\n\ndef alumno(alumno_id: str) -> dict | None:\n    r = _tabla("alumnos").select("*").eq("id", alumno_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef panel_alumnos(solo_activos: bool = True) -> pd.DataFrame:\n    """Una fila por alumno con su paquete mas relevante (vista v_alumnos_estado)."""\n    q = _tabla("v_alumnos_estado").select("*").order("apellidos")\n    if solo_activos:\n        q = q.eq("activo", True)\n    return _df(q.execute().data)\n\n\ndef buscar_alumnos(texto: str, limite: int = 25) -> pd.DataFrame:\n    """Busca por nombre, apellido, codigo, DNI o telefono."""\n    texto = (texto or "").strip()\n    if not texto:\n        return panel_alumnos().head(limite)\n    patron = f"%{texto}%"\n    filtro = ",".join([\n        f"nombres.ilike.{patron}",\n        f"apellidos.ilike.{patron}",\n        f"codigo.ilike.{patron}",\n        f"dni.ilike.{patron}",\n        f"telefono.ilike.{patron}",\n    ])\n    rows = _tabla("v_alumnos_estado").select("*").or_(filtro).limit(limite).execute().data\n    return _df(rows)\n\n\ndef identificar(texto: str) -> list[dict]:\n    """Busqueda del kiosco: DNI o codigo exacto primero, luego nombre parcial."""\n    texto = (texto or "").strip()\n    if not texto:\n        return []\n\n    digitos = logic.solo_digitos(texto)\n    if digitos and len(digitos) >= 8:\n        exacto = _tabla("v_alumnos_estado").select("*").or_(\n            f"dni.eq.{digitos},telefono.eq.{digitos}"\n        ).execute().data\n        if exacto:\n            return exacto\n\n    codigo = texto.upper()\n    if codigo.startswith("FC-"):\n        exacto = _tabla("v_alumnos_estado").select("*").eq("codigo", codigo).execute().data\n        if exacto:\n            return exacto\n\n    patron = f"%{texto}%"\n    return _tabla("v_alumnos_estado").select("*").or_(\n        f"nombres.ilike.{patron},apellidos.ilike.{patron},codigo.ilike.{patron}"\n    ).limit(8).execute().data\n\n\n# ---------------------------------------------------------------------\n# Paquetes\n# ---------------------------------------------------------------------\ndef paquetes_de(alumno_id: str) -> pd.DataFrame:\n    rows = (_tabla("v_paquetes").select("*")\n            .eq("alumno_id", alumno_id).order("fecha_inicio", desc=True).execute().data)\n    return _df(rows)\n\n\ndef paquete(paquete_id: str) -> dict | None:\n    r = _tabla("v_paquetes").select("*").eq("id", paquete_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef paquete_vigente(alumno_id: str) -> dict | None:\n    """El paquete que manda hoy: ACTIVO o CONGELADO, el que vence primero."""\n    rows = (_tabla("v_paquetes").select("*")\n            .eq("alumno_id", alumno_id)\n            .in_("estado_real", ["ACTIVO", "CONGELADO"])\n            .order("fecha_fin").execute().data)\n    return rows[0] if rows else None\n\n\ndef ultimo_paquete(alumno_id: str) -> dict | None:\n    rows = (_tabla("v_paquetes").select("*")\n            .eq("alumno_id", alumno_id).order("fecha_fin", desc=True).limit(1).execute().data)\n    return rows[0] if rows else None\n\n\ndef listar_paquetes(estados: list[str] | None = None) -> pd.DataFrame:\n    q = _tabla("v_paquetes").select("*").order("fecha_fin", desc=True)\n    if estados:\n        q = q.in_("estado_real", estados)\n    return _df(q.execute().data)\n\n\ndef crear_paquete(alumno_id, plan: dict, fecha_inicio: date, precio: float,\n                  medio_pago: str, pagado: bool = True, observacion: str | None = None,\n                  fecha_pedido: date | None = None, sede: str | None = None,\n                  dias_asiste: str | None = None, vendedor: str | None = None,\n                  tipo: str = "NUEVO", sesiones: int | None = None,\n                  vigencia_dias: int | None = None, grupo_id: str | None = None):\n    """Registra la venta con todos los datos del pedido.\n\n    sesiones y vigencia_dias permiten ajustar el plan para una venta puntual\n    (por ejemplo, regalar dos sesiones) sin tocar el catalogo.\n    """\n    total = int(sesiones or plan["sesiones"])\n    dias = int(vigencia_dias or plan["vigencia_dias"])\n    # El plan termina cuando se acaban las sesiones, contando solo los dias\n    # que entrena ese grupo. Si no hay dias, cae al metodo de dias corridos.\n    fecha_fin = logic.fecha_fin_por_calendario(fecha_inicio, total,\n                                               dias_asiste, dias)\n\n    return _tabla("paquetes").insert({\n        "alumno_id": alumno_id,\n        "plan_id": plan.get("id"),\n        "plan_nombre": plan["nombre"],\n        "sesiones_totales": total,\n        "fecha_pedido": (fecha_pedido or fecha_inicio).isoformat(),\n        "fecha_inicio": fecha_inicio.isoformat(),\n        "fecha_fin": fecha_fin.isoformat(),\n        "precio": float(precio),\n        "medio_pago": medio_pago,\n        "pagado": bool(pagado),\n        "sede": sede,\n        "dias_asiste": dias_asiste,\n        "grupo_id": grupo_id,\n        "vendedor": vendedor,\n        "tipo": tipo,\n        "observacion": observacion,\n    }).execute().data\n\n\ndef actualizar_paquete(paquete_id: str, cambios: dict):\n    limpio = {k: _iso(v) for k, v in cambios.items()}\n    return _tabla("paquetes").update(limpio).eq("id", paquete_id).execute().data\n\n\ndef siguiente_pedido() -> int:\n    """Solo para mostrarlo antes de guardar; el numero real lo pone la base."""\n    r = (_tabla("paquetes").select("nro_pedido")\n         .order("nro_pedido", desc=True).limit(1).execute().data)\n    return (r[0]["nro_pedido"] or 0) + 1 if r else 1\n\n\ndef vendedores() -> list:\n    """Los vendedores que ya se usaron, para no escribirlos de nuevo."""\n    r = _tabla("paquetes").select("vendedor").execute().data or []\n    return sorted({(x.get("vendedor") or "").strip() for x in r if x.get("vendedor")})\n\n\ndef sedes() -> list:\n    r = _tabla("alumnos").select("sede").execute().data or []\n    vistas = {(x.get("sede") or "").strip() for x in r if x.get("sede")}\n    return sorted(vistas | {"SURQUILLO"})\n\n\ndef cancelar_paquete(paquete_id: str, motivo: str):\n    return _tabla("paquetes").update({\n        "estado": "CANCELADO",\n        "observacion": motivo,\n    }).eq("id", paquete_id).execute().data\n\n\n# ---------------------------------------------------------------------\n# Congelamientos\n# ---------------------------------------------------------------------\ndef congelar(paquete_id: str, alumno_id: str, motivo: str, detalle: str,\n             desde: date, alta_prevista: date | None = None):\n    """Pausa el paquete.\n\n    alta_prevista es cuando se espera que vuelva. Es solo una estimacion:\n    la fecha real se confirma al reactivar, y es esa la que manda.\n    """\n    _tabla("congelamientos").insert({\n        "paquete_id": paquete_id,\n        "alumno_id": alumno_id,\n        "motivo": motivo,\n        "detalle": detalle,\n        "fecha_inicio": desde.isoformat(),\n        "fecha_alta_prevista": alta_prevista.isoformat() if alta_prevista else None,\n    }).execute()\n    _tabla("paquetes").update({"estado": "CONGELADO"}).eq("id", paquete_id).execute()\n\n\ndef reactivar(congelamiento_id: str, hasta: date) -> int:\n    """Cierra el congelamiento y le devuelve al alumno los dias perdidos."""\n    cong = _tabla("congelamientos").select("*").eq("id", congelamiento_id).limit(1).execute().data\n    if not cong:\n        raise ValueError("No se encontro el congelamiento.")\n    cong = cong[0]\n\n    inicio = logic.a_fecha(cong["fecha_inicio"])\n    dias = logic.dias_congelamiento(inicio, hasta)\n\n    vista = paquete(cong["paquete_id"])\n    pq = _tabla("paquetes").select("*").eq("id", cong["paquete_id"]).limit(1).execute().data[0]\n\n    # La nueva fecha de fin es la de su ultima sesion contando desde el alta.\n    # Sumar dias corridos podria dejarla en un dia que su grupo no entrena.\n    restantes = int(vista["sesiones_restantes"]) if vista else 0\n    dias_grupo = (vista or {}).get("dias_asiste")\n    nueva_fin = None\n    if restantes > 0 and dias_grupo:\n        nueva_fin = logic.fecha_de_sesion(hasta, restantes, dias_grupo)\n    if not nueva_fin:\n        nueva_fin = logic.extender(logic.a_fecha(pq["fecha_fin"]), dias)\n\n    _tabla("paquetes").update({\n        "estado": "ACTIVO",\n        "fecha_fin": nueva_fin.isoformat(),\n        "dias_congelados": int(pq.get("dias_congelados") or 0) + dias,\n    }).eq("id", pq["id"]).execute()\n\n    _tabla("congelamientos").update({\n        "fecha_fin": hasta.isoformat(),\n        "dias_aplicados": dias,\n        "activo": False,\n    }).eq("id", congelamiento_id).execute()\n\n    return dias\n\n\ndef congelamientos(activos: bool | None = True) -> pd.DataFrame:\n    q = _tabla("congelamientos").select("*, alumnos(codigo,nombres,apellidos,telefono)")\n    if activos is not None:\n        q = q.eq("activo", activos)\n    rows = q.order("fecha_inicio", desc=True).execute().data or []\n    for r in rows:\n        a = r.pop("alumnos", None) or {}\n        r["codigo"] = a.get("codigo")\n        r["alumno"] = f"{a.get(\'nombres\',\'\')} {a.get(\'apellidos\',\'\')}".strip()\n        r["telefono"] = a.get("telefono")\n    return _df(rows)\n\n\ndef congelados_que_vuelven(hasta: date) -> pd.DataFrame:\n    """Congelamientos cuya fecha prevista de alta ya llego o esta por llegar."""\n    try:\n        rows = (_tabla("congelamientos")\n                .select("*, alumnos(codigo,nombres,apellidos,telefono)")\n                .eq("activo", True)\n                .lte("fecha_alta_prevista", hasta.isoformat())\n                .order("fecha_alta_prevista").execute().data) or []\n    except Exception:\n        return pd.DataFrame()\n    for r in rows:\n        a = r.pop("alumnos", None) or {}\n        r["codigo"] = a.get("codigo")\n        r["alumno"] = f"{a.get(\'nombres\',\'\')} {a.get(\'apellidos\',\'\')}".strip()\n        r["telefono"] = a.get("telefono")\n    return _df(rows)\n\n\ndef congelamiento_abierto(paquete_id: str) -> dict | None:\n    r = (_tabla("congelamientos").select("*")\n         .eq("paquete_id", paquete_id).eq("activo", True).limit(1).execute().data)\n    return r[0] if r else None\n\n\n# ---------------------------------------------------------------------\n# Asistencias\n# ---------------------------------------------------------------------\ndef ya_marco_hoy(alumno_id: str, fecha: date | None = None) -> bool:\n    fecha = fecha or logic.hoy()\n    r = (_tabla("asistencias").select("id")\n         .eq("alumno_id", alumno_id).eq("fecha", fecha.isoformat())\n         .eq("anulada", False).limit(1).execute().data)\n    return bool(r)\n\n\ndef marcar_asistencia(alumno_id: str, paquete_id: str, sede: str | None = None,\n                      origen: str = "KIOSCO", fecha: date | None = None):\n    payload = {\n        "alumno_id": alumno_id,\n        "paquete_id": paquete_id,\n        "sede": sede,\n        "origen": origen,\n    }\n    if fecha:\n        payload["fecha"] = fecha.isoformat()\n    return _tabla("asistencias").insert(payload).execute().data\n\n\ndef anular_asistencia(asistencia_id: str, quien: str = "admin"):\n    """Al anular, la sesion vuelve automaticamente al saldo del alumno."""\n    return _tabla("asistencias").update({\n        "anulada": True, "anulada_por": quien,\n    }).eq("id", asistencia_id).execute().data\n\n\ndef asistencias(desde: date, hasta: date, incluir_anuladas: bool = False) -> pd.DataFrame:\n    q = (_tabla("v_asistencias").select("*")\n         .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat()))\n    if not incluir_anuladas:\n        q = q.eq("anulada", False)\n    return _df(q.order("fecha", desc=True).order("hora", desc=True).execute().data)\n\n\ndef registrar_bloqueo(alumno_id: str | None, texto: str, motivo: str):\n    """Deja constancia de quien quiso entrenar sin paquete valido."""\n    return _tabla("bloqueos").insert({\n        "alumno_id": alumno_id, "texto": texto, "motivo": motivo,\n    }).execute().data\n\n\ndef bloqueos(desde: date, hasta: date) -> pd.DataFrame:\n    rows = (_tabla("bloqueos").select("*, alumnos(codigo,nombres,apellidos,telefono)")\n            .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat())\n            .order("fecha", desc=True).order("hora", desc=True).execute().data) or []\n    for r in rows:\n        a = r.pop("alumnos", None) or {}\n        r["codigo"] = a.get("codigo")\n        r["alumno"] = f"{a.get(\'nombres\',\'\')} {a.get(\'apellidos\',\'\')}".strip() or r.get("texto")\n        r["telefono"] = a.get("telefono")\n    return _df(rows)\n'


MIGRACION_SQL = '-- =====================================================================\n-- FUTCROSS | Migracion 012 - Fecha prevista de alta\n--\n-- Al congelar por lesion o enfermedad casi siempre se sabe cuando vuelve\n-- ("un mes de reposo"). Guardar esa fecha desde el inicio permite avisar\n-- cuando le toca volver, en vez de esperar a que alguien se acuerde.\n--\n-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.\n-- =====================================================================\n\nalter table congelamientos\n    add column if not exists fecha_alta_prevista date;\n\ncomment on column congelamientos.fecha_alta_prevista is\n    \'Cuando se espera que vuelva. La fecha real de alta va en fecha_fin.\';\n\ncreate index if not exists ix_congelamientos_alta\n    on congelamientos (fecha_alta_prevista) where activo;\n'


# ---------------------------------------------------------------------
# Utilidades de archivo
# ---------------------------------------------------------------------
def leer(ruta):
    """Devuelve (texto con \\n, salto de linea original)."""
    datos = ruta.read_bytes()
    salto = "\r\n" if b"\r\n" in datos else "\n"
    return datos.decode("utf-8").replace("\r\n", "\n"), salto


def escribir(ruta, texto, salto):
    ruta.write_bytes(texto.replace("\n", salto).encode("utf-8"))


def respaldar(ruta):
    CARPETA_BACKUP.mkdir(parents=True, exist_ok=True)
    destino = CARPETA_BACKUP / ruta.name
    if not destino.exists():
        shutil.copy2(ruta, destino)
    return destino


def error(mensaje):
    print("")
    print("  ERROR: " + mensaje)
    print("")
    sys.exit(1)


# ---------------------------------------------------------------------
def revertir():
    app = Path("app.py")
    tema = Path("db.py")
    origen_app = CARPETA_BACKUP / "app.py"
    origen_tema = CARPETA_BACKUP / "theme.py"

    if not origen_app.exists() or not origen_tema.exists():
        error("No hay respaldos en " + str(CARPETA_BACKUP) + ". Nada que revertir.")

    shutil.copy2(origen_app, app)
    shutil.copy2(origen_tema, tema)
    print("")
    print("  Revertido. app.py y theme.py volvieron a la version anterior.")
    print("")


def aplicar():
    app = Path("app.py")
    tema = Path("db.py")

    if not app.exists() or not tema.exists():
        error(
            "No encuentro app.py y db.py en esta carpeta.\n"
            "         Parate en la carpeta admin-streamlit y vuelve a intentar:\n"
            "         cd admin-streamlit"
        )

    texto_app, salto_app = leer(app)
    _, salto_tema = leer(tema)

    # ---------------------------------------------------------- idempotencia
    if MARCA_APLICADO in texto_app:
        print("")
        print("  El parche " + PARCHE + " ya estaba aplicado. No se toco nada.")
        print("")
        return

    if MARCA_ORIGINAL not in texto_app:
        error("Faltan los parches 001 a 005. Aplicalos primero, en orden.")

    # ------------------------------------------------ verificar antes de tocar
    # Primero comprobamos que TODOS los bloques calcen. Asi nunca queda el
    # archivo a medio parchear.
    faltantes = []
    for indice, (viejo, _) in enumerate(CAMBIOS_APP, start=1):
        apariciones = texto_app.count(viejo)
        if apariciones != 1:
            faltantes.append((indice, apariciones))

    if faltantes:
        print("")
        print("  No se aplico nada. Estos bloques no calzan con tu app.py:")
        for indice, apariciones in faltantes:
            estado = "no aparece" if apariciones == 0 else str(apariciones) + " veces"
            print("    bloque " + str(indice) + ": " + estado)
        error("Tu app.py fue modificado. Usa el ZIP completo.")

    # ------------------------------------------------------------- respaldar
    respaldar(app)
    respaldar(tema)

    # -------------------------------------------------------------- aplicar
    for viejo, nuevo in CAMBIOS_APP:
        texto_app = texto_app.replace(viejo, nuevo, 1)

    escribir(app, texto_app, salto_app)
    escribir(tema, DB_NUEVO, salto_tema)

    # La migracion queda lista para copiar y pegar en Supabase
    escribir(Path("migracion-012.sql"), MIGRACION_SQL, salto_app)

    # ---------------------------------------------------------- verificacion
    final_app, _ = leer(app)
    final_tema, _ = leer(tema)
    sql = Path("migracion-012.sql")

    controles = [
        ("Fecha prevista al congelar", "Fecha prevista de alta" in final_app),
        ("Se guarda en la base", "fecha_alta_prevista" in final_tema),
        ("Precarga la fecha al reactivar", "por_defecto = prevista" in final_app),
        ("Avisa si ya debia volver", "Debia volver el" in final_app),
        ("Seccion de retornos en el Panel",
         "Vuelven de congelamiento" in final_app),
        ("Texto del congelamiento corregido",
         "recalcula el vencimiento" in final_app),
        ("Migracion SQL generada", sql.exists() and sql.stat().st_size > 300),
        ("Version 2.2", 'VERSION = "2.2"' in final_app),
    ]

    print("")
    print("  Parche " + PARCHE + " aplicado")
    print("  " + "-" * 46)
    for etiqueta, ok in controles:
        print("  [" + ("OK" if ok else "  ") + "]  " + etiqueta)

    if not all(ok for _, ok in controles):
        error("Alguna verificacion fallo. Revisa " + str(CARPETA_BACKUP))

    print("  " + "-" * 46)
    print("  Respaldo en: " + str(CARPETA_BACKUP))
    print("")
    print("  PASO OBLIGATORIO antes de usarlo:")
    print("    1. Abre migracion-012.sql (quedo en esta carpeta)")
    print("    2. Copia todo y pegalo en Supabase > SQL Editor > Run")
    print("    3. Recien ahi reinicia Streamlit")
    print("")


if __name__ == "__main__":
    if "--revertir" in sys.argv:
        revertir()
    else:
        aplicar()