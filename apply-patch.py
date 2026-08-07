"""
FUTCROSS | Patch 011 - Fecha de inicio del plan a la vista

Requiere los parches 001 a 010 aplicados. No necesita migracion SQL.

  1. Nueva columna "Inicio del plan" en la lista de Alumnos.
     Antes solo se veia "Inscrito", que es cuando se registro al alumno,
     no cuando arranca su plan. Si alguien se inscribe el 7 y su plan
     empieza el 11, esas son dos fechas distintas y hacian falta las dos
     para poder verificar el vencimiento.

     Las tres columnas de fecha ahora traen una ayuda que explica cual
     es cual al pasar el mouse.

  2. Cronograma en la ficha del alumno.
     Un desplegable con las fechas exactas de sus sesiones, numeradas y
     marcando cuales ya uso. Sirve para revisar de una que las cuentas
     cuadran, sin tener que calcular a mano.

Solo modifica app.py.
"""

import shutil
import sys
from pathlib import Path

PARCHE = "011-fecha-de-inicio"
CARPETA_BACKUP = Path("respaldos") / PARCHE

# Si esta marca ya esta en app.py, el parche ya se aplico
MARCA_APLICADO = "Cuando arranca el plan, no cuando se inscribio"
MARCA_ORIGINAL = "Registrar su primer pedido ahora"


CAMBIOS_APP = [
    (
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.0"\n\n',
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.1"\n\n',
    ),
    (
        '                           "sesiones_usadas", "sesiones_totales",\n                           "sesiones_restantes", "fecha_fin", "estado_real",\n                           "fecha_inscripcion"]].copy()\n            vista["avance"] = (vista["sesiones_usadas"].fillna(0)\n',
        '                           "sesiones_usadas", "sesiones_totales",\n                           "sesiones_restantes", "fecha_inicio", "fecha_fin",\n                           "estado_real", "fecha_inscripcion"]].copy()\n            vista["avance"] = (vista["sesiones_usadas"].fillna(0)\n',
    ),
    (
        '            vista.columns = ["Codigo", "Alumno", "Telefono", "Plan", "Restantes",\n                             "Vence", "Estado", "Inscrito", "Avance"]\n            vista = vista[["Codigo", "Alumno", "Telefono", "Plan", "Avance",\n',
        '            vista.columns = ["Codigo", "Alumno", "Telefono", "Plan", "Restantes",\n                             "Inicio del plan", "Vence", "Estado", "Inscrito", "Avance"]\n            vista = vista[["Codigo", "Alumno", "Telefono", "Plan", "Avance",\n',
    ),
    (
        '            vista = vista[["Codigo", "Alumno", "Telefono", "Plan", "Avance",\n                           "Restantes", "Vence", "Estado", "Inscrito"]]\n            for col in ("Vence", "Inscrito"):\n                vista[col] = pd.to_datetime(vista[col], errors="coerce")\n',
        '            vista = vista[["Codigo", "Alumno", "Telefono", "Plan", "Avance",\n                           "Restantes", "Inicio del plan", "Vence", "Estado",\n                           "Inscrito"]]\n            for col in ("Inicio del plan", "Vence", "Inscrito"):\n                vista[col] = pd.to_datetime(vista[col], errors="coerce")\n',
    ),
    (
        '                    "Restantes": st.column_config.NumberColumn("Restantes", format="%d"),\n                    "Vence": st.column_config.DateColumn("Vence", format="DD/MM/YYYY"),\n                    "Inscrito": st.column_config.DateColumn("Inscrito", format="DD/MM/YYYY"),\n                })\n',
        '                    "Restantes": st.column_config.NumberColumn("Restantes", format="%d"),\n                    "Inicio del plan": st.column_config.DateColumn(\n                        "Inicio del plan", format="DD/MM/YYYY",\n                        help="Cuando arranca el plan, no cuando se inscribio"),\n                    "Vence": st.column_config.DateColumn(\n                        "Vence", format="DD/MM/YYYY",\n                        help="Fecha de su ultima sesion"),\n                    "Inscrito": st.column_config.DateColumn(\n                        "Inscrito", format="DD/MM/YYYY",\n                        help="Cuando se registro en la academia"),\n                })\n',
    ),
    (
        '        c3.metric("Vence", "\u2014")\n\n',
        '        c3.metric("Vence", "\u2014")\n\n    if vigente is not None and not vigente.empty:\n        pv = vigente.iloc[0]\n        dias_pv = pv.get("dias_asiste")\n        if dias_pv and not pd.isna(dias_pv):\n            usadas_pv = int(pv["sesiones_usadas"])\n            totales_pv = int(pv["sesiones_totales"])\n            todas = logic.proximas_sesiones(logic.a_fecha(pv["fecha_inicio"]),\n                                            totales_pv, dias_pv)\n            if todas:\n                with st.expander(\n                        f"Cronograma de sus {totales_pv} sesiones "\n                        f"({logic.frecuencia(dias_pv)})"):\n                    filas = []\n                    for n, f in enumerate(todas, 1):\n                        estado = "usada" if n <= usadas_pv else "pendiente"\n                        filas.append({"N": n,\n                                      "Fecha": fecha_larga(f).title(),\n                                      "Estado": estado})\n                    st.dataframe(pd.DataFrame(filas), width="stretch",\n                                 hide_index=True, height=260)\n                    st.caption(f"Primera sesion el {fecha_larga(todas[0])}, "\n                               f"ultima el {fecha_larga(todas[-1])}.")\n\n',
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
        ("Columna Inicio del plan", '"Inicio del plan"' in final_app),
        ("Se distingue de la fecha de inscripcion",
         "Cuando arranca el plan, no cuando se inscribio" in final_app),
        ("Cronograma en la ficha", "Cronograma de sus" in final_app),
        ("Marca las sesiones usadas", '"usada" if n <= usadas_pv' in final_app),
        ("Version 2.1", 'VERSION = "2.1"' in final_app),
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