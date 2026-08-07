-- =====================================================================
-- FUTCROSS | Migracion 006
-- Agrega los campos que FutCross maneja en su Excel de clientes:
-- numero de pedido, fecha del pedido, sede, dias que asiste, vendedor
-- y si la venta es nueva o una renovacion.
--
-- Ejecutar TODO en Supabase > SQL Editor > New query > Run.
-- Es idempotente: se puede correr de nuevo sin romper nada.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Numero de pedido correlativo
-- ---------------------------------------------------------------------
create sequence if not exists seq_nro_pedido start 1;

alter table paquetes
    add column if not exists nro_pedido   int,
    add column if not exists fecha_pedido date,
    add column if not exists sede         text,
    add column if not exists dias_asiste  text,
    add column if not exists vendedor     text,
    add column if not exists tipo         text default 'NUEVO';

-- Los paquetes que ya existian reciben su numero y su fecha de pedido
update paquetes set nro_pedido = nextval('seq_nro_pedido') where nro_pedido is null;
update paquetes set fecha_pedido = fecha_inicio where fecha_pedido is null;
update paquetes set tipo = 'NUEVO' where tipo is null;

-- De aca en adelante el numero se asigna solo
alter table paquetes alter column nro_pedido set default nextval('seq_nro_pedido');
alter table paquetes alter column fecha_pedido set default hoy_lima();

-- La secuencia arranca despues del maximo que ya exista
select setval('seq_nro_pedido',
              coalesce((select max(nro_pedido) from paquetes), 0) + 1,
              false);

-- Solo dos tipos de venta posibles
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'paquetes_tipo_check') then
        alter table paquetes add constraint paquetes_tipo_check
            check (tipo in ('NUEVO', 'RENOVACION'));
    end if;
end $$;

create index if not exists ix_paquetes_pedido on paquetes (nro_pedido desc);

-- ---------------------------------------------------------------------
-- 2. Dias de asistencia habituales del alumno
-- ---------------------------------------------------------------------
alter table alumnos
    add column if not exists dias_asiste text,
    add column if not exists turno       text;

-- ---------------------------------------------------------------------
-- 3. Vistas: se recrean porque cambiaron las columnas
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
       coalesce(b.sede, a.sede)               as sede,
       coalesce(b.dias_asiste, a.dias_asiste) as dias_asiste,
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
       b.precio,
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
join alumnos a on a.id = b.alumno_id;

create view v_alumnos_estado as
select a.id            as alumno_id,
       a.codigo,
       a.nombres,
       a.apellidos,
       (a.nombres || ' ' || a.apellidos) as alumno,
       a.dni,
       a.telefono,
       a.email,
       a.sede,
       a.turno,
       a.dias_asiste,
       a.horario,
       a.fecha_inscripcion,
       a.activo,
       vp.id            as paquete_id,
       vp.nro_pedido,
       vp.plan_nombre,
       vp.fecha_pedido,
       vp.fecha_inicio,
       vp.fecha_fin,
       vp.sesiones_totales,
       vp.sesiones_usadas,
       vp.sesiones_restantes,
       vp.dias_restantes,
       vp.dias_congelados,
       vp.vendedor,
       vp.tipo,
       vp.precio,
       vp.medio_pago,
       coalesce(vp.estado_real, 'SIN PAQUETE') as estado_real
from alumnos a
left join lateral (
    select p.* from v_paquetes p
    where p.alumno_id = a.id
    order by case p.estado_real
               when 'ACTIVO'    then 0
               when 'CONGELADO' then 1
               else 2
             end,
             p.fecha_fin desc
    limit 1
) vp on true;

create or replace view v_asistencias as
select s.id,
       s.fecha,
       s.hora,
       s.sede,
       s.origen,
       s.anulada,
       s.alumno_id,
       s.paquete_id,
       a.codigo,
       (a.nombres || ' ' || a.apellidos) as alumno,
       a.telefono
from asistencias s
join alumnos a on a.id = s.alumno_id;

-- ---------------------------------------------------------------------
-- 4. Planes que FutCross vende de verdad
-- ---------------------------------------------------------------------
insert into planes (nombre, sesiones, vigencia_dias, precio, descripcion) values
  ('PLAN BASICO 36 SESIONES 3 MESES PROMO', 36, 90, 590.00,
   'Promocion trimestral, 3 sesiones por semana')
on conflict (nombre) do nothing;
