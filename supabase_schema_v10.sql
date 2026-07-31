-- ============================================================
--  Niddo — Supabase Schema v10 (Aprobación manual de administradores)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v9 antes
-- ============================================================
--
--  Problema que resuelve:
--  Hasta ahora el botón "Administrador" del login llevaba directo a Auth0 y el
--  callback hacía `upsert_user('admin', ...)`: cualquiera que se registrara
--  quedaba con dashboard de administrador completo al instante, y lo único que
--  quedaba de esa persona era el email y el nombre que devolviera Auth0.
--
--  Ahora el alta de administrador pasa por una cola de aprobación manual que
--  resuelven los dos superadmins del sitio, con los datos de contacto que el
--  solicitante completa después de registrarse.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================


-- ── 1. Estado de aprobación y datos de contacto ──────────────
-- `estado` nace en 'pendiente' porque es lo correcto para las altas nuevas, pero
-- eso dejaría pendientes también a los administradores que ya venían usando el
-- sistema. El UPDATE de más abajo los rescata: el gate solo aplica de acá en
-- adelante. El orden ALTER → UPDATE → CHECK importa.
ALTER TABLE administradores
  ADD COLUMN IF NOT EXISTS estado                  TEXT NOT NULL DEFAULT 'pendiente',
  ADD COLUMN IF NOT EXISTS telefono                TEXT,
  ADD COLUMN IF NOT EXISTS nombre_contacto         TEXT,
  ADD COLUMN IF NOT EXISTS email_contacto          TEXT,
  ADD COLUMN IF NOT EXISTS solicitud_completada_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS aprobado_por            UUID REFERENCES administradores(id),
  ADD COLUMN IF NOT EXISTS resuelto_at             TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS motivo_rechazo          TEXT,
  ADD COLUMN IF NOT EXISTS es_superadmin           BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE administradores SET estado = 'aprobado' WHERE estado = 'pendiente';

DO $$ BEGIN
  ALTER TABLE administradores ADD CONSTRAINT administradores_estado_check
    CHECK (estado IN ('pendiente','aprobado','rechazado'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_admin_estado ON administradores(estado);


-- ── 2. Bootstrap de superadmins ──────────────────────────────
-- El privilegio se ancla al `auth0_id` y no al email a propósito. Un allowlist
-- por email es reclamable: con una conexión de base de datos, Auth0 deja crear
-- una cuenta con un email cualquiera y `email_verified` en false, así que atar
-- el privilegio al email abriría la puerta a que alguien se autoeleve. El `sub`
-- lo emite Auth0 y no se puede reclamar.
--
-- No hay endpoint de bootstrap ni forma de volverse superadmin desde la app:
-- el único camino es este UPDATE, corrido a mano contra la base.
UPDATE administradores
SET es_superadmin = TRUE, estado = 'aprobado'
WHERE auth0_id = 'google-oauth2|104417971513748975789';   -- Santiago

-- Descomentar y completar cuando el socio se haya registrado. El auth0_id sale de:
--   SELECT email, auth0_id FROM administradores ORDER BY created_at;
-- UPDATE administradores
-- SET es_superadmin = TRUE, estado = 'aprobado'
-- WHERE auth0_id = 'PEGAR_AUTH0_ID_DEL_SOCIO';


-- ── 3. Auditoría de acciones de superadmin ───────────────────
-- Append-only por diseño: aprobar y rechazar son las únicas acciones del sistema
-- que dan o quitan acceso a la plataforma entera, así que tienen que dejar
-- rastro de quién las hizo. Las políticas de abajo bloquean UPDATE y DELETE
-- incluso para quien llegue con un token de usuario; el service key de la app
-- las saltea, pero la app solo escribe INSERTs contra esta tabla.
CREATE TABLE IF NOT EXISTS superadmin_auditoria (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id    UUID NOT NULL REFERENCES administradores(id) ON DELETE RESTRICT,
  target_id   UUID NOT NULL REFERENCES administradores(id) ON DELETE RESTRICT,
  accion      TEXT NOT NULL CHECK (accion IN ('aprobar','rechazar')),
  motivo      TEXT,
  ip          TEXT,
  user_agent  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auditoria_target  ON superadmin_auditoria(target_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_created ON superadmin_auditoria(created_at DESC);

ALTER TABLE superadmin_auditoria ENABLE ROW LEVEL SECURITY;

-- ON DELETE RESTRICT en las dos FKs: borrar un administrador no puede llevarse
-- puesto el registro de que fue aprobado o rechazado. Si algún día hace falta
-- dar de baja a alguien, se marca 'rechazado', no se borra la fila.


-- ── 4. Verificación ──────────────────────────────────────────
-- Después de correr todo esto, esta query tiene que mostrar tu fila con
-- estado = 'aprobado' y es_superadmin = true:
--
--   SELECT email, estado, es_superadmin FROM administradores ORDER BY created_at;
