"""
FUTCROSS | Patch 008 - Arreglo: no se podia crear el primer alumno

Requiere los parches 001 a 007 aplicados.

EL BUG
  Con la base vacia, la pantalla de Alumnos salia de la funcion apenas
  veia que no habia nadie en la lista. Resultado: las pestanas
  "Inscribir alumno" y "Editar alumno" se dibujaban pero quedaban en
  blanco, y no habia forma de registrar al primer alumno.
  El problema del huevo y la gallina: para crear un alumno hacia falta
  que ya hubiera alumnos.

  La pantalla de Paquetes tenia exactamente el mismo defecto en tres
  lugares: sin alumnos, sin planes y sin pedidos.

EL ARREGLO
  Los estados vacios ahora muestran un mensaje y siguen, en vez de
  cortar la pantalla. Todas las pestanas se dibujan siempre.

  Ademas los avisos genericos pasaron a estados vacios con diseno, que
  dicen que hacer: "Usa la pestana Inscribir alumno para registrar al
  primero" en vez de "No hay alumnos que coincidan".

Verificado con la base completamente vacia: se puede crear el primer
plan, el primer alumno y el primer pedido sin tener nada cargado.

Solo modifica app.py.

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

PARCHE = "008-arranque-en-vacio"
CARPETA_BACKUP = Path("respaldos") / PARCHE

# Si esta marca ya esta en app.py, el parche ya se aplico
MARCA_APLICADO = "problema del huevo y la gallina"
MARCA_ORIGINAL = "def editar_alumno()"


CAMBIOS_APP = [
    (
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "1.7"\n\n',
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "1.8"\n\n',
    ),
    (
        '        if datos.empty:\n            st.info("No hay alumnos que coincidan.")\n            return\n        if filtro != "Todos":\n            datos = datos[datos["estado_real"] == filtro]\n\n',
        '        if datos.empty:\n            # Aca NO puede ir un return: si sale de la funcion, las pestanas\n            # Inscribir y Editar quedan vacias y no se puede registrar al\n            # primer alumno. Es el problema del huevo y la gallina.\n            theme.vacio("Todavia no hay alumnos",\n                        "Usa la pestana Inscribir alumno para registrar al primero.")\n        else:\n            if filtro != "Todos":\n                datos = datos[datos["estado_real"] == filtro]\n\n',
    ),
    (
        '\n        vista = datos[["codigo", "alumno", "telefono", "plan_nombre",\n                       "sesiones_usadas", "sesiones_totales",\n                       "sesiones_restantes", "fecha_fin", "estado_real",\n                       "fecha_inscripcion"]].copy()\n        vista["avance"] = (vista["sesiones_usadas"].fillna(0)\n                           / vista["sesiones_totales"].replace(0, 1) * 100).fillna(0)\n        vista = vista.drop(columns=["sesiones_usadas", "sesiones_totales"])\n        vista.columns = ["Codigo", "Alumno", "Telefono", "Plan", "Restantes",\n                         "Vence", "Estado", "Inscrito", "Avance"]\n        vista = vista[["Codigo", "Alumno", "Telefono", "Plan", "Avance",\n                       "Restantes", "Vence", "Estado", "Inscrito"]]\n        for col in ("Vence", "Inscrito"):\n            vista[col] = pd.to_datetime(vista[col], errors="coerce")\n\n',
        '\n            vista = datos[["codigo", "alumno", "telefono", "plan_nombre",\n                           "sesiones_usadas", "sesiones_totales",\n                           "sesiones_restantes", "fecha_fin", "estado_real",\n                           "fecha_inscripcion"]].copy()\n            vista["avance"] = (vista["sesiones_usadas"].fillna(0)\n                               / vista["sesiones_totales"].replace(0, 1) * 100).fillna(0)\n            vista = vista.drop(columns=["sesiones_usadas", "sesiones_totales"])\n            vista.columns = ["Codigo", "Alumno", "Telefono", "Plan", "Restantes",\n                             "Vence", "Estado", "Inscrito", "Avance"]\n            vista = vista[["Codigo", "Alumno", "Telefono", "Plan", "Avance",\n                           "Restantes", "Vence", "Estado", "Inscrito"]]\n            for col in ("Vence", "Inscrito"):\n                vista[col] = pd.to_datetime(vista[col], errors="coerce")\n\n',
    ),
    (
        '\n        st.dataframe(\n            vista, width="stretch", hide_index=True, height=420,\n            column_config={\n                "Avance": st.column_config.ProgressColumn(\n                    "Avance", min_value=0, max_value=100, format="%d%%",\n                    help="Sesiones usadas del paquete"),\n                "Restantes": st.column_config.NumberColumn("Restantes", format="%d"),\n                "Vence": st.column_config.DateColumn("Vence", format="DD/MM/YYYY"),\n                "Inscrito": st.column_config.DateColumn("Inscrito", format="DD/MM/YYYY"),\n            })\n        st.download_button("Descargar CSV", vista.to_csv(index=False).encode("utf-8"),\n                           "futcross_alumnos.csv", "text/csv")\n\n',
        '\n            st.dataframe(\n                vista, width="stretch", hide_index=True, height=420,\n                column_config={\n                    "Avance": st.column_config.ProgressColumn(\n                        "Avance", min_value=0, max_value=100, format="%d%%",\n                        help="Sesiones usadas del paquete"),\n                    "Restantes": st.column_config.NumberColumn("Restantes", format="%d"),\n                    "Vence": st.column_config.DateColumn("Vence", format="DD/MM/YYYY"),\n                    "Inscrito": st.column_config.DateColumn("Inscrito", format="DD/MM/YYYY"),\n                })\n            st.download_button("Descargar CSV", vista.to_csv(index=False).encode("utf-8"),\n                               "futcross_alumnos.csv", "text/csv")\n\n',
    ),
    (
        '\n        st.divider()\n        st.subheader("Ficha del alumno")\n        opciones = {f"{r[\'codigo\']} \xb7 {r[\'alumno\']}": r["alumno_id"]\n                    for _, r in datos.iterrows()}\n        elegido = st.selectbox("Selecciona", list(opciones.keys()))\n        if elegido:\n            ficha_alumno(opciones[elegido])\n\n',
        '\n            st.divider()\n            st.subheader("Ficha del alumno")\n            opciones = {f"{r[\'codigo\']} \xb7 {r[\'alumno\']}": r["alumno_id"]\n                        for _, r in datos.iterrows()}\n            elegido = st.selectbox("Selecciona", list(opciones.keys()))\n            if elegido:\n                ficha_alumno(opciones[elegido])\n\n',
    ),
    (
        '    planes = db.listar_planes()\n    if planes.empty:\n',
        '    planes = db.listar_planes()\n    tab_vender, tab_lista = st.tabs(["Vender o renovar", "Todos los paquetes"])\n\n    if planes.empty:\n',
    ),
    (
        '    if planes.empty:\n        st.warning("No hay planes cargados. Crealos en la pantalla Planes.")\n        return\n',
        '    if planes.empty:\n        with tab_vender:\n            theme.vacio("No hay planes activos",\n                        "Crea al menos un plan en la pantalla Planes.")\n        with tab_lista:\n            theme.vacio("Sin pedidos", "Todavia no se registro ninguno.")\n        return\n',
    ),
    (
        '        return\n\n    tab_vender, tab_lista = st.tabs(["Vender o renovar", "Todos los paquetes"])\n\n',
        '        return\n\n',
    ),
    (
        '        if alumnos.empty:\n            st.info("Primero registra alumnos.")\n            return\n\n',
        '        if alumnos.empty:\n            theme.vacio("Todavia no hay alumnos",\n                        "Inscribelos en la pantalla Alumnos y vuelve aca a "\n                        "venderles su paquete.")\n        else:\n\n',
    ),
    (
        '\n        etiquetas = {\n            f"{r[\'codigo\']} \xb7 {r[\'alumno\']}  [{r[\'estado_real\']}]": r["alumno_id"]\n            for _, r in alumnos.iterrows()\n        }\n        elegido = st.selectbox("Alumno", list(etiquetas.keys()))\n        alumno_id = etiquetas[elegido]\n\n',
        '\n            etiquetas = {\n                f"{r[\'codigo\']} \xb7 {r[\'alumno\']}  [{r[\'estado_real\']}]": r["alumno_id"]\n                for _, r in alumnos.iterrows()\n            }\n            elegido = st.selectbox("Alumno", list(etiquetas.keys()))\n            alumno_id = etiquetas[elegido]\n\n',
    ),
    (
        '\n        vigente = db.paquete_vigente(alumno_id)\n        if vigente:\n            st.warning(\n                f"Este alumno ya tiene un paquete {vigente[\'estado_real\'].lower()}: "\n                f"{vigente[\'plan_nombre\']}, le quedan {vigente[\'sesiones_restantes\']} sesiones "\n                f"y vence el {logic.a_fecha(vigente[\'fecha_fin\']).strftime(\'%d/%m/%Y\')}. "\n                "Si vendes uno nuevo, el sistema consumira primero el que vence antes."\n            )\n\n',
        '\n            vigente = db.paquete_vigente(alumno_id)\n            if vigente:\n                st.warning(\n                    f"Este alumno ya tiene un paquete {vigente[\'estado_real\'].lower()}: "\n                    f"{vigente[\'plan_nombre\']}, le quedan {vigente[\'sesiones_restantes\']} sesiones "\n                    f"y vence el {logic.a_fecha(vigente[\'fecha_fin\']).strftime(\'%d/%m/%Y\')}. "\n                    "Si vendes uno nuevo, el sistema consumira primero el que vence antes."\n                )\n\n',
    ),
    (
        '\n        # Lo que ya sabemos del alumno se hereda, para no volver a escribirlo\n        datos_alumno = alumnos[alumnos["alumno_id"] == alumno_id].iloc[0]\n        try:\n            pedido = db.siguiente_pedido()\n            lista_vendedores = db.vendedores()\n            lista_sedes = db.sedes()\n        except Exception:\n            pedido, lista_vendedores, lista_sedes = 1, [], ["SURQUILLO"]\n\n',
        '\n            # Lo que ya sabemos del alumno se hereda, para no volver a escribirlo\n            datos_alumno = alumnos[alumnos["alumno_id"] == alumno_id].iloc[0]\n            try:\n                pedido = db.siguiente_pedido()\n                lista_vendedores = db.vendedores()\n                lista_sedes = db.sedes()\n            except Exception:\n                pedido, lista_vendedores, lista_sedes = 1, [], ["SURQUILLO"]\n\n',
    ),
    (
        '\n        with st.form("form_paquete"):\n            st.markdown(f"**Pedido N {pedido}**")\n\n',
        '\n            with st.form("form_paquete"):\n                st.markdown(f"**Pedido N {pedido}**")\n\n',
    ),
    (
        '\n            c1, c2, c3 = st.columns([2, 1, 1])\n            nombre_plan = c1.selectbox("Plan contratado", planes["nombre"].tolist())\n            plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()\n            fecha_pedido = c2.date_input("Fecha del pedido", value=logic.hoy(),\n                                         format="DD/MM/YYYY",\n                                         help="Cuando se cerro la venta")\n            inicio = c3.date_input("Inicio del plan", value=logic.hoy(),\n                                   format="DD/MM/YYYY",\n                                   help="Puede ser posterior a la fecha del pedido")\n\n',
        '\n                c1, c2, c3 = st.columns([2, 1, 1])\n                nombre_plan = c1.selectbox("Plan contratado", planes["nombre"].tolist())\n                plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()\n                fecha_pedido = c2.date_input("Fecha del pedido", value=logic.hoy(),\n                                             format="DD/MM/YYYY",\n                                             help="Cuando se cerro la venta")\n                inicio = c3.date_input("Inicio del plan", value=logic.hoy(),\n                                       format="DD/MM/YYYY",\n                                       help="Puede ser posterior a la fecha del pedido")\n\n',
    ),
    (
        '\n            # Se puede ajustar el plan para una venta puntual sin tocar el catalogo\n            a1, a2 = st.columns(2)\n            sesiones = a1.number_input("Sesiones", min_value=1,\n                                       value=int(plan["sesiones"]),\n                                       help="Cambialo solo si esta venta es una excepcion")\n            vigencia = a2.number_input("Dias de vigencia", min_value=1,\n                                       value=int(plan["vigencia_dias"]))\n            fin = logic.fecha_fin_plan(inicio, int(vigencia))\n\n',
        '\n                # Se puede ajustar el plan para una venta puntual sin tocar el catalogo\n                a1, a2 = st.columns(2)\n                sesiones = a1.number_input("Sesiones", min_value=1,\n                                           value=int(plan["sesiones"]),\n                                           help="Cambialo solo si esta venta es una excepcion")\n                vigencia = a2.number_input("Dias de vigencia", min_value=1,\n                                           value=int(plan["vigencia_dias"]))\n                fin = logic.fecha_fin_plan(inicio, int(vigencia))\n\n',
    ),
    (
        '\n            st.markdown("**Donde entrena**")\n            d1, d2 = st.columns([1, 2])\n            sede_previa = datos_alumno.get("sede")\n            if sede_previa and not pd.isna(sede_previa):\n                opciones = [sede_previa] + [x for x in lista_sedes if x != sede_previa]\n            else:\n                opciones = lista_sedes\n            sede = d1.selectbox("Sede y turno", opciones)\n            dias_previos = datos_alumno.get("dias_asiste")\n            if dias_previos and not pd.isna(dias_previos):\n                por_defecto = str(dias_previos).split()\n            else:\n                por_defecto = ["LUN", "MIE", "VIE"]\n            dias = d2.multiselect("Dias que asiste", DIAS_SEMANA,\n                                  default=[d for d in por_defecto if d in DIAS_SEMANA])\n\n',
        '\n                st.markdown("**Donde entrena**")\n                d1, d2 = st.columns([1, 2])\n                sede_previa = datos_alumno.get("sede")\n                if sede_previa and not pd.isna(sede_previa):\n                    opciones = [sede_previa] + [x for x in lista_sedes if x != sede_previa]\n                else:\n                    opciones = lista_sedes\n                sede = d1.selectbox("Sede y turno", opciones)\n                dias_previos = datos_alumno.get("dias_asiste")\n                if dias_previos and not pd.isna(dias_previos):\n                    por_defecto = str(dias_previos).split()\n                else:\n                    por_defecto = ["LUN", "MIE", "VIE"]\n                dias = d2.multiselect("Dias que asiste", DIAS_SEMANA,\n                                      default=[d for d in por_defecto if d in DIAS_SEMANA])\n\n',
    ),
    (
        '\n            st.markdown("**Cobro**")\n            e1, e2, e3 = st.columns(3)\n            precio = e1.number_input("Monto total (S/)", value=float(plan["precio"]),\n                                     min_value=0.0, step=10.0)\n            medio = e2.selectbox("Metodo de pago", MEDIOS_PAGO)\n            recibido = e3.text_input("Recibido por", placeholder="Ej. GARY",\n                                     help="Queda registrado como \'YAPE GARY\'")\n\n',
        '\n                st.markdown("**Cobro**")\n                e1, e2, e3 = st.columns(3)\n                precio = e1.number_input("Monto total (S/)", value=float(plan["precio"]),\n                                         min_value=0.0, step=10.0)\n                medio = e2.selectbox("Metodo de pago", MEDIOS_PAGO)\n                recibido = e3.text_input("Recibido por", placeholder="Ej. GARY",\n                                         help="Queda registrado como \'YAPE GARY\'")\n\n',
    ),
    (
        '\n            f1, f2, f3 = st.columns(3)\n            es_renovacion = bool(vigente) or bool(db.ultimo_paquete(alumno_id))\n            tipo = f1.selectbox("Renovacion o nuevo", ["NUEVO", "RENOVACION"],\n                                index=1 if es_renovacion else 0)\n            if lista_vendedores:\n                vendedor = f2.selectbox("Vendedor", lista_vendedores + ["Otro..."])\n            else:\n                vendedor = "Otro..."\n            if vendedor == "Otro...":\n                vendedor = f2.text_input("Nombre del vendedor", key="vend_nuevo")\n            pagado = f3.selectbox("Estado del pago", ["Pagado", "Pendiente"]) == "Pagado"\n\n',
        '\n                f1, f2, f3 = st.columns(3)\n                es_renovacion = bool(vigente) or bool(db.ultimo_paquete(alumno_id))\n                tipo = f1.selectbox("Renovacion o nuevo", ["NUEVO", "RENOVACION"],\n                                    index=1 if es_renovacion else 0)\n                if lista_vendedores:\n                    vendedor = f2.selectbox("Vendedor", lista_vendedores + ["Otro..."])\n                else:\n                    vendedor = "Otro..."\n                if vendedor == "Otro...":\n                    vendedor = f2.text_input("Nombre del vendedor", key="vend_nuevo")\n                pagado = f3.selectbox("Estado del pago", ["Pagado", "Pendiente"]) == "Pagado"\n\n',
    ),
    (
        '\n            obs = st.text_input("Observacion", placeholder="Opcional")\n\n',
        '\n                obs = st.text_input("Observacion", placeholder="Opcional")\n\n',
    ),
    (
        '\n            st.info(f"**{sesiones} sesiones** con vigencia del "\n                    f"{inicio.strftime(\'%d/%m/%Y\')} al **{fin.strftime(\'%d/%m/%Y\')}** "\n                    f"({vigencia} dias).")\n\n',
        '\n                st.info(f"**{sesiones} sesiones** con vigencia del "\n                        f"{inicio.strftime(\'%d/%m/%Y\')} al **{fin.strftime(\'%d/%m/%Y\')}** "\n                        f"({vigencia} dias).")\n\n',
    ),
    (
        '\n            if st.form_submit_button("Registrar pedido", type="primary"):\n                medio_completo = f"{medio} {recibido}".strip() if recibido else medio\n                try:\n                    db.crear_paquete(\n                        alumno_id, plan, inicio, precio, medio_completo, pagado,\n                        obs or None, fecha_pedido=fecha_pedido, sede=sede,\n                        dias_asiste=" ".join(dias),\n                        vendedor=(vendedor or "").strip().upper() or None,\n                        tipo=tipo, sesiones=int(sesiones), vigencia_dias=int(vigencia))\n                    st.toast(f"Pedido {pedido} registrado", icon="\\u2705")\n                    st.success(f"Pedido N {pedido} registrado. "\n                               f"Vence el {fin.strftime(\'%d/%m/%Y\')}.")\n                    st.rerun()\n                except Exception as e:\n                    st.error(f"No se pudo registrar: {e}")\n\n',
        '\n                if st.form_submit_button("Registrar pedido", type="primary"):\n                    medio_completo = f"{medio} {recibido}".strip() if recibido else medio\n                    try:\n                        db.crear_paquete(\n                            alumno_id, plan, inicio, precio, medio_completo, pagado,\n                            obs or None, fecha_pedido=fecha_pedido, sede=sede,\n                            dias_asiste=" ".join(dias),\n                            vendedor=(vendedor or "").strip().upper() or None,\n                            tipo=tipo, sesiones=int(sesiones), vigencia_dias=int(vigencia))\n                        st.toast(f"Pedido {pedido} registrado", icon="\\u2705")\n                        st.success(f"Pedido N {pedido} registrado. "\n                                   f"Vence el {fin.strftime(\'%d/%m/%Y\')}.")\n                        st.rerun()\n                    except Exception as e:\n                        st.error(f"No se pudo registrar: {e}")\n\n',
    ),
    (
        '        if datos.empty:\n            st.info("Sin resultados.")\n            return\n',
        '        if datos.empty:\n            theme.vacio("Sin paquetes que mostrar",\n                        "Cambia los filtros o registra el primer pedido.")\n            return\n',
    ),
]





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
    origen_app = CARPETA_BACKUP / "app.py"
    origen_tema = CARPETA_BACKUP / "theme.py"

    if not origen_app.exists() or not origen_tema.exists():
        error("No hay respaldos en " + str(CARPETA_BACKUP) + ". Nada que revertir.")

    shutil.copy2(origen_app, app)
    print("")
    print("  Revertido. app.py volvio a la version anterior.")
    print("")


def aplicar():
    app = Path("app.py")

    if not app.exists():
        error(
            "No encuentro app.py en esta carpeta.\n"
            "         Parate en la carpeta admin-streamlit y vuelve a intentar:\n"
            "         cd admin-streamlit"
        )

    texto_app, salto_app = leer(app)

    # ---------------------------------------------------------- idempotencia
    if MARCA_APLICADO in texto_app:
        print("")
        print("  El parche " + PARCHE + " ya estaba aplicado. No se toco nada.")
        print("")
        return

    if MARCA_ORIGINAL not in texto_app:
        error("Faltan los parches 001 a 006. Aplicalos primero, en orden.")

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

    # -------------------------------------------------------------- aplicar
    for viejo, nuevo in CAMBIOS_APP:
        texto_app = texto_app.replace(viejo, nuevo, 1)

    escribir(app, texto_app, salto_app)

    # ---------------------------------------------------------- verificacion
    final_app, _ = leer(app)

    controles = [
        ("Alumnos: sin return que corte la pantalla",
         'st.info("No hay alumnos que coincidan.")' not in final_app),
        ("Alumnos: aviso que explica que hacer",
         "Usa la pestana Inscribir alumno" in final_app),
        ("Paquetes: sin alumnos no corta",
         'st.info("Primero registra alumnos.")' not in final_app),
        ("Paquetes: sin planes muestra las pestanas",
         "No hay planes activos" in final_app),
        ("Paquetes: lista vacia con diseno",
         'st.info("Sin resultados.")' not in final_app),
        ("Version 1.8", 'VERSION = "1.8"' in final_app),
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
    print("  Ahora reinicia Streamlit:")
    print("    Ctrl+C en la terminal y luego  streamlit run app.py")
    print("")


if __name__ == "__main__":
    if "--revertir" in sys.argv:
        revertir()
    else:
        aplicar()