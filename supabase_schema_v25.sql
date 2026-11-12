-- ============================================================
--  Niddo — Schema v25 (Panel del negocio)
--  Ejecutar en: Neon → SQL Editor (proyecto Niddo-SP)
--  Requiere haber ejecutado v1 → v24 antes
--  Es idempotente y sólo agrega: se puede correr más de una vez.
-- ============================================================

-- ── Finanzas de Niddo ──
-- Lo que entra y sale de la empresa, cargado a mano desde /superadmin.
-- No tiene nada que ver con las expensas de los consorcios.
create table if not exists negocio_movimientos (
  id uuid primary key default gen_random_uuid(),
  fecha date not null,
  tipo text not null check (tipo in ('ingreso', 'gasto')),
  categoria text not null default 'Otros',
  monto numeric(14,2) not null check (monto > 0),
  nota text,
  created_at timestamp with time zone default now()
);
create index if not exists negocio_movimientos_fecha_idx on negocio_movimientos (fecha);

-- ── Pipeline comercial ──
-- Administraciones con las que se está hablando, y en qué etapa está cada una.
create table if not exists negocio_prospectos (
  id uuid primary key default gen_random_uuid(),
  nombre text not null,
  contacto text,
  email text,
  telefono text,
  etapa text not null default 'contactado'
    check (etapa in ('contactado', 'demo', 'piloto', 'cliente', 'perdido')),
  consorcios integer default 0,
  unidades integer default 0,
  proxima_accion text,
  proxima_fecha date,
  notas text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- ── Configuración del panel ──
-- Planes y precios, metas, notas del plan comercial y los precios de la
-- proyección. Una fila por clave, con el contenido en JSON.
create table if not exists negocio_config (
  clave text primary key,
  valor jsonb not null default '{}'::jsonb,
  updated_at timestamp with time zone default now()
);
