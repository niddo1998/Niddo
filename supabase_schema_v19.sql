-- ============================================================
--  Niddo — Supabase Schema v19 (Mensajes 1 a 1 con el vecino)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v18 antes
-- ============================================================
--
--  El panel del administrador tenía una sección "Mensajería" que decía
--  "estará disponible en la próxima versión". Esta es esa tabla.
--
--  Un hilo por vecino, no por tema: la conversación con la administración es
--  una sola, como en cualquier chat, y cualquiera de los dos lados puede
--  escribir primero. El hilo no es una fila: es (consorcio_id, vecino_id), y
--  los mensajes cuelgan de ahí. Sin tabla de hilos no hay estado que
--  sincronizar ni hilo vacío que limpiar.
--
--  El adjunto va en base64 en la fila, igual que en `reclamos` y `avisos_pago`:
--  el proyecto no usa Storage en ningún lado y meter un bucket sólo para esto
--  agregaría credenciales, políticas y un modo de fallar nuevos. El límite de
--  5 MB lo aplica `validar_adjunto` en app.py, que es el mismo de siempre.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================


create table if not exists mensajes (
  id             uuid primary key default gen_random_uuid(),

  -- El hilo. Los dos, y no sólo el vecino: el administrador lista por
  -- consorcio, y con el índice de abajo esa consulta no recorre la tabla.
  consorcio_id   uuid not null references consorcios(id) on delete cascade,
  vecino_id      uuid not null references vecinos(id)    on delete cascade,

  -- Quién escribió. 'admin' o 'vecino', y de ahí sale de qué lado del chat se
  -- pinta la burbuja y a quién le cuenta como no leído.
  autor          text not null check (autor in ('admin', 'vecino')),
  -- Qué administrador, cuando fue del lado admin. Un consorcio puede cambiar
  -- de administración y el mensaje viejo tiene que seguir diciendo quién lo
  -- mandó; por eso `set null` y no `cascade`.
  admin_id       uuid references administradores(id) on delete set null,

  cuerpo         text not null default '',

  adjunto_base64 text,
  adjunto_nombre text,
  adjunto_mime   text,

  -- Cuándo lo leyó el otro lado. NULL = todavía no. Es lo que cuenta el
  -- badge, así que va indexado junto con el autor.
  leido_at       timestamptz,

  created_at     timestamptz not null default now()
);


-- El hilo completo en orden: es la consulta que hace la pantalla al abrirlo.
create index if not exists idx_mensajes_hilo
  on mensajes(consorcio_id, vecino_id, created_at);

-- Los no leídos de cada lado, para los dos badges.
create index if not exists idx_mensajes_sin_leer
  on mensajes(vecino_id, autor, leido_at);


-- ── RLS, igual que el resto (v13) ────────────────────────────
-- Sin políticas a propósito: con RLS activada y ninguna política, anon y
-- authenticated no ven nada y service_role —que es con la que habla Flask—
-- sigue viendo todo. La autorización vive en app.py; esto es el piso.
alter table mensajes enable  row level security;
alter table mensajes force   row level security;
revoke all on table mensajes from anon, authenticated;
