-- ============================================================
--  Niddo — Supabase Schema v3 (Amenities & Reservas)
--  Agregar al SQL Editor de Supabase (ejecutar después de v2)
-- ============================================================

-- ── Tabla: amenities ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS amenities (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id    UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  nombre          TEXT NOT NULL,
  descripcion     TEXT,
  condiciones_uso TEXT,
  capacidad_maxima INTEGER,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_amenities_consorcio ON amenities(consorcio_id);


-- ── Tabla: reservas_amenities ─────────────────────────────
CREATE TABLE IF NOT EXISTS reservas_amenities (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  amenity_id        UUID NOT NULL REFERENCES amenities(id) ON DELETE CASCADE,
  vecino_id         UUID REFERENCES vecinos(id) ON DELETE SET NULL,
  fecha             DATE NOT NULL,
  hora_inicio       TIME NOT NULL,
  hora_fin          TIME NOT NULL,
  estado            TEXT DEFAULT 'confirmada', -- confirmada/cancelada
  created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reservas_amenities_amenity ON reservas_amenities(amenity_id);
CREATE INDEX IF NOT EXISTS idx_reservas_amenities_vecino  ON reservas_amenities(vecino_id);
CREATE INDEX IF NOT EXISTS idx_reservas_amenities_fecha   ON reservas_amenities(fecha);
