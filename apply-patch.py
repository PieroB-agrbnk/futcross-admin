"""
FUTCROSS | Patch 007 - Editar alumno y numero de version

Requiere los parches 001 a 006 aplicados.

  1. Nueva pestana "Editar alumno" en la pantalla de Alumnos.
     Modifica nombres, DNI, telefono, correo, fecha de nacimiento, sede,
     turno, dias que asiste, hora, contacto de emergencia y notas.
     Tambien permite dar de baja a un alumno sin borrar su historial.
     El codigo y la fecha de inscripcion no se tocan, a proposito.

  2. La barra lateral ahora muestra el numero de version.
     Sirve para saber de un vistazo si la version que se ve en la nube es
     la misma que corre en la computadora. Si los numeros no coinciden,
     falta hacer git push o reiniciar la app en el servidor.

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

PARCHE = "007-editar-alumno"
CARPETA_BACKUP = Path("respaldos") / PARCHE

# Si esta marca ya esta en app.py, el parche ya se aplico
MARCA_APLICADO = "def editar_alumno()"
MARCA_ORIGINAL = "Registrar pedido"


CAMBIOS_APP = [
    (
        'theme.aplicar_estilos()\n\n',
        'theme.aplicar_estilos()\n\n# Se muestra en la barra lateral. Sirve para saber de un vistazo si la version\n# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "1.7"\n\n',
    ),
    (
        '    if es_admin():\n        tab_lista, tab_nuevo = st.tabs(["Lista", "Inscribir alumno"])\n    else:\n',
        '    if es_admin():\n        tab_lista, tab_nuevo, tab_editar = st.tabs(\n            ["Lista", "Inscribir alumno", "Editar alumno"])\n    else:\n',
    ),
    (
        '        (tab_lista,) = st.tabs(["Lista"])\n        tab_nuevo = None\n\n',
        '        (tab_lista,) = st.tabs(["Lista"])\n        tab_nuevo = tab_editar = None\n\n',
    ),
    (
        '    if tab_nuevo is None:\n        return\n\n    with tab_nuevo:\n',
        '    if tab_nuevo is None:\n        return\n\n    with tab_editar:\n        editar_alumno()\n\n    with tab_nuevo:\n',
    ),
    (
        '                    except Exception as e:\n                        st.error(f"No se pudo guardar: {e}")\n\n\n',
        '                    except Exception as e:\n                        st.error(f"No se pudo guardar: {e}")\n\n\ndef editar_alumno() -> None:\n    """Modifica los datos de un alumno ya inscrito.\n\n    Todo llega precargado con lo que ya tiene, asi que solo se toca lo que\n    cambia. Tambien permite darlo de baja sin borrar su historial.\n    """\n    todos = db.panel_alumnos(solo_activos=False)\n    if todos.empty:\n        theme.vacio("No hay alumnos", "Primero inscribe a alguien.")\n        return\n\n    etiquetas = {f"{r[\'codigo\']} - {r[\'alumno\']}": r["alumno_id"]\n                 for _, r in todos.iterrows()}\n    elegido = st.selectbox("Alumno a editar", list(etiquetas.keys()),\n                           key="alumno_editar")\n    alumno_id = etiquetas[elegido]\n\n    a = db.alumno(alumno_id)\n    if not a:\n        st.error("No se encontro el alumno.")\n        return\n\n    def texto(clave, defecto=""):\n        valor = a.get(clave)\n        return defecto if valor is None or (isinstance(valor, float) and pd.isna(valor)) \\\n            else str(valor)\n\n    try:\n        opciones_sede = db.sedes()\n    except Exception:\n        opciones_sede = ["SURQUILLO"]\n    sede_actual = texto("sede") or (opciones_sede[0] if opciones_sede else "SURQUILLO")\n    if sede_actual not in opciones_sede:\n        opciones_sede = [sede_actual] + opciones_sede\n\n    turno_actual = texto("turno") or TURNOS[0]\n    dias_actuales = [d for d in texto("dias_asiste").split() if d in DIAS_SEMANA]\n\n    with st.form("form_editar_alumno"):\n        c1, c2 = st.columns(2)\n        nombres = c1.text_input("Nombres *", value=texto("nombres"))\n        apellidos = c2.text_input("Apellidos *", value=texto("apellidos"))\n        dni = c1.text_input("DNI", value=texto("dni"))\n        telefono = c2.text_input("Telefono", value=texto("telefono"))\n        email = c1.text_input("Correo", value=texto("email"))\n\n        nac = logic.a_fecha(a.get("fecha_nacimiento"))\n        nacimiento = c2.date_input("Fecha de nacimiento", value=nac,\n                                   min_value=logic.hoy() - timedelta(days=365 * 80),\n                                   max_value=logic.hoy(), format="DD/MM/YYYY")\n\n        st.markdown("**Donde y cuando entrena**")\n        d1, d2, d3 = st.columns([1.2, 1, 2])\n        sede = d1.selectbox("Sede", opciones_sede,\n                            index=opciones_sede.index(sede_actual))\n        turno = d2.selectbox("Turno", TURNOS,\n                             index=TURNOS.index(turno_actual)\n                             if turno_actual in TURNOS else 0)\n        dias = d3.multiselect("Dias que asiste", DIAS_SEMANA, default=dias_actuales)\n        horario = st.text_input("Hora exacta", value=texto("horario"))\n\n        e1, e2 = st.columns(2)\n        emergencia = e1.text_input("Contacto de emergencia",\n                                   value=texto("contacto_emergencia"))\n        activo = e2.selectbox(\n            "Estado del alumno", ["Activo", "Dado de baja"],\n            index=0 if a.get("activo", True) else 1,\n            help="Dar de baja lo saca de los listados pero conserva su historial",\n        ) == "Activo"\n        notas = st.text_area("Notas", value=texto("notas"))\n\n        st.caption(f"Codigo {a[\'codigo\']} - inscrito el "\n                   f"{logic.a_fecha(a[\'fecha_inscripcion\']).strftime(\'%d/%m/%Y\')}. "\n                   "El codigo y la fecha de inscripcion no se modifican.")\n\n        if st.form_submit_button("Guardar cambios", type="primary"):\n            if not nombres.strip() or not apellidos.strip():\n                st.error("Nombres y apellidos son obligatorios.")\n            else:\n                try:\n                    db.actualizar_alumno(alumno_id, {\n                        "nombres": nombres.strip().title(),\n                        "apellidos": apellidos.strip().title(),\n                        "dni": logic.solo_digitos(dni) or None,\n                        "telefono": logic.solo_digitos(telefono) or None,\n                        "email": email.strip() or None,\n                        "fecha_nacimiento": nacimiento,\n                        "sede": sede,\n                        "turno": turno,\n                        "dias_asiste": " ".join(dias),\n                        "horario": horario or None,\n                        "contacto_emergencia": emergencia or None,\n                        "notas": notas or None,\n                        "activo": activo,\n                    })\n                    st.toast("Alumno actualizado", icon="\\u2705")\n                    st.success(f"Datos de {nombres} {apellidos} actualizados.")\n                    st.rerun()\n                except Exception as e:\n                    st.error(f"No se pudo guardar: {e}")\n\n\n',
    ),
    (
        '            f\'<div class="menu-grupo" style="margin:0 0 .2rem">Sesion</div>\'\n            f\'<div style="font-size:.8rem;color:#C7CBD1;margin-bottom:.5rem">\'\n            f\'{ETIQUETA_ROL.get(rol(), "")}</div>\',\n            unsafe_allow_html=True)\n',
        '            f\'<div class="menu-grupo" style="margin:0 0 .2rem">Sesion</div>\'\n            f\'<div style="font-size:.8rem;color:#C7CBD1;margin-bottom:.15rem">\'\n            f\'{ETIQUETA_ROL.get(rol(), "")}</div>\'\n            f\'<div style="font-size:.68rem;color:#5F656D;margin-bottom:.5rem">\'\n            f\'Version {VERSION}</div>\',\n            unsafe_allow_html=True)\n',
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
        ("Editor de alumnos", "def editar_alumno()" in final_app),
        ("Pestana Editar alumno", '"Editar alumno"' in final_app),
        ("Permite dar de baja", '"Dado de baja"' in final_app),
        ("Guarda sede, turno y dias", '"dias_asiste": " ".join(dias)' in final_app),
        ("Numero de version visible", 'VERSION = "1.7"' in final_app),
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