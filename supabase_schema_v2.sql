-- ============================================================
--  Niddo — Supabase Schema v2
--  Agregar al SQL Editor de Supabase (ejecutar después del v1)
-- ============================================================

-- ── Tabla: consorcios ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS consorcios (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre           TEXT NOT NULL,
  direccion        TEXT,
  cuit             TEXT,
  pisos            INTEGER,
  unidades_totales INTEGER,
  encargado_nombre TEXT,
  encargado_tel    TEXT,
  admin_id         UUID REFERENCES administradores(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consorcios_admin ON consorcios(admin_id);


-- ── Tabla: unidades_funcionales ────────────────────────────
CREATE TABLE IF NOT EXISTS unidades_funcionales (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id    UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  numero          TEXT NOT NULL,         -- "3B", "PH1", "01"
  piso            TEXT,
  tipo            TEXT DEFAULT 'departamento',  -- departamento/local/cochera
  superficie_m2   NUMERIC(8,2),
  vecino_nombre   TEXT,
  vecino_email    TEXT,
  vecino_id       UUID REFERENCES vecinos(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ufs_consorcio ON unidades_funcionales(consorcio_id);


-- ── Tabla: proveedores ────────────────────────────────────
CREATE TABLE IF NOT EXISTS proveedores (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre     TEXT NOT NULL,
  cuit       TEXT,
  rubro      TEXT,   -- electricidad/gas/agua/limpieza/ascensor/seguro/otro
  email      TEXT,
  telefono   TEXT,
  admin_id   UUID REFERENCES administradores(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_proveedores_admin ON proveedores(admin_id);


-- ── Tabla: gastos ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gastos (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consorcio_id      UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  proveedor_id      UUID REFERENCES proveedores(id) ON DELETE SET NULL,
  descripcion       TEXT NOT NULL,
  categoria         TEXT,   -- electricidad/gas/agua/limpieza/ascensor/seguro/honorarios/otro
  monto             NUMERIC(12,2) NOT NULL,
  fecha_gasto       DATE NOT NULL DEFAULT CURRENT_DATE,
  fecha_vencimiento DATE,
  pagado            BOOLEAN DEFAULT false,
  fecha_pago        DATE,
  metodo_pago       TEXT,   -- transferencia/cheque/efectivo/debito
  recurrente        BOOLEAN DEFAULT false,
  frecuencia        TEXT,   -- mensual/bimestral/trimestral/anual
  archivo_nombre    TEXT,
  notas             TEXT,
  admin_id          UUID REFERENCES administradores(id) ON DELETE SET NULL,
  created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gastos_consorcio ON gastos(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha     ON gastos(fecha_gasto);
CREATE INDEX IF NOT EXISTS idx_gastos_pagado    ON gastos(pagado);


-- ── Tabla: cobros ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cobros (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  unidad_id         UUID NOT NULL REFERENCES unidades_funcionales(id) ON DELETE CASCADE,
  consorcio_id      UUID NOT NULL REFERENCES consorcios(id) ON DELETE CASCADE,
  periodo           TEXT NOT NULL,          -- "2026-05"
  monto_base        NUMERIC(12,2) NOT NULL,
  interes_mora      NUMERIC(12,2) DEFAULT 0,
  total             NUMERIC(12,2) NOT NULL,
  estado            TEXT DEFAULT 'pendiente', -- pendiente/pagado/vencido/en_mora
  fecha_vencimiento DATE,
  fecha_pago        DATE,
  comprobante_nombre TEXT,
  notas             TEXT,
  created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cobros_consorcio ON cobros(consorcio_id);
CREATE INDEX IF NOT EXISTS idx_cobros_unidad    ON cobros(unidad_id);
CREATE INDEX IF NOT EXISTS idx_cobros_periodo   ON cobros(periodo);
CREATE INDEX IF NOT EXISTS idx_cobros_estado    ON cobros(estado);


-- ── FK de vecinos a consorcios (existía como comentario) ──
-- ALTER TABLE vecinos ADD COLUMN IF NOT EXISTS consorcio_id UUID REFERENCES consorcios(id);
