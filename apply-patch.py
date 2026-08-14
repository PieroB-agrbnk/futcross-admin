"""
FUTCROSS | Patch 015 - Que dias asiste cada alumno

Requiere los parches 001 a 014 aplicados.

1. LOS DIAS SON DEL ALUMNO, NO DEL GRUPO
   El grupo dice que dias abre (Surquillo entrena lunes, miercoles y
   viernes). El plan dice cuantos usa por semana (el basico, dos).
   Pero cuales de esos dos dias va cada alumno es decision suya, y eso
   no se podia registrar: a todos se les asignaban los tres dias del
   grupo, y el vencimiento salia mal.

   Ahora al inscribir o vender aparecen los dias del grupo como casillas
   y se marcan los que corresponden. Si el plan es de 2 dias por semana,
   propone 2; si marcas una cantidad distinta, avisa pero deja hacerlo
   (hay excepciones) y calcula el vencimiento con lo que marcaste.

   En la pantalla de inscripcion el plan ahora va antes del grupo,
   porque de el sale cuantos dias se pueden marcar.

2. PLANES CORTOS
   Se agregan CLASE SUELTA (1 sesion) y PAQUETE 4 CLASES al catalogo.
   Quedan con precio 0 para que los completes en la pantalla Planes.

3. COMPRAR UN PAQUETE SIN HABER TERMINADO EL ANTERIOR
   Al vender a alguien que ya tiene un paquete corriendo, el sistema
   propone que el nuevo arranque al dia siguiente de la ultima sesion
   del actual. Asi las sesiones se suman en vez de correr en paralelo,
   y avisa el total combinado: "primero termina sus 6 pendientes y
   despues las 12 nuevas: le quedaran 18 sesiones".

   Si se elige una fecha que se superpone, tambien avisa y explica que
   el kiosco descuenta primero el paquete que termina antes.

   La ficha del alumno ahora muestra el total sumando sus paquetes
   encolados, no solo el del primero.

IMPORTANTE
  Necesita que ANTES corras migracion-015.sql en Supabase. El archivo se
  genera solo al aplicar el parche, en esta misma carpeta.
"""

import shutil
import sys
from pathlib import Path

PARCHE = "015-dias-por-alumno"
CARPETA_BACKUP = Path("respaldos") / PARCHE

# Si esta marca ya esta en app.py, el parche ya se aplico
MARCA_APLICADO = "dias_del_plan"
MARCA_ORIGINAL = "reactivar_automaticos"


CAMBIOS_APP = [
    (
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.4"\n\n',
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.5"\n\n',
    ),
    (
        '\ndef selector_de_grupo(etiqueta="Grupo", clave=None, grupo_actual=None):\n    """Devuelve (grupo_id, dias, texto). Los grupos son sede + horario + genero,\n    y de ahi salen los dias de entrenamiento que definen el vencimiento."""\n    grupos = db.listar_grupos()\n',
        '\ndef selector_de_grupo(etiqueta="Grupo", clave=None, grupo_actual=None,\n                      dias_previos=None, dias_del_plan=None):\n    """Elige el grupo y, dentro de el, que dias asiste el alumno.\n\n    El grupo dice que dias hay disponibles (Surquillo abre lun, mie y vie).\n    El plan dice cuantos usa por semana (el basico, dos). Cual de esos dias\n    va cada alumno es decision suya, asi que se pregunta.\n\n    Devuelve (grupo_id, dias_elegidos, texto).\n    """\n    grupos = db.listar_grupos()\n',
    ),
    (
        '                break\n    elegido = st.selectbox(etiqueta, llaves, index=indice, key=clave)\n    g = opciones[elegido]\n',
        '                break\n\n    c1, c2 = st.columns([1.4, 1.6])\n    elegido = c1.selectbox(etiqueta, llaves, index=indice, key=clave)\n    g = opciones[elegido]\n',
    ),
    (
        '    g = opciones[elegido]\n    return g["id"], g["dias"], f"{g[\'sede\']} {g[\'hora\']} - {logic.frecuencia(g[\'dias\'])}"\n\n',
        '    g = opciones[elegido]\n    disponibles = [d for d in str(g["dias"]).split() if d in DIAS_SEMANA]\n\n    # Que dias viene: por defecto los que ya tenia, o los primeros que\n    # alcancen para la frecuencia del plan.\n    previos = [d for d in (dias_previos or "").split() if d in disponibles]\n    if not previos:\n        previos = disponibles[:dias_del_plan] if dias_del_plan else disponibles\n\n    elegidos = c2.multiselect(\n        "Dias que asiste", disponibles, default=previos,\n        key=f"{clave}_dias" if clave else None,\n        help=f"El grupo entrena {\' \'.join(disponibles)}. "\n             "Marca solo los dias que viene este alumno.")\n\n    if dias_del_plan and elegidos and len(elegidos) != dias_del_plan:\n        c2.warning(f"Este plan es de {dias_del_plan} "\n                   f"{\'dia\' if dias_del_plan == 1 else \'dias\'} por semana y "\n                   f"marcaste {len(elegidos)}. El vencimiento se calcula con "\n                   "los dias marcados.")\n\n    # Se ordenan como la semana, no como se hizo clic\n    orden = {d: i for i, d in enumerate(DIAS_SEMANA)}\n    dias = " ".join(sorted(elegidos, key=lambda d: orden[d]))\n    texto = f"{g[\'sede\']} {g[\'hora\']}"\n    if dias:\n        texto += f" - {logic.frecuencia(dias)}"\n    return g["id"], dias, texto\n\n',
    ),
    (
        '\n            st.markdown("**Grupo al que entra**")\n            grupo_id, dias_grupo, detalle = selector_de_grupo(\n                "Sede, horario y genero", clave="grupo_nuevo_alumno")\n            if detalle:\n                st.caption(detalle)\n            sede = dias = horario = turno = None\n\n            emergencia = c2.text_input("Contacto de emergencia")\n',
        '\n            emergencia = c2.text_input("Contacto de emergencia")\n',
    ),
    (
        '            # paso para no obligar a ir despues a la pantalla de Paquetes.\n            st.markdown("**Plan que contrata**")\n',
        '            # paso para no obligar a ir despues a la pantalla de Paquetes.\n            # El plan va antes del grupo porque de el sale cuantos dias por\n            # semana entrena, y eso define que dias se pueden marcar.\n            st.markdown("**Plan que contrata**")\n',
    ),
    (
        '            inicio_plan = precio_plan = medio_plan = vendedor_plan = None\n            if not planes_disp.empty:\n',
        '            inicio_plan = precio_plan = medio_plan = vendedor_plan = None\n            frecuencia_plan = None\n            if not planes_disp.empty:\n',
    ),
    (
        '                                            format="DD/MM/YYYY")\n\n',
        '                                            format="DD/MM/YYYY")\n                frecuencia_plan = plan_elegido.get("dias_por_semana")\n                if frecuencia_plan is not None and pd.isna(frecuencia_plan):\n                    frecuencia_plan = None\n\n',
    ),
    (
        '\n                fin_plan = logic.fecha_fin_por_calendario(\n',
        '\n            st.markdown("**Grupo y dias que entrena**")\n            grupo_id, dias_grupo, detalle = selector_de_grupo(\n                "Sede, horario y genero", clave="grupo_nuevo_alumno",\n                dias_del_plan=int(frecuencia_plan) if frecuencia_plan else None)\n            if detalle:\n                st.caption(detalle)\n            sede = dias = horario = turno = None\n\n            if plan_elegido is not None:\n                fin_plan = logic.fecha_fin_por_calendario(\n',
    ),
    (
        '                if dias_grupo:\n                    st.caption(\n                        f"{plan_elegido[\'sesiones\']} sesiones entrenando "\n                        f"{logic.frecuencia(dias_grupo)}. Ultima sesion el "\n                        f"{fecha_larga(fin_plan)}."\n                    )\n',
        '                if dias_grupo:\n                    st.info(\n                        f"**{plan_elegido[\'sesiones\']} sesiones** entrenando "\n                        f"{logic.frecuencia(dias_grupo)} ({dias_grupo}). "\n                        f"Ultima sesion el **{fecha_larga(fin_plan)}**."\n                    )\n',
    ),
    (
        '                    )\n\n',
        '                    )\n\n            if plan_elegido is not None:\n\n',
    ),
    (
        '\n        st.markdown("**Grupo**")\n        grupo_id, dias_grupo, detalle = selector_de_grupo(\n',
        '\n        st.markdown("**Grupo y dias que entrena**")\n        grupo_id, dias_grupo, detalle = selector_de_grupo(\n',
    ),
    (
        '            "Sede, horario y genero", clave="grupo_editar",\n            grupo_actual=a.get("grupo_id"))\n        if detalle:\n',
        '            "Sede, horario y genero", clave="grupo_editar",\n            grupo_actual=a.get("grupo_id"),\n            dias_previos=texto("dias_asiste"))\n        if detalle:\n',
    ),
    (
        '        p = vigente.iloc[0]\n        c2.metric("Sesiones restantes", f"{p[\'sesiones_restantes\']} de {p[\'sesiones_totales\']}")\n        c3.metric("Vence", logic.a_fecha(p["fecha_fin"]).strftime("%d/%m/%Y"),\n',
        '        p = vigente.iloc[0]\n        # Si tiene varios paquetes encolados, lo que importa es el total\n        por_consumir = paquetes[paquetes["estado_real"].isin(["ACTIVO", "CONGELADO"])]\n        total_pend = int(por_consumir["sesiones_restantes"].sum())\n        if len(por_consumir) > 1:\n            c2.metric("Sesiones restantes", total_pend,\n                      f"en {len(por_consumir)} paquetes")\n        else:\n            c2.metric("Sesiones restantes",\n                      f"{p[\'sesiones_restantes\']} de {p[\'sesiones_totales\']}")\n        c3.metric("Vence", logic.a_fecha(p["fecha_fin"]).strftime("%d/%m/%Y"),\n',
    ),
    (
        '                    f"Este alumno ya tiene un paquete {vigente[\'estado_real\'].lower()}: "\n                    f"{vigente[\'plan_nombre\']}, le quedan {vigente[\'sesiones_restantes\']} sesiones "\n                    f"y vence el {logic.a_fecha(vigente[\'fecha_fin\']).strftime(\'%d/%m/%Y\')}. "\n                    "Si vendes uno nuevo, el sistema consumira primero el que vence antes."\n                )\n',
        '                    f"Este alumno ya tiene un paquete {vigente[\'estado_real\'].lower()}: "\n                    f"{vigente[\'plan_nombre\']}, le quedan "\n                    f"{vigente[\'sesiones_restantes\']} sesiones y su ultima cae el "\n                    f"{logic.a_fecha(vigente[\'fecha_fin\']).strftime(\'%d/%m/%Y\')}. "\n                    "El nuevo se puede encolar para que arranque cuando termine ese."\n                )\n',
    ),
    (
        '                                             help="Cuando se cerro la venta")\n                inicio = c3.date_input("Inicio del plan", value=logic.hoy(),\n                                       format="DD/MM/YYYY",\n                                       help="Puede ser posterior a la fecha del pedido")\n\n',
        '                                             help="Cuando se cerro la venta")\n\n',
    ),
    (
        '\n                st.markdown("**Grupo**")\n                grupo_previo = datos_alumno.get("grupo_id")\n',
        '\n                # Si ya tiene un paquete corriendo, lo natural es que el nuevo\n                # arranque al dia siguiente de la ultima sesion del actual.\n                # Asi las sesiones se suman en vez de correr en paralelo.\n                if vigente is not None:\n                    sugerido = logic.a_fecha(vigente["fecha_fin"]) + timedelta(days=1)\n                    sugerido = max(sugerido, logic.hoy())\n                else:\n                    sugerido = logic.hoy()\n\n                inicio = c3.date_input(\n                    "Inicio del plan", value=sugerido, format="DD/MM/YYYY",\n                    help="Si ya tiene un paquete, se propone el dia siguiente al "\n                         "que termina, para que las sesiones se sumen")\n\n                st.markdown("**Grupo y dias que entrena**")\n                grupo_previo = datos_alumno.get("grupo_id")\n',
    ),
    (
        '                    grupo_previo = None\n                grupo_id, dias_grupo, detalle = selector_de_grupo(\n',
        '                    grupo_previo = None\n                dias_previos = datos_alumno.get("dias_asiste")\n                if dias_previos is None or (isinstance(dias_previos, float)\n                                            and pd.isna(dias_previos)):\n                    dias_previos = ""\n                frec = plan.get("dias_por_semana")\n                if frec is not None and pd.isna(frec):\n                    frec = None\n                grupo_id, dias_grupo, detalle = selector_de_grupo(\n',
    ),
    (
        '                    "Sede, horario y genero", clave="grupo_venta",\n                    grupo_actual=grupo_previo)\n                if detalle:\n',
        '                    "Sede, horario y genero", clave="grupo_venta",\n                    grupo_actual=grupo_previo, dias_previos=str(dias_previos),\n                    dias_del_plan=int(frec) if frec else None)\n                if detalle:\n',
    ),
    (
        '                obs = st.text_input("Observacion", placeholder="Opcional")\n\n',
        '                obs = st.text_input("Observacion", placeholder="Opcional")\n\n                if vigente is not None:\n                    fin_actual = logic.a_fecha(vigente["fecha_fin"])\n                    restantes_actual = int(vigente["sesiones_restantes"])\n                    if inicio > fin_actual:\n                        st.success(\n                            f"Se encola: primero termina sus {restantes_actual} "\n                            f"sesiones pendientes (hasta el {fecha_larga(fin_actual)}) "\n                            f"y despues corren las {sesiones} nuevas. En total le "\n                            f"quedaran **{restantes_actual + int(sesiones)} sesiones**."\n                        )\n                    else:\n                        st.warning(\n                            f"Los dos paquetes van a estar vigentes a la vez. El "\n                            f"kiosco descuenta primero el que termina antes "\n                            f"({fecha_larga(fin_actual)}). Si querias que se sumen "\n                            f"uno detras del otro, pon el inicio despues de esa fecha."\n                        )\n\n',
    ),
]


DB_NUEVO = '"""\nFUTCROSS | Capa de datos sobre Supabase (PostgREST).\n\nTodas las consultas pasan por aca. Ninguna pantalla arma queries por su cuenta.\n"""\n\nfrom __future__ import annotations\n\nimport os\nfrom datetime import date\n\nimport pandas as pd\nimport streamlit as st\nfrom supabase import Client, create_client\n\nimport logic\n\n\n# ---------------------------------------------------------------------\n# Conexion\n# ---------------------------------------------------------------------\ndef secreto(clave: str, defecto=None):\n    """Busca primero en .streamlit/secrets.toml y luego en variables de entorno.\n\n    En local usamos secrets.toml; Hugging Face Spaces inyecta los secretos\n    como variables de entorno. Asi el mismo codigo sirve en los dos lados.\n    """\n    try:\n        if clave in st.secrets:\n            return st.secrets[clave]\n    except Exception:\n        pass\n    return os.environ.get(clave, defecto)\n\n\n@st.cache_resource(show_spinner=False)\ndef cliente() -> Client:\n    url = secreto("SUPABASE_URL")\n    key = secreto("SUPABASE_KEY")\n    if not url or not key:\n        st.error(\n            "Falta configurar la conexion a Supabase. "\n            "Crea el archivo `.streamlit/secrets.toml` con SUPABASE_URL y SUPABASE_KEY "\n            "(o cargalos en Settings > Secrets si ya desplegaste en la nube)."\n        )\n        st.stop()\n    return create_client(url, key)\n\n\ndef _tabla(nombre: str):\n    return cliente().table(nombre)\n\n\ndef _df(rows) -> pd.DataFrame:\n    return pd.DataFrame(rows or [])\n\n\ndef _iso(valor):\n    """Serializa fechas para PostgREST."""\n    return valor.isoformat() if isinstance(valor, date) else valor\n\n\n# ---------------------------------------------------------------------\n# Planes\n# ---------------------------------------------------------------------\ndef listar_planes(solo_activos: bool = True) -> pd.DataFrame:\n    q = _tabla("planes").select("*").order("sesiones")\n    if solo_activos:\n        q = q.eq("activo", True)\n    return _df(q.execute().data)\n\n\ndef crear_plan(nombre, sesiones, vigencia_dias, precio, descripcion=None):\n    return _tabla("planes").insert({\n        "nombre": nombre.strip().upper(),\n        "sesiones": int(sesiones),\n        "vigencia_dias": int(vigencia_dias),\n        "precio": float(precio),\n        "descripcion": descripcion,\n    }).execute().data\n\n\ndef plan(plan_id: str) -> dict | None:\n    r = _tabla("planes").select("*").eq("id", plan_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef eliminar_plan(plan_id: str) -> None:\n    """Borra el plan del catalogo.\n\n    Solo si nunca se vendio. Si ya tiene pedidos, borrarlo dejaria esos\n    pedidos apuntando a un plan que no existe, asi que en ese caso se\n    desactiva: desaparece al vender pero el historial queda intacto.\n    """\n    usos = paquetes_con_plan(plan_id)\n    if usos:\n        raise ValueError(\n            f"Este plan ya se vendio {usos} {\'vez\' if usos == 1 else \'veces\'}. "\n            "No se puede borrar sin romper esos pedidos. Usa \'Ocultar del catalogo\'."\n        )\n    _tabla("planes").delete().eq("id", plan_id).execute()\n\n\ndef paquetes_con_plan(plan_id: str) -> int:\n    """Cuantas ventas usan este plan. Sirve para avisar antes de editarlo."""\n    r = (_tabla("paquetes").select("id", count="exact")\n         .eq("plan_id", plan_id).execute())\n    return r.count or 0\n\n\ndef actualizar_plan(plan_id: str, cambios: dict):\n    return _tabla("planes").update(cambios).eq("id", plan_id).execute().data\n\n\n# ---------------------------------------------------------------------\n# Grupos (sede + horario + genero + dias de entrenamiento)\n# ---------------------------------------------------------------------\ndef listar_grupos(solo_activos: bool = True) -> pd.DataFrame:\n    try:\n        q = _tabla("grupos").select("*").order("sede")\n        if solo_activos:\n            q = q.eq("activo", True)\n        return _df(q.execute().data)\n    except Exception:\n        # Si la migracion 009 todavia no se corrio, no romper la pantalla\n        return pd.DataFrame()\n\n\ndef grupo(grupo_id: str) -> dict | None:\n    r = _tabla("grupos").select("*").eq("id", grupo_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef crear_grupo(nombre, sede, genero, hora, dias):\n    return _tabla("grupos").insert({\n        "nombre": nombre.strip().upper(),\n        "sede": sede.strip().upper(),\n        "genero": genero,\n        "hora": hora,\n        "dias": dias,\n        "dias_por_semana": len(dias.split()),\n    }).execute().data\n\n\ndef actualizar_grupo(grupo_id: str, cambios: dict):\n    return _tabla("grupos").update(cambios).eq("id", grupo_id).execute().data\n\n\n# ---------------------------------------------------------------------\n# Alumnos\n# ---------------------------------------------------------------------\ndef crear_alumno(datos: dict):\n    limpio = {k: _iso(v) for k, v in datos.items() if v not in (None, "")}\n    return _tabla("alumnos").insert(limpio).execute().data\n\n\ndef actualizar_alumno(alumno_id: str, cambios: dict):\n    limpio = {k: _iso(v) for k, v in cambios.items()}\n    return _tabla("alumnos").update(limpio).eq("id", alumno_id).execute().data\n\n\ndef alumno(alumno_id: str) -> dict | None:\n    r = _tabla("alumnos").select("*").eq("id", alumno_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef panel_alumnos(solo_activos: bool = True) -> pd.DataFrame:\n    """Una fila por alumno con su paquete mas relevante (vista v_alumnos_estado)."""\n    q = _tabla("v_alumnos_estado").select("*").order("apellidos")\n    if solo_activos:\n        q = q.eq("activo", True)\n    return _df(q.execute().data)\n\n\ndef buscar_alumnos(texto: str, limite: int = 25) -> pd.DataFrame:\n    """Busca por nombre, apellido, codigo, DNI o telefono."""\n    texto = (texto or "").strip()\n    if not texto:\n        return panel_alumnos().head(limite)\n    patron = f"%{texto}%"\n    filtro = ",".join([\n        f"nombres.ilike.{patron}",\n        f"apellidos.ilike.{patron}",\n        f"codigo.ilike.{patron}",\n        f"dni.ilike.{patron}",\n        f"telefono.ilike.{patron}",\n    ])\n    rows = _tabla("v_alumnos_estado").select("*").or_(filtro).limit(limite).execute().data\n    return _df(rows)\n\n\ndef identificar(texto: str) -> list[dict]:\n    """Busqueda del kiosco: DNI o codigo exacto primero, luego nombre parcial."""\n    texto = (texto or "").strip()\n    if not texto:\n        return []\n\n    digitos = logic.solo_digitos(texto)\n    if digitos and len(digitos) >= 8:\n        exacto = _tabla("v_alumnos_estado").select("*").or_(\n            f"dni.eq.{digitos},telefono.eq.{digitos}"\n        ).execute().data\n        if exacto:\n            return exacto\n\n    codigo = texto.upper()\n    if codigo.startswith("FC-"):\n        exacto = _tabla("v_alumnos_estado").select("*").eq("codigo", codigo).execute().data\n        if exacto:\n            return exacto\n\n    patron = f"%{texto}%"\n    return _tabla("v_alumnos_estado").select("*").or_(\n        f"nombres.ilike.{patron},apellidos.ilike.{patron},codigo.ilike.{patron}"\n    ).limit(8).execute().data\n\n\n# ---------------------------------------------------------------------\n# Paquetes\n# ---------------------------------------------------------------------\ndef paquetes_de(alumno_id: str) -> pd.DataFrame:\n    rows = (_tabla("v_paquetes").select("*")\n            .eq("alumno_id", alumno_id).order("fecha_inicio", desc=True).execute().data)\n    return _df(rows)\n\n\ndef paquete(paquete_id: str) -> dict | None:\n    r = _tabla("v_paquetes").select("*").eq("id", paquete_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef paquete_vigente(alumno_id: str) -> dict | None:\n    """El paquete que manda hoy: ACTIVO o CONGELADO, el que vence primero."""\n    rows = (_tabla("v_paquetes").select("*")\n            .eq("alumno_id", alumno_id)\n            .in_("estado_real", ["ACTIVO", "CONGELADO"])\n            .order("fecha_fin").execute().data)\n    return rows[0] if rows else None\n\n\ndef ultimo_paquete(alumno_id: str) -> dict | None:\n    rows = (_tabla("v_paquetes").select("*")\n            .eq("alumno_id", alumno_id).order("fecha_fin", desc=True).limit(1).execute().data)\n    return rows[0] if rows else None\n\n\ndef listar_paquetes(estados: list[str] | None = None) -> pd.DataFrame:\n    q = _tabla("v_paquetes").select("*").order("fecha_fin", desc=True)\n    if estados:\n        q = q.in_("estado_real", estados)\n    return _df(q.execute().data)\n\n\ndef crear_paquete(alumno_id, plan: dict, fecha_inicio: date, precio: float,\n                  medio_pago: str, pagado: bool = True, observacion: str | None = None,\n                  fecha_pedido: date | None = None, sede: str | None = None,\n                  dias_asiste: str | None = None, vendedor: str | None = None,\n                  tipo: str = "NUEVO", sesiones: int | None = None,\n                  vigencia_dias: int | None = None, grupo_id: str | None = None):\n    """Registra la venta con todos los datos del pedido.\n\n    sesiones y vigencia_dias permiten ajustar el plan para una venta puntual\n    (por ejemplo, regalar dos sesiones) sin tocar el catalogo.\n    """\n    total = int(sesiones or plan["sesiones"])\n    dias = int(vigencia_dias or plan["vigencia_dias"])\n    # El plan termina cuando se acaban las sesiones, contando solo los dias\n    # que entrena ese grupo. Si no hay dias, cae al metodo de dias corridos.\n    fecha_fin = logic.fecha_fin_por_calendario(fecha_inicio, total,\n                                               dias_asiste, dias)\n\n    return _tabla("paquetes").insert({\n        "alumno_id": alumno_id,\n        "plan_id": plan.get("id"),\n        "plan_nombre": plan["nombre"],\n        "sesiones_totales": total,\n        "fecha_pedido": (fecha_pedido or fecha_inicio).isoformat(),\n        "fecha_inicio": fecha_inicio.isoformat(),\n        "fecha_fin": fecha_fin.isoformat(),\n        "precio": float(precio),\n        "medio_pago": medio_pago,\n        "pagado": bool(pagado),\n        "sede": sede,\n        "dias_asiste": dias_asiste,\n        "grupo_id": grupo_id,\n        "vendedor": vendedor,\n        "tipo": tipo,\n        "observacion": observacion,\n    }).execute().data\n\n\ndef actualizar_paquete(paquete_id: str, cambios: dict):\n    limpio = {k: _iso(v) for k, v in cambios.items()}\n    return _tabla("paquetes").update(limpio).eq("id", paquete_id).execute().data\n\n\ndef siguiente_pedido() -> int:\n    """Solo para mostrarlo antes de guardar; el numero real lo pone la base."""\n    r = (_tabla("paquetes").select("nro_pedido")\n         .order("nro_pedido", desc=True).limit(1).execute().data)\n    return (r[0]["nro_pedido"] or 0) + 1 if r else 1\n\n\ndef vendedores() -> list:\n    """Los vendedores que ya se usaron, para no escribirlos de nuevo."""\n    r = _tabla("paquetes").select("vendedor").execute().data or []\n    return sorted({(x.get("vendedor") or "").strip() for x in r if x.get("vendedor")})\n\n\ndef sedes() -> list:\n    r = _tabla("alumnos").select("sede").execute().data or []\n    vistas = {(x.get("sede") or "").strip() for x in r if x.get("sede")}\n    return sorted(vistas | {"SURQUILLO"})\n\n\ndef cancelar_paquete(paquete_id: str, motivo: str):\n    return _tabla("paquetes").update({\n        "estado": "CANCELADO",\n        "observacion": motivo,\n    }).eq("id", paquete_id).execute().data\n\n\n# ---------------------------------------------------------------------\n# Congelamientos\n# ---------------------------------------------------------------------\ndef congelar(paquete_id: str, alumno_id: str, motivo: str, detalle: str,\n             desde: date, alta_prevista: date | None = None):\n    """Pausa el paquete.\n\n    alta_prevista es cuando se espera que vuelva. Es solo una estimacion:\n    la fecha real se confirma al reactivar, y es esa la que manda.\n    """\n    _tabla("congelamientos").insert({\n        "paquete_id": paquete_id,\n        "alumno_id": alumno_id,\n        "motivo": motivo,\n        "detalle": detalle,\n        "fecha_inicio": desde.isoformat(),\n        "fecha_alta_prevista": alta_prevista.isoformat() if alta_prevista else None,\n    }).execute()\n    _tabla("paquetes").update({"estado": "CONGELADO"}).eq("id", paquete_id).execute()\n\n\ndef reactivar(congelamiento_id: str, hasta: date) -> int:\n    """Cierra el congelamiento y le devuelve al alumno los dias perdidos."""\n    cong = _tabla("congelamientos").select("*").eq("id", congelamiento_id).limit(1).execute().data\n    if not cong:\n        raise ValueError("No se encontro el congelamiento.")\n    cong = cong[0]\n\n    inicio = logic.a_fecha(cong["fecha_inicio"])\n    dias = logic.dias_congelamiento(inicio, hasta)\n\n    vista = paquete(cong["paquete_id"])\n    pq = _tabla("paquetes").select("*").eq("id", cong["paquete_id"]).limit(1).execute().data[0]\n\n    # La nueva fecha de fin es la de su ultima sesion contando desde el alta.\n    # Sumar dias corridos podria dejarla en un dia que su grupo no entrena.\n    restantes = int(vista["sesiones_restantes"]) if vista else 0\n    dias_grupo = (vista or {}).get("dias_asiste")\n    nueva_fin = None\n    if restantes > 0 and dias_grupo:\n        nueva_fin = logic.fecha_de_sesion(hasta, restantes, dias_grupo)\n    if not nueva_fin:\n        nueva_fin = logic.extender(logic.a_fecha(pq["fecha_fin"]), dias)\n\n    _tabla("paquetes").update({\n        "estado": "ACTIVO",\n        "fecha_fin": nueva_fin.isoformat(),\n        "dias_congelados": int(pq.get("dias_congelados") or 0) + dias,\n    }).eq("id", pq["id"]).execute()\n\n    _tabla("congelamientos").update({\n        "fecha_fin": hasta.isoformat(),\n        "dias_aplicados": dias,\n        "activo": False,\n    }).eq("id", congelamiento_id).execute()\n\n    return dias\n\n\ndef congelamientos(activos: bool | None = True) -> pd.DataFrame:\n    q = _tabla("congelamientos").select("*, alumnos(codigo,nombres,apellidos,telefono)")\n    if activos is not None:\n        q = q.eq("activo", activos)\n    rows = q.order("fecha_inicio", desc=True).execute().data or []\n    for r in rows:\n        a = r.pop("alumnos", None) or {}\n        r["codigo"] = a.get("codigo")\n        r["alumno"] = f"{a.get(\'nombres\',\'\')} {a.get(\'apellidos\',\'\')}".strip()\n        r["telefono"] = a.get("telefono")\n    return _df(rows)\n\n\ndef reactivar_automaticos() -> int:\n    """Da de alta los congelamientos cuya fecha prevista ya llego.\n\n    La misma funcion corre sola en la base todas las noches (pg_cron). Esto\n    la ejecuta ademas al abrir el panel, para que el efecto se vea al\n    instante y no haya que esperar al dia siguiente.\n    """\n    try:\n        r = supabase().rpc("fc_reactivar_previstos", {}).execute()\n        return int(r.data or 0)\n    except Exception:\n        # Si la migracion 014 aun no se corrio, no pasa nada\n        return 0\n\n\ndef congelados_que_vuelven(hasta: date) -> pd.DataFrame:\n    """Congelamientos cuya fecha prevista de alta ya llego o esta por llegar."""\n    try:\n        rows = (_tabla("congelamientos")\n                .select("*, alumnos(codigo,nombres,apellidos,telefono)")\n                .eq("activo", True)\n                .lte("fecha_alta_prevista", hasta.isoformat())\n                .order("fecha_alta_prevista").execute().data) or []\n    except Exception:\n        return pd.DataFrame()\n    for r in rows:\n        a = r.pop("alumnos", None) or {}\n        r["codigo"] = a.get("codigo")\n        r["alumno"] = f"{a.get(\'nombres\',\'\')} {a.get(\'apellidos\',\'\')}".strip()\n        r["telefono"] = a.get("telefono")\n    return _df(rows)\n\n\ndef congelamiento_abierto(paquete_id: str) -> dict | None:\n    r = (_tabla("congelamientos").select("*")\n         .eq("paquete_id", paquete_id).eq("activo", True).limit(1).execute().data)\n    return r[0] if r else None\n\n\n# ---------------------------------------------------------------------\n# Asistencias\n# ---------------------------------------------------------------------\ndef ya_marco_hoy(alumno_id: str, fecha: date | None = None) -> bool:\n    fecha = fecha or logic.hoy()\n    r = (_tabla("asistencias").select("id")\n         .eq("alumno_id", alumno_id).eq("fecha", fecha.isoformat())\n         .eq("anulada", False).limit(1).execute().data)\n    return bool(r)\n\n\ndef marcar_asistencia(alumno_id: str, paquete_id: str, sede: str | None = None,\n                      origen: str = "KIOSCO", fecha: date | None = None):\n    payload = {\n        "alumno_id": alumno_id,\n        "paquete_id": paquete_id,\n        "sede": sede,\n        "origen": origen,\n    }\n    if fecha:\n        payload["fecha"] = fecha.isoformat()\n    return _tabla("asistencias").insert(payload).execute().data\n\n\ndef anular_asistencia(asistencia_id: str, quien: str = "admin"):\n    """Al anular, la sesion vuelve automaticamente al saldo del alumno."""\n    return _tabla("asistencias").update({\n        "anulada": True, "anulada_por": quien,\n    }).eq("id", asistencia_id).execute().data\n\n\ndef asistencias(desde: date, hasta: date, incluir_anuladas: bool = False) -> pd.DataFrame:\n    q = (_tabla("v_asistencias").select("*")\n         .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat()))\n    if not incluir_anuladas:\n        q = q.eq("anulada", False)\n    return _df(q.order("fecha", desc=True).order("hora", desc=True).execute().data)\n\n\ndef registrar_bloqueo(alumno_id: str | None, texto: str, motivo: str):\n    """Deja constancia de quien quiso entrenar sin paquete valido."""\n    return _tabla("bloqueos").insert({\n        "alumno_id": alumno_id, "texto": texto, "motivo": motivo,\n    }).execute().data\n\n\ndef bloqueos(desde: date, hasta: date) -> pd.DataFrame:\n    rows = (_tabla("bloqueos").select("*, alumnos(codigo,nombres,apellidos,telefono)")\n            .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat())\n            .order("fecha", desc=True).order("hora", desc=True).execute().data) or []\n    for r in rows:\n        a = r.pop("alumnos", None) or {}\n        r["codigo"] = a.get("codigo")\n        r["alumno"] = f"{a.get(\'nombres\',\'\')} {a.get(\'apellidos\',\'\')}".strip() or r.get("texto")\n        r["telefono"] = a.get("telefono")\n    return _df(rows)\n'


MIGRACION_SQL = "-- =====================================================================\n-- FUTCROSS | Migracion 015 - Planes cortos y dias por alumno\n--\n-- 1. Agrega los planes que faltaban: clase suelta y paquete de 4 clases.\n-- 2. Deja registrado en el grupo cuantos dias entrena, para poder validar\n--    que un plan basico (2 veces por semana) no elija 3 dias.\n--\n-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.\n-- =====================================================================\n\ninsert into planes (nombre, sesiones, vigencia_dias, precio, descripcion,\n                    dias_por_semana, meses, categoria) values\n  ('CLASE SUELTA',        1,   7, 0.00, 'Una sola sesion',        1, 0, 'SUELTO'),\n  ('PAQUETE 4 CLASES',    4,  30, 0.00, 'Pack corto de 4 clases', 2, 0, 'SUELTO')\non conflict (nombre) do nothing;\n\n-- Los planes premium y basico ya existen; nos aseguramos de su frecuencia\nupdate planes set dias_por_semana = 3 where nombre like 'PLAN PREMIUM%';\nupdate planes set dias_por_semana = 2 where nombre like 'PLAN BASICO%';\n\n-- Un plan sin frecuencia definida se toma como libre: puede elegir\n-- cualquier cantidad de dias dentro de los de su grupo.\ncomment on column planes.dias_por_semana is\n    'Cuantos dias por semana entrena este plan. Null = sin restriccion.';\n"


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
    escribir(Path("migracion-015.sql"), MIGRACION_SQL, salto_app)

    # ---------------------------------------------------------- verificacion
    final_app, _ = leer(app)
    final_tema, _ = leer(tema)
    sql = Path("migracion-015.sql")

    texto_sql = leer(sql)[0] if sql.exists() else ""
    controles = [
        ("Se eligen los dias del alumno", "dias_del_plan" in final_app),
        ("Solo ofrece los dias de su grupo", "disponibles = [d for d" in final_app),
        ("Avisa si no cuadra con el plan",
         "por semana y " in final_app),
        ("Plan antes del grupo al inscribir",
         "Grupo y dias que entrena" in final_app),
        ("Encola el paquete nuevo", "Se encola" in final_app),
        ("Avisa si se superponen", "van a estar vigentes a la vez" in final_app),
        ("Total de sesiones encoladas", "en {len(por_consumir)} paquetes" in final_app),
        ("Planes cortos en la migracion", "CLASE SUELTA" in texto_sql),
        ("Version 2.5", 'VERSION = "2.5"' in final_app),
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
    print("    1. Abre migracion-015.sql (quedo en esta carpeta)")
    print("    2. Copia todo y pegalo en Supabase > SQL Editor > Run")
    print("    3. Recien ahi reinicia Streamlit")
    print("")


if __name__ == "__main__":
    if "--revertir" in sys.argv:
        revertir()
    else:
        aplicar()