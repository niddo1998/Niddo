-- ============================================================
--  Niddo — Supabase Schema v20 (comunicados: las columnas que faltan)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v19 antes
-- ============================================================
--
--  Mandar un comunicado desde el panel del administrador fallaba con:
--
--    Could not find the 'importante' column of 'comunicados' in the schema
--    cache (PGRST204)
--
--  v6 crea la tabla con CREATE TABLE IF NOT EXISTS. En la base de producción
--  `comunicados` ya existía de antes, así que el CREATE no hizo nada y las
--  columnas que v6 agregaba nunca llegaron. PostgREST sólo avisa de la primera
--  que falta, por eso acá van todas las que escribe el panel, no sólo
--  `importante`.
--
--  Van sin NOT NULL a propósito: agregar una columna NOT NULL a una tabla con
--  filas falla, y el panel ya valida que título y cuerpo vengan con texto.
--
--  Si después de correrlo el comunicado sigue fallando, correr esto y pasar
--  el resultado —dice cómo quedó armada la tabla de verdad—:
--
--    select column_name, data_type, is_nullable, column_default
--      from information_schema.columns
--     where table_name = 'comunicados'
--     order by ordinal_position;
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================


alter table comunicados add column if not exists consorcio_id uuid references consorcios(id) on delete cascade;
alter table comunicados add column if not exists admin_id     uuid references administradores(id) on delete set null;
alter table comunicados add column if not exists titulo       text;
alter table comunicados add column if not exists cuerpo       text;
alter table comunicados add column if not exists importante   boolean default false;
alter table comunicados add column if not exists created_at   timestamptz default now();

create index if not exists idx_comunicados_consorcio on comunicados(consorcio_id);
create index if not exists idx_comunicados_fecha     on comunicados(created_at desc);


-- Quién leyó cada comunicado: el badge de "no leídos" del vecino y la columna
-- "Leído por" del administrador salen de acá. Viene de v6 igual que las
-- columnas de arriba, así que puede faltar por la misma razón.
create table if not exists comunicados_leidos (
  id             uuid primary key default gen_random_uuid(),
  comunicado_id  uuid not null references comunicados(id) on delete cascade,
  vecino_id      uuid not null references vecinos(id) on delete cascade,
  leido_at       timestamptz default now(),
  unique (comunicado_id, vecino_id)
);

create index if not exists idx_com_leidos_vecino on comunicados_leidos(vecino_id);


-- PostgREST guarda el esquema en caché: sin esto las columnas nuevas pueden
-- seguir "sin existir" para la API un rato después de creadas.
notify pgrst, 'reload schema';
