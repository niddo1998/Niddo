-- ============================================================
--  Niddo — 027: débito automático con Mercado Pago
--  Requiere schema.sql, 025 y 026
--  Es idempotente y sólo agrega: se puede correr más de una vez.
-- ============================================================

-- Una suscripción de Mercado Pago (preapproval) por administrador: el débito
-- mensual de lo que le paga a Niddo. Se guarda lo último que dijo la API.
create table if not exists suscripciones_mp (
  admin_id uuid primary key references administradores(id) on delete cascade,
  preapproval_id text not null unique,
  estado text not null default 'pending',   -- pending, authorized, paused, cancelled
  monto numeric(14,2) not null default 0,
  payer_email text,
  proximo_cobro date,
  init_point text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- El pago de Mercado Pago que saldó cada cobro. Único: el webhook puede
-- llegar más de una vez y no tiene que contar el pago dos veces.
alter table cobros_niddo add column if not exists mp_pago_id text;
create unique index if not exists cobros_niddo_mp_pago_id_key
  on cobros_niddo (mp_pago_id) where mp_pago_id is not null;
