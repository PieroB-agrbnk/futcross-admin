"""
FUTCROSS | Claves de acceso.

Los PIN vivian en la configuracion del servidor, asi que cambiarlos dependia
de quien administra el despliegue: cada vez que salia un entrenador habia que
escribirle. Ahora se guardan en la tabla `config` y se cambian desde el panel.

Nunca se guarda el PIN en texto plano. Se guarda un hash pbkdf2 con sal
aleatoria, en el formato:

    pbkdf2$<iteraciones>$<sal en hex>$<hash en hex>

Asi, aunque alguien vea la tabla, no puede leer la clave. Y como la sal es
distinta en cada guardado, dos personas con el mismo PIN tienen hashes
distintos: no se puede deducir que comparten clave.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

ALGORITMO = "sha256"
ITERACIONES = 240_000     # ~0.1 s por verificacion en un servidor modesto
BYTES_SAL = 16
LARGO_MINIMO = 4


def hashear_pin(pin: str, iteraciones: int = ITERACIONES) -> str:
    """Convierte el PIN en la cadena que se guarda en la base."""
    pin = (pin or "").strip()
    if len(pin) < LARGO_MINIMO:
        raise ValueError(f"El PIN debe tener al menos {LARGO_MINIMO} caracteres.")

    sal = secrets.token_bytes(BYTES_SAL)
    hash_ = hashlib.pbkdf2_hmac(ALGORITMO, pin.encode("utf-8"), sal, iteraciones)
    return f"pbkdf2${iteraciones}${sal.hex()}${hash_.hex()}"


def verificar_pin(pin: str, guardado: str | None) -> bool:
    """Compara el PIN escrito contra lo que hay en la base.

    Devuelve False ante cualquier problema (cadena vacia, formato raro,
    numeros invalidos) en vez de lanzar excepcion: esto corre en la
    pantalla de ingreso y un error ahi dejaria a todos afuera.
    """
    if not pin or not guardado:
        return False

    partes = str(guardado).split("$")
    if len(partes) != 4 or partes[0] != "pbkdf2":
        return False

    try:
        iteraciones = int(partes[1])
        sal = bytes.fromhex(partes[2])
        esperado = bytes.fromhex(partes[3])
    except (ValueError, TypeError):
        return False

    if iteraciones < 1 or not sal or not esperado:
        return False

    calculado = hashlib.pbkdf2_hmac(ALGORITMO, str(pin).encode("utf-8"),
                                    sal, iteraciones)
    # compare_digest tarda lo mismo acierte o falle: el tiempo de respuesta
    # no delata cuantos caracteres del PIN eran correctos.
    return hmac.compare_digest(calculado, esperado)


def es_hash(valor: str | None) -> bool:
    """True si el valor ya esta hasheado. Sirve para distinguir lo que viene
    de la base de un PIN suelto en los secretos del servidor."""
    return bool(valor) and str(valor).startswith("pbkdf2$")


def validar_pin_nuevo(pin: str, confirmacion: str) -> str | None:
    """Revisa un PIN antes de guardarlo. Devuelve el mensaje de error, o None.

    No se piden mayusculas ni simbolos: esto se teclea a las 6:45 de la
    manana con una tablet en la mano. Se pide que no sea trivial y que
    este escrito dos veces igual.
    """
    pin = (pin or "").strip()
    if len(pin) < LARGO_MINIMO:
        return f"El PIN debe tener al menos {LARGO_MINIMO} caracteres."
    if pin != (confirmacion or "").strip():
        return "Los dos PIN no coinciden."
    if pin.lower() in {"1234", "0000", "1111", "12345", "123456",
                       "futcross", "admin", "clave", "password"}:
        return "Ese PIN es demasiado facil de adivinar. Elige otro."
    if len(set(pin)) == 1:
        return "El PIN no puede ser el mismo caracter repetido."
    return None
