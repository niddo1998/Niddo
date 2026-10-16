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
