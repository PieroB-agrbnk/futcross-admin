"""
FUTCROSS | Patch 020 - El plan corre por calendario

Requiere la version 2.9 (parche 019 aplicado).

EL CAMBIO DE FONDO
  Hasta ahora una sesion se consumia cuando el alumno marcaba
  asistencia. FutCross no funciona asi: el plan corre desde el dia 1 y
  las sesiones se cuentan vaya o no vaya. La lista que pasan los profes
  es para que no se cuele nadie, no para descontar.

  Desde este parche, las sesiones usadas salen del calendario: cuantas
  de sus fechas ya pasaron, descontando los dias que estuvo en pausa y
  los dias que la academia no abrio. Las asistencias se siguen
  guardando, pero como registro de quien vino.

EL KIOSCO
  Deja de descontar y pasa a verificar. El alumno escribe su DNI y la
  pantalla le dice al momento si esta al dia. Asi se detecta al colado
  en el momento, en vez de revisar la lista al dia siguiente.

  Si viene un dia que no es de los suyos, igual queda registrado pero
  se le avisa que su plan corre por los dias que eligio.

ESTADO NUEVO: POR EMPEZAR
  Un plan vendido que arranca el lunes ya no figura como activo desde
  hoy. Aparece como POR EMPEZAR y el kiosco le dice la fecha en que
  arranca.

DIAS SIN ENTRENAMIENTO
  Pantalla nueva. Si la academia no abre por feriado, lluvia o cancha
  ocupada, se marca el dia y esa sesion deja de contarle a todos: el
  plan se corre solo. Se puede marcar para todos los grupos o para uno.

VIAJES AVISADOS CON ANTICIPACION
  Arreglo importante: al registrar una pausa que empieza en dos semanas,
  el plan quedaba congelado DESDE HOY, asi que la persona no podia
  entrenar en el medio. Ahora la pausa se activa sola al llegar su
  fecha, igual que la reactivacion.

IMPORTANTE
  Necesita que ANTES corras migracion-020.sql en Supabase. El archivo se
  genera solo al aplicar el parche.

  Aviso: al aplicarlo, los alumnos ya cargados van a recalcular su
  avance. Uno que hoy figura en 0% porque nunca marco va a pasar a
  mostrar las sesiones que ya transcurrieron. Eso es lo correcto con el
  modelo nuevo, pero conviene avisarle al equipo para que no piensen que
  se descuadro algo.
"""

import shutil
import sys
from pathlib import Path

PARCHE = "020-plan-por-calendario"
CARPETA_BACKUP = Path("respaldos") / PARCHE

MARCA_APLICADO = "POR_EMPEZAR"
MARCA_ORIGINAL = "def pagina_accesos"


CAMBIOS_APP = [
    (
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "2.9"\n\n',
        '# que estas viendo en la nube es la misma que tienes en tu computadora.\nVERSION = "3.0"\n\n',
    ),
    (
        '    "admin": ["Panel", "Marcar asistencia", "Renovaciones", "Alumnos",\n              "Paquetes", "Congelamientos", "Reportes", "Planes", "Accesos"],\n    "entrenador": ["Panel", "Marcar asistencia", "Alumnos", "Renovaciones"],\n',
        '    "admin": ["Panel", "Marcar asistencia", "Renovaciones", "Alumnos",\n              "Paquetes", "Congelamientos", "Reportes", "Planes",\n              "Dias sin entrenar", "Accesos"],\n    "entrenador": ["Panel", "Marcar asistencia", "Alumnos", "Renovaciones"],\n',
    ),
    (
        '\n    usadas = int(pq["sesiones_usadas"]) if pq else None\n',
        '\n    # El plan corre por calendario: marcar NO descuenta nada, solo deja\n    # constancia de quien vino. Estas dos cifras salen de la vista.\n    usadas = int(pq["sesiones_usadas"]) if pq else None\n',
    ),
    (
        '            db.marcar_asistencia(alumno_id, pq["id"], sede=fila.get("sede"), origen="KIOSCO")\n            usadas += 1\n        except Exception as e:\n',
        '            db.marcar_asistencia(alumno_id, pq["id"], sede=fila.get("sede"), origen="KIOSCO")\n        except Exception as e:\n',
    ),
    (
        '        "OK": "Pasa a la cancha",\n        "YA_MARCO": "Ya marcaste hoy",\n        "VENCIDO": "Paquete vencido",\n        "AGOTADO": "Sesiones agotadas",\n        "CONGELADO": "Paquete congelado",\n        "CANCELADO": "Paquete anulado",\n        "SIN_PAQUETE": "Sin paquete",\n    }.get(motivo, "Revisar en recepcion")\n',
        '        "OK": "Pasa a la cancha",\n        "OTRO_DIA": "Pasa, pero ojo",\n        "YA_MARCO": "Ya marcaste hoy",\n        "VENCIDO": "Plan terminado",\n        "AGOTADO": "Plan terminado",\n        "CONGELADO": "Plan en pausa",\n        "POR_EMPEZAR": "Todavia no arranca",\n        "CANCELADO": "Plan anulado",\n        "SIN_PAQUETE": "Sin plan",\n    }.get(motivo, "Revisar en recepcion")\n',
    ),
    (
        '        st.caption(\n            "Cada alumno marca una sola vez por dia. "\n            "Si tu paquete esta vencido o congelado, el sistema no lo descuenta."\n        )\n',
        '        st.caption(\n            "El plan corre por calendario: las sesiones se cuentan desde el dia "\n            "que arranca, vaya o no vaya el alumno. Marcar aca no descuenta "\n            "nada, solo deja registro de quien vino."\n        )\n',
    ),
    (
        '# =====================================================================\n# 9. ACCESOS\n# =====================================================================\n',
        '# =====================================================================\n# 9. DIAS SIN ENTRENAMIENTO\n# =====================================================================\ndef pagina_dias_libres() -> None:\n    theme.cabecera("Dias sin entrenamiento", fecha_larga(logic.hoy()).upper(),\n                   "Feriados y cancelaciones")\n    st.caption(\n        "Como el plan corre por calendario, un dia que la academia no abre le "\n        "consumiria una sesion a todos igual. Al marcarlo aca, ese dia deja de "\n        "contar y a cada alumno se le corre el plan una sesion mas."\n    )\n\n    grupos = db.listar_grupos()\n\n    with st.form("form_no_laborable"):\n        c1, c2 = st.columns([1, 2])\n        fecha = c1.date_input("Dia que no se entreno", value=logic.hoy(),\n                              format="DD/MM/YYYY")\n\n        opciones = {"Todos los grupos": None}\n        if not grupos.empty:\n            for _, g in grupos.iterrows():\n                opciones[f"{g[\'nombre\']} ({g[\'dias\']})"] = g["id"]\n        cual = c2.selectbox("A que grupo afecta", list(opciones.keys()),\n                            help="Un feriado afecta a todos; una cancha ocupada, "\n                                 "solo a ese grupo")\n\n        motivo = st.text_input("Motivo", placeholder="Ej. Feriado 28 de julio, "\n                                                     "lluvia, cancha ocupada")\n\n        if st.form_submit_button("Marcar el dia", type="primary"):\n            try:\n                db.marcar_no_laborable(fecha, opciones[cual], motivo or None)\n                st.toast("Dia marcado", icon="\\u2705")\n                st.success(\n                    f"El {fecha_larga(fecha)} ya no le cuenta a "\n                    f"{cual.lower()}. Sus planes se corren una sesion."\n                )\n                st.rerun()\n            except Exception as e:\n                if "uq_no_laborable" in str(e) or "duplicate" in str(e).lower():\n                    st.warning("Ese dia ya estaba marcado para ese grupo.")\n                else:\n                    st.error(f"No se pudo marcar: {e}")\n\n    theme.seccion("Dias marcados", "de los ultimos meses")\n    dias = db.dias_no_laborables(logic.hoy() - timedelta(days=180))\n    if dias.empty:\n        theme.vacio("Ningun dia marcado",\n                    "Cuando no entrenen por feriado o lluvia, marcalo aca para "\n                    "que nadie pierda su sesion.")\n    else:\n        for _, d in dias.iterrows():\n            f = logic.a_fecha(d["fecha"])\n            c1, c2 = st.columns([5, 1])\n            with c1:\n                theme.fila(fecha_larga(f).title(),\n                           f\'{d.get("grupo", "")} \xb7 {d.get("motivo") or "sin motivo"}\',\n                           theme.AZUL)\n            if c2.button("Quitar", key=f"quitar_{d[\'id\']}", width="stretch"):\n                db.quitar_no_laborable(d["id"])\n                st.toast("Dia desmarcado", icon="\\u2705")\n                st.rerun()\n\n\n# =====================================================================\n# 10. ACCESOS\n# =====================================================================\n',
    ),
    (
        '    "Planes": pagina_planes,\n    "Accesos": pagina_accesos,\n}\n\nGRUPOS = [\n    ("Dia a dia", ["Panel", "Marcar asistencia", "Renovaciones"]),\n    ("Alumnos y pagos", ["Alumnos", "Paquetes", "Congelamientos"]),\n    ("Gestion", ["Reportes", "Planes", "Accesos"]),\n]\n',
        '    "Planes": pagina_planes,\n    "Dias sin entrenar": pagina_dias_libres,\n    "Accesos": pagina_accesos,\n}\n\nGRUPOS = [\n    ("Dia a dia", ["Panel", "Marcar asistencia", "Renovaciones"]),\n    ("Alumnos y pagos", ["Alumnos", "Paquetes", "Congelamientos"]),\n    ("Gestion", ["Reportes", "Planes", "Dias sin entrenar", "Accesos"]),\n]\n',
    ),
    (
        '            pass\n\n',
        '            pass\n        # Y las pausas programadas cuya fecha ya llego (viajes avisados\n        # con anticipacion)\n        try:\n            c = db.activar_congelamientos()\n            if c:\n                st.toast(f"{c} plan(es) entraron en pausa programada", icon="\\u2744\\ufe0f")\n        except Exception:\n            pass\n\n',
    ),
]


CAMBIOS_DB = [
    (
        '    }).execute()\n    _tabla("paquetes").update({"estado": "CONGELADO"}).eq("id", paquete_id).execute()\n    invalidar_cache()\n',
        '    }).execute()\n\n    # Un viaje que empieza en dos semanas no puede pausar el plan hoy: la\n    # persona todavia entrena. La pausa se activa sola al llegar la fecha\n    # (fc_activar_congelamientos, que corre de noche y al abrir el panel).\n    if desde <= logic.hoy():\n        _tabla("paquetes").update({"estado": "CONGELADO"}).eq("id", paquete_id).execute()\n    invalidar_cache()\n',
    ),
    (
        '\ndef reactivar_automaticos() -> int:\n',
        '\ndef activar_congelamientos() -> int:\n    """Pone en pausa los congelamientos programados cuya fecha ya llego."""\n    try:\n        r = cliente().rpc("fc_activar_congelamientos", {}).execute()\n        n = int(r.data or 0)\n    except Exception:\n        return 0\n    if n:\n        invalidar_cache()\n    return n\n\n\ndef reactivar_automaticos() -> int:\n',
    ),
    (
        '         .eq("paquete_id", paquete_id).eq("activo", True).limit(1).execute().data)\n    return r[0] if r else None\n\n\n',
        '         .eq("paquete_id", paquete_id).eq("activo", True).limit(1).execute().data)\n    return r[0] if r else None\n\n\n# ---------------------------------------------------------------------\n# Dias que la academia no abrio\n#\n# Esas sesiones no se le cuentan a nadie: el plan se corre solo, porque\n# `sesiones_usadas` sale del calendario y estos dias se descuentan ahi.\n# ---------------------------------------------------------------------\n@_cache(CACHE_CORTO)\ndef dias_no_laborables(desde: date | None = None) -> pd.DataFrame:\n    try:\n        q = _tabla("dias_no_laborables").select("*, grupos(nombre)")\n        if desde:\n            q = q.gte("fecha", desde.isoformat())\n        rows = q.order("fecha", desc=True).execute().data or []\n    except Exception:\n        return pd.DataFrame()\n    for r in rows:\n        g = r.pop("grupos", None) or {}\n        r["grupo"] = g.get("nombre") or "Todos los grupos"\n    return _df(rows)\n\n\ndef marcar_no_laborable(fecha: date, grupo_id: str | None, motivo: str):\n    r = _tabla("dias_no_laborables").insert({\n        "fecha": fecha.isoformat(),\n        "grupo_id": grupo_id,\n        "motivo": motivo,\n    }).execute().data\n    invalidar_cache()\n    return r\n\n\ndef quitar_no_laborable(registro_id: str):\n    _tabla("dias_no_laborables").delete().eq("id", registro_id).execute()\n    invalidar_cache()\n\n\n',
    ),
]


CAMBIOS_LOGICA = [
    (
        '        return "CONGELADO"\n    usadas = int(paquete.get("sesiones_usadas") or 0)\n',
        '        return "CONGELADO"\n    inicio = a_fecha(paquete.get("fecha_inicio"))\n    if inicio and ref < inicio:\n        return "POR EMPEZAR"\n    usadas = int(paquete.get("sesiones_usadas") or 0)\n',
    ),
    (
        '    estado = estado_real(paquete, ref)\n\n    if estado == "CANCELADO":\n        return False, "CANCELADO", "Este paquete fue anulado. Consulta en recepcion."\n    if estado == "CONGELADO":\n        return False, "CONGELADO", "Tu paquete esta congelado. Avisa en recepcion para reactivarlo."\n    if estado == "AGOTADO":\n        total = paquete.get("sesiones_totales")\n        return False, "AGOTADO", f"Ya usaste tus {total} sesiones. Toca renovar el paquete."\n    if estado == "VENCIDO":\n        fin = a_fecha(paquete.get("fecha_fin"))\n        return False, "VENCIDO", f"Tu paquete vencio el {fin.strftime(\'%d/%m/%Y\')}. Toca renovar."\n    if ya_marco_hoy:\n        return False, "YA_MARCO", "Ya registraste tu asistencia de hoy."\n\n    return True, "OK", "Asistencia registrada. A entrenar."\n\n',
        '    estado = estado_real(paquete, ref)\n    ref = ref or hoy()\n\n    if estado == "CANCELADO":\n        return False, "CANCELADO", "Este paquete fue anulado. Consulta en recepcion."\n    if estado == "CONGELADO":\n        return False, "CONGELADO", "Tu plan esta en pausa. Avisa en recepcion para reactivarlo."\n    if estado == "POR EMPEZAR":\n        inicio = a_fecha(paquete.get("fecha_inicio"))\n        return False, "POR_EMPEZAR", (\n            f"Tu plan arranca el {inicio.strftime(\'%d/%m/%Y\')}. Nos vemos ese dia.")\n    if estado == "AGOTADO":\n        total = paquete.get("sesiones_totales")\n        return False, "AGOTADO", f"Ya se cumplieron tus {total} sesiones. Toca renovar."\n    if estado == "VENCIDO":\n        fin = a_fecha(paquete.get("fecha_fin"))\n        return False, "VENCIDO", f"Tu plan termino el {fin.strftime(\'%d/%m/%Y\')}. Toca renovar."\n\n    # Hoy no toca entrenar a su grupo: no se le impide pasar, pero se le\n    # avisa, porque su plan corre por los dias que eligio.\n    dias = paquete.get("dias_asiste")\n    if dias and not es_dia_de_entrenamiento(ref, dias):\n        return True, "OTRO_DIA", (\n            "Hoy no es uno de tus dias. Igual quedas registrado, pero tu plan "\n            "corre por los dias que elegiste.")\n    if ya_marco_hoy:\n        return False, "YA_MARCO", "Ya registraste tu asistencia de hoy."\n\n    return True, "OK", "Estas al dia. A entrenar."\n\n',
    ),
]


MIGRACION_SQL = "-- =====================================================================\n-- FUTCROSS | Migracion 020 - El plan corre por calendario\n--\n-- CAMBIO DE FONDO\n--   Hasta ahora una sesion se consumia cuando el alumno marcaba\n--   asistencia. FutCross no funciona asi: el plan corre desde el dia 1\n--   y las sesiones se cuentan vaya o no vaya. La lista de los profes es\n--   para control, no para descontar.\n--\n--   Desde esta migracion, `sesiones_usadas` es cuantas de sus fechas ya\n--   pasaron, descontando los dias que estuvo congelado y los dias que\n--   la academia no abrio. Las asistencias siguen guardandose, pero como\n--   registro de quien vino, no como contador.\n--\n-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.\n-- =====================================================================\n\n-- ---------------------------------------------------------------------\n-- 1. 'LUN MIE VIE' -> {1,3,5}   (en Postgres domingo = 0)\n-- ---------------------------------------------------------------------\ncreate or replace function fc_indices_dias(p_dias text)\nreturns int[]\nlanguage sql immutable as $$\n    select array_agg(case d\n               when 'LUN' then 1 when 'MAR' then 2 when 'MIE' then 3\n               when 'JUE' then 4 when 'VIE' then 5 when 'SAB' then 6\n               when 'DOM' then 0 end)\n      from unnest(string_to_array(upper(trim(coalesce(p_dias, ''))), ' ')) as d\n     where d <> '';\n$$;\n\n-- ---------------------------------------------------------------------\n-- 2. Dias que la academia no abrio\n--    grupo_id nulo = no abrio ninguna sede ese dia (feriado).\n--    Con grupo, solo ese grupo (cancha ocupada, por ejemplo).\n-- ---------------------------------------------------------------------\ncreate table if not exists dias_no_laborables (\n    id        uuid primary key default gen_random_uuid(),\n    fecha     date not null,\n    grupo_id  uuid references grupos(id),\n    motivo    text,\n    creado_en timestamptz not null default now()\n);\n\ncreate unique index if not exists uq_no_laborable\n    on dias_no_laborables (fecha, coalesce(grupo_id, '00000000-0000-0000-0000-000000000000'::uuid));\n\ncomment on table dias_no_laborables is\n    'Dias en que no se entreno. Esas sesiones no se le cuentan a nadie y '\n    'el plan se corre al siguiente dia de entrenamiento del grupo.';\n\n-- ---------------------------------------------------------------------\n-- 3. Cuantas sesiones ya transcurrieron\n--\n--    Cuenta los dias de entrenamiento entre el inicio y hoy, restando\n--    los que cayeron dentro de un congelamiento y los que la academia\n--    no abrio. Nunca pasa del total del paquete.\n-- ---------------------------------------------------------------------\ncreate or replace function fc_sesiones_transcurridas(p_paquete_id uuid)\nreturns int\nlanguage sql stable as $$\n    with p as (\n        select pq.id, pq.fecha_inicio, pq.fecha_fin, pq.sesiones_totales,\n               pq.grupo_id, pq.estado,\n               fc_indices_dias(coalesce(pq.dias_asiste, g.dias, a.dias_asiste)) as idx\n          from paquetes pq\n          join alumnos a on a.id = pq.alumno_id\n     left join grupos  g on g.id = pq.grupo_id\n         where pq.id = p_paquete_id\n    )\n    select case\n        when p.idx is null then 0\n        when p.estado = 'CANCELADO' then 0\n        else least(\n            p.sesiones_totales,\n            (select count(*)::int\n               from p, generate_series(p.fecha_inicio,\n                                       least(hoy_lima(), p.fecha_fin),\n                                       interval '1 day') as d\n              where extract(dow from d)::int = any(p.idx)\n                -- dias que estuvo congelado\n                and not exists (\n                    select 1 from congelamientos c\n                     where c.paquete_id = p.id\n                       and d::date >= c.fecha_inicio\n                       and d::date <= coalesce(c.fecha_fin, date '9999-12-31'))\n                -- dias que la academia no abrio\n                and not exists (\n                    select 1 from dias_no_laborables n\n                     where n.fecha = d::date\n                       and (n.grupo_id is null or n.grupo_id = p.grupo_id))\n            ))\n        end\n      from p;\n$$;\n\n-- ---------------------------------------------------------------------\n-- 4. Activar los congelamientos programados a futuro\n--\n--    Al registrar un viaje que empieza en dos semanas, el paquete no\n--    puede quedar congelado desde hoy: la persona todavia entrena. Esto\n--    lo pone en pausa recien cuando llega la fecha.\n-- ---------------------------------------------------------------------\ncreate or replace function fc_activar_congelamientos()\nreturns int\nlanguage plpgsql as $$\ndeclare\n    n int;\nbegin\n    with debidos as (\n        select distinct c.paquete_id\n          from congelamientos c\n          join paquetes p on p.id = c.paquete_id\n         where c.activo\n           and c.fecha_inicio <= hoy_lima()\n           and coalesce(c.fecha_fin, date '9999-12-31') >= hoy_lima()\n           and p.estado = 'ACTIVO'\n    )\n    update paquetes set estado = 'CONGELADO'\n     where id in (select paquete_id from debidos);\n    get diagnostics n = row_count;\n    return n;\nend $$;\n\n-- ---------------------------------------------------------------------\n-- 5. Vistas\n--    sesiones_usadas pasa a salir del calendario.\n--    asistencias_registradas queda como el conteo de quien vino: sigue\n--    sirviendo para ver constancia, pero ya no descuenta.\n-- ---------------------------------------------------------------------\ndrop view if exists v_alumnos_estado cascade;\ndrop view if exists v_paquetes cascade;\n\ncreate view v_paquetes as\nwith base as (\n    select p.*,\n           fc_sesiones_transcurridas(p.id) as sesiones_usadas,\n           coalesce((select count(*) from asistencias s\n                     where s.paquete_id = p.id and not s.anulada), 0)::int\n               as asistencias_registradas\n    from paquetes p\n)\nselect b.id,\n       b.nro_pedido,\n       b.alumno_id,\n       a.codigo, a.nombres, a.apellidos,\n       (a.nombres || ' ' || a.apellidos) as alumno,\n       a.dni, a.telefono,\n       b.grupo_id,\n       coalesce(g.nombre, b.sede, a.sede)      as grupo,\n       coalesce(g.sede, b.sede, a.sede)        as sede,\n       g.genero, g.hora,\n       coalesce(b.dias_asiste, g.dias, a.dias_asiste) as dias_asiste,\n       a.turno, a.horario,\n       b.plan_id, b.plan_nombre,\n       b.sesiones_totales,\n       b.sesiones_usadas,\n       b.asistencias_registradas,\n       (b.sesiones_totales - b.sesiones_usadas) as sesiones_restantes,\n       b.fecha_pedido, b.fecha_inicio, b.fecha_fin,\n       (b.fecha_fin - hoy_lima())            as dias_restantes,\n       b.dias_congelados,\n       coalesce(b.precio_lista, b.precio)     as precio_lista,\n       b.precio,\n       (coalesce(b.precio_lista, b.precio) - b.precio) as descuento,\n       case when coalesce(b.precio_lista, 0) > 0\n            then round((coalesce(b.precio_lista, b.precio) - b.precio)\n                       / b.precio_lista * 100, 1)\n            else 0 end                        as descuento_pct,\n       coalesce(b.monto_entregado, 0)         as monto_entregado,\n       (b.precio - coalesce(b.monto_entregado, 0)) as saldo,\n       b.fecha_limite_pago,\n       case\n         when coalesce(b.monto_entregado, 0) >= b.precio then 'PAGADO'\n         when coalesce(b.monto_entregado, 0) > 0         then 'PARCIAL'\n         else 'PENDIENTE'\n       end                                    as estado_pago,\n       case\n         when coalesce(b.monto_entregado, 0) >= b.precio then null\n         when b.fecha_limite_pago is null                then null\n         else (b.fecha_limite_pago - hoy_lima())\n       end                                    as dias_para_pagar,\n       b.medio_pago, b.pagado, b.vendedor, b.tipo,\n       b.estado, b.observacion, b.creado_en,\n       case\n         when b.estado = 'CANCELADO'                  then 'CANCELADO'\n         when b.estado = 'CONGELADO'                  then 'CONGELADO'\n         when hoy_lima() < b.fecha_inicio             then 'POR EMPEZAR'\n         when b.sesiones_usadas >= b.sesiones_totales then 'AGOTADO'\n         when hoy_lima() > b.fecha_fin                then 'VENCIDO'\n         else 'ACTIVO'\n       end as estado_real\nfrom base b\njoin alumnos a on a.id = b.alumno_id\nleft join grupos g on g.id = b.grupo_id;\n\ncreate view v_alumnos_estado as\nselect a.id            as alumno_id,\n       a.codigo, a.nombres, a.apellidos,\n       (a.nombres || ' ' || a.apellidos) as alumno,\n       a.dni, a.telefono, a.email,\n       a.grupo_id,\n       ga.nombre       as grupo,\n       coalesce(ga.sede, a.sede)        as sede,\n       ga.genero, ga.hora,\n       coalesce(vp.dias_asiste, ga.dias, a.dias_asiste) as dias_asiste,\n       a.turno, a.horario, a.fecha_inscripcion, a.activo,\n       vp.id            as paquete_id,\n       vp.nro_pedido, vp.plan_nombre, vp.fecha_pedido,\n       vp.fecha_inicio, vp.fecha_fin,\n       vp.sesiones_totales, vp.sesiones_usadas, vp.asistencias_registradas,\n       vp.sesiones_restantes, vp.dias_restantes, vp.dias_congelados,\n       vp.vendedor, vp.tipo,\n       vp.precio_lista, vp.precio, vp.descuento, vp.descuento_pct,\n       vp.monto_entregado, vp.saldo, vp.fecha_limite_pago,\n       vp.estado_pago, vp.dias_para_pagar,\n       vp.medio_pago,\n       coalesce(vp.estado_real, 'SIN PAQUETE') as estado_real\nfrom alumnos a\nleft join grupos ga on ga.id = a.grupo_id\nleft join lateral (\n    select p.* from v_paquetes p\n    where p.alumno_id = a.id\n    order by case p.estado_real\n               when 'ACTIVO' then 0 when 'POR EMPEZAR' then 1\n               when 'CONGELADO' then 2 else 3 end,\n             p.fecha_fin desc\n    limit 1\n) vp on true;\n\ncreate or replace view v_asistencias as\nselect s.id, s.fecha, s.hora, s.sede, s.origen, s.anulada,\n       s.alumno_id, s.paquete_id, a.codigo,\n       (a.nombres || ' ' || a.apellidos) as alumno, a.telefono\nfrom asistencias s\njoin alumnos a on a.id = s.alumno_id;\n\n-- ---------------------------------------------------------------------\n-- 6. La tarea nocturna tambien activa los congelamientos programados\n-- ---------------------------------------------------------------------\ndo $$\nbegin\n    perform cron.unschedule('futcross-congelar')\n      where exists (select 1 from cron.job where jobname = 'futcross-congelar');\n    perform cron.schedule('futcross-congelar', '10 5 * * *',\n                          'select fc_activar_congelamientos();');\nexception when others then\n    raise notice 'pg_cron no disponible (%). Corre igual al abrir el panel.', sqlerrm;\nend $$;\n\n-- ---------------------------------------------------------------------\n-- 7. Verificacion\n-- ---------------------------------------------------------------------\nselect fc_activar_congelamientos() as congelamientos_activados;\n\nselect alumno, plan_nombre, fecha_inicio, fecha_fin,\n       sesiones_usadas, sesiones_totales, sesiones_restantes,\n       asistencias_registradas, estado_real\n  from v_paquetes\n order by fecha_inicio desc\n limit 20;\n"


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
    for nombre in ("app.py", "db.py", "logic.py"):
        origen = CARPETA_BACKUP / nombre
        if origen.exists():
            shutil.copy2(origen, Path(nombre))
    print("")
    print("  Revertido. app.py, db.py y logic.py volvieron a la version anterior.")
    print("  migracion-020.sql queda, no molesta.")
    print("")


def aplicar():
    app, base, logica = Path("app.py"), Path("db.py"), Path("logic.py")

    if not app.exists() or not base.exists() or not logica.exists():
        error(
            "No encuentro app.py, db.py y logic.py en esta carpeta.\n"
            "         Parate en la carpeta admin-streamlit y vuelve a intentar:\n"
            "         cd admin-streamlit"
        )

    texto_app, salto_app = leer(app)
    texto_db, salto_db = leer(base)
    texto_lg, salto_lg = leer(logica)

    if MARCA_APLICADO in texto_app:
        print("")
        print("  El parche " + PARCHE + " ya estaba aplicado. No se toco nada.")
        print("")
        return

    if MARCA_ORIGINAL not in texto_app:
        error("Este parche espera la version 2.9 (parche 019 aplicado).")

    # Se verifica TODO antes de escribir una sola letra: si algo no calza,
    # el archivo no queda a medio parchear.
    faltantes = []
    for etiqueta, texto, cambios in (("app.py", texto_app, CAMBIOS_APP),
                                     ("db.py", texto_db, CAMBIOS_DB),
                                     ("logic.py", texto_lg, CAMBIOS_LOGICA)):
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
    respaldar(logica)

    for viejo, nuevo in CAMBIOS_APP:
        texto_app = texto_app.replace(viejo, nuevo, 1)
    for viejo, nuevo in CAMBIOS_DB:
        texto_db = texto_db.replace(viejo, nuevo, 1)
    for viejo, nuevo in CAMBIOS_LOGICA:
        texto_lg = texto_lg.replace(viejo, nuevo, 1)

    escribir(app, texto_app, salto_app)
    escribir(base, texto_db, salto_db)
    escribir(logica, texto_lg, salto_lg)
    escribir(Path("migracion-020.sql"), MIGRACION_SQL, salto_app)

    final_app = leer(app)[0]
    final_db = leer(base)[0]
    final_lg = leer(logica)[0]
    sql = Path("migracion-020.sql")

    controles = [
        ("Estado POR EMPEZAR", "POR EMPEZAR" in final_lg),
        ("La puerta mira vigencia, no sesiones", "POR_EMPEZAR" in final_lg),
        ("Avisa si viene un dia que no es suyo", "OTRO_DIA" in final_lg),
        ("El kiosco ya no descuenta", "marcar NO descuenta" in final_app),
        ("Pantalla de dias sin entrenamiento",
         "def pagina_dias_libres" in final_app),
        ("Dias no laborables en la capa de datos",
         "def marcar_no_laborable" in final_db),
        ("Pausa programada no congela hoy",
         "if desde <= logic.hoy()" in final_db),
        ("Activacion automatica de pausas",
         "def activar_congelamientos" in final_db),
        ("Sesiones por calendario en la migracion",
         "fc_sesiones_transcurridas" in leer(sql)[0] if sql.exists() else False),
        ("Version 3.0", 'VERSION = "3.0"' in final_app),
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
    print("    1. Abre migracion-020.sql (quedo en esta carpeta)")
    print("    2. Copia todo y pegalo en Supabase > SQL Editor > Run")
    print("    3. Recien ahi sube los cambios y reinicia")
    print("")


if __name__ == "__main__":
    if "--revertir" in sys.argv:
        revertir()
    else:
        aplicar()