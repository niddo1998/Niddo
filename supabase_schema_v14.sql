-- ============================================================
--  Niddo — Supabase Schema v14 (teléfono del vecino)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v13 antes
-- ============================================================
--
--  El vecino no tenía dónde dejar un teléfono. `administradores` sí tiene la
--  columna desde v2, así que esto empareja las dos tablas y habilita el
--  PUT /api/me: hasta ahora el perfil del vecino era de sólo lectura y para
--  corregir un nombre mal escrito había que entrar a la base.
--
--  Se salta la v13 a propósito: ese número lo ocupa la migración de RLS que
--  viene en feat/mobile-admin-v2. Correr las dos en cualquier orden es seguro,
--  no se tocan.

ALTER TABLE vecinos ADD COLUMN IF NOT EXISTS telefono TEXT;

COMMENT ON COLUMN vecinos.telefono IS 'Contacto del vecino, editable por él mismo desde Mi Perfil';
