-- =====================================================================
-- FUTCROSS | Migracion 024
--
-- UNA SOLA REGLA PARA LA FECHA DE FIN
--   La fecha de fin se calculaba en varios lugares con reglas distintas
--   y ninguno descontaba los feriados. Resultado: si se marcaba un dia
--   sin entrenamiento, el plan vencia igual en la fecha vieja y al
--   alumno le quedaba una clase sin usar. Con los congelamientos pasaba
--   algo parecido.
--
--   Desde ahora la fecha de fin la calcula la base, con la misma regla
--   que cuenta las clases: los dias que eligio el alumno, saltando los
--   dias sin entrenamiento y los dias en pausa. Y se recalcula sola cuando
--   se marca o quita un feriado, cuando se congela o reactiva, y cuando se
--   edita el pedido.
--
-- EL DIA DE ALTA CUENTA
--   Un congelamiento cubre desde su fecha de inicio hasta el dia ANTERIOR
--   a la fecha de alta. La fecha de alta es el dia que el alumno vuelve,
--   asi que ese dia ya cuenta como clase.
--
-- FECHA DE FIN A MANO
--   Si se fija la fecha de fin a mano desde Editar pedido, la base no la
--   vuelve a tocar, y el plan sigue activo hasta esa fecha.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

alter table paquetes
    add column if not exists fin_manual boolean not null default false,
    add column if not exists fin_manual_motivo text;

-- ---------------------------------------------------------------------
-- 1. Clases transcurridas (misma funcion, el alta ahora cuenta)
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

-- ---------------------------------------------------------------------
-- 2. La fecha de la ultima clase, con la misma regla
--    Devuelve null si no se puede saber (dias vacios, o una pausa abierta
--    sin fecha de vuelta): en ese caso se deja la fecha que habia.
-- ---------------------------------------------------------------------
create or replace function fc_fin_calculado(p_inicio date, p_sesiones int,
                                            p_dias text, p_grupo uuid,
                                            p_paquete uuid)
returns date
language sql stable as $$
    select d::date
      from generate_series(p_inicio, p_inicio + 1500, interval '1 day') as d
     where p_inicio is not null
       and extract(dow from d)::int = any(fc_indices_dias(p_dias))
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

create or replace function fc_recalcular_fin(p_paquete uuid)
returns void
language sql as $$
    update paquetes p
       set fecha_fin = coalesce(
               fc_fin_calculado(p.fecha_inicio, p.sesiones_totales,
                                coalesce(p.dias_asiste,
                                         (select g.dias from grupos g
                                           where g.id = p.grupo_id)),
                                p.grupo_id, p.id),
               p.fecha_fin)
     where p.id = p_paquete
       and not p.fin_manual
       and p.estado <> 'CANCELADO';
$$;

-- ---------------------------------------------------------------------
-- 3. Recalculo automatico
-- ---------------------------------------------------------------------

-- a) Al crear o editar un pedido
create or replace function fc_trg_paquete_fin()
returns trigger
language plpgsql as $$
declare
    v_fin date;
begin
    if new.fin_manual or new.estado = 'CANCELADO' then
        return new;
    end if;
    v_fin := fc_fin_calculado(
        new.fecha_inicio, new.sesiones_totales,
        coalesce(new.dias_asiste,
                 (select g.dias from grupos g where g.id = new.grupo_id)),
        new.grupo_id, new.id);
    if v_fin is not null then
        new.fecha_fin := v_fin;
    end if;
    return new;
end $$;

drop trigger if exists trg_paquete_fin on paquetes;
create trigger trg_paquete_fin
    before insert or update of fecha_inicio, sesiones_totales, dias_asiste,
                               grupo_id, fin_manual
    on paquetes
    for each row execute function fc_trg_paquete_fin();

-- b) Al congelar, reactivar o borrar un congelamiento
create or replace function fc_trg_congelamiento_fin()
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

drop trigger if exists trg_congelamiento_fin on congelamientos;
create trigger trg_congelamiento_fin
    after insert or update or delete on congelamientos
    for each row execute function fc_trg_congelamiento_fin();

-- c) Al marcar o quitar un dia sin entrenamiento
create or replace function fc_trg_no_laborable_fin()
returns trigger
language plpgsql as $$
declare
    v_fecha date;
    v_grupo uuid;
    r       record;
begin
    if tg_op = 'DELETE' then
        v_fecha := old.fecha;  v_grupo := old.grupo_id;
    else
        v_fecha := new.fecha;  v_grupo := new.grupo_id;
    end if;

    for r in
        select p.id from paquetes p
         where p.fecha_inicio <= v_fecha
           and p.fecha_fin    >= v_fecha
           and (v_grupo is null or p.grupo_id = v_grupo)
    loop
        perform fc_recalcular_fin(r.id);
    end loop;
    return null;
end $$;

drop trigger if exists trg_no_laborable_fin on dias_no_laborables;
create trigger trg_no_laborable_fin
    after insert or delete on dias_no_laborables
    for each row execute function fc_trg_no_laborable_fin();

-- ---------------------------------------------------------------------
-- 4. Reactivacion automatica: cierra la pausa y deja que la base calcule
--    la fecha de fin. Antes calculaba lo que quedaba contando asistencias,
--    que era el modelo viejo.
-- ---------------------------------------------------------------------
create or replace function fc_reactivar_previstos()
returns int
language plpgsql as $$
declare
    r       record;
    v_dias  int;
    v_total int := 0;
begin
    for r in
        select c.id, c.paquete_id, c.fecha_inicio, c.fecha_alta_prevista
          from congelamientos c
         where c.activo
           and c.fecha_alta_prevista is not null
           and c.fecha_alta_prevista <= hoy_lima()
    loop
        v_dias := greatest(r.fecha_alta_prevista - r.fecha_inicio, 0);

        update paquetes
           set estado = 'ACTIVO',
               dias_congelados = coalesce(dias_congelados, 0) + v_dias
         where id = r.paquete_id
           and estado = 'CONGELADO';

        update congelamientos
           set activo = false,
               fecha_fin = r.fecha_alta_prevista,
               dias_aplicados = v_dias
         where id = r.id;

        v_total := v_total + 1;
    end loop;
    return v_total;
end $$;

-- ---------------------------------------------------------------------
-- 5. Vistas: el estado respeta la fecha de fin puesta a mano
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
       b.fin_manual, b.fin_manual_motivo,
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
         when b.fin_manual and hoy_lima() <= b.fecha_fin then 'ACTIVO'
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
-- 6. Recalcular los pedidos que ya existen, dejando constancia
-- ---------------------------------------------------------------------
drop table if exists fin_antes;
create temp table fin_antes as
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

select v.alumno, v.plan_nombre, a.fecha_fin as fin_antes,
       v.fecha_fin as fin_ahora, v.sesiones_usadas, v.sesiones_totales,
       v.estado_real
  from v_paquetes v
  join fin_antes a on a.id = v.id
 order by (a.fecha_fin is distinct from v.fecha_fin) desc, v.fecha_inicio desc;
