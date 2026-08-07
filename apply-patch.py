"""
FUTCROSS | Patch 013 - Arreglo: congelar con fecha futura

Requiere los parches 001 a 012 aplicados. No necesita migracion SQL.

EL BUG
  Si se congelaba un paquete con una fecha de inicio posterior a hoy
  (por ejemplo, un alumno que avisa que se va de viaje la proxima
  semana), la pantalla de Congelamientos se caia con un error.
  La causa: se contaban los dias transcurridos desde el inicio, y con
  una fecha futura ese calculo daba negativo y lanzaba excepcion.

EL ARREGLO
  Un congelamiento programado a futuro ahora se muestra bien: en vez de
  "congelado desde hace X dias" dice "se congela el 11/08, en 4 dias".

  Ademas, la fecha prevista de alta ya no puede ser anterior a la fecha
  de congelamiento, y al reactivar la fecha propuesta nunca cae antes
  del inicio. Los dos casos que podian volver a producir el error.

Solo modifica app.py.
"""

import shutil
import sys
from pathlib import Path

PARCHE = "013-congelar-a-futuro"
CARPETA_BACKUP = Path("respaldos") / PARCHE

# Si esta marca ya esta en app.py, el parche ya se aplico
MARCA_APLICADO = "aun_no_empieza"
MARCA_ORIGINAL = "Fecha prevista de alta"


CAMBIOS_APP = [
    (
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.2"\n\n',
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.3"\n\n',
    ),
    (
        '                alta_prevista = d2.date_input(\n                    "Fecha prevista de alta", value=logic.hoy() + timedelta(days=30),\n                    format="DD/MM/YYYY", disabled=not sabe_cuando,\n                    help="Es una estimacion. La fecha real se confirma al reactivar.")\n',
        '                alta_prevista = d2.date_input(\n                    "Fecha prevista de alta", value=desde + timedelta(days=30),\n                    min_value=desde, format="DD/MM/YYYY", disabled=not sabe_cuando,\n                    help="Es una estimacion. La fecha real se confirma al reactivar.")\n',
    ),
    (
        '                inicio = logic.a_fecha(c["fecha_inicio"])\n                dias = logic.dias_congelamiento(inicio, logic.hoy())\n                prevista = logic.a_fecha(c.get("fecha_alta_prevista"))\n',
        '                inicio = logic.a_fecha(c["fecha_inicio"])\n                # El congelamiento puede estar programado a futuro: en ese caso\n                # todavia no lleva dias, y contarlos daria un numero negativo.\n                aun_no_empieza = inicio > logic.hoy()\n                dias = 0 if aun_no_empieza else logic.dias_congelamiento(inicio, logic.hoy())\n                prevista = logic.a_fecha(c.get("fecha_alta_prevista"))\n',
    ),
    (
        '\n                    c2.metric("Congelado desde", inicio.strftime("%d/%m/%Y"), f"{dias} dias")\n                    # Se propone la fecha que se habia estimado al congelar\n',
        '\n                    if aun_no_empieza:\n                        faltan_ini = (inicio - logic.hoy()).days\n                        c2.metric("Se congela el", inicio.strftime("%d/%m/%Y"),\n                                  f"en {faltan_ini} dias", delta_color="off")\n                    else:\n                        c2.metric("Congelado desde", inicio.strftime("%d/%m/%Y"),\n                                  f"{dias} dias")\n                    # Se propone la fecha que se habia estimado al congelar\n',
    ),
    (
        '                    # Se propone la fecha que se habia estimado al congelar\n                    por_defecto = prevista if prevista and prevista >= inicio else logic.hoy()\n                    alta = c3.date_input("Fecha de alta", value=por_defecto,\n',
        '                    # Se propone la fecha que se habia estimado al congelar\n                    por_defecto = prevista if prevista and prevista >= inicio \\\n                        else max(inicio, logic.hoy())\n                    alta = c3.date_input("Fecha de alta", value=por_defecto,\n',
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
        ("Congelamiento a futuro no rompe", "aun_no_empieza" in final_app),
        ("Muestra cuando empieza", '"Se congela el"' in final_app),
        ("Alta prevista posterior al inicio", "min_value=desde" in final_app),
        ("Fecha de alta siempre valida", "max(inicio, logic.hoy())" in final_app),
        ("Version 2.3", 'VERSION = "2.3"' in final_app),
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