-- ============================================================
--  Niddo — Supabase Schema v21 (Conversación en los reclamos y
--                               secciones vistas para los badges)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v20 antes
-- ============================================================
--
--  1. reclamo_mensajes
--     Un reclamo tenía una sola `respuesta_admin` que se pisaba en cada
--     edición, y el vecino no podía contestar. Ahora cada reclamo es una
--     conversación: la descripción original es el primer mensaje (vive en
--     `reclamos`) y lo que siguen escribiendo los dos lados va acá.
--     `respuesta_admin` no se borra: se sigue escribiendo con la última
--     respuesta para los mails y para quien lea la tabla vieja.
--
--  2. secciones_vistas
--     Los badges dejan de contar "lo que está en tal estado" y pasan a contar
--     "lo que llegó desde la última vez que entraste". Entrar a la sección
--     escribe `visto_at`; el número vuelve a aparecer cuando llega algo más
--     nuevo. Una fila por usuario y sección.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================

create table if not exists reclamo_mensajes (
  id             uuid primary key default gen_random_uuid(),
  reclamo_id     uuid not null references reclamos(id) on delete cascade,

  autor          text not null check (autor in ('admin', 'vecino')),
  -- Qué administrador contestó. `set null`: si el consorcio cambia de
  -- administración, el mensaje viejo sigue existiendo.
  admin_id       uuid references administradores(id) on delete set null,

  cuerpo         text not null default '',

  -- Igual que en `mensajes` y `reclamos`: base64 en la fila, validado por
  -- `validar_adjunto` en app.py (5 MB, PDF o imagen).
  adjunto_base64 text,
  adjunto_nombre text,
  adjunto_mime   text,

  -- Cuándo lo leyó el otro lado. NULL = todavía no.
  leido_at       timestamptz,
  created_at     timestamptz not null default now()
);

create index if not exists idx_reclamo_mensajes_hilo
  on reclamo_mensajes(reclamo_id, created_at);

-- La respuesta que ya existía pasa a ser el primer mensaje del administrador,
-- ya leída: el vecino la vio en su momento y no tiene que volver a aparecerle
-- como novedad.
insert into reclamo_mensajes (reclamo_id, autor, cuerpo, created_at, leido_at)
select r.id, 'admin', r.respuesta_admin,
       coalesce(r.updated_at, r.created_at), coalesce(r.updated_at, r.created_at)
  from reclamos r
 where coalesce(trim(r.respuesta_admin), '') <> ''
   and not exists (select 1 from reclamo_mensajes m where m.reclamo_id = r.id);


create table if not exists secciones_vistas (
  usuario_tipo text not null check (usuario_tipo in ('admin', 'vecino')),
  usuario_id   uuid not null,
  seccion      text not null,
  visto_at     timestamptz not null default now(),
  primary key (usuario_tipo, usuario_id, seccion)
);


-- ── RLS, igual que el resto (v13) ────────────────────────────
-- Sin políticas: anon y authenticated no ven nada; service_role (Flask) sí.
alter table reclamo_mensajes enable row level security;
alter table reclamo_mensajes force  row level security;
revoke all on table reclamo_mensajes from anon, authenticated;

alter table secciones_vistas enable row level security;
alter table secciones_vistas force  row level security;
revoke all on table secciones_vistas from anon, authenticated;

notify pgrst, 'reload schema';
