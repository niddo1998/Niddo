-- ============================================================
--  Niddo — Supabase Schema v5 (Comprobantes de Gastos)
--  Agregar al SQL Editor de Supabase (ejecutar después de v4)
-- ============================================================

-- ── Tabla: comprobantes_gastos ─────────────────────────────
CREATE TABLE IF NOT EXISTS comprobantes_gastos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  gasto_id        UUID UNIQUE NOT NULL REFERENCES gastos(id) ON DELETE CASCADE,
  archivo_nombre  TEXT NOT NULL,
  archivo_base64  TEXT NOT NULL,
  mime_type       TEXT DEFAULT 'application/pdf',
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comprobantes_gasto ON comprobantes_gastos(gasto_id);
