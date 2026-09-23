-- =====================================================================
-- FUTCROSS | Migracion 023
--
-- 1. OTROS INGRESOS
--    Plata que entra sin un alumno detras: el partido amistoso del
--    domingo, un alquiler de cancha. Se registra el total del dia, no
--    persona por persona, y suma en Reportes como ingreso de caja.
--
-- 2. NUEVO HORARIO DE SURCO
--    Lunes a las 8:00 p.m.; miercoles y viernes a las 9:00 p.m.
--    Es solo el texto del horario: los dias de entrenamiento no cambian,
--    asi que ningun vencimiento se mueve.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

create table if not exists ingresos_extra (
    id          uuid primary key default gen_random_uuid(),
    fecha       date not null default hoy_lima(),
    concepto    text not null,
    personas    int check (personas is null or personas >= 0),
    monto       numeric(10,2) not null check (monto >= 0),
    medio_pago  text,
    notas       text,
    creado_en   timestamptz not null default now()
);

create index if not exists ix_ingresos_extra_fecha on ingresos_extra (fecha desc);

comment on table ingresos_extra is
    'Ingresos sin alumno asociado: partidos amistosos, alquileres, etc.';

update grupos
   set nombre = 'SURCO',
       hora   = 'LUN 8:00 PM, MIE y VIE 9:00 PM'
 where sede = 'SURCO';

-- Verificacion
select nombre, sede, hora, dias from grupos order by sede;
