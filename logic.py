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

    if estado == "CANCELADO":
        return False, "CANCELADO", "Este paquete fue anulado. Consulta en recepcion."
    if estado == "CONGELADO":
        return False, "CONGELADO", "Tu paquete esta congelado. Avisa en recepcion para reactivarlo."
    if estado == "AGOTADO":
        total = paquete.get("sesiones_totales")
        return False, "AGOTADO", f"Ya usaste tus {total} sesiones. Toca renovar el paquete."
    if estado == "VENCIDO":
        fin = a_fecha(paquete.get("fecha_fin"))
        return False, "VENCIDO", f"Tu paquete vencio el {fin.strftime('%d/%m/%Y')}. Toca renovar."
    if ya_marco_hoy:
        return False, "YA_MARCO", "Ya registraste tu asistencia de hoy."

    return True, "OK", "Asistencia registrada. A entrenar."


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
