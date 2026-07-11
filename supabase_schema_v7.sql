-- ============================================================
--  Niddo — Supabase Schema v7 (Liquidaciones de Expensas)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v6 antes
-- ============================================================

-- ── Agregar porcentajes de prorrateo a unidades_funcionales ──
ALTER TABLE unidades_funcionales ADD COLUMN IF NOT EXISTS porcentaje_a NUMERIC(6,3) DEFAULT 0;
ALTER TABLE unidades_funcionales ADD COLUMN IF NOT EXISTS porcentaje_c NUMERIC(6,3) DEFAULT 0;

-- ── Agregar datos bancarios al consorcio ─────────────────────
ALTER TABLE consorcios ADD COLUMN IF NOT EXISTS banco_nombre TEXT;
ALTER TABLE consorcios ADD COLUMN IF NOT EXISTS banco_sucursal TEXT;
ALTER TABLE consorcios ADD COLUMN IF NOT EXISTS banco_cuenta TEXT;
ALTER TABLE consorcios ADD COLUMN IF NOT EXISTS banco_cbu TEXT;
ALTER TABLE consorcios ADD COLUMN IF NOT EXISTS banco_cuit_pago TEXT;


-- ── Tabla: liquidaciones ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS liquidaciones (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id        UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  admin_id            UUID NOT NULL REFERENCES administradores(id) ON DELETE CASCADE,
  periodo             TEXT NOT NULL,                -- "2026-07"
  fecha_vencimiento_1 DATE,
  fecha_vencimiento_2 DATE,
  interes_2_vto       NUMERIC(5,2) DEFAULT 0,      -- % recargo 2do vto

  -- Resumen financiero
  saldo_inicial       NUMERIC(14,2) DEFAULT 0,
  total_ingresos      NUMERIC(14,2) DEFAULT 0,
  total_egresos       NUMERIC(14,2) DEFAULT 0,
  saldo_final         NUMERIC(14,2) DEFAULT 0,

  -- Composición de saldo
  saldo_bancario      NUMERIC(14,2) DEFAULT 0,
  saldo_superfondo    NUMERIC(14,2) DEFAULT 0,
  saldo_administrador NUMERIC(14,2) DEFAULT 0,

  -- Notas y estado
  notas               TEXT,
  estado              TEXT DEFAULT 'borrador',       -- borrador / publicada / cerrada
  created_at          TIMESTAMPTZ DEFAULT now(),

  UNIQUE(consorcio_id, periodo)
);

CREATE INDEX IF NOT EXISTS idx_liquidaciones_consorcio ON liquidaciones(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_liquidaciones_periodo   ON liquidaciones(periodo);
CREATE INDEX IF NOT EXISTS idx_liquidaciones_estado    ON liquidaciones(estado);


-- ── Tabla: liquidacion_rubros ────────────────────────────────
CREATE TABLE IF NOT EXISTS liquidacion_rubros (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  liquidacion_id        UUID NOT NULL REFERENCES liquidaciones(id) ON DELETE CASCADE,
  numero_rubro          INTEGER NOT NULL,            -- 1-10
  nombre                TEXT NOT NULL,
  subtotal              NUMERIC(14,2) DEFAULT 0,
  porcentaje_sobre_total NUMERIC(5,2) DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_liq_rubros_liquidacion ON liquidacion_rubros(liquidacion_id);


-- ── Tabla: liquidacion_items ─────────────────────────────────
CREATE TABLE IF NOT EXISTS liquidacion_items (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rubro_id      UUID NOT NULL REFERENCES liquidacion_rubros(id) ON DELETE CASCADE,
  descripcion   TEXT NOT NULL,
  monto         NUMERIC(14,2) DEFAULT 0,
  gasto_id      UUID REFERENCES gastos(id) ON DELETE SET NULL,  -- vincula con gasto real
  es_cuota      BOOLEAN DEFAULT false,
  cuota_actual  INTEGER,
  cuota_total   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_liq_items_rubro  ON liquidacion_items(rubro_id);
CREATE INDEX IF NOT EXISTS idx_liq_items_gasto  ON liquidacion_items(gasto_id);


-- ── Tabla: liquidacion_prorrateo ─────────────────────────────
CREATE TABLE IF NOT EXISTS liquidacion_prorrateo (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  liquidacion_id      UUID NOT NULL REFERENCES liquidaciones(id) ON DELETE CASCADE,
  unidad_id           UUID NOT NULL REFERENCES unidades_funcionales(id) ON DELETE CASCADE,
  saldo_anterior      NUMERIC(14,2) DEFAULT 0,
  pago_realizado      NUMERIC(14,2) DEFAULT 0,
  saldo_pendiente     NUMERIC(14,2) DEFAULT 0,
  interes_mora        NUMERIC(14,2) DEFAULT 0,
  porcentaje_a        NUMERIC(6,3) DEFAULT 0,
  expensa_a           NUMERIC(14,2) DEFAULT 0,
  porcentaje_c        NUMERIC(6,3) DEFAULT 0,
  adicional_ordinaria NUMERIC(14,2) DEFAULT 0,
  extraordinaria      NUMERIC(14,2) DEFAULT 0,
  redondeo            NUMERIC(14,2) DEFAULT 0,
  total_unidad        NUMERIC(14,2) DEFAULT 0,

  UNIQUE(liquidacion_id, unidad_id)
);

CREATE INDEX IF NOT EXISTS idx_liq_prorrateo_liquidacion ON liquidacion_prorrateo(liquidacion_id);
CREATE INDEX IF NOT EXISTS idx_liq_prorrateo_unidad      ON liquidacion_prorrateo(unidad_id);


-- ── Tabla: resumen_envios ────────────────────────────────────
CREATE TABLE IF NOT EXISTS resumen_envios (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  liquidacion_id  UUID NOT NULL REFERENCES liquidaciones(id) ON DELETE CASCADE,
  unidad_id       UUID NOT NULL REFERENCES unidades_funcionales(id) ON DELETE CASCADE,
  canal           TEXT DEFAULT 'email',              -- email / whatsapp / plataforma
  estado          TEXT DEFAULT 'pendiente',           -- pendiente / enviado / leido / fallido
  email_destino   TEXT,
  fecha_envio     TIMESTAMPTZ,
  fecha_lectura   TIMESTAMPTZ,
  error_detalle   TEXT,
  resumen_html    TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_resumen_envios_liquidacion ON resumen_envios(liquidacion_id);
CREATE INDEX IF NOT EXISTS idx_resumen_envios_unidad      ON resumen_envios(unidad_id);
CREATE INDEX IF NOT EXISTS idx_resumen_envios_estado      ON resumen_envios(estado);


-- ── Tabla: envio_programado ──────────────────────────────────
CREATE TABLE IF NOT EXISTS envio_programado (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id  UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  admin_id      UUID NOT NULL REFERENCES administradores(id) ON DELETE CASCADE,
  dia_mes       INTEGER NOT NULL DEFAULT 1,          -- 1-28
  hora_envio    TIME DEFAULT '09:00',
  canal         TEXT DEFAULT 'email',                -- email / whatsapp / ambos
  activo        BOOLEAN DEFAULT true,
  created_at    TIMESTAMPTZ DEFAULT now(),

  UNIQUE(consorcio_id)
);

CREATE INDEX IF NOT EXISTS idx_envio_programado_consorcio ON envio_programado(consorcio_id);
