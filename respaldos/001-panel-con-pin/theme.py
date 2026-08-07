"""
FUTCROSS | Identidad visual.

Paleta:
  naranja  #F07412  color de marca
  brasa    #FF9147  hover / acentos suaves
  carbon   #101215  fondo de tarjetas oscuras
  cal      #F4F4F0  blanco de las lineas de cancha
  verde    #16A34A  paso libre
  ambar    #D97706  por renovar
  rojo     #DC2626  bloqueado

Tipografia:
  Barlow Condensed  -> numeros y titulos (aire de camiseta / marcador de cancha)
  Inter             -> texto y formularios

Elemento firma: el MARCADOR de sesiones. Doce marcas, una por sesion,
que se van tachando. Es lo que el alumno ve cuando marca su asistencia
y responde de un vistazo la unica pregunta que importa: cuantas me quedan.
"""

import streamlit as st

NARANJA = "#F07412"
BRASA = "#FF9147"
CARBON = "#101215"
GRAFITO = "#1C1F24"
CAL = "#F4F4F0"
VERDE = "#16A34A"
AMBAR = "#D97706"
ROJO = "#DC2626"

COLOR_ESTADO = {
    "ACTIVO": VERDE,
    "CONGELADO": "#0EA5E9",
    "VENCIDO": ROJO,
    "AGOTADO": AMBAR,
    "CANCELADO": "#6B7280",
    "SIN PAQUETE": "#6B7280",
}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"], .stMarkdown, .stTextInput input, .stSelectbox {{
    font-family: 'Inter', system-ui, sans-serif;
}}
h1, h2, h3, h4 {{
    font-family: 'Barlow Condensed', 'Inter', sans-serif !important;
    letter-spacing: .02em;
    text-transform: uppercase;
    font-weight: 700 !important;
}}

/* Cabecera de marca */
.fc-header {{
    display: flex; align-items: center; gap: 14px;
    background: {CARBON};
    border-left: 6px solid {NARANJA};
    padding: 16px 22px; border-radius: 4px; margin-bottom: 22px;
}}
.fc-logo {{
    font-family: 'Barlow Condensed', sans-serif; font-size: 30px; font-weight: 700;
    color: {CAL}; letter-spacing: .06em; line-height: 1;
}}
.fc-logo span {{ color: {NARANJA}; }}
.fc-sub {{
    font-size: 12px; color: #9AA0A6; letter-spacing: .18em;
    text-transform: uppercase; margin-top: 3px;
}}
.fc-fecha {{
    margin-left: auto; text-align: right; color: {CAL};
    font-family: 'Barlow Condensed', sans-serif; font-size: 20px; letter-spacing: .04em;
}}

/* Tarjeta del kiosco */
.fc-card {{
    background: {CARBON}; border-radius: 6px; padding: 26px 30px;
    border-top: 5px solid {NARANJA}; color: {CAL};
}}
.fc-card.ok  {{ border-top-color: {VERDE}; }}
.fc-card.no  {{ border-top-color: {ROJO}; }}
.fc-nombre {{
    font-family: 'Barlow Condensed', sans-serif; font-size: 40px; font-weight: 700;
    line-height: 1.05; text-transform: uppercase; margin: 0;
}}
.fc-meta {{ font-size: 13px; color: #9AA0A6; letter-spacing: .1em; text-transform: uppercase; }}
.fc-veredicto {{
    font-family: 'Barlow Condensed', sans-serif; font-size: 26px;
    text-transform: uppercase; letter-spacing: .04em; margin: 14px 0 4px;
}}
.fc-veredicto.ok {{ color: {VERDE}; }}
.fc-veredicto.no {{ color: #FF6B6B; }}
.fc-detalle {{ font-size: 15px; color: #C9CDD2; }}

/* Elemento firma: marcador de sesiones */
.fc-marcador {{ display: flex; align-items: flex-end; gap: 16px; margin: 18px 0 10px; }}
.fc-numero {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 76px; line-height: .8; color: {NARANJA};
}}
.fc-de {{
    font-family: 'Barlow Condensed', sans-serif; font-size: 26px;
    color: #6B7280; padding-bottom: 6px;
}}
.fc-etiqueta {{
    font-size: 11px; letter-spacing: .22em; color: #9AA0A6;
    text-transform: uppercase; padding-bottom: 10px;
}}
.fc-marcas {{ display: flex; gap: 5px; flex-wrap: wrap; margin-top: 6px; }}
.fc-marca {{
    width: 26px; height: 9px; border-radius: 2px; background: {GRAFITO};
    border: 1px solid #2A2E35;
}}
.fc-marca.usada {{ background: {NARANJA}; border-color: {NARANJA}; }}
.fc-marca.hoy   {{ background: {CAL}; border-color: {CAL}; }}

/* Chips de estado */
.fc-chip {{
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 600; letter-spacing: .1em;
    text-transform: uppercase; color: #fff;
}}

/* Fila de alerta en renovaciones */
.fc-fila {{
    display: flex; align-items: center; gap: 12px; padding: 10px 14px;
    border-left: 4px solid #ddd; background: #fff; border-radius: 4px; margin-bottom: 7px;
    border-top: 1px solid #EEE; border-right: 1px solid #EEE; border-bottom: 1px solid #EEE;
}}
.fc-fila .nom {{ font-weight: 600; }}
.fc-fila .mot {{ color: #6B7280; font-size: 13px; }}

/* Botones */
.stButton > button {{
    border-radius: 4px; font-weight: 600; letter-spacing: .02em;
}}
.stButton > button[kind="primary"] {{
    background: {NARANJA}; border-color: {NARANJA};
}}
.stButton > button[kind="primary"]:hover {{
    background: {BRASA}; border-color: {BRASA};
}}

/* KPIs */
[data-testid="stMetricValue"] {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
}}

@media (prefers-reduced-motion: reduce) {{
  * {{ animation: none !important; transition: none !important; }}
}}
</style>
"""


def aplicar_estilos() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def cabecera(titulo: str, fecha_txt: str) -> None:
    st.markdown(
        f"""<div class="fc-header">
              <div>
                <div class="fc-logo">FUT<span>CROSS</span></div>
                <div class="fc-sub">{titulo}</div>
              </div>
              <div class="fc-fecha">{fecha_txt}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def chip(texto: str) -> str:
    color = COLOR_ESTADO.get(texto, "#6B7280")
    return f'<span class="fc-chip" style="background:{color}">{texto}</span>'


def marcador_html(usadas: int, totales: int, marcar_hoy: bool = False) -> str:
    """Las 12 marcas del paquete. La blanca es la sesion que se acaba de usar."""
    marcas = []
    for i in range(totales):
        if marcar_hoy and i == usadas - 1:
            clase = "fc-marca hoy"
        elif i < usadas:
            clase = "fc-marca usada"
        else:
            clase = "fc-marca"
        marcas.append(f'<div class="{clase}"></div>')
    restantes = max(0, totales - usadas)
    return f"""
    <div class="fc-marcador">
      <div class="fc-numero">{restantes:02d}</div>
      <div class="fc-de">/ {totales}</div>
      <div class="fc-etiqueta">sesiones<br>restantes</div>
    </div>
    <div class="fc-marcas">{''.join(marcas)}</div>
    """


def tarjeta_kiosco(nombre: str, codigo: str, veredicto: str, mensaje: str,
                   autorizado: bool, usadas: int | None = None,
                   totales: int | None = None, vence: str | None = None) -> str:
    clase = "ok" if autorizado else "no"
    bloques = [
        f'<div class="fc-card {clase}">',
        f'<div class="fc-meta">{codigo}</div>',
        f'<h2 class="fc-nombre">{nombre}</h2>',
        f'<div class="fc-veredicto {clase}">{veredicto}</div>',
        f'<div class="fc-detalle">{mensaje}</div>',
    ]
    if usadas is not None and totales:
        bloques.append(marcador_html(usadas, totales, marcar_hoy=autorizado))
    if vence:
        bloques.append(f'<div class="fc-meta" style="margin-top:14px">Vence el {vence}</div>')
    bloques.append("</div>")
    return "".join(bloques)
