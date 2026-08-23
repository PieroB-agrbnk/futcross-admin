"""
FUTCROSS | Carga masiva desde Excel.

Modulo puro: no toca Supabase ni Streamlit, solo valida y normaliza. Asi
se puede probar con `python test_importar.py` sin levantar nada.

La idea es que NUNCA se escriba una fila con problemas. Se revisa el
archivo entero, se muestra que esta bien y que no, y recien ahi se
importa. Una carga a medias en la base es mucho peor que cargar veinte
alumnos a mano.
"""

from __future__ import annotations

from datetime import date, datetime

import logic

# Las columnas del archivo. Las tres primeras son obligatorias; el resto
# se puede dejar en blanco y el sistema completa con lo que sabe.
COLUMNAS = [
    "nombres", "apellidos", "dni", "telefono", "grupo", "dias_asiste",
    "plan", "fecha_inicio", "precio_lista", "precio_cobrado",
    "monto_entregado", "vendedor",
]

OBLIGATORIAS = ["nombres", "apellidos", "plan"]

EJEMPLO = [
    {
        "nombres": "David", "apellidos": "Gavilan", "dni": "45678912",
        "telefono": "987654321", "grupo": "SURQUILLO", "dias_asiste": "LUN MIE VIE",
        "plan": "PLAN PREMIUM 1 MES", "fecha_inicio": "11/08/2026",
        "precio_lista": "240", "precio_cobrado": "229",
        "monto_entregado": "229", "vendedor": "EDDIMAR",
    },
    {
        "nombres": "Ana", "apellidos": "Rojas", "dni": "41112233",
        "telefono": "912345678", "grupo": "MIRAFLORES", "dias_asiste": "MAR JUE",
        "plan": "PLAN BASICO 1 MES", "fecha_inicio": "17/08/2026",
        "precio_lista": "200", "precio_cobrado": "200",
        "monto_entregado": "100", "vendedor": "GARY",
    },
]


def plantilla_csv() -> str:
    """El archivo que se descarga para llenar.

    Punto y coma, que es lo que abre bien el Excel de la oficina.
    """
    lineas = [";".join(COLUMNAS)]
    for fila in EJEMPLO:
        lineas.append(";".join(str(fila.get(c, "")) for c in COLUMNAS))
    return "\n".join(lineas) + "\n"


def _texto(valor) -> str:
    if valor is None:
        return ""
    s = str(valor).strip()
    return "" if s.lower() in ("nan", "nat", "none") else s


def _numero(valor) -> float | None:
    s = _texto(valor).replace("S/", "").replace(" ", "")
    if not s:
        return None
    # Un Excel peruano escribe 1.234,50; uno en ingles, 1,234.50
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") \
            else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def leer_fecha(valor) -> date | None:
    """Acepta lo que salga de Excel: texto en varios formatos o fecha real."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = _texto(valor)
    if not s:
        return None
    if " " in s:
        s = s.split(" ")[0]
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, formato).date()
        except ValueError:
            continue
    return None


def _normalizar(texto: str) -> str:
    return logic.normalizar(texto).replace(".", "").replace("-", " ")


def buscar_grupo(nombre: str, grupos: list[dict]) -> dict | None:
    """Encuentra el grupo por nombre completo o solo por sede.

    En el archivo la gente va a escribir "SURQUILLO", no
    "SURQUILLO 6:45 AM", asi que se busca por las dos.
    """
    objetivo = _normalizar(nombre)
    if not objetivo:
        return None
    for g in grupos:
        if _normalizar(g.get("nombre", "")) == objetivo:
            return g
    coincidencias = [g for g in grupos if _normalizar(g.get("sede", "")) == objetivo]
    if len(coincidencias) == 1:
        return coincidencias[0]
    for g in grupos:
        if objetivo in _normalizar(g.get("nombre", "")):
            return g
    return None


def buscar_plan(nombre: str, planes: list[dict]) -> dict | None:
    objetivo = _normalizar(nombre)
    if not objetivo:
        return None
    for p in planes:
        if _normalizar(p.get("nombre", "")) == objetivo:
            return p
    parciales = [p for p in planes if objetivo in _normalizar(p.get("nombre", ""))]
    return parciales[0] if len(parciales) == 1 else None


def validar(filas: list[dict], grupos: list[dict], planes: list[dict],
            dnis_existentes: dict | None = None) -> list[dict]:
    """Revisa cada fila y devuelve el resultado listo para mostrar.

    Cada elemento trae los datos ya normalizados mas `_problemas` (lista
    de textos) y `_accion`: NUEVO, EXISTENTE o ERROR.
    """
    dnis_existentes = dnis_existentes or {}
    vistos: dict = {}
    salida = []

    for numero, cruda in enumerate(filas, start=2):   # fila 1 = cabecera
        fila = {c: _texto(cruda.get(c)) for c in COLUMNAS}
        problemas: list[str] = []

        for campo in OBLIGATORIAS:
            if not fila[campo]:
                problemas.append(f"falta {campo}")

        # DNI
        dni = logic.solo_digitos(fila["dni"])
        if dni and len(dni) not in (8, 9):
            problemas.append(f"el DNI '{fila['dni']}' no tiene 8 digitos")
        if dni and dni in vistos:
            problemas.append(f"el DNI se repite con la fila {vistos[dni]}")
        elif dni:
            vistos[dni] = numero
        fila["dni"] = dni or None

        telefono = logic.solo_digitos(fila["telefono"])
        fila["telefono"] = telefono or None

        # Grupo y dias
        g = buscar_grupo(fila["grupo"], grupos) if fila["grupo"] else None
        if fila["grupo"] and not g:
            problemas.append(f"no existe el grupo '{fila['grupo']}'")
        fila["_grupo"] = g
        disponibles = str(g.get("dias", "")).split() if g else []

        if fila["dias_asiste"]:
            pedidos = [d.strip().upper()[:3] for d in
                       fila["dias_asiste"].replace(",", " ").split() if d.strip()]
            invalidos = [d for d in pedidos if d not in logic.INDICE_DIA]
            fuera = [d for d in pedidos if d in logic.INDICE_DIA
                     and disponibles and d not in disponibles]
            if invalidos:
                problemas.append(f"dias que no existen: {' '.join(invalidos)}")
            if fuera:
                problemas.append(
                    f"su grupo no entrena {' '.join(fuera)} "
                    f"(solo {' '.join(disponibles)})")
            dias = [d for d in pedidos if d in logic.INDICE_DIA and d not in fuera]
        else:
            dias = disponibles

        orden = {d: i for i, d in enumerate(
            ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"])}
        fila["dias_asiste"] = " ".join(sorted(set(dias), key=lambda d: orden[d]))
        if not fila["dias_asiste"]:
            problemas.append("sin dias de entrenamiento: pon el grupo o los dias")

        # Plan
        pl = buscar_plan(fila["plan"], planes) if fila["plan"] else None
        if fila["plan"] and not pl:
            problemas.append(f"no existe el plan '{fila['plan']}'")
        fila["_plan"] = pl

        # Fechas y montos
        inicio = leer_fecha(cruda.get("fecha_inicio"))
        if fila["plan"] and not inicio:
            problemas.append("la fecha de inicio esta vacia o no se entiende "
                             "(usa 11/08/2026)")
        fila["_inicio"] = inicio

        lista = _numero(cruda.get("precio_lista"))
        cobrado = _numero(cruda.get("precio_cobrado"))
        entregado = _numero(cruda.get("monto_entregado"))

        if lista is None and pl:
            lista = float(pl.get("precio") or 0)
        if cobrado is None:
            cobrado = lista
        if entregado is None:
            entregado = cobrado
        if cobrado is not None and entregado is not None and entregado > cobrado:
            problemas.append("entrego mas de lo que se le cobro")
        fila["_lista"] = lista
        fila["_cobrado"] = cobrado
        fila["_entregado"] = entregado

        fila["vendedor"] = fila["vendedor"].upper() or None

        # Fin y estado
        if inicio and pl and fila["dias_asiste"]:
            fila["_fin"] = logic.fecha_fin_por_calendario(
                inicio, int(pl["sesiones"]), fila["dias_asiste"],
                int(pl.get("vigencia_dias") or 30))
        else:
            fila["_fin"] = None

        existente = dnis_existentes.get(dni) if dni else None
        fila["_alumno_existente"] = existente

        fila["_fila"] = numero
        fila["_problemas"] = problemas
        fila["_accion"] = ("ERROR" if problemas
                           else "EXISTENTE" if existente else "NUEVO")
        salida.append(fila)

    return salida


def resumen(validadas: list[dict]) -> dict:
    return {
        "total": len(validadas),
        "nuevos": sum(1 for f in validadas if f["_accion"] == "NUEVO"),
        "existentes": sum(1 for f in validadas if f["_accion"] == "EXISTENTE"),
        "errores": sum(1 for f in validadas if f["_accion"] == "ERROR"),
    }


def para_mostrar(validadas: list[dict]) -> list[dict]:
    """Version legible del resultado, para la tabla de vista previa."""
    filas = []
    for f in validadas:
        filas.append({
            "Fila": f["_fila"],
            "Estado": {"NUEVO": "Listo", "EXISTENTE": "Ya existe, se le agrega el plan",
                       "ERROR": "Revisar"}[f["_accion"]],
            "Alumno": f"{f['nombres']} {f['apellidos']}".strip(),
            "DNI": f["dni"] or "",
            "Grupo": (f["_grupo"] or {}).get("nombre", "") if f["_grupo"] else "",
            "Dias": f["dias_asiste"],
            "Plan": (f["_plan"] or {}).get("nombre", "") if f["_plan"] else "",
            "Inicio": f["_inicio"].strftime("%d/%m/%Y") if f["_inicio"] else "",
            "Ultima sesion": f["_fin"].strftime("%d/%m/%Y") if f["_fin"] else "",
            "Cobrado": f["_cobrado"],
            "Entregado": f["_entregado"],
            "Problema": "; ".join(f["_problemas"]),
        })
    return filas
