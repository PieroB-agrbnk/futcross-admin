-- =====================================================================
-- FUTCROSS | Migracion 016 - Planes sueltos sin frecuencia fija
--
-- Un paquete de 4 clases o una clase suelta no obligan a una cantidad de
-- dias por semana: el alumno puede venir solo los lunes si quiere. Dejar
-- su frecuencia en null hace que el sistema no proponga ni cuestione
-- ninguna cantidad de dias.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

update planes
   set dias_por_semana = null
 where nombre in ('CLASE SUELTA', 'PAQUETE 4 CLASES')
    or categoria = 'SUELTO';

-- Los planes con frecuencia fija se mantienen
update planes set dias_por_semana = 3 where nombre like 'PLAN PREMIUM%';
update planes set dias_por_semana = 2 where nombre like 'PLAN BASICO%';

select nombre, sesiones, dias_por_semana, precio
  from planes where activo order by nombre;
