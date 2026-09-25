-- ============================================================
--  Niddo — Supabase Schema v22 (Notificaciones push)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v21 antes
-- ============================================================
--
--  Niddo no tiene app nativa: es una web que se agrega a la pantalla de
--  inicio. Las notificaciones al celular son Web Push: cuando alguien activa
--  las notificaciones, el navegador entrega una "suscripción" (una URL del
--  servicio de push de Google, Apple o Mozilla y dos claves) y se guarda acá.
--  Para avisarle algo, el servidor le manda el mensaje cifrado a esa URL.
--
--  Una persona puede tener varias: el celular, la compu del trabajo, la
--  tablet. El endpoint es único por dispositivo y navegador.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================

create table if not exists push_suscripciones (
  id            uuid primary key default gen_random_uuid(),
  usuario_tipo  text not null check (usuario_tipo in ('admin', 'vecino')),
  usuario_id    uuid not null,
  endpoint      text not null unique,
  p256dh        text not null,
  auth          text not null,
  -- Para mostrarle al usuario desde dónde está suscripto ("Chrome en Android").
  user_agent    text,
  created_at    timestamptz not null default now(),
  -- La última vez que un envío llegó bien. Una suscripción que el servicio de
  -- push rechaza (410/404) se borra en el momento, no se acumula.
  ultimo_ok_at  timestamptz
);

create index if not exists idx_push_suscripciones_usuario
  on push_suscripciones(usuario_tipo, usuario_id);

-- ── RLS, igual que el resto (v13) ────────────────────────────
alter table push_suscripciones enable row level security;
alter table push_suscripciones force  row level security;
revoke all on table push_suscripciones from anon, authenticated;

notify pgrst, 'reload schema';
