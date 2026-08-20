-- ============================================================
--  Niddo — Supabase Schema v14 (Roadmap del mapa conceptual)
--  Ejecutar en: Supabase Dashboard → SQL Editor
-- ============================================================
--
--  Esta migración nació como `supabase_schema_v12.sql` en la rama del mapa
--  conceptual, al mismo tiempo que la de gastos recurrentes tomaba ese mismo
--  número en la rama de mobile v2. Al juntarlas chocaron por el nombre y no
--  por el contenido: son dos cosas independientes.
--
--  Se renumera ésta y no la otra porque `v12` aparece diez veces en app.py
--  (ERROR_FALTA_V12, _falta_schema_v12): ahí v12 significa gastos recurrentes
--  y renombrarla dejaría los mensajes de error apuntando a un archivo que no
--  existe.
--
--  Si ya la corriste cuando se llamaba v12, no hace falta volver a correrla:
--  es idempotente y el contenido es el mismo.
-- ============================================================


-- v12: Roadmap del mapa conceptual (Superadmin)
--
-- Guarda el estado de cada componente del mapa por categoría (mismo id que
-- usa el frontend: "categoria::indice_funcionalidad::indice_item", ej "exp::0::0").
-- Solo se persisten filas para items en 'planeada' o 'construida'; el estado
-- 'sin_definir' es la ausencia de fila (no se guarda), igual que hacía
-- window.storage en la versión de Claude.

create table if not exists roadmap_estado (
  id text primary key,
  estado text not null check (estado in ('planeada', 'construida')),
  actualizado_por uuid references administradores(id) on delete set null,
  actualizado_at timestamptz not null default now()
);

comment on table roadmap_estado is 'Estado manual del mapa conceptual por categoría, editado desde /superadmin/mapa';

-- RLS: igual que el resto de las tablas de negocio hoy, sin políticas.
-- El acceso real lo controla el decorador @require_superadmin en Flask,
-- no Postgres — service_role key salta RLS de cualquier forma. Si en algún
-- momento migran a políticas reales, esta tabla debería sumarse a la lista.
alter table roadmap_estado enable row level security;
