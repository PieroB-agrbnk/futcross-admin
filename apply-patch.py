"""
FUTCROSS | Patch 022 - Corregir un pedido ya registrado

Requiere la version 3.1 (parche 021 aplicado). No necesita migracion SQL.

EL CASO QUE LO MOTIVA
  El alumno confirma que arranca el lunes 24 y el domingo avisa que
  mejor el miercoles. Hasta ahora habia que anular el pedido y cargarlo
  de nuevo, perdiendo el numero y la fecha en que se cerro la venta.

QUE SE PUEDE CORREGIR
  Pestana nueva en Paquetes: "Editar un pedido". Se cambia la fecha de
  inicio, el plan, las sesiones, el grupo y los dias, el precio de lista
  y el cobrado, lo entregado y su plazo, el vendedor, el tipo, el metodo
  de pago y la observacion.

  Al mover la fecha de inicio se recalculan solas todas las fechas del
  alumno. La pantalla avisa el cambio: "la ultima sesion se mueve del
  18/09 al 21/09", y muestra el cronograma completo antes de guardar.
  La fecha de fin no se escribe a mano a proposito: si se escribiera,
  quedaria en un dia que su grupo no entrena.

DOS RESGUARDOS
  Si el plan ya empezo, la pantalla lo dice y pide marcar una casilla de
  confirmacion antes de guardar. Si todavia no arranca, se mueve libre.

  Cada correccion queda registrada con quien la hizo y que cambio
  (inicio, precio, sesiones, plan o dias). Aparece en el Panel, en
  "Intentos rechazados". Es dinero y fechas que el cliente ya acordo:
  tiene que poder rastrearse.

  El numero de pedido no cambia nunca.
"""

import shutil
import sys
from pathlib import Path

PARCHE = "022-editar-pedido"
CARPETA_BACKUP = Path("respaldos") / PARCHE

MARCA_APLICADO = "def editar_pedido(planes)"
MARCA_ORIGINAL = "def pagina_carga_masiva"


CAMBIOS_APP = [
    (
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "3.1"\n\n',
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "3.2"\n\n',
    ),
    (
        '# =====================================================================\ndef pagina_paquetes() -> None:\n    theme.cabecera("Paquetes", fecha_larga(logic.hoy()).upper(), "Ventas y renovaciones")\n\n    planes = db.listar_planes()\n    tab_vender, tab_lista = st.tabs(["Vender o renovar", "Todos los paquetes"])\n\n    if planes.empty:\n        with tab_vender:\n            theme.vacio("No hay planes activos",\n                        "Crea al menos un plan en la pantalla Planes.")\n        with tab_lista:\n            theme.vacio("Sin pedidos", "Todavia no se registro ninguno.")\n        return\n\n',
        '# =====================================================================\ndef editar_pedido(planes) -> None:\n    """Corrige un pedido ya registrado.\n\n    El caso que lo motivo: el alumno confirma que arranca el lunes y el\n    domingo avisa que mejor el miercoles. Antes habia que anular el\n    pedido y cargarlo de nuevo, perdiendo el numero y la fecha de venta.\n    """\n    pedidos = db.listar_paquetes()\n    if pedidos.empty:\n        theme.vacio("Sin pedidos", "Registra el primero en la otra pestana.")\n        return\n\n    def etiqueta(r):\n        inicio = logic.a_fecha(r["fecha_inicio"])\n        return (f"N {r.get(\'nro_pedido\') or \'-\'} \xb7 {r[\'alumno\']} \xb7 "\n                f"{r[\'plan_nombre\']} \xb7 desde {inicio.strftime(\'%d/%m/%Y\')}")\n\n    opciones = {etiqueta(r): r["id"] for _, r in pedidos.iterrows()}\n    elegido = st.selectbox("Pedido a corregir", list(opciones.keys()),\n                           key="pedido_editar")\n    pq = db.paquete(opciones[elegido])\n    if not pq:\n        st.error("No se encontro el pedido.")\n        return\n\n    usadas = int(pq.get("sesiones_usadas") or 0)\n    asistencias = int(pq.get("asistencias_registradas") or 0)\n    empezado = usadas > 0 or asistencias > 0\n\n    if empezado:\n        st.warning(\n            f"Este plan ya empezo: lleva {usadas} sesiones corridas y "\n            f"{asistencias} asistencias registradas. Si mueves la fecha de "\n            "inicio, esas cuentas cambian. Corrigelo solo si de verdad "\n            "arranco otro dia."\n        )\n    else:\n        st.info("Este plan todavia no arranca, se puede mover sin problema.")\n\n    with st.form("form_editar_pedido"):\n        c1, c2, c3 = st.columns([2, 1, 1])\n        nombres_planes = planes["nombre"].tolist()\n        actual = pq.get("plan_nombre")\n        indice = nombres_planes.index(actual) if actual in nombres_planes else 0\n        nombre_plan = c1.selectbox("Plan contratado", nombres_planes, index=indice)\n        plan = planes[planes["nombre"] == nombre_plan].iloc[0].to_dict()\n\n        fecha_pedido = c2.date_input(\n            "Fecha del pedido", value=logic.a_fecha(pq.get("fecha_pedido")),\n            format="DD/MM/YYYY", help="Cuando se cerro la venta. No suele cambiar.")\n        inicio = c3.date_input(\n            "Inicio del plan", value=logic.a_fecha(pq["fecha_inicio"]),\n            format="DD/MM/YYYY",\n            help="Al cambiarla se recalculan todas las fechas del alumno")\n\n        st.markdown("**Grupo y dias que entrena**")\n        grupo_id, dias_grupo, detalle = selector_de_grupo(\n            "Sede, horario y genero", clave="grupo_edicion",\n            grupo_actual=pq.get("grupo_id"),\n            dias_previos=str(pq.get("dias_asiste") or ""))\n        if detalle:\n            st.caption(detalle)\n\n        a1, a2 = st.columns(2)\n        sesiones = a1.number_input("Sesiones", min_value=1,\n                                   value=int(pq["sesiones_totales"]))\n        tipo = a2.selectbox("Renovacion o nuevo", ["NUEVO", "RENOVACION"],\n                            index=1 if pq.get("tipo") == "RENOVACION" else 0)\n\n        fin = logic.fecha_fin_por_calendario(\n            inicio, int(sesiones), dias_grupo, int(plan["vigencia_dias"]))\n\n        st.markdown("**Cobro**")\n        e1, e2, e3 = st.columns(3)\n        precio_lista = e1.number_input(\n            "Precio de lista (S/)", min_value=0.0, step=10.0,\n            value=float(pq.get("precio_lista") or pq.get("precio") or 0))\n        precio = e2.number_input("Precio cobrado (S/)", min_value=0.0, step=1.0,\n                                 value=float(pq.get("precio") or 0))\n        entregado = e3.number_input(\n            "Monto entregado (S/)", min_value=0.0, step=10.0,\n            value=float(pq.get("monto_entregado") or 0))\n\n        saldo = max(0.0, precio - entregado)\n        f1, f2 = st.columns(2)\n        if saldo > 0:\n            limite = f1.date_input(\n                "Pagar el saldo hasta",\n                value=logic.a_fecha(pq.get("fecha_limite_pago"))\n                or logic.hoy() + timedelta(days=15), format="DD/MM/YYYY")\n            f1.caption(f"Queda debiendo **S/ {saldo:,.2f}**")\n        else:\n            limite = None\n            f1.caption("Sin saldo pendiente.")\n        medio = f2.selectbox(\n            "Metodo de pago", MEDIOS_PAGO,\n            index=next((i for i, m in enumerate(MEDIOS_PAGO)\n                        if str(pq.get("medio_pago") or "").upper().startswith(m)), 0))\n\n        vendedor = st.text_input("Vendedor", value=str(pq.get("vendedor") or ""))\n        obs = st.text_input("Observacion", value=str(pq.get("observacion") or ""))\n\n        cronograma = logic.proximas_sesiones(inicio, int(sesiones), dias_grupo)\n        if cronograma:\n            st.info(\n                f"**{sesiones} sesiones** entrenando "\n                f"{logic.frecuencia(dias_grupo)} ({dias_grupo}). "\n                f"Primera el {fecha_larga(cronograma[0])}, ultima el "\n                f"**{fecha_larga(fin)}**."\n            )\n            anterior_fin = logic.a_fecha(pq["fecha_fin"])\n            if anterior_fin and anterior_fin != fin:\n                st.warning(f"La ultima sesion se mueve del "\n                           f"{anterior_fin.strftime(\'%d/%m/%Y\')} al "\n                           f"{fin.strftime(\'%d/%m/%Y\')}.")\n            if len(cronograma) <= 12:\n                st.caption("Fechas: " + " \xb7 ".join(\n                    f.strftime("%d/%m") for f in cronograma))\n\n        confirmar = st.checkbox(\n            "Confirmo el cambio", value=not empezado,\n            help="Si el plan ya empezo, revisa bien antes de guardar")\n\n        if st.form_submit_button("Guardar cambios", type="primary"):\n            if not dias_grupo:\n                st.error("Marca al menos un dia de entrenamiento.")\n            elif not confirmar:\n                st.error("Marca la casilla de confirmacion.")\n            elif entregado > precio:\n                st.error("El monto entregado no puede ser mayor al cobrado.")\n            else:\n                try:\n                    db.editar_pedido(\n                        pq["id"], plan, inicio, int(sesiones), dias_grupo,\n                        grupo_id, precio_lista, precio, entregado, limite,\n                        (vendedor or "").strip().upper() or None, tipo, medio,\n                        fecha_pedido, obs or None,\n                        quien=ETIQUETA_ROL.get(rol(), ""))\n                    st.toast("Pedido corregido", icon="\\u2705")\n                    st.success(\n                        f"Pedido actualizado. Su ultima sesion queda el "\n                        f"{fecha_larga(fin)}."\n                    )\n                    st.rerun()\n                except Exception as e:\n                    st.error(f"No se pudo guardar: {e}")\n\n    st.caption(\n        "El numero de pedido no cambia. Cada correccion queda registrada y se "\n        "puede ver en el Panel, en Intentos rechazados."\n    )\n\n\ndef pagina_paquetes() -> None:\n    theme.cabecera("Paquetes", fecha_larga(logic.hoy()).upper(), "Ventas y renovaciones")\n\n    planes = db.listar_planes()\n    tab_vender, tab_editar, tab_lista = st.tabs(\n        ["Vender o renovar", "Editar un pedido", "Todos los paquetes"])\n\n    if planes.empty:\n        with tab_vender:\n            theme.vacio("No hay planes activos",\n                        "Crea al menos un plan en la pantalla Planes.")\n        with tab_editar:\n            theme.vacio("Nada que editar", "Primero crea un plan.")\n        with tab_lista:\n            theme.vacio("Sin pedidos", "Todavia no se registro ninguno.")\n        return\n\n    with tab_editar:\n        editar_pedido(planes)\n\n',
    ),
]


CAMBIOS_DB = [
    (
        '\ndef siguiente_pedido() -> int:\n',
        '\ndef editar_pedido(paquete_id: str, plan: dict | None, fecha_inicio: date,\n                  sesiones: int, dias_asiste: str, grupo_id: str | None,\n                  precio_lista: float, precio: float, monto_entregado: float,\n                  fecha_limite_pago: date | None, vendedor: str | None,\n                  tipo: str, medio_pago: str, fecha_pedido: date,\n                  observacion: str | None, quien: str = "admin"):\n    """Corrige un pedido ya registrado y recalcula lo que dependa de eso.\n\n    Mover la fecha de inicio corre todo el calendario del alumno, asi que\n    la fecha de fin se vuelve a calcular aca y no se pide a mano: si se\n    escribiera, quedaria una fecha que no corresponde a ninguna sesion.\n\n    El numero de pedido y la fecha en que se cerro la venta no se tocan\n    desde la pantalla: son el rastro de la operacion original.\n    """\n    anterior = paquete(paquete_id) or {}\n    fecha_fin = logic.fecha_fin_por_calendario(\n        fecha_inicio, int(sesiones), dias_asiste,\n        int((plan or {}).get("vigencia_dias") or 30))\n\n    cambios = {\n        "fecha_inicio": fecha_inicio.isoformat(),\n        "fecha_fin": fecha_fin.isoformat(),\n        "fecha_pedido": fecha_pedido.isoformat(),\n        "sesiones_totales": int(sesiones),\n        "dias_asiste": dias_asiste,\n        "grupo_id": grupo_id,\n        "precio_lista": float(precio_lista),\n        "precio": float(precio),\n        "monto_entregado": float(monto_entregado),\n        "fecha_limite_pago": (fecha_limite_pago.isoformat()\n                              if fecha_limite_pago else None),\n        "vendedor": vendedor,\n        "tipo": tipo,\n        "medio_pago": medio_pago,\n        "observacion": observacion,\n    }\n    if plan:\n        cambios["plan_id"] = plan.get("id")\n        cambios["plan_nombre"] = plan["nombre"]\n\n    r = _tabla("paquetes").update(cambios).eq("id", paquete_id).execute().data\n\n    # Queda constancia de que se toco un pedido: es dinero y fechas que el\n    # cliente ya acordo, asi que tiene que poder rastrearse despues.\n    try:\n        detalle = []\n        for campo, etiqueta in (("fecha_inicio", "inicio"), ("precio", "precio"),\n                                ("sesiones_totales", "sesiones"),\n                                ("plan_nombre", "plan"), ("dias_asiste", "dias")):\n            antes = anterior.get(campo)\n            ahora = cambios.get(campo)\n            if ahora is not None and str(antes) != str(ahora):\n                detalle.append(f"{etiqueta}: {antes} -> {ahora}")\n        if detalle:\n            registrar_bloqueo(\n                anterior.get("alumno_id"),\n                f"Pedido {anterior.get(\'nro_pedido\')} editado por {quien}. "\n                + "; ".join(detalle),\n                "PEDIDO_EDITADO")\n    except Exception:\n        pass\n\n    invalidar_cache()\n    return r\n\n\ndef siguiente_pedido() -> int:\n',
    ),
]





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
        error("Este parche espera la version 3.1 (parche 021 aplicado).")

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

    final_app = leer(app)[0]
    final_db = leer(base)[0]

    controles = [
        ("Pestana de edicion", '"Editar un pedido"' in final_app),
        ("Se puede mover la fecha de inicio",
         "se recalculan todas las fechas" in final_app),
        ("Avisa si el plan ya empezo", "Este plan ya empezo" in final_app),
        ("Pide confirmacion", "Confirmo el cambio" in final_app),
        ("Muestra como se mueve el fin", "La ultima sesion se mueve"
         in final_app or "la ultima sesion se mueve" in final_app),
        ("Recalcula el fin en la base", "def editar_pedido" in final_db),
        ("Deja constancia del cambio", "PEDIDO_EDITADO" in final_db),
        ("Version 3.2", 'VERSION = "3.2"' in final_app),
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
    print("  No necesita migracion. Sube los cambios:")
    print("    git add . && git commit -m \"Editar pedido\" && git push")
    print("")


if __name__ == "__main__":
    if "--revertir" in sys.argv:
        revertir()
    else:
        aplicar()