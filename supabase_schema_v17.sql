-- ============================================================
--  Niddo — Supabase Schema v17 (el alta del vecino la aprueba el admin)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v16 antes
-- ============================================================
--
--  Hasta ahora, cualquiera con una cuenta elegía un edificio de la lista, se
--  quedaba con una unidad libre y entraba: veía las expensas de esa unidad,
--  los gastos del consorcio, los comunicados y los archivos. Nadie confirmaba
--  que esa unidad fuera suya.
--
--  El camino "no encuentro mi unidad" ya dejaba al vecino en espera, pero le
--  escribía `consorcio_id` igual, así que la mitad de las pantallas —gastos,
--  comunicados, archivos, medios de pago— ya le respondían con datos del
--  edificio antes de que el administrador lo mirara.
--
--  El modelo nuevo separa lo que el vecino pide de lo que tiene. `consorcio_id`
--  y `unidad_id` pasan a significar "aprobado y adentro", y nada más los
--  escribe que la aprobación del administrador. La solicitud vive en las
--  columnas `*_solicitado_id`, que ninguna consulta de datos mira.
--
--  Es idempotente: se puede correr más de una vez.
-- ============================================================


-- ── 1. Columnas de la solicitud ──────────────────────────────
ALTER TABLE vecinos
  -- 'pendiente' | 'aprobado' | 'rechazado'. NULL solo en el vecino recién
  -- creado por Auth0 que todavía no eligió edificio.
  ADD COLUMN IF NOT EXISTS estado_asociacion       TEXT,

  -- Lo que el vecino pidió. Deliberadamente separado de consorcio_id: si
  -- compartieran columna, cada consulta que hoy filtra por consorcio_id
  -- tendría que acordarse de excluir a los pendientes.
  ADD COLUMN IF NOT EXISTS consorcio_solicitado_id UUID REFERENCES consorcios(id) ON DELETE SET NULL,

  -- NULL = "no encuentro mi unidad": el administrador elige cuál al aprobar.
  ADD COLUMN IF NOT EXISTS unidad_solicitada_id    UUID REFERENCES unidades_funcionales(id) ON DELETE SET NULL,

  ADD COLUMN IF NOT EXISTS solicitud_at            TIMESTAMPTZ,

  -- Para que el rechazo no sea una pared muda: el vecino lee el motivo y sabe
  -- si tiene que volver a pedir con otra unidad o llamar por teléfono.
  ADD COLUMN IF NOT EXISTS motivo_rechazo          TEXT;


ALTER TABLE vecinos
  DROP CONSTRAINT IF EXISTS vecinos_estado_asociacion_valido;
ALTER TABLE vecinos
  ADD CONSTRAINT vecinos_estado_asociacion_valido
  CHECK (estado_asociacion IS NULL
         OR estado_asociacion IN ('pendiente', 'aprobado', 'rechazado'));


-- ── 2. Los vecinos que ya están adentro siguen adentro ───────
-- Sin esto, el primer deploy después de la migración deja afuera a todos los
-- vecinos existentes, porque el gate nuevo mira `estado_asociacion`.
UPDATE vecinos
   SET estado_asociacion = 'aprobado'
 WHERE estado_asociacion IS NULL
   AND consorcio_id IS NOT NULL
   AND COALESCE(unidad, '') <> 'Pendiente';


-- ── 3. Los que estaban esperando pasan al modelo nuevo ───────
-- Eran los del camino "no encuentro mi unidad". Se les mueve el consorcio a la
-- columna de solicitud y se les vacía consorcio_id, que es justamente lo que
-- les estaba mostrando datos del edificio sin aprobación.
UPDATE vecinos
   SET estado_asociacion       = 'pendiente',
       consorcio_solicitado_id = consorcio_id,
       unidad_solicitada_id    = NULL,
       solicitud_at            = COALESCE(solicitud_at, now()),
       consorcio_id            = NULL
 WHERE estado_asociacion IS NULL
   AND consorcio_id IS NOT NULL
   AND COALESCE(unidad, '') = 'Pendiente';


-- ── 4. Índice para la bandeja del administrador ──────────────
CREATE INDEX IF NOT EXISTS idx_vecinos_solicitud_pendiente
  ON vecinos(consorcio_solicitado_id)
  WHERE estado_asociacion = 'pendiente';


-- ── 5. Verificación ──────────────────────────────────────────
-- Cuántos quedaron en cada estado. Si ves vecinos con NULL y consorcio_id
-- cargado, algo del paso 2 no los alcanzó: avisá antes de deployar.
SELECT COALESCE(estado_asociacion, '(sin estado)') AS estado,
       COUNT(*)                                    AS vecinos,
       COUNT(consorcio_id)                         AS con_consorcio,
       COUNT(consorcio_solicitado_id)              AS con_solicitud
  FROM vecinos
 GROUP BY 1
 ORDER BY 1;
