-- =====================================================================
-- FUTCROSS | Migracion 009 - Grupos de entrenamiento y calendario real
--
-- Cambia la forma de calcular el vencimiento. Antes el plan duraba
-- "30 dias corridos". Ahora el plan dura hasta que se acaban las sesiones,
-- contando solo los dias que ese grupo entrena.
--
-- Un premium de 12 sesiones que arranca el lunes 3 de agosto en el grupo
-- de lunes, miercoles y viernes termina el viernes 28 de agosto.
--
-- Ejecutar TODO en Supabase > SQL Editor > New query > Run.
-- Es idempotente.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. GRUPOS (sede + horario + genero + dias)
-- ---------------------------------------------------------------------
create table if not exists grupos (
    id              uuid primary key default gen_random_uuid(),
    nombre          text not null unique,
    sede            text not null,
    genero          text not null default 'MASCULINO'
                    check (genero in ('MASCULINO', 'FEMENINO', 'MIXTO')),
    hora            text,
    dias            text not null,          -- 'LUN MIE VIE'
    dias_por_semana int  not null default 3,
    activo          boolean not null default true,
    creado_en       timestamptz not null default now()
);

insert into grupos (nombre, sede, genero, hora, dias, dias_por_semana) values
  ('SURQUILLO 6:45 AM',  'SURQUILLO',  'MASCULINO', '6:45 a.m.',      'LUN MIE VIE', 3),
  ('SURCO 9:00 PM',      'SURCO',      'MASCULINO', '9:00 p.m.',      'LUN MIE VIE', 3),
  ('MIRAFLORES 8:00 PM', 'MIRAFLORES', 'FEMENINO',  '8:00 a 9:00 p.m.', 'MAR JUE',   2)
on conflict (nombre) do nothing;

-- ---------------------------------------------------------------------
-- 2. El alumno y cada pedido pertenecen a un grupo
-- ---------------------------------------------------------------------
alter table alumnos
    add column if not exists grupo_id uuid references grupos(id);

alter table paquetes
    add column if not exists grupo_id uuid references grupos(id);

-- ---------------------------------------------------------------------
-- 3. Los planes guardan su frecuencia y duracion en meses
-- ---------------------------------------------------------------------
alter table planes
    add column if not exists dias_por_semana int,
    add column if not exists meses           int,
    add column if not exists categoria       text;

-- Catalogo real de FutCross.
-- PREMIUM entrena 3 veces por semana (solo Surco y Surquillo).
-- BASICO entrena 2 veces por semana (las tres sedes).
-- Los precios que no conocemos quedan en 0: se completan en la pantalla
-- Planes. El unico confirmado es el premium de 1 mes a 240.
insert into planes (nombre, sesiones, vigencia_dias, precio, descripcion,
                    dias_por_semana, meses, categoria) values
  ('PLAN PREMIUM 1 MES',   12,  30, 240.00, '3 veces por semana durante 1 mes',   3, 1, 'PREMIUM'),
  ('PLAN PREMIUM 3 MESES', 36,  90,   0.00, '3 veces por semana durante 3 meses', 3, 3, 'PREMIUM'),
  ('PLAN PREMIUM 6 MESES', 72, 180,   0.00, '3 veces por semana durante 6 meses', 3, 6, 'PREMIUM'),
  ('PLAN BASICO 1 MES',     8,  30,   0.00, '2 veces por semana durante 1 mes',   2, 1, 'BASICO'),
  ('PLAN BASICO 3 MESES',  24,  90,   0.00, '2 veces por semana durante 3 meses', 2, 3, 'BASICO'),
  ('PLAN BASICO 6 MESES',  48, 180,   0.00, '2 veces por semana durante 6 meses', 2, 6, 'BASICO')
on conflict (nombre) do nothing;

-- Los planes de prueba que veniamos arrastrando salen del catalogo
update planes set activo = false
where nombre in ('Plan Mensual 12 sesiones', 'Plan Mensual 8 sesiones',
                 'Plan Trimestral 36 sesiones', 'Pack 4 sesiones', 'Clase suelta',
                 'PLAN BASICO 36 SESIONES 3 MESES PROMO');

-- ---------------------------------------------------------------------
-- 4. Vistas con el grupo incluido
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
       coalesce(g.dias, b.dias_asiste, a.dias_asiste) as dias_asiste,
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
join alumnos a on a.id = b.alumno_id
left join grupos g on g.id = b.grupo_id;

create view v_alumnos_estado as
select a.id            as alumno_id,
       a.codigo,
       a.nombres,
       a.apellidos,
       (a.nombres || ' ' || a.apellidos) as alumno,
       a.dni,
       a.telefono,
       a.email,
       a.grupo_id,
       ga.nombre       as grupo,
       coalesce(ga.sede, a.sede)        as sede,
       ga.genero,
       ga.hora,
       coalesce(ga.dias, a.dias_asiste) as dias_asiste,
       a.turno,
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
left join grupos ga on ga.id = a.grupo_id
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
select s.id, s.fecha, s.hora, s.sede, s.origen, s.anulada,
       s.alumno_id, s.paquete_id, a.codigo,
       (a.nombres || ' ' || a.apellidos) as alumno, a.telefono
from asistencias s
join alumnos a on a.id = s.alumno_id;
