-- =====================================================================
-- FUTCROSS | Migracion 026 - Surco deja los lunes desde octubre
--
-- EL PROBLEMA
--   Desde el 1 de octubre Surco entrena solo miercoles y viernes. No
--   basta con cambiar los dias del grupo: los alumnos que ya tienen plan
--   corriendo contaron los lunes hasta setiembre. Si se cambiaran los
--   dias de golpe, el sistema recalcularia tambien el pasado y les
--   descuadraria las clases ya hechas.
--
-- LA SOLUCION
--   Cada plan guarda con que dias venia HASTA una fecha, y desde esa fecha
--   usa los nuevos. Lo entrenado hasta setiembre queda como estaba, y
--   desde octubre corre con miercoles y viernes. Nadie pierde clases: el
--   que tenia tres dias por semana pasa a dos y su plan dura mas.
--
--   Los dias de cada alumno se ajustan asi: se quedan los que siguen
--   existiendo y se completa con los nuevos del grupo hasta tener la misma
--   cantidad por semana que antes, si se puede. LUN MIE pasa a MIE VIE;
--   LUN MIE VIE pasa a MIE VIE; MIE VIE queda igual.
--
-- ADEMAS
--   Oculta los planes de 6 meses, que ya no se ofrecen, y el plan
--   repetido "PLAN PREMIUM". No se borran: los vendidos siguen funcionando.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

create table if not exists historial_dias (
    paquete_id uuid not null references paquetes(id) on delete cascade,
    hasta      date not null,
    dias       text not null,
    creado_en  timestamptz not null default now(),
    primary key (paquete_id, hasta)
);

comment on table historial_dias is
    'Dias con los que entrenaba un plan antes de un cambio de horario. '
    'Antes de `hasta` rigen estos dias; desde `hasta`, los del plan.';

-- ---------------------------------------------------------------------
-- 1. Que dias rigen para un plan en una fecha dada
-- ---------------------------------------------------------------------
create or replace function fc_dias_en(p_paquete uuid, p_dia date, p_actual text)
returns text
language sql stable as $$
    select coalesce(
        (select h.dias from historial_dias h
          where h.paquete_id = p_paquete and p_dia < h.hasta
          order by h.hasta limit 1),
        p_actual);
$$;

-- ---------------------------------------------------------------------
-- 2. Las dos funciones del calendario ahora miran los dias de cada fecha
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
    )
    select case
        when p.estado = 'CANCELADO' then 0
        else least(
            p.sesiones_totales,
            (select count(*)::int
               from generate_series(p.fecha_inicio,
                                    least(hoy_lima(), p.fecha_fin),
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
            ))
        end
      from p;
$$;

create or replace function fc_fin_calculado(p_inicio date, p_sesiones int,
                                            p_dias text, p_grupo uuid,
                                            p_paquete uuid)
returns date
language sql stable as $$
    select d::date
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
     order by d
    offset greatest(coalesce(p_sesiones, 1), 1) - 1
     limit 1;
$$;

-- Si se agrega o borra un cambio de dias, se recalcula la fecha de fin
create or replace function fc_trg_historial_fin()
returns trigger
language plpgsql as $$
begin
    perform fc_recalcular_fin(case when tg_op = 'DELETE'
                                   then old.paquete_id else new.paquete_id end);
    return null;
end $$;

drop trigger if exists trg_historial_fin on historial_dias;
create trigger trg_historial_fin
    after insert or delete on historial_dias
    for each row execute function fc_trg_historial_fin();

-- ---------------------------------------------------------------------
-- 3. Ajustar los dias de un alumno al nuevo horario del grupo
-- ---------------------------------------------------------------------
create or replace function fc_ajustar_dias(p_viejos text, p_nuevos text)
returns text
language plpgsql immutable as $$
declare
    nuevos text[] := array_remove(string_to_array(upper(trim(coalesce(p_nuevos, ''))), ' '), '');
    viejos text[] := array_remove(string_to_array(upper(trim(coalesce(p_viejos, ''))), ' '), '');
    quedan text[] := '{}';
    meta   int;
    d      text;
begin
    if coalesce(array_length(viejos, 1), 0) = 0 then
        return array_to_string(nuevos, ' ');
    end if;
    meta := least(array_length(viejos, 1), coalesce(array_length(nuevos, 1), 0));
    -- Primero los dias que ya tenia y siguen existiendo
    foreach d in array nuevos loop
        if d = any(viejos) then
            quedan := quedan || d;
        end if;
    end loop;
    -- Despues se completa con los del grupo, hasta la misma cantidad
    foreach d in array nuevos loop
        exit when coalesce(array_length(quedan, 1), 0) >= meta;
        if not (d = any(quedan)) then
            quedan := quedan || d;
        end if;
    end loop;
    return array_to_string(array(select x from unnest(nuevos) as x
                                  where x = any(quedan)), ' ');
end $$;

-- ---------------------------------------------------------------------
-- 4. Cambiar los dias de un grupo desde una fecha
--    Sirve para este cambio y para los que vengan (horario de verano).
-- ---------------------------------------------------------------------
create or replace function fc_cambiar_dias_grupo(p_grupo uuid, p_desde date,
                                                 p_nuevos text)
returns int
language plpgsql as $$
declare
    r        record;
    v_nuevos text;
    v_total  int := 0;
begin
    for r in
        select p.id, p.fecha_inicio, coalesce(p.dias_asiste, g.dias) as dias
          from paquetes p
          join grupos g on g.id = p.grupo_id
         where p.grupo_id = p_grupo
           and p.estado <> 'CANCELADO'
           and p.fecha_fin >= p_desde
    loop
        v_nuevos := fc_ajustar_dias(r.dias, p_nuevos);
        continue when v_nuevos = r.dias;

        -- Lo anterior a la fecha queda con los dias de siempre
        if r.fecha_inicio < p_desde then
            insert into historial_dias (paquete_id, hasta, dias)
                 values (r.id, p_desde, r.dias)
            on conflict (paquete_id, hasta) do nothing;
        end if;
        update paquetes set dias_asiste = v_nuevos where id = r.id;
        v_total := v_total + 1;
    end loop;

    update alumnos a
       set dias_asiste = fc_ajustar_dias(coalesce(a.dias_asiste, g.dias), p_nuevos)
      from grupos g
     where g.id = a.grupo_id and a.grupo_id = p_grupo;

    update grupos
       set dias = p_nuevos,
           dias_por_semana = coalesce(array_length(
               array_remove(string_to_array(trim(p_nuevos), ' '), ''), 1), 0)
     where id = p_grupo;

    return v_total;
end $$;

-- ---------------------------------------------------------------------
-- 5. Surco: miercoles y viernes 9 p.m. desde el 1 de octubre de 2026
-- ---------------------------------------------------------------------
drop table if exists surco_antes;
create temp table surco_antes as
    select p.id, coalesce(p.dias_asiste, g.dias) as dias, p.fecha_fin
      from paquetes p join grupos g on g.id = p.grupo_id
     where g.sede = 'SURCO';

select fc_cambiar_dias_grupo(id, date '2026-10-01', 'MIE VIE')
  from grupos where sede = 'SURCO';

update grupos set hora = 'MIE y VIE 9:00 PM' where sede = 'SURCO';

-- ---------------------------------------------------------------------
-- 6. Planes que ya no se ofrecen
-- ---------------------------------------------------------------------
update planes set activo = false
 where nombre in ('PLAN BASICO 6 MESES', 'PLAN PREMIUM 6 MESES', 'PLAN PREMIUM');

-- ---------------------------------------------------------------------
-- 7. Verificacion: alumnos de Surco, como estaban y como quedan
-- ---------------------------------------------------------------------
select a.nombres || ' ' || a.apellidos as alumno, p.plan_nombre,
       s.dias as dias_hasta_setiembre, p.dias_asiste as dias_desde_octubre,
       s.fecha_fin as fin_antes, p.fecha_fin as fin_ahora,
       v.sesiones_usadas, p.sesiones_totales
  from surco_antes s
  join paquetes p on p.id = s.id
  join alumnos a on a.id = p.alumno_id
  join v_paquetes v on v.id = p.id
 where p.estado <> 'CANCELADO' and p.fecha_fin >= date '2026-09-01'
 order by a.apellidos, a.nombres;
