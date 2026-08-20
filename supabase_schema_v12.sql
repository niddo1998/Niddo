-- ============================================================
--  Niddo — Supabase Schema v12 (Gastos recurrentes de verdad)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v11 antes
-- ============================================================
--
--  Hasta ahora `gastos.recurrente` era una etiqueta: se guardaba el tilde, se
--  pintaba un badge en la tabla y ahí terminaba todo. Nada generaba el gasto
--  del mes siguiente, así que la UI prometía una automatización inexistente y
--  un gasto fijo olvidado quedaba afuera de la liquidación sin aviso.
--
--  A partir de v12 un gasto recurrente es una PLANTILLA y cada período genera
--  un HIJO que apunta a ella:
--
--    plantilla → recurrente = true, dia_carga = 10, gasto_origen_id = NULL
--    hijo      → recurrente = false, gasto_origen_id = <plantilla>,
--                periodo_generado = '2026-09', tarifa_confirmada = false
--
--  Los hijos nacen con `recurrente = false` a propósito: si heredaran el tilde
--  cada hijo generaría sus propios hijos y el mes siguiente habría una
--  progresión geométrica de gastos duplicados.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================


-- ── 1. Columnas nuevas ───────────────────────────────────────
ALTER TABLE gastos
  -- Día del mes en que se genera el gasto. Solo tiene sentido en plantillas.
  -- Se admite 1..31 y la app recorta al último día en los meses cortos: un
  -- gasto con dia_carga = 31 cae el 28 en febrero.
  ADD COLUMN IF NOT EXISTS dia_carga SMALLINT,

  -- Enlace del hijo con la plantilla que lo generó. NULL en las plantillas y
  -- en los gastos comunes cargados a mano.
  ADD COLUMN IF NOT EXISTS gasto_origen_id UUID REFERENCES gastos(id) ON DELETE CASCADE,

  -- Período del hijo en formato YYYY-MM. Junto con gasto_origen_id es lo que
  -- impide generar dos veces el mismo mes.
  ADD COLUMN IF NOT EXISTS periodo_generado TEXT,

  -- Los hijos nacen sin confirmar: copian el monto del período anterior y hay
  -- que revisar si la tarifa cambió. Los gastos cargados a mano nacen en true,
  -- porque el monto lo escribió una persona recién.
  ADD COLUMN IF NOT EXISTS tarifa_confirmada BOOLEAN NOT NULL DEFAULT true;


ALTER TABLE gastos
  DROP CONSTRAINT IF EXISTS gastos_dia_carga_valido;
ALTER TABLE gastos
  ADD CONSTRAINT gastos_dia_carga_valido
  CHECK (dia_carga IS NULL OR (dia_carga BETWEEN 1 AND 31));


-- ── 2. La garantía de no duplicar ────────────────────────────
-- Esta es la pieza importante de la migración. La generación es perezosa: la
-- dispara la request que entra a Gastos. Con dos pestañas abiertas, o con un
-- doble click, dos requests pueden evaluar "¿ya existe el gasto de agosto?" al
-- mismo tiempo, ver que no, y crearlo las dos.
--
-- Un chequeo en Python no cierra esa ventana porque el intervalo entre el
-- SELECT y el INSERT no es atómico. El índice único sí: la segunda inserción
-- falla contra la base y la app la ignora, porque el gasto ya existe, que es
-- exactamente el resultado buscado.
CREATE UNIQUE INDEX IF NOT EXISTS idx_gastos_origen_periodo
  ON gastos(gasto_origen_id, periodo_generado)
  WHERE gasto_origen_id IS NOT NULL;

-- Para el modal de tarifas pendientes, que filtra por admin y por confirmada.
CREATE INDEX IF NOT EXISTS idx_gastos_tarifa_pendiente
  ON gastos(admin_id)
  WHERE tarifa_confirmada = false;

-- Para el barrido de plantillas activas en cada entrada a Gastos.
CREATE INDEX IF NOT EXISTS idx_gastos_plantillas
  ON gastos(admin_id)
  WHERE recurrente = true;


-- ── 3. Los recurrentes que ya existen ────────────────────────
-- Hay gastos con `recurrente = true` cargados antes de esta migración y
-- ninguno tiene día. Pedirle al administrador que los edite uno por uno para
-- destrabar la generación es trabajo manual evitable: el día en que cargó el
-- gasto original es una respuesta razonable y él puede cambiarla después.
--
-- Se recorta a 28 a propósito. Si alguien cargó el seguro un 31 de enero,
-- dia_carga = 31 haría que en febrero el gasto se genere recién el día 28,
-- corriendo la fecha mes a mes de forma difícil de explicar. 28 se comporta
-- igual en los doce meses.
UPDATE gastos
   SET dia_carga = LEAST(EXTRACT(DAY FROM fecha_gasto)::SMALLINT, 28)
 WHERE recurrente = true
   AND dia_carga IS NULL;

-- Los gastos preexistentes no pasaron por el cartel, y hacerlos aparecer ahí
-- de golpe llenaría el modal con meses viejos que nadie va a revisar.
UPDATE gastos
   SET tarifa_confirmada = true
 WHERE tarifa_confirmada IS NULL;


-- ── 4. Verificación ──────────────────────────────────────────
-- Devuelve las plantillas listas para generar. Si está vacío y esperabas
-- filas, revisá que los gastos tengan el tilde de recurrente puesto.
SELECT id, descripcion, frecuencia, dia_carga, fecha_gasto
  FROM gastos
 WHERE recurrente = true
 ORDER BY fecha_gasto DESC
 LIMIT 20;
