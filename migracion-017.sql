-- =====================================================================
-- FUTCROSS | Migracion 017 - Precio de lista y descuento
--
-- Guarda el precio de lista junto al que realmente se cobro. La
-- diferencia entre los dos es el descuento, y hasta ahora se perdia:
-- solo quedaba el monto final y no habia forma de saber cuanto se
-- estaba regalando ni quien lo autorizo.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

alter table paquetes
    add column if not exists precio_lista numeric(10,2);

-- Los pedidos que ya existen se toman como vendidos sin descuento
update paquetes set precio_lista = precio where precio_lista is null;

comment on column paquetes.precio_lista is
    'Precio de catalogo al momento de la venta. precio es lo que se cobro.';

-- ---------------------------------------------------------------------
-- La vista expone el descuento ya calculado, para no repetir la cuenta
-- ---------------------------------------------------------------------
drop view if exists v_alumnos_estado cascade;
drop view if exists v_paquetes cascade;

create view v_paquetes as
with base as (
    select p.*,
           coalesce((select count(*) from asistencias s
                     where s.paquete_id = p.id and not s.anulada), 0)::int as sesiones_usadas
    from paquetes p
)
select b.id,
       b.nro_pedido,
       b.alumno_id,
       a.codigo,
       a.nombres,
       a.apellidos,
       (a.nombres || ' ' || a.apellidos) as alumno,
       a.dni,
       a.telefono,
       b.grupo_id,
       coalesce(g.nombre, b.sede, a.sede)      as grupo,
       coalesce(g.sede, b.sede, a.sede)        as sede,
       g.genero,
       g.hora,
       coalesce(b.dias_asiste, g.dias, a.dias_asiste) as dias_asiste,
       a.turno,
       a.horario,
       b.plan_id,
       b.plan_nombre,
       b.sesiones_totales,
       b.sesiones_usadas,
       (b.sesiones_totales - b.sesiones_usadas) as sesiones_restantes,
       b.fecha_pedido,
       b.fecha_inicio,
       b.fecha_fin,
       (b.fecha_fin - hoy_lima())            as dias_restantes,
       b.dias_congelados,
       coalesce(b.precio_lista, b.precio)     as precio_lista,
       b.precio,
       (coalesce(b.precio_lista, b.precio) - b.precio) as descuento,
       case when coalesce(b.precio_lista, 0) > 0
            then round((coalesce(b.precio_lista, b.precio) - b.precio)
                       / b.precio_lista * 100, 1)
            else 0 end                        as descuento_pct,
       b.medio_pago,
       b.pagado,
       b.vendedor,
       b.tipo,
       b.estado,
       b.observacion,
       b.creado_en,
       case
         when b.estado = 'CANCELADO'                  then 'CANCELADO'
         when b.estado = 'CONGELADO'                  then 'CONGELADO'
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
       vp.sesiones_totales, vp.sesiones_usadas, vp.sesiones_restantes,
       vp.dias_restantes, vp.dias_congelados,
       vp.vendedor, vp.tipo,
       vp.precio_lista, vp.precio, vp.descuento, vp.descuento_pct,
       vp.medio_pago,
       coalesce(vp.estado_real, 'SIN PAQUETE') as estado_real
from alumnos a
left join grupos ga on ga.id = a.grupo_id
left join lateral (
    select p.* from v_paquetes p
    where p.alumno_id = a.id
    order by case p.estado_real
               when 'ACTIVO' then 0 when 'CONGELADO' then 1 else 2 end,
             p.fecha_fin desc
    limit 1
) vp on true;

create or replace view v_asistencias as
select s.id, s.fecha, s.hora, s.sede, s.origen, s.anulada,
       s.alumno_id, s.paquete_id, a.codigo,
       (a.nombres || ' ' || a.apellidos) as alumno, a.telefono
from asistencias s
join alumnos a on a.id = s.alumno_id;
