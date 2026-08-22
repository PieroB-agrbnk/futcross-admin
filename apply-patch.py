"""
FUTCROSS | Patch 019 - Pagos parciales y claves administrables

Requiere la version 2.8 (la que dejo Claude Code).

1. PAGOS PARCIALES
   FutCross a veces cobra la mitad al momento y la otra mitad dentro de
   15 dias. Eso no habia donde registrarlo: marcar "Pendiente" hacia que
   los 120 que si entraron a caja no contaran en ningun reporte.

   Al vender, el selector "Estado del pago" se reemplaza por un campo
   "Monto entregado" que arranca igual al precio. Si se cobra menos,
   aparece el saldo y se pide el plazo, con 15 dias por defecto.

   En el Panel, "Pendientes de cobro" muestra el SALDO y no el precio
   total, dice cuanto ya entrego, y avisa en rojo cuando el plazo se
   paso. El boton "Cobrar" permite registrar un abono parcial, no solo
   saldar todo.

   En Reportes se separan tres cosas que antes eran una: Vendido (valor
   de los pedidos), Cobrado (lo que entro a caja de verdad) y Por cobrar
   (los saldos). Antes el KPI de cobrado sumaba el precio completo, lo
   que mentia apenas hubiera un pago parcial.

   `pagado` deja de escribirse a mano: un trigger en la base lo calcula
   desde el monto entregado, asi no puede quedar un pedido marcado como
   pagado con saldo pendiente.

2. CLAVES ADMINISTRABLES
   Los PIN vivian en la configuracion del servidor, asi que cambiarlos
   dependia de quien administra el despliegue: cada vez que salia un
   entrenador habia que pedirlo.

   Pantalla nueva "Accesos", solo para administracion. Cambia las dos
   claves escribiendo la de administracion actual. Se guardan hasheadas
   (pbkdf2 con sal aleatoria) en la tabla `config`, nunca en texto
   plano.

   El login busca primero en la base y, si no hay nada guardado, usa las
   de los secretos: la app sigue funcionando apenas se aplica el parche,
   sin configurar nada.

   Se agrega el archivo acceso.py con sus 20 pruebas (test_acceso.py).

IMPORTANTE
  Necesita que ANTES corras migracion-019.sql en Supabase. El archivo se
  genera solo al aplicar el parche, en esta misma carpeta.

Uso, parado en admin-streamlit:

    python apply-patch-019.py

Es idempotente y verifica todos los bloques antes de escribir nada.
Para revertir:  python apply-patch-019.py --revertir
"""

import shutil
import sys
from pathlib import Path

PARCHE = "019-pagos-parciales-y-claves"
CARPETA_BACKUP = Path("respaldos") / PARCHE

MARCA_APLICADO = "Monto entregado"
MARCA_ORIGINAL = "def con_alertas"


CAMBIOS_APP = [
    (
        '\nimport db          # noqa: E402\nimport logic       # noqa: E402\nimport theme       # noqa: E402\n\ntheme.aplicar_estilos()\n\n# Se muestra en la barra lateral. Sirve para saber de un vistazo si la version\n# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.8"\n\n',
        '\nimport acceso      # noqa: E402\nimport db          # noqa: E402\nimport logic       # noqa: E402\nimport theme       # noqa: E402\n\ntheme.aplicar_estilos()\n\n# Se muestra en la barra lateral. Sirve para saber de un vistazo si la version\n# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.9"\n\n',
    ),
    (
        '    "admin": ["Panel", "Marcar asistencia", "Renovaciones", "Alumnos",\n              "Paquetes", "Congelamientos", "Reportes", "Planes"],\n    "entrenador": ["Panel", "Marcar asistencia", "Alumnos", "Renovaciones"],\n',
        '    "admin": ["Panel", "Marcar asistencia", "Renovaciones", "Alumnos",\n              "Paquetes", "Congelamientos", "Reportes", "Planes", "Accesos"],\n    "entrenador": ["Panel", "Marcar asistencia", "Alumnos", "Renovaciones"],\n',
    ),
    (
        'INACTIVIDAD_MAX = 2 * 60 * 60\n\n',
        'INACTIVIDAD_MAX = 2 * 60 * 60\n\n\n# Las claves se guardan hasheadas en la tabla `config` y se cambian desde\n# la pantalla Accesos. Si todavia no hay nada guardado (recien aplicado el\n# parche), se usan las de los secretos del servidor, para que nadie quede\n# afuera. Cambiar una clave desde el panel la mueve a la base y a partir de\n# ahi manda esa.\nCLAVES_PIN = {"admin": "pin_admin", "entrenador": "pin_entrenador"}\nSECRETOS_PIN = {"admin": "ADMIN_PIN", "entrenador": "ENTRENADOR_PIN"}\n\n\ndef pin_guardado(rol_pin: str) -> str | None:\n    """Devuelve el hash de la base, o el PIN suelto de los secretos."""\n    try:\n        guardado = db.leer_config(CLAVES_PIN[rol_pin])\n    except Exception:\n        guardado = None\n    return guardado or secreto(SECRETOS_PIN[rol_pin])\n\n\ndef comparar_pin(escrito: str, guardado: str | None) -> bool:\n    """Acepta las dos formas: hash de la base o PIN plano de los secretos."""\n    if not escrito or not guardado:\n        return False\n    if acceso.es_hash(guardado):\n        return acceso.verificar_pin(escrito, guardado)\n    # compare_digest tarda lo mismo acierte o falle\n    return hmac.compare_digest(str(escrito), str(guardado))\n\n',
    ),
    (
        '    # significaba que una instalacion mal configurada quedaba abierta.\n    pin_admin = secreto("ADMIN_PIN")\n    pin_entrenador = secreto("ENTRENADOR_PIN")\n    if not pin_admin:\n',
        '    # significaba que una instalacion mal configurada quedaba abierta.\n    pin_admin = pin_guardado("admin")\n    pin_entrenador = pin_guardado("entrenador")\n    if not pin_admin:\n',
    ),
    (
        '        # los dos PIN siempre, para que tampoco se note cual acerto.\n        acierta_admin = bool(pin) and hmac.compare_digest(str(pin), str(pin_admin))\n        acierta_entrenador = (bool(pin) and bool(pin_entrenador)\n                              and hmac.compare_digest(str(pin), str(pin_entrenador)))\n\n',
        '        # los dos PIN siempre, para que tampoco se note cual acerto.\n        acierta_admin = comparar_pin(pin, pin_admin)\n        acierta_entrenador = comparar_pin(pin, pin_entrenador)\n\n',
    ),
    (
        '        if not deuda.empty:\n            total = float(deuda["precio"].fillna(0).sum())\n            theme.seccion("Pendientes de cobro",\n                          f"{len(deuda)} pedidos por S/ {total:,.2f}")\n            for _, d in deuda.head(10).iterrows():\n                pedido = logic.a_fecha(d.get("fecha_pedido") or d.get("fecha_inicio"))\n                dias = (hoy - pedido).days if pedido else None\n                antiguedad = (f"hace {dias} dias" if dias and dias > 0\n                              else "de hoy")\n                c1, c2 = st.columns([4, 1])\n                with c1:\n                    theme.fila(\n                        d["alumno"],\n                        f\'{d.get("codigo", "")} \xb7 {d.get("plan_nombre", "")} \xb7 \'\n                        f\'S/ {float(d.get("precio") or 0):,.2f} \xb7 {antiguedad}\',\n                        theme.ROJO if dias and dias > 7 else theme.AMBAR)\n                if c2.button("Marcar pagado", key=f"pago_{d[\'id\']}",\n                             width="stretch"):\n                    db.marcar_pagado(d["id"])\n                    st.toast("Pedido marcado como pagado", icon="\u2705")\n                    st.rerun()\n            if len(deuda) > 10:\n',
        '        if not deuda.empty:\n            # El saldo, no el precio: si entrego la mitad, lo que falta\n            # cobrar es la otra mitad.\n            if "saldo" in deuda.columns:\n                deuda["_saldo"] = deuda["saldo"].fillna(deuda["precio"])\n            else:\n                deuda["_saldo"] = deuda["precio"]\n            total = float(deuda["_saldo"].fillna(0).sum())\n            theme.seccion("Pendientes de cobro",\n                          f"{len(deuda)} pedidos por S/ {total:,.2f}")\n            for _, d in deuda.head(10).iterrows():\n                limite = logic.a_fecha(d.get("fecha_limite_pago"))\n                pedido = logic.a_fecha(d.get("fecha_pedido") or d.get("fecha_inicio"))\n\n                if limite:\n                    faltan = (limite - hoy).days\n                    if faltan < 0:\n                        plazo = f"vencio hace {abs(faltan)} dias"\n                        color = theme.ROJO\n                    elif faltan == 0:\n                        plazo, color = "vence hoy", theme.ROJO\n                    else:\n                        plazo, color = f"vence en {faltan} dias", theme.AMBAR\n                else:\n                    dias = (hoy - pedido).days if pedido else None\n                    plazo = (f"hace {dias} dias" if dias and dias > 0 else "de hoy")\n                    color = theme.ROJO if dias and dias > 7 else theme.AMBAR\n\n                entregado = float(d.get("monto_entregado") or 0)\n                saldo_d = float(d.get("_saldo") or 0)\n                detalle_pago = f"debe S/ {saldo_d:,.2f}"\n                if entregado > 0:\n                    detalle_pago += f" (ya entrego S/ {entregado:,.2f})"\n\n                c1, c2 = st.columns([4, 1])\n                with c1:\n                    theme.fila(\n                        d["alumno"],\n                        f\'{d.get("codigo", "")} \xb7 {d.get("plan_nombre", "")} \xb7 \'\n                        f\'{detalle_pago} \xb7 {plazo}\',\n                        color)\n                if c2.button("Cobrar", key=f"pago_{d[\'id\']}", width="stretch"):\n                    st.session_state["cobrando"] = d["id"]\n                    st.rerun()\n\n                if st.session_state.get("cobrando") == d["id"]:\n                    with st.form(f"form_cobro_{d[\'id\']}"):\n                        h1, h2 = st.columns([2, 1])\n                        abono = h1.number_input(\n                            "Monto que entrega ahora (S/)", value=float(saldo_d),\n                            min_value=0.0, max_value=float(saldo_d), step=10.0)\n                        h2.write("")\n                        if h2.form_submit_button("Registrar", type="primary",\n                                                 width="stretch"):\n                            db.registrar_abono(d["id"], abono)\n                            st.session_state.pop("cobrando", None)\n                            restante = saldo_d - abono\n                            st.toast(\n                                "Pago completo" if restante <= 0\n                                else f"Abono registrado, quedan S/ {restante:,.2f}",\n                                icon="\u2705")\n                            st.rerun()\n\n            if len(deuda) > 10:\n',
    ),
    (
        '\n                f1, f2, f3 = st.columns(3)\n                es_renovacion = bool(vigente) or bool(db.ultimo_paquete(alumno_id))\n',
        '\n                # FutCross a veces cobra la mitad ahora y la otra mitad en\n                # quince dias. Antes eso no habia donde registrarlo: marcar\n                # "Pendiente" hacia que lo que si entro a caja no contara.\n                g1, g2 = st.columns(2)\n                entregado = g1.number_input(\n                    "Monto entregado (S/)", value=float(precio),\n                    min_value=0.0, max_value=float(precio), step=10.0,\n                    help="Cuanto paga ahora. Dejalo igual al precio si paga todo.")\n                saldo = max(0.0, precio - entregado)\n                pagado = saldo <= 0\n\n                if saldo > 0:\n                    limite = g2.date_input(\n                        "Pagar el saldo hasta", value=logic.hoy() + timedelta(days=15),\n                        min_value=logic.hoy(), format="DD/MM/YYYY",\n                        help="Plazo acordado con el cliente")\n                    g2.caption(f"Queda debiendo **S/ {saldo:,.2f}**")\n                else:\n                    limite = None\n                    g2.caption("Pago completo, sin saldo pendiente.")\n\n                f1, f2 = st.columns(2)\n                es_renovacion = bool(vigente) or bool(db.ultimo_paquete(alumno_id))\n',
    ),
    (
        '                    vendedor = f2.text_input("Nombre del vendedor", key="vend_nuevo")\n                pagado = f3.selectbox("Estado del pago", ["Pagado", "Pendiente"]) == "Pagado"\n\n',
        '                    vendedor = f2.text_input("Nombre del vendedor", key="vend_nuevo")\n\n',
    ),
    (
        '                            tipo=tipo, sesiones=int(sesiones), vigencia_dias=int(vigencia),\n                            grupo_id=grupo_id, precio_lista=precio_lista)\n                        st.toast(f"Pedido {pedido} registrado", icon="\\u2705")\n                        st.success(f"Pedido N {pedido} registrado. "\n                                   f"Vence el {fin.strftime(\'%d/%m/%Y\')}.")\n                        st.rerun()\n',
        '                            tipo=tipo, sesiones=int(sesiones), vigencia_dias=int(vigencia),\n                            grupo_id=grupo_id, precio_lista=precio_lista,\n                            monto_entregado=entregado, fecha_limite_pago=limite)\n                        st.toast(f"Pedido {pedido} registrado", icon="\\u2705")\n                        aviso_pedido = (f"Pedido N {pedido} registrado. "\n                                        f"Vence el {fin.strftime(\'%d/%m/%Y\')}.")\n                        if saldo > 0:\n                            aviso_pedido += (f" Queda un saldo de S/ {saldo:,.2f} "\n                                             f"con plazo hasta el "\n                                             f"{limite.strftime(\'%d/%m/%Y\')}.")\n                        st.success(aviso_pedido)\n                        st.rerun()\n',
    ),
    (
        '                    "dias_restantes", "dias_congelados", "estado_real", "tipo",\n                    "vendedor", "pagado"]\n        # Si la migracion 006 aun no se corrio faltan columnas: avisar sin romper\n',
        '                    "dias_restantes", "dias_congelados", "estado_real", "tipo",\n                    "vendedor", "monto_entregado", "saldo", "fecha_limite_pago",\n                    "estado_pago"]\n        # Si la migracion 006 aun no se corrio faltan columnas: avisar sin romper\n',
    ),
    (
        '                         "Restantes", "Dias por vencer", "Dias congelados", "Status",\n                         "Renovacion/Nuevo", "Vendedor", "Pagado"]\n        vista["Avance"] = (vista["Usadas"] / vista["Totales"].replace(0, 1) * 100)\n        vista = vista[["N pedido", "Fecha", "Cliente", "Plan contratado",\n                       "Precio lista", "Precio cobrado", "Descuento", "Dcto %",\n                       "Metodo de pago", "Inicio del plan", "Fin del plan",\n                       "Sede y turno", "Dias que asiste", "Avance", "Restantes",\n                       "Dias por vencer", "Dias congelados", "Status",\n                       "Renovacion/Nuevo", "Vendedor", "Pagado"]]\n        for col in ("Fecha", "Inicio del plan", "Fin del plan"):\n            vista[col] = pd.to_datetime(vista[col], errors="coerce")\n',
        '                         "Restantes", "Dias por vencer", "Dias congelados", "Status",\n                         "Renovacion/Nuevo", "Vendedor", "Entregado", "Saldo",\n                         "Plazo de pago", "Estado del pago"]\n        vista["Avance"] = (vista["Usadas"] / vista["Totales"].replace(0, 1) * 100)\n        vista = vista[["N pedido", "Fecha", "Cliente", "Plan contratado",\n                       "Precio lista", "Precio cobrado", "Descuento", "Dcto %",\n                       "Metodo de pago", "Inicio del plan", "Fin del plan",\n                       "Sede y turno", "Dias que asiste", "Avance", "Restantes",\n                       "Dias por vencer", "Dias congelados", "Status",\n                       "Renovacion/Nuevo", "Vendedor", "Entregado", "Saldo",\n                       "Plazo de pago", "Estado del pago"]]\n        for col in ("Fecha", "Inicio del plan", "Fin del plan", "Plazo de pago"):\n            vista[col] = pd.to_datetime(vista[col], errors="coerce")\n',
    ),
    (
        '                    "Fin del plan", format="DD/MM/YYYY"),\n                "Pagado": st.column_config.CheckboxColumn("Pagado"),\n            })\n',
        '                    "Fin del plan", format="DD/MM/YYYY"),\n                "Entregado": st.column_config.NumberColumn(\n                    "Entregado", format="S/ %.2f"),\n                "Saldo": st.column_config.NumberColumn(\n                    "Saldo", format="S/ %.2f",\n                    help="Lo que todavia falta cobrar"),\n                "Plazo de pago": st.column_config.DateColumn(\n                    "Plazo de pago", format="DD/MM/YYYY"),\n            })\n',
    ),
    (
        '\n    theme.kpis([\n        ("Asistencias", len(asis), f"en {dias_rango} dias", "naranja"),\n        ("Alumnos distintos", asis["alumno_id"].nunique() if not asis.empty else 0,\n         "vinieron al menos una vez"),\n        ("Paquetes vendidos", len(vendidos), "en el rango elegido"),\n        ("Cobrado", f"S/ {cobrado_total:,.0f}", "lo que entro a caja", "verde"),\n        ("Descuentos", f"S/ {descuento_total:,.0f}",\n',
        '\n    # Vendido no es lo mismo que cobrado: con pagos parciales, parte de lo\n    # vendido todavia esta en la calle.\n    if not vendidos.empty and "monto_entregado" in vendidos.columns:\n        entrado = float(vendidos["monto_entregado"].fillna(0).sum())\n        por_cobrar = max(0.0, cobrado_total - entrado)\n    else:\n        entrado, por_cobrar = cobrado_total, 0.0\n\n    theme.kpis([\n        ("Asistencias", len(asis), f"en {dias_rango} dias", "naranja"),\n        ("Paquetes vendidos", len(vendidos), "en el rango elegido"),\n        ("Vendido", f"S/ {cobrado_total:,.0f}", "valor de los pedidos"),\n        ("Cobrado", f"S/ {entrado:,.0f}", "entro a caja de verdad", "verde"),\n        ("Por cobrar", f"S/ {por_cobrar:,.0f}", "saldos pendientes",\n         "rojo" if por_cobrar else "verde"),\n        ("Descuentos", f"S/ {descuento_total:,.0f}",\n',
    ),
    (
        '# =====================================================================\n# NAVEGACION\n',
        '# =====================================================================\n# 9. ACCESOS\n# =====================================================================\ndef pagina_accesos() -> None:\n    theme.cabecera("Accesos", fecha_larga(logic.hoy()).upper(), "Claves del equipo")\n    st.caption(\n        "Hay una sola direccion para todo el equipo: la clave que escriben "\n        "decide que ven. La de administracion abre las nueve pantallas; la de "\n        "entrenador solo Panel, Marcar asistencia, Alumnos y Renovaciones."\n    )\n\n    origen_admin = db.leer_config("pin_admin")\n    origen_prof = db.leer_config("pin_entrenador")\n\n    theme.seccion("Situacion actual", "")\n    c1, c2 = st.columns(2)\n    for col, etiqueta, guardado, clave in [\n        (c1, "Administracion", origen_admin, "pin_admin"),\n        (c2, "Entrenador", origen_prof, "pin_entrenador"),\n    ]:\n        with col:\n            if guardado:\n                info = db.config_actualizada(clave) or {}\n                cuando = str(info.get("actualizado_en") or "")[:10]\n                col.success(f"**{etiqueta}**: clave propia"\n                            + (f", cambiada el {cuando}" if cuando else ""))\n            else:\n                col.warning(f"**{etiqueta}**: usando la clave de los secretos "\n                            "del servidor. Cambiala aca para poder administrarla "\n                            "desde el panel.")\n\n    theme.seccion("Cambiar una clave", "hay que escribir la clave de administracion actual")\n    with st.form("form_pin", clear_on_submit=True):\n        cual = st.radio("Que clave cambio",\n                        ["Entrenador", "Administracion"], horizontal=True)\n        actual = st.text_input("Clave de administracion actual", type="password")\n        c3, c4 = st.columns(2)\n        nueva = c3.text_input("Clave nueva", type="password")\n        repetida = c4.text_input("Repite la clave nueva", type="password")\n\n        if st.form_submit_button("Guardar clave", type="primary"):\n            rol_pin = "admin" if cual == "Administracion" else "entrenador"\n\n            if not comparar_pin(actual, pin_guardado("admin")):\n                registrar_fallo()\n                st.error("La clave de administracion actual no es correcta.")\n            else:\n                problema = acceso.validar_pin_nuevo(nueva, repetida)\n                if problema:\n                    st.error(problema)\n                elif rol_pin == "entrenador" and comparar_pin(\n                        nueva, pin_guardado("admin")):\n                    st.error("La clave de entrenador no puede ser igual a la de "\n                             "administracion: le daria acceso a todo.")\n                else:\n                    try:\n                        db.guardar_config(CLAVES_PIN[rol_pin],\n                                          acceso.hashear_pin(nueva),\n                                          quien=ETIQUETA_ROL.get(rol(), ""))\n                        st.toast("Clave actualizada", icon="\\u2705")\n                        st.success(\n                            f"Clave de {cual.lower()} actualizada. "\n                            + ("Vas a tener que volver a entrar con la nueva."\n                               if rol_pin == "admin" else\n                               "Pasasela a los entrenadores; la anterior ya no sirve.")\n                        )\n                    except Exception as e:\n                        st.error(f"No se pudo guardar: {e}")\n\n    st.caption(\n        "Las claves se guardan cifradas: ni yo ni nadie con acceso a la base "\n        "puede leerlas. Si se olvida la de administracion, se recupera "\n        "borrando la fila `pin_admin` de la tabla `config` en Supabase, y "\n        "vuelve a valer la de los secretos del servidor."\n    )\n\n\n# =====================================================================\n# NAVEGACION\n',
    ),
    (
        '    "Planes": pagina_planes,\n}\n\nGRUPOS = [\n    ("Dia a dia", ["Panel", "Marcar asistencia", "Renovaciones"]),\n    ("Alumnos y pagos", ["Alumnos", "Paquetes", "Congelamientos"]),\n    ("Gestion", ["Reportes", "Planes"]),\n]\n',
        '    "Planes": pagina_planes,\n    "Accesos": pagina_accesos,\n}\n\nGRUPOS = [\n    ("Dia a dia", ["Panel", "Marcar asistencia", "Renovaciones"]),\n    ("Alumnos y pagos", ["Alumnos", "Paquetes", "Congelamientos"]),\n    ("Gestion", ["Reportes", "Planes", "Accesos"]),\n]\n',
    ),
]


CAMBIOS_DB = [
    (
        '    r = _tabla("planes").update(cambios).eq("id", plan_id).execute().data\n    invalidar_cache()\n    return r\n\n\n# ---------------------------------------------------------------------\n',
        '    r = _tabla("planes").update(cambios).eq("id", plan_id).execute().data\n    invalidar_cache()\n    return r\n\n\n# ---------------------------------------------------------------------\n# Configuracion (claves de acceso)\n#\n# Sin cache a proposito: si se cambia un PIN, tiene que valer al\n# instante en todas las pestanas abiertas.\n# ---------------------------------------------------------------------\ndef leer_config(clave: str) -> str | None:\n    try:\n        r = (_tabla("config").select("valor")\n             .eq("clave", clave).limit(1).execute().data)\n        return r[0]["valor"] if r else None\n    except Exception:\n        # La migracion 019 todavia no se corrio: se cae a los secretos\n        return None\n\n\ndef guardar_config(clave: str, valor: str, quien: str = "admin") -> None:\n    _tabla("config").upsert({\n        "clave": clave,\n        "valor": valor,\n        "actualizado_en": datetime.now(timezone.utc).isoformat(),\n        "actualizado_por": quien,\n    }, on_conflict="clave").execute()\n    invalidar_cache()\n\n\ndef config_actualizada(clave: str) -> dict | None:\n    """Cuando y quien cambio esta clave por ultima vez."""\n    try:\n        r = (_tabla("config").select("actualizado_en,actualizado_por")\n             .eq("clave", clave).limit(1).execute().data)\n        return r[0] if r else None\n    except Exception:\n        return None\n\n\n# ---------------------------------------------------------------------\n',
    ),
    (
        '                .neq("estado_real", "CANCELADO")\n                .order("fecha_pedido", desc=True).execute().data)\n    except Exception:\n        return pd.DataFrame()\n    return _df(rows)\n\n\ndef marcar_pagado(paquete_id: str):\n    r = _tabla("paquetes").update({"pagado": True}).eq("id", paquete_id).execute().data\n    invalidar_cache()\n    return r\n\n\ndef crear_paquete(alumno_id, plan: dict, fecha_inicio: date, precio: float,\n                  medio_pago: str, pagado: bool = True, observacion: str | None = None,\n                  fecha_pedido: date | None = None, sede: str | None = None,\n                  dias_asiste: str | None = None, vendedor: str | None = None,\n                  tipo: str = "NUEVO", sesiones: int | None = None,\n                  vigencia_dias: int | None = None, grupo_id: str | None = None,\n                  precio_lista: float | None = None):\n    """Registra la venta con todos los datos del pedido.\n',
        '                .neq("estado_real", "CANCELADO")\n                .order("fecha_limite_pago", desc=False).execute().data)\n    except Exception:\n        # Antes de la migracion 019 no existe fecha_limite_pago\n        try:\n            rows = (_tabla("v_paquetes").select("*")\n                    .eq("pagado", False)\n                    .neq("estado_real", "CANCELADO")\n                    .order("fecha_pedido", desc=True).execute().data)\n        except Exception:\n            return pd.DataFrame()\n    return _df(rows)\n\n\ndef registrar_abono(paquete_id: str, monto: float, total: bool = False):\n    """Anota lo que el cliente entrego.\n\n    `pagado` no se toca aca: lo calcula un trigger en la base a partir\n    del monto entregado. Asi no puede quedar un pedido marcado como\n    pagado con saldo pendiente.\n    """\n    pq = paquete(paquete_id) or {}\n    precio = float(pq.get("precio") or 0)\n    entregado = float(pq.get("monto_entregado") or 0)\n    nuevo = precio if total else min(precio, entregado + float(monto))\n\n    r = (_tabla("paquetes").update({"monto_entregado": nuevo})\n         .eq("id", paquete_id).execute().data)\n    invalidar_cache()\n    return r\n\n\ndef marcar_pagado(paquete_id: str):\n    """Salda el pedido completo. Se conserva por compatibilidad."""\n    return registrar_abono(paquete_id, 0, total=True)\n\n\ndef crear_paquete(alumno_id, plan: dict, fecha_inicio: date, precio: float,\n                  medio_pago: str, pagado: bool = True, observacion: str | None = None,\n                  fecha_pedido: date | None = None, sede: str | None = None,\n                  dias_asiste: str | None = None, vendedor: str | None = None,\n                  tipo: str = "NUEVO", sesiones: int | None = None,\n                  vigencia_dias: int | None = None, grupo_id: str | None = None,\n                  precio_lista: float | None = None,\n                  monto_entregado: float | None = None,\n                  fecha_limite_pago: date | None = None):\n    """Registra la venta con todos los datos del pedido.\n',
    ),
    (
        '        "precio": float(precio),\n        "medio_pago": medio_pago,\n',
        '        "precio": float(precio),\n        # Si no se dice cuanto entrego, se asume que pago todo o nada,\n        # como funcionaba antes de que existieran los pagos parciales.\n        "monto_entregado": float(\n            monto_entregado if monto_entregado is not None\n            else (precio if pagado else 0)),\n        "fecha_limite_pago": (fecha_limite_pago.isoformat()\n                              if fecha_limite_pago else None),\n        "medio_pago": medio_pago,\n',
    ),
]


ACCESO_PY = '"""\nFUTCROSS | Claves de acceso.\n\nLos PIN vivian en la configuracion del servidor, asi que cambiarlos dependia\nde quien administra el despliegue: cada vez que salia un entrenador habia que\nescribirle. Ahora se guardan en la tabla `config` y se cambian desde el panel.\n\nNunca se guarda el PIN en texto plano. Se guarda un hash pbkdf2 con sal\naleatoria, en el formato:\n\n    pbkdf2$<iteraciones>$<sal en hex>$<hash en hex>\n\nAsi, aunque alguien vea la tabla, no puede leer la clave. Y como la sal es\ndistinta en cada guardado, dos personas con el mismo PIN tienen hashes\ndistintos: no se puede deducir que comparten clave.\n"""\n\nfrom __future__ import annotations\n\nimport hashlib\nimport hmac\nimport secrets\n\nALGORITMO = "sha256"\nITERACIONES = 240_000     # ~0.1 s por verificacion en un servidor modesto\nBYTES_SAL = 16\nLARGO_MINIMO = 4\n\n\ndef hashear_pin(pin: str, iteraciones: int = ITERACIONES) -> str:\n    """Convierte el PIN en la cadena que se guarda en la base."""\n    pin = (pin or "").strip()\n    if len(pin) < LARGO_MINIMO:\n        raise ValueError(f"El PIN debe tener al menos {LARGO_MINIMO} caracteres.")\n\n    sal = secrets.token_bytes(BYTES_SAL)\n    hash_ = hashlib.pbkdf2_hmac(ALGORITMO, pin.encode("utf-8"), sal, iteraciones)\n    return f"pbkdf2${iteraciones}${sal.hex()}${hash_.hex()}"\n\n\ndef verificar_pin(pin: str, guardado: str | None) -> bool:\n    """Compara el PIN escrito contra lo que hay en la base.\n\n    Devuelve False ante cualquier problema (cadena vacia, formato raro,\n    numeros invalidos) en vez de lanzar excepcion: esto corre en la\n    pantalla de ingreso y un error ahi dejaria a todos afuera.\n    """\n    if not pin or not guardado:\n        return False\n\n    partes = str(guardado).split("$")\n    if len(partes) != 4 or partes[0] != "pbkdf2":\n        return False\n\n    try:\n        iteraciones = int(partes[1])\n        sal = bytes.fromhex(partes[2])\n        esperado = bytes.fromhex(partes[3])\n    except (ValueError, TypeError):\n        return False\n\n    if iteraciones < 1 or not sal or not esperado:\n        return False\n\n    calculado = hashlib.pbkdf2_hmac(ALGORITMO, str(pin).encode("utf-8"),\n                                    sal, iteraciones)\n    # compare_digest tarda lo mismo acierte o falle: el tiempo de respuesta\n    # no delata cuantos caracteres del PIN eran correctos.\n    return hmac.compare_digest(calculado, esperado)\n\n\ndef es_hash(valor: str | None) -> bool:\n    """True si el valor ya esta hasheado. Sirve para distinguir lo que viene\n    de la base de un PIN suelto en los secretos del servidor."""\n    return bool(valor) and str(valor).startswith("pbkdf2$")\n\n\ndef validar_pin_nuevo(pin: str, confirmacion: str) -> str | None:\n    """Revisa un PIN antes de guardarlo. Devuelve el mensaje de error, o None.\n\n    No se piden mayusculas ni simbolos: esto se teclea a las 6:45 de la\n    manana con una tablet en la mano. Se pide que no sea trivial y que\n    este escrito dos veces igual.\n    """\n    pin = (pin or "").strip()\n    if len(pin) < LARGO_MINIMO:\n        return f"El PIN debe tener al menos {LARGO_MINIMO} caracteres."\n    if pin != (confirmacion or "").strip():\n        return "Los dos PIN no coinciden."\n    if pin.lower() in {"1234", "0000", "1111", "12345", "123456",\n                       "futcross", "admin", "clave", "password"}:\n        return "Ese PIN es demasiado facil de adivinar. Elige otro."\n    if len(set(pin)) == 1:\n        return "El PIN no puede ser el mismo caracter repetido."\n    return None\n'


MIGRACION_SQL = '-- =====================================================================\n-- FUTCROSS | Migracion 019\n--\n-- 1. PAGOS PARCIALES\n--    Hasta ahora el pago era todo o nada. FutCross a veces cobra la\n--    mitad al momento y la otra mitad dentro de 15 dias, y eso no habia\n--    donde registrarlo: marcar "Pendiente" hacia que los 120 que si\n--    entraron a caja no contaran en ningun reporte.\n--\n-- 2. CLAVES EN LA BASE\n--    Los PIN vivian en la configuracion del servidor, asi que cambiarlos\n--    dependia de quien administra el despliegue. Ahora se guardan\n--    hasheados en la tabla `config` y se pueden cambiar desde el panel.\n--\n-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.\n-- =====================================================================\n\n-- ---------------------------------------------------------------------\n-- 1. Pagos parciales\n-- ---------------------------------------------------------------------\nalter table paquetes\n    add column if not exists monto_entregado numeric(10,2),\n    add column if not exists fecha_limite_pago date;\n\n-- Los pedidos que ya existen: si estaban pagados, se entrego todo;\n-- si estaban pendientes, no se entrego nada.\nupdate paquetes\n   set monto_entregado = case when pagado then precio else 0 end\n where monto_entregado is null;\n\nalter table paquetes alter column monto_entregado set default 0;\n\ncomment on column paquetes.monto_entregado is\n    \'Cuanto pago el cliente hasta ahora. El saldo es precio - monto_entregado.\';\ncomment on column paquetes.fecha_limite_pago is\n    \'Hasta cuando tiene plazo para completar el saldo.\';\n\n-- `pagado` pasa a ser un reflejo del monto entregado, no un dato que se\n-- escribe aparte. Con un trigger no puede quedar en "pagado" un pedido\n-- al que le falta plata, ni al reves.\ncreate or replace function fc_sincronizar_pagado()\nreturns trigger\nlanguage plpgsql as $$\nbegin\n    new.monto_entregado := coalesce(new.monto_entregado, 0);\n    new.pagado := (new.monto_entregado >= coalesce(new.precio, 0));\n    return new;\nend $$;\n\ndrop trigger if exists trg_sincronizar_pagado on paquetes;\ncreate trigger trg_sincronizar_pagado\n    before insert or update of monto_entregado, precio, pagado on paquetes\n    for each row execute function fc_sincronizar_pagado();\n\n-- Deja consistentes las filas que ya estaban\nupdate paquetes set monto_entregado = coalesce(monto_entregado, 0);\n\ncreate index if not exists ix_paquetes_por_cobrar\n    on paquetes (fecha_limite_pago) where not pagado;\n\n-- ---------------------------------------------------------------------\n-- 2. Configuracion: claves de acceso\n-- ---------------------------------------------------------------------\ncreate table if not exists config (\n    clave           text primary key,\n    valor           text not null,\n    actualizado_en  timestamptz not null default now(),\n    actualizado_por text\n);\n\ncomment on table config is\n    \'Configuracion editable desde el panel. Los PIN se guardan hasheados \'\n    \'(pbkdf2), nunca en texto plano.\';\n\n-- ---------------------------------------------------------------------\n-- 3. Vistas con saldo y estado de pago\n-- ---------------------------------------------------------------------\ndrop view if exists v_alumnos_estado cascade;\ndrop view if exists v_paquetes cascade;\n\ncreate view v_paquetes as\nwith base as (\n    select p.*,\n           coalesce((select count(*) from asistencias s\n                     where s.paquete_id = p.id and not s.anulada), 0)::int as sesiones_usadas\n    from paquetes p\n)\nselect b.id,\n       b.nro_pedido,\n       b.alumno_id,\n       a.codigo,\n       a.nombres,\n       a.apellidos,\n       (a.nombres || \' \' || a.apellidos) as alumno,\n       a.dni,\n       a.telefono,\n       b.grupo_id,\n       coalesce(g.nombre, b.sede, a.sede)      as grupo,\n       coalesce(g.sede, b.sede, a.sede)        as sede,\n       g.genero,\n       g.hora,\n       coalesce(b.dias_asiste, g.dias, a.dias_asiste) as dias_asiste,\n       a.turno,\n       a.horario,\n       b.plan_id,\n       b.plan_nombre,\n       b.sesiones_totales,\n       b.sesiones_usadas,\n       (b.sesiones_totales - b.sesiones_usadas) as sesiones_restantes,\n       b.fecha_pedido,\n       b.fecha_inicio,\n       b.fecha_fin,\n       (b.fecha_fin - hoy_lima())            as dias_restantes,\n       b.dias_congelados,\n       coalesce(b.precio_lista, b.precio)     as precio_lista,\n       b.precio,\n       (coalesce(b.precio_lista, b.precio) - b.precio) as descuento,\n       case when coalesce(b.precio_lista, 0) > 0\n            then round((coalesce(b.precio_lista, b.precio) - b.precio)\n                       / b.precio_lista * 100, 1)\n            else 0 end                        as descuento_pct,\n       coalesce(b.monto_entregado, 0)         as monto_entregado,\n       (b.precio - coalesce(b.monto_entregado, 0)) as saldo,\n       b.fecha_limite_pago,\n       case\n         when coalesce(b.monto_entregado, 0) >= b.precio then \'PAGADO\'\n         when coalesce(b.monto_entregado, 0) > 0         then \'PARCIAL\'\n         else \'PENDIENTE\'\n       end                                    as estado_pago,\n       case\n         when coalesce(b.monto_entregado, 0) >= b.precio then null\n         when b.fecha_limite_pago is null                then null\n         else (b.fecha_limite_pago - hoy_lima())\n       end                                    as dias_para_pagar,\n       b.medio_pago,\n       b.pagado,\n       b.vendedor,\n       b.tipo,\n       b.estado,\n       b.observacion,\n       b.creado_en,\n       case\n         when b.estado = \'CANCELADO\'                  then \'CANCELADO\'\n         when b.estado = \'CONGELADO\'                  then \'CONGELADO\'\n         when b.sesiones_usadas >= b.sesiones_totales then \'AGOTADO\'\n         when hoy_lima() > b.fecha_fin                then \'VENCIDO\'\n         else \'ACTIVO\'\n       end as estado_real\nfrom base b\njoin alumnos a on a.id = b.alumno_id\nleft join grupos g on g.id = b.grupo_id;\n\ncreate view v_alumnos_estado as\nselect a.id            as alumno_id,\n       a.codigo, a.nombres, a.apellidos,\n       (a.nombres || \' \' || a.apellidos) as alumno,\n       a.dni, a.telefono, a.email,\n       a.grupo_id,\n       ga.nombre       as grupo,\n       coalesce(ga.sede, a.sede)        as sede,\n       ga.genero, ga.hora,\n       coalesce(vp.dias_asiste, ga.dias, a.dias_asiste) as dias_asiste,\n       a.turno, a.horario, a.fecha_inscripcion, a.activo,\n       vp.id            as paquete_id,\n       vp.nro_pedido, vp.plan_nombre, vp.fecha_pedido,\n       vp.fecha_inicio, vp.fecha_fin,\n       vp.sesiones_totales, vp.sesiones_usadas, vp.sesiones_restantes,\n       vp.dias_restantes, vp.dias_congelados,\n       vp.vendedor, vp.tipo,\n       vp.precio_lista, vp.precio, vp.descuento, vp.descuento_pct,\n       vp.monto_entregado, vp.saldo, vp.fecha_limite_pago,\n       vp.estado_pago, vp.dias_para_pagar,\n       vp.medio_pago,\n       coalesce(vp.estado_real, \'SIN PAQUETE\') as estado_real\nfrom alumnos a\nleft join grupos ga on ga.id = a.grupo_id\nleft join lateral (\n    select p.* from v_paquetes p\n    where p.alumno_id = a.id\n    order by case p.estado_real\n               when \'ACTIVO\' then 0 when \'CONGELADO\' then 1 else 2 end,\n             p.fecha_fin desc\n    limit 1\n) vp on true;\n\ncreate or replace view v_asistencias as\nselect s.id, s.fecha, s.hora, s.sede, s.origen, s.anulada,\n       s.alumno_id, s.paquete_id, a.codigo,\n       (a.nombres || \' \' || a.apellidos) as alumno, a.telefono\nfrom asistencias s\njoin alumnos a on a.id = s.alumno_id;\n\n-- ---------------------------------------------------------------------\n-- 4. Verificacion\n-- ---------------------------------------------------------------------\nselect estado_pago, count(*) as pedidos,\n       sum(precio) as total, sum(monto_entregado) as cobrado, sum(saldo) as por_cobrar\n  from v_paquetes\n group by estado_pago\n order by estado_pago;\n'


def leer(ruta):
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


def error(mensaje):
    print("")
    print("  ERROR: " + mensaje)
    print("")
    sys.exit(1)


def revertir():
    for nombre in ("app.py", "db.py"):
        origen = CARPETA_BACKUP / nombre
        if origen.exists():
            shutil.copy2(origen, Path(nombre))
    print("")
    print("  Revertido. app.py y db.py volvieron a la version anterior.")
    print("  acceso.py y migracion-019.sql quedan, no molestan.")
    print("")


def aplicar():
    app, base = Path("app.py"), Path("db.py")

    if not app.exists() or not base.exists():
        error(
            "No encuentro app.py y db.py en esta carpeta.\n"
            "         Parate en la carpeta admin-streamlit y vuelve a intentar:\n"
            "         cd admin-streamlit"
        )

    texto_app, salto_app = leer(app)
    texto_db, salto_db = leer(base)

    if MARCA_APLICADO in texto_app:
        print("")
        print("  El parche " + PARCHE + " ya estaba aplicado. No se toco nada.")
        print("")
        return

    if MARCA_ORIGINAL not in texto_app:
        error("Este parche espera la version 2.8. Tu app.py es otra: descarga "
              "el ZIP completo en vez de parchear.")

    # Se verifica TODO antes de escribir una sola letra: si algo no calza,
    # el archivo no queda a medio parchear.
    faltantes = []
    for etiqueta, texto, cambios in (("app.py", texto_app, CAMBIOS_APP),
                                     ("db.py", texto_db, CAMBIOS_DB)):
        for indice, (viejo, _) in enumerate(cambios, start=1):
            if texto.count(viejo) != 1:
                faltantes.append((etiqueta, indice, texto.count(viejo)))

    if faltantes:
        print("")
        print("  No se aplico nada. Estos bloques no calzan:")
        for archivo, indice, veces in faltantes:
            estado = "no aparece" if veces == 0 else f"{veces} veces"
            print(f"    {archivo} bloque {indice}: {estado}")
        error("Tus archivos fueron modificados. Usa el ZIP completo.")

    respaldar(app)
    respaldar(base)

    for viejo, nuevo in CAMBIOS_APP:
        texto_app = texto_app.replace(viejo, nuevo, 1)
    for viejo, nuevo in CAMBIOS_DB:
        texto_db = texto_db.replace(viejo, nuevo, 1)

    escribir(app, texto_app, salto_app)
    escribir(base, texto_db, salto_db)
    escribir(Path("acceso.py"), ACCESO_PY, salto_app)
    escribir(Path("migracion-019.sql"), MIGRACION_SQL, salto_app)

    final_app = leer(app)[0]
    final_db = leer(base)[0]
    acceso_py = Path("acceso.py")
    sql = Path("migracion-019.sql")

    controles = [
        ("Monto entregado al vender", "Monto entregado" in final_app),
        ("Plazo para el saldo", "Pagar el saldo hasta" in final_app),
        ("Cobro parcial en el Panel", "registrar_abono" in final_app),
        ("Reportes separa vendido de cobrado",
         "entro a caja de verdad" in final_app),
        ("Abonos en la capa de datos", "def registrar_abono" in final_db),
        ("Pantalla de Accesos", "def pagina_accesos" in final_app),
        ("Claves leidas de la base", "def leer_config" in final_db),
        ("Modulo acceso.py", acceso_py.exists() and "pbkdf2" in acceso_py.read_text()),
        ("Migracion SQL generada", sql.exists() and sql.stat().st_size > 3000),
        ("Version 2.9", 'VERSION = "2.9"' in final_app),
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
    print("  PASO OBLIGATORIO antes de usarlo:")
    print("    1. Abre migracion-019.sql (quedo en esta carpeta)")
    print("    2. Copia todo y pegalo en Supabase > SQL Editor > Run")
    print("    3. Recien ahi sube los cambios y reinicia")
    print("")


if __name__ == "__main__":
    if "--revertir" in sys.argv:
        revertir()
    else:
        aplicar()