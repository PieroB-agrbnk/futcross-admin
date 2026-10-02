"""
FUTCROSS | Reglas de negocio puras.

Este modulo no toca la base de datos ni Streamlit: solo fechas y numeros.
Asi se puede testear con `python test_logic.py` sin levantar nada.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")

# Umbrales para avisar de renovacion
SESIONES_AVISO = 3      # avisar cuando quedan 3 sesiones o menos
DIAS_AVISO = 7          # avisar cuando quedan 7 dias o menos


# ---------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------
def hoy() -> date:
    """Fecha de hoy en hora de Lima (no del servidor, que suele estar en UTC)."""
    return datetime.now(LIMA).date()


def ahora_hhmm() -> str:
    return datetime.now(LIMA).strftime("%H:%M")


def a_fecha(valor) -> date | None:
    """Convierte lo que devuelve Supabase (str o date) a un date de Python."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def fecha_fin_plan(fecha_inicio: date, vigencia_dias: int) -> date:
    """Un plan de 30 dias que arranca el 6-ago vence el 5-set (30 dias de uso)."""
    return fecha_inicio + timedelta(days=vigencia_dias - 1)


def dias_congelamiento(inicio: date, fin: date) -> int:
    """Dias perdidos por lesion, contando ambos extremos.

    Lesionado del 10 al 15 = 6 dias que se le devuelven al alumno.
    """
    if fin < inicio:
        raise ValueError("La fecha de alta no puede ser anterior a la de la lesion.")
    return (fin - inicio).days + 1


def extender(fecha_fin: date, dias: int) -> date:
    return fecha_fin + timedelta(days=dias)


def edad(fecha_nacimiento: date | None, ref: date | None = None) -> int | None:
    if not fecha_nacimiento:
        return None
    ref = ref or hoy()
    return ref.year - fecha_nacimiento.year - (
        (ref.month, ref.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
    )


# ---------------------------------------------------------------------
# Estado del paquete
# ---------------------------------------------------------------------
def estado_real(paquete: dict, ref: date | None = None) -> str:
    """Misma logica que la vista v_paquetes, replicada en Python.

    Se usa para previsualizar en pantalla antes de guardar.
    """
    ref = ref or hoy()
    if paquete.get("estado") == "CANCELADO":
        return "CANCELADO"
    if paquete.get("estado") == "CONGELADO":
        return "CONGELADO"
    inicio = a_fecha(paquete.get("fecha_inicio"))
    if inicio and ref < inicio:
        return "POR EMPEZAR"
    usadas = int(paquete.get("sesiones_usadas") or 0)
    totales = int(paquete.get("sesiones_totales") or 0)
    if usadas >= totales:
        return "AGOTADO"
    fin = a_fecha(paquete.get("fecha_fin"))
    if fin and ref > fin:
        return "VENCIDO"
    return "ACTIVO"


def sesiones_restantes(paquete: dict) -> int:
    return max(0, int(paquete.get("sesiones_totales") or 0) - int(paquete.get("sesiones_usadas") or 0))


def dias_restantes(paquete: dict, ref: date | None = None) -> int | None:
    fin = a_fecha(paquete.get("fecha_fin"))
    if not fin:
        return None
    return (fin - (ref or hoy())).days


# ---------------------------------------------------------------------
# Puerta: quien puede entrenar
# ---------------------------------------------------------------------
def puede_entrenar(paquete: dict | None, ya_marco_hoy: bool = False,
                   ref: date | None = None) -> tuple[bool, str, str]:
    """Decide si el alumno entra a la sesion.

    Devuelve (autorizado, codigo_motivo, mensaje para pantalla).
    """
    if paquete is None:
        return False, "SIN_PAQUETE", "No tiene un paquete registrado. Pasa por caja para inscribirte."

    estado = estado_real(paquete, ref)
    ref = ref or hoy()

    if estado == "CANCELADO":
        return False, "CANCELADO", "Este paquete fue anulado. Consulta en recepcion."
    if estado == "CONGELADO":
        return False, "CONGELADO", "Tu plan esta en pausa. Avisa en recepcion para reactivarlo."
    if estado == "POR EMPEZAR":
        inicio = a_fecha(paquete.get("fecha_inicio"))
        return False, "POR_EMPEZAR", (
            f"Tu plan arranca el {inicio.strftime('%d/%m/%Y')}. Nos vemos ese dia.")
    if estado == "AGOTADO":
        total = paquete.get("sesiones_totales")
        return False, "AGOTADO", f"Ya se cumplieron tus {total} sesiones. Toca renovar."
    if estado == "VENCIDO":
        fin = a_fecha(paquete.get("fecha_fin"))
        return False, "VENCIDO", f"Tu plan termino el {fin.strftime('%d/%m/%Y')}. Toca renovar."

    # Hoy no es su dia: puede pasar, pero esa clase se le descuenta como
    # extra (migracion 029) y su plan termina una clase antes.
    dias = paquete.get("dias_asiste")
    if dias and not es_dia_de_entrenamiento(ref, dias):
        return True, "OTRO_DIA", (
            "Hoy no es uno de tus dias. Puedes entrenar, y esta clase se te "
            "descuenta como una clase extra.")
    if ya_marco_hoy:
        return False, "YA_MARCO", "Ya registraste tu asistencia de hoy."

    return True, "OK", "Estas al dia. A entrenar."


# ---------------------------------------------------------------------
# Renovaciones
# ---------------------------------------------------------------------
def alerta_renovacion(fila: dict, ref: date | None = None) -> tuple[str, str]:
    """Clasifica a un alumno para el panel de renovaciones.

    Devuelve (nivel, motivo). Nivel: VENCIDO | URGENTE | PROXIMO | OK.
    """
    ref = ref or hoy()
    estado = fila.get("estado_real") or "SIN PAQUETE"

    if estado in ("SIN PAQUETE", "CANCELADO"):
        return "VENCIDO", "Sin paquete vigente"
    if estado == "AGOTADO":
        return "VENCIDO", "Sesiones agotadas"
    if estado == "VENCIDO":
        dias = fila.get("dias_restantes")
        vencido_hace = abs(int(dias)) if dias is not None else None
        return "VENCIDO", f"Vencio hace {vencido_hace} dias" if vencido_hace else "Paquete vencido"
    if estado == "CONGELADO":
        return "OK", "Congelado (no cuenta para renovacion)"

    rest = fila.get("sesiones_restantes")
    dias = fila.get("dias_restantes")
    rest = int(rest) if rest is not None else None
    dias = int(dias) if dias is not None else None

    if rest is not None and rest <= 1:
        return "URGENTE", f"Le queda {rest} sesion"
    if dias is not None and dias <= 3:
        return "URGENTE", f"Vence en {dias} dias"
    if rest is not None and rest <= SESIONES_AVISO:
        return "PROXIMO", f"Le quedan {rest} sesiones"
    if dias is not None and dias <= DIAS_AVISO:
        return "PROXIMO", f"Vence en {dias} dias"
    return "OK", "Al dia"


def ritmo_semanal(sesiones_usadas: int, fecha_inicio: date, ref: date | None = None) -> float:
    """Sesiones por semana que viene haciendo el alumno.

    Sirve para proyectar si va a terminar sus 12 sesiones antes de que venza.
    """
    ref = ref or hoy()
    dias = max(1, (ref - fecha_inicio).days + 1)
    return round(sesiones_usadas / (dias / 7), 2)


def proyeccion_termino(sesiones_usadas: int, sesiones_totales: int,
                       fecha_inicio: date, ref: date | None = None) -> date | None:
    """Fecha estimada en que agotara sus sesiones al ritmo actual."""
    ref = ref or hoy()
    faltan = sesiones_totales - sesiones_usadas
    if faltan <= 0:
        return ref
    ritmo = ritmo_semanal(sesiones_usadas, fecha_inicio, ref)
    if ritmo <= 0:
        return None
    return ref + timedelta(days=int(round(faltan / ritmo * 7)))


# ---------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Quita tildes y pasa a minusculas, para buscar 'Nunez' y encontrar 'Nunez'."""
    if not texto:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.lower().strip()


def solo_digitos(texto) -> str:
    """Tolera None, NaN y numeros: pandas devuelve NaN en las celdas vacias."""
    if texto is None:
        return ""
    if isinstance(texto, float):
        if texto != texto:          # NaN
            return ""
        texto = f"{texto:.0f}"
    return re.sub(r"\D", "", str(texto))


def link_whatsapp(telefono: str, mensaje: str) -> str | None:
    """Arma el link wa.me. Asume Peru (+51) si el numero viene sin codigo."""
    num = solo_digitos(telefono)
    if not num:
        return None
    if len(num) == 9:
        num = "51" + num
    from urllib.parse import quote
    return f"https://wa.me/{num}?text={quote(mensaje)}"


def mensaje_renovacion(nombre: str, motivo: str, plan: str = "") -> str:
    saludo = nombre.split()[0].title() if nombre else "crack"
    base = f"Hola {saludo}! Te escribimos de FUTCROSS. "
    if "Vencio" in motivo or "vencid" in motivo.lower() or "agotad" in motivo.lower():
        return base + "Tu paquete ya termino y te extranamos en la cancha. Renuevalo y seguimos entrenando."
    return base + f"Ojo que {motivo.lower()}. Renueva a tiempo y no pierdes el ritmo. Nos vemos en la cancha."


# ---------------------------------------------------------------------
# Calendario de entrenamiento
#
# FutCross no vende "30 dias": vende sesiones que caen en dias fijos.
# Un plan de 12 sesiones que arranca el lunes 3 de agosto con grupo de
# lunes, miercoles y viernes termina el viernes 28, no "30 dias despues".
# Por eso la fecha de fin se calcula recorriendo el calendario real.
# ---------------------------------------------------------------------
INDICE_DIA = {"LUN": 0, "MAR": 1, "MIE": 2, "JUE": 3, "VIE": 4, "SAB": 5, "DOM": 6}
NOMBRE_DIA = {v: k for k, v in INDICE_DIA.items()}


def dias_a_indices(dias) -> list[int]:
    """Acepta 'LUN MIE VIE' o ['LUN','MIE','VIE'] y devuelve [0, 2, 4]."""
    if not dias:
        return []
    if isinstance(dias, str):
        dias = dias.replace(",", " ").split()
    vistos = {INDICE_DIA[d.strip().upper()[:3]]
              for d in dias if d.strip().upper()[:3] in INDICE_DIA}
    return sorted(vistos)


def es_dia_de_entrenamiento(fecha: date, dias) -> bool:
    return fecha.weekday() in dias_a_indices(dias)


def dias_en(fecha: date, dias, historial=None):
    """Los dias que rigen para un plan en una fecha.

    `historial` son pares (hasta, dias_anteriores): antes de `hasta` el plan
    entrenaba con esos dias. Asi un cambio de horario del grupo (Surco
    dejo los lunes en octubre) no cambia lo que ya se entreno.
    """
    for hasta, anteriores in sorted(historial or (), key=lambda h: h[0]):
        if fecha < hasta:
            return anteriores
    return dias


def fecha_de_sesion(inicio: date, numero: int, dias,
                    excluir=None, historial=None) -> date | None:
    """Fecha en la que cae la sesion numero N.

    Cuenta desde `inicio` inclusive: si el inicio cae en un dia de
    entrenamiento, ese dia es la sesion 1. `excluir` son fechas que no
    cuentan (dias sin entrenamiento): la sesion se corre a la siguiente.
    """
    if not dias_a_indices(dias) and not historial:
        return None
    if numero < 1:
        return None
    excluir = set(excluir or ())

    fecha = inicio
    contadas = 0
    # Tope de seguridad: 5 anios. Ningun plan real llega ni cerca.
    for _ in range(365 * 5):
        indices = dias_a_indices(dias_en(fecha, dias, historial))
        if fecha.weekday() in indices and fecha not in excluir:
            contadas += 1
            if contadas == numero:
                return fecha
        fecha += timedelta(days=1)
    return None


def fecha_fin_por_calendario(inicio: date, sesiones: int, dias,
                             vigencia_dias: int | None = None,
                             excluir=None, historial=None) -> date:
    """Fecha de la ultima sesion del plan.

    Si el grupo no tiene dias definidos, cae en el metodo viejo de contar
    dias corridos, para que nada quede sin fecha de fin.
    """
    fin = fecha_de_sesion(inicio, sesiones, dias, excluir, historial)
    if fin:
        return fin
    return fecha_fin_plan(inicio, vigencia_dias or 30)


def proximas_sesiones(inicio: date, cantidad: int, dias, excluir=None,
                      historial=None) -> list:
    """Las fechas exactas de las proximas N sesiones. Para mostrar el
    cronograma al alumno cuando compra."""
    if (not dias_a_indices(dias) and not historial) or cantidad < 1:
        return []
    excluir = set(excluir or ())

    fechas, fecha = [], inicio
    for _ in range(365 * 5):
        indices = dias_a_indices(dias_en(fecha, dias, historial))
        if fecha.weekday() in indices and fecha not in excluir:
            fechas.append(fecha)
            if len(fechas) == cantidad:
                break
        fecha += timedelta(days=1)
    return fechas


def sesiones_entre(desde: date, hasta: date, dias) -> int:
    """Cuantas sesiones caen en un rango. Sirve para calcular cuantas se
    perdio un alumno mientras estuvo congelado."""
    indices = dias_a_indices(dias)
    if not indices or hasta < desde:
        return 0
    total, fecha = 0, desde
    while fecha <= hasta:
        if fecha.weekday() in indices:
            total += 1
        fecha += timedelta(days=1)
    return total


def ventanas_alternas(desde: date, vuelta: date, cada_semanas: int,
                      veces: int) -> list:
    """Pausas que se repiten: [(inicio, vuelta), ...].

    Para el alumno que trabaja en mina, una semana si y otra no: la pausa
    del 21 al 28 se repite cada 2 semanas, del 5 al 12, del 19 al 26...
    La vuelta es el dia que regresa, asi que ese dia ya cuenta como clase.
    """
    salto = timedelta(weeks=max(1, int(cada_semanas)))
    return [(desde + salto * i, vuelta + salto * i)
            for i in range(max(1, int(veces)))]


def se_superpone(desde: date, vuelta: date | None, existentes) -> bool:
    """True si la pausa [desde, vuelta) choca con alguna de las existentes.

    `existentes` son pares (inicio, fin) donde fin es el dia de vuelta, o
    None si la pausa sigue abierta sin fecha de vuelta.
    """
    fin_nueva = vuelta or date.max
    for inicio, fin in existentes:
        if inicio is None:
            continue
        if desde < (fin or date.max) and inicio < fin_nueva:
            return True
    return False


# Feriados nacionales (Decreto Legislativo 713 y leyes que lo modifican,
# calendario de gob.pe). Semana Santa cambia cada anio. Hay un proyecto en
# el Congreso para mover algunos a lunes: revisar esta lista cada enero.
FERIADOS_PERU = {
    date(2026, 10, 8): "Combate de Angamos",
    date(2026, 11, 1): "Todos los Santos",
    date(2026, 12, 8): "Inmaculada Concepcion",
    date(2026, 12, 9): "Batalla de Ayacucho",
    date(2026, 12, 25): "Navidad",
    date(2027, 1, 1): "Anio Nuevo",
    date(2027, 3, 25): "Jueves Santo",
    date(2027, 3, 26): "Viernes Santo",
    date(2027, 5, 1): "Dia del Trabajo",
    date(2027, 6, 7): "Batalla de Arica y Dia de la Bandera",
    date(2027, 6, 29): "San Pedro y San Pablo",
    date(2027, 7, 23): "Dia de la Fuerza Aerea",
    date(2027, 7, 28): "Fiestas Patrias",
    date(2027, 7, 29): "Fiestas Patrias",
    date(2027, 8, 6): "Batalla de Junin",
    date(2027, 8, 30): "Santa Rosa de Lima",
    date(2027, 10, 8): "Combate de Angamos",
    date(2027, 11, 1): "Todos los Santos",
    date(2027, 12, 8): "Inmaculada Concepcion",
    date(2027, 12, 9): "Batalla de Ayacucho",
    date(2027, 12, 25): "Navidad",
}


ORDEN_SEMANA = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]


def _lista_dias(dias) -> list:
    if not dias:
        return []
    if isinstance(dias, str):
        dias = dias.replace(",", " ").split()
    return [d.strip().upper()[:3] for d in dias if d.strip()]


def ajustar_dias(viejos, nuevos) -> str:
    """Los dias de un alumno despues de un cambio de horario del grupo.

    Se quedan los que siguen existiendo y se completa con los nuevos hasta
    la misma cantidad. Misma regla que fc_ajustar_dias en la base.
    """
    v, n = _lista_dias(viejos), _lista_dias(nuevos)
    if not v:
        return " ".join(n)
    meta = min(len(v), len(n))
    quedan = [d for d in n if d in v]
    for d in n:
        if len(quedan) >= meta:
            break
        if d not in quedan:
            quedan.append(d)
    return " ".join(d for d in n if d in quedan)


def dias_previos(actuales, antes, frecuencia=None) -> str:
    """Los dias que un plan tenia antes de un cambio de horario, por defecto.

    Se quedan los de hoy que tambien existian antes y se completa con los
    de antes hasta la frecuencia del plan: un premium de Surco vuelve a
    LUN MIE VIE. Misma regla que fc_dias_previos en la base.
    """
    a, b = _lista_dias(actuales), _lista_dias(antes)
    if not b:
        return " ".join(a)
    meta = min(int(frecuencia) if frecuencia else len(a), len(b))
    quedan = [d for d in b if d in a]
    for d in b:
        if len(quedan) >= meta:
            break
        if d not in quedan:
            quedan.append(d)
    return " ".join(d for d in b if d in quedan)


def sesiones_txt(n) -> str:
    """'1 sesion', '12 sesiones'. Evita el '1 sesiones' de la pantalla."""
    n = int(n)
    return f"{n} sesion" if n == 1 else f"{n} sesiones"


def frecuencia(dias) -> str:
    """'LUN MIE VIE' -> '3 veces por semana'."""
    n = len(dias_a_indices(dias))
    if n == 0:
        return "sin dias definidos"
    return "1 vez por semana" if n == 1 else f"{n} veces por semana"
