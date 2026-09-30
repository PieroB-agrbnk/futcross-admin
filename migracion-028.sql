-- =====================================================================
-- FUTCROSS | Migracion 028 - Planes viejos cargados despues del cambio
--
-- EL PROBLEMA
--   La migracion 026 corrigio a los alumnos de Surco que ya estaban en el
--   sistema. Pero si hoy se registra a alguien cuyo plan empezo en
--   setiembre, el grupo ya solo tiene miercoles y viernes, y el plan se
--   calculaba entero con esos dos dias: se saltaba los lunes de setiembre
--   que si entreno. Un premium del lunes 21/09 salia hasta el 30/10 y
--   debia terminar el 23/10.
--
-- LA SOLUCION
--   El grupo guarda sus cambios de horario. Cualquier plan que empiece
--   antes de un cambio, se registre cuando se registre (inscripcion,
--   venta, carga masiva), recibe solo los dias de antes hasta esa fecha.
--   Por defecto se toman los del grupo segun la frecuencia del plan: el
--   premium, lunes miercoles y viernes; el basico, los dos que tiene hoy.
--   Si en realidad iba otros dias, se corrige en Editar un pedido.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

create table if not exists cambios_grupo (
    grupo_id     uuid not null references grupos(id) on delete cascade,
    desde        date not null,
    dias_antes   text not null,
    dias_despues text not null,
    creado_en    timestamptz not null default now(),
    primary key (grupo_id, desde)
);

comment on table cambios_grupo is
    'Cambios de horario de cada grupo: antes de `desde` entrenaba dias_antes.';

-- El cambio de Surco del 1 de octubre
insert into cambios_grupo (grupo_id, desde, dias_antes, dias_despues)
select id, date '2026-10-01', 'LUN MIE VIE', 'MIE VIE'
  from grupos where sede = 'SURCO'
on conflict (grupo_id, desde) do nothing;

-- ---------------------------------------------------------------------
-- 1. Los dias que un plan tenia antes del cambio, por defecto
--    Se quedan los de hoy que tambien existian antes, y se completa con
--    los de antes hasta la frecuencia del plan.
-- ---------------------------------------------------------------------
create or replace function fc_dias_previos(p_actual text, p_antes text,
                                           p_frecuencia int)
returns text
language plpgsql immutable as $$
declare
    actual text[] := array_remove(string_to_array(upper(trim(coalesce(p_actual, ''))), ' '), '');
    antes  text[] := array_remove(string_to_array(upper(trim(coalesce(p_antes, ''))), ' '), '');
    quedan text[] := '{}';
    meta   int;
    d      text;
begin
    if coalesce(array_length(antes, 1), 0) = 0 then
        return p_actual;
    end if;
    meta := least(coalesce(p_frecuencia, array_length(actual, 1), 0),
                  array_length(antes, 1));
    foreach d in array antes loop
        if d = any(actual) then
            quedan := quedan || d;
        end if;
    end loop;
    foreach d in array antes loop
        exit when coalesce(array_length(quedan, 1), 0) >= meta;
        if not (d = any(quedan)) then
            quedan := quedan || d;
        end if;
    end loop;
    return array_to_string(array(select x from unnest(antes) as x
                                  where x = any(quedan)), ' ');
end $$;

-- ---------------------------------------------------------------------
-- 2. Al registrar un plan que empieza antes de un cambio, se le pone
--    el historial solo
-- ---------------------------------------------------------------------
create or replace function fc_trg_paquete_historial()
returns trigger
language plpgsql as $$
declare
    c       record;
    v_freq  int;
    v_dias  text;
    v_prev  text;
begin
    if new.grupo_id is null or new.fecha_inicio is null then
        return null;
    end if;
    v_dias := coalesce(new.dias_asiste,
                       (select g.dias from grupos g where g.id = new.grupo_id));
    v_freq := (select pl.dias_por_semana from planes pl where pl.id = new.plan_id);
    for c in
        select * from cambios_grupo
         where grupo_id = new.grupo_id and desde > new.fecha_inicio
    loop
        v_prev := fc_dias_previos(v_dias, c.dias_antes, v_freq);
        if v_prev is distinct from v_dias then
            insert into historial_dias (paquete_id, hasta, dias)
                 values (new.id, c.desde, v_prev)
            on conflict (paquete_id, hasta) do nothing;
        end if;
    end loop;
    return null;
end $$;

drop trigger if exists trg_paquete_historial on paquetes;
create trigger trg_paquete_historial
    after insert or update of fecha_inicio, grupo_id on paquetes
    for each row execute function fc_trg_paquete_historial();

-- Si se corrige el historial a mano (upsert), tambien se recalcula el fin
drop trigger if exists trg_historial_fin on historial_dias;
create trigger trg_historial_fin
    after insert or update or delete on historial_dias
    for each row execute function fc_trg_historial_fin();

-- ---------------------------------------------------------------------
-- 3. Futuros cambios de horario quedan registrados en el grupo
-- ---------------------------------------------------------------------
create or replace function fc_cambiar_dias_grupo(p_grupo uuid, p_desde date,
                                                 p_nuevos text)
returns int
language plpgsql as $$
declare
    r        record;
    v_nuevos text;
    v_total  int := 0;
    v_antes  text;
begin
    select dias into v_antes from grupos where id = p_grupo;
    if v_antes is distinct from p_nuevos then
        insert into cambios_grupo (grupo_id, desde, dias_antes, dias_despues)
             values (p_grupo, p_desde, v_antes, p_nuevos)
        on conflict (grupo_id, desde) do nothing;
    end if;

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
-- 4. Corregir los planes que ya se cargaron con el error
-- ---------------------------------------------------------------------
drop table if exists corregidos;
create temp table corregidos as
    select p.id, p.fecha_fin as fin_antes
      from paquetes p
      join cambios_grupo c on c.grupo_id = p.grupo_id and c.desde > p.fecha_inicio
     where p.estado <> 'CANCELADO'
       and not exists (select 1 from historial_dias h
                        where h.paquete_id = p.id and h.hasta = c.desde)
       and fc_dias_previos(coalesce(p.dias_asiste, (select g.dias from grupos g where g.id = p.grupo_id)),
                           c.dias_antes,
                           (select pl.dias_por_semana from planes pl where pl.id = p.plan_id))
           is distinct from coalesce(p.dias_asiste, (select g.dias from grupos g where g.id = p.grupo_id));

insert into historial_dias (paquete_id, hasta, dias)
select p.id, c.desde,
       fc_dias_previos(coalesce(p.dias_asiste, g.dias), c.dias_antes, pl.dias_por_semana)
  from corregidos k
  join paquetes p on p.id = k.id
  join grupos g on g.id = p.grupo_id
  join cambios_grupo c on c.grupo_id = p.grupo_id and c.desde > p.fecha_inicio
  left join planes pl on pl.id = p.plan_id
on conflict (paquete_id, hasta) do nothing;

-- Verificacion: los planes que se corrigieron
select a.nombres || ' ' || a.apellidos as alumno, p.plan_nombre, p.fecha_inicio,
       h.dias as dias_hasta_setiembre, p.dias_asiste as dias_desde_octubre,
       k.fin_antes, p.fecha_fin as fin_ahora
  from corregidos k
  join paquetes p on p.id = k.id
  join alumnos a on a.id = p.alumno_id
  left join historial_dias h on h.paquete_id = p.id
 order by a.apellidos, a.nombres;
