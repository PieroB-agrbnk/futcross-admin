-- =====================================================================
-- FUTCROSS | Migracion 025 - Precios por sede
--
-- El mismo plan cuesta distinto segun la sede: el de 1 mes y 8 clases
-- sale 169 en Surco, 179 en Miraflores y 189 en Surquillo. Y cada uno
-- tiene un precio normal (el tachado del flyer) y el de promocion.
--
-- Esta tabla guarda los dos por plan y sede. Al vender, el sistema los
-- propone solos segun el grupo elegido: el normal como precio de lista y
-- el de promocion como precio cobrado, asi el descuento sale solo, igual
-- que el "Ahorras" del flyer.
--
-- Carga los precios de los flyers de Verano 2027. Si la corres de nuevo
-- no pisa los precios que hayas cambiado desde el panel.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

create table if not exists precios_sede (
    plan_id        uuid not null references planes(id) on delete cascade,
    sede           text not null,
    precio_lista   numeric(10,2) not null check (precio_lista >= 0),
    precio         numeric(10,2) not null check (precio >= 0),
    actualizado_en timestamptz not null default now(),
    primary key (plan_id, sede)
);

comment on table precios_sede is
    'Precio normal (lista) y precio actual de cada plan en cada sede.';

-- Los planes de 2 meses que aparecen en los flyers
insert into planes (nombre, sesiones, vigencia_dias, precio, descripcion,
                    dias_por_semana, meses, categoria) values
  ('PLAN BASICO 2 MESES',  16, 60, 458, '2 veces por semana durante 2 meses', 2, 2, 'BASICO'),
  ('PLAN PREMIUM 2 MESES', 24, 60, 578, '3 veces por semana durante 2 meses', 3, 2, 'PREMIUM')
on conflict (nombre) do nothing;

-- Precio de referencia del catalogo: el precio normal de los flyers.
-- De paso corrige el basico de 1 mes, que estaba en 2000.
update planes set precio = v.precio
  from (values
    ('PLAN BASICO 1 MES', 229), ('PLAN BASICO 2 MESES', 458),
    ('PLAN BASICO 3 MESES', 590), ('PLAN PREMIUM 1 MES', 289),
    ('PLAN PREMIUM 2 MESES', 578), ('PLAN PREMIUM 3 MESES', 867),
    ('PAQUETE 4 CLASES', 120), ('CLASE SUELTA', 30)
  ) as v(nombre, precio)
 where planes.nombre = v.nombre;

-- Precios de los flyers Verano 2027: (sede, plan, normal, promocion)
insert into precios_sede (plan_id, sede, precio_lista, precio)
select p.id, v.sede, v.lista, v.precio
  from (values
    ('SURCO',      'PLAN BASICO 1 MES',    229, 169),
    ('SURCO',      'PLAN BASICO 2 MESES',  458, 305),
    ('SURCO',      'PLAN BASICO 3 MESES',  590, 409),
    ('SURCO',      'PAQUETE 4 CLASES',     120, 120),
    ('SURCO',      'CLASE SUELTA',          30,  30),
    ('MIRAFLORES', 'PLAN BASICO 1 MES',    229, 179),
    ('MIRAFLORES', 'PLAN BASICO 2 MESES',  458, 320),
    ('MIRAFLORES', 'PLAN BASICO 3 MESES',  590, 429),
    ('MIRAFLORES', 'PAQUETE 4 CLASES',     120, 120),
    ('MIRAFLORES', 'CLASE SUELTA',          30,  30),
    ('SURQUILLO',  'PLAN BASICO 1 MES',    229, 189),
    ('SURQUILLO',  'PLAN BASICO 2 MESES',  458, 329),
    ('SURQUILLO',  'PLAN BASICO 3 MESES',  590, 429),
    ('SURQUILLO',  'PLAN PREMIUM 1 MES',   289, 229),
    ('SURQUILLO',  'PLAN PREMIUM 2 MESES', 578, 419),
    ('SURQUILLO',  'PLAN PREMIUM 3 MESES', 867, 519),
    ('SURQUILLO',  'PAQUETE 4 CLASES',     120, 120),
    ('SURQUILLO',  'CLASE SUELTA',          30,  30)
  ) as v(sede, plan, lista, precio)
  join planes p on p.nombre = v.plan
on conflict (plan_id, sede) do nothing;

-- Verificacion: lo que quedo cargado, con el ahorro de cada uno
select s.sede, p.nombre as plan, s.precio_lista as normal, s.precio as actual,
       s.precio_lista - s.precio as ahorro
  from precios_sede s
  join planes p on p.id = s.plan_id
 order by s.sede, p.sesiones;
