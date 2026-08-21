-- ============================================================
--  Niddo — Supabase Schema v16 (capacidad y cupo de amenities)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v15 antes
-- ============================================================
--
--  `amenities.capacidad_maxima` existe desde v3 y el admin la carga desde el
--  panel ("Ej: 30"), pero nunca se leyó: son personas, y la reserva no decía
--  cuántas venían, así que no había contra qué compararla.
--
--  `max_reservas_mes` es nuevo y va en el amenity, no en una constante del
--  código: cuántas veces por mes se puede tomar el SUM es una decisión de cada
--  edificio. NULL = sin límite, que es como se comporta hoy.

ALTER TABLE reservas_amenities ADD COLUMN IF NOT EXISTS cantidad_personas INTEGER;
ALTER TABLE amenities           ADD COLUMN IF NOT EXISTS max_reservas_mes  INTEGER;

COMMENT ON COLUMN reservas_amenities.cantidad_personas IS 'Cuántas personas van, para contrastar con amenities.capacidad_maxima';
COMMENT ON COLUMN amenities.max_reservas_mes IS 'Tope de reservas por vecino y por mes en este espacio. NULL = sin límite';
