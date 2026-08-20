-- ============================================================
--  Niddo — Supabase Schema v14 (teléfono del vecino)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v12 antes
-- ============================================================
--
--  El vecino no tenía dónde dejar un teléfono. `administradores` sí tiene la
--  columna desde v2, así que esto empareja las dos tablas y habilita el
--  PUT /api/me: hasta ahora el perfil del vecino era de sólo lectura y para
--  corregir un nombre mal escrito había que entrar a la base.
--
--  Va después de la v12 y no de la v13: la v13 no está en esta rama, la ocupa
--  la migración de RLS de feat/mobile-admin-v2. No hace falta esperarla — las
--  dos tocan cosas distintas y corren en cualquier orden.

ALTER TABLE vecinos ADD COLUMN IF NOT EXISTS telefono TEXT;

COMMENT ON COLUMN vecinos.telefono IS 'Contacto del vecino, editable por él mismo desde Mi Perfil';
