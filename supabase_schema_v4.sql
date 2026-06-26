-- ============================================================
--  Niddo — Supabase Schema v4
--  Tabla para comunicados generales y notificaciones
--  Agregar al SQL Editor de Supabase (ejecutar después de v3)
-- ============================================================

CREATE TABLE IF NOT EXISTS comunicados (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_id      UUID NOT NULL REFERENCES administradores(id) ON DELETE CASCADE,
  consorcio_id  UUID REFERENCES consorcios(id) ON DELETE CASCADE, -- NULL si es para todos los consorcios
  unidad_id     UUID REFERENCES unidades_funcionales(id) ON DELETE CASCADE, -- NULL si es para todo el consorcio
  asunto        TEXT NOT NULL,
  cuerpo        TEXT NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Índices para optimizar búsquedas
CREATE INDEX IF NOT EXISTS idx_comunicados_admin ON comunicados(admin_id);
CREATE INDEX IF NOT EXISTS idx_comunicados_consorcio ON comunicados(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_comunicados_unidad ON comunicados(unidad_id);

-- Habilitar RLS
ALTER TABLE comunicados ENABLE ROW LEVEL SECURITY;

-- Políticas de RLS
CREATE POLICY "Permitir todo a service_role" ON comunicados
  FOR ALL USING (true);
