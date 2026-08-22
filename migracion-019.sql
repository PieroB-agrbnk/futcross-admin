-- =====================================================================
-- FUTCROSS | Migracion 019
--
-- 1. PAGOS PARCIALES
--    Hasta ahora el pago era todo o nada. FutCross a veces cobra la
--    mitad al momento y la otra mitad dentro de 15 dias, y eso no habia
--    donde registrarlo: marcar "Pendiente" hacia que los 120 que si
--    entraron a caja no contaran en ningun reporte.
--
-- 2. CLAVES EN LA BASE
--    Los PIN vivian en la configuracion del servidor, asi que cambiarlos
--    dependia de quien administra el despliegue. Ahora se guardan
--    hasheados en la tabla `config` y se pueden cambiar desde el panel.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Pagos parciales
-- ---------------------------------------------------------------------
alter table paquetes
    add column if not exists monto_entregado numeric(10,2),
    add column if not exists fecha_limite_pago date;

-- Los pedidos que ya existen: si estaban pagados, se entrego todo;
-- si estaban pendientes, no se entrego nada.
update paquetes
   set monto_entregado = case when pagado then precio else 0 end
 where monto_entregado is null;

alter table paquetes alter column monto_entregado set default 0;

comment on column paquetes.monto_entregado is
    'Cuanto pago el cliente hasta ahora. El saldo es precio - monto_entregado.';
comment on column paquetes.fecha_limite_pago is
    'Hasta cuando tiene plazo para completar el saldo.';

-- `pagado` pasa a ser un reflejo del monto entregado, no un dato que se
-- escribe aparte. Con un trigger no puede quedar en "pagado" un pedido
-- al que le falta plata, ni al reves.
create or replace function fc_sincronizar_pagado()
returns trigger
language plpgsql as $$
begin
    new.monto_entregado := coalesce(new.monto_entregado, 0);
    new.pagado := (new.monto_entregado >= coalesce(new.precio, 0));
    return new;
end $$;

drop trigger if exists trg_sincronizar_pagado on paquetes;
create trigger trg_sincronizar_pagado
    before insert or update of monto_entregado, precio, pagado on paquetes
    for each row execute function fc_sincronizar_pagado();

-- Deja consistentes las filas que ya estaban
update paquetes set monto_entregado = coalesce(monto_entregado, 0);

create index if not exists ix_paquetes_por_cobrar
    on paquetes (fecha_limite_pago) where not pagado;

-- ---------------------------------------------------------------------
-- 2. Configuracion: claves de acceso
-- ---------------------------------------------------------------------
create table if not exists config (
    clave           text primary key,
    valor           text not null,
    actualizado_en  timestamptz not null default now(),
    actualizado_por text
);

comment on table config is
    'Configuracion editable desde el panel. Los PIN se guardan hasheados '
    '(pbkdf2), nunca en texto plano.';

-- ---------------------------------------------------------------------
-- 3. Vistas con saldo y estado de pago
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

-- ---------------------------------------------------------------------
-- 4. Verificacion
-- ---------------------------------------------------------------------
select estado_pago, count(*) as pedidos,
       sum(precio) as total, sum(monto_entregado) as cobrado, sum(saldo) as por_cobrar
  from v_paquetes
 group by estado_pago
 order by estado_pago;
