-- ============================================================
--  Niddo — Supabase Schema v3
--  Tabla para solicitudes de vinculación entre vecinos y UFs
--  Agregar al SQL Editor de Supabase (ejecutar después de v2)
-- ============================================================

CREATE TABLE IF NOT EXISTS solicitudes_vinculacion (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vecino_id     UUID NOT NULL REFERENCES vecinos(id) ON DELETE CASCADE,
  consorcio_id  UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  unidad_id     UUID NOT NULL REFERENCES unidades_funcionales(id) ON DELETE CASCADE,
  estado        TEXT NOT NULL DEFAULT 'pendiente', -- 'pendiente', 'aprobada', 'rechazada'
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Índices para optimizar búsquedas
CREATE INDEX IF NOT EXISTS idx_solicitudes_consorcio ON solicitudes_vinculacion(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_vecino ON solicitudes_vinculacion(vecino_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_estado ON solicitudes_vinculacion(estado);

-- Habilitar RLS
ALTER TABLE solicitudes_vinculacion ENABLE ROW LEVEL SECURITY;

-- Políticas básicas de RLS (el backend al usar service_role las bypassea, pero es buena práctica)
CREATE POLICY "Permitir todo a service_role" ON solicitudes_vinculacion
  FOR ALL USING (true);
