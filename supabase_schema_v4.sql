-- ============================================================
--  Niddo — Supabase Schema v4 (Múltiples Vecinos por Unidad & Roles)
--  Agregar al SQL Editor de Supabase (ejecutar después de v3)
-- ============================================================

-- ── Agregar columnas a la tabla vecinos ─────────────────────
ALTER TABLE vecinos ADD COLUMN IF NOT EXISTS rol TEXT DEFAULT 'propietario';
ALTER TABLE vecinos ADD COLUMN IF NOT EXISTS unidad_id UUID REFERENCES unidades_funcionales(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_vecinos_unidad_id ON vecinos(unidad_id);

-- ── Migrar relaciones existentes ───────────────────────────
-- Vincular vecinos existentes a sus respectivas UFs (unidades_funcionales)
UPDATE vecinos v
SET unidad_id = uf.id
FROM unidades_funcionales uf
WHERE v.consorcio_id = uf.consorcio_id 
  AND v.unidad = uf.numero
  AND v.unidad_id IS NULL;

-- Sincronizar unidades_funcionales.vecino_id con el primer vecino para compatibilidad
UPDATE unidades_funcionales uf
SET vecino_id = v.id
FROM vecinos v
WHERE uf.id = v.unidad_id 
  AND uf.vecino_id IS NULL;
