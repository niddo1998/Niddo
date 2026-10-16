-- ============================================================
--  Niddo — Schema v24 (Listo para pilotos)
--  Ejecutar en: Neon → SQL Editor (proyecto Niddo-SP)
--  Requiere haber ejecutado v1 → v23 antes
--  Es idempotente y sólo agrega: se puede correr más de una vez.
-- ============================================================

-- ── QR de la liquidación (Disp. DGDyPC 1146/2024 y 521/2025) ──
-- Cada liquidación tiene una página pública con sus comprobantes, el
-- reglamento y el manual de buenas prácticas. Se llega con este token al
-- azar, que es lo que va impreso en el QR. Nace la primera vez que se arma
-- el PDF.
alter table liquidaciones add column if not exists token_publico text;
create unique index if not exists liquidaciones_token_publico_key
  on liquidaciones (token_publico) where token_publico is not null;

-- ── Saldo anterior por unidad (migrar desde otro sistema) ──
-- Lo que cada unidad debía en el sistema anterior. Entra una sola vez, como
-- saldo anterior de la primera liquidación de la unidad en Niddo. Negativo es
-- saldo a favor.
alter table unidades_funcionales add column if not exists saldo_inicial numeric(14,2) default 0;

-- ── Mercado Pago por consorcio ──
-- El access token de la cuenta del edificio, cifrado (Fernet, ver cifrado.py).
-- Tabla aparte de consorcios a propósito: así ningún select('*') de
-- consorcios lo puede mandar al navegador.
create table if not exists consorcio_secretos (
  consorcio_id uuid primary key references consorcios(id) on delete cascade,
  mp_access_token_cifrado text,
  mp_cuenta text,
  updated_at timestamp with time zone default now()
);
