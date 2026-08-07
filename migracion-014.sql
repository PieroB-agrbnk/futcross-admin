-- =====================================================================
-- FUTCROSS | Migracion 014 - Reactivacion automatica
--
-- Hasta ahora el alta de un congelamiento era manual. Esto lo automatiza:
-- cuando llega la fecha prevista de alta, el paquete vuelve a estar activo
-- y su vencimiento se recalcula contando las sesiones que le quedan en el
-- calendario de su grupo.
--
-- Corre solo, todos los dias a medianoche hora de Lima, dentro de la base
-- de datos. No depende de que nadie abra el panel.
--
-- Ejecutar en Supabase > SQL Editor > New query > Run. Es idempotente.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. La misma cuenta de sesiones que hace la app, pero en la base
-- ---------------------------------------------------------------------
create or replace function fc_fecha_de_sesion(p_inicio date, p_numero int, p_dias text)
returns date
language plpgsql
immutable as $$
declare
    v_fecha    date := p_inicio;
    v_contadas int  := 0;
    v_indices  int[];
    v_dow      int;
begin
    if p_dias is null or p_inicio is null or p_numero < 1 then
        return null;
    end if;

    -- 'LUN MIE VIE' -> {1,3,5}   (en Postgres, domingo = 0)
    select array_agg(case d
               when 'LUN' then 1 when 'MAR' then 2 when 'MIE' then 3
               when 'JUE' then 4 when 'VIE' then 5 when 'SAB' then 6
               when 'DOM' then 0 end)
      into v_indices
      from unnest(string_to_array(upper(trim(p_dias)), ' ')) as d
     where d <> '';

    if v_indices is null then
        return null;
    end if;

    -- Tope de seguridad: 5 anios
    for i in 1..1825 loop
        v_dow := extract(dow from v_fecha);
        if v_dow = any(v_indices) then
            v_contadas := v_contadas + 1;
            if v_contadas = p_numero then
                return v_fecha;
            end if;
        end if;
        v_fecha := v_fecha + 1;
    end loop;

    return null;
end $$;

-- ---------------------------------------------------------------------
-- 2. Reactivar los congelamientos cuya fecha prevista ya llego
-- ---------------------------------------------------------------------
create or replace function fc_reactivar_previstos()
returns int
language plpgsql as $$
declare
    r           record;
    v_restantes int;
    v_fin       date;
    v_dias_off  int;
    v_total     int := 0;
begin
    for r in
        select c.id            as cong_id,
               c.fecha_inicio,
               c.fecha_alta_prevista,
               p.id            as paquete_id,
               p.sesiones_totales,
               p.fecha_fin,
               p.dias_congelados,
               coalesce(g.dias, p.dias_asiste, a.dias_asiste) as dias
          from congelamientos c
          join paquetes p on p.id = c.paquete_id
          join alumnos  a on a.id = p.alumno_id
     left join grupos   g on g.id = p.grupo_id
         where c.activo
           and c.fecha_alta_prevista is not null
           and c.fecha_alta_prevista <= hoy_lima()
    loop
        select r.sesiones_totales - count(*)
          into v_restantes
          from asistencias s
         where s.paquete_id = r.paquete_id and not s.anulada;

        v_dias_off := (r.fecha_alta_prevista - r.fecha_inicio) + 1;

        -- Nueva fecha de fin: su ultima sesion contando desde el alta
        v_fin := fc_fecha_de_sesion(r.fecha_alta_prevista,
                                    greatest(v_restantes, 1), r.dias);
        -- Si el grupo no tiene dias definidos, se corre la fecha igual que antes
        if v_fin is null then
            v_fin := r.fecha_fin + v_dias_off;
        end if;

        update paquetes
           set estado          = 'ACTIVO',
               fecha_fin       = v_fin,
               dias_congelados = coalesce(dias_congelados, 0) + v_dias_off
         where id = r.paquete_id;

        update congelamientos
           set activo         = false,
               fecha_fin      = r.fecha_alta_prevista,
               dias_aplicados = v_dias_off
         where id = r.cong_id;

        v_total := v_total + 1;
    end loop;

    return v_total;
end $$;

-- ---------------------------------------------------------------------
-- 3. Que corra solo todos los dias
--    05:05 UTC = 00:05 en Lima. Si pg_cron no esta disponible, el script
--    sigue funcionando: la app igual la ejecuta al abrirse.
-- ---------------------------------------------------------------------
do $$
begin
    create extension if not exists pg_cron;

    perform cron.unschedule('futcross-reactivar')
      where exists (select 1 from cron.job where jobname = 'futcross-reactivar');

    perform cron.schedule('futcross-reactivar', '5 5 * * *',
                          'select fc_reactivar_previstos();');
exception when others then
    raise notice 'pg_cron no disponible (%). La reactivacion corre igual al abrir el panel.',
                 sqlerrm;
end $$;

-- ---------------------------------------------------------------------
-- 4. Verificacion: corre una vez ahora mismo
-- ---------------------------------------------------------------------
select fc_reactivar_previstos() as reactivados_ahora;
