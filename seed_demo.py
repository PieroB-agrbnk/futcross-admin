"""
FUTCROSS | Carga datos de prueba para ver el sistema funcionando.

Uso:   streamlit run seed_demo.py
Luego, cuando ya tengas alumnos reales, borra este archivo.

Crea 6 alumnos que cubren todos los casos:
  - uno al dia
  - uno con una sola sesion restante (aparece como urgente)
  - uno vencido con sesiones sin usar
  - uno lesionado y congelado
  - uno que ya termino sus 12 sesiones
  - uno recien inscrito sin paquete
"""

from datetime import timedelta

import streamlit as st

import db
import logic

st.set_page_config(page_title="FutCross | Datos de prueba", page_icon="🟠")
st.title("Cargar datos de prueba")
st.warning("Esto crea alumnos ficticios. No lo corras sobre la base real.")

hoy = logic.hoy()

PERFILES = [
    # (nombres, apellidos, dni, telefono, inicio_hace_dias, asistencias, congelar)
    ("Piero",  "Best",    "45678912", "987111222", 12, 5,  False),
    ("Luis",   "Nunez",   "41112233", "987222333", 26, 11, False),
    ("Marco",  "Salazar", "44556677", "987333444", 48, 7,  False),
    ("Andrea", "Quispe",  "47788990", "987444555", 20, 6,  True),
    ("Diego",  "Ramos",   "42211334", "987555666", 33, 12, False),
    ("Ana",    "Rojas",   "46655443", "987666777", None, 0, False),
]

if st.button("Cargar los 6 alumnos de prueba", type="primary"):
    planes = db.listar_planes()
    plan = planes[planes["sesiones"] == 12].iloc[0].to_dict()
    creados = []

    for nombres, apellidos, dni, tel, hace, asistencias, congelar in PERFILES:
        try:
            alumno = db.crear_alumno({
                "nombres": nombres, "apellidos": apellidos, "dni": dni,
                "telefono": tel, "horario": "Lun/Mie/Vie 8 p.m.",
                "fecha_inscripcion": hoy - timedelta(days=hace or 0),
            })[0]
        except Exception as e:
            st.write(f"- {nombres} {apellidos}: ya existia o fallo ({e})")
            continue

        if hace is None:
            creados.append(f"{alumno['codigo']} {nombres} {apellidos} — sin paquete")
            continue

        inicio = hoy - timedelta(days=hace)
        db.crear_paquete(alumno["id"], plan, inicio, plan["precio"], "Yape")
        paquete = db.ultimo_paquete(alumno["id"])

        # Asistencias repartidas lunes, miercoles y viernes hacia atras
        fecha = inicio
        puestas = 0
        while puestas < asistencias and fecha <= hoy:
            if fecha.weekday() in (0, 2, 4):
                try:
                    db.marcar_asistencia(alumno["id"], paquete["id"],
                                         origen="ADMIN", fecha=fecha)
                    puestas += 1
                except Exception:
                    pass
            fecha += timedelta(days=1)

        if congelar:
            db.congelar(paquete["id"], alumno["id"], "LESION",
                        "Esguince de tobillo, reposo indicado por el fisio",
                        hoy - timedelta(days=6))

        creados.append(f"{alumno['codigo']} {nombres} {apellidos} — "
                       f"{puestas} sesiones usadas{' (congelado)' if congelar else ''}")

    st.success("Listo. Abre app.py para ver el sistema con datos.")
    for c in creados:
        st.write("- " + c)
