"""
FUTCROSS | Identidad visual del panel de administracion.

Este panel NO lo ve el alumno. El alumno usa el kiosco (la app instalable de la
tablet). Aca entra solo quien administra: recepcion y direccion. Por eso el tono
es de herramienta de trabajo, no de vitrina.

Paleta
  naranja  #F26A1B  marca
  brasa    #FF9147  hover y acentos
  carbon   #0E0F11  barra lateral y tarjetas oscuras
  grafito  #1A1D22  superficies dentro de lo oscuro
  cal      #F4F4F0  texto sobre oscuro
  humo     #8A9099  texto secundario
  verde / ambar / rojo  estados

Tipografia
  Barlow Condensed  numeros, titulos y navegacion
  Inter             texto, formularios y tablas
"""

import streamlit as st

NARANJA = "#F26A1B"
BRASA = "#FF9147"
CARBON = "#0E0F11"
GRAFITO = "#1A1D22"
BORDE = "#E4E4E1"
CAL = "#F4F4F0"
HUMO = "#8A9099"
TINTA = "#14161A"
VERDE = "#16A34A"
AMBAR = "#D97706"
ROJO = "#DC2626"
AZUL = "#0EA5E9"

COLOR_ESTADO = {
    "ACTIVO": VERDE,
    "CONGELADO": AZUL,
    "VENCIDO": ROJO,
    "AGOTADO": AMBAR,
    "CANCELADO": "#6B7280",
    "SIN PAQUETE": "#6B7280",
}

TONOS = {"naranja": NARANJA, "verde": VERDE, "ambar": AMBAR, "rojo": ROJO, "neutro": TINTA}


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

/* ---------------------------------------------------------------- base */
html, body, [class*="css"], .stMarkdown, input, textarea, select, button {{
    font-family: 'Inter', system-ui, sans-serif;
}}
h1, h2, h3, h4 {{
    font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif !important;
    letter-spacing: .02em;
    text-transform: uppercase;
    font-weight: 700 !important;
}}
.stApp {{ background: #FAFAF8; }}
.block-container {{ padding-top: 2.2rem; max-width: 1250px; }}

/* Sin el boton Deploy ni el pie: esto es una herramienta interna */
.stAppDeployButton, [data-testid="stDecoration"] {{ display: none !important; }}
footer {{ visibility: hidden; }}

/* ------------------------------------------------------- barra lateral */
section[data-testid="stSidebar"] {{
    background: {CARBON};
    border-right: 1px solid #000;
}}
section[data-testid="stSidebar"] * {{ color: {CAL}; }}
section[data-testid="stSidebar"] .stRadio label p {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 1.05rem;
    letter-spacing: .06em;
    text-transform: uppercase;
    color: #C7CBD1;
}}
section[data-testid="stSidebar"] .stRadio label:hover p {{ color: {BRASA}; }}
section[data-testid="stSidebar"] [data-baseweb="radio"] div:first-child {{
    background: transparent !important;
    border-color: #3A3F47 !important;
}}
section[data-testid="stSidebar"] hr {{ border-color: #2A2E35; }}
.menu-grupo {{
    font-size: .62rem; letter-spacing: .22em; text-transform: uppercase;
    color: #5F656D; margin: 1.1rem 0 .3rem;
}}

/* Navegacion: botones que se ven como items de menu */
section[data-testid="stSidebar"] .stButton > button {{
    background: transparent; border: 1px solid transparent; color: #C7CBD1;
    justify-content: flex-start; padding: .32rem .7rem; min-height: 2.1rem;
    border-radius: 3px; box-shadow: none;
}}
section[data-testid="stSidebar"] .stButton > button p {{
    font-family: 'Barlow Condensed', sans-serif; font-size: 1.05rem;
    letter-spacing: .07em; text-transform: uppercase; font-weight: 600;
    margin: 0; text-align: left;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{
    background: {GRAFITO}; border-color: {GRAFITO}; color: {BRASA};
}}
section[data-testid="stSidebar"] .stButton > button:hover p {{ color: {BRASA}; }}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
    background: {GRAFITO}; border-color: {GRAFITO};
    border-left: 3px solid {NARANJA};
}}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] p {{ color: {NARANJA}; }}

/* --------------------------------------------------------- marca */
.marca {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700; line-height: .9; letter-spacing: .04em;
}}
.marca span {{ color: {NARANJA}; }}

/* ------------------------------------------------- cabecera de pantalla */
.encabezado {{
    display: flex; align-items: flex-end; justify-content: space-between;
    gap: 1rem; padding-bottom: .7rem; margin-bottom: 1.6rem;
    border-bottom: 2px solid {TINTA};
}}
.encabezado .ojo {{
    font-size: .62rem; letter-spacing: .22em; text-transform: uppercase;
    color: {NARANJA}; font-weight: 600;
}}
.encabezado h1 {{
    font-size: 2.3rem; line-height: 1; margin: .15rem 0 0; color: {TINTA};
}}
.encabezado .fecha {{
    font-family: 'Barlow Condensed', sans-serif; font-size: 1rem;
    letter-spacing: .08em; text-transform: uppercase; color: {HUMO};
    white-space: nowrap; padding-bottom: .25rem;
}}

/* ------------------------------------------------------------- tarjetas */
.kpis {{ display: flex; gap: .75rem; flex-wrap: wrap; margin-bottom: .5rem; }}
.kpi {{
    flex: 1 1 0; min-width: 130px; background: #fff;
    border: 1px solid {BORDE}; border-top: 3px solid {TINTA};
    border-radius: 4px; padding: .85rem 1rem 1rem;
}}
.kpi .etq {{
    font-size: .6rem; letter-spacing: .16em; text-transform: uppercase;
    color: {HUMO}; font-weight: 600;
}}
.kpi .val {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 2.6rem; line-height: 1; color: {TINTA}; margin-top: .2rem;
}}
.kpi .nota {{ font-size: .72rem; color: {HUMO}; margin-top: .15rem; }}

/* --------------------------------------------------------------- chips */
.chip {{
    display: inline-block; padding: 2px 9px; border-radius: 999px;
    font-size: .62rem; font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; color: #fff;
}}

/* --------------------------------------------------- filas de atencion */
.fila {{
    display: flex; align-items: center; gap: .9rem;
    background: #fff; border: 1px solid {BORDE}; border-left: 4px solid {HUMO};
    border-radius: 4px; padding: .7rem 1rem; margin-bottom: .45rem;
}}
.fila .nom {{ font-weight: 600; color: {TINTA}; }}
.fila .mot {{ font-size: .78rem; color: {HUMO}; }}
.fila .der {{ margin-left: auto; text-align: right; }}

/* ------------------------------------------------------ estados vacios */
.vacio {{
    border: 1px dashed #CFCFCA; border-radius: 6px; background: #fff;
    padding: 2.2rem 1.5rem; text-align: center;
}}
.vacio h3 {{ color: {TINTA}; font-size: 1.4rem; margin: 0 0 .3rem; }}
.vacio p {{ color: {HUMO}; margin: 0; font-size: .9rem; }}

/* ---------------------------------------------- tarjeta de resultado */
.resultado {{
    background: {CARBON}; border-radius: 6px; padding: 1.6rem 1.8rem;
    border-top: 4px solid {NARANJA}; color: {CAL};
}}
.resultado.ok {{ border-top-color: {VERDE}; }}
.resultado.no {{ border-top-color: {ROJO}; }}
.resultado .cod {{
    font-size: .62rem; letter-spacing: .2em; text-transform: uppercase; color: {HUMO};
}}
.resultado h2 {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 2.4rem; line-height: 1.03; text-transform: uppercase;
    margin: .1rem 0 0; color: {CAL};
}}
.resultado .vered {{
    font-family: 'Barlow Condensed', sans-serif; font-size: 1.5rem;
    text-transform: uppercase; letter-spacing: .04em; margin: .9rem 0 .1rem;
}}
.resultado .vered.ok {{ color: #4ADE80; }}
.resultado .vered.no {{ color: #FF7A7A; }}
.resultado .det {{ font-size: .95rem; color: #C4C9CF; }}

/* ------------------------------- el marcador: una marca por sesion */
.marcador {{ display: flex; align-items: flex-end; gap: 1rem; margin: 1.1rem 0 .4rem; }}
.marcador .num {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 4.2rem; line-height: .78; color: {NARANJA};
}}
.marcador .de {{ font-family: 'Barlow Condensed', sans-serif; font-size: 1.4rem; color: #6B7280; padding-bottom: .3rem; }}
.marcador .etq {{ font-size: .6rem; letter-spacing: .2em; color: {HUMO}; text-transform: uppercase; padding-bottom: .5rem; }}
.marcas {{ display: flex; gap: 4px; margin-top: .35rem; }}
.mk {{ height: 9px; flex: 1 1 0; border-radius: 2px; background: {GRAFITO}; border: 1px solid #2A2E35; }}
.mk.usada {{ background: {NARANJA}; border-color: {NARANJA}; }}
.mk.nueva {{ background: {CAL}; border-color: {CAL}; }}

/* ------------------------------------------------------------ botones */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
    border-radius: 4px; font-weight: 600; letter-spacing: .02em;
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
    background: {NARANJA}; border-color: {NARANJA}; color: #fff;
}}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
    background: {BRASA}; border-color: {BRASA}; color: #fff;
}}

/* -------------------------------------------------------------- tablas */
[data-testid="stDataFrame"] {{ border: 1px solid {BORDE}; border-radius: 4px; }}

/* ------------------------------------------------ pantalla de ingreso */
.acceso-fondo section[data-testid="stSidebar"] {{ display: none; }}
.acceso {{
    max-width: 380px; margin: 4vh auto 1.2rem; text-align: center;
}}
.acceso .logo {{ font-size: 3.4rem; }}
.acceso .bajada {{
    font-size: .62rem; letter-spacing: .24em; text-transform: uppercase;
    color: {HUMO}; margin-top: .35rem;
}}
.acceso .aviso {{
    margin-top: 1.6rem; padding: .8rem 1rem; border-left: 3px solid {NARANJA};
    background: #fff; border-radius: 3px; text-align: left;
    font-size: .82rem; color: #4B5158;
}}
</style>
"""

CSS_OCULTAR_MENU = """
<style>
section[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { max-width: 460px; }
</style>
"""


def aplicar_estilos() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def ocultar_navegacion() -> None:
    """Se usa en la pantalla de ingreso: sin PIN no se ve ni el menu."""
    st.markdown(CSS_OCULTAR_MENU, unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Piezas de pantalla
# ---------------------------------------------------------------------
def logo(tamano: str = "1.7rem", oscuro: bool = False) -> str:
    color = CAL if oscuro else TINTA
    return (
        f'<div class="marca" style="font-size:{tamano};color:{color}">'
        f'FUT<span>CROSS</span></div>'
    )


def cabecera(titulo: str, fecha_txt: str, ojo: str = "Panel de administracion") -> None:
    st.markdown(
        f"""<div class="encabezado">
              <div>
                <div class="ojo">{ojo}</div>
                <h1>{titulo}</h1>
              </div>
              <div class="fecha">{fecha_txt}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def kpis(items: list[tuple]) -> None:
    """items: lista de (etiqueta, valor, nota, tono). Nota y tono son opcionales."""
    tarjetas = []
    for it in items:
        etiqueta, valor = it[0], it[1]
        nota = it[2] if len(it) > 2 else ""
        tono = TONOS.get(it[3] if len(it) > 3 else "neutro", TINTA)
        tarjetas.append(
            f'<div class="kpi" style="border-top-color:{tono}">'
            f'<div class="etq">{etiqueta}</div>'
            f'<div class="val">{valor}</div>'
            f'<div class="nota">{nota}</div></div>'
        )
    st.markdown(f'<div class="kpis">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def chip(texto: str) -> str:
    color = COLOR_ESTADO.get(texto, "#6B7280")
    return f'<span class="chip" style="background:{color}">{texto}</span>'


def fila(nombre: str, detalle: str, color: str, derecha: str = "") -> None:
    st.markdown(
        f'<div class="fila" style="border-left-color:{color}">'
        f'<div><div class="nom">{nombre}</div><div class="mot">{detalle}</div></div>'
        f'<div class="der">{derecha}</div></div>',
        unsafe_allow_html=True,
    )


def vacio(titulo: str, mensaje: str) -> None:
    st.markdown(
        f'<div class="vacio"><h3>{titulo}</h3><p>{mensaje}</p></div>',
        unsafe_allow_html=True,
    )


def marcador_html(usadas: int, totales: int, marcar_hoy: bool = False) -> str:
    marcas = []
    for i in range(totales):
        if marcar_hoy and i == usadas - 1:
            clase = "mk nueva"
        elif i < usadas:
            clase = "mk usada"
        else:
            clase = "mk"
        marcas.append(f'<div class="{clase}"></div>')
    restantes = max(0, totales - usadas)
    return (
        f'<div class="marcador">'
        f'<div class="num">{restantes:02d}</div>'
        f'<div class="de">/ {totales}</div>'
        f'<div class="etq">sesiones<br>restantes</div></div>'
        f'<div class="marcas">{"".join(marcas)}</div>'
    )


def tarjeta_resultado(nombre: str, codigo: str, veredicto: str, mensaje: str,
                      autorizado: bool, usadas: int | None = None,
                      totales: int | None = None, vence: str | None = None) -> str:
    clase = "ok" if autorizado else "no"
    partes = [
        f'<div class="resultado {clase}">',
        f'<div class="cod">{codigo}</div>',
        f'<h2>{nombre}</h2>',
        f'<div class="vered {clase}">{veredicto}</div>',
        f'<div class="det">{mensaje}</div>',
    ]
    if usadas is not None and totales:
        partes.append(marcador_html(usadas, totales, marcar_hoy=autorizado))
    if vence:
        partes.append(f'<div class="cod" style="margin-top:.9rem">Vence el {vence}</div>')
    partes.append("</div>")
    return "".join(partes)


def pantalla_acceso() -> None:
    """Marca y explicacion de la pantalla de ingreso."""
    st.markdown(
        f"""<div class="acceso">
              {logo("3.4rem")}
              <div class="bajada">Panel de administracion</div>
            </div>""",
        unsafe_allow_html=True,
    )


def aviso_kiosco() -> None:
    st.markdown(
        '<div class="acceso"><div class="aviso">'
        "<b>¿Eres alumno?</b> Esta no es tu pantalla. Para marcar tu asistencia "
        "usa la tablet de la cancha."
        "</div></div>",
        unsafe_allow_html=True,
    )
