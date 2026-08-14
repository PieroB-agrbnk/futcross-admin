-- =====================================================================
-- FUTCROSS | Migracion 015 - Planes cortos y dias por alumno
--
-- 1. Agrega los planes que faltaban: clase suelta y paquete de 4 clases.
-- 2. Deja registrado en el grupo cuantos dias entrena, para poder validar
--    que un plan basico (2 veces por semana) no elija 3 dias.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

insert into planes (nombre, sesiones, vigencia_dias, precio, descripcion,
                    dias_por_semana, meses, categoria) values
  ('CLASE SUELTA',        1,   7, 0.00, 'Una sola sesion',        1, 0, 'SUELTO'),
  ('PAQUETE 4 CLASES',    4,  30, 0.00, 'Pack corto de 4 clases', 2, 0, 'SUELTO')
on conflict (nombre) do nothing;

-- Los planes premium y basico ya existen; nos aseguramos de su frecuencia
update planes set dias_por_semana = 3 where nombre like 'PLAN PREMIUM%';
update planes set dias_por_semana = 2 where nombre like 'PLAN BASICO%';

-- Un plan sin frecuencia definida se toma como libre: puede elegir
-- cualquier cantidad de dias dentro de los de su grupo.
comment on column planes.dias_por_semana is
    'Cuantos dias por semana entrena este plan. Null = sin restriccion.';
