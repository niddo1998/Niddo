-- ============================================================
--  Niddo — Schema v26 (Planes y cobro a administradores)
--  Ejecutar en: Neon → SQL Editor (proyecto Niddo-SP)
--  Requiere haber ejecutado v1 → v25 antes
--  Es idempotente y sólo agrega: se puede correr más de una vez.
-- ============================================================

-- ── Planes ──
-- Cada edificio paga según cuántas unidades tiene: le corresponde el plan
-- más chico cuyo tope alcance. No se guarda el plan en el consorcio: se
-- deduce de la cantidad de unidades, así nunca queda desactualizado y "pasar
-- de plan" es automático al cargar más unidades.
create table if not exists planes (
  id uuid primary key default gen_random_uuid(),
  nombre text not null,
  max_unidades integer,              -- null = sin tope (el último escalón)
  precio_mensual numeric(14,2) not null default 0 check (precio_mensual >= 0),
  descripcion text,
  orden integer not null default 0,
  created_at timestamp with time zone default now()
);

-- Los escalones de arranque, por edificio y por mes. Quedan por debajo de
-- CONSO (ARS 2.950 + IVA por unidad) desde las 16 unidades para arriba.
-- Se editan desde /superadmin → Comercial.
insert into planes (nombre, max_unidades, precio_mensual, orden)
select * from (values
  ('Hasta 10 unidades', 10, 20000, 1),
  ('Hasta 25 unidades', 25, 45000, 2),
  ('Hasta 60 unidades', 60, 90000, 3),
  ('Más de 60 unidades', null::integer, 150000, 4)
) as v(nombre, max_unidades, precio_mensual, orden)
where not exists (select 1 from planes);

-- ── Pase gratis por administrador ──
-- Hasta esa fecha no paga. Los que ya usaban Niddo son "fundadores" y
-- arrancan con seis meses; a los nuevos se les pone la prueba al aprobarlos.
alter table administradores add column if not exists gratis_hasta date;
alter table administradores add column if not exists es_fundador boolean default false;
-- Cuentas que nunca pagan (las del equipo). Se marcan a mano en la base.
alter table administradores add column if not exists siempre_gratis boolean default false;

update administradores
   set es_fundador = true,
       gratis_hasta = (current_date + interval '6 months')::date
 where estado = 'aprobado'
   and coalesce(es_superadmin, false) = false
   and gratis_hasta is null
   and created_at < '2026-11-13';

-- ── Lo que Niddo le cobra a cada administrador, por mes ──
-- Una fila por administrador y período. `detalle` guarda la foto de cada
-- edificio con su plan y precio al momento de armarla: si después cambian
-- los precios o las unidades, lo que se cobró no se reescribe.
create table if not exists cobros_niddo (
  id uuid primary key default gen_random_uuid(),
  admin_id uuid not null references administradores(id) on delete cascade,
  periodo text not null,                                   -- 'YYYY-MM'
  total numeric(14,2) not null default 0,
  estado text not null default 'pendiente'
    check (estado in ('pendiente', 'pagado', 'bonificado')),
  detalle jsonb not null default '[]'::jsonb,
  pagado_at timestamp with time zone,
  movimiento_id uuid references negocio_movimientos(id) on delete set null,
  created_at timestamp with time zone default now(),
  unique (admin_id, periodo)
);
