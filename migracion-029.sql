-- =====================================================================
-- FUTCROSS | Migracion 029 - Clases extra
--
-- EL PROBLEMA
--   Un alumno de lunes y miercoles se mete a la clase del viernes y el
--   profe lo marca. El sistema registraba que vino, pero no le descontaba
--   nada: el plan solo consume clases en los dias que eligio el alumno, asi
--   que esa clase le salia gratis.
--
-- LA REGLA NUEVA
--   Si un alumno entrena un dia que no le consume clase (no es su dia, o
--   era un dia sin entrenamiento), esa asistencia cuenta como una clase
--   extra: se suma a las usadas y su plan termina una clase antes. Si se
--   anula la asistencia, la clase se devuelve.
--
--   Funciona igual se marque por pase de lista, uno por uno o la tablet,
--   porque lo hace la base. La fecha de fin se recalcula sola al marcar.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Clases usadas: las del calendario mas las extra
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
         where extract(dow from d)::int
               = any(fc_indices_dias(fc_dias_en(p.id, d::date, p.dias)))
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
           and extract(dow from d)::int
               = any(fc_indices_dias(fc_dias_en(p_paquete, d::date, p_dias)))
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

-- ---------------------------------------------------------------------
-- 3. Al marcar, anular o borrar una asistencia, se recalcula el fin
-- ---------------------------------------------------------------------
create or replace function fc_trg_asistencia_fin()
returns trigger
language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        perform fc_recalcular_fin(old.paquete_id);
    else
        perform fc_recalcular_fin(new.paquete_id);
        if tg_op = 'UPDATE' and old.paquete_id is distinct from new.paquete_id then
            perform fc_recalcular_fin(old.paquete_id);
        end if;
    end if;
    return null;
end $$;

drop trigger if exists trg_asistencia_fin on asistencias;
create trigger trg_asistencia_fin
    after insert or update of anulada, fecha, paquete_id or delete on asistencias
    for each row execute function fc_trg_asistencia_fin();

-- ---------------------------------------------------------------------
-- 4. Aplicar a lo que ya se marco, dejando constancia
-- ---------------------------------------------------------------------
drop table if exists fin_antes_029;
create temp table fin_antes_029 as
    select id, fecha_fin from paquetes;

update paquetes p
   set fecha_fin = coalesce(
           fc_fin_calculado(p.fecha_inicio, p.sesiones_totales,
                            coalesce(p.dias_asiste,
                                     (select g.dias from grupos g
                                       where g.id = p.grupo_id)),
                            p.grupo_id, p.id),
           p.fecha_fin)
 where not p.fin_manual
   and p.estado <> 'CANCELADO';

-- Verificacion: los alumnos que tienen clases extra
select v.alumno, v.plan_nombre, v.dias_asiste,
       (select string_agg(to_char(s.fecha, 'DD/MM'), ', ' order by s.fecha)
          from asistencias s
         where s.paquete_id = v.id and not coalesce(s.anulada, false)
           and s.fecha <> all (array(
               select d::date from generate_series(v.fecha_inicio, v.fecha_fin, interval '1 day') d
                where extract(dow from d)::int
                      = any(fc_indices_dias(fc_dias_en(v.id, d::date, v.dias_asiste)))))
       ) as clases_extra,
       a.fecha_fin as fin_antes, v.fecha_fin as fin_ahora,
       v.sesiones_usadas, v.sesiones_totales, v.estado_real
  from v_paquetes v
  join fin_antes_029 a on a.id = v.id
 where a.fecha_fin is distinct from v.fecha_fin
 order by v.alumno;
