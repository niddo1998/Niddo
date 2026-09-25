-- ============================================================
--  Niddo — Supabase Schema v23 (Comunicados que manda un vecino)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v22 antes
-- ============================================================
--
--  Al reservar un amenity, el vecino puede avisarle al resto del edificio
--  ("el sábado a la noche el SUM está ocupado"). Ese aviso es un comunicado
--  más —lo ven todos en Comunicados y le llega también a la administración—,
--  pero lo escribió un vecino y no la administración. Esta columna dice
--  quién, para mostrarlo y para no notificarle a él su propio aviso.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================

alter table comunicados
  add column if not exists autor_vecino_id uuid references vecinos(id) on delete set null;

-- La reserva que lo originó, si vino de una. Borrar la reserva no borra el
-- aviso: ya se leyó.
alter table comunicados
  add column if not exists reserva_id uuid references reservas_amenities(id) on delete set null;

notify pgrst, 'reload schema';
