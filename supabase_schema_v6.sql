-- ============================================================
--  Niddo — Supabase Schema v6 (Dashboard Vecinos Completo)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v5 antes
-- ============================================================

-- ── Tabla: vecinos_unidades (múltiples unidades por vecino) ─
CREATE TABLE IF NOT EXISTS vecinos_unidades (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vecino_id     UUID NOT NULL REFERENCES vecinos(id) ON DELETE CASCADE,
  unidad_id     UUID NOT NULL REFERENCES unidades_funcionales(id) ON DELETE CASCADE,
  consorcio_id  UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  rol           TEXT DEFAULT 'propietario',
  activo        BOOLEAN DEFAULT true,
  created_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE(vecino_id, unidad_id)
);

CREATE INDEX IF NOT EXISTS idx_vecinos_unidades_vecino    ON vecinos_unidades(vecino_id);
CREATE INDEX IF NOT EXISTS idx_vecinos_unidades_unidad    ON vecinos_unidades(unidad_id);
CREATE INDEX IF NOT EXISTS idx_vecinos_unidades_consorcio ON vecinos_unidades(consorcio_id);

-- Migrar relaciones existentes
INSERT INTO vecinos_unidades (vecino_id, unidad_id, consorcio_id, rol)
SELECT v.id, v.unidad_id, v.consorcio_id, COALESCE(v.rol, 'propietario')
FROM vecinos v
WHERE v.unidad_id IS NOT NULL AND v.consorcio_id IS NOT NULL
ON CONFLICT (vecino_id, unidad_id) DO NOTHING;


-- ── Tabla: comunicados ────────────────────────────────────
CREATE TABLE IF NOT EXISTS comunicados (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id  UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  admin_id      UUID REFERENCES administradores(id) ON DELETE SET NULL,
  titulo        TEXT NOT NULL,
  cuerpo        TEXT NOT NULL,
  importante    BOOLEAN DEFAULT false,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comunicados_consorcio  ON comunicados(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_comunicados_fecha      ON comunicados(created_at DESC);


-- ── Tabla: comunicados_leidos ────────────────────────────
CREATE TABLE IF NOT EXISTS comunicados_leidos (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  comunicado_id  UUID NOT NULL REFERENCES comunicados(id) ON DELETE CASCADE,
  vecino_id      UUID NOT NULL REFERENCES vecinos(id) ON DELETE CASCADE,
  leido_at       TIMESTAMPTZ DEFAULT now(),
  UNIQUE(comunicado_id, vecino_id)
);

CREATE INDEX IF NOT EXISTS idx_com_leidos_vecino ON comunicados_leidos(vecino_id);


-- ── Tabla: reclamos ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS reclamos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id    UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  vecino_id       UUID NOT NULL REFERENCES vecinos(id) ON DELETE CASCADE,
  unidad_id       UUID REFERENCES unidades_funcionales(id) ON DELETE SET NULL,
  titulo          TEXT NOT NULL,
  descripcion     TEXT NOT NULL,
  categoria       TEXT DEFAULT 'otro',
  estado          TEXT DEFAULT 'activo',
  respuesta_admin TEXT,
  adjunto_nombre  TEXT,
  adjunto_base64  TEXT,
  adjunto_mime    TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reclamos_consorcio ON reclamos(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_reclamos_vecino    ON reclamos(vecino_id);
CREATE INDEX IF NOT EXISTS idx_reclamos_estado    ON reclamos(estado);


-- ── Tabla: votaciones ────────────────────────────────────
CREATE TABLE IF NOT EXISTS votaciones (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id     UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  admin_id         UUID REFERENCES administradores(id) ON DELETE SET NULL,
  titulo           TEXT NOT NULL,
  descripcion      TEXT,
  opciones         JSONB DEFAULT '["Si","No","Abstención"]'::jsonb,
  fecha_limite     DATE,
  estado           TEXT DEFAULT 'activa',
  votos_necesarios INTEGER,
  created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_votaciones_consorcio ON votaciones(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_votaciones_estado    ON votaciones(estado);


-- ── Tabla: votos ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS votos (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  votacion_id  UUID NOT NULL REFERENCES votaciones(id) ON DELETE CASCADE,
  vecino_id    UUID NOT NULL REFERENCES vecinos(id) ON DELETE CASCADE,
  unidad_id    UUID REFERENCES unidades_funcionales(id) ON DELETE SET NULL,
  opcion       TEXT NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT now(),
  UNIQUE(votacion_id, unidad_id)
);

CREATE INDEX IF NOT EXISTS idx_votos_votacion ON votos(votacion_id);
CREATE INDEX IF NOT EXISTS idx_votos_vecino   ON votos(vecino_id);


-- ── Tabla: archivos_consorcio ────────────────────────────
CREATE TABLE IF NOT EXISTS archivos_consorcio (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id    UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  admin_id        UUID REFERENCES administradores(id) ON DELETE SET NULL,
  categoria       TEXT NOT NULL,
  nombre          TEXT NOT NULL,
  archivo_base64  TEXT NOT NULL,
  mime_type       TEXT DEFAULT 'application/pdf',
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_archivos_consorcio ON archivos_consorcio(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_archivos_categoria ON archivos_consorcio(categoria);


-- ── Tabla: avisos_pago ──────────────────────────────────
CREATE TABLE IF NOT EXISTS avisos_pago (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id    UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  vecino_id       UUID NOT NULL REFERENCES vecinos(id) ON DELETE CASCADE,
  unidad_id       UUID REFERENCES unidades_funcionales(id) ON DELETE SET NULL,
  cobro_id        UUID REFERENCES cobros(id) ON DELETE SET NULL,
  monto           NUMERIC(12,2),
  fecha_pago      DATE,
  medio_pago      TEXT,
  observaciones   TEXT,
  adjunto_nombre  TEXT,
  adjunto_base64  TEXT,
  adjunto_mime    TEXT,
  estado          TEXT DEFAULT 'pendiente',
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_avisos_pago_consorcio ON avisos_pago(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_avisos_pago_vecino    ON avisos_pago(vecino_id);


-- ── Tabla: medios_pago ───────────────────────────────────
CREATE TABLE IF NOT EXISTS medios_pago (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id  UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  admin_id      UUID REFERENCES administradores(id) ON DELETE SET NULL,
  nombre        TEXT NOT NULL,
  descripcion   TEXT,
  activo        BOOLEAN DEFAULT true,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_medios_pago_consorcio ON medios_pago(consorcio_id);
