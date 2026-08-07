-- =====================================================================
-- FUTCROSS | Migracion 012 - Fecha prevista de alta
--
-- Al congelar por lesion o enfermedad casi siempre se sabe cuando vuelve
-- ("un mes de reposo"). Guardar esa fecha desde el inicio permite avisar
-- cuando le toca volver, en vez de esperar a que alguien se acuerde.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

alter table congelamientos
    add column if not exists fecha_alta_prevista date;

comment on column congelamientos.fecha_alta_prevista is
    'Cuando se espera que vuelva. La fecha real de alta va en fecha_fin.';

create index if not exists ix_congelamientos_alta
    on congelamientos (fecha_alta_prevista) where activo;
