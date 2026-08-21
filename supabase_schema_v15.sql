-- ============================================================
--  Niddo — Supabase Schema v15 (teléfono del vecino)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v14 antes
-- ============================================================
--
--  El vecino no tenía dónde dejar un teléfono. `administradores` sí tiene la
--  columna desde v2, así que esto empareja las dos tablas y habilita el
--  PUT /api/me: hasta ahora el perfil del vecino era de sólo lectura y para
--  corregir un nombre mal escrito había que entrar a la base.
--
--  Nació como v14 cuando la v13 todavía no estaba mergeada. Al entrar mobile
--  v2, v13 pasó a ser la de RLS y v14 la del roadmap, así que ésta corre el
--  número. No toca nada de esas dos: se puede correr antes o después.

ALTER TABLE vecinos ADD COLUMN IF NOT EXISTS telefono TEXT;

COMMENT ON COLUMN vecinos.telefono IS 'Contacto del vecino, editable por él mismo desde Mi Perfil';
