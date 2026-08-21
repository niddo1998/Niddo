-- ============================================================
--  Niddo — Supabase Schema v18 (prorrateo por coeficientes)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v17 antes
-- ============================================================
--
--  Los cuatro sistemas del mercado —SIPAC, Octopus, Expensas Flow y Consorcio
--  Abierto— reparten por VARIOS coeficientes a la vez, no por uno. SIPAC usa
--  A, C y E; Consorcio Abierto, "% ORD A" y "% ORD B". Por eso los cuatro
--  imprimen "SUBTOTALES POR COEFICIENTE" al cierre de cada rubro.
--
--  Para qué sirve: un edificio con cocheras o locales no puede repartir la
--  factura del ascensor igual que la del seguro. El ascensor va por un
--  coeficiente donde la cochera pesa 0; el seguro, por otro donde pesa.
--
--  `liquidacion_prorrateo` ya tenía el molde de dos (porcentaje_a/expensa_a y
--  porcentaje_c/adicional_ordinaria), pero faltaba la mitad que decide: ningún
--  gasto podía declarar por cuál se reparte. Eso es `gastos.coeficiente`.
--
--  Es idempotente y no cambia el comportamiento por sí sola: todo nace en 'A',
--  que es como se reparte hoy.
-- ============================================================


-- ── 1. Cada gasto declara por qué coeficiente se reparte ─────
ALTER TABLE gastos
  ADD COLUMN IF NOT EXISTS coeficiente TEXT NOT NULL DEFAULT 'A';

ALTER TABLE gastos DROP CONSTRAINT IF EXISTS gastos_coeficiente_valido;
ALTER TABLE gastos ADD CONSTRAINT gastos_coeficiente_valido
  CHECK (coeficiente IN ('A', 'B', 'C', 'E'));

COMMENT ON COLUMN gastos.coeficiente IS
  'Coeficiente de reparto (A/B/C/E). La UF tiene un porcentaje para cada uno.';


-- ── 2. La unidad tiene un porcentaje por coeficiente ─────────
-- a y c ya existen desde v7. Se suman b y e para cerrar el juego.
ALTER TABLE unidades_funcionales
  ADD COLUMN IF NOT EXISTS porcentaje_b NUMERIC(6,3) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS porcentaje_e NUMERIC(6,3) DEFAULT 0;


-- ── 3. El prorrateo guarda el reparto de cada coeficiente ────
ALTER TABLE liquidacion_prorrateo
  ADD COLUMN IF NOT EXISTS porcentaje_b     NUMERIC(6,3)  DEFAULT 0,
  ADD COLUMN IF NOT EXISTS expensa_b        NUMERIC(12,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS porcentaje_e     NUMERIC(6,3)  DEFAULT 0,
  ADD COLUMN IF NOT EXISTS expensa_e        NUMERIC(12,2) DEFAULT 0,
  -- Consorcio Abierto cobra las reservas de amenities en la expensa y les da
  -- columna propia. Niddo ya tiene amenities y reservas que no cobran nada.
  ADD COLUMN IF NOT EXISTS uso_amenities    NUMERIC(12,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS descuentos       NUMERIC(12,2) DEFAULT 0,
  -- Los cuatro imprimen las dos columnas de total. Se guarda calculado para
  -- que el PDF y el mail no puedan discrepar por redondear distinto.
  ADD COLUMN IF NOT EXISTS total_segundo_vto NUMERIC(12,2) DEFAULT 0;


-- ── 4. Las tasas son del consorcio, no del código ────────────
-- Octopus y Consorcio Abierto las declaran en el encabezado de la liquidación
-- ("Tasa de interés: 3,000 %", "Recargo 2º vto: 3,00 %"). En Niddo estaban
-- escritas a mano en el HTML de la pantalla de Configuración.
ALTER TABLE consorcios
  ADD COLUMN IF NOT EXISTS tasa_interes_mora  NUMERIC(6,3) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS dias_gracia_mora   SMALLINT     DEFAULT 0,
  ADD COLUMN IF NOT EXISTS recargo_segundo_vto NUMERIC(5,2) DEFAULT 0;


-- ── 5. El detalle que la Ley 941 obliga a rendir ─────────────
-- Los cuatro imprimen, por gasto: proveedor, CUIT, tipo y número de
-- comprobante, y fecha de pago. Niddo mostraba categoría e importe.
ALTER TABLE gastos
  ADD COLUMN IF NOT EXISTS comprobante_tipo   TEXT,
  ADD COLUMN IF NOT EXISTS comprobante_numero TEXT;

ALTER TABLE liquidacion_items
  ADD COLUMN IF NOT EXISTS proveedor_nombre   TEXT,
  ADD COLUMN IF NOT EXISTS proveedor_cuit     TEXT,
  ADD COLUMN IF NOT EXISTS comprobante_tipo   TEXT,
  ADD COLUMN IF NOT EXISTS comprobante_numero TEXT,
  ADD COLUMN IF NOT EXISTS fecha_pago         DATE,
  ADD COLUMN IF NOT EXISTS coeficiente        TEXT DEFAULT 'A';


-- ── 6. El cobro sabe de qué liquidación salió ────────────────
-- Hoy la liquidación y los cobros son dos mundos: el mail lleva el total
-- prorrateado y la app del vecino muestra un monto plano cargado a mano.
ALTER TABLE cobros
  ADD COLUMN IF NOT EXISTS liquidacion_id UUID REFERENCES liquidaciones(id) ON DELETE SET NULL;

-- Un cobro por unidad y liquidación: es lo que hace que emitir dos veces no
-- duplique la deuda del vecino. El chequeo en Python no cierra la ventana
-- entre el SELECT y el INSERT; el índice sí.
CREATE UNIQUE INDEX IF NOT EXISTS idx_cobros_liquidacion_unidad
  ON cobros(liquidacion_id, unidad_id)
  WHERE liquidacion_id IS NOT NULL;


-- ── 7. Verificación ──────────────────────────────────────────
SELECT 'gastos por coeficiente' AS control, coeficiente, COUNT(*) AS filas
  FROM gastos GROUP BY coeficiente ORDER BY coeficiente;


-- ── 8. Precio de uso del amenity ─────────────────────────────
-- Consorcio Abierto cobra las reservas en la expensa, con columna propia.
-- NULL o 0 = gratis, que es como se comportan todos los amenities hoy.
ALTER TABLE amenities
  ADD COLUMN IF NOT EXISTS precio_uso NUMERIC(12,2);

COMMENT ON COLUMN amenities.precio_uso IS
  'Cargo por reserva confirmada, que se suma a la expensa de la unidad. NULL = gratis';
