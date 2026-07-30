-- ============================================================
--  Niddo — Supabase Schema v9 (Prorrateo lineal + gastos por UF)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v8 antes
-- ============================================================
--
--  Problema que resuelve:
--  v7 agregó `unidades_funcionales.porcentaje_a/porcentaje_c` con DEFAULT 0 y
--  el prorrateo se calculaba como `total_egresos * porcentaje_a / 100`. Como no
--  hay ninguna pantalla que cargue esos porcentajes, en la práctica siempre
--  valen 0 y toda la tabla de prorrateo daba $0 por unidad.
--
--  Solución (dos partes):
--   1. El reparto pasa a ser lineal: el gasto general se divide en partes
--      iguales entre todas las UFs del consorcio. Los porcentajes se siguen
--      respetando si algún día se cargan y suman 100 (ver _generar_prorrateo).
--   2. Un gasto puede ser general del consorcio (lo normal) o específico de una
--      UF — el juego de llaves extra que pidió el 3º B, por ejemplo. El gasto
--      específico NO se prorratea: se le carga entero a esa unidad.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================


-- ── 1. Alcance del gasto: NULL = general del consorcio ───────
-- ON DELETE SET NULL y no CASCADE a propósito: si se borra la UF preferimos que
-- el gasto quede como general del consorcio antes que desaparecer y descuadrar
-- una liquidación ya emitida.
ALTER TABLE gastos
  ADD COLUMN IF NOT EXISTS unidad_id UUID REFERENCES unidades_funcionales(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_gastos_unidad ON gastos(unidad_id);


-- ── 2. El ítem liquidado se lleva el alcance del gasto ───────
-- El prorrateo se calcula sobre los ítems de la liquidación, no sobre la tabla
-- `gastos`: una liquidación vieja tiene que seguir repartiéndose como se emitió
-- aunque después se edite el gasto original.
ALTER TABLE liquidacion_items
  ADD COLUMN IF NOT EXISTS unidad_id UUID REFERENCES unidades_funcionales(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_liq_items_unidad ON liquidacion_items(unidad_id);


-- ── 3. Columna de gastos particulares en el prorrateo ────────
-- Suma de los gastos específicos de esa UF en esta liquidación. Va aparte de
-- `expensa_a` para que el resumen pueda mostrarle al vecino qué le tocó a él y
-- qué es parte prorrateada del edificio.
ALTER TABLE liquidacion_prorrateo
  ADD COLUMN IF NOT EXISTS gastos_particulares NUMERIC(14,2) DEFAULT 0;


-- ── 4. Backfill ──────────────────────────────────────────────
-- Todo lo que ya existía era general del consorcio: unidad_id queda en NULL y
-- gastos_particulares en 0, que es justamente el DEFAULT. No hay nada que
-- migrar; las liquidaciones viejas conservan sus montos tal cual se emitieron.
UPDATE liquidacion_prorrateo
SET    gastos_particulares = 0
WHERE  gastos_particulares IS NULL;


-- ── 5. Refrescar el caché de esquema de PostgREST ────────────
-- Sin esto la API sigue respondiendo PGRST204 "column not found" para las
-- columnas recién creadas hasta que PostgREST recicle solo.
NOTIFY pgrst, 'reload schema';


-- ============================================================
--  Verificación — correr aparte y leer el resultado
-- ============================================================
--
-- (a) Las tres columnas nuevas tienen que aparecer:
--
-- SELECT table_name, column_name, data_type
-- FROM   information_schema.columns
-- WHERE  (table_name, column_name) IN (
--          ('gastos', 'unidad_id'),
--          ('liquidacion_items', 'unidad_id'),
--          ('liquidacion_prorrateo', 'gastos_particulares'))
-- ORDER  BY table_name;
--
-- (b) Cuántos gastos quedaron marcados como específicos de una UF:
--
-- SELECT CASE WHEN unidad_id IS NULL THEN 'general' ELSE 'particular' END AS alcance,
--        count(*), sum(monto)
-- FROM   gastos
-- GROUP  BY 1;
