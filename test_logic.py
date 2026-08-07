"""
Pruebas de las reglas de negocio. Correr con:  python test_logic.py
No necesita Supabase ni Streamlit.
"""

from datetime import date

import logic


def check(condicion, descripcion):
    print(("  OK   " if condicion else "  FALLA") + f"  {descripcion}")
    assert condicion, descripcion


print("\nVigencia de los planes")
check(logic.fecha_fin_plan(date(2026, 8, 6), 30) == date(2026, 9, 4),
      "Plan de 30 dias iniciado el 06/08 vence el 04/09")
check(logic.fecha_fin_plan(date(2026, 8, 6), 1) == date(2026, 8, 6),
      "Clase suelta vence el mismo dia")

print("\nCongelamiento por lesion")
check(logic.dias_congelamiento(date(2026, 8, 10), date(2026, 8, 15)) == 6,
      "Lesionado del 10 al 15 = 6 dias devueltos")
check(logic.dias_congelamiento(date(2026, 8, 10), date(2026, 8, 10)) == 1,
      "Un solo dia de baja = 1 dia devuelto")
check(logic.extender(date(2026, 9, 4), 6) == date(2026, 9, 10),
      "La vigencia se corre 6 dias hacia adelante")

# Caso completo del enunciado: plan mensual de 12 sesiones, se lesiona a la mitad.
inicio = date(2026, 8, 6)
fin = logic.fecha_fin_plan(inicio, 30)                       # 04/09
dias = logic.dias_congelamiento(date(2026, 8, 20), date(2026, 9, 3))  # 15 dias de baja
fin_nuevo = logic.extender(fin, dias)
check(fin_nuevo == date(2026, 9, 19),
      "Con 15 dias de lesion, el plan de 12 sesiones vence recien el 19/09")

print("\nEstado del paquete")
base = {"estado": "ACTIVO", "sesiones_totales": 12, "sesiones_usadas": 6,
        "fecha_fin": "2026-09-04"}
check(logic.estado_real(base, ref=date(2026, 8, 20)) == "ACTIVO", "Al dia = ACTIVO")
check(logic.estado_real(base, ref=date(2026, 9, 10)) == "VENCIDO", "Pasada la fecha = VENCIDO")
check(logic.estado_real({**base, "sesiones_usadas": 12}, ref=date(2026, 8, 20)) == "AGOTADO",
      "12 de 12 sesiones = AGOTADO")
check(logic.estado_real({**base, "estado": "CONGELADO"}, ref=date(2026, 9, 30)) == "CONGELADO",
      "Congelado no vence aunque pase la fecha")

print("\nControl de la puerta")
ok, cod, _ = logic.puede_entrenar(base, ya_marco_hoy=False, ref=date(2026, 8, 20))
check(ok and cod == "OK", "Paquete vigente: pasa")
ok, cod, _ = logic.puede_entrenar(base, ya_marco_hoy=True, ref=date(2026, 8, 20))
check(not ok and cod == "YA_MARCO", "Doble marca el mismo dia: no descuenta")
ok, cod, _ = logic.puede_entrenar(base, ref=date(2026, 9, 10))
check(not ok and cod == "VENCIDO", "Paquete vencido: no pasa")
ok, cod, _ = logic.puede_entrenar({**base, "estado": "CONGELADO"}, ref=date(2026, 8, 25))
check(not ok and cod == "CONGELADO", "Congelado: no se le descuenta sesion")
ok, cod, _ = logic.puede_entrenar(None)
check(not ok and cod == "SIN_PAQUETE", "Sin paquete: no pasa")

print("\nAlertas de renovacion")
check(logic.alerta_renovacion({"estado_real": "ACTIVO", "sesiones_restantes": 1,
                               "dias_restantes": 20})[0] == "URGENTE",
      "Con 1 sesion restante es urgente")
check(logic.alerta_renovacion({"estado_real": "ACTIVO", "sesiones_restantes": 3,
                               "dias_restantes": 20})[0] == "PROXIMO",
      "Con 3 sesiones restantes avisa")
check(logic.alerta_renovacion({"estado_real": "ACTIVO", "sesiones_restantes": 9,
                               "dias_restantes": 25})[0] == "OK",
      "Con 9 sesiones y 25 dias esta al dia")
check(logic.alerta_renovacion({"estado_real": "VENCIDO", "sesiones_restantes": 4,
                               "dias_restantes": -5})[0] == "VENCIDO",
      "Vencido con sesiones sin usar tambien entra a la lista")
check(logic.alerta_renovacion({"estado_real": "SIN PAQUETE"})[0] == "VENCIDO",
      "Alumno sin paquete aparece para contactar")
check(logic.alerta_renovacion({"estado_real": "CONGELADO", "sesiones_restantes": 6,
                               "dias_restantes": 2})[0] == "OK",
      "Un congelado no se cuenta como pendiente de renovar")

print("\nRitmo y proyeccion")
check(logic.ritmo_semanal(6, date(2026, 8, 1), ref=date(2026, 8, 14)) == 3.0,
      "6 sesiones en 14 dias = 3 por semana")
check(logic.proyeccion_termino(6, 12, date(2026, 8, 1), ref=date(2026, 8, 14)) == date(2026, 8, 28),
      "A 3 por semana, las 6 que faltan salen en 2 semanas")

print("\nUtilitarios")
check(logic.normalizar("Núñez  ") == "nunez", "La busqueda ignora tildes")
check(logic.link_whatsapp("987654321", "hola").startswith("https://wa.me/51987654321"),
      "El link de WhatsApp antepone el codigo de Peru")
check(logic.link_whatsapp("", "hola") is None, "Sin telefono no hay link")

print("\nTodo en orden.\n")
