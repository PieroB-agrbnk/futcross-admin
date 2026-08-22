-- =====================================================================
-- FUTCROSS | Migracion 018 - Indices que faltaban
--
-- No agrega ni cambia ninguna columna: solo crea indices. Se puede
-- correr con la app funcionando y no rompe nada si se corre dos veces.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. EL IMPORTANTE: asistencias por paquete
--
-- La vista v_paquetes calcula las sesiones usadas contando asistencias:
--
--     select count(*) from asistencias s
--     where s.paquete_id = p.id and not s.anulada
--
-- Esa cuenta se repite UNA VEZ POR PAQUETE, y hasta ahora no habia
-- ningun indice sobre asistencias.paquete_id: Postgres recorria la
-- tabla entera de asistencias por cada paquete de la lista. Con 200
-- paquetes y 5000 asistencias son un millon de filas leidas para
-- dibujar la pantalla de Alumnos.
--
-- v_alumnos_estado se apoya en v_paquetes, asi que el Panel, Alumnos,
-- Renovaciones y el kiosco pagaban todos ese costo.
--
-- El indice es parcial (solo las no anuladas) porque es exactamente lo
-- que pide la consulta: mas chico y mas rapido.
-- ---------------------------------------------------------------------
create index if not exists ix_asistencias_paquete
    on asistencias (paquete_id) where not anulada;

-- ---------------------------------------------------------------------
-- 2. Asistencias de un alumno en un rango
--
-- La ficha del alumno dibuja su mapa de calor de los ultimos 6 meses.
-- El indice unico que ya existia (alumno_id, fecha) solo cubre las no
-- anuladas y sirve para el anti doble marca; este ordena por fecha
-- descendente, que es como se leen siempre.
-- ---------------------------------------------------------------------
create index if not exists ix_asistencias_alumno_fecha
    on asistencias (alumno_id, fecha desc);

-- ---------------------------------------------------------------------
-- 3. Intentos fallidos de PIN
--
-- El bloqueo por intentos fallidos cuenta los registros PIN_FALLIDO de
-- los ultimos 15 minutos. Esa consulta corre en cada intento de
-- ingreso, o sea antes de que haya nadie autenticado: conviene que sea
-- barata para que no se pueda usar para castigar al servidor.
-- ---------------------------------------------------------------------
create index if not exists ix_bloqueos_motivo_creado
    on bloqueos (motivo, creado_en desc);

-- ---------------------------------------------------------------------
-- 4. Pedidos pendientes de cobro
--
-- Son pocos entre muchos: el indice parcial ocupa casi nada y evita
-- recorrer toda la tabla de paquetes para armar el aviso del Panel.
-- ---------------------------------------------------------------------
create index if not exists ix_paquetes_por_cobrar
    on paquetes (fecha_pedido desc) where not pagado;

-- ---------------------------------------------------------------------
-- 5. Ventas por fecha de inicio
--
-- Reportes ahora filtra el rango en la base en vez de traerse el
-- historico completo. Este indice es el que hace que ese filtro valga
-- la pena.
-- ---------------------------------------------------------------------
create index if not exists ix_paquetes_inicio
    on paquetes (fecha_inicio desc);

-- ---------------------------------------------------------------------
-- 6. Busqueda por texto (nombre, apellido, DNI, telefono)
--
-- El buscador de Alumnos y el del kiosco usan ilike '%texto%'. El
-- comodin al principio inutiliza cualquier indice normal, asi que
-- Postgres leia la tabla entera en cada tecla.
--
-- pg_trgm parte el texto en grupos de tres letras y los indexa: con
-- esto 'ilike %nun%' si usa indice. Ademas tolera el orden, asi que
-- buscar "perez juan" encuentra a "Juan Perez".
--
-- La extension viene incluida en Supabase, solo hay que habilitarla.
-- ---------------------------------------------------------------------
create extension if not exists pg_trgm;

create index if not exists ix_alumnos_busqueda
    on alumnos using gin (
        (coalesce(nombres, '') || ' ' ||
         coalesce(apellidos, '') || ' ' ||
         coalesce(codigo, '') || ' ' ||
         coalesce(dni, '') || ' ' ||
         coalesce(telefono, '')) gin_trgm_ops
    );

create index if not exists ix_alumnos_nombres_trgm
    on alumnos using gin (nombres gin_trgm_ops);

create index if not exists ix_alumnos_apellidos_trgm
    on alumnos using gin (apellidos gin_trgm_ops);

-- El kiosco busca el telefono por igualdad exacta (telefono.eq.999888777)
create index if not exists ix_alumnos_telefono
    on alumnos (telefono);

-- ---------------------------------------------------------------------
-- 7. Que el planificador se entere
--
-- Sin estadisticas frescas Postgres puede seguir eligiendo el plan
-- viejo aunque el indice ya exista.
-- ---------------------------------------------------------------------
analyze asistencias;
analyze paquetes;
analyze alumnos;
analyze bloqueos;

-- ---------------------------------------------------------------------
-- Comprobacion: deberia listar los indices recien creados
-- ---------------------------------------------------------------------
select tablename, indexname
from pg_indexes
where schemaname = 'public'
  and indexname in ('ix_asistencias_paquete',
                    'ix_asistencias_alumno_fecha',
                    'ix_bloqueos_motivo_creado',
                    'ix_paquetes_por_cobrar',
                    'ix_paquetes_inicio',
                    'ix_alumnos_busqueda',
                    'ix_alumnos_telefono')
order by tablename, indexname;
