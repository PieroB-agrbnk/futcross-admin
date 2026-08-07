"""
FUTCROSS | Control de sesiones
Streamlit + Supabase. Ejecutar con:  streamlit run app.py
"""

from datetime import timedelta

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="FUTCROSS | Control de sesiones",
    page_icon="🟠",
    layout="wide",
    initial_sidebar_state="expanded",
)

import db          # noqa: E402
import logic       # noqa: E402
import theme       # noqa: E402

theme.aplicar_estilos()

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def fecha_larga(d) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def secreto(clave, defecto=None):
    """Delegamos en db.secreto para tener una sola forma de leer configuracion."""
    return db.secreto(clave, defecto)


# =====================================================================
# ACCESO
# =====================================================================
def es_admin() -> bool:
    return bool(st.session_state.get("admin_ok"))


def caja_de_acceso() -> None:
    """El kiosco queda abierto; la administracion pide PIN."""
    if es_admin():
        st.sidebar.caption("Sesion de administracion abierta")
        if st.sidebar.button("Cerrar sesion", width="stretch"):
            st.session_state["admin_ok"] = False
            st.session_state["pagina"] = "Check-in"
            st.rerun()
        return

    with st.sidebar.expander("Entrar como administrador"):
        pin = st.text_input("PIN", type="password", key="pin_input")
        if st.button("Entrar", width="stretch", type="primary"):
            if pin and pin == str(secreto("ADMIN_PIN", "futcross")):
                st.session_state["admin_ok"] = True
                st.rerun()
            else:
                st.error("PIN incorrecto.")


# =====================================================================
# 1. CHECK-IN (kiosco)
# =====================================================================
def procesar_marca(fila: dict) -> None:
    """Aplica las reglas y arma la tarjeta que ve el alumno."""
    alumno_id = fila["alumno_id"]
    nombre = fila.get("alumno") or f"{fila.get('nombres','')} {fila.get('apellidos','')}"
    codigo = fila.get("codigo", "")

    pq = db.paquete_vigente(alumno_id)
    if pq is None:
        pq = db.ultimo_paquete(alumno_id)

    marco = db.ya_marco_hoy(alumno_id)
    autorizado, motivo, mensaje = logic.puede_entrenar(pq, ya_marco_hoy=marco)

    usadas = int(pq["sesiones_usadas"]) if pq else None
    totales = int(pq["sesiones_totales"]) if pq else None
    vence = None
    if pq and logic.a_fecha(pq.get("fecha_fin")):
        vence = logic.a_fecha(pq["fecha_fin"]).strftime("%d/%m/%Y")

    if autorizado:
        try:
            db.marcar_asistencia(alumno_id, pq["id"], sede=fila.get("sede"), origen="KIOSCO")
            usadas += 1
        except Exception as e:
            if "uq_asistencia_dia" in str(e) or "duplicate" in str(e).lower():
                autorizado, motivo = False, "YA_MARCO"
                mensaje = "Ya registraste tu asistencia de hoy."
            else:
                st.error(f"No se pudo registrar la asistencia: {e}")
                return
    if not autorizado:
        db.registrar_bloqueo(alumno_id, nombre, motivo)

    veredicto = {
        "OK": "Pasa a la cancha",
        "YA_MARCO": "Ya marcaste hoy",
        "VENCIDO": "Paquete vencido",
        "AGOTADO": "Sesiones agotadas",
        "CONGELADO": "Paquete congelado",
        "CANCELADO": "Paquete anulado",
        "SIN_PAQUETE": "Sin paquete",
    }.get(motivo, "Revisar en recepcion")

    st.session_state["kiosco"] = {
        "html": theme.tarjeta_kiosco(nombre, codigo, veredicto, mensaje,
                                     autorizado, usadas, totales, vence),
        "hora": logic.ahora_hhmm(),
    }
    st.session_state["candidatos"] = []


def pagina_checkin() -> None:
    hoy = logic.hoy()
    theme.cabecera("Marca tu asistencia", fecha_larga(hoy).upper())

    izq, der = st.columns([1, 1.15], gap="large")

    with izq:
        with st.form("form_checkin", clear_on_submit=True):
            texto = st.text_input(
                "Escribe tu DNI, tu codigo (FC-0001) o tu nombre",
                placeholder="Ej. 45678912",
                label_visibility="visible",
            )
            enviado = st.form_submit_button("Marcar asistencia", type="primary",
                                            width="stretch")

        if enviado:
            st.session_state["kiosco"] = None
            candidatos = db.identificar(texto)
            if not candidatos:
                db.registrar_bloqueo(None, texto, "NO_ENCONTRADO")
                st.session_state["candidatos"] = []
                st.session_state["kiosco"] = {
                    "html": theme.tarjeta_kiosco(
                        "No te encontramos", texto.upper(), "Sin registro",
                        "Ese dato no figura en el sistema. Acercate a recepcion para inscribirte.",
                        autorizado=False),
                    "hora": logic.ahora_hhmm(),
                }
            elif len(candidatos) == 1:
                procesar_marca(candidatos[0])
            else:
                st.session_state["candidatos"] = candidatos

        for c in st.session_state.get("candidatos", []) or []:
            etiqueta = f"{c['codigo']} · {c.get('alumno','')}"
            if st.button(etiqueta, key=f"cand_{c['alumno_id']}", width="stretch"):
                procesar_marca(c)
                st.rerun()

        st.caption(
            "Cada alumno marca una sola vez por dia. "
            "Si tu paquete esta vencido o congelado, el sistema no lo descuenta."
        )

    with der:
        res = st.session_state.get("kiosco")
        if res:
            st.markdown(res["html"], unsafe_allow_html=True)
            st.caption(f"Registrado a las {res['hora']}")
        else:
            st.markdown(
                '<div class="fc-card"><div class="fc-meta">Esperando</div>'
                '<h2 class="fc-nombre">Marca tu ingreso</h2>'
                '<div class="fc-detalle">Escribe tu DNI a la izquierda y presiona '
                '<b>Marcar asistencia</b>.</div></div>',
                unsafe_allow_html=True)

    hoy_df = db.asistencias(hoy, hoy)
    st.divider()
    st.subheader(f"Ya entrenaron hoy · {len(hoy_df)}")
    if hoy_df.empty:
        st.caption("Todavia nadie marco asistencia.")
    else:
        st.dataframe(
            hoy_df[["hora", "codigo", "alumno"]].rename(
                columns={"hora": "Hora", "codigo": "Codigo", "alumno": "Alumno"}),
            width="stretch", hide_index=True, height=260)


# =====================================================================
# 2. PANEL DEL DIA
# =====================================================================
def pagina_panel() -> None:
    hoy = logic.hoy()
    theme.cabecera("Panel de control", fecha_larga(hoy).upper())

    alumnos = db.panel_alumnos()
    asist_hoy = db.asistencias(hoy, hoy)
    mes_ini = hoy.replace(day=1)
    asist_mes = db.asistencias(mes_ini, hoy)

    if alumnos.empty:
        st.info("Aun no hay alumnos registrados. Empieza por la pantalla **Alumnos**.")
        return

    alertas = alumnos.apply(lambda f: logic.alerta_renovacion(f.to_dict()), axis=1)
    alumnos["nivel"] = [a[0] for a in alertas]
    alumnos["motivo"] = [a[1] for a in alertas]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Alumnos activos", len(alumnos))
    c2.metric("Paquetes vigentes", int((alumnos["estado_real"] == "ACTIVO").sum()))
    c3.metric("Asistencias hoy", len(asist_hoy))
    c4.metric("Congelados", int((alumnos["estado_real"] == "CONGELADO").sum()))
    c5.metric("Por renovar", int(alumnos["nivel"].isin(["VENCIDO", "URGENTE"]).sum()),
              delta_color="inverse")

    st.divider()
    izq, der = st.columns([1.2, 1], gap="large")

    with izq:
        st.subheader("Atencion inmediata")
        criticos = alumnos[alumnos["nivel"].isin(["VENCIDO", "URGENTE"])]
        if criticos.empty:
            st.success("Nadie pendiente de renovar. Todo al dia.")
        else:
            for _, f in criticos.head(12).iterrows():
                color = theme.ROJO if f["nivel"] == "VENCIDO" else theme.AMBAR
                st.markdown(
                    f'<div class="fc-fila" style="border-left-color:{color}">'
                    f'<div><div class="nom">{f["alumno"]}</div>'
                    f'<div class="mot">{f["codigo"]} · {f["motivo"]}</div></div></div>',
                    unsafe_allow_html=True)
            if len(criticos) > 12:
                st.caption(f"y {len(criticos) - 12} mas en la pantalla Renovaciones.")

    with der:
        st.subheader("Asistencias del mes")
        if asist_mes.empty:
            st.caption("Sin asistencias este mes.")
        else:
            serie = (asist_mes.groupby("fecha").size()
                     .rename("Asistencias").reset_index().set_index("fecha"))
            st.bar_chart(serie, color=theme.NARANJA, height=240)
            prom = round(len(asist_mes) / max(1, len(serie)), 1)
            st.caption(f"{len(asist_mes)} asistencias en {len(serie)} dias de entrenamiento "
                       f"(promedio {prom} por dia).")

    st.divider()
    st.subheader("Intentos sin paquete valido")
    bl = db.bloqueos(hoy - timedelta(days=7), hoy)
    if bl.empty:
        st.caption("Nadie intento entrenar sin paquete en los ultimos 7 dias.")
    else:
        st.dataframe(
            bl[["fecha", "hora", "alumno", "motivo"]].rename(
                columns={"fecha": "Fecha", "hora": "Hora",
                         "alumno": "Alumno", "motivo": "Motivo"}),
            width="stretch", hide_index=True, height=220)


# =====================================================================
# 3. ALUMNOS
# =====================================================================
def pagina_alumnos() -> None:
    theme.cabecera("Alumnos", fecha_larga(logic.hoy()).upper())

    tab_lista, tab_nuevo = st.tabs(["Lista", "Inscribir alumno"])

    with tab_lista:
        col_a, col_b = st.columns([2, 1])
        texto = col_a.text_input("Buscar", placeholder="Nombre, DNI, codigo o telefono")
        filtro = col_b.selectbox("Estado", ["Todos", "ACTIVO", "VENCIDO", "AGOTADO",
                                            "CONGELADO", "SIN PAQUETE"])

        datos = db.buscar_alumnos(texto) if texto else db.panel_alumnos()
        if datos.empty:
            st.info("No hay alumnos que coincidan.")
            return
        if filtro != "Todos":
            datos = datos[datos["estado_real"] == filtro]

        vista = datos[["codigo", "alumno", "dni", "telefono", "plan_nombre",
                       "sesiones_restantes", "fecha_fin", "estado_real",
                       "fecha_inscripcion"]].copy()
        vista.columns = ["Codigo", "Alumno", "DNI", "Telefono", "Plan",
                         "Sesiones restantes", "Vence", "Estado", "Inscrito el"]
        st.dataframe(vista, width="stretch", hide_index=True, height=420)
        st.download_button("Descargar CSV", vista.to_csv(index=False).encode("utf-8"),
                           "futcross_alumnos.csv", "text/csv")

        st.divider()
        st.subheader("Ficha del alumno")
        opciones = {f"{r['codigo']} · {r['alumno']}": r["alumno_id"]
                    for _, r in datos.iterrows()}
        elegido = st.selectbox("Selecciona", list(opciones.keys()))
        if elegido:
            ficha_alumno(opciones[elegido])

    with tab_nuevo:
        with st.form("form_alumno", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombres = c1.text_input("Nombres *")
            apellidos = c2.text_input("Apellidos *")
            dni = c1.text_input("DNI")
            telefono = c2.text_input("Telefono (9 digitos)")
            email = c1.text_input("Correo")
            nacimiento = c2.date_input("Fecha de nacimiento", value=None,
                                       min_value=logic.hoy() - timedelta(days=365 * 80),
                                       max_value=logic.hoy(), format="DD/MM/YYYY")
            inscripcion = c1.date_input("Fecha de inscripcion", value=logic.hoy(),
                                        format="DD/MM/YYYY")
            sede = c2.text_input("Sede", value="Sede principal")
            horario = c1.text_input("Horario habitual", placeholder="Lun/Mie/Vie 8 p.m.")
            emergencia = c2.text_input("Contacto de emergencia")
            notas = st.text_area("Notas", placeholder="Lesiones previas, observaciones, etc.")

            if st.form_submit_button("Guardar alumno", type="primary"):
                if not nombres or not apellidos:
                    st.error("Nombres y apellidos son obligatorios.")
                else:
                    try:
                        creado = db.crear_alumno({
                            "nombres": nombres.strip().title(),
                            "apellidos": apellidos.strip().title(),
                            "dni": logic.solo_digitos(dni) or None,
                            "telefono": logic.solo_digitos(telefono) or None,
                            "email": email.strip() or None,
                            "fecha_nacimiento": nacimiento,
                            "fecha_inscripcion": inscripcion,
                            "sede": sede, "horario": horario,
                            "contacto_emergencia": emergencia, "notas": notas,
                        })
                        st.success(f"Alumno registrado con codigo {creado[0]['codigo']}. "
                                   "Ahora asignale un paquete en la pantalla Paquetes.")
                    except Exception as e:
                        st.error(f"No se pudo guardar: {e}")


def ficha_alumno(alumno_id: str) -> None:
    a = db.alumno(alumno_id)
    if not a:
        return
    paquetes = db.paquetes_de(alumno_id)

    c1, c2, c3 = st.columns([1.3, 1, 1])
    with c1:
        st.markdown(f"**{a['nombres']} {a['apellidos']}** · {a['codigo']}")
        st.caption(f"DNI {a.get('dni') or '—'} · Tel. {a.get('telefono') or '—'}")
        st.caption(f"Inscrito el {logic.a_fecha(a['fecha_inscripcion']).strftime('%d/%m/%Y')}"
                   f" · {a.get('horario') or 'sin horario fijo'}")
    vigente = None if paquetes.empty else paquetes[
        paquetes["estado_real"].isin(["ACTIVO", "CONGELADO"])]
    if vigente is not None and not vigente.empty:
        p = vigente.iloc[0]
        c2.metric("Sesiones restantes", f"{p['sesiones_restantes']} de {p['sesiones_totales']}")
        c3.metric("Vence", logic.a_fecha(p["fecha_fin"]).strftime("%d/%m/%Y"),
                  f"{p['dias_restantes']} dias")
        if int(p["sesiones_usadas"]) > 0:
            ritmo = logic.ritmo_semanal(int(p["sesiones_usadas"]),
                                        logic.a_fecha(p["fecha_inicio"]))
            proy = logic.proyeccion_termino(int(p["sesiones_usadas"]),
                                            int(p["sesiones_totales"]),
                                            logic.a_fecha(p["fecha_inicio"]))
            texto = f"Ritmo actual: {ritmo} sesiones por semana."
            if proy:
                texto += f" A ese ritmo termina sus sesiones alrededor del {proy.strftime('%d/%m/%Y')}."
            st.caption(texto)
    else:
        c2.metric("Sesiones restantes", "—")
        c3.metric("Vence", "—")

    if not paquetes.empty:
        st.markdown("**Historial de paquetes**")
        hist = paquetes[["plan_nombre", "fecha_inicio", "fecha_fin", "sesiones_usadas",
                         "sesiones_totales", "dias_congelados", "precio", "estado_real"]].copy()
        hist.columns = ["Plan", "Inicio", "Fin", "Usadas", "Totales",
                        "Dias congelados", "Precio", "Estado"]
        st.dataframe(hist, width="stretch", hide_index=True)

    asis = db.asistencias(logic.hoy() - timedelta(days=180), logic.hoy())
    if not asis.empty:
        mias = asis[asis["alumno_id"] == alumno_id]
        if not mias.empty:
            st.markdown("**Ultimas asistencias**")
            for _, r in mias.head(8).iterrows():
                col1, col2 = st.columns([4, 1])
                col1.write(f"{logic.a_fecha(r['fecha']).strftime('%d/%m/%Y')} · {r['hora']}")
                if es_admin() and col2.button("Anular", key=f"anu_{r['id']}"):
                    db.anular_asistencia(r["id"])
                    st.success("Asistencia anulada. La sesion volvio al saldo del alumno.")
                    st.rerun()


# =====================================================================
# 4. PAQUETES
# =====================================================================
def pagina_paquetes() -> None:
    theme.cabecera("Paquetes y renovaciones", fecha_larga(logic.hoy()).upper())

    planes = db.listar_planes()
    if planes.empty:
        st.warning("No hay planes cargados. Crealos en la pantalla Planes.")
        return

    tab_vender, tab_lista = st.tabs(["Vender o renovar", "Todos los paquetes"])

    with tab_vender:
        alumnos = db.panel_alumnos()
        if alumnos.empty:
            st.info("Primero registra alumnos.")
            return

        etiquetas = {
            f"{r['codigo']} · {r['alumno']}  [{r['estado_real']}]": r["alumno_id"]
            for _, r in alumnos.iterrows()
        }
        elegido = st.selectbox("Alumno", list(etiquetas.keys()))
        alumno_id = etiquetas[elegido]

        vigente = db.paquete_vigente(alumno_id)
        if vigente:
            st.warning(
                f"Este alumno ya tiene un paquete {vigente['estado_real'].lower()}: "
                f"{vigente['plan_nombre']}, le quedan {vigente['sesiones_restantes']} sesiones "
                f"y vence el {logic.a_fecha(vigente['fecha_fin']).strftime('%d/%m/%Y')}. "
                "Si vendes uno nuevo, el sistema consumira primero el que vence antes."
            )

        with st.form("form_paquete"):
            c1, c2 = st.columns(2)
            nombre_plan = c1.selectbox("Plan", planes["nombre"].tolist())
            plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()
            inicio = c2.date_input("Inicio de vigencia", value=logic.hoy(), format="DD/MM/YYYY")
            fin = logic.fecha_fin_plan(inicio, int(plan["vigencia_dias"]))

            c3, c4, c5 = st.columns(3)
            precio = c3.number_input("Precio cobrado (S/)", value=float(plan["precio"]),
                                     min_value=0.0, step=10.0)
            medio = c4.selectbox("Medio de pago", ["Yape", "Plin", "Efectivo",
                                                   "Transferencia", "Tarjeta", "Otro"])
            pagado = c5.selectbox("Estado del pago", ["Pagado", "Pendiente"]) == "Pagado"
            obs = st.text_input("Observacion", placeholder="Opcional")

            st.info(f"**{plan['sesiones']} sesiones** con vigencia del "
                    f"{inicio.strftime('%d/%m/%Y')} al **{fin.strftime('%d/%m/%Y')}** "
                    f"({plan['vigencia_dias']} dias).")

            if st.form_submit_button("Registrar paquete", type="primary"):
                try:
                    db.crear_paquete(alumno_id, plan, inicio, precio, medio, pagado, obs or None)
                    st.success(f"Paquete registrado. Vence el {fin.strftime('%d/%m/%Y')}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo registrar: {e}")

    with tab_lista:
        estados = st.multiselect(
            "Estado", ["ACTIVO", "CONGELADO", "VENCIDO", "AGOTADO", "CANCELADO"],
            default=["ACTIVO", "CONGELADO"])
        datos = db.listar_paquetes(estados or None)
        if datos.empty:
            st.info("Sin resultados.")
            return
        vista = datos[["codigo", "alumno", "plan_nombre", "fecha_inicio", "fecha_fin",
                       "sesiones_usadas", "sesiones_totales", "sesiones_restantes",
                       "dias_restantes", "dias_congelados", "precio", "pagado",
                       "estado_real"]].copy()
        vista.columns = ["Codigo", "Alumno", "Plan", "Inicio", "Fin", "Usadas", "Totales",
                         "Restantes", "Dias por vencer", "Dias congelados", "Precio",
                         "Pagado", "Estado"]
        st.dataframe(vista, width="stretch", hide_index=True, height=430)
        st.download_button("Descargar CSV", vista.to_csv(index=False).encode("utf-8"),
                           "futcross_paquetes.csv", "text/csv")


# =====================================================================
# 5. CONGELAMIENTOS
# =====================================================================
def pagina_congelamientos() -> None:
    theme.cabecera("Congelamientos por lesion", fecha_larga(logic.hoy()).upper())
    st.caption(
        "Congelar detiene el reloj del paquete. Al dar de alta, el sistema suma "
        "los dias perdidos a la fecha de vencimiento, asi el alumno no pierde lo que pago."
    )

    tab_nuevo, tab_activos, tab_hist = st.tabs(["Congelar", "Congelados", "Historial"])

    with tab_nuevo:
        activos = db.listar_paquetes(["ACTIVO"])
        if activos.empty:
            st.info("No hay paquetes activos para congelar.")
        else:
            etiquetas = {
                f"{r['codigo']} · {r['alumno']} — {r['plan_nombre']} "
                f"({r['sesiones_restantes']} sesiones, vence {logic.a_fecha(r['fecha_fin']).strftime('%d/%m')})":
                    (r["id"], r["alumno_id"])
                for _, r in activos.iterrows()
            }
            elegido = st.selectbox("Paquete", list(etiquetas.keys()))
            paquete_id, alumno_id = etiquetas[elegido]

            with st.form("form_congelar"):
                c1, c2 = st.columns(2)
                motivo = c1.selectbox("Motivo",
                                      ["LESION", "ENFERMEDAD", "VIAJE", "TRABAJO", "OTRO"])
                desde = c2.date_input("Congelar desde", value=logic.hoy(), format="DD/MM/YYYY")
                detalle = st.text_input("Detalle",
                                        placeholder="Ej. esguince de tobillo, 3 semanas de reposo")
                if st.form_submit_button("Congelar paquete", type="primary"):
                    try:
                        db.congelar(paquete_id, alumno_id, motivo, detalle, desde)
                        st.success("Paquete congelado. No se le descontaran sesiones "
                                   "hasta que lo reactives.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo congelar: {e}")

    with tab_activos:
        cong = db.congelamientos(activos=True)
        if cong.empty:
            st.info("No hay alumnos congelados.")
        else:
            for _, c in cong.iterrows():
                inicio = logic.a_fecha(c["fecha_inicio"])
                dias = logic.dias_congelamiento(inicio, logic.hoy())
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.markdown(f"**{c['alumno']}** · {c['codigo']}")
                    c1.caption(f"{c['motivo'].title()} · {c.get('detalle') or 'sin detalle'}")
                    c2.metric("Congelado desde", inicio.strftime("%d/%m/%Y"), f"{dias} dias")
                    alta = c3.date_input("Fecha de alta", value=logic.hoy(),
                                         min_value=inicio, format="DD/MM/YYYY",
                                         key=f"alta_{c['id']}")
                    if c3.button("Reactivar", key=f"react_{c['id']}",
                                 type="primary", width="stretch"):
                        try:
                            d = db.reactivar(c["id"], alta)
                            st.success(f"Alumno reactivado. Se sumaron {d} dias "
                                       "a la vigencia del paquete.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo reactivar: {e}")

    with tab_hist:
        hist = db.congelamientos(activos=None)
        if hist.empty:
            st.caption("Sin registros.")
        else:
            vista = hist[["codigo", "alumno", "motivo", "detalle", "fecha_inicio",
                          "fecha_fin", "dias_aplicados", "activo"]].copy()
            vista.columns = ["Codigo", "Alumno", "Motivo", "Detalle", "Desde",
                             "Hasta", "Dias devueltos", "Vigente"]
            st.dataframe(vista, width="stretch", hide_index=True)


# =====================================================================
# 6. RENOVACIONES
# =====================================================================
def pagina_renovaciones() -> None:
    theme.cabecera("A quien hay que llamar", fecha_larga(logic.hoy()).upper())

    alumnos = db.panel_alumnos()
    if alumnos.empty:
        st.info("Sin alumnos registrados.")
        return

    alertas = alumnos.apply(lambda f: logic.alerta_renovacion(f.to_dict()), axis=1)
    alumnos["nivel"] = [a[0] for a in alertas]
    alumnos["motivo"] = [a[1] for a in alertas]

    orden = {"VENCIDO": 0, "URGENTE": 1, "PROXIMO": 2, "OK": 3}
    alumnos["orden"] = alumnos["nivel"].map(orden)
    alumnos = alumnos.sort_values(["orden", "apellidos"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Ya vencidos", int((alumnos["nivel"] == "VENCIDO").sum()))
    c2.metric("Urgentes", int((alumnos["nivel"] == "URGENTE").sum()))
    c3.metric("Proximos", int((alumnos["nivel"] == "PROXIMO").sum()))

    niveles = st.multiselect("Mostrar", ["VENCIDO", "URGENTE", "PROXIMO", "OK"],
                             default=["VENCIDO", "URGENTE", "PROXIMO"])
    datos = alumnos[alumnos["nivel"].isin(niveles)]

    if datos.empty:
        st.success("No hay nadie pendiente.")
        return

    st.divider()
    for _, f in datos.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([2.2, 1.3, 1])
            c1.markdown(f"**{f['alumno']}** · {f['codigo']}")
            c1.caption(f"{f.get('plan_nombre') or 'Sin plan'} · {f['motivo']}")
            c2.markdown(theme.chip(f["estado_real"]), unsafe_allow_html=True)
            if pd.notna(f.get("fecha_fin")):
                c2.caption(f"Vence {logic.a_fecha(f['fecha_fin']).strftime('%d/%m/%Y')} · "
                           f"{f.get('sesiones_restantes')} sesiones")
            link = logic.link_whatsapp(
                f.get("telefono") or "",
                logic.mensaje_renovacion(f["alumno"], f["motivo"], f.get("plan_nombre") or ""))
            if link:
                c3.link_button("WhatsApp", link, width="stretch")
            else:
                c3.caption("Sin telefono")

    vista = datos[["codigo", "alumno", "telefono", "plan_nombre", "sesiones_restantes",
                   "fecha_fin", "estado_real", "nivel", "motivo"]]
    st.download_button("Descargar lista de llamadas",
                       vista.to_csv(index=False).encode("utf-8"),
                       "futcross_renovaciones.csv", "text/csv")


# =====================================================================
# 7. REPORTES
# =====================================================================
def pagina_reportes() -> None:
    theme.cabecera("Reportes", fecha_larga(logic.hoy()).upper())
    hoy = logic.hoy()

    c1, c2 = st.columns(2)
    desde = c1.date_input("Desde", value=hoy.replace(day=1), format="DD/MM/YYYY")
    hasta = c2.date_input("Hasta", value=hoy, format="DD/MM/YYYY")
    if desde > hasta:
        st.error("La fecha inicial no puede ser posterior a la final.")
        return

    asis = db.asistencias(desde, hasta)
    paquetes = db.listar_paquetes()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Asistencias", len(asis))
    k2.metric("Alumnos distintos", asis["alumno_id"].nunique() if not asis.empty else 0)

    if not paquetes.empty:
        paquetes["fecha_inicio_d"] = paquetes["fecha_inicio"].map(logic.a_fecha)
        vendidos = paquetes[(paquetes["fecha_inicio_d"] >= desde) &
                            (paquetes["fecha_inicio_d"] <= hasta) &
                            (paquetes["estado_real"] != "CANCELADO")]
        k3.metric("Paquetes vendidos", len(vendidos))
        k4.metric("Ingresos", f"S/ {vendidos['precio'].sum():,.0f}")
    else:
        vendidos = pd.DataFrame()

    st.divider()
    if asis.empty:
        st.info("No hay asistencias en el rango elegido.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Asistencias por dia")
            serie = asis.groupby("fecha").size().rename("Asistencias")
            st.bar_chart(serie, color=theme.NARANJA, height=280)
        with col2:
            st.subheader("Alumnos mas constantes")
            top = (asis.groupby("alumno").size().rename("Sesiones")
                   .sort_values(ascending=False).head(10))
            st.bar_chart(top, color=theme.NARANJA, horizontal=True, height=280)

        st.subheader("Detalle")
        detalle = asis[["fecha", "hora", "codigo", "alumno", "origen"]].copy()
        detalle.columns = ["Fecha", "Hora", "Codigo", "Alumno", "Origen"]
        st.dataframe(detalle, width="stretch", hide_index=True, height=320)
        st.download_button("Descargar asistencias",
                           detalle.to_csv(index=False).encode("utf-8"),
                           f"futcross_asistencias_{desde}_{hasta}.csv", "text/csv")

    if not vendidos.empty:
        st.divider()
        st.subheader("Ventas por plan")
        ventas = (vendidos.groupby("plan_nombre")
                  .agg(Paquetes=("id", "count"), Ingresos=("precio", "sum"))
                  .sort_values("Ingresos", ascending=False))
        st.dataframe(ventas, width="stretch")


# =====================================================================
# 8. PLANES
# =====================================================================
def pagina_planes() -> None:
    theme.cabecera("Planes", fecha_larga(logic.hoy()).upper())

    planes = db.listar_planes(solo_activos=False)
    if not planes.empty:
        vista = planes[["nombre", "sesiones", "vigencia_dias", "precio",
                        "descripcion", "activo"]].copy()
        vista.columns = ["Plan", "Sesiones", "Vigencia (dias)", "Precio",
                         "Descripcion", "Activo"]
        st.dataframe(vista, width="stretch", hide_index=True)

        st.markdown("**Activar o desactivar**")
        c1, c2 = st.columns([3, 1])
        elegido = c1.selectbox("Plan", planes["nombre"].tolist())
        fila = planes[planes["nombre"] == elegido].iloc[0]
        etiqueta = "Desactivar" if fila["activo"] else "Activar"
        if c2.button(etiqueta, width="stretch"):
            db.actualizar_plan(fila["id"], {"activo": not bool(fila["activo"])})
            st.rerun()

    st.divider()
    with st.form("form_plan", clear_on_submit=True):
        st.markdown("**Nuevo plan**")
        c1, c2, c3, c4 = st.columns(4)
        nombre = c1.text_input("Nombre")
        sesiones = c2.number_input("Sesiones", min_value=1, value=12)
        vigencia = c3.number_input("Vigencia (dias)", min_value=1, value=30)
        precio = c4.number_input("Precio (S/)", min_value=0.0, value=180.0, step=10.0)
        desc = st.text_input("Descripcion")
        if st.form_submit_button("Crear plan", type="primary"):
            if not nombre:
                st.error("Ponle un nombre al plan.")
            else:
                try:
                    db.crear_plan(nombre, sesiones, vigencia, precio, desc)
                    st.success("Plan creado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo crear: {e}")


# =====================================================================
# NAVEGACION
# =====================================================================
PAGINAS_ADMIN = {
    "Check-in": pagina_checkin,
    "Panel": pagina_panel,
    "Alumnos": pagina_alumnos,
    "Paquetes": pagina_paquetes,
    "Congelamientos": pagina_congelamientos,
    "Renovaciones": pagina_renovaciones,
    "Reportes": pagina_reportes,
    "Planes": pagina_planes,
}


def main() -> None:
    st.session_state.setdefault("candidatos", [])
    st.session_state.setdefault("kiosco", None)

    st.sidebar.markdown(
        '<div class="fc-logo" style="color:#101215">FUT<span>CROSS</span></div>'
        '<div class="fc-sub" style="color:#6B7280">Control de sesiones</div><br>',
        unsafe_allow_html=True)

    if es_admin():
        pagina = st.sidebar.radio("Ir a", list(PAGINAS_ADMIN.keys()),
                                  label_visibility="collapsed")
    else:
        pagina = "Check-in"
        st.sidebar.info("Modo kiosco. Los alumnos solo marcan asistencia.")

    caja_de_acceso()
    st.sidebar.divider()
    st.sidebar.caption("FutCross · entrenamiento funcional de futbol")

    PAGINAS_ADMIN[pagina]()


if __name__ == "__main__":
    main()
