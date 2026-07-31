-- ============================================================
--  Niddo — Supabase Schema v11 (Portal de superadmin)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v10 antes
-- ============================================================
--
--  Dos cosas que necesita el portal:
--
--  1. Una señal de actividad honesta. `last_login` solo se escribe en el
--     callback de Auth0, así que un administrador que usa Niddo todos los días
--     con la sesión abierta figura como inactivo hace semanas. Cualquier
--     métrica de "activos" construida sobre eso subestima el uso.
--
--  2. Registrar la impersonación. Con el portal se puede entrar a ver la
--     plataforma como un administrador; eso toca datos personales de vecinos
--     que no son clientes de Niddo, así que cada entrada y cada salida quedan
--     asentadas.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================


-- ── 1. Señal de actividad real ───────────────────────────────
-- La escribe cargar_admin_actual() como mucho una vez por hora, no en cada
-- request: la diferencia entre saber la hora exacta y saber la hora aproximada
-- del último uso no justifica un UPDATE por carga de página.
ALTER TABLE administradores
  ADD COLUMN IF NOT EXISTS ultima_actividad TIMESTAMPTZ;

-- Arranca con lo último que sabemos de cada uno, para que las métricas no
-- muestren a todo el mundo como inactivo el primer día.
UPDATE administradores
SET ultima_actividad = COALESCE(last_login, created_at)
WHERE ultima_actividad IS NULL;

CREATE INDEX IF NOT EXISTS idx_admin_ultima_actividad
  ON administradores(ultima_actividad DESC);


-- ── 2. Auditoría de impersonación ────────────────────────────
-- v10 dejó el CHECK limitado a aprobar/rechazar. Se amplía en lugar de
-- quitarlo: la restricción es lo que impide que una acción mal escrita entre
-- silenciosamente al registro y después no se pueda agrupar por tipo.
DO $$ BEGIN
  ALTER TABLE superadmin_auditoria DROP CONSTRAINT superadmin_auditoria_accion_check;
EXCEPTION WHEN undefined_object THEN NULL; END $$;

ALTER TABLE superadmin_auditoria
  ADD CONSTRAINT superadmin_auditoria_accion_check
  CHECK (accion IN ('aprobar','rechazar','impersonar_inicio','impersonar_fin'));


-- ── 3. Índices para el tablero ───────────────────────────────
-- El embudo de activación y la tendencia agrupan por fecha de alta sobre las
-- tablas que más crecen. Sin esto, cada carga de "Hoy" hace scan completo.
CREATE INDEX IF NOT EXISTS idx_consorcios_created  ON consorcios(created_at);
CREATE INDEX IF NOT EXISTS idx_vecinos_created     ON vecinos(created_at);
CREATE INDEX IF NOT EXISTS idx_liquidaciones_admin ON liquidaciones(admin_id);


-- ── 4. Verificación ──────────────────────────────────────────
--   SELECT email, estado, es_superadmin, ultima_actividad
--   FROM administradores ORDER BY ultima_actividad DESC NULLS LAST;
