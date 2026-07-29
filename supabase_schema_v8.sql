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


-- ── 1. Columna de revisión ───────────────────────────────────
ALTER TABLE liquidaciones
  ADD COLUMN IF NOT EXISTS numero_revision INTEGER NOT NULL DEFAULT 1;


-- ── 2. Bajar el UNIQUE(consorcio_id, periodo) de v7 ──────────
-- Se busca por definición y no por nombre fijo, porque el nombre que le puso
-- Postgres depende de cómo se creó la tabla.
DO $$
DECLARE
  c RECORD;
BEGIN
  FOR c IN
    SELECT con.conname
    FROM   pg_constraint con
    JOIN   pg_class      rel ON rel.oid = con.conrelid
    JOIN   pg_namespace  nsp ON nsp.oid = rel.relnamespace
    WHERE  rel.relname = 'liquidaciones'
      AND  nsp.nspname = 'public'
      AND  con.contype = 'u'
      AND  (
             SELECT array_agg(att.attname ORDER BY att.attname)
             FROM   unnest(con.conkey) AS k(attnum)
             JOIN   pg_attribute att
                    ON att.attrelid = con.conrelid AND att.attnum = k.attnum
           ) = ARRAY['consorcio_id', 'periodo']
  LOOP
    EXECUTE format('ALTER TABLE liquidaciones DROP CONSTRAINT %I', c.conname);
    RAISE NOTICE 'Constraint % eliminada', c.conname;
  END LOOP;
END $$;


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


-- ── Verificación ─────────────────────────────────────────────
-- SELECT periodo, numero_revision, estado, total_egresos
-- FROM   liquidaciones
-- WHERE  consorcio_id = '<tu-consorcio>'
-- ORDER  BY periodo DESC, numero_revision;
