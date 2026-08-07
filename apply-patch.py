"""
FUTCROSS | Patch 006 - Datos de venta y planes editables

Requiere los parches 001 a 005 aplicados.

ALUMNOS
  El formulario ahora pide sede, turno y los dias que asiste
  (LUN MIE VIE), ademas de los datos que ya tenia.

PAQUETES (ahora "pedidos")
  Numero de pedido correlativo automatico.
  Fecha del pedido separada de la fecha de inicio del plan.
  Sede y turno, dias que asiste, vendedor.
  Metodo de pago con quien lo recibio: queda como "YAPE GARY".
  Marca automatica de NUEVO o RENOVACION segun el historial del alumno.
  Se pueden ajustar sesiones y vigencia para una venta puntual sin
  tocar el catalogo de planes.
  La tabla muestra las mismas columnas del Excel de FutCross.

PLANES
  Tres pestanas: catalogo, editar y crear.
  Ahora se puede editar todo de un plan: nombre, sesiones, vigencia,
  precio, descripcion y si esta activo.
  Muestra el costo por sesion, para comparar si el plan largo conviene.
  Avisa cuantas ventas usan el plan antes de que lo cambies.

IMPORTANTE
  Este parche necesita que ANTES corras migracion-006.sql en Supabase.
  El archivo se genera solo al aplicar el parche, en esta misma carpeta.

Como se usa, parado en la carpeta admin-streamlit:

    python apply-patch.py

Es idempotente: si ya esta aplicado, avisa y no toca nada. Guarda copia de
seguridad de los dos archivos antes de escribir. Respeta los saltos de linea
originales (CRLF o LF) y no escribe un solo caracter fuera de ASCII.

Para revertir:  python apply-patch.py --revertir
"""

import shutil
import sys
from pathlib import Path

PARCHE = "006-datos-de-venta"
CARPETA_BACKUP = Path("respaldos") / PARCHE

# Si esta marca ya esta en app.py, el parche ya se aplico
MARCA_APLICADO = "Registrar pedido"
MARCA_ORIGINAL = "PERMISOS = {"


CAMBIOS_APP = [
    (
        'theme.aplicar_estilos()\n\n',
        'theme.aplicar_estilos()\n\nDIAS_SEMANA = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]\nTURNOS = ["MANANA", "TARDE", "NOCHE"]\nMEDIOS_PAGO = ["YAPE", "PLIN", "EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO"]\n\n',
    ),
    (
        '            apellidos = c2.text_input("Apellidos *")\n            dni = c1.text_input("DNI")\n            telefono = c2.text_input("Telefono (9 digitos)")\n            email = c1.text_input("Correo")\n',
        '            apellidos = c2.text_input("Apellidos *")\n            dni = c1.text_input("DNI", help="Es lo que el alumno escribe en la tablet")\n            telefono = c2.text_input("Telefono (9 digitos)",\n                                     help="Se usa para el WhatsApp de renovacion")\n            email = c1.text_input("Correo")\n',
    ),
    (
        '                                       max_value=logic.hoy(), format="DD/MM/YYYY")\n            inscripcion = c1.date_input("Fecha de inscripcion", value=logic.hoy(),\n                                        format="DD/MM/YYYY")\n            sede = c2.text_input("Sede", value="Sede principal")\n            horario = c1.text_input("Horario habitual", placeholder="Lun/Mie/Vie 8 p.m.")\n            emergencia = c2.text_input("Contacto de emergencia")\n',
        '                                       max_value=logic.hoy(), format="DD/MM/YYYY")\n            inscripcion = c1.text_input("Fecha de inscripcion", value="", disabled=True,\n                                        placeholder="se toma la de hoy")\n            inscripcion = logic.hoy()\n\n            st.markdown("**Donde y cuando entrena**")\n            d1, d2, d3 = st.columns([1.2, 1, 2])\n            try:\n                opciones_sede = db.sedes()\n            except Exception:\n                opciones_sede = ["SURQUILLO"]\n            sede = d1.selectbox("Sede", opciones_sede + ["Otra..."])\n            if sede == "Otra...":\n                sede = d1.text_input("Nombre de la sede nueva", key="sede_nueva")\n            turno = d2.selectbox("Turno", TURNOS)\n            dias = d3.multiselect("Dias que asiste", DIAS_SEMANA,\n                                  default=["LUN", "MIE", "VIE"])\n            horario = st.text_input("Hora exacta", placeholder="8:00 p.m.")\n\n            emergencia = c2.text_input("Contacto de emergencia")\n',
    ),
    (
        '                            "fecha_inscripcion": inscripcion,\n                            "sede": sede, "horario": horario,\n                            "contacto_emergencia": emergencia, "notas": notas,\n',
        '                            "fecha_inscripcion": inscripcion,\n                            "sede": sede,\n                            "turno": turno,\n                            "dias_asiste": " ".join(dias),\n                            "horario": horario,\n                            "contacto_emergencia": emergencia, "notas": notas,\n',
    ),
    (
        '\n        with st.form("form_paquete"):\n',
        '\n        # Lo que ya sabemos del alumno se hereda, para no volver a escribirlo\n        datos_alumno = alumnos[alumnos["alumno_id"] == alumno_id].iloc[0]\n        try:\n            pedido = db.siguiente_pedido()\n            lista_vendedores = db.vendedores()\n            lista_sedes = db.sedes()\n        except Exception:\n            pedido, lista_vendedores, lista_sedes = 1, [], ["SURQUILLO"]\n\n        with st.form("form_paquete"):\n',
    ),
    (
        '        with st.form("form_paquete"):\n            c1, c2 = st.columns(2)\n            nombre_plan = c1.selectbox("Plan", planes["nombre"].tolist())\n            plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()\n',
        '        with st.form("form_paquete"):\n            st.markdown(f"**Pedido N {pedido}**")\n\n            c1, c2, c3 = st.columns([2, 1, 1])\n            nombre_plan = c1.selectbox("Plan contratado", planes["nombre"].tolist())\n            plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()\n',
    ),
    (
        '            plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()\n            inicio = c2.date_input("Inicio de vigencia", value=logic.hoy(), format="DD/MM/YYYY")\n            fin = logic.fecha_fin_plan(inicio, int(plan["vigencia_dias"]))\n\n',
        '            plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()\n            fecha_pedido = c2.date_input("Fecha del pedido", value=logic.hoy(),\n                                         format="DD/MM/YYYY",\n                                         help="Cuando se cerro la venta")\n            inicio = c3.date_input("Inicio del plan", value=logic.hoy(),\n                                   format="DD/MM/YYYY",\n                                   help="Puede ser posterior a la fecha del pedido")\n\n',
    ),
    (
        '\n            c3, c4, c5 = st.columns(3)\n            precio = c3.number_input("Precio cobrado (S/)", value=float(plan["precio"]),\n                                     min_value=0.0, step=10.0)\n',
        '\n            # Se puede ajustar el plan para una venta puntual sin tocar el catalogo\n            a1, a2 = st.columns(2)\n            sesiones = a1.number_input("Sesiones", min_value=1,\n                                       value=int(plan["sesiones"]),\n                                       help="Cambialo solo si esta venta es una excepcion")\n            vigencia = a2.number_input("Dias de vigencia", min_value=1,\n                                       value=int(plan["vigencia_dias"]))\n            fin = logic.fecha_fin_plan(inicio, int(vigencia))\n\n            st.markdown("**Donde entrena**")\n            d1, d2 = st.columns([1, 2])\n            sede_previa = datos_alumno.get("sede")\n            if sede_previa and not pd.isna(sede_previa):\n                opciones = [sede_previa] + [x for x in lista_sedes if x != sede_previa]\n            else:\n                opciones = lista_sedes\n            sede = d1.selectbox("Sede y turno", opciones)\n            dias_previos = datos_alumno.get("dias_asiste")\n            if dias_previos and not pd.isna(dias_previos):\n                por_defecto = str(dias_previos).split()\n            else:\n                por_defecto = ["LUN", "MIE", "VIE"]\n            dias = d2.multiselect("Dias que asiste", DIAS_SEMANA,\n                                  default=[d for d in por_defecto if d in DIAS_SEMANA])\n\n            st.markdown("**Cobro**")\n            e1, e2, e3 = st.columns(3)\n            precio = e1.number_input("Monto total (S/)", value=float(plan["precio"]),\n                                     min_value=0.0, step=10.0)\n',
    ),
    (
        '                                     min_value=0.0, step=10.0)\n            medio = c4.selectbox("Medio de pago", ["Yape", "Plin", "Efectivo",\n                                                   "Transferencia", "Tarjeta", "Otro"])\n            pagado = c5.selectbox("Estado del pago", ["Pagado", "Pendiente"]) == "Pagado"\n            obs = st.text_input("Observacion", placeholder="Opcional")\n',
        '                                     min_value=0.0, step=10.0)\n            medio = e2.selectbox("Metodo de pago", MEDIOS_PAGO)\n            recibido = e3.text_input("Recibido por", placeholder="Ej. GARY",\n                                     help="Queda registrado como \'YAPE GARY\'")\n\n            f1, f2, f3 = st.columns(3)\n            es_renovacion = bool(vigente) or bool(db.ultimo_paquete(alumno_id))\n            tipo = f1.selectbox("Renovacion o nuevo", ["NUEVO", "RENOVACION"],\n                                index=1 if es_renovacion else 0)\n            if lista_vendedores:\n                vendedor = f2.selectbox("Vendedor", lista_vendedores + ["Otro..."])\n            else:\n                vendedor = "Otro..."\n            if vendedor == "Otro...":\n                vendedor = f2.text_input("Nombre del vendedor", key="vend_nuevo")\n            pagado = f3.selectbox("Estado del pago", ["Pagado", "Pendiente"]) == "Pagado"\n\n            obs = st.text_input("Observacion", placeholder="Opcional")\n',
    ),
    (
        '\n            st.info(f"**{plan[\'sesiones\']} sesiones** con vigencia del "\n                    f"{inicio.strftime(\'%d/%m/%Y\')} al **{fin.strftime(\'%d/%m/%Y\')}** "\n',
        '\n            st.info(f"**{sesiones} sesiones** con vigencia del "\n                    f"{inicio.strftime(\'%d/%m/%Y\')} al **{fin.strftime(\'%d/%m/%Y\')}** "\n',
    ),
    (
        '                    f"{inicio.strftime(\'%d/%m/%Y\')} al **{fin.strftime(\'%d/%m/%Y\')}** "\n                    f"({plan[\'vigencia_dias\']} dias).")\n\n',
        '                    f"{inicio.strftime(\'%d/%m/%Y\')} al **{fin.strftime(\'%d/%m/%Y\')}** "\n                    f"({vigencia} dias).")\n\n',
    ),
    (
        '\n            if st.form_submit_button("Registrar paquete", type="primary"):\n                try:\n',
        '\n            if st.form_submit_button("Registrar pedido", type="primary"):\n                medio_completo = f"{medio} {recibido}".strip() if recibido else medio\n                try:\n',
    ),
    (
        '                try:\n                    db.crear_paquete(alumno_id, plan, inicio, precio, medio, pagado, obs or None)\n                    st.toast(f"Paquete registrado, vence el {fin.strftime(\'%d/%m/%Y\')}", icon="\u2705")\n                    st.success(f"Paquete registrado. Vence el {fin.strftime(\'%d/%m/%Y\')}.")\n                    st.rerun()\n',
        '                try:\n                    db.crear_paquete(\n                        alumno_id, plan, inicio, precio, medio_completo, pagado,\n                        obs or None, fecha_pedido=fecha_pedido, sede=sede,\n                        dias_asiste=" ".join(dias),\n                        vendedor=(vendedor or "").strip().upper() or None,\n                        tipo=tipo, sesiones=int(sesiones), vigencia_dias=int(vigencia))\n                    st.toast(f"Pedido {pedido} registrado", icon="\\u2705")\n                    st.success(f"Pedido N {pedido} registrado. "\n                               f"Vence el {fin.strftime(\'%d/%m/%Y\')}.")\n                    st.rerun()\n',
    ),
    (
        '            return\n        vista = datos[["codigo", "alumno", "plan_nombre", "fecha_inicio", "fecha_fin",\n                       "sesiones_usadas", "sesiones_totales", "sesiones_restantes",\n                       "dias_restantes", "dias_congelados", "precio", "pagado",\n                       "estado_real"]].copy()\n        vista.columns = ["Codigo", "Alumno", "Plan", "Inicio", "Fin", "Usadas", "Totales",\n                         "Restantes", "Dias por vencer", "Dias congelados", "Precio",\n                         "Pagado", "Estado"]\n        vista["Avance"] = (vista["Usadas"] / vista["Totales"].replace(0, 1) * 100)\n',
        '            return\n        columnas = ["nro_pedido", "fecha_pedido", "alumno", "plan_nombre", "precio",\n                    "medio_pago", "fecha_inicio", "fecha_fin", "sede", "dias_asiste",\n                    "sesiones_usadas", "sesiones_totales", "sesiones_restantes",\n                    "dias_restantes", "dias_congelados", "estado_real", "tipo",\n                    "vendedor", "pagado"]\n        # Si la migracion 006 aun no se corrio faltan columnas: avisar sin romper\n        faltan = [c for c in columnas if c not in datos.columns]\n        for c in faltan:\n            datos[c] = None\n        if faltan:\n            st.warning("Faltan campos nuevos en la base. Corre migracion-006.sql en "\n                       "Supabase para tener numero de pedido, sede y vendedor.")\n\n        vista = datos[columnas].copy()\n        vista.columns = ["N pedido", "Fecha", "Cliente", "Plan contratado", "Monto total",\n                         "Metodo de pago", "Inicio del plan", "Fin del plan",\n                         "Sede y turno", "Dias que asiste", "Usadas", "Totales",\n                         "Restantes", "Dias por vencer", "Dias congelados", "Status",\n                         "Renovacion/Nuevo", "Vendedor", "Pagado"]\n        vista["Avance"] = (vista["Usadas"] / vista["Totales"].replace(0, 1) * 100)\n',
    ),
    (
        '        vista["Avance"] = (vista["Usadas"] / vista["Totales"].replace(0, 1) * 100)\n        vista = vista[["Codigo", "Alumno", "Plan", "Avance", "Restantes", "Inicio",\n                       "Fin", "Dias por vencer", "Dias congelados", "Precio",\n                       "Pagado", "Estado"]]\n        for col in ("Inicio", "Fin"):\n            vista[col] = pd.to_datetime(vista[col], errors="coerce")\n',
        '        vista["Avance"] = (vista["Usadas"] / vista["Totales"].replace(0, 1) * 100)\n        vista = vista[["N pedido", "Fecha", "Cliente", "Plan contratado", "Monto total",\n                       "Metodo de pago", "Inicio del plan", "Fin del plan", "Sede y turno",\n                       "Dias que asiste", "Avance", "Restantes", "Dias por vencer",\n                       "Dias congelados", "Status", "Renovacion/Nuevo", "Vendedor",\n                       "Pagado"]]\n        for col in ("Fecha", "Inicio del plan", "Fin del plan"):\n            vista[col] = pd.to_datetime(vista[col], errors="coerce")\n',
    ),
    (
        '            vista, width="stretch", hide_index=True, height=430,\n            column_config={\n                "Avance": st.column_config.ProgressColumn(\n                    "Avance", min_value=0, max_value=100, format="%d%%"),\n',
        '            vista, width="stretch", hide_index=True, height=430,\n            column_config={\n                "N pedido": st.column_config.NumberColumn("N pedido", format="%d"),\n                "Avance": st.column_config.ProgressColumn(\n                    "Avance", min_value=0, max_value=100, format="%d%%"),\n',
    ),
    (
        '                    "Avance", min_value=0, max_value=100, format="%d%%"),\n                "Precio": st.column_config.NumberColumn("Precio", format="S/ %.2f"),\n                "Inicio": st.column_config.DateColumn("Inicio", format="DD/MM/YYYY"),\n                "Fin": st.column_config.DateColumn("Fin", format="DD/MM/YYYY"),\n                "Pagado": st.column_config.CheckboxColumn("Pagado"),\n',
        '                    "Avance", min_value=0, max_value=100, format="%d%%"),\n                "Monto total": st.column_config.NumberColumn(\n                    "Monto total", format="S/ %.2f"),\n                "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),\n                "Inicio del plan": st.column_config.DateColumn(\n                    "Inicio del plan", format="DD/MM/YYYY"),\n                "Fin del plan": st.column_config.DateColumn(\n                    "Fin del plan", format="DD/MM/YYYY"),\n                "Pagado": st.column_config.CheckboxColumn("Pagado"),\n',
    ),
    (
        '    planes = db.listar_planes(solo_activos=False)\n    if not planes.empty:\n        vista = planes[["nombre", "sesiones", "vigencia_dias", "precio",\n                        "descripcion", "activo"]].copy()\n        vista.columns = ["Plan", "Sesiones", "Vigencia (dias)", "Precio",\n                         "Descripcion", "Activo"]\n        st.dataframe(vista, width="stretch", hide_index=True)\n\n',
        '    planes = db.listar_planes(solo_activos=False)\n\n',
    ),
    (
        '\n        st.markdown("**Activar o desactivar**")\n        c1, c2 = st.columns([3, 1])\n        elegido = c1.selectbox("Plan", planes["nombre"].tolist())\n        fila = planes[planes["nombre"] == elegido].iloc[0]\n        etiqueta = "Desactivar" if fila["activo"] else "Activar"\n        if c2.button(etiqueta, width="stretch"):\n            db.actualizar_plan(fila["id"], {"activo": not bool(fila["activo"])})\n            st.rerun()\n\n',
        '\n    tab_lista, tab_editar, tab_nuevo = st.tabs(\n        ["Catalogo", "Editar un plan", "Crear plan"])\n\n',
    ),
    (
        '\n    st.divider()\n    with st.form("form_plan", clear_on_submit=True):\n        st.markdown("**Nuevo plan**")\n        c1, c2, c3, c4 = st.columns(4)\n        nombre = c1.text_input("Nombre")\n        sesiones = c2.number_input("Sesiones", min_value=1, value=12)\n        vigencia = c3.number_input("Vigencia (dias)", min_value=1, value=30)\n        precio = c4.number_input("Precio (S/)", min_value=0.0, value=180.0, step=10.0)\n        desc = st.text_input("Descripcion")\n        if st.form_submit_button("Crear plan", type="primary"):\n            if not nombre:\n                st.error("Ponle un nombre al plan.")\n            else:\n                try:\n                    db.crear_plan(nombre, sesiones, vigencia, precio, desc)\n                    st.success("Plan creado.")\n                    st.rerun()\n                except Exception as e:\n                    st.error(f"No se pudo crear: {e}")\n\n',
        '\n    # ---------------------------------------------------------- catalogo\n    with tab_lista:\n        if planes.empty:\n            theme.vacio("Todavia no hay planes",\n                        "Crea el primero en la pestana Crear plan.")\n        else:\n            vista = planes[["nombre", "sesiones", "vigencia_dias", "precio",\n                            "descripcion", "activo"]].copy()\n            vista["por_sesion"] = (vista["precio"] / vista["sesiones"].replace(0, 1))\n            vista.columns = ["Plan", "Sesiones", "Vigencia (dias)", "Precio",\n                             "Descripcion", "Activo", "Costo por sesion"]\n            vista = vista[["Plan", "Sesiones", "Vigencia (dias)", "Precio",\n                           "Costo por sesion", "Descripcion", "Activo"]]\n            st.dataframe(\n                vista, width="stretch", hide_index=True,\n                column_config={\n                    "Precio": st.column_config.NumberColumn("Precio", format="S/ %.2f"),\n                    "Costo por sesion": st.column_config.NumberColumn(\n                        "Costo por sesion", format="S/ %.2f",\n                        help="Sirve para comparar si el plan largo conviene"),\n                    "Activo": st.column_config.CheckboxColumn("Activo"),\n                })\n            st.caption("Los planes desactivados no aparecen al vender, pero los alumnos "\n                       "que ya los tienen los siguen usando hasta agotarlos.")\n\n    # ------------------------------------------------------------ editar\n    with tab_editar:\n        if planes.empty:\n            theme.vacio("Nada que editar", "Primero crea un plan.")\n        else:\n            elegido = st.selectbox("Plan a editar", planes["nombre"].tolist(),\n                                   key="plan_editar")\n            fila = planes[planes["nombre"] == elegido].iloc[0]\n\n            try:\n                usos = db.paquetes_con_plan(fila["id"])\n            except Exception:\n                usos = 0\n            if usos:\n                st.info(f"Este plan se vendio {usos} {\'vez\' if usos == 1 else \'veces\'}. "\n                        "Cambiarlo no altera esas ventas: cada paquete guarda las "\n                        "sesiones y el precio con los que se cobro.")\n\n            with st.form("form_editar_plan"):\n                c1, c2, c3 = st.columns([2, 1, 1])\n                nombre = c1.text_input("Nombre", value=str(fila["nombre"]))\n                sesiones = c2.number_input("Sesiones", min_value=1,\n                                           value=int(fila["sesiones"]))\n                vigencia = c3.number_input("Vigencia (dias)", min_value=1,\n                                           value=int(fila["vigencia_dias"]))\n\n                d1, d2 = st.columns([1, 1])\n                precio = d1.number_input("Precio (S/)", min_value=0.0,\n                                         value=float(fila["precio"]), step=10.0)\n                activo = d2.selectbox("Estado", ["Activo", "Desactivado"],\n                                      index=0 if bool(fila["activo"]) else 1) == "Activo"\n                desc = st.text_input("Descripcion",\n                                     value=str(fila["descripcion"] or ""))\n\n                if sesiones:\n                    st.caption(f"Costo por sesion: S/ {precio / sesiones:.2f}")\n\n                if st.form_submit_button("Guardar cambios", type="primary"):\n                    try:\n                        db.actualizar_plan(fila["id"], {\n                            "nombre": nombre.strip().upper(),\n                            "sesiones": int(sesiones),\n                            "vigencia_dias": int(vigencia),\n                            "precio": float(precio),\n                            "descripcion": desc or None,\n                            "activo": activo,\n                        })\n                        st.toast("Plan actualizado", icon="\\u2705")\n                        st.success("Plan actualizado.")\n                        st.rerun()\n                    except Exception as e:\n                        st.error(f"No se pudo guardar: {e}")\n\n    # ------------------------------------------------------------- crear\n    with tab_nuevo:\n        with st.form("form_plan", clear_on_submit=True):\n            c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])\n            nombre = c1.text_input("Nombre del plan",\n                                   placeholder="PLAN BASICO 36 SESIONES 3 MESES PROMO")\n            sesiones = c2.number_input("Sesiones", min_value=1, value=12)\n            vigencia = c3.number_input("Vigencia (dias)", min_value=1, value=30,\n                                       help="30 = un mes, 90 = tres meses")\n            precio = c4.number_input("Precio (S/)", min_value=0.0, value=180.0, step=10.0)\n            desc = st.text_input("Descripcion",\n                                 placeholder="3 sesiones por semana durante un mes")\n\n            st.caption(f"Costo por sesion: S/ {precio / max(1, sesiones):.2f}")\n\n            if st.form_submit_button("Crear plan", type="primary"):\n                if not nombre.strip():\n                    st.error("Ponle un nombre al plan.")\n                else:\n                    try:\n                        db.crear_plan(nombre, sesiones, vigencia, precio, desc or None)\n                        st.toast("Plan creado", icon="\\u2705")\n                        st.success(f"Plan creado: {nombre.strip().upper()}")\n                        st.rerun()\n                    except Exception as e:\n                        st.error(f"No se pudo crear: {e}")\n\n',
    ),
]


DB_NUEVO = '"""\nFUTCROSS | Capa de datos sobre Supabase (PostgREST).\n\nTodas las consultas pasan por aca. Ninguna pantalla arma queries por su cuenta.\n"""\n\nfrom __future__ import annotations\n\nimport os\nfrom datetime import date\n\nimport pandas as pd\nimport streamlit as st\nfrom supabase import Client, create_client\n\nimport logic\n\n\n# ---------------------------------------------------------------------\n# Conexion\n# ---------------------------------------------------------------------\ndef secreto(clave: str, defecto=None):\n    """Busca primero en .streamlit/secrets.toml y luego en variables de entorno.\n\n    En local usamos secrets.toml; Hugging Face Spaces inyecta los secretos\n    como variables de entorno. Asi el mismo codigo sirve en los dos lados.\n    """\n    try:\n        if clave in st.secrets:\n            return st.secrets[clave]\n    except Exception:\n        pass\n    return os.environ.get(clave, defecto)\n\n\n@st.cache_resource(show_spinner=False)\ndef cliente() -> Client:\n    url = secreto("SUPABASE_URL")\n    key = secreto("SUPABASE_KEY")\n    if not url or not key:\n        st.error(\n            "Falta configurar la conexion a Supabase. "\n            "Crea el archivo `.streamlit/secrets.toml` con SUPABASE_URL y SUPABASE_KEY "\n            "(o cargalos en Settings > Secrets si ya desplegaste en la nube)."\n        )\n        st.stop()\n    return create_client(url, key)\n\n\ndef _tabla(nombre: str):\n    return cliente().table(nombre)\n\n\ndef _df(rows) -> pd.DataFrame:\n    return pd.DataFrame(rows or [])\n\n\ndef _iso(valor):\n    """Serializa fechas para PostgREST."""\n    return valor.isoformat() if isinstance(valor, date) else valor\n\n\n# ---------------------------------------------------------------------\n# Planes\n# ---------------------------------------------------------------------\ndef listar_planes(solo_activos: bool = True) -> pd.DataFrame:\n    q = _tabla("planes").select("*").order("sesiones")\n    if solo_activos:\n        q = q.eq("activo", True)\n    return _df(q.execute().data)\n\n\ndef crear_plan(nombre, sesiones, vigencia_dias, precio, descripcion=None):\n    return _tabla("planes").insert({\n        "nombre": nombre.strip().upper(),\n        "sesiones": int(sesiones),\n        "vigencia_dias": int(vigencia_dias),\n        "precio": float(precio),\n        "descripcion": descripcion,\n    }).execute().data\n\n\ndef plan(plan_id: str) -> dict | None:\n    r = _tabla("planes").select("*").eq("id", plan_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef paquetes_con_plan(plan_id: str) -> int:\n    """Cuantas ventas usan este plan. Sirve para avisar antes de editarlo."""\n    r = (_tabla("paquetes").select("id", count="exact")\n         .eq("plan_id", plan_id).execute())\n    return r.count or 0\n\n\ndef actualizar_plan(plan_id: str, cambios: dict):\n    return _tabla("planes").update(cambios).eq("id", plan_id).execute().data\n\n\n# ---------------------------------------------------------------------\n# Alumnos\n# ---------------------------------------------------------------------\ndef crear_alumno(datos: dict):\n    limpio = {k: _iso(v) for k, v in datos.items() if v not in (None, "")}\n    return _tabla("alumnos").insert(limpio).execute().data\n\n\ndef actualizar_alumno(alumno_id: str, cambios: dict):\n    limpio = {k: _iso(v) for k, v in cambios.items()}\n    return _tabla("alumnos").update(limpio).eq("id", alumno_id).execute().data\n\n\ndef alumno(alumno_id: str) -> dict | None:\n    r = _tabla("alumnos").select("*").eq("id", alumno_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef panel_alumnos(solo_activos: bool = True) -> pd.DataFrame:\n    """Una fila por alumno con su paquete mas relevante (vista v_alumnos_estado)."""\n    q = _tabla("v_alumnos_estado").select("*").order("apellidos")\n    if solo_activos:\n        q = q.eq("activo", True)\n    return _df(q.execute().data)\n\n\ndef buscar_alumnos(texto: str, limite: int = 25) -> pd.DataFrame:\n    """Busca por nombre, apellido, codigo, DNI o telefono."""\n    texto = (texto or "").strip()\n    if not texto:\n        return panel_alumnos().head(limite)\n    patron = f"%{texto}%"\n    filtro = ",".join([\n        f"nombres.ilike.{patron}",\n        f"apellidos.ilike.{patron}",\n        f"codigo.ilike.{patron}",\n        f"dni.ilike.{patron}",\n        f"telefono.ilike.{patron}",\n    ])\n    rows = _tabla("v_alumnos_estado").select("*").or_(filtro).limit(limite).execute().data\n    return _df(rows)\n\n\ndef identificar(texto: str) -> list[dict]:\n    """Busqueda del kiosco: DNI o codigo exacto primero, luego nombre parcial."""\n    texto = (texto or "").strip()\n    if not texto:\n        return []\n\n    digitos = logic.solo_digitos(texto)\n    if digitos and len(digitos) >= 8:\n        exacto = _tabla("v_alumnos_estado").select("*").or_(\n            f"dni.eq.{digitos},telefono.eq.{digitos}"\n        ).execute().data\n        if exacto:\n            return exacto\n\n    codigo = texto.upper()\n    if codigo.startswith("FC-"):\n        exacto = _tabla("v_alumnos_estado").select("*").eq("codigo", codigo).execute().data\n        if exacto:\n            return exacto\n\n    patron = f"%{texto}%"\n    return _tabla("v_alumnos_estado").select("*").or_(\n        f"nombres.ilike.{patron},apellidos.ilike.{patron},codigo.ilike.{patron}"\n    ).limit(8).execute().data\n\n\n# ---------------------------------------------------------------------\n# Paquetes\n# ---------------------------------------------------------------------\ndef paquetes_de(alumno_id: str) -> pd.DataFrame:\n    rows = (_tabla("v_paquetes").select("*")\n            .eq("alumno_id", alumno_id).order("fecha_inicio", desc=True).execute().data)\n    return _df(rows)\n\n\ndef paquete(paquete_id: str) -> dict | None:\n    r = _tabla("v_paquetes").select("*").eq("id", paquete_id).limit(1).execute().data\n    return r[0] if r else None\n\n\ndef paquete_vigente(alumno_id: str) -> dict | None:\n    """El paquete que manda hoy: ACTIVO o CONGELADO, el que vence primero."""\n    rows = (_tabla("v_paquetes").select("*")\n            .eq("alumno_id", alumno_id)\n            .in_("estado_real", ["ACTIVO", "CONGELADO"])\n            .order("fecha_fin").execute().data)\n    return rows[0] if rows else None\n\n\ndef ultimo_paquete(alumno_id: str) -> dict | None:\n    rows = (_tabla("v_paquetes").select("*")\n            .eq("alumno_id", alumno_id).order("fecha_fin", desc=True).limit(1).execute().data)\n    return rows[0] if rows else None\n\n\ndef listar_paquetes(estados: list[str] | None = None) -> pd.DataFrame:\n    q = _tabla("v_paquetes").select("*").order("fecha_fin", desc=True)\n    if estados:\n        q = q.in_("estado_real", estados)\n    return _df(q.execute().data)\n\n\ndef crear_paquete(alumno_id, plan: dict, fecha_inicio: date, precio: float,\n                  medio_pago: str, pagado: bool = True, observacion: str | None = None,\n                  fecha_pedido: date | None = None, sede: str | None = None,\n                  dias_asiste: str | None = None, vendedor: str | None = None,\n                  tipo: str = "NUEVO", sesiones: int | None = None,\n                  vigencia_dias: int | None = None):\n    """Registra la venta con todos los datos del pedido.\n\n    sesiones y vigencia_dias permiten ajustar el plan para una venta puntual\n    (por ejemplo, regalar dos sesiones) sin tocar el catalogo.\n    """\n    total = int(sesiones or plan["sesiones"])\n    dias = int(vigencia_dias or plan["vigencia_dias"])\n    fecha_fin = logic.fecha_fin_plan(fecha_inicio, dias)\n\n    return _tabla("paquetes").insert({\n        "alumno_id": alumno_id,\n        "plan_id": plan.get("id"),\n        "plan_nombre": plan["nombre"],\n        "sesiones_totales": total,\n        "fecha_pedido": (fecha_pedido or fecha_inicio).isoformat(),\n        "fecha_inicio": fecha_inicio.isoformat(),\n        "fecha_fin": fecha_fin.isoformat(),\n        "precio": float(precio),\n        "medio_pago": medio_pago,\n        "pagado": bool(pagado),\n        "sede": sede,\n        "dias_asiste": dias_asiste,\n        "vendedor": vendedor,\n        "tipo": tipo,\n        "observacion": observacion,\n    }).execute().data\n\n\ndef actualizar_paquete(paquete_id: str, cambios: dict):\n    limpio = {k: _iso(v) for k, v in cambios.items()}\n    return _tabla("paquetes").update(limpio).eq("id", paquete_id).execute().data\n\n\ndef siguiente_pedido() -> int:\n    """Solo para mostrarlo antes de guardar; el numero real lo pone la base."""\n    r = (_tabla("paquetes").select("nro_pedido")\n         .order("nro_pedido", desc=True).limit(1).execute().data)\n    return (r[0]["nro_pedido"] or 0) + 1 if r else 1\n\n\ndef vendedores() -> list:\n    """Los vendedores que ya se usaron, para no escribirlos de nuevo."""\n    r = _tabla("paquetes").select("vendedor").execute().data or []\n    return sorted({(x.get("vendedor") or "").strip() for x in r if x.get("vendedor")})\n\n\ndef sedes() -> list:\n    r = _tabla("alumnos").select("sede").execute().data or []\n    vistas = {(x.get("sede") or "").strip() for x in r if x.get("sede")}\n    return sorted(vistas | {"SURQUILLO"})\n\n\ndef cancelar_paquete(paquete_id: str, motivo: str):\n    return _tabla("paquetes").update({\n        "estado": "CANCELADO",\n        "observacion": motivo,\n    }).eq("id", paquete_id).execute().data\n\n\n# ---------------------------------------------------------------------\n# Congelamientos\n# ---------------------------------------------------------------------\ndef congelar(paquete_id: str, alumno_id: str, motivo: str, detalle: str, desde: date):\n    """Pausa el paquete. La vigencia se extiende recien al reactivar."""\n    _tabla("congelamientos").insert({\n        "paquete_id": paquete_id,\n        "alumno_id": alumno_id,\n        "motivo": motivo,\n        "detalle": detalle,\n        "fecha_inicio": desde.isoformat(),\n    }).execute()\n    _tabla("paquetes").update({"estado": "CONGELADO"}).eq("id", paquete_id).execute()\n\n\ndef reactivar(congelamiento_id: str, hasta: date) -> int:\n    """Cierra el congelamiento y le devuelve al alumno los dias perdidos."""\n    cong = _tabla("congelamientos").select("*").eq("id", congelamiento_id).limit(1).execute().data\n    if not cong:\n        raise ValueError("No se encontro el congelamiento.")\n    cong = cong[0]\n\n    inicio = logic.a_fecha(cong["fecha_inicio"])\n    dias = logic.dias_congelamiento(inicio, hasta)\n\n    pq = _tabla("paquetes").select("*").eq("id", cong["paquete_id"]).limit(1).execute().data[0]\n    nueva_fin = logic.extender(logic.a_fecha(pq["fecha_fin"]), dias)\n\n    _tabla("paquetes").update({\n        "estado": "ACTIVO",\n        "fecha_fin": nueva_fin.isoformat(),\n        "dias_congelados": int(pq.get("dias_congelados") or 0) + dias,\n    }).eq("id", pq["id"]).execute()\n\n    _tabla("congelamientos").update({\n        "fecha_fin": hasta.isoformat(),\n        "dias_aplicados": dias,\n        "activo": False,\n    }).eq("id", congelamiento_id).execute()\n\n    return dias\n\n\ndef congelamientos(activos: bool | None = True) -> pd.DataFrame:\n    q = _tabla("congelamientos").select("*, alumnos(codigo,nombres,apellidos,telefono)")\n    if activos is not None:\n        q = q.eq("activo", activos)\n    rows = q.order("fecha_inicio", desc=True).execute().data or []\n    for r in rows:\n        a = r.pop("alumnos", None) or {}\n        r["codigo"] = a.get("codigo")\n        r["alumno"] = f"{a.get(\'nombres\',\'\')} {a.get(\'apellidos\',\'\')}".strip()\n        r["telefono"] = a.get("telefono")\n    return _df(rows)\n\n\ndef congelamiento_abierto(paquete_id: str) -> dict | None:\n    r = (_tabla("congelamientos").select("*")\n         .eq("paquete_id", paquete_id).eq("activo", True).limit(1).execute().data)\n    return r[0] if r else None\n\n\n# ---------------------------------------------------------------------\n# Asistencias\n# ---------------------------------------------------------------------\ndef ya_marco_hoy(alumno_id: str, fecha: date | None = None) -> bool:\n    fecha = fecha or logic.hoy()\n    r = (_tabla("asistencias").select("id")\n         .eq("alumno_id", alumno_id).eq("fecha", fecha.isoformat())\n         .eq("anulada", False).limit(1).execute().data)\n    return bool(r)\n\n\ndef marcar_asistencia(alumno_id: str, paquete_id: str, sede: str | None = None,\n                      origen: str = "KIOSCO", fecha: date | None = None):\n    payload = {\n        "alumno_id": alumno_id,\n        "paquete_id": paquete_id,\n        "sede": sede,\n        "origen": origen,\n    }\n    if fecha:\n        payload["fecha"] = fecha.isoformat()\n    return _tabla("asistencias").insert(payload).execute().data\n\n\ndef anular_asistencia(asistencia_id: str, quien: str = "admin"):\n    """Al anular, la sesion vuelve automaticamente al saldo del alumno."""\n    return _tabla("asistencias").update({\n        "anulada": True, "anulada_por": quien,\n    }).eq("id", asistencia_id).execute().data\n\n\ndef asistencias(desde: date, hasta: date, incluir_anuladas: bool = False) -> pd.DataFrame:\n    q = (_tabla("v_asistencias").select("*")\n         .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat()))\n    if not incluir_anuladas:\n        q = q.eq("anulada", False)\n    return _df(q.order("fecha", desc=True).order("hora", desc=True).execute().data)\n\n\ndef registrar_bloqueo(alumno_id: str | None, texto: str, motivo: str):\n    """Deja constancia de quien quiso entrenar sin paquete valido."""\n    return _tabla("bloqueos").insert({\n        "alumno_id": alumno_id, "texto": texto, "motivo": motivo,\n    }).execute().data\n\n\ndef bloqueos(desde: date, hasta: date) -> pd.DataFrame:\n    rows = (_tabla("bloqueos").select("*, alumnos(codigo,nombres,apellidos,telefono)")\n            .gte("fecha", desde.isoformat()).lte("fecha", hasta.isoformat())\n            .order("fecha", desc=True).order("hora", desc=True).execute().data) or []\n    for r in rows:\n        a = r.pop("alumnos", None) or {}\n        r["codigo"] = a.get("codigo")\n        r["alumno"] = f"{a.get(\'nombres\',\'\')} {a.get(\'apellidos\',\'\')}".strip() or r.get("texto")\n        r["telefono"] = a.get("telefono")\n    return _df(rows)\n'


MIGRACION_SQL = "-- =====================================================================\n-- FUTCROSS | Migracion 006\n-- Agrega los campos que FutCross maneja en su Excel de clientes:\n-- numero de pedido, fecha del pedido, sede, dias que asiste, vendedor\n-- y si la venta es nueva o una renovacion.\n--\n-- Ejecutar TODO en Supabase > SQL Editor > New query > Run.\n-- Es idempotente: se puede correr de nuevo sin romper nada.\n-- =====================================================================\n\n-- ---------------------------------------------------------------------\n-- 1. Numero de pedido correlativo\n-- ---------------------------------------------------------------------\ncreate sequence if not exists seq_nro_pedido start 1;\n\nalter table paquetes\n    add column if not exists nro_pedido   int,\n    add column if not exists fecha_pedido date,\n    add column if not exists sede         text,\n    add column if not exists dias_asiste  text,\n    add column if not exists vendedor     text,\n    add column if not exists tipo         text default 'NUEVO';\n\n-- Los paquetes que ya existian reciben su numero y su fecha de pedido\nupdate paquetes set nro_pedido = nextval('seq_nro_pedido') where nro_pedido is null;\nupdate paquetes set fecha_pedido = fecha_inicio where fecha_pedido is null;\nupdate paquetes set tipo = 'NUEVO' where tipo is null;\n\n-- De aca en adelante el numero se asigna solo\nalter table paquetes alter column nro_pedido set default nextval('seq_nro_pedido');\nalter table paquetes alter column fecha_pedido set default hoy_lima();\n\n-- La secuencia arranca despues del maximo que ya exista\nselect setval('seq_nro_pedido',\n              coalesce((select max(nro_pedido) from paquetes), 0) + 1,\n              false);\n\n-- Solo dos tipos de venta posibles\ndo $$\nbegin\n    if not exists (select 1 from pg_constraint where conname = 'paquetes_tipo_check') then\n        alter table paquetes add constraint paquetes_tipo_check\n            check (tipo in ('NUEVO', 'RENOVACION'));\n    end if;\nend $$;\n\ncreate index if not exists ix_paquetes_pedido on paquetes (nro_pedido desc);\n\n-- ---------------------------------------------------------------------\n-- 2. Dias de asistencia habituales del alumno\n-- ---------------------------------------------------------------------\nalter table alumnos\n    add column if not exists dias_asiste text,\n    add column if not exists turno       text;\n\n-- ---------------------------------------------------------------------\n-- 3. Vistas: se recrean porque cambiaron las columnas\n-- ---------------------------------------------------------------------\ndrop view if exists v_alumnos_estado cascade;\ndrop view if exists v_paquetes cascade;\n\ncreate view v_paquetes as\nwith base as (\n    select p.*,\n           coalesce((select count(*) from asistencias s\n                     where s.paquete_id = p.id and not s.anulada), 0)::int as sesiones_usadas\n    from paquetes p\n)\nselect b.id,\n       b.nro_pedido,\n       b.alumno_id,\n       a.codigo,\n       a.nombres,\n       a.apellidos,\n       (a.nombres || ' ' || a.apellidos) as alumno,\n       a.dni,\n       a.telefono,\n       coalesce(b.sede, a.sede)               as sede,\n       coalesce(b.dias_asiste, a.dias_asiste) as dias_asiste,\n       a.turno,\n       a.horario,\n       b.plan_id,\n       b.plan_nombre,\n       b.sesiones_totales,\n       b.sesiones_usadas,\n       (b.sesiones_totales - b.sesiones_usadas) as sesiones_restantes,\n       b.fecha_pedido,\n       b.fecha_inicio,\n       b.fecha_fin,\n       (b.fecha_fin - hoy_lima())            as dias_restantes,\n       b.dias_congelados,\n       b.precio,\n       b.medio_pago,\n       b.pagado,\n       b.vendedor,\n       b.tipo,\n       b.estado,\n       b.observacion,\n       b.creado_en,\n       case\n         when b.estado = 'CANCELADO'                  then 'CANCELADO'\n         when b.estado = 'CONGELADO'                  then 'CONGELADO'\n         when b.sesiones_usadas >= b.sesiones_totales then 'AGOTADO'\n         when hoy_lima() > b.fecha_fin                then 'VENCIDO'\n         else 'ACTIVO'\n       end as estado_real\nfrom base b\njoin alumnos a on a.id = b.alumno_id;\n\ncreate view v_alumnos_estado as\nselect a.id            as alumno_id,\n       a.codigo,\n       a.nombres,\n       a.apellidos,\n       (a.nombres || ' ' || a.apellidos) as alumno,\n       a.dni,\n       a.telefono,\n       a.email,\n       a.sede,\n       a.turno,\n       a.dias_asiste,\n       a.horario,\n       a.fecha_inscripcion,\n       a.activo,\n       vp.id            as paquete_id,\n       vp.nro_pedido,\n       vp.plan_nombre,\n       vp.fecha_pedido,\n       vp.fecha_inicio,\n       vp.fecha_fin,\n       vp.sesiones_totales,\n       vp.sesiones_usadas,\n       vp.sesiones_restantes,\n       vp.dias_restantes,\n       vp.dias_congelados,\n       vp.vendedor,\n       vp.tipo,\n       vp.precio,\n       vp.medio_pago,\n       coalesce(vp.estado_real, 'SIN PAQUETE') as estado_real\nfrom alumnos a\nleft join lateral (\n    select p.* from v_paquetes p\n    where p.alumno_id = a.id\n    order by case p.estado_real\n               when 'ACTIVO'    then 0\n               when 'CONGELADO' then 1\n               else 2\n             end,\n             p.fecha_fin desc\n    limit 1\n) vp on true;\n\ncreate or replace view v_asistencias as\nselect s.id,\n       s.fecha,\n       s.hora,\n       s.sede,\n       s.origen,\n       s.anulada,\n       s.alumno_id,\n       s.paquete_id,\n       a.codigo,\n       (a.nombres || ' ' || a.apellidos) as alumno,\n       a.telefono\nfrom asistencias s\njoin alumnos a on a.id = s.alumno_id;\n\n-- ---------------------------------------------------------------------\n-- 4. Planes que FutCross vende de verdad\n-- ---------------------------------------------------------------------\ninsert into planes (nombre, sesiones, vigencia_dias, precio, descripcion) values\n  ('PLAN BASICO 36 SESIONES 3 MESES PROMO', 36, 90, 590.00,\n   'Promocion trimestral, 3 sesiones por semana')\non conflict (nombre) do nothing;\n"


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
    escribir(Path("migracion-006.sql"), MIGRACION_SQL, salto_app)

    # ---------------------------------------------------------- verificacion
    final_app, _ = leer(app)
    final_tema, _ = leer(tema)
    sql = Path("migracion-006.sql")

    controles = [
        ("Numero de pedido y vendedor", "siguiente_pedido" in final_tema),
        ("Sede y dias que asiste", "dias_asiste" in final_app),
        ("Metodo de pago con quien recibio", "Recibido por" in final_app),
        ("Nuevo o renovacion automatico", "es_renovacion" in final_app),
        ("Editor de planes completo", "form_editar_plan" in final_app),
        ("Costo por sesion", "Costo por sesion" in final_app),
        ("Tabla igual al Excel", "Renovacion/Nuevo" in final_app),
        ("Migracion SQL generada", sql.exists() and sql.stat().st_size > 3000),
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
    print("    1. Abre migracion-006.sql (quedo en esta carpeta)")
    print("    2. Copia todo y pegalo en Supabase > SQL Editor > Run")
    print("    3. Recien ahi reinicia Streamlit")
    print("")


if __name__ == "__main__":
    if "--revertir" in sys.argv:
        revertir()
    else:
        aplicar()