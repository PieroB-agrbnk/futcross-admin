"""
FUTCROSS | Control de sesiones
Streamlit + Supabase. Ejecutar con:  streamlit run app.py
"""

import hmac
import time
from datetime import timedelta

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="FUTCROSS | Control de sesiones",
    page_icon="🟠",
    layout="wide",
    initial_sidebar_state="expanded",
)

import acceso      # noqa: E402
import db          # noqa: E402
import importar    # noqa: E402
import logic       # noqa: E402
import theme       # noqa: E402

theme.aplicar_estilos()

# Se muestra en la barra lateral. Sirve para saber de un vistazo si la version
# que estas viendo en la nube es la misma que tienes en tu computadora.
VERSION = "3.3"

DIAS_SEMANA = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]
TURNOS = ["MANANA", "TARDE", "NOCHE"]
MEDIOS_PAGO = ["YAPE", "PLIN", "EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO"]

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def selector_de_grupo(etiqueta="Grupo", clave=None, grupo_actual=None,
                      dias_previos=None, dias_del_plan=None):
    """Elige el grupo y, dentro de el, que dias asiste el alumno.

    El grupo dice que dias hay disponibles (Surquillo abre lun, mie y vie).
    El plan dice cuantos usa por semana (el basico, dos). Cual de esos dias
    va cada alumno es decision suya, asi que se pregunta.

    Devuelve (grupo_id, dias_elegidos, texto).
    """
    grupos = db.listar_grupos()
    if grupos.empty:
        st.warning("No hay grupos cargados. Corre migracion-009.sql en Supabase.")
        return None, "", ""

    opciones = {
        f"{g['nombre']} - {g['genero'].title()} ({g['dias']})": g
        for _, g in grupos.iterrows()
    }
    llaves = list(opciones.keys())
    indice = 0
    if grupo_actual:
        for i, k in enumerate(llaves):
            if opciones[k]["id"] == grupo_actual:
                indice = i
                break

    c1, c2 = st.columns([1.4, 1.6])
    elegido = c1.selectbox(etiqueta, llaves, index=indice, key=clave)
    g = opciones[elegido]
    disponibles = [d for d in str(g["dias"]).split() if d in DIAS_SEMANA]

    # Que dias viene: por defecto los que ya tenia, o los primeros que
    # alcancen para la frecuencia del plan.
    previos = [d for d in (dias_previos or "").split() if d in disponibles]
    if not previos:
        previos = disponibles[:dias_del_plan] if dias_del_plan else disponibles

    # La clave incluye el grupo: al cambiar de grupo, Streamlit crea un
    # widget nuevo y vuelve a proponer los dias correctos. Sin esto, los
    # dias del grupo anterior no existen en la lista nueva y queda vacia.
    elegidos = c2.multiselect(
        "Dias que asiste", disponibles, default=previos,
        key=f"{clave}_dias_{g['id']}" if clave else None,
        help=f"Este grupo entrena {' '.join(disponibles)}. "
             "Marca solo los dias que viene este alumno; puede ser uno solo.")

    if not elegidos:
        c2.error("Marca al menos un dia: de ahi sale la fecha de vencimiento.")
    elif dias_del_plan and len(elegidos) != dias_del_plan:
        c2.caption(f"Nota: el plan es de {dias_del_plan} "
                   f"{'dia' if dias_del_plan == 1 else 'dias'} por semana y "
                   f"marcaste {len(elegidos)}. Se respeta lo que marcaste.")

    # Se ordenan como la semana, no como se hizo clic
    orden = {d: i for i, d in enumerate(DIAS_SEMANA)}
    dias = " ".join(sorted(elegidos, key=lambda d: orden[d]))
    texto = f"{g['sede']} {g['hora']}"
    if dias:
        texto += f" - {logic.frecuencia(dias)}"
    return g["id"], dias, texto


def fecha_larga(d) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def secreto(clave, defecto=None):
    """Delegamos en db.secreto para tener una sola forma de leer configuracion."""
    return db.secreto(clave, defecto)


def esc(valor) -> str:
    """Atajo al escapador de theme, para el HTML que se arma en estas pantallas."""
    return theme.esc(valor)


def descargar_csv(etiqueta: str, datos: pd.DataFrame, archivo: str, clave=None) -> None:
    """Boton de descarga en el formato que abre bien el Excel de la oficina.

    Excel en configuracion regional peruana usa el punto y coma como
    separador: con comas metia todo en la columna A y habia que usar el
    asistente de importacion. El BOM (utf-8-sig) es lo que hace que las
    tildes y la enie se vean bien al abrirlo con doble clic.
    """
    st.download_button(
        etiqueta,
        datos.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        archivo, "text/csv", key=clave)


def con_alertas(alumnos: pd.DataFrame) -> pd.DataFrame:
    """Agrega las columnas nivel y motivo del semaforo de renovacion.

    La misma cuenta la hacian por separado el Panel, Renovaciones y el
    resumen de la barra lateral. Estaba escrita tres veces, con el
    riesgo de que se fueran despegando entre si.
    """
    if alumnos.empty:
        return alumnos
    alertas = [logic.alerta_renovacion(f) for f in alumnos.to_dict("records")]
    alumnos = alumnos.copy()
    alumnos["nivel"] = [a[0] for a in alertas]
    alumnos["motivo"] = [a[1] for a in alertas]
    return alumnos


# =====================================================================
# ACCESO
# =====================================================================
# Quien puede ver que. El entrenador necesita saber quien entrena y cuantas
# sesiones le quedan a cada alumno, pero no tiene por que ver los ingresos ni
# poder cambiar precios: eso es plata y es del administrador.
PERMISOS = {
    "admin": ["Panel", "Marcar asistencia", "Renovaciones", "Alumnos",
              "Paquetes", "Congelamientos", "Reportes", "Planes",
              "Dias sin entrenar", "Carga masiva", "Accesos",
              "Otros ingresos"],
    "entrenador": ["Panel", "Marcar asistencia", "Alumnos", "Renovaciones"],
}

ETIQUETA_ROL = {"admin": "Administracion", "entrenador": "Entrenador"}


def rol() -> str | None:
    return st.session_state.get("rol")


def hay_sesion() -> bool:
    return rol() in PERMISOS


def es_admin() -> bool:
    """Solo la administracion vende, congela, anula y ve la plata."""
    return rol() == "admin"


def paginas_permitidas() -> list:
    return PERMISOS.get(rol(), [])


# Tras 5 intentos fallidos se bloquea el ingreso, y cada bloque siguiente dura
# el doble. Cinco intentos alcanzan de sobra para un dedo torpe, y frenan a
# quien este probando claves al azar.
INTENTOS_MAX = 5
CASTIGO_SEGUNDOS = 120
VENTANA_INTENTOS = 15    # minutos que se miran hacia atras para contar fallos

# Una sesion de administracion abierta en la tablet de la cancha se cierra
# sola tras dos horas sin uso. Sin esto quedaba abierta hasta que alguien
# se acordara de salir, con los ingresos y los precios a la vista.
INACTIVIDAD_MAX = 2 * 60 * 60


# Las claves se guardan hasheadas en la tabla `config` y se cambian desde
# la pantalla Accesos. Si todavia no hay nada guardado (recien aplicado el
# parche), se usan las de los secretos del servidor, para que nadie quede
# afuera. Cambiar una clave desde el panel la mueve a la base y a partir de
# ahi manda esa.
CLAVES_PIN = {"admin": "pin_admin", "entrenador": "pin_entrenador"}
SECRETOS_PIN = {"admin": "ADMIN_PIN", "entrenador": "ENTRENADOR_PIN"}


def pin_guardado(rol_pin: str) -> str | None:
    """Devuelve el hash de la base, o el PIN suelto de los secretos."""
    try:
        guardado = db.leer_config(CLAVES_PIN[rol_pin])
    except Exception:
        guardado = None
    return guardado or secreto(SECRETOS_PIN[rol_pin])


def comparar_pin(escrito: str, guardado: str | None) -> bool:
    """Acepta las dos formas: hash de la base o PIN plano de los secretos."""
    if not escrito or not guardado:
        return False
    if acceso.es_hash(guardado):
        return acceso.verificar_pin(escrito, guardado)
    # compare_digest tarda lo mismo acierte o falle
    return hmac.compare_digest(str(escrito), str(guardado))


def _control_acceso() -> dict:
    return st.session_state.setdefault("acceso", {"fallos": 0, "hasta": 0.0})


def fallos_totales() -> int:
    """Fallos de esta pestana y de cualquier otra, en la ventana de tiempo.

    El contador de `session_state` se reinicia con solo abrir una pestana
    nueva, asi que por si solo no frena a nadie. El de la base cuenta los
    intentos de toda la instalacion.
    """
    control = _control_acceso()
    return max(control["fallos"], db.intentos_fallidos_recientes(VENTANA_INTENTOS))


def segundos_de_castigo() -> int:
    """Bloqueado si esta pestana ya cumplio su castigo, o si en los ultimos
    15 minutos hubo demasiados fallos en cualquier pestana."""
    propio = max(0, int(_control_acceso()["hasta"] - time.time()))
    if propio:
        return propio
    if fallos_totales() >= INTENTOS_MAX:
        return CASTIGO_SEGUNDOS
    return 0


def registrar_fallo() -> None:
    control = _control_acceso()
    control["fallos"] += 1

    # Se anota cada fallo, no solo el ultimo: es lo que permite contarlos
    # entre pestanas distintas. Llegado el tope el ingreso queda bloqueado,
    # asi que la tabla no puede crecer sin control.
    try:
        db.registrar_bloqueo(
            None, f"Intento de acceso al panel (fallo {control['fallos']})",
            "PIN_FALLIDO")
    except Exception:
        pass

    if control["fallos"] >= INTENTOS_MAX:
        exceso = control["fallos"] - INTENTOS_MAX
        control["hasta"] = time.time() + CASTIGO_SEGUNDOS * (2 ** min(exceso, 5))


def sesion_expirada() -> bool:
    """Cierra la sesion si estuvo mas de INACTIVIDAD_MAX sin tocar nada."""
    ultimo = st.session_state.get("ultimo_uso")
    ahora = time.time()
    if ultimo and ahora - ultimo > INACTIVIDAD_MAX:
        return True
    st.session_state["ultimo_uso"] = ahora
    return False


def pantalla_login() -> None:
    """Sin PIN no se ve absolutamente nada: ni el menu ni los datos.

    El alumno no tiene por que llegar aca. Su pantalla es el kiosco de la
    tablet, que es una app aparte.
    """
    theme.ocultar_navegacion()
    theme.pantalla_acceso()

    # Sin PIN configurado no se entra. Antes habia un valor por defecto y eso
    # significaba que una instalacion mal configurada quedaba abierta.
    pin_admin = pin_guardado("admin")
    pin_entrenador = pin_guardado("entrenador")
    if not pin_admin:
        st.error(
            "Falta configurar ADMIN_PIN. Agregalo a .streamlit/secrets.toml "
            "(o a los secretos del servidor) y reinicia la aplicacion."
        )
        return

    castigo = segundos_de_castigo()
    if castigo:
        st.error(
            f"Demasiados intentos fallidos. Vuelve a intentar en {castigo} segundos."
        )
        theme.aviso_kiosco()
        return

    with st.form("ingreso"):
        pin = st.text_input("PIN de acceso", type="password",
                            placeholder="PIN de acceso",
                            label_visibility="collapsed")
        entrar = st.form_submit_button("Entrar", type="primary", width="stretch")

    if entrar:
        # compare_digest tarda lo mismo acierte o falle, asi el tiempo de
        # respuesta no delata cuantos caracteres eran correctos. Se comparan
        # los dos PIN siempre, para que tampoco se note cual acerto.
        acierta_admin = comparar_pin(pin, pin_admin)
        acierta_entrenador = comparar_pin(pin, pin_entrenador)

        if acierta_admin or acierta_entrenador:
            st.session_state["rol"] = "admin" if acierta_admin else "entrenador"
            st.session_state["pagina"] = "Panel"
            st.session_state["ultimo_uso"] = time.time()
            st.session_state.pop("acceso", None)
            st.rerun()
        else:
            registrar_fallo()
            restantes = INTENTOS_MAX - fallos_totales()
            if restantes > 0:
                st.error(f"PIN incorrecto. Te quedan {restantes} intentos.")
            else:
                st.error("PIN incorrecto. Ingreso bloqueado temporalmente.")

    theme.aviso_kiosco()


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

    # El plan corre por calendario: marcar NO descuenta nada, solo deja
    # constancia de quien vino. Estas dos cifras salen de la vista.
    usadas = int(pq["sesiones_usadas"]) if pq else None
    totales = int(pq["sesiones_totales"]) if pq else None
    vence = None
    if pq and logic.a_fecha(pq.get("fecha_fin")):
        vence = logic.a_fecha(pq["fecha_fin"]).strftime("%d/%m/%Y")

    if autorizado:
        try:
            db.marcar_asistencia(alumno_id, pq["id"], sede=fila.get("sede"), origen="KIOSCO")
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
        "OTRO_DIA": "Pasa, pero ojo",
        "YA_MARCO": "Ya marcaste hoy",
        "VENCIDO": "Plan terminado",
        "AGOTADO": "Plan terminado",
        "CONGELADO": "Plan en pausa",
        "POR_EMPEZAR": "Todavia no arranca",
        "CANCELADO": "Plan anulado",
        "SIN_PAQUETE": "Sin plan",
    }.get(motivo, "Revisar en recepcion")

    st.session_state["kiosco"] = {
        "html": theme.tarjeta_resultado(nombre, codigo, veredicto, mensaje,
                                     autorizado, usadas, totales, vence),
        "hora": logic.ahora_hhmm(),
    }
    st.session_state["candidatos"] = []


def pagina_checkin() -> None:
    hoy = logic.hoy()
    theme.cabecera("Marcar asistencia", fecha_larga(hoy).upper(), "Recepcion")
    st.caption(
        "Esta pantalla es el respaldo de recepcion: sirve para marcar a mano cuando "
        "el alumno no pudo usar la tablet de la cancha."
    )

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
                    "html": theme.tarjeta_resultado(
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
            "El plan corre por calendario: las sesiones se cuentan desde el dia "
            "que arranca, vaya o no vaya el alumno. Marcar aca no descuenta "
            "nada, solo deja registro de quien vino."
        )

    with der:
        res = st.session_state.get("kiosco")
        if res:
            st.markdown(res["html"], unsafe_allow_html=True)
            st.caption(f"Registrado a las {res['hora']}")
        else:
            st.markdown(
                '<div class="resultado"><div class="cod">Esperando</div>'
                '<h2>Listo para marcar</h2>'
                '<div class="det">Escribe el DNI del alumno a la izquierda y presiona '
                '<b>Marcar asistencia</b>.</div></div>',
                unsafe_allow_html=True)

    hoy_df = db.asistencias(hoy, hoy)
    st.divider()
    st.subheader(f"Ya entrenaron hoy · {len(hoy_df)}")
    if hoy_df.empty:
        theme.vacio("Nadie ha marcado hoy",
                    "Las asistencias del dia van a ir apareciendo aca.")
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
    theme.cabecera("Panel de control", fecha_larga(hoy).upper(), "Como va el dia")

    alumnos = db.panel_alumnos()

    # Antes esta pantalla pedia las asistencias tres veces: las de hoy, las
    # del mes y las de diez semanas. El rango largo ya contiene a los otros
    # dos, asi que se trae una sola vez y los cortes se hacen en memoria.
    mes_ini = hoy.replace(day=1)
    desde = min(hoy - timedelta(weeks=10), mes_ini)
    historico = db.asistencias(desde, hoy)
    if historico.empty:
        asist_hoy = asist_mes = historico
        fechas = pd.Series(dtype="object")
    else:
        fechas = historico["fecha"].map(logic.a_fecha)
        asist_hoy = historico[fechas == hoy]
        asist_mes = historico[fechas >= mes_ini]

    if alumnos.empty:
        theme.vacio("Todavia no hay alumnos",
                    "Empieza registrando el primero en la pantalla Alumnos.")
        return

    alumnos = con_alertas(alumnos)

    por_renovar = int(alumnos["nivel"].isin(["VENCIDO", "URGENTE"]).sum())
    vigentes = int((alumnos["estado_real"] == "ACTIVO").sum())
    congelados = int((alumnos["estado_real"] == "CONGELADO").sum())

    theme.kpis([
        ("Alumnos activos", len(alumnos), "en el padron"),
        ("Paquetes vigentes", vigentes, "pueden entrenar hoy", "verde"),
        ("Asistencias hoy", len(asist_hoy), fecha_larga(hoy), "naranja"),
        ("Congelados", congelados, "por lesion o viaje"),
        ("Por renovar", por_renovar, "necesitan una llamada",
         "rojo" if por_renovar else "verde"),
    ])

    theme.seccion("Ritmo de la academia", "asistencias de las ultimas 9 semanas")
    conteos = {}
    if not historico.empty:
        for fecha, cantidad in historico.groupby("fecha").size().items():
            conteos[logic.a_fecha(fecha)] = int(cantidad)
    st.markdown(theme.mapa_calor(conteos, hoy), unsafe_allow_html=True)

    if not asist_hoy.empty:
        theme.seccion("Entrenaron hoy",
                      f"{len(asist_hoy)} de {vigentes} alumnos con paquete vigente")
        st.markdown(
            "".join(theme.pastilla(r["alumno"], str(r["hora"])[:5])
                    for _, r in asist_hoy.iterrows()),
            unsafe_allow_html=True)

    izq, der = st.columns([1.2, 1], gap="large")

    with izq:
        theme.seccion("Atencion inmediata", "ordenado por urgencia")
        criticos = alumnos[alumnos["nivel"].isin(["VENCIDO", "URGENTE"])]
        if criticos.empty:
            theme.vacio("Todo al dia",
                        "Nadie tiene el paquete vencido ni a punto de vencer.")
        else:
            for _, f in criticos.head(12).iterrows():
                color = theme.ROJO if f["nivel"] == "VENCIDO" else theme.AMBAR
                st.markdown(
                    f'<div class="fila" style="border-left-color:{color}">'
                    f'{theme.avatar(f["alumno"])}'
                    f'<div><div class="nom">{esc(f["alumno"])}</div>'
                    f'<div class="mot">{esc(f["codigo"])} &middot; '
                    f'{esc(f["motivo"])}</div></div>'
                    f'<div class="der">{theme.chip(f["estado_real"])}</div></div>',
                    unsafe_allow_html=True)
            if len(criticos) > 12:
                st.caption(f"y {len(criticos) - 12} mas en la pantalla Renovaciones.")

    with der:
        theme.seccion("Asistencias del mes", fecha_larga(hoy).split(" de ")[-1])
        if asist_mes.empty:
            st.caption("Sin asistencias este mes.")
        else:
            serie = (asist_mes.groupby("fecha").size()
                     .rename("Asistencias").reset_index().set_index("fecha"))
            st.bar_chart(serie, color=theme.NARANJA, height=240)
            prom = round(len(asist_mes) / max(1, len(serie)), 1)
            st.caption(f"{len(asist_mes)} asistencias en {len(serie)} dias de entrenamiento "
                       f"(promedio {prom} por dia).")

    # Quien tenia que volver de su congelamiento y todavia no lo reactivaron
    vuelven = db.congelados_que_vuelven(hoy + timedelta(days=3))
    if not vuelven.empty:
        theme.seccion("Vuelven de congelamiento", "para reactivar su paquete")
        for _, v in vuelven.iterrows():
            prevista = logic.a_fecha(v.get("fecha_alta_prevista"))
            faltan = (prevista - hoy).days if prevista else None
            if faltan is None:
                detalle, color = v.get("motivo", ""), theme.AZUL
            elif faltan < 0:
                detalle = f"Debia volver hace {abs(faltan)} dias"
                color = theme.ROJO
            elif faltan == 0:
                detalle, color = "Vuelve hoy", theme.AMBAR
            else:
                detalle, color = f"Vuelve en {faltan} dias", theme.AZUL
            theme.fila(v["alumno"], f'{v.get("codigo", "")} · {detalle}', color,
                       theme.chip("CONGELADO"))
        st.caption("Reactivalos en la pantalla Congelamientos para que su paquete "
                   "vuelva a correr.")

    # Pedidos que se registraron como "Pendiente" y despues no aparecian en
    # ninguna pantalla: se vendia el paquete, el alumno entrenaba y la plata
    # quedaba sin cobrar y sin rastro.
    if es_admin():
        deuda = db.paquetes_por_cobrar()
        if not deuda.empty:
            # El saldo, no el precio: si entrego la mitad, lo que falta
            # cobrar es la otra mitad.
            if "saldo" in deuda.columns:
                deuda["_saldo"] = deuda["saldo"].fillna(deuda["precio"])
            else:
                deuda["_saldo"] = deuda["precio"]
            total = float(deuda["_saldo"].fillna(0).sum())
            theme.seccion("Pendientes de cobro",
                          f"{len(deuda)} pedidos por S/ {total:,.2f}")
            for _, d in deuda.head(10).iterrows():
                limite = logic.a_fecha(d.get("fecha_limite_pago"))
                pedido = logic.a_fecha(d.get("fecha_pedido") or d.get("fecha_inicio"))

                if limite:
                    faltan = (limite - hoy).days
                    if faltan < 0:
                        plazo = f"vencio hace {abs(faltan)} dias"
                        color = theme.ROJO
                    elif faltan == 0:
                        plazo, color = "vence hoy", theme.ROJO
                    else:
                        plazo, color = f"vence en {faltan} dias", theme.AMBAR
                else:
                    dias = (hoy - pedido).days if pedido else None
                    plazo = (f"hace {dias} dias" if dias and dias > 0 else "de hoy")
                    color = theme.ROJO if dias and dias > 7 else theme.AMBAR

                entregado = float(d.get("monto_entregado") or 0)
                saldo_d = float(d.get("_saldo") or 0)
                detalle_pago = f"debe S/ {saldo_d:,.2f}"
                if entregado > 0:
                    detalle_pago += f" (ya entrego S/ {entregado:,.2f})"

                c1, c2 = st.columns([4, 1])
                with c1:
                    theme.fila(
                        d["alumno"],
                        f'{d.get("codigo", "")} · {d.get("plan_nombre", "")} · '
                        f'{detalle_pago} · {plazo}',
                        color)
                if c2.button("Cobrar", key=f"pago_{d['id']}", width="stretch"):
                    st.session_state["cobrando"] = d["id"]
                    st.rerun()

                if st.session_state.get("cobrando") == d["id"]:
                    with st.form(f"form_cobro_{d['id']}"):
                        h1, h2 = st.columns([2, 1])
                        abono = h1.number_input(
                            "Monto que entrega ahora (S/)", value=float(saldo_d),
                            min_value=0.0, max_value=float(saldo_d), step=10.0)
                        h2.write("")
                        if h2.form_submit_button("Registrar", type="primary",
                                                 width="stretch"):
                            db.registrar_abono(d["id"], abono)
                            st.session_state.pop("cobrando", None)
                            restante = saldo_d - abono
                            st.toast(
                                "Pago completo" if restante <= 0
                                else f"Abono registrado, quedan S/ {restante:,.2f}",
                                icon="✅")
                            st.rerun()

            if len(deuda) > 10:
                st.caption(f"y {len(deuda) - 10} pedidos mas. Estan todos en "
                           "Paquetes filtrando por la columna Pagado.")

    theme.seccion("Intentos rechazados",
                  "ultimos 7 dias: puerta y accesos al panel")
    bl = db.bloqueos(hoy - timedelta(days=7), hoy)
    if bl.empty:
        theme.vacio("Sin intentos rechazados",
                    "Nadie quiso entrenar sin paquete al dia ni fallo el PIN del panel.")
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
    theme.cabecera("Alumnos", fecha_larga(logic.hoy()).upper(), "Padron")

    if es_admin():
        tab_lista, tab_nuevo, tab_editar = st.tabs(
            ["Lista", "Inscribir alumno", "Editar alumno"])
    else:
        (tab_lista,) = st.tabs(["Lista"])
        tab_nuevo = tab_editar = None

    with tab_lista:
        col_a, col_b = st.columns([2, 1])
        texto = col_a.text_input("Buscar", placeholder="Nombre, DNI, codigo o telefono")
        filtro = col_b.selectbox("Estado", ["Todos", "ACTIVO", "VENCIDO", "AGOTADO",
                                            "CONGELADO", "SIN PAQUETE"])

        datos = db.buscar_alumnos(texto) if texto else db.panel_alumnos()
        if datos.empty:
            # Aca NO puede ir un return: si sale de la funcion, las pestanas
            # Inscribir y Editar quedan vacias y no se puede registrar al
            # primer alumno. Es el problema del huevo y la gallina.
            theme.vacio("Todavia no hay alumnos",
                        "Usa la pestana Inscribir alumno para registrar al primero.")
        else:
            if filtro != "Todos":
                datos = datos[datos["estado_real"] == filtro]

            vista = datos[["codigo", "alumno", "telefono", "plan_nombre",
                           "sesiones_usadas", "sesiones_totales",
                           "sesiones_restantes", "fecha_inicio", "fecha_fin",
                           "estado_real", "fecha_inscripcion"]].copy()
            vista["avance"] = (vista["sesiones_usadas"].fillna(0)
                               / vista["sesiones_totales"].replace(0, 1) * 100).fillna(0)
            vista = vista.drop(columns=["sesiones_usadas", "sesiones_totales"])
            vista.columns = ["Codigo", "Alumno", "Telefono", "Plan", "Restantes",
                             "Inicio del plan", "Vence", "Estado", "Inscrito", "Avance"]
            vista = vista[["Codigo", "Alumno", "Telefono", "Plan", "Avance",
                           "Restantes", "Inicio del plan", "Vence", "Estado",
                           "Inscrito"]]
            for col in ("Inicio del plan", "Vence", "Inscrito"):
                vista[col] = pd.to_datetime(vista[col], errors="coerce")

            # Un paquete congelado no tiene fecha de vencimiento valida: la
            # que quedo guardada es la de antes de la pausa y se va a
            # recalcular al reactivarlo. Mostrarla induce a error.
            vista.loc[vista["Estado"] == "CONGELADO", "Vence"] = pd.NaT

            st.dataframe(
                vista, width="stretch", hide_index=True, height=420,
                column_config={
                    "Avance": st.column_config.ProgressColumn(
                        "Avance", min_value=0, max_value=100, format="%d%%",
                        help="Sesiones usadas del paquete"),
                    "Restantes": st.column_config.NumberColumn("Restantes", format="%d"),
                    "Inicio del plan": st.column_config.DateColumn(
                        "Inicio del plan", format="DD/MM/YYYY",
                        help="Cuando arranca el plan, no cuando se inscribio"),
                    "Vence": st.column_config.DateColumn(
                        "Vence", format="DD/MM/YYYY",
                        help="Fecha de su ultima sesion"),
                    "Inscrito": st.column_config.DateColumn(
                        "Inscrito", format="DD/MM/YYYY",
                        help="Cuando se registro en la academia"),
                })
            if (vista["Estado"] == "CONGELADO").any():
                st.caption(
                    "Los alumnos congelados no muestran vencimiento a proposito: "
                    "esa fecha se recalcula el dia que se les da de alta, contando "
                    "las sesiones que les quedan."
                )
            descargar_csv("Descargar CSV", vista, "futcross_alumnos.csv",
                          clave="csv_alumnos")

            st.divider()
            st.subheader("Ficha del alumno")
            opciones = {f"{r['codigo']} · {r['alumno']}": r["alumno_id"]
                        for _, r in datos.iterrows()}
            elegido = st.selectbox("Selecciona", list(opciones.keys()))
            if elegido:
                ficha_alumno(opciones[elegido])

    if tab_nuevo is None:
        return

    with tab_editar:
        editar_alumno()

    with tab_nuevo:
        with st.form("form_alumno", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombres = c1.text_input("Nombres *")
            apellidos = c2.text_input("Apellidos *")
            dni = c1.text_input("DNI", help="Es lo que el alumno escribe en la tablet")
            telefono = c2.text_input("Telefono (9 digitos)",
                                     help="Se usa para el WhatsApp de renovacion")
            email = c1.text_input("Correo")
            nacimiento = c2.date_input("Fecha de nacimiento", value=None,
                                       min_value=logic.hoy() - timedelta(days=365 * 80),
                                       max_value=logic.hoy(), format="DD/MM/YYYY")
            inscripcion = c1.text_input("Fecha de inscripcion", value="", disabled=True,
                                        placeholder="se toma la de hoy")
            inscripcion = logic.hoy()

            emergencia = c2.text_input("Contacto de emergencia")
            notas = st.text_area("Notas", placeholder="Lesiones previas, observaciones, etc.")

            # Un alumno nuevo casi siempre entra comprando. Se hace en el mismo
            # paso para no obligar a ir despues a la pantalla de Paquetes.
            # El plan va antes del grupo porque de el sale cuantos dias por
            # semana entrena, y eso define que dias se pueden marcar.
            st.markdown("**Plan que contrata**")
            planes_disp = db.listar_planes()
            vender_ahora = st.checkbox("Registrar su primer pedido ahora",
                                       value=not planes_disp.empty,
                                       disabled=planes_disp.empty)
            if planes_disp.empty:
                st.caption("No hay planes activos. Crealos en la pantalla Planes.")

            plan_elegido = None
            inicio_plan = precio_plan = medio_plan = vendedor_plan = None
            frecuencia_plan = None
            if not planes_disp.empty:
                q1, q2 = st.columns([2, 1])
                nombre_plan = q1.selectbox("Plan", planes_disp["nombre"].tolist())
                plan_elegido = planes_disp[
                    planes_disp["nombre"] == nombre_plan].iloc[0].to_dict()
                inicio_plan = q2.date_input("Inicio del plan", value=logic.hoy(),
                                            format="DD/MM/YYYY")
                frecuencia_plan = plan_elegido.get("dias_por_semana")
                if frecuencia_plan is not None and pd.isna(frecuencia_plan):
                    frecuencia_plan = None

            st.markdown("**Grupo y dias que entrena**")
            grupo_id, dias_grupo, detalle = selector_de_grupo(
                "Sede, horario y genero", clave="grupo_nuevo_alumno",
                dias_del_plan=int(frecuencia_plan) if frecuencia_plan else None)
            if detalle:
                st.caption(detalle)
            sede = dias = horario = turno = None

            if plan_elegido is not None:
                fin_plan = logic.fecha_fin_por_calendario(
                    inicio_plan, int(plan_elegido["sesiones"]), dias_grupo,
                    int(plan_elegido["vigencia_dias"]))
                if dias_grupo:
                    st.info(
                        f"**{plan_elegido['sesiones']} sesiones** entrenando "
                        f"{logic.frecuencia(dias_grupo)} ({dias_grupo}). "
                        f"Ultima sesion el **{fecha_larga(fin_plan)}**."
                    )

            if plan_elegido is not None:

                r1, r2, r3 = st.columns(3)
                lista_plan = r1.number_input(
                    "Precio de lista (S/)", min_value=0.0,
                    value=float(plan_elegido["precio"]), step=10.0,
                    key="lista_inscripcion")
                precio_plan = r2.number_input(
                    "Precio cobrado (S/)", min_value=0.0,
                    value=float(plan_elegido["precio"]), step=1.0,
                    key="cobrado_inscripcion",
                    help="Lo que paga el cliente, con descuento si hubo")
                medio_plan = r3.selectbox("Metodo de pago", MEDIOS_PAGO,
                                          key="medio_inscripcion")
                if lista_plan - precio_plan > 0:
                    d = lista_plan - precio_plan
                    st.caption(f"Descuento: **S/ {d:,.2f}** "
                               f"({d / lista_plan * 100:.1f}%)")
                recibido_plan = st.text_input("Recibido por", placeholder="Ej. GARY",
                                              key="recibido_inscripcion")
                vendedor_plan = st.text_input("Vendedor", key="vendedor_inscripcion",
                                              placeholder="Ej. EDDIMAR")

            if st.form_submit_button("Guardar alumno", type="primary"):
                if vender_ahora and plan_elegido is not None and not dias_grupo:
                    st.error("Marca al menos un dia de entrenamiento.")
                elif not nombres or not apellidos:
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
                            "grupo_id": grupo_id,
                            "dias_asiste": dias_grupo,
                            "contacto_emergencia": emergencia, "notas": notas,
                        })
                        alumno_nuevo = creado[0]
                        aviso = f"Alumno registrado con codigo {alumno_nuevo['codigo']}."

                        if vender_ahora and plan_elegido:
                            medio_full = (f"{medio_plan} {recibido_plan}".strip()
                                          if recibido_plan else medio_plan)
                            db.crear_paquete(
                                alumno_nuevo["id"], plan_elegido, inicio_plan,
                                precio_plan, medio_full, True, None,
                                fecha_pedido=logic.hoy(), sede=None,
                                dias_asiste=dias_grupo,
                                vendedor=(vendedor_plan or "").strip().upper() or None,
                                tipo="NUEVO", grupo_id=grupo_id,
                                precio_lista=lista_plan)
                            fin_final = logic.fecha_fin_por_calendario(
                                inicio_plan, int(plan_elegido["sesiones"]), dias_grupo,
                                int(plan_elegido["vigencia_dias"]))
                            aviso += (f" Se registro su {plan_elegido['nombre']}: "
                                      f"ultima sesion el {fecha_larga(fin_final)}.")
                        else:
                            aviso += " Asignale un paquete en la pantalla Paquetes."

                        st.toast("Alumno registrado", icon="\u2705")
                        st.success(aviso)
                    except Exception as e:
                        st.error(f"No se pudo guardar: {e}")


def editar_alumno() -> None:
    """Modifica los datos de un alumno ya inscrito.

    Todo llega precargado con lo que ya tiene, asi que solo se toca lo que
    cambia. Tambien permite darlo de baja sin borrar su historial.
    """
    todos = db.panel_alumnos(solo_activos=False)
    if todos.empty:
        theme.vacio("No hay alumnos", "Primero inscribe a alguien.")
        return

    etiquetas = {f"{r['codigo']} - {r['alumno']}": r["alumno_id"]
                 for _, r in todos.iterrows()}
    elegido = st.selectbox("Alumno a editar", list(etiquetas.keys()),
                           key="alumno_editar")
    alumno_id = etiquetas[elegido]

    a = db.alumno(alumno_id)
    if not a:
        st.error("No se encontro el alumno.")
        return

    def texto(clave, defecto=""):
        valor = a.get(clave)
        return defecto if valor is None or (isinstance(valor, float) and pd.isna(valor)) \
            else str(valor)

    try:
        opciones_sede = db.sedes()
    except Exception:
        opciones_sede = ["SURQUILLO"]
    sede_actual = texto("sede") or (opciones_sede[0] if opciones_sede else "SURQUILLO")
    if sede_actual not in opciones_sede:
        opciones_sede = [sede_actual] + opciones_sede

    turno_actual = texto("turno") or TURNOS[0]
    dias_actuales = [d for d in texto("dias_asiste").split() if d in DIAS_SEMANA]

    with st.form("form_editar_alumno"):
        c1, c2 = st.columns(2)
        nombres = c1.text_input("Nombres *", value=texto("nombres"))
        apellidos = c2.text_input("Apellidos *", value=texto("apellidos"))
        dni = c1.text_input("DNI", value=texto("dni"))
        telefono = c2.text_input("Telefono", value=texto("telefono"))
        email = c1.text_input("Correo", value=texto("email"))

        nac = logic.a_fecha(a.get("fecha_nacimiento"))
        nacimiento = c2.date_input("Fecha de nacimiento", value=nac,
                                   min_value=logic.hoy() - timedelta(days=365 * 80),
                                   max_value=logic.hoy(), format="DD/MM/YYYY")

        st.markdown("**Grupo y dias que entrena**")
        grupo_id, dias_grupo, detalle = selector_de_grupo(
            "Sede, horario y genero", clave="grupo_editar",
            grupo_actual=a.get("grupo_id"),
            dias_previos=texto("dias_asiste"))
        if detalle:
            st.caption(detalle)
        sede = turno = horario = None

        e1, e2 = st.columns(2)
        emergencia = e1.text_input("Contacto de emergencia",
                                   value=texto("contacto_emergencia"))
        activo = e2.selectbox(
            "Estado del alumno", ["Activo", "Dado de baja"],
            index=0 if a.get("activo", True) else 1,
            help="Dar de baja lo saca de los listados pero conserva su historial",
        ) == "Activo"
        notas = st.text_area("Notas", value=texto("notas"))

        st.caption(f"Codigo {a['codigo']} - inscrito el "
                   f"{logic.a_fecha(a['fecha_inscripcion']).strftime('%d/%m/%Y')}. "
                   "El codigo y la fecha de inscripcion no se modifican.")

        if st.form_submit_button("Guardar cambios", type="primary"):
            if not nombres.strip() or not apellidos.strip():
                st.error("Nombres y apellidos son obligatorios.")
            else:
                try:
                    db.actualizar_alumno(alumno_id, {
                        "nombres": nombres.strip().title(),
                        "apellidos": apellidos.strip().title(),
                        "dni": logic.solo_digitos(dni) or None,
                        "telefono": logic.solo_digitos(telefono) or None,
                        "email": email.strip() or None,
                        "fecha_nacimiento": nacimiento,
                        "grupo_id": grupo_id,
                        "dias_asiste": dias_grupo,
                        "contacto_emergencia": emergencia or None,
                        "notas": notas or None,
                        "activo": activo,
                    })
                    st.toast("Alumno actualizado", icon="\u2705")
                    st.success(f"Datos de {nombres} {apellidos} actualizados.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo guardar: {e}")


def ficha_alumno(alumno_id: str) -> None:
    a = db.alumno(alumno_id)
    if not a:
        return
    paquetes = db.paquetes_de(alumno_id)

    nombre = f"{a['nombres']} {a['apellidos']}"
    inscrito = logic.a_fecha(a["fecha_inscripcion"])
    antiguedad = (logic.hoy() - inscrito).days
    st.markdown(
        theme.ficha_alumno(
            nombre, a["codigo"],
            f"DNI {a.get('dni') or '—'} &middot; Tel. {a.get('telefono') or '—'} "
            f"&middot; {a.get('horario') or 'sin horario fijo'}",
            f'<div style="font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;'
            f'color:{theme.HUMO}">Alumno desde</div>'
            f'<div style="font-family:Barlow Condensed;font-size:1.3rem;font-weight:700">'
            f'{inscrito.strftime("%d/%m/%Y")}</div>'
            f'<div style="font-size:.72rem;color:{theme.HUMO}">hace {antiguedad} dias</div>'),
        unsafe_allow_html=True)
    st.write("")

    c1, c2, c3 = st.columns([1.3, 1, 1])
    vigente = None if paquetes.empty else paquetes[
        paquetes["estado_real"].isin(["ACTIVO", "CONGELADO"])]
    if vigente is not None and not vigente.empty:
        p = vigente.iloc[0]
        # Si tiene varios paquetes encolados, lo que importa es el total
        por_consumir = paquetes[paquetes["estado_real"].isin(["ACTIVO", "CONGELADO"])]
        total_pend = int(por_consumir["sesiones_restantes"].sum())
        if len(por_consumir) > 1:
            c2.metric("Sesiones restantes", total_pend,
                      f"en {len(por_consumir)} paquetes")
        else:
            c2.metric("Sesiones restantes",
                      f"{p['sesiones_restantes']} de {p['sesiones_totales']}")
        c3.metric("Vence", logic.a_fecha(p["fecha_fin"]).strftime("%d/%m/%Y"),
                  f"{p['dias_restantes']} dias")
        with c1:
            st.markdown(theme.barra(int(p["sesiones_usadas"]), int(p["sesiones_totales"])),
                        unsafe_allow_html=True)
            st.caption(f"{p['sesiones_usadas']} de {p['sesiones_totales']} sesiones usadas "
                       f"del {p['plan_nombre']}")
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

    if vigente is not None and not vigente.empty:
        pv = vigente.iloc[0]
        dias_pv = pv.get("dias_asiste")
        if dias_pv and not pd.isna(dias_pv):
            usadas_pv = int(pv["sesiones_usadas"])
            totales_pv = int(pv["sesiones_totales"])
            todas = logic.proximas_sesiones(logic.a_fecha(pv["fecha_inicio"]),
                                            totales_pv, dias_pv)
            if todas:
                with st.expander(
                        f"Cronograma de sus {totales_pv} sesiones "
                        f"({logic.frecuencia(dias_pv)})"):
                    filas = []
                    for n, f in enumerate(todas, 1):
                        estado = "usada" if n <= usadas_pv else "pendiente"
                        filas.append({"N": n,
                                      "Fecha": fecha_larga(f).title(),
                                      "Estado": estado})
                    st.dataframe(pd.DataFrame(filas), width="stretch",
                                 hide_index=True, height=260)
                    st.caption(f"Primera sesion el {fecha_larga(todas[0])}, "
                               f"ultima el {fecha_larga(todas[-1])}.")

    if not paquetes.empty:
        st.markdown("**Historial de paquetes**")
        hist = paquetes[["plan_nombre", "fecha_inicio", "fecha_fin", "sesiones_usadas",
                         "sesiones_totales", "dias_congelados", "precio", "estado_real"]].copy()
        hist.columns = ["Plan", "Inicio", "Fin", "Usadas", "Totales",
                        "Dias congelados", "Precio", "Estado"]
        st.dataframe(hist, width="stretch", hide_index=True)

    # Solo las de este alumno: antes se bajaban seis meses de asistencias de
    # toda la academia para despues filtrar una sola persona en pandas.
    mias = db.asistencias_de(alumno_id, logic.hoy() - timedelta(days=180), logic.hoy())
    if not mias.empty:
        theme.seccion("Su ritmo", "ultimas 9 semanas")
        propios = {logic.a_fecha(f): int(n)
                   for f, n in mias.groupby("fecha").size().items()}
        st.markdown(theme.mapa_calor(propios, logic.hoy()), unsafe_allow_html=True)
        st.write("")
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
def editar_pedido(planes) -> None:
    """Corrige un pedido ya registrado.

    El caso que lo motivo: el alumno confirma que arranca el lunes y el
    domingo avisa que mejor el miercoles. Antes habia que anular el
    pedido y cargarlo de nuevo, perdiendo el numero y la fecha de venta.
    """
    pedidos = db.listar_paquetes()
    if pedidos.empty:
        theme.vacio("Sin pedidos", "Registra el primero en la otra pestana.")
        return

    def etiqueta(r):
        inicio = logic.a_fecha(r["fecha_inicio"])
        return (f"N {r.get('nro_pedido') or '-'} · {r['alumno']} · "
                f"{r['plan_nombre']} · desde {inicio.strftime('%d/%m/%Y')}")

    opciones = {etiqueta(r): r["id"] for _, r in pedidos.iterrows()}
    elegido = st.selectbox("Pedido a corregir", list(opciones.keys()),
                           key="pedido_editar")
    pq = db.paquete(opciones[elegido])
    if not pq:
        st.error("No se encontro el pedido.")
        return

    usadas = int(pq.get("sesiones_usadas") or 0)
    asistencias = int(pq.get("asistencias_registradas") or 0)
    empezado = usadas > 0 or asistencias > 0

    if empezado:
        st.warning(
            f"Este plan ya empezo: lleva {usadas} sesiones corridas y "
            f"{asistencias} asistencias registradas. Si mueves la fecha de "
            "inicio, esas cuentas cambian. Corrigelo solo si de verdad "
            "arranco otro dia."
        )
    else:
        st.info("Este plan todavia no arranca, se puede mover sin problema.")

    with st.form("form_editar_pedido"):
        c1, c2, c3 = st.columns([2, 1, 1])
        nombres_planes = planes["nombre"].tolist()
        actual = pq.get("plan_nombre")
        indice = nombres_planes.index(actual) if actual in nombres_planes else 0
        nombre_plan = c1.selectbox("Plan contratado", nombres_planes, index=indice)
        plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()

        fecha_pedido = c2.date_input(
            "Fecha del pedido", value=logic.a_fecha(pq.get("fecha_pedido")),
            format="DD/MM/YYYY", help="Cuando se cerro la venta. No suele cambiar.")
        inicio = c3.date_input(
            "Inicio del plan", value=logic.a_fecha(pq["fecha_inicio"]),
            format="DD/MM/YYYY",
            help="Al cambiarla se recalculan todas las fechas del alumno")

        st.markdown("**Grupo y dias que entrena**")
        grupo_id, dias_grupo, detalle = selector_de_grupo(
            "Sede, horario y genero", clave="grupo_edicion",
            grupo_actual=pq.get("grupo_id"),
            dias_previos=str(pq.get("dias_asiste") or ""))
        if detalle:
            st.caption(detalle)

        a1, a2 = st.columns(2)
        sesiones = a1.number_input("Sesiones", min_value=1,
                                   value=int(pq["sesiones_totales"]))
        tipo = a2.selectbox("Renovacion o nuevo", ["NUEVO", "RENOVACION"],
                            index=1 if pq.get("tipo") == "RENOVACION" else 0)

        fin = logic.fecha_fin_por_calendario(
            inicio, int(sesiones), dias_grupo, int(plan["vigencia_dias"]))

        st.markdown("**Cobro**")
        e1, e2, e3 = st.columns(3)
        precio_lista = e1.number_input(
            "Precio de lista (S/)", min_value=0.0, step=10.0,
            value=float(pq.get("precio_lista") or pq.get("precio") or 0))
        precio = e2.number_input("Precio cobrado (S/)", min_value=0.0, step=1.0,
                                 value=float(pq.get("precio") or 0))
        entregado = e3.number_input(
            "Monto entregado (S/)", min_value=0.0, step=10.0,
            value=float(pq.get("monto_entregado") or 0))

        saldo = max(0.0, precio - entregado)
        f1, f2 = st.columns(2)
        if saldo > 0:
            limite = f1.date_input(
                "Pagar el saldo hasta",
                value=logic.a_fecha(pq.get("fecha_limite_pago"))
                or logic.hoy() + timedelta(days=15), format="DD/MM/YYYY")
            f1.caption(f"Queda debiendo **S/ {saldo:,.2f}**")
        else:
            limite = None
            f1.caption("Sin saldo pendiente.")
        medio = f2.selectbox(
            "Metodo de pago", MEDIOS_PAGO,
            index=next((i for i, m in enumerate(MEDIOS_PAGO)
                        if str(pq.get("medio_pago") or "").upper().startswith(m)), 0))

        vendedor = st.text_input("Vendedor", value=str(pq.get("vendedor") or ""))
        obs = st.text_input("Observacion", value=str(pq.get("observacion") or ""))

        cronograma = logic.proximas_sesiones(inicio, int(sesiones), dias_grupo)
        if cronograma:
            st.info(
                f"**{sesiones} sesiones** entrenando "
                f"{logic.frecuencia(dias_grupo)} ({dias_grupo}). "
                f"Primera el {fecha_larga(cronograma[0])}, ultima el "
                f"**{fecha_larga(fin)}**."
            )
            anterior_fin = logic.a_fecha(pq["fecha_fin"])
            if anterior_fin and anterior_fin != fin:
                st.warning(f"La ultima sesion se mueve del "
                           f"{anterior_fin.strftime('%d/%m/%Y')} al "
                           f"{fin.strftime('%d/%m/%Y')}.")
            if len(cronograma) <= 12:
                st.caption("Fechas: " + " · ".join(
                    f.strftime("%d/%m") for f in cronograma))

        confirmar = st.checkbox(
            "Confirmo el cambio", value=not empezado,
            help="Si el plan ya empezo, revisa bien antes de guardar")

        if st.form_submit_button("Guardar cambios", type="primary"):
            if not dias_grupo:
                st.error("Marca al menos un dia de entrenamiento.")
            elif not confirmar:
                st.error("Marca la casilla de confirmacion.")
            elif entregado > precio:
                st.error("El monto entregado no puede ser mayor al cobrado.")
            else:
                try:
                    db.editar_pedido(
                        pq["id"], plan, inicio, int(sesiones), dias_grupo,
                        grupo_id, precio_lista, precio, entregado, limite,
                        (vendedor or "").strip().upper() or None, tipo, medio,
                        fecha_pedido, obs or None,
                        quien=ETIQUETA_ROL.get(rol(), ""))
                    st.toast("Pedido corregido", icon="\u2705")
                    st.success(
                        f"Pedido actualizado. Su ultima sesion queda el "
                        f"{fecha_larga(fin)}."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo guardar: {e}")

    st.caption(
        "El numero de pedido no cambia. Cada correccion queda registrada y se "
        "puede ver en el Panel, en Intentos rechazados."
    )


def pagina_paquetes() -> None:
    theme.cabecera("Paquetes", fecha_larga(logic.hoy()).upper(), "Ventas y renovaciones")

    planes = db.listar_planes()
    tab_vender, tab_editar, tab_lista = st.tabs(
        ["Vender o renovar", "Editar un pedido", "Todos los paquetes"])

    if planes.empty:
        with tab_vender:
            theme.vacio("No hay planes activos",
                        "Crea al menos un plan en la pantalla Planes.")
        with tab_editar:
            theme.vacio("Nada que editar", "Primero crea un plan.")
        with tab_lista:
            theme.vacio("Sin pedidos", "Todavia no se registro ninguno.")
        return

    with tab_editar:
        editar_pedido(planes)

    with tab_vender:
        alumnos = db.panel_alumnos()
        if alumnos.empty:
            theme.vacio("Todavia no hay alumnos",
                        "Inscribelos en la pantalla Alumnos y vuelve aca a "
                        "venderles su paquete.")
        else:

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
                    f"{vigente['plan_nombre']}, le quedan "
                    f"{vigente['sesiones_restantes']} sesiones y su ultima cae el "
                    f"{logic.a_fecha(vigente['fecha_fin']).strftime('%d/%m/%Y')}. "
                    "El nuevo se puede encolar para que arranque cuando termine ese."
                )

            # Lo que ya sabemos del alumno se hereda, para no volver a escribirlo
            datos_alumno = alumnos[alumnos["alumno_id"] == alumno_id].iloc[0]
            try:
                pedido = db.siguiente_pedido()
                lista_vendedores = db.vendedores()
                lista_sedes = db.sedes()
            except Exception:
                pedido, lista_vendedores, lista_sedes = 1, [], ["SURQUILLO"]

            with st.form("form_paquete"):
                st.markdown(f"**Pedido N {pedido}**")

                c1, c2, c3 = st.columns([2, 1, 1])
                nombre_plan = c1.selectbox("Plan contratado", planes["nombre"].tolist())
                plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()
                fecha_pedido = c2.date_input("Fecha del pedido", value=logic.hoy(),
                                             format="DD/MM/YYYY",
                                             help="Cuando se cerro la venta")

                # Si ya tiene un paquete corriendo, lo natural es que el nuevo
                # arranque al dia siguiente de la ultima sesion del actual.
                # Asi las sesiones se suman en vez de correr en paralelo.
                if vigente is not None:
                    sugerido = logic.a_fecha(vigente["fecha_fin"]) + timedelta(days=1)
                    sugerido = max(sugerido, logic.hoy())
                else:
                    sugerido = logic.hoy()

                inicio = c3.date_input(
                    "Inicio del plan", value=sugerido, format="DD/MM/YYYY",
                    help="Si ya tiene un paquete, se propone el dia siguiente al "
                         "que termina, para que las sesiones se sumen")

                st.markdown("**Grupo y dias que entrena**")
                grupo_previo = datos_alumno.get("grupo_id")
                if grupo_previo is not None and pd.isna(grupo_previo):
                    grupo_previo = None
                dias_previos = datos_alumno.get("dias_asiste")
                if dias_previos is None or (isinstance(dias_previos, float)
                                            and pd.isna(dias_previos)):
                    dias_previos = ""
                frec = plan.get("dias_por_semana")
                if frec is not None and pd.isna(frec):
                    frec = None
                grupo_id, dias_grupo, detalle = selector_de_grupo(
                    "Sede, horario y genero", clave="grupo_venta",
                    grupo_actual=grupo_previo, dias_previos=str(dias_previos),
                    dias_del_plan=int(frec) if frec else None)
                if detalle:
                    st.caption(detalle)

                # Ajuste para una venta puntual, sin tocar el catalogo de planes
                a1, a2 = st.columns(2)
                sesiones = a1.number_input("Sesiones", min_value=1,
                                           value=int(plan["sesiones"]),
                                           help="Cambialo solo si esta venta es una excepcion")
                vigencia = a2.number_input("Dias de vigencia (respaldo)", min_value=1,
                                           value=int(plan["vigencia_dias"]),
                                           help="Solo se usa si el grupo no tiene dias")

                # La fecha de fin es la de la ultima sesion en el calendario del grupo
                fin = logic.fecha_fin_por_calendario(inicio, int(sesiones), dias_grupo,
                                                     int(vigencia))
                sede = None

                st.markdown("**Cobro**")
                e1, e2, e3 = st.columns(3)
                precio_lista = e1.number_input(
                    "Precio de lista (S/)", value=float(plan["precio"]),
                    min_value=0.0, step=10.0,
                    help="El del catalogo. Se completa solo con el del plan.")
                precio = e2.number_input(
                    "Precio cobrado (S/)", value=float(plan["precio"]),
                    min_value=0.0, step=1.0,
                    help="Lo que realmente paga el cliente, con descuento si hubo")
                medio = e3.selectbox("Metodo de pago", MEDIOS_PAGO)

                dcto = precio_lista - precio
                if dcto > 0:
                    pct = dcto / precio_lista * 100 if precio_lista else 0
                    st.caption(f"Descuento aplicado: **S/ {dcto:,.2f}** ({pct:.1f}%)")
                elif dcto < 0:
                    st.caption(f"Cobrado **S/ {abs(dcto):,.2f}** por encima del "
                               "precio de lista.")

                recibido = st.text_input("Recibido por", placeholder="Ej. GARY",
                                         help="Queda registrado como 'YAPE GARY'")

                # FutCross a veces cobra la mitad ahora y la otra mitad en
                # quince dias. Antes eso no habia donde registrarlo: marcar
                # "Pendiente" hacia que lo que si entro a caja no contara.
                g1, g2 = st.columns(2)
                entregado = g1.number_input(
                    "Monto entregado (S/)", value=float(precio),
                    min_value=0.0, max_value=float(precio), step=10.0,
                    help="Cuanto paga ahora. Dejalo igual al precio si paga todo.")
                saldo = max(0.0, precio - entregado)
                pagado = saldo <= 0

                if saldo > 0:
                    limite = g2.date_input(
                        "Pagar el saldo hasta", value=logic.hoy() + timedelta(days=15),
                        min_value=logic.hoy(), format="DD/MM/YYYY",
                        help="Plazo acordado con el cliente")
                    g2.caption(f"Queda debiendo **S/ {saldo:,.2f}**")
                else:
                    limite = None
                    g2.caption("Pago completo, sin saldo pendiente.")

                f1, f2 = st.columns(2)
                es_renovacion = bool(vigente) or bool(db.ultimo_paquete(alumno_id))
                tipo = f1.selectbox("Renovacion o nuevo", ["NUEVO", "RENOVACION"],
                                    index=1 if es_renovacion else 0)
                if lista_vendedores:
                    vendedor = f2.selectbox("Vendedor", lista_vendedores + ["Otro..."])
                else:
                    vendedor = "Otro..."
                if vendedor == "Otro...":
                    vendedor = f2.text_input("Nombre del vendedor", key="vend_nuevo")

                obs = st.text_input("Observacion", placeholder="Opcional")

                if vigente is not None:
                    fin_actual = logic.a_fecha(vigente["fecha_fin"])
                    restantes_actual = int(vigente["sesiones_restantes"])
                    if inicio > fin_actual:
                        st.success(
                            f"Se encola: primero termina sus {restantes_actual} "
                            f"sesiones pendientes (hasta el {fecha_larga(fin_actual)}) "
                            f"y despues corren las {sesiones} nuevas. En total le "
                            f"quedaran **{restantes_actual + int(sesiones)} sesiones**."
                        )
                    else:
                        st.warning(
                            f"Los dos paquetes van a estar vigentes a la vez. El "
                            f"kiosco descuenta primero el que termina antes "
                            f"({fecha_larga(fin_actual)}). Si querias que se sumen "
                            f"uno detras del otro, pon el inicio despues de esa fecha."
                        )

                cronograma = logic.proximas_sesiones(inicio, int(sesiones), dias_grupo)
                if cronograma:
                    st.info(
                        f"**{sesiones} sesiones** entrenando "
                        f"{logic.frecuencia(dias_grupo)} ({dias_grupo}). "
                        f"Primera el {fecha_larga(cronograma[0])}, ultima el "
                        f"**{fecha_larga(fin)}**."
                    )
                    if len(cronograma) <= 12:
                        st.caption("Fechas: " + " · ".join(
                            f.strftime("%d/%m") for f in cronograma))
                else:
                    st.info(f"**{sesiones} sesiones** del "
                            f"{inicio.strftime('%d/%m/%Y')} al "
                            f"**{fin.strftime('%d/%m/%Y')}**.")

                if st.form_submit_button("Registrar pedido", type="primary"):
                    if not dias_grupo:
                        st.error("Marca al menos un dia de entrenamiento antes de "
                                 "registrar el pedido.")
                        st.stop()
                    medio_completo = f"{medio} {recibido}".strip() if recibido else medio
                    try:
                        db.crear_paquete(
                            alumno_id, plan, inicio, precio, medio_completo, pagado,
                            obs or None, fecha_pedido=fecha_pedido, sede=sede,
                            dias_asiste=dias_grupo,
                            vendedor=(vendedor or "").strip().upper() or None,
                            tipo=tipo, sesiones=int(sesiones), vigencia_dias=int(vigencia),
                            grupo_id=grupo_id, precio_lista=precio_lista,
                            monto_entregado=entregado, fecha_limite_pago=limite)
                        st.toast(f"Pedido {pedido} registrado", icon="\u2705")
                        aviso_pedido = (f"Pedido N {pedido} registrado. "
                                        f"Vence el {fin.strftime('%d/%m/%Y')}.")
                        if saldo > 0:
                            aviso_pedido += (f" Queda un saldo de S/ {saldo:,.2f} "
                                             f"con plazo hasta el "
                                             f"{limite.strftime('%d/%m/%Y')}.")
                        st.success(aviso_pedido)
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo registrar: {e}")

    with tab_lista:
        estados = st.multiselect(
            "Estado", ["ACTIVO", "CONGELADO", "VENCIDO", "AGOTADO", "CANCELADO"],
            default=["ACTIVO", "CONGELADO"])
        datos = db.listar_paquetes(estados or None)
        if datos.empty:
            theme.vacio("Sin paquetes que mostrar",
                        "Cambia los filtros o registra el primer pedido.")
            return
        columnas = ["nro_pedido", "fecha_pedido", "alumno", "plan_nombre",
                    "precio_lista", "precio", "descuento", "descuento_pct",
                    "medio_pago", "fecha_inicio", "fecha_fin", "sede", "dias_asiste",
                    "sesiones_usadas", "sesiones_totales", "sesiones_restantes",
                    "dias_restantes", "dias_congelados", "estado_real", "tipo",
                    "vendedor", "monto_entregado", "saldo", "fecha_limite_pago",
                    "estado_pago"]
        # Si la migracion 006 aun no se corrio faltan columnas: avisar sin romper
        faltan = [c for c in columnas if c not in datos.columns]
        for c in faltan:
            datos[c] = None
        if faltan:
            st.warning("Faltan campos nuevos en la base. Corre migracion-006.sql en "
                       "Supabase para tener numero de pedido, sede y vendedor.")

        vista = datos[columnas].copy()
        vista.columns = ["N pedido", "Fecha", "Cliente", "Plan contratado",
                         "Precio lista", "Precio cobrado", "Descuento", "Dcto %",
                         "Metodo de pago", "Inicio del plan", "Fin del plan",
                         "Sede y turno", "Dias que asiste", "Usadas", "Totales",
                         "Restantes", "Dias por vencer", "Dias congelados", "Status",
                         "Renovacion/Nuevo", "Vendedor", "Entregado", "Saldo",
                         "Plazo de pago", "Estado del pago"]
        vista["Avance"] = (vista["Usadas"] / vista["Totales"].replace(0, 1) * 100)
        vista = vista[["N pedido", "Fecha", "Cliente", "Plan contratado",
                       "Precio lista", "Precio cobrado", "Descuento", "Dcto %",
                       "Metodo de pago", "Inicio del plan", "Fin del plan",
                       "Sede y turno", "Dias que asiste", "Avance", "Restantes",
                       "Dias por vencer", "Dias congelados", "Status",
                       "Renovacion/Nuevo", "Vendedor", "Entregado", "Saldo",
                       "Plazo de pago", "Estado del pago"]]
        for col in ("Fecha", "Inicio del plan", "Fin del plan", "Plazo de pago"):
            vista[col] = pd.to_datetime(vista[col], errors="coerce")

        st.dataframe(
            vista, width="stretch", hide_index=True, height=430,
            column_config={
                "N pedido": st.column_config.NumberColumn("N pedido", format="%d"),
                "Avance": st.column_config.ProgressColumn(
                    "Avance", min_value=0, max_value=100, format="%d%%"),
                "Precio lista": st.column_config.NumberColumn(
                    "Precio lista", format="S/ %.2f"),
                "Precio cobrado": st.column_config.NumberColumn(
                    "Precio cobrado", format="S/ %.2f"),
                "Descuento": st.column_config.NumberColumn(
                    "Descuento", format="S/ %.2f",
                    help="Cuanto se dejo de cobrar respecto al precio de lista"),
                "Dcto %": st.column_config.NumberColumn("Dcto %", format="%.1f%%"),
                "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                "Inicio del plan": st.column_config.DateColumn(
                    "Inicio del plan", format="DD/MM/YYYY"),
                "Fin del plan": st.column_config.DateColumn(
                    "Fin del plan", format="DD/MM/YYYY"),
                "Entregado": st.column_config.NumberColumn(
                    "Entregado", format="S/ %.2f"),
                "Saldo": st.column_config.NumberColumn(
                    "Saldo", format="S/ %.2f",
                    help="Lo que todavia falta cobrar"),
                "Plazo de pago": st.column_config.DateColumn(
                    "Plazo de pago", format="DD/MM/YYYY"),
            })
        descargar_csv("Descargar CSV", vista, "futcross_paquetes.csv",
                      clave="csv_paquetes")


# =====================================================================
# 5. CONGELAMIENTOS
# =====================================================================
def pagina_congelamientos() -> None:
    theme.cabecera("Congelamientos", fecha_larga(logic.hoy()).upper(), "Lesiones y pausas")
    st.caption(
        "Congelar detiene el reloj del paquete: mientras esta pausado no se le "
        "descuentan sesiones. Al dar de alta, el sistema recalcula el vencimiento "
        "contando sus sesiones restantes desde ese dia, en el calendario de su grupo."
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
                detalle = st.text_input(
                    "Detalle", placeholder="Ej. esguince de tobillo, 3 semanas de reposo")

                d1, d2 = st.columns([1, 2])
                sabe_cuando = d1.checkbox("Ya se cuando vuelve", value=True)
                alta_prevista = d2.date_input(
                    "Fecha prevista de alta", value=desde + timedelta(days=30),
                    min_value=desde, format="DD/MM/YYYY", disabled=not sabe_cuando,
                    help="Es una estimacion. La fecha real se confirma al reactivar.")

                if st.form_submit_button("Congelar paquete", type="primary"):
                    try:
                        db.congelar(paquete_id, alumno_id, motivo, detalle, desde,
                                    alta_prevista if sabe_cuando else None)
                        st.toast("Paquete congelado", icon="❄️")
                        aviso = ("Paquete congelado. No se le descontaran "
                                 "sesiones hasta que lo reactives.")
                        if sabe_cuando:
                            aviso += (" Se espera su vuelta el "
                                      f"{fecha_larga(alta_prevista)}.")
                        st.success(aviso)
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
                # El congelamiento puede estar programado a futuro: en ese caso
                # todavia no lleva dias, y contarlos daria un numero negativo.
                aun_no_empieza = inicio > logic.hoy()
                dias = 0 if aun_no_empieza else logic.dias_congelamiento(inicio, logic.hoy())
                prevista = logic.a_fecha(c.get("fecha_alta_prevista"))
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.markdown(f"**{c['alumno']}** · {c['codigo']}")
                    c1.caption(f"{c['motivo'].title()} · {c.get('detalle') or 'sin detalle'}")

                    if prevista:
                        faltan = (prevista - logic.hoy()).days
                        if faltan > 0:
                            c1.caption(f"Vuelve el {fecha_larga(prevista)} "
                                       f"(faltan {faltan} dias)")
                        elif faltan == 0:
                            c1.markdown(f":orange[**Vuelve hoy**, {fecha_larga(prevista)}]")
                        else:
                            c1.markdown(f":red[Debia volver el {fecha_larga(prevista)}, "
                                        f"hace {abs(faltan)} dias]")
                    else:
                        c1.caption("Sin fecha prevista de alta")

                    if aun_no_empieza:
                        faltan_ini = (inicio - logic.hoy()).days
                        c2.metric("Se congela el", inicio.strftime("%d/%m/%Y"),
                                  f"en {faltan_ini} dias", delta_color="off")
                    else:
                        c2.metric("Congelado desde", inicio.strftime("%d/%m/%Y"),
                                  f"{dias} dias")
                    # Se propone la fecha que se habia estimado al congelar
                    por_defecto = prevista if prevista and prevista >= inicio \
                        else max(inicio, logic.hoy())
                    alta = c3.date_input("Fecha de alta", value=por_defecto,
                                         min_value=inicio, format="DD/MM/YYYY",
                                         key=f"alta_{c['id']}")
                    if c3.button("Reactivar", key=f"react_{c['id']}",
                                 type="primary", width="stretch"):
                        try:
                            d = db.reactivar(c["id"], alta)
                            st.toast(f"Reactivado, +{d} dias de vigencia", icon="✅")
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
            columnas = ["codigo", "alumno", "motivo", "detalle", "fecha_inicio",
                        "fecha_alta_prevista", "fecha_fin", "dias_aplicados", "activo"]
            for col in columnas:
                if col not in hist.columns:
                    hist[col] = None
            vista = hist[columnas].copy()
            vista.columns = ["Codigo", "Alumno", "Motivo", "Detalle", "Desde",
                             "Alta prevista", "Alta real", "Dias devueltos", "Vigente"]
            st.dataframe(vista, width="stretch", hide_index=True)


# =====================================================================
# 6. RENOVACIONES
# =====================================================================
def pagina_renovaciones() -> None:
    theme.cabecera("Renovaciones", fecha_larga(logic.hoy()).upper(), "A quien hay que llamar")

    alumnos = db.panel_alumnos()
    if alumnos.empty:
        st.info("Sin alumnos registrados.")
        return

    alumnos = con_alertas(alumnos)

    orden = {"VENCIDO": 0, "URGENTE": 1, "PROXIMO": 2, "OK": 3}
    alumnos["orden"] = alumnos["nivel"].map(orden)
    alumnos = alumnos.sort_values(["orden", "apellidos"])

    n_vencidos = int((alumnos["nivel"] == "VENCIDO").sum())
    n_urgentes = int((alumnos["nivel"] == "URGENTE").sum())
    n_proximos = int((alumnos["nivel"] == "PROXIMO").sum())

    theme.kpis([
        ("Ya vencidos", n_vencidos, "sin paquete al dia", "rojo" if n_vencidos else "verde"),
        ("Urgentes", n_urgentes, "les queda 1 sesion o 3 dias",
         "ambar" if n_urgentes else "verde"),
        ("Proximos", n_proximos, "avisar esta semana"),
    ])

    niveles = st.multiselect("Mostrar", ["VENCIDO", "URGENTE", "PROXIMO", "OK"],
                             default=["VENCIDO", "URGENTE", "PROXIMO"])
    datos = alumnos[alumnos["nivel"].isin(niveles)]

    if datos.empty:
        theme.vacio("Sin pendientes",
                    "Ningun alumno de los filtros elegidos necesita renovar.")
        return

    st.divider()
    for _, f in datos.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([2.4, 1.3, 1])
            # pandas devuelve NaN, no None, en los alumnos sin paquete
            usadas = f.get("sesiones_usadas")
            totales = f.get("sesiones_totales")
            usadas = 0 if pd.isna(usadas) else int(usadas)
            totales = 0 if pd.isna(totales) else int(totales)
            c1.markdown(
                f'<div style="display:flex;gap:.7rem;align-items:center">'
                f'{theme.avatar(f["alumno"])}'
                f'<div><b>{esc(f["alumno"])}</b><br>'
                f'<span style="font-size:.78rem;color:{theme.HUMO}">'
                f'{esc(f.get("plan_nombre") or "Sin plan")} &middot; '
                f'{esc(f["motivo"])}</span></div></div>'
                + (theme.barra(usadas, totales) if totales else ""),
                unsafe_allow_html=True)
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
    descargar_csv("Descargar lista de llamadas", vista, "futcross_renovaciones.csv")


# =====================================================================
# 7. REPORTES
# =====================================================================
def pagina_reportes() -> None:
    theme.cabecera("Reportes", fecha_larga(logic.hoy()).upper(), "Asistencia e ingresos")
    hoy = logic.hoy()

    c1, c2 = st.columns(2)
    desde = c1.date_input("Desde", value=hoy.replace(day=1), format="DD/MM/YYYY")
    hasta = c2.date_input("Hasta", value=hoy, format="DD/MM/YYYY")
    if desde > hasta:
        st.error("La fecha inicial no puede ser posterior a la final.")
        return

    asis = db.asistencias(desde, hasta)

    # El rango lo filtra Postgres. Antes se bajaba el historico completo de
    # pedidos de la academia para quedarse con los de un mes.
    vendidos = db.listar_paquetes(desde=desde, hasta=hasta)
    if not vendidos.empty:
        vendidos = vendidos[vendidos["estado_real"] != "CANCELADO"]

    dias_rango = (hasta - desde).days + 1

    # Cuanto se dejo de cobrar por descuentos en el rango
    if not vendidos.empty and "precio_lista" in vendidos.columns:
        lista_total = float(vendidos["precio_lista"].fillna(
            vendidos["precio"]).sum())
        cobrado_total = float(vendidos["precio"].sum())
        descuento_total = lista_total - cobrado_total
        pct_dcto = descuento_total / lista_total * 100 if lista_total else 0
    else:
        cobrado_total = float(vendidos["precio"].sum()) if not vendidos.empty else 0.0
        descuento_total, pct_dcto = 0.0, 0.0

    # Plata que entro sin alumno detras: partidos del domingo y otros cobros
    extra = db.ingresos_extra(desde, hasta)
    total_extra = (float(extra["monto"].fillna(0).astype(float).sum())
                   if not extra.empty else 0.0)

    # Vendido no es lo mismo que cobrado: con pagos parciales, parte de lo
    # vendido todavia esta en la calle.
    if not vendidos.empty and "monto_entregado" in vendidos.columns:
        entrado = float(vendidos["monto_entregado"].fillna(0).sum())
        por_cobrar = max(0.0, cobrado_total - entrado)
    else:
        entrado, por_cobrar = cobrado_total, 0.0

    theme.kpis([
        ("Asistencias", len(asis), f"en {dias_rango} dias", "naranja"),
        ("Paquetes vendidos", len(vendidos), "en el rango elegido"),
        ("Vendido", f"S/ {cobrado_total:,.0f}", "valor de los pedidos"),
        ("Cobrado", f"S/ {entrado:,.0f}", "entro a caja de verdad", "verde"),
        ("Otros ingresos", f"S/ {total_extra:,.0f}", "partidos y cobros sueltos",
         "verde"),
        ("Por cobrar", f"S/ {por_cobrar:,.0f}", "saldos pendientes",
         "rojo" if por_cobrar else "verde"),
        ("Descuentos", f"S/ {descuento_total:,.0f}",
         f"{pct_dcto:.1f}% del precio de lista",
         "ambar" if descuento_total else "neutro"),
    ])
    st.caption(
        f"Entro a caja en el periodo: **S/ {entrado + total_extra:,.2f}** "
        f"(planes S/ {entrado:,.2f} + otros ingresos S/ {total_extra:,.2f})."
    )

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

        theme.seccion("Que dias entrena la gente", "para dimensionar horarios y canchas")
        porc_dia = asis.copy()
        porc_dia["dia"] = porc_dia["fecha"].map(
            lambda f: DIAS[logic.a_fecha(f).weekday()].capitalize())
        conteo_dia = (porc_dia.groupby("dia").size()
                      .reindex([d.capitalize() for d in DIAS]).fillna(0)
                      .rename("Asistencias"))
        st.bar_chart(conteo_dia, color=theme.NARANJA, height=230)

        theme.seccion("Detalle", f"{len(asis)} registros")
        detalle = asis[["fecha", "hora", "codigo", "alumno", "origen"]].copy()
        detalle.columns = ["Fecha", "Hora", "Codigo", "Alumno", "Origen"]
        st.dataframe(detalle, width="stretch", hide_index=True, height=320)
        descargar_csv("Descargar asistencias", detalle,
                      f"futcross_asistencias_{desde}_{hasta}.csv")

    if not vendidos.empty:
        st.divider()
        theme.seccion("Ventas por plan", "cuanto se cobro y cuanto se descontó")
        agrupado = vendidos.copy()
        if "precio_lista" not in agrupado.columns:
            agrupado["precio_lista"] = agrupado["precio"]
        agrupado["precio_lista"] = agrupado["precio_lista"].fillna(agrupado["precio"])
        agrupado["dcto"] = agrupado["precio_lista"] - agrupado["precio"]

        ventas = (agrupado.groupby("plan_nombre")
                  .agg(Paquetes=("id", "count"),
                       Lista=("precio_lista", "sum"),
                       Cobrado=("precio", "sum"),
                       Descuento=("dcto", "sum"))
                  .sort_values("Cobrado", ascending=False))
        st.dataframe(
            ventas, width="stretch",
            column_config={
                "Lista": st.column_config.NumberColumn("Precio lista", format="S/ %.2f"),
                "Cobrado": st.column_config.NumberColumn("Cobrado", format="S/ %.2f"),
                "Descuento": st.column_config.NumberColumn("Descuento", format="S/ %.2f"),
            })

        if "vendedor" in agrupado.columns and agrupado["vendedor"].notna().any():
            theme.seccion("Descuentos por vendedor", "quien esta bajando mas el precio")
            por_vend = (agrupado.dropna(subset=["vendedor"])
                        .groupby("vendedor")
                        .agg(Ventas=("id", "count"),
                             Cobrado=("precio", "sum"),
                             Descuento=("dcto", "sum"))
                        .sort_values("Descuento", ascending=False))
            st.dataframe(
                por_vend, width="stretch",
                column_config={
                    "Cobrado": st.column_config.NumberColumn("Cobrado", format="S/ %.2f"),
                    "Descuento": st.column_config.NumberColumn("Descuento", format="S/ %.2f"),
                })


# =====================================================================
# 8. PLANES
# =====================================================================
def pagina_planes() -> None:
    theme.cabecera("Planes", fecha_larga(logic.hoy()).upper(), "Catalogo y precios")

    planes = db.listar_planes(solo_activos=False)

    tab_lista, tab_editar, tab_nuevo = st.tabs(
        ["Catalogo", "Editar un plan", "Crear plan"])

    # ---------------------------------------------------------- catalogo
    with tab_lista:
        if planes.empty:
            theme.vacio("Todavia no hay planes",
                        "Crea el primero en la pestana Crear plan.")
        else:
            vista = planes[["nombre", "sesiones", "vigencia_dias", "precio",
                            "descripcion", "activo"]].copy()
            vista["por_sesion"] = (vista["precio"] / vista["sesiones"].replace(0, 1))
            vista.columns = ["Plan", "Sesiones", "Vigencia (dias)", "Precio",
                             "Descripcion", "Activo", "Costo por sesion"]
            vista = vista[["Plan", "Sesiones", "Vigencia (dias)", "Precio",
                           "Costo por sesion", "Descripcion", "Activo"]]
            st.dataframe(
                vista, width="stretch", hide_index=True,
                column_config={
                    "Precio": st.column_config.NumberColumn("Precio", format="S/ %.2f"),
                    "Costo por sesion": st.column_config.NumberColumn(
                        "Costo por sesion", format="S/ %.2f",
                        help="Sirve para comparar si el plan largo conviene"),
                    "Activo": st.column_config.CheckboxColumn("Activo"),
                })
            st.caption("Los planes desactivados no aparecen al vender, pero los alumnos "
                       "que ya los tienen los siguen usando hasta agotarlos.")

    # ------------------------------------------------------------ editar
    with tab_editar:
        if planes.empty:
            theme.vacio("Nada que editar", "Primero crea un plan.")
        else:
            elegido = st.selectbox("Plan a editar", planes["nombre"].tolist(),
                                   key="plan_editar")
            fila = planes[planes["nombre"] == elegido].iloc[0]

            try:
                usos = db.paquetes_con_plan(fila["id"])
            except Exception:
                usos = 0
            if usos:
                st.info(f"Este plan se vendio {usos} {'vez' if usos == 1 else 'veces'}. "
                        "Cambiarlo no altera esas ventas: cada paquete guarda las "
                        "sesiones y el precio con los que se cobro.")

            with st.form("form_editar_plan"):
                c1, c2, c3 = st.columns([2, 1, 1])
                nombre = c1.text_input("Nombre", value=str(fila["nombre"]))
                sesiones = c2.number_input("Sesiones", min_value=1,
                                           value=int(fila["sesiones"]))
                vigencia = c3.number_input("Vigencia (dias)", min_value=1,
                                           value=int(fila["vigencia_dias"]))

                d1, d2 = st.columns([1, 1])
                precio = d1.number_input("Precio (S/)", min_value=0.0,
                                         value=float(fila["precio"]), step=10.0)
                activo = d2.selectbox("Estado", ["Activo", "Desactivado"],
                                      index=0 if bool(fila["activo"]) else 1) == "Activo"
                desc = st.text_input("Descripcion",
                                     value=str(fila["descripcion"] or ""))

                if sesiones:
                    st.caption(f"Costo por sesion: S/ {precio / sesiones:.2f}")

                if st.form_submit_button("Guardar cambios", type="primary"):
                    try:
                        db.actualizar_plan(fila["id"], {
                            "nombre": nombre.strip().upper(),
                            "sesiones": int(sesiones),
                            "vigencia_dias": int(vigencia),
                            "precio": float(precio),
                            "descripcion": desc or None,
                            "activo": activo,
                        })
                        st.toast("Plan actualizado", icon="\u2705")
                        st.success("Plan actualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo guardar: {e}")

            st.divider()
            st.markdown("**Sacarlo del catalogo**")
            g1, g2 = st.columns(2)

            etiqueta = "Ocultar del catalogo" if fila["activo"] else "Volver a mostrar"
            if g1.button(etiqueta, width="stretch", key="ocultar_plan"):
                db.actualizar_plan(fila["id"], {"activo": not bool(fila["activo"])})
                st.toast("Catalogo actualizado", icon="\u2705")
                st.rerun()
            g1.caption("Deja de aparecer al vender. Los alumnos que ya lo tienen "
                       "lo siguen usando y el historial queda intacto.")

            confirmar = g2.checkbox("Confirmo que quiero borrarlo",
                                    key="confirmar_borrar_plan")
            if g2.button("Eliminar definitivamente", width="stretch",
                         disabled=not confirmar, key="borrar_plan"):
                try:
                    db.eliminar_plan(fila["id"])
                    st.toast("Plan eliminado", icon="\u2705")
                    st.success(f"Plan {fila['nombre']} eliminado del catalogo.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            g2.caption("Solo se puede si el plan nunca se vendio.")

    # ------------------------------------------------------------- crear
    with tab_nuevo:
        with st.form("form_plan", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])
            nombre = c1.text_input("Nombre del plan",
                                   placeholder="PLAN BASICO 36 SESIONES 3 MESES PROMO")
            sesiones = c2.number_input("Sesiones", min_value=1, value=12)
            vigencia = c3.number_input("Vigencia (dias)", min_value=1, value=30,
                                       help="30 = un mes, 90 = tres meses")
            precio = c4.number_input("Precio (S/)", min_value=0.0, value=180.0, step=10.0)
            desc = st.text_input("Descripcion",
                                 placeholder="3 sesiones por semana durante un mes")

            st.caption(f"Costo por sesion: S/ {precio / max(1, sesiones):.2f}")

            if st.form_submit_button("Crear plan", type="primary"):
                if not nombre.strip():
                    st.error("Ponle un nombre al plan.")
                else:
                    try:
                        db.crear_plan(nombre, sesiones, vigencia, precio, desc or None)
                        st.toast("Plan creado", icon="\u2705")
                        st.success(f"Plan creado: {nombre.strip().upper()}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo crear: {e}")


# =====================================================================
# 9. CARGA MASIVA
# =====================================================================
def pagina_carga_masiva() -> None:
    theme.cabecera("Carga masiva", fecha_larga(logic.hoy()).upper(),
                   "Cargar el padron desde Excel")
    st.caption(
        "Sirve para cargar de golpe a los alumnos que ya tienen. El sistema "
        "revisa el archivo entero y muestra fila por fila que esta bien y que "
        "no; recien cuando todo esta limpio se importa. Nunca se guarda una "
        "carga a medias."
    )

    grupos = db.listar_grupos().to_dict("records")
    planes = db.listar_planes().to_dict("records")

    theme.seccion("1. Descarga la plantilla", "llenala en Excel y vuelve aca")
    c1, c2 = st.columns([1, 2])
    c1.download_button("Descargar plantilla",
                       importar.plantilla_csv().encode("utf-8-sig"),
                       "futcross_plantilla.csv", "text/csv", type="primary")
    with c2:
        st.caption(
            "Solo son obligatorios **nombres**, **apellidos** y **plan**. "
            "Si dejas los dias en blanco, se toman los del grupo; si dejas los "
            "precios, se toma el del plan. La fecha va como 11/08/2026."
        )
        if grupos:
            st.caption("Grupos que puedes usar: " + ", ".join(
                f"**{g['sede']}**" for g in grupos))
        if planes:
            st.caption("Planes: " + ", ".join(f"**{p['nombre']}**" for p in planes))

    theme.seccion("2. Sube el archivo lleno", "acepta Excel y CSV")
    archivo = st.file_uploader("Archivo", type=["csv", "xlsx", "xls"],
                               label_visibility="collapsed")
    if not archivo:
        return

    try:
        if archivo.name.lower().endswith(".csv"):
            crudo = pd.read_csv(archivo, sep=None, engine="python",
                                dtype=str, keep_default_na=False)
        else:
            crudo = pd.read_excel(archivo, dtype=str)
    except ImportError:
        st.error("Para leer Excel falta la libreria openpyxl. Guarda el archivo "
                 "como CSV desde Excel (Archivo > Guardar como > CSV) y subelo.")
        return
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")
        return

    crudo.columns = [str(c).strip().lower().replace(" ", "_") for c in crudo.columns]
    faltan = [c for c in importar.OBLIGATORIAS if c not in crudo.columns]
    if faltan:
        st.error(f"Al archivo le faltan columnas: {', '.join(faltan)}. "
                 "Descarga la plantilla y usa esas cabeceras.")
        return

    for col in importar.COLUMNAS:
        if col not in crudo.columns:
            crudo[col] = ""
    crudo = crudo[[c for c in importar.COLUMNAS]]
    crudo = crudo[crudo.apply(
        lambda f: any(str(v).strip() for v in f), axis=1)]

    if crudo.empty:
        theme.vacio("El archivo esta vacio", "Llena al menos una fila.")
        return

    try:
        existentes = db.dnis_registrados()
    except Exception:
        existentes = {}

    validadas = importar.validar(crudo.to_dict("records"), grupos, planes, existentes)
    res = importar.resumen(validadas)

    theme.seccion("3. Revisa antes de guardar", f"{res['total']} filas leidas")
    theme.kpis([
        ("Alumnos nuevos", res["nuevos"], "se van a crear", "verde"),
        ("Ya existen", res["existentes"], "se les agrega el plan"),
        ("Con problemas", res["errores"], "hay que corregirlos",
         "rojo" if res["errores"] else "verde"),
    ])

    vista = pd.DataFrame(importar.para_mostrar(validadas))
    st.dataframe(vista, width="stretch", hide_index=True, height=380,
                 column_config={
                     "Cobrado": st.column_config.NumberColumn(
                         "Cobrado", format="S/ %.2f"),
                     "Entregado": st.column_config.NumberColumn(
                         "Entregado", format="S/ %.2f"),
                 })

    if res["errores"]:
        st.error(
            f"Hay {res['errores']} filas con problemas. Corrigelas en el Excel "
            "y vuelve a subirlo: no se importa nada hasta que todo este limpio. "
            "La columna Problema dice que le pasa a cada una."
        )
        descargar_csv("Descargar las observaciones",
                      vista[vista["Estado"] == "Revisar"],
                      "futcross_filas_con_problema.csv", clave="csv_errores")
        return

    st.success(
        f"Todo listo: {res['nuevos']} alumnos nuevos y "
        f"{res['existentes']} que ya estaban. "
        "Cada uno queda con su plan y su fecha de vencimiento calculada."
    )
    confirmar = st.checkbox("Confirmo que revise la lista y esta correcta")
    if st.button("Importar ahora", type="primary", disabled=not confirmar,
                 width="stretch"):
        barra = st.progress(0.0, "Importando...")
        creados, fallidas = 0, []
        for i, fila in enumerate(validadas, start=1):
            try:
                db.importar_fila(fila)
                creados += 1
            except Exception as e:
                fallidas.append((fila["_fila"], str(e)[:120]))
            barra.progress(i / len(validadas), f"Importando {i} de {len(validadas)}")
        barra.empty()

        if fallidas:
            st.error(f"Se importaron {creados} de {len(validadas)}. "
                     "Estas filas fallaron:")
            for numero, motivo in fallidas:
                st.write(f"- Fila {numero}: {motivo}")
            st.caption("Las que fallaron NO quedaron a medias. Corrigelas y "
                       "vuelve a subir solo esas: las que ya estan no se duplican.")
        else:
            st.toast(f"{creados} alumnos importados", icon="\u2705")
            st.success(f"Listos los {creados}. Revisalos en la pantalla Alumnos.")


# =====================================================================
# 10. OTROS INGRESOS
# =====================================================================
def pagina_otros_ingresos() -> None:
    """Plata que entra sin un alumno detras.

    El partido amistoso del domingo lo pagan varias personas sueltas y a
    FutCross le interesa el total del dia, no quien pago cuanto. Cargar a
    cada una como alumno con una clase suelta seria inflar el padron con
    gente que no es alumna.
    """
    hoy = logic.hoy()
    theme.cabecera("Otros ingresos", fecha_larga(hoy).upper(),
                   "Partidos y cobros sueltos")
    st.caption(
        "Para la plata que entra sin un alumno detras: el partido amistoso "
        "del domingo, un alquiler de cancha. Se registra el total del dia, no "
        "persona por persona, y suma en Reportes como ingreso de caja."
    )

    # Se propone el domingo mas reciente (hoy mismo si es domingo), que es
    # cuando se juegan los partidos.
    domingo = hoy - timedelta(days=(hoy.weekday() + 1) % 7)

    with st.form("form_ingreso_extra", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        fecha = c1.date_input("Fecha", value=domingo, format="DD/MM/YYYY")
        concepto = c2.text_input("Concepto", value="Partido amistoso domingo")

        c3, c4, c5 = st.columns(3)
        monto = c3.number_input("Monto total (S/)", min_value=0.0, step=10.0,
                                help="Lo que se junto en total ese dia")
        personas = c4.number_input("Cuantas personas (opcional)", min_value=0,
                                   step=1, value=0)
        medio = c5.selectbox("Metodo de pago", ["VARIOS"] + MEDIOS_PAGO)
        notas = st.text_input("Notas", placeholder="Opcional")

        if st.form_submit_button("Registrar ingreso", type="primary"):
            if monto <= 0:
                st.error("Pon el monto total que se cobro.")
            elif not concepto.strip():
                st.error("Ponle un concepto, por ejemplo Partido amistoso domingo.")
            else:
                try:
                    db.registrar_ingreso_extra(
                        fecha, concepto.strip(), float(monto),
                        int(personas) or None, medio, notas.strip() or None)
                    st.toast("Ingreso registrado", icon="\u2705")
                    st.success(f"Registrado: S/ {monto:,.2f} del "
                               f"{fecha_larga(fecha)}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo registrar: {e}")

    theme.seccion("Registrados", "ultimos 90 dias")
    datos = db.ingresos_extra(hoy - timedelta(days=90), hoy + timedelta(days=30))
    if datos.empty:
        theme.vacio("Todavia no hay ingresos registrados",
                    "Cuando se juegue el partido del domingo, anota aca el total.")
        return

    total = float(datos["monto"].fillna(0).astype(float).sum())
    st.caption(f"Total de los ultimos 90 dias: **S/ {total:,.2f}**")

    for _, r in datos.iterrows():
        f = logic.a_fecha(r["fecha"])
        detalle = f"S/ {float(r['monto']):,.2f}"
        gente = r.get("personas")
        if gente is not None and pd.notna(gente) and int(gente) > 0:
            detalle += f" · {int(gente)} personas"
        # pandas convierte los vacios de la base en NaN, que es "verdadero"
        # y se imprimia como "nan". Se filtran los dos casos.
        for campo in ("medio_pago", "notas"):
            valor = r.get(campo)
            if valor is not None and pd.notna(valor) and str(valor).strip():
                detalle += f" · {valor}"

        c1, c2 = st.columns([5, 1])
        with c1:
            theme.fila(f"{fecha_larga(f).title()} · {r['concepto']}",
                       detalle, theme.VERDE)
        if c2.button("Quitar", key=f"quitar_ing_{r['id']}", width="stretch"):
            db.eliminar_ingreso_extra(r["id"])
            st.toast("Ingreso quitado", icon="\u2705")
            st.rerun()


# =====================================================================
# 11. DIAS SIN ENTRENAMIENTO
# =====================================================================
def pagina_dias_libres() -> None:
    theme.cabecera("Dias sin entrenamiento", fecha_larga(logic.hoy()).upper(),
                   "Feriados y cancelaciones")
    st.caption(
        "Como el plan corre por calendario, un dia que la academia no abre le "
        "consumiria una sesion a todos igual. Al marcarlo aca, ese dia deja de "
        "contar y a cada alumno se le corre el plan una sesion mas."
    )

    grupos = db.listar_grupos()

    with st.form("form_no_laborable"):
        c1, c2 = st.columns([1, 2])
        fecha = c1.date_input("Dia que no se entreno", value=logic.hoy(),
                              format="DD/MM/YYYY")

        opciones = {"Todos los grupos": None}
        if not grupos.empty:
            for _, g in grupos.iterrows():
                opciones[f"{g['nombre']} ({g['dias']})"] = g["id"]
        cual = c2.selectbox("A que grupo afecta", list(opciones.keys()),
                            help="Un feriado afecta a todos; una cancha ocupada, "
                                 "solo a ese grupo")

        motivo = st.text_input("Motivo", placeholder="Ej. Feriado 28 de julio, "
                                                     "lluvia, cancha ocupada")

        if st.form_submit_button("Marcar el dia", type="primary"):
            try:
                db.marcar_no_laborable(fecha, opciones[cual], motivo or None)
                st.toast("Dia marcado", icon="\u2705")
                st.success(
                    f"El {fecha_larga(fecha)} ya no le cuenta a "
                    f"{cual.lower()}. Sus planes se corren una sesion."
                )
                st.rerun()
            except Exception as e:
                if "uq_no_laborable" in str(e) or "duplicate" in str(e).lower():
                    st.warning("Ese dia ya estaba marcado para ese grupo.")
                else:
                    st.error(f"No se pudo marcar: {e}")

    theme.seccion("Dias marcados", "de los ultimos meses")
    dias = db.dias_no_laborables(logic.hoy() - timedelta(days=180))
    if dias.empty:
        theme.vacio("Ningun dia marcado",
                    "Cuando no entrenen por feriado o lluvia, marcalo aca para "
                    "que nadie pierda su sesion.")
    else:
        for _, d in dias.iterrows():
            f = logic.a_fecha(d["fecha"])
            c1, c2 = st.columns([5, 1])
            with c1:
                theme.fila(fecha_larga(f).title(),
                           f'{d.get("grupo", "")} · {d.get("motivo") or "sin motivo"}',
                           theme.AZUL)
            if c2.button("Quitar", key=f"quitar_{d['id']}", width="stretch"):
                db.quitar_no_laborable(d["id"])
                st.toast("Dia desmarcado", icon="\u2705")
                st.rerun()


# =====================================================================
# 12. ACCESOS
# =====================================================================
def pagina_accesos() -> None:
    theme.cabecera("Accesos", fecha_larga(logic.hoy()).upper(), "Claves del equipo")
    st.caption(
        "Hay una sola direccion para todo el equipo: la clave que escriben "
        "decide que ven. La de administracion abre las nueve pantallas; la de "
        "entrenador solo Panel, Marcar asistencia, Alumnos y Renovaciones."
    )

    origen_admin = db.leer_config("pin_admin")
    origen_prof = db.leer_config("pin_entrenador")

    theme.seccion("Situacion actual", "")
    c1, c2 = st.columns(2)
    for col, etiqueta, guardado, clave in [
        (c1, "Administracion", origen_admin, "pin_admin"),
        (c2, "Entrenador", origen_prof, "pin_entrenador"),
    ]:
        with col:
            if guardado:
                info = db.config_actualizada(clave) or {}
                cuando = str(info.get("actualizado_en") or "")[:10]
                col.success(f"**{etiqueta}**: clave propia"
                            + (f", cambiada el {cuando}" if cuando else ""))
            else:
                col.warning(f"**{etiqueta}**: usando la clave de los secretos "
                            "del servidor. Cambiala aca para poder administrarla "
                            "desde el panel.")

    theme.seccion("Cambiar una clave", "hay que escribir la clave de administracion actual")
    with st.form("form_pin", clear_on_submit=True):
        cual = st.radio("Que clave cambio",
                        ["Entrenador", "Administracion"], horizontal=True)
        actual = st.text_input("Clave de administracion actual", type="password")
        c3, c4 = st.columns(2)
        nueva = c3.text_input("Clave nueva", type="password")
        repetida = c4.text_input("Repite la clave nueva", type="password")

        if st.form_submit_button("Guardar clave", type="primary"):
            rol_pin = "admin" if cual == "Administracion" else "entrenador"

            if not comparar_pin(actual, pin_guardado("admin")):
                registrar_fallo()
                st.error("La clave de administracion actual no es correcta.")
            else:
                problema = acceso.validar_pin_nuevo(nueva, repetida)
                if problema:
                    st.error(problema)
                elif rol_pin == "entrenador" and comparar_pin(
                        nueva, pin_guardado("admin")):
                    st.error("La clave de entrenador no puede ser igual a la de "
                             "administracion: le daria acceso a todo.")
                else:
                    try:
                        db.guardar_config(CLAVES_PIN[rol_pin],
                                          acceso.hashear_pin(nueva),
                                          quien=ETIQUETA_ROL.get(rol(), ""))
                        st.toast("Clave actualizada", icon="\u2705")
                        st.success(
                            f"Clave de {cual.lower()} actualizada. "
                            + ("Vas a tener que volver a entrar con la nueva."
                               if rol_pin == "admin" else
                               "Pasasela a los entrenadores; la anterior ya no sirve.")
                        )
                    except Exception as e:
                        st.error(f"No se pudo guardar: {e}")

    st.caption(
        "Las claves se guardan cifradas: ni yo ni nadie con acceso a la base "
        "puede leerlas. Si se olvida la de administracion, se recupera "
        "borrando la fila `pin_admin` de la tabla `config` en Supabase, y "
        "vuelve a valer la de los secretos del servidor."
    )


# =====================================================================
# NAVEGACION
# =====================================================================
PAGINAS_ADMIN = {
    "Panel": pagina_panel,
    "Marcar asistencia": pagina_checkin,
    "Renovaciones": pagina_renovaciones,
    "Alumnos": pagina_alumnos,
    "Paquetes": pagina_paquetes,
    "Congelamientos": pagina_congelamientos,
    "Reportes": pagina_reportes,
    "Planes": pagina_planes,
    "Dias sin entrenar": pagina_dias_libres,
    "Carga masiva": pagina_carga_masiva,
    "Otros ingresos": pagina_otros_ingresos,
    "Accesos": pagina_accesos,
}

GRUPOS = [
    ("Dia a dia", ["Panel", "Marcar asistencia", "Renovaciones"]),
    ("Alumnos y pagos", ["Alumnos", "Paquetes", "Congelamientos",
                         "Otros ingresos"]),
    ("Gestion", ["Reportes", "Planes", "Dias sin entrenar",
                 "Carga masiva", "Accesos"]),
]


@st.cache_data(ttl=60, show_spinner=False)
def resumen_del_dia() -> dict:
    """Numeros del pie de la barra lateral. Se refrescan cada minuto para no
    consultar la base en cada clic del menu."""
    hoy = logic.hoy()
    alumnos = db.panel_alumnos()
    asistencias = db.asistencias(hoy, hoy)
    if alumnos.empty:
        return {"asistencias": len(asistencias), "vigentes": 0, "renovar": 0}
    niveles = [logic.alerta_renovacion(f.to_dict())[0] for _, f in alumnos.iterrows()]
    return {
        "asistencias": len(asistencias),
        "vigentes": int((alumnos["estado_real"] == "ACTIVO").sum()),
        "renovar": sum(1 for n in niveles if n in ("VENCIDO", "URGENTE")),
    }


def menu_lateral() -> str:
    """Menu agrupado por lo que uno viene a hacer, no por tabla de la base."""
    st.session_state.setdefault("pagina", "Panel")

    with st.sidebar:
        st.markdown(theme.logo("2.1rem", oscuro=True), unsafe_allow_html=True)
        st.markdown('<div class="menu-grupo">Control de sesiones</div>',
                    unsafe_allow_html=True)

        permitidas = paginas_permitidas()
        for grupo, paginas in GRUPOS:
            visibles = [p for p in paginas if p in permitidas]
            if not visibles:
                continue
            st.markdown(f'<div class="menu-grupo">{grupo}</div>', unsafe_allow_html=True)
            for nombre in visibles:
                activa = st.session_state["pagina"] == nombre
                if st.button(nombre, key=f"nav_{nombre}", width="stretch",
                             type="primary" if activa else "secondary"):
                    st.session_state["pagina"] = nombre
                    st.rerun()

        st.markdown('<div class="menu-grupo">Hoy</div>', unsafe_allow_html=True)
        try:
            r = resumen_del_dia()
            theme.resumen_lateral([
                ("Asistencias", r["asistencias"], theme.CAL),
                ("Vigentes", r["vigentes"], theme.VERDE),
                ("Por renovar", r["renovar"],
                 theme.ROJO if r["renovar"] else theme.VERDE),
            ])
        except Exception:
            st.caption("Sin datos todavia.")

        st.divider()
        st.markdown(
            f'<div class="menu-grupo" style="margin:0 0 .2rem">Sesion</div>'
            f'<div style="font-size:.8rem;color:#C7CBD1;margin-bottom:.15rem">'
            f'{ETIQUETA_ROL.get(rol(), "")}</div>'
            f'<div style="font-size:.68rem;color:#5F656D;margin-bottom:.5rem">'
            f'Version {VERSION}</div>',
            unsafe_allow_html=True)
        if st.button("Cerrar sesion", key="salir", width="stretch"):
            st.session_state.pop("rol", None)
            st.session_state["pagina"] = "Panel"
            st.rerun()

    # Si el rol no alcanza para la pantalla guardada, vuelve al Panel.
    # Esto tapa el caso de un entrenador que entra con una sesion vieja.
    if st.session_state["pagina"] not in permitidas:
        st.session_state["pagina"] = permitidas[0] if permitidas else "Panel"

    return st.session_state["pagina"]


def main() -> None:
    st.session_state.setdefault("candidatos", [])
    st.session_state.setdefault("kiosco", None)
    st.session_state.setdefault("rol", None)

    if hay_sesion() and sesion_expirada():
        st.session_state.pop("rol", None)
        st.session_state.pop("ultimo_uso", None)
        st.session_state["expirada"] = True

    if not hay_sesion():
        if st.session_state.pop("expirada", False):
            st.info("La sesion se cerro sola por inactividad. Vuelve a ingresar el PIN.")
        pantalla_login()
        return

    # Altas automaticas: los congelamientos cuya fecha prevista ya llego.
    # Corre una vez por sesion; en la base ademas corre solo cada noche.
    if not st.session_state.get("altas_revisadas"):
        st.session_state["altas_revisadas"] = True
        try:
            n = db.reactivar_automaticos()
            if n:
                st.toast(f"{n} alumno(s) reactivados automaticamente", icon="\u2705")
        except Exception:
            pass
        # Y las pausas programadas cuya fecha ya llego (viajes avisados
        # con anticipacion)
        try:
            c = db.activar_congelamientos()
            if c:
                st.toast(f"{c} plan(es) entraron en pausa programada", icon="\u2744\ufe0f")
        except Exception:
            pass

    PAGINAS_ADMIN[menu_lateral()]()


if __name__ == "__main__":
    main()
