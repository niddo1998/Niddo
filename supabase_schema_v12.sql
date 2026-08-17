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
