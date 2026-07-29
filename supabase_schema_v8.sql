-- ============================================================
--  Niddo — Supabase Schema v8 (Reliquidación del mismo período)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v7 antes
-- ============================================================
--
--  Problema que resuelve:
--  v7 creó `liquidaciones` con UNIQUE(consorcio_id, periodo), así que una vez
--  enviadas las expensas de un mes no se podía generar otra liquidación para
--  ese mismo mes con los gastos cargados después. El insert fallaba con
--  "duplicate key value violates unique constraint" y la UI mostraba un error
--  genérico sin salida posible.
--
--  Solución: permitir N liquidaciones por consorcio+período, numeradas por
--  `numero_revision` (1 = la original, 2+ = reliquidaciones del mismo mes).
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================


-- ── 1. Bajar el UNIQUE(consorcio_id, periodo) de v7 ──────────
-- v7 lo declaró como UNIQUE(...) dentro del CREATE TABLE, así que Postgres lo
-- nombró <tabla>_<columnas>_key. El IF EXISTS hace que no falle si ya se bajó
-- o si nunca se llamó así (para ese caso está la verificación del final).
ALTER TABLE liquidaciones
  DROP CONSTRAINT IF EXISTS liquidaciones_consorcio_id_periodo_key;


-- ── 2. Columna de revisión ───────────────────────────────────
ALTER TABLE liquidaciones
  ADD COLUMN IF NOT EXISTS numero_revision INTEGER NOT NULL DEFAULT 1;


-- ── 3. Backfill: numerar las liquidaciones que ya existían ───
-- Las filas previas quedan con revisión 1; si por algún motivo hubiera más de
-- una por consorcio+período, se numeran por antigüedad.
WITH numeradas AS (
  SELECT id,
         ROW_NUMBER() OVER (
           PARTITION BY consorcio_id, periodo
           ORDER BY created_at, id
         ) AS rev
  FROM liquidaciones
)
UPDATE liquidaciones l
SET    numero_revision = n.rev
FROM   numeradas n
WHERE  l.id = n.id
  AND  l.numero_revision IS DISTINCT FROM n.rev;


-- ── 4. Nuevo unique: una revisión por consorcio+período ──────
CREATE UNIQUE INDEX IF NOT EXISTS uq_liquidaciones_consorcio_periodo_rev
  ON liquidaciones(consorcio_id, periodo, numero_revision);


-- ── 5. Índice para resolver "qué gastos ya se avisaron" ──────
-- _gastos_ya_enviados() filtra resumen_envios por estado dentro de un set de
-- liquidaciones; este índice evita el seq scan cuando crece la tabla.
CREATE INDEX IF NOT EXISTS idx_resumen_envios_liq_estado
  ON resumen_envios(liquidacion_id, estado);


-- ============================================================
--  Verificación — correr aparte y leer el resultado
-- ============================================================
--
-- (a) ¿Quedó alguna UNIQUE vieja que siga bloqueando la reliquidación?
--     Lo esperado es ver SÓLO la primary key. Si aparece una fila cuya
--     definición sea "UNIQUE (consorcio_id, periodo)" hay que bajarla a mano:
--       ALTER TABLE liquidaciones DROP CONSTRAINT <conname>;
--
-- SELECT con.conname, pg_get_constraintdef(con.oid) AS definicion
-- FROM   pg_constraint con
-- JOIN   pg_class rel ON rel.oid = con.conrelid
-- WHERE  rel.relname = 'liquidaciones'
--   AND  con.contype IN ('u', 'p');
--
-- (b) Las liquidaciones existentes deberían quedar todas en revisión 1:
--
-- SELECT periodo, numero_revision, estado, total_egresos
-- FROM   liquidaciones
-- ORDER  BY periodo DESC, numero_revision;
