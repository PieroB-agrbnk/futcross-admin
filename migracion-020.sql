-- =====================================================================
-- FUTCROSS | Migracion 020 - El plan corre por calendario
--
-- CAMBIO DE FONDO
--   Hasta ahora una sesion se consumia cuando el alumno marcaba
--   asistencia. FutCross no funciona asi: el plan corre desde el dia 1
--   y las sesiones se cuentan vaya o no vaya. La lista de los profes es
--   para control, no para descontar.
--
--   Desde esta migracion, `sesiones_usadas` es cuantas de sus fechas ya
--   pasaron, descontando los dias que estuvo congelado y los dias que
--   la academia no abrio. Las asistencias siguen guardandose, pero como
--   registro de quien vino, no como contador.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. 'LUN MIE VIE' -> {1,3,5}   (en Postgres domingo = 0)
-- ---------------------------------------------------------------------
create or replace function fc_indices_dias(p_dias text)
returns int[]
language sql immutable as $$
    select array_agg(case d
               when 'LUN' then 1 when 'MAR' then 2 when 'MIE' then 3
               when 'JUE' then 4 when 'VIE' then 5 when 'SAB' then 6
               when 'DOM' then 0 end)
      from unnest(string_to_array(upper(trim(coalesce(p_dias, ''))), ' ')) as d
     where d <> '';
$$;

-- ---------------------------------------------------------------------
-- 2. Dias que la academia no abrio
--    grupo_id nulo = no abrio ninguna sede ese dia (feriado).
--    Con grupo, solo ese grupo (cancha ocupada, por ejemplo).
-- ---------------------------------------------------------------------
create table if not exists dias_no_laborables (
    id        uuid primary key default gen_random_uuid(),
    fecha     date not null,
    grupo_id  uuid references grupos(id),
    motivo    text,
    creado_en timestamptz not null default now()
);

create unique index if not exists uq_no_laborable
    on dias_no_laborables (fecha, coalesce(grupo_id, '00000000-0000-0000-0000-000000000000'::uuid));

comment on table dias_no_laborables is
    'Dias en que no se entreno. Esas sesiones no se le cuentan a nadie y '
    'el plan se corre al siguiente dia de entrenamiento del grupo.';

-- ---------------------------------------------------------------------
-- 3. Cuantas sesiones ya transcurrieron
--
--    Cuenta los dias de entrenamiento entre el inicio y hoy, restando
--    los que cayeron dentro de un congelamiento y los que la academia
--    no abrio. Nunca pasa del total del paquete.
-- ---------------------------------------------------------------------
create or replace function fc_sesiones_transcurridas(p_paquete_id uuid)
returns int
language sql stable as $$
    with p as (
        select pq.id, pq.fecha_inicio, pq.fecha_fin, pq.sesiones_totales,
               pq.grupo_id, pq.estado,
               fc_indices_dias(coalesce(pq.dias_asiste, g.dias, a.dias_asiste)) as idx
          from paquetes pq
          join alumnos a on a.id = pq.alumno_id
     left join grupos  g on g.id = pq.grupo_id
         where pq.id = p_paquete_id
    )
    select case
        when p.idx is null then 0
        when p.estado = 'CANCELADO' then 0
        else least(
            p.sesiones_totales,
            (select count(*)::int
               from p, generate_series(p.fecha_inicio,
                                       least(hoy_lima(), p.fecha_fin),
                                       interval '1 day') as d
              where extract(dow from d)::int = any(p.idx)
                -- dias que estuvo congelado
                and not exists (
                    select 1 from congelamientos c
                     where c.paquete_id = p.id
                       and d::date >= c.fecha_inicio
                       and d::date <= coalesce(c.fecha_fin, date '9999-12-31'))
                -- dias que la academia no abrio
                and not exists (
                    select 1 from dias_no_laborables n
                     where n.fecha = d::date
                       and (n.grupo_id is null or n.grupo_id = p.grupo_id))
            ))
        end
      from p;
$$;

-- ---------------------------------------------------------------------
-- 4. Activar los congelamientos programados a futuro
--
--    Al registrar un viaje que empieza en dos semanas, el paquete no
--    puede quedar congelado desde hoy: la persona todavia entrena. Esto
--    lo pone en pausa recien cuando llega la fecha.
-- ---------------------------------------------------------------------
create or replace function fc_activar_congelamientos()
returns int
language plpgsql as $$
declare
    n int;
begin
    with debidos as (
        select distinct c.paquete_id
          from congelamientos c
          join paquetes p on p.id = c.paquete_id
         where c.activo
           and c.fecha_inicio <= hoy_lima()
           and coalesce(c.fecha_fin, date '9999-12-31') >= hoy_lima()
           and p.estado = 'ACTIVO'
    )
    update paquetes set estado = 'CONGELADO'
     where id in (select paquete_id from debidos);
    get diagnostics n = row_count;
    return n;
end $$;

-- ---------------------------------------------------------------------
-- 5. Vistas
--    sesiones_usadas pasa a salir del calendario.
--    asistencias_registradas queda como el conteo de quien vino: sigue
--    sirviendo para ver constancia, pero ya no descuenta.
-- ---------------------------------------------------------------------
drop view if exists v_alumnos_estado cascade;
drop view if exists v_paquetes cascade;

create view v_paquetes as
with base as (
    select p.*,
           fc_sesiones_transcurridas(p.id) as sesiones_usadas,
           coalesce((select count(*) from asistencias s
                     where s.paquete_id = p.id and not s.anulada), 0)::int
               as asistencias_registradas
    from paquetes p
)
select b.id,
       b.nro_pedido,
       b.alumno_id,
       a.codigo, a.nombres, a.apellidos,
       (a.nombres || ' ' || a.apellidos) as alumno,
       a.dni, a.telefono,
       b.grupo_id,
       coalesce(g.nombre, b.sede, a.sede)      as grupo,
       coalesce(g.sede, b.sede, a.sede)        as sede,
       g.genero, g.hora,
       coalesce(b.dias_asiste, g.dias, a.dias_asiste) as dias_asiste,
       a.turno, a.horario,
       b.plan_id, b.plan_nombre,
       b.sesiones_totales,
       b.sesiones_usadas,
       b.asistencias_registradas,
       (b.sesiones_totales - b.sesiones_usadas) as sesiones_restantes,
       b.fecha_pedido, b.fecha_inicio, b.fecha_fin,
       (b.fecha_fin - hoy_lima())            as dias_restantes,
       b.dias_congelados,
       coalesce(b.precio_lista, b.precio)     as precio_lista,
       b.precio,
       (coalesce(b.precio_lista, b.precio) - b.precio) as descuento,
       case when coalesce(b.precio_lista, 0) > 0
            then round((coalesce(b.precio_lista, b.precio) - b.precio)
                       / b.precio_lista * 100, 1)
            else 0 end                        as descuento_pct,
       coalesce(b.monto_entregado, 0)         as monto_entregado,
       (b.precio - coalesce(b.monto_entregado, 0)) as saldo,
       b.fecha_limite_pago,
       case
         when coalesce(b.monto_entregado, 0) >= b.precio then 'PAGADO'
         when coalesce(b.monto_entregado, 0) > 0         then 'PARCIAL'
         else 'PENDIENTE'
       end                                    as estado_pago,
       case
         when coalesce(b.monto_entregado, 0) >= b.precio then null
         when b.fecha_limite_pago is null                then null
         else (b.fecha_limite_pago - hoy_lima())
       end                                    as dias_para_pagar,
       b.medio_pago, b.pagado, b.vendedor, b.tipo,
       b.estado, b.observacion, b.creado_en,
       case
         when b.estado = 'CANCELADO'                  then 'CANCELADO'
         when b.estado = 'CONGELADO'                  then 'CONGELADO'
         when hoy_lima() < b.fecha_inicio             then 'POR EMPEZAR'
         when b.sesiones_usadas >= b.sesiones_totales then 'AGOTADO'
         when hoy_lima() > b.fecha_fin                then 'VENCIDO'
         else 'ACTIVO'
       end as estado_real
from base b
join alumnos a on a.id = b.alumno_id
left join grupos g on g.id = b.grupo_id;

create view v_alumnos_estado as
select a.id            as alumno_id,
       a.codigo, a.nombres, a.apellidos,
       (a.nombres || ' ' || a.apellidos) as alumno,
       a.dni, a.telefono, a.email,
       a.grupo_id,
       ga.nombre       as grupo,
       coalesce(ga.sede, a.sede)        as sede,
       ga.genero, ga.hora,
       coalesce(vp.dias_asiste, ga.dias, a.dias_asiste) as dias_asiste,
       a.turno, a.horario, a.fecha_inscripcion, a.activo,
       vp.id            as paquete_id,
       vp.nro_pedido, vp.plan_nombre, vp.fecha_pedido,
       vp.fecha_inicio, vp.fecha_fin,
       vp.sesiones_totales, vp.sesiones_usadas, vp.asistencias_registradas,
       vp.sesiones_restantes, vp.dias_restantes, vp.dias_congelados,
       vp.vendedor, vp.tipo,
       vp.precio_lista, vp.precio, vp.descuento, vp.descuento_pct,
       vp.monto_entregado, vp.saldo, vp.fecha_limite_pago,
       vp.estado_pago, vp.dias_para_pagar,
       vp.medio_pago,
       coalesce(vp.estado_real, 'SIN PAQUETE') as estado_real
from alumnos a
left join grupos ga on ga.id = a.grupo_id
left join lateral (
    select p.* from v_paquetes p
    where p.alumno_id = a.id
    order by case p.estado_real
               when 'ACTIVO' then 0 when 'POR EMPEZAR' then 1
               when 'CONGELADO' then 2 else 3 end,
             p.fecha_fin desc
    limit 1
) vp on true;

create or replace view v_asistencias as
select s.id, s.fecha, s.hora, s.sede, s.origen, s.anulada,
       s.alumno_id, s.paquete_id, a.codigo,
       (a.nombres || ' ' || a.apellidos) as alumno, a.telefono
from asistencias s
join alumnos a on a.id = s.alumno_id;

-- ---------------------------------------------------------------------
-- 6. La tarea nocturna tambien activa los congelamientos programados
-- ---------------------------------------------------------------------
do $$
begin
    perform cron.unschedule('futcross-congelar')
      where exists (select 1 from cron.job where jobname = 'futcross-congelar');
    perform cron.schedule('futcross-congelar', '10 5 * * *',
                          'select fc_activar_congelamientos();');
exception when others then
    raise notice 'pg_cron no disponible (%). Corre igual al abrir el panel.', sqlerrm;
end $$;

-- ---------------------------------------------------------------------
-- 7. Verificacion
-- ---------------------------------------------------------------------
select fc_activar_congelamientos() as congelamientos_activados;

select alumno, plan_nombre, fecha_inicio, fecha_fin,
       sesiones_usadas, sesiones_totales, sesiones_restantes,
       asistencias_registradas, estado_real
  from v_paquetes
 order by fecha_inicio desc
 limit 20;
