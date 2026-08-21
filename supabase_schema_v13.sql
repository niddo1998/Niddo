-- ============================================================
--  Niddo — Supabase Schema v13 (Row Level Security en todo)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v12 antes
-- ============================================================
--
--  Hasta ahora la única tabla con RLS era `superadmin_auditoria` (v10). Todas
--  las demás quedaban abiertas, y eso importa aunque la app nunca use la anon
--  key: Supabase publica PostgREST en internet y la anon key es pública por
--  diseño. Sin RLS, cualquiera que la tenga lee la base entera —expensas,
--  emails, CBUs, adjuntos en base64— sin pasar jamás por Flask.
--
--  Activarla no cambia nada del comportamiento de Niddo: el backend habla con
--  la service_role key, que bypassea RLS por definición. Lo que cambia es lo
--  que pasa por afuera del backend, que hoy es todo.
--
--  A propósito NO se crean políticas. Una tabla con RLS activada y sin
--  políticas no devuelve nada a anon ni a authenticated, y sigue devolviendo
--  todo a service_role. Ese es exactamente el estado que queremos: la
--  autorización vive en app.py, y esto es el piso que la sostiene si ahí se
--  escapa algo.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================


-- ── 1. RLS en las 26 tablas ──────────────────────────────────
-- `superadmin_auditoria` ya la tenía desde v10; se la incluye igual porque
-- ENABLE sobre una tabla que ya lo tiene activado es un no-op.
DO $$
DECLARE
  t TEXT;
  tablas TEXT[] := ARRAY[
    'administradores', 'amenities', 'archivos_consorcio', 'avisos_pago',
    'cobros', 'comprobantes_gastos', 'comunicados', 'comunicados_leidos',
    'consorcios', 'envio_programado', 'gastos', 'liquidacion_items',
    'liquidacion_prorrateo', 'liquidacion_rubros', 'liquidaciones',
    'medios_pago', 'proveedores', 'reclamos', 'reservas_amenities',
    'resumen_envios', 'superadmin_auditoria', 'unidades_funcionales',
    'roadmap_estado', 'vecinos', 'vecinos_unidades', 'votaciones', 'votos'
  ];
BEGIN
  FOREACH t IN ARRAY tablas LOOP
    -- to_regclass devuelve NULL si la tabla no existe: así el script no se
    -- cae en un entorno donde falte alguna migración intermedia.
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
      -- FORCE hace que la política valga también para el dueño de la tabla.
      -- Sin esto, una conexión con el rol propietario seguiría viendo todo.
      EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t);
    END IF;
  END LOOP;
END $$;


-- ── 2. Quitar los privilegios directos de los roles públicos ─
-- RLS filtra filas, pero el GRANT es la puerta de entrada. Sacar los dos deja
-- a anon y authenticated sin nada que hacer contra estas tablas.
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

-- Y que las tablas que se creen de acá en adelante nazcan igual de cerradas,
-- para no depender de acordarse de correr esto de nuevo.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON TABLES    FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON FUNCTIONS FROM anon, authenticated;


-- ── 3. Verificación ──────────────────────────────────────────
-- Después de correr el script, esta query no debería devolver ninguna fila.
-- Si devuelve alguna, esa tabla quedó sin RLS:
--
--   SELECT tablename
--     FROM pg_tables
--    WHERE schemaname = 'public' AND rowsecurity = FALSE;
--
-- Y esta debería devolver cero para anon y authenticated:
--
--   SELECT grantee, COUNT(*)
--     FROM information_schema.role_table_grants
--    WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated')
--    GROUP BY grantee;
