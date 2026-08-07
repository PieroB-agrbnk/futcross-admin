"""
FUTCROSS | Patch 005 - Entrenadores y administracion

Requiere los parches 001 a 004 aplicados.

Ahora hay dos claves y dos niveles de acceso:

  ADMIN_PIN       ve las 8 pantallas: vende paquetes, congela por lesion,
                  cambia precios y ve los ingresos.

  ENTRENADOR_PIN  ve solo Panel, Marcar asistencia, Alumnos y Renovaciones.
                  Puede consultar cuantas sesiones le quedan a cada alumno
                  y marcar asistencia, pero no ve plata, no vende paquetes,
                  no cambia precios y no puede inscribir ni anular.

El menu se arma segun quien entro, y si alguien fuerza una pantalla que su
rol no permite, el sistema lo devuelve al Panel.

Acuerdate de agregar ENTRENADOR_PIN a .streamlit/secrets.toml (y a los
secretos del servidor, si ya publicaste el panel). Sin esa clave, el modo
entrenador simplemente no existe y todo sigue funcionando como antes.

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

PARCHE = "005-roles"
CARPETA_BACKUP = Path("respaldos") / PARCHE

# Si esta marca ya esta en app.py, el parche ya se aplico
MARCA_APLICADO = "PERMISOS = {"
MARCA_ORIGINAL = "def registrar_fallo()"


CAMBIOS_APP = [
    (
        '# =====================================================================\ndef es_admin() -> bool:\n',
        '# =====================================================================\n# Quien puede ver que. El entrenador necesita saber quien entrena y cuantas\n# sesiones le quedan a cada alumno, pero no tiene por que ver los ingresos ni\n# poder cambiar precios: eso es plata y es del administrador.\nPERMISOS = {\n    "admin": ["Panel", "Marcar asistencia", "Renovaciones", "Alumnos",\n              "Paquetes", "Congelamientos", "Reportes", "Planes"],\n    "entrenador": ["Panel", "Marcar asistencia", "Alumnos", "Renovaciones"],\n}\n\nETIQUETA_ROL = {"admin": "Administracion", "entrenador": "Entrenador"}\n\n\ndef rol() -> str | None:\n    return st.session_state.get("rol")\n\n\ndef hay_sesion() -> bool:\n    return rol() in PERMISOS\n\n\ndef es_admin() -> bool:\n',
    ),
    (
        'def es_admin() -> bool:\n    return bool(st.session_state.get("admin_ok"))\n\n',
        'def es_admin() -> bool:\n    """Solo la administracion vende, congela, anula y ve la plata."""\n    return rol() == "admin"\n\n\ndef paginas_permitidas() -> list:\n    return PERMISOS.get(rol(), [])\n\n',
    ),
    (
        '    # significaba que una instalacion mal configurada quedaba abierta.\n    pin_valido = secreto("ADMIN_PIN")\n    if not pin_valido:\n        st.error(\n',
        '    # significaba que una instalacion mal configurada quedaba abierta.\n    pin_admin = secreto("ADMIN_PIN")\n    pin_entrenador = secreto("ENTRENADOR_PIN")\n    if not pin_admin:\n        st.error(\n',
    ),
    (
        '        # compare_digest tarda lo mismo acierte o falle, asi el tiempo de\n        # respuesta no delata cuantos caracteres eran correctos.\n        if pin and hmac.compare_digest(str(pin), str(pin_valido)):\n            st.session_state["admin_ok"] = True\n            st.session_state.pop("acceso", None)\n',
        '        # compare_digest tarda lo mismo acierte o falle, asi el tiempo de\n        # respuesta no delata cuantos caracteres eran correctos. Se comparan\n        # los dos PIN siempre, para que tampoco se note cual acerto.\n        acierta_admin = bool(pin) and hmac.compare_digest(str(pin), str(pin_admin))\n        acierta_entrenador = (bool(pin) and bool(pin_entrenador)\n                              and hmac.compare_digest(str(pin), str(pin_entrenador)))\n\n        if acierta_admin or acierta_entrenador:\n            st.session_state["rol"] = "admin" if acierta_admin else "entrenador"\n            st.session_state["pagina"] = "Panel"\n            st.session_state.pop("acceso", None)\n',
    ),
    (
        '\n    tab_lista, tab_nuevo = st.tabs(["Lista", "Inscribir alumno"])\n\n',
        '\n    if es_admin():\n        tab_lista, tab_nuevo = st.tabs(["Lista", "Inscribir alumno"])\n    else:\n        (tab_lista,) = st.tabs(["Lista"])\n        tab_nuevo = None\n\n',
    ),
    (
        '            ficha_alumno(opciones[elegido])\n\n',
        '            ficha_alumno(opciones[elegido])\n\n    if tab_nuevo is None:\n        return\n\n',
    ),
    (
        '\n        for grupo, paginas in GRUPOS:\n',
        '\n        permitidas = paginas_permitidas()\n        for grupo, paginas in GRUPOS:\n',
    ),
    (
        '        for grupo, paginas in GRUPOS:\n            st.markdown(f\'<div class="menu-grupo">{grupo}</div>\', unsafe_allow_html=True)\n',
        '        for grupo, paginas in GRUPOS:\n            visibles = [p for p in paginas if p in permitidas]\n            if not visibles:\n                continue\n            st.markdown(f\'<div class="menu-grupo">{grupo}</div>\', unsafe_allow_html=True)\n',
    ),
    (
        '            st.markdown(f\'<div class="menu-grupo">{grupo}</div>\', unsafe_allow_html=True)\n            for nombre in paginas:\n                activa = st.session_state["pagina"] == nombre\n',
        '            st.markdown(f\'<div class="menu-grupo">{grupo}</div>\', unsafe_allow_html=True)\n            for nombre in visibles:\n                activa = st.session_state["pagina"] == nombre\n',
    ),
    (
        '        st.divider()\n        if st.button("Cerrar sesion", key="salir", width="stretch"):\n',
        '        st.divider()\n        st.markdown(\n            f\'<div class="menu-grupo" style="margin:0 0 .2rem">Sesion</div>\'\n            f\'<div style="font-size:.8rem;color:#C7CBD1;margin-bottom:.5rem">\'\n            f\'{ETIQUETA_ROL.get(rol(), "")}</div>\',\n            unsafe_allow_html=True)\n        if st.button("Cerrar sesion", key="salir", width="stretch"):\n',
    ),
    (
        '        if st.button("Cerrar sesion", key="salir", width="stretch"):\n            st.session_state["admin_ok"] = False\n            st.session_state["pagina"] = "Panel"\n',
        '        if st.button("Cerrar sesion", key="salir", width="stretch"):\n            st.session_state.pop("rol", None)\n            st.session_state["pagina"] = "Panel"\n',
    ),
    (
        '            st.session_state["pagina"] = "Panel"\n            st.rerun()\n\n    return st.session_state["pagina"]\n',
        '            st.session_state["pagina"] = "Panel"\n            st.rerun()\n\n    # Si el rol no alcanza para la pantalla guardada, vuelve al Panel.\n    # Esto tapa el caso de un entrenador que entra con una sesion vieja.\n    if st.session_state["pagina"] not in permitidas:\n        st.session_state["pagina"] = permitidas[0] if permitidas else "Panel"\n\n    return st.session_state["pagina"]\n',
    ),
    (
        '    st.session_state.setdefault("kiosco", None)\n\n',
        '    st.session_state.setdefault("kiosco", None)\n    st.session_state.setdefault("rol", None)\n\n',
    ),
    (
        '\n    if not es_admin():\n        pantalla_login()\n',
        '\n    if not hay_sesion():\n        pantalla_login()\n',
    ),
]


EJEMPLO_SECRETOS = '# Copia este archivo como  .streamlit/secrets.toml  y completa tus datos.\n# NUNCA subas secrets.toml a GitHub (ya esta en .gitignore).\n\nSUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"\nSUPABASE_KEY = "eyJ...service_role..."   # Supabase > Settings > API > service_role\n\n# Dos claves distintas, dos niveles de acceso:\nADMIN_PIN      = "clave-de-administracion"  # ve todo: paquetes, precios, ingresos\nENTRENADOR_PIN = "clave-de-entrenadores"    # solo Panel, asistencia, alumnos y renovaciones\n'


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
    origen_tema = CARPETA_BACKUP / "secrets.toml.example"

    if not origen_app.exists():
        error("No hay respaldos en " + str(CARPETA_BACKUP) + ". Nada que revertir.")

    shutil.copy2(origen_app, app)
    print("")
    print("  Revertido. app.py volvio a la version anterior.")
    print("")


def aplicar():
    app = Path("app.py")
    tema = Path(".streamlit/secrets.toml.example")

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
        error("Faltan los parches 001 a 004. Aplicalos primero, en orden.")

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
    if tema.exists():
        respaldar(tema)

    # -------------------------------------------------------------- aplicar
    for viejo, nuevo in CAMBIOS_APP:
        texto_app = texto_app.replace(viejo, nuevo, 1)

    escribir(app, texto_app, salto_app)
    if tema.exists():
        escribir(tema, EJEMPLO_SECRETOS, leer(tema)[1])

    # ---------------------------------------------------------- verificacion
    final_app, _ = leer(app)

    controles = [
        ("Dos roles definidos", '"entrenador"' in final_app and '"admin"' in final_app),
        ("Clave de entrenador", "ENTRENADOR_PIN" in final_app),
        ("Menu filtrado por rol", "paginas_permitidas()" in final_app),
        ("Reportes fuera del alcance del entrenador",
         '"Reportes"' in final_app.split("PERMISOS = {")[1].split("}")[0]),
        ("Redireccion si el rol no alcanza",
         'st.session_state["pagina"] not in permitidas' in final_app),
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