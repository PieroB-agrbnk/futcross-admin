-- =====================================================================
-- FUTCROSS | Migracion 030 - Fechas a medida y quien marco la asistencia
--
-- 1. FECHAS A MEDIDA
--    Para casos excepcionales, como un alumno que viene en fechas
--    acordadas y a cualquier sede: el plan cuenta sus clases solo en esas
--    fechas, no por dias de la semana. Lo demas no cambia: si viene en
--    una fecha que no esta en su lista, cuenta como clase extra, y las
--    pausas y los dias sin entrenamiento siguen corriendo la fecha.
--
-- 2. QUIEN MARCO
--    Cada asistencia guarda el nombre del profe que la marco. Sirve para
--    el reporte de asistencia de cada alumno, cuando alguien dice que un
--    dia no fue.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

alter table asistencias add column if not exists marcado_por text;

create or replace view v_asistencias as
select s.id, s.fecha, s.hora, s.sede, s.origen, s.anulada,
       s.alumno_id, s.paquete_id, a.codigo,
       (a.nombres || ' ' || a.apellidos) as alumno, a.telefono,
       s.marcado_por
from asistencias s
join alumnos a on a.id = s.alumno_id;

create table if not exists fechas_paquete (
    paquete_id uuid not null references paquetes(id) on delete cascade,
    fecha      date not null,
    primary key (paquete_id, fecha)
);

comment on table fechas_paquete is
    'Fechas acordadas de un plan a medida: sus clases cuentan solo en estas fechas.';

-- ---------------------------------------------------------------------
-- Las dos funciones del calendario: si el plan tiene fechas a medida,
-- cuentan esas; si no, los dias de la semana como siempre
-- ---------------------------------------------------------------------
create or replace function fc_sesiones_transcurridas(p_paquete_id uuid)
returns int
language sql stable as $$
    with p as (
        select pq.id, pq.fecha_inicio, pq.fecha_fin, pq.sesiones_totales,
               pq.grupo_id, pq.estado,
               coalesce(pq.dias_asiste, g.dias, a.dias_asiste) as dias
          from paquetes pq
          join alumnos a on a.id = pq.alumno_id
     left join grupos  g on g.id = pq.grupo_id
         where pq.id = p_paquete_id
    ),
    programadas as (
        select d::date as dia
          from p, generate_series(p.fecha_inicio, least(hoy_lima(), p.fecha_fin),
                                  interval '1 day') as d
         where (case when exists (select 1 from fechas_paquete f where f.paquete_id = p.id)
                     then exists (select 1 from fechas_paquete f
                                   where f.paquete_id = p.id and f.fecha = d::date)
                     else extract(dow from d)::int
                          = any(fc_indices_dias(fc_dias_en(p.id, d::date, p.dias)))
                end)
           and not exists (
               select 1 from congelamientos c
                where c.paquete_id = p.id
                  and d::date >= c.fecha_inicio
                  and d::date < coalesce(c.fecha_fin, date '9999-12-31'))
           and not exists (
               select 1 from dias_no_laborables n
                where n.fecha = d::date
                  and (n.grupo_id is null or n.grupo_id = p.grupo_id))
    ),
    extras as (
        -- Vino un dia que no le consumia clase
        select distinct s.fecha as dia
          from p join asistencias s on s.paquete_id = p.id
         where not coalesce(s.anulada, false)
           and s.fecha between p.fecha_inicio and least(hoy_lima(), p.fecha_fin)
           and s.fecha not in (select dia from programadas)
    )
    select case
        when p.estado = 'CANCELADO' then 0
        else least(p.sesiones_totales,
                   (select count(*)::int from programadas)
                   + (select count(*)::int from extras))
        end
      from p;
$$;

-- ---------------------------------------------------------------------
-- 2. Fecha de fin: la clase numero N contando tambien las extra
-- ---------------------------------------------------------------------
create or replace function fc_fin_calculado(p_inicio date, p_sesiones int,
                                            p_dias text, p_grupo uuid,
                                            p_paquete uuid)
returns date
language sql stable as $$
    with programadas as (
        select d::date as dia
          from generate_series(p_inicio, p_inicio + 1500, interval '1 day') as d
         where p_inicio is not null
           and (case when p_paquete is not null
                          and exists (select 1 from fechas_paquete f where f.paquete_id = p_paquete)
                     then exists (select 1 from fechas_paquete f
                                   where f.paquete_id = p_paquete and f.fecha = d::date)
                     else extract(dow from d)::int
                          = any(fc_indices_dias(fc_dias_en(p_paquete, d::date, p_dias)))
                end)
           and not exists (
               select 1 from congelamientos c
                where p_paquete is not null
                  and c.paquete_id = p_paquete
                  and d::date >= c.fecha_inicio
                  and d::date < coalesce(c.fecha_fin, c.fecha_alta_prevista,
                                         date '9999-12-31'))
           and not exists (
               select 1 from dias_no_laborables n
                where n.fecha = d::date
                  and (n.grupo_id is null or n.grupo_id = p_grupo))
    ),
    extras as (
        select distinct s.fecha as dia
          from asistencias s
         where p_paquete is not null
           and s.paquete_id = p_paquete
           and not coalesce(s.anulada, false)
           and s.fecha >= p_inicio
           and s.fecha not in (select dia from programadas)
    )
    select dia
      from (select dia from programadas union all select dia from extras) as todas
     order by dia
    offset greatest(coalesce(p_sesiones, 1), 1) - 1
     limit 1;
$$;

-- Al poner o quitar fechas a medida, se recalcula la fecha de fin
create or replace function fc_trg_fechas_fin()
returns trigger
language plpgsql as $$
begin
    perform fc_recalcular_fin(case when tg_op = 'DELETE'
                                   then old.paquete_id else new.paquete_id end);
    return null;
end $$;

drop trigger if exists trg_fechas_fin on fechas_paquete;
create trigger trg_fechas_fin
    after insert or delete on fechas_paquete
    for each row execute function fc_trg_fechas_fin();

-- Verificacion
select (select count(*) from information_schema.columns
         where table_name = 'asistencias' and column_name = 'marcado_por') as columna_profe,
       (select count(*) from fechas_paquete) as fechas_a_medida_cargadas;
