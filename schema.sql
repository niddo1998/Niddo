-- ══════════════════════════════════════════════════════════════════════════════
-- Niddo — esquema completo de la base (Postgres 17, Neon)
-- ══════════════════════════════════════════════════════════════════════════════
--
-- Es el estado que tenía producción en Supabase el 16/10/2026, después de
-- supabase_schema_v23.sql, sacado del catálogo y no de los archivos: lo que
-- manda es lo que estaba corriendo. Para levantar una base nueva alcanza con
-- correr este archivo; los supabase_schema_vN.sql quedan como historia.
--
-- Lo único que no se trajo son las políticas de RLS: las de Supabase leían el
-- JWT de PostgREST (request.jwt.claims), que en Neon no existe, y el backend se
-- conecta como dueño de la base, así que nunca pasaba por ellas.
--
-- Los cambios que vengan van en archivos nuevos (migraciones/NNN_nombre.sql).

-- db.py devuelve las fechas con zona tal como las formatea Postgres, y la app
-- espera "+00:00" como mandaba Supabase. Fijarlo en la base y no por consulta
-- le ahorra a cada una un viaje de ida y vuelta.
DO $$ BEGIN
  EXECUTE format('ALTER DATABASE %I SET timezone TO ''UTC''', current_database());
END $$;

CREATE TABLE public.administradores (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  auth0_id text NOT NULL,
  email text NOT NULL,
  nombre text,
  created_at timestamp with time zone DEFAULT now(),
  last_login timestamp with time zone,
  estado text DEFAULT 'pendiente'::text NOT NULL,
  telefono text,
  nombre_contacto text,
  email_contacto text,
  solicitud_completada_at timestamp with time zone,
  aprobado_por uuid,
  resuelto_at timestamp with time zone,
  motivo_rechazo text,
  es_superadmin boolean DEFAULT false NOT NULL,
  ultima_actividad timestamp with time zone,
  cuit text,
  matricula text,
  direccion text
);
CREATE TABLE public.amenities (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  nombre text NOT NULL,
  descripcion text,
  condiciones_uso text,
  capacidad_maxima integer,
  created_at timestamp with time zone DEFAULT now(),
  max_reservas_mes integer,
  precio_uso numeric(12,2)
);
CREATE TABLE public.archivos_consorcio (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  admin_id uuid,
  categoria text NOT NULL,
  nombre text NOT NULL,
  archivo_base64 text NOT NULL,
  mime_type text DEFAULT 'application/pdf'::text,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.avisos_pago (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  vecino_id uuid NOT NULL,
  unidad_id uuid,
  cobro_id uuid,
  monto numeric(12,2),
  fecha_pago date,
  medio_pago text,
  observaciones text,
  adjunto_nombre text,
  adjunto_base64 text,
  adjunto_mime text,
  estado text DEFAULT 'pendiente'::text,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.cobros (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  unidad_id uuid NOT NULL,
  consorcio_id uuid NOT NULL,
  periodo text NOT NULL,
  monto_base numeric(12,2) NOT NULL,
  interes_mora numeric(12,2) DEFAULT 0,
  total numeric(12,2) NOT NULL,
  estado text DEFAULT 'pendiente'::text,
  fecha_vencimiento date,
  fecha_pago date,
  comprobante_nombre text,
  notas text,
  created_at timestamp with time zone DEFAULT now(),
  liquidacion_id uuid
);
CREATE TABLE public.comprobantes_gastos (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  gasto_id uuid NOT NULL,
  archivo_nombre text NOT NULL,
  archivo_base64 text NOT NULL,
  mime_type text DEFAULT 'application/pdf'::text,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.comunicados (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  admin_id uuid NOT NULL,
  consorcio_id uuid,
  unidad_id uuid,
  asunto text NOT NULL,
  cuerpo text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  titulo text,
  importante boolean DEFAULT false,
  autor_vecino_id uuid,
  reserva_id uuid
);
CREATE TABLE public.comunicados_leidos (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  comunicado_id uuid NOT NULL,
  vecino_id uuid NOT NULL,
  leido_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.consorcios (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  nombre text NOT NULL,
  direccion text,
  cuit text,
  pisos integer,
  unidades_totales integer,
  encargado_nombre text,
  encargado_tel text,
  admin_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  banco_nombre text,
  banco_sucursal text,
  banco_cuenta text,
  banco_cbu text,
  banco_cuit_pago text,
  tasa_interes_mora numeric(6,3) DEFAULT 0,
  dias_gracia_mora smallint DEFAULT 0,
  recargo_segundo_vto numeric(5,2) DEFAULT 0,
  clave_suterh text,
  banco_titular text,
  banco_alias text,
  metodo_prorrateo text DEFAULT 'm2'::text NOT NULL
);
CREATE TABLE public.envio_programado (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  admin_id uuid NOT NULL,
  dia_mes integer DEFAULT 1 NOT NULL,
  hora_envio time without time zone DEFAULT '09:00:00'::time without time zone,
  canal text DEFAULT 'email'::text,
  activo boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.gastos (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  proveedor_id uuid,
  descripcion text NOT NULL,
  categoria text,
  monto numeric(12,2) NOT NULL,
  fecha_gasto date DEFAULT CURRENT_DATE NOT NULL,
  fecha_vencimiento date,
  pagado boolean DEFAULT false,
  fecha_pago date,
  metodo_pago text,
  recurrente boolean DEFAULT false,
  frecuencia text,
  archivo_nombre text,
  notas text,
  admin_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  unidad_id uuid,
  dia_carga smallint,
  gasto_origen_id uuid,
  periodo_generado text,
  tarifa_confirmada boolean DEFAULT true NOT NULL,
  coeficiente text DEFAULT 'A'::text NOT NULL,
  comprobante_tipo text,
  comprobante_numero text
);
CREATE TABLE public.liquidacion_items (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  rubro_id uuid NOT NULL,
  descripcion text NOT NULL,
  monto numeric(14,2) DEFAULT 0,
  gasto_id uuid,
  es_cuota boolean DEFAULT false,
  cuota_actual integer,
  cuota_total integer,
  unidad_id uuid,
  proveedor_nombre text,
  proveedor_cuit text,
  comprobante_tipo text,
  comprobante_numero text,
  fecha_pago date,
  coeficiente text DEFAULT 'A'::text
);
CREATE TABLE public.liquidacion_prorrateo (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  liquidacion_id uuid NOT NULL,
  unidad_id uuid NOT NULL,
  saldo_anterior numeric(14,2) DEFAULT 0,
  pago_realizado numeric(14,2) DEFAULT 0,
  saldo_pendiente numeric(14,2) DEFAULT 0,
  interes_mora numeric(14,2) DEFAULT 0,
  porcentaje_a numeric(6,3) DEFAULT 0,
  expensa_a numeric(14,2) DEFAULT 0,
  porcentaje_c numeric(6,3) DEFAULT 0,
  adicional_ordinaria numeric(14,2) DEFAULT 0,
  extraordinaria numeric(14,2) DEFAULT 0,
  redondeo numeric(14,2) DEFAULT 0,
  total_unidad numeric(14,2) DEFAULT 0,
  gastos_particulares numeric(14,2) DEFAULT 0,
  porcentaje_b numeric(6,3) DEFAULT 0,
  expensa_b numeric(12,2) DEFAULT 0,
  porcentaje_e numeric(6,3) DEFAULT 0,
  expensa_e numeric(12,2) DEFAULT 0,
  uso_amenities numeric(12,2) DEFAULT 0,
  descuentos numeric(12,2) DEFAULT 0,
  total_segundo_vto numeric(12,2) DEFAULT 0
);
CREATE TABLE public.liquidacion_rubros (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  liquidacion_id uuid NOT NULL,
  numero_rubro integer NOT NULL,
  nombre text NOT NULL,
  subtotal numeric(14,2) DEFAULT 0,
  porcentaje_sobre_total numeric(5,2) DEFAULT 0
);
CREATE TABLE public.liquidaciones (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  admin_id uuid NOT NULL,
  periodo text NOT NULL,
  fecha_vencimiento_1 date,
  fecha_vencimiento_2 date,
  interes_2_vto numeric(5,2) DEFAULT 0,
  saldo_inicial numeric(14,2) DEFAULT 0,
  total_ingresos numeric(14,2) DEFAULT 0,
  total_egresos numeric(14,2) DEFAULT 0,
  saldo_final numeric(14,2) DEFAULT 0,
  saldo_bancario numeric(14,2) DEFAULT 0,
  saldo_superfondo numeric(14,2) DEFAULT 0,
  saldo_administrador numeric(14,2) DEFAULT 0,
  notas text,
  estado text DEFAULT 'borrador'::text,
  created_at timestamp with time zone DEFAULT now(),
  numero_revision integer DEFAULT 1 NOT NULL
);
CREATE TABLE public.medios_pago (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  admin_id uuid,
  nombre text NOT NULL,
  descripcion text,
  activo boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.mensajes (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  vecino_id uuid NOT NULL,
  autor text NOT NULL,
  admin_id uuid,
  cuerpo text DEFAULT ''::text NOT NULL,
  adjunto_base64 text,
  adjunto_nombre text,
  adjunto_mime text,
  leido_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.proveedores (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  nombre text NOT NULL,
  cuit text,
  rubro text,
  email text,
  telefono text,
  admin_id uuid,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.push_suscripciones (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  usuario_tipo text NOT NULL,
  usuario_id uuid NOT NULL,
  endpoint text NOT NULL,
  p256dh text NOT NULL,
  auth text NOT NULL,
  user_agent text,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  ultimo_ok_at timestamp with time zone
);
CREATE TABLE public.reclamo_mensajes (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  reclamo_id uuid NOT NULL,
  autor text NOT NULL,
  admin_id uuid,
  cuerpo text DEFAULT ''::text NOT NULL,
  adjunto_base64 text,
  adjunto_nombre text,
  adjunto_mime text,
  leido_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.reclamos (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  vecino_id uuid NOT NULL,
  unidad_id uuid,
  titulo text NOT NULL,
  descripcion text NOT NULL,
  categoria text DEFAULT 'otro'::text,
  estado text DEFAULT 'activo'::text,
  respuesta_admin text,
  adjunto_nombre text,
  adjunto_base64 text,
  adjunto_mime text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.reservas_amenities (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  amenity_id uuid NOT NULL,
  vecino_id uuid,
  fecha date NOT NULL,
  hora_inicio time without time zone NOT NULL,
  hora_fin time without time zone NOT NULL,
  estado text DEFAULT 'confirmada'::text,
  created_at timestamp with time zone DEFAULT now(),
  cantidad_personas integer
);
CREATE TABLE public.resumen_envios (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  liquidacion_id uuid NOT NULL,
  unidad_id uuid NOT NULL,
  canal text DEFAULT 'email'::text,
  estado text DEFAULT 'pendiente'::text,
  email_destino text,
  fecha_envio timestamp with time zone,
  fecha_lectura timestamp with time zone,
  error_detalle text,
  resumen_html text,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.roadmap_estado (
  id text NOT NULL,
  estado text NOT NULL,
  actualizado_por uuid,
  actualizado_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.secciones_vistas (
  usuario_tipo text NOT NULL,
  usuario_id uuid NOT NULL,
  seccion text NOT NULL,
  visto_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.solicitudes_vinculacion (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  vecino_id uuid NOT NULL,
  consorcio_id uuid NOT NULL,
  unidad_id uuid NOT NULL,
  estado text DEFAULT 'pendiente'::text NOT NULL,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.superadmin_auditoria (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  actor_id uuid NOT NULL,
  target_id uuid NOT NULL,
  accion text NOT NULL,
  motivo text,
  ip text,
  user_agent text,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.unidades_funcionales (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  numero text NOT NULL,
  piso text,
  tipo text DEFAULT 'departamento'::text,
  superficie_m2 numeric(8,2),
  vecino_nombre text,
  vecino_email text,
  vecino_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  porcentaje_a numeric(6,3) DEFAULT 0,
  porcentaje_c numeric(6,3) DEFAULT 0,
  porcentaje_b numeric(6,3) DEFAULT 0,
  porcentaje_e numeric(6,3) DEFAULT 0,
  ambientes smallint
);
CREATE TABLE public.vecinos (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  auth0_id text NOT NULL,
  email text NOT NULL,
  nombre text,
  unidad text,
  consorcio_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  last_login timestamp with time zone,
  rol text DEFAULT 'propietario'::text,
  unidad_id uuid,
  telefono text,
  estado_asociacion text,
  consorcio_solicitado_id uuid,
  unidad_solicitada_id uuid,
  solicitud_at timestamp with time zone,
  motivo_rechazo text
);
CREATE TABLE public.vecinos_unidades (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  vecino_id uuid NOT NULL,
  unidad_id uuid NOT NULL,
  consorcio_id uuid NOT NULL,
  rol text DEFAULT 'propietario'::text,
  activo boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.votaciones (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  consorcio_id uuid NOT NULL,
  admin_id uuid,
  titulo text NOT NULL,
  descripcion text,
  opciones jsonb DEFAULT '["Si", "No", "Abstención"]'::jsonb,
  fecha_limite date,
  estado text DEFAULT 'activa'::text,
  votos_necesarios integer,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.votos (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  votacion_id uuid NOT NULL,
  vecino_id uuid NOT NULL,
  unidad_id uuid,
  opcion text NOT NULL,
  created_at timestamp with time zone DEFAULT now()
);

-- ── Claves primarias ─────────────────────────────────────────────────────────
ALTER TABLE public.administradores ADD CONSTRAINT administradores_pkey PRIMARY KEY (id);
ALTER TABLE public.amenities ADD CONSTRAINT amenities_pkey PRIMARY KEY (id);
ALTER TABLE public.archivos_consorcio ADD CONSTRAINT archivos_consorcio_pkey PRIMARY KEY (id);
ALTER TABLE public.avisos_pago ADD CONSTRAINT avisos_pago_pkey PRIMARY KEY (id);
ALTER TABLE public.cobros ADD CONSTRAINT cobros_pkey PRIMARY KEY (id);
ALTER TABLE public.comprobantes_gastos ADD CONSTRAINT comprobantes_gastos_pkey PRIMARY KEY (id);
ALTER TABLE public.comunicados ADD CONSTRAINT comunicados_pkey PRIMARY KEY (id);
ALTER TABLE public.comunicados_leidos ADD CONSTRAINT comunicados_leidos_pkey PRIMARY KEY (id);
ALTER TABLE public.consorcios ADD CONSTRAINT consorcios_pkey PRIMARY KEY (id);
ALTER TABLE public.envio_programado ADD CONSTRAINT envio_programado_pkey PRIMARY KEY (id);
ALTER TABLE public.gastos ADD CONSTRAINT gastos_pkey PRIMARY KEY (id);
ALTER TABLE public.liquidacion_items ADD CONSTRAINT liquidacion_items_pkey PRIMARY KEY (id);
ALTER TABLE public.liquidacion_prorrateo ADD CONSTRAINT liquidacion_prorrateo_pkey PRIMARY KEY (id);
ALTER TABLE public.liquidacion_rubros ADD CONSTRAINT liquidacion_rubros_pkey PRIMARY KEY (id);
ALTER TABLE public.liquidaciones ADD CONSTRAINT liquidaciones_pkey PRIMARY KEY (id);
ALTER TABLE public.medios_pago ADD CONSTRAINT medios_pago_pkey PRIMARY KEY (id);
ALTER TABLE public.mensajes ADD CONSTRAINT mensajes_pkey PRIMARY KEY (id);
ALTER TABLE public.proveedores ADD CONSTRAINT proveedores_pkey PRIMARY KEY (id);
ALTER TABLE public.push_suscripciones ADD CONSTRAINT push_suscripciones_pkey PRIMARY KEY (id);
ALTER TABLE public.reclamo_mensajes ADD CONSTRAINT reclamo_mensajes_pkey PRIMARY KEY (id);
ALTER TABLE public.reclamos ADD CONSTRAINT reclamos_pkey PRIMARY KEY (id);
ALTER TABLE public.reservas_amenities ADD CONSTRAINT reservas_amenities_pkey PRIMARY KEY (id);
ALTER TABLE public.resumen_envios ADD CONSTRAINT resumen_envios_pkey PRIMARY KEY (id);
ALTER TABLE public.roadmap_estado ADD CONSTRAINT roadmap_estado_pkey PRIMARY KEY (id);
ALTER TABLE public.secciones_vistas ADD CONSTRAINT secciones_vistas_pkey PRIMARY KEY (usuario_tipo, usuario_id, seccion);
ALTER TABLE public.solicitudes_vinculacion ADD CONSTRAINT solicitudes_vinculacion_pkey PRIMARY KEY (id);
ALTER TABLE public.superadmin_auditoria ADD CONSTRAINT superadmin_auditoria_pkey PRIMARY KEY (id);
ALTER TABLE public.unidades_funcionales ADD CONSTRAINT unidades_funcionales_pkey PRIMARY KEY (id);
ALTER TABLE public.vecinos ADD CONSTRAINT vecinos_pkey PRIMARY KEY (id);
ALTER TABLE public.vecinos_unidades ADD CONSTRAINT vecinos_unidades_pkey PRIMARY KEY (id);
ALTER TABLE public.votaciones ADD CONSTRAINT votaciones_pkey PRIMARY KEY (id);
ALTER TABLE public.votos ADD CONSTRAINT votos_pkey PRIMARY KEY (id);

-- ── Únicos ───────────────────────────────────────────────────────────────────
ALTER TABLE public.administradores ADD CONSTRAINT administradores_auth0_id_key UNIQUE (auth0_id);
ALTER TABLE public.administradores ADD CONSTRAINT administradores_email_key UNIQUE (email);
ALTER TABLE public.comprobantes_gastos ADD CONSTRAINT comprobantes_gastos_gasto_id_key UNIQUE (gasto_id);
ALTER TABLE public.comunicados_leidos ADD CONSTRAINT comunicados_leidos_comunicado_id_vecino_id_key UNIQUE (comunicado_id, vecino_id);
ALTER TABLE public.envio_programado ADD CONSTRAINT envio_programado_consorcio_id_key UNIQUE (consorcio_id);
ALTER TABLE public.liquidacion_prorrateo ADD CONSTRAINT liquidacion_prorrateo_liquidacion_id_unidad_id_key UNIQUE (liquidacion_id, unidad_id);
ALTER TABLE public.push_suscripciones ADD CONSTRAINT push_suscripciones_endpoint_key UNIQUE (endpoint);
ALTER TABLE public.vecinos ADD CONSTRAINT vecinos_auth0_id_key UNIQUE (auth0_id);
ALTER TABLE public.vecinos ADD CONSTRAINT vecinos_email_key UNIQUE (email);
ALTER TABLE public.vecinos_unidades ADD CONSTRAINT vecinos_unidades_vecino_id_unidad_id_key UNIQUE (vecino_id, unidad_id);
ALTER TABLE public.votos ADD CONSTRAINT votos_votacion_id_unidad_id_key UNIQUE (votacion_id, unidad_id);

-- ── Checks ───────────────────────────────────────────────────────────────────
ALTER TABLE public.administradores ADD CONSTRAINT administradores_estado_check CHECK ((estado = ANY (ARRAY['pendiente'::text, 'aprobado'::text, 'rechazado'::text])));
ALTER TABLE public.consorcios ADD CONSTRAINT consorcios_metodo_prorrateo_check CHECK ((metodo_prorrateo = ANY (ARRAY['m2'::text, 'ambientes'::text, 'partes_iguales'::text, 'porcentaje'::text])));
ALTER TABLE public.gastos ADD CONSTRAINT gastos_coeficiente_valido CHECK ((coeficiente = ANY (ARRAY['A'::text, 'B'::text, 'C'::text, 'E'::text])));
ALTER TABLE public.gastos ADD CONSTRAINT gastos_dia_carga_valido CHECK (((dia_carga IS NULL) OR ((dia_carga >= 1) AND (dia_carga <= 31))));
ALTER TABLE public.mensajes ADD CONSTRAINT mensajes_autor_check CHECK ((autor = ANY (ARRAY['admin'::text, 'vecino'::text])));
ALTER TABLE public.push_suscripciones ADD CONSTRAINT push_suscripciones_usuario_tipo_check CHECK ((usuario_tipo = ANY (ARRAY['admin'::text, 'vecino'::text])));
ALTER TABLE public.reclamo_mensajes ADD CONSTRAINT reclamo_mensajes_autor_check CHECK ((autor = ANY (ARRAY['admin'::text, 'vecino'::text])));
ALTER TABLE public.roadmap_estado ADD CONSTRAINT roadmap_estado_estado_check CHECK ((estado = ANY (ARRAY['planeada'::text, 'construida'::text])));
ALTER TABLE public.secciones_vistas ADD CONSTRAINT secciones_vistas_usuario_tipo_check CHECK ((usuario_tipo = ANY (ARRAY['admin'::text, 'vecino'::text])));
ALTER TABLE public.superadmin_auditoria ADD CONSTRAINT superadmin_auditoria_accion_check CHECK ((accion = ANY (ARRAY['aprobar'::text, 'rechazar'::text, 'impersonar_inicio'::text, 'impersonar_fin'::text])));
ALTER TABLE public.vecinos ADD CONSTRAINT vecinos_estado_asociacion_valido CHECK (((estado_asociacion IS NULL) OR (estado_asociacion = ANY (ARRAY['pendiente'::text, 'aprobado'::text, 'rechazado'::text]))));

-- ── Claves foráneas ──────────────────────────────────────────────────────────
-- Los nombres importan: db.py los usa para resolver los joins embebidos del
-- estilo select('*, consorcios(nombre)').
ALTER TABLE public.administradores ADD CONSTRAINT administradores_aprobado_por_fkey FOREIGN KEY (aprobado_por) REFERENCES public.administradores(id);
ALTER TABLE public.amenities ADD CONSTRAINT amenities_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.archivos_consorcio ADD CONSTRAINT archivos_consorcio_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE SET NULL;
ALTER TABLE public.archivos_consorcio ADD CONSTRAINT archivos_consorcio_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.avisos_pago ADD CONSTRAINT avisos_pago_cobro_id_fkey FOREIGN KEY (cobro_id) REFERENCES public.cobros(id) ON DELETE SET NULL;
ALTER TABLE public.avisos_pago ADD CONSTRAINT avisos_pago_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.avisos_pago ADD CONSTRAINT avisos_pago_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE SET NULL;
ALTER TABLE public.avisos_pago ADD CONSTRAINT avisos_pago_vecino_id_fkey FOREIGN KEY (vecino_id) REFERENCES public.vecinos(id) ON DELETE CASCADE;
ALTER TABLE public.cobros ADD CONSTRAINT cobros_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.cobros ADD CONSTRAINT cobros_liquidacion_id_fkey FOREIGN KEY (liquidacion_id) REFERENCES public.liquidaciones(id) ON DELETE SET NULL;
ALTER TABLE public.cobros ADD CONSTRAINT cobros_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE CASCADE;
ALTER TABLE public.comprobantes_gastos ADD CONSTRAINT comprobantes_gastos_gasto_id_fkey FOREIGN KEY (gasto_id) REFERENCES public.gastos(id) ON DELETE CASCADE;
ALTER TABLE public.comunicados ADD CONSTRAINT comunicados_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE CASCADE;
ALTER TABLE public.comunicados ADD CONSTRAINT comunicados_autor_vecino_id_fkey FOREIGN KEY (autor_vecino_id) REFERENCES public.vecinos(id) ON DELETE SET NULL;
ALTER TABLE public.comunicados ADD CONSTRAINT comunicados_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.comunicados ADD CONSTRAINT comunicados_reserva_id_fkey FOREIGN KEY (reserva_id) REFERENCES public.reservas_amenities(id) ON DELETE SET NULL;
ALTER TABLE public.comunicados ADD CONSTRAINT comunicados_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE CASCADE;
ALTER TABLE public.comunicados_leidos ADD CONSTRAINT comunicados_leidos_comunicado_id_fkey FOREIGN KEY (comunicado_id) REFERENCES public.comunicados(id) ON DELETE CASCADE;
ALTER TABLE public.comunicados_leidos ADD CONSTRAINT comunicados_leidos_vecino_id_fkey FOREIGN KEY (vecino_id) REFERENCES public.vecinos(id) ON DELETE CASCADE;
ALTER TABLE public.consorcios ADD CONSTRAINT consorcios_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE SET NULL;
ALTER TABLE public.envio_programado ADD CONSTRAINT envio_programado_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE CASCADE;
ALTER TABLE public.envio_programado ADD CONSTRAINT envio_programado_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.gastos ADD CONSTRAINT gastos_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE SET NULL;
ALTER TABLE public.gastos ADD CONSTRAINT gastos_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.gastos ADD CONSTRAINT gastos_gasto_origen_id_fkey FOREIGN KEY (gasto_origen_id) REFERENCES public.gastos(id) ON DELETE CASCADE;
ALTER TABLE public.gastos ADD CONSTRAINT gastos_proveedor_id_fkey FOREIGN KEY (proveedor_id) REFERENCES public.proveedores(id) ON DELETE SET NULL;
ALTER TABLE public.gastos ADD CONSTRAINT gastos_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE SET NULL;
ALTER TABLE public.liquidacion_items ADD CONSTRAINT liquidacion_items_gasto_id_fkey FOREIGN KEY (gasto_id) REFERENCES public.gastos(id) ON DELETE SET NULL;
ALTER TABLE public.liquidacion_items ADD CONSTRAINT liquidacion_items_rubro_id_fkey FOREIGN KEY (rubro_id) REFERENCES public.liquidacion_rubros(id) ON DELETE CASCADE;
ALTER TABLE public.liquidacion_items ADD CONSTRAINT liquidacion_items_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE SET NULL;
ALTER TABLE public.liquidacion_prorrateo ADD CONSTRAINT liquidacion_prorrateo_liquidacion_id_fkey FOREIGN KEY (liquidacion_id) REFERENCES public.liquidaciones(id) ON DELETE CASCADE;
ALTER TABLE public.liquidacion_prorrateo ADD CONSTRAINT liquidacion_prorrateo_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE CASCADE;
ALTER TABLE public.liquidacion_rubros ADD CONSTRAINT liquidacion_rubros_liquidacion_id_fkey FOREIGN KEY (liquidacion_id) REFERENCES public.liquidaciones(id) ON DELETE CASCADE;
ALTER TABLE public.liquidaciones ADD CONSTRAINT liquidaciones_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE CASCADE;
ALTER TABLE public.liquidaciones ADD CONSTRAINT liquidaciones_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.medios_pago ADD CONSTRAINT medios_pago_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE SET NULL;
ALTER TABLE public.medios_pago ADD CONSTRAINT medios_pago_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.mensajes ADD CONSTRAINT mensajes_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE SET NULL;
ALTER TABLE public.mensajes ADD CONSTRAINT mensajes_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.mensajes ADD CONSTRAINT mensajes_vecino_id_fkey FOREIGN KEY (vecino_id) REFERENCES public.vecinos(id) ON DELETE CASCADE;
ALTER TABLE public.proveedores ADD CONSTRAINT proveedores_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE SET NULL;
ALTER TABLE public.reclamo_mensajes ADD CONSTRAINT reclamo_mensajes_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE SET NULL;
ALTER TABLE public.reclamo_mensajes ADD CONSTRAINT reclamo_mensajes_reclamo_id_fkey FOREIGN KEY (reclamo_id) REFERENCES public.reclamos(id) ON DELETE CASCADE;
ALTER TABLE public.reclamos ADD CONSTRAINT reclamos_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.reclamos ADD CONSTRAINT reclamos_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE SET NULL;
ALTER TABLE public.reclamos ADD CONSTRAINT reclamos_vecino_id_fkey FOREIGN KEY (vecino_id) REFERENCES public.vecinos(id) ON DELETE CASCADE;
ALTER TABLE public.reservas_amenities ADD CONSTRAINT reservas_amenities_amenity_id_fkey FOREIGN KEY (amenity_id) REFERENCES public.amenities(id) ON DELETE CASCADE;
ALTER TABLE public.reservas_amenities ADD CONSTRAINT reservas_amenities_vecino_id_fkey FOREIGN KEY (vecino_id) REFERENCES public.vecinos(id) ON DELETE SET NULL;
ALTER TABLE public.resumen_envios ADD CONSTRAINT resumen_envios_liquidacion_id_fkey FOREIGN KEY (liquidacion_id) REFERENCES public.liquidaciones(id) ON DELETE CASCADE;
ALTER TABLE public.resumen_envios ADD CONSTRAINT resumen_envios_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE CASCADE;
ALTER TABLE public.roadmap_estado ADD CONSTRAINT roadmap_estado_actualizado_por_fkey FOREIGN KEY (actualizado_por) REFERENCES public.administradores(id) ON DELETE SET NULL;
ALTER TABLE public.solicitudes_vinculacion ADD CONSTRAINT solicitudes_vinculacion_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.solicitudes_vinculacion ADD CONSTRAINT solicitudes_vinculacion_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE CASCADE;
ALTER TABLE public.solicitudes_vinculacion ADD CONSTRAINT solicitudes_vinculacion_vecino_id_fkey FOREIGN KEY (vecino_id) REFERENCES public.vecinos(id) ON DELETE CASCADE;
ALTER TABLE public.superadmin_auditoria ADD CONSTRAINT superadmin_auditoria_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.administradores(id) ON DELETE RESTRICT;
ALTER TABLE public.superadmin_auditoria ADD CONSTRAINT superadmin_auditoria_target_id_fkey FOREIGN KEY (target_id) REFERENCES public.administradores(id) ON DELETE RESTRICT;
ALTER TABLE public.unidades_funcionales ADD CONSTRAINT unidades_funcionales_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.unidades_funcionales ADD CONSTRAINT unidades_funcionales_vecino_id_fkey FOREIGN KEY (vecino_id) REFERENCES public.vecinos(id) ON DELETE SET NULL;
ALTER TABLE public.vecinos ADD CONSTRAINT vecinos_consorcio_solicitado_id_fkey FOREIGN KEY (consorcio_solicitado_id) REFERENCES public.consorcios(id) ON DELETE SET NULL;
ALTER TABLE public.vecinos ADD CONSTRAINT vecinos_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE SET NULL;
ALTER TABLE public.vecinos ADD CONSTRAINT vecinos_unidad_solicitada_id_fkey FOREIGN KEY (unidad_solicitada_id) REFERENCES public.unidades_funcionales(id) ON DELETE SET NULL;
ALTER TABLE public.vecinos_unidades ADD CONSTRAINT vecinos_unidades_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.vecinos_unidades ADD CONSTRAINT vecinos_unidades_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE CASCADE;
ALTER TABLE public.vecinos_unidades ADD CONSTRAINT vecinos_unidades_vecino_id_fkey FOREIGN KEY (vecino_id) REFERENCES public.vecinos(id) ON DELETE CASCADE;
ALTER TABLE public.votaciones ADD CONSTRAINT votaciones_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.administradores(id) ON DELETE SET NULL;
ALTER TABLE public.votaciones ADD CONSTRAINT votaciones_consorcio_id_fkey FOREIGN KEY (consorcio_id) REFERENCES public.consorcios(id) ON DELETE CASCADE;
ALTER TABLE public.votos ADD CONSTRAINT votos_unidad_id_fkey FOREIGN KEY (unidad_id) REFERENCES public.unidades_funcionales(id) ON DELETE SET NULL;
ALTER TABLE public.votos ADD CONSTRAINT votos_vecino_id_fkey FOREIGN KEY (vecino_id) REFERENCES public.vecinos(id) ON DELETE CASCADE;
ALTER TABLE public.votos ADD CONSTRAINT votos_votacion_id_fkey FOREIGN KEY (votacion_id) REFERENCES public.votaciones(id) ON DELETE CASCADE;

-- ── Índices ──────────────────────────────────────────────────────────────────
CREATE INDEX idx_admin_estado ON public.administradores USING btree (estado);
CREATE INDEX idx_admin_ultima_actividad ON public.administradores USING btree (ultima_actividad DESC);
CREATE INDEX idx_admin_auth0_id ON public.administradores USING btree (auth0_id);
CREATE INDEX idx_amenities_consorcio ON public.amenities USING btree (consorcio_id);
CREATE INDEX idx_archivos_consorcio ON public.archivos_consorcio USING btree (consorcio_id);
CREATE INDEX idx_archivos_categoria ON public.archivos_consorcio USING btree (categoria);
CREATE INDEX idx_avisos_pago_vecino ON public.avisos_pago USING btree (vecino_id);
CREATE INDEX idx_avisos_pago_consorcio ON public.avisos_pago USING btree (consorcio_id);
CREATE INDEX idx_cobros_estado ON public.cobros USING btree (estado);
CREATE UNIQUE INDEX idx_cobros_liquidacion_unidad ON public.cobros USING btree (liquidacion_id, unidad_id) WHERE (liquidacion_id IS NOT NULL);
CREATE INDEX idx_cobros_consorcio ON public.cobros USING btree (consorcio_id);
CREATE INDEX idx_cobros_periodo ON public.cobros USING btree (periodo);
CREATE INDEX idx_cobros_unidad ON public.cobros USING btree (unidad_id);
CREATE INDEX idx_comprobantes_gasto ON public.comprobantes_gastos USING btree (gasto_id);
CREATE INDEX idx_comunicados_unidad ON public.comunicados USING btree (unidad_id);
CREATE INDEX idx_comunicados_consorcio ON public.comunicados USING btree (consorcio_id);
CREATE INDEX idx_comunicados_fecha ON public.comunicados USING btree (created_at DESC);
CREATE INDEX idx_comunicados_admin ON public.comunicados USING btree (admin_id);
CREATE INDEX idx_com_leidos_vecino ON public.comunicados_leidos USING btree (vecino_id);
CREATE INDEX idx_consorcios_admin ON public.consorcios USING btree (admin_id);
CREATE INDEX idx_consorcios_created ON public.consorcios USING btree (created_at);
CREATE INDEX idx_envio_programado_consorcio ON public.envio_programado USING btree (consorcio_id);
CREATE INDEX idx_gastos_plantillas ON public.gastos USING btree (admin_id) WHERE (recurrente = true);
CREATE INDEX idx_gastos_fecha ON public.gastos USING btree (fecha_gasto);
CREATE INDEX idx_gastos_unidad ON public.gastos USING btree (unidad_id);
CREATE INDEX idx_gastos_tarifa_pendiente ON public.gastos USING btree (admin_id) WHERE (tarifa_confirmada = false);
CREATE INDEX idx_gastos_pagado ON public.gastos USING btree (pagado);
CREATE UNIQUE INDEX idx_gastos_origen_periodo ON public.gastos USING btree (gasto_origen_id, periodo_generado) WHERE (gasto_origen_id IS NOT NULL);
CREATE INDEX idx_gastos_consorcio ON public.gastos USING btree (consorcio_id);
CREATE INDEX idx_liq_items_unidad ON public.liquidacion_items USING btree (unidad_id);
CREATE INDEX idx_liq_items_gasto ON public.liquidacion_items USING btree (gasto_id);
CREATE INDEX idx_liq_items_rubro ON public.liquidacion_items USING btree (rubro_id);
CREATE INDEX idx_liq_prorrateo_unidad ON public.liquidacion_prorrateo USING btree (unidad_id);
CREATE INDEX idx_liq_prorrateo_liquidacion ON public.liquidacion_prorrateo USING btree (liquidacion_id);
CREATE INDEX idx_liq_rubros_liquidacion ON public.liquidacion_rubros USING btree (liquidacion_id);
CREATE UNIQUE INDEX uq_liquidaciones_consorcio_periodo_rev ON public.liquidaciones USING btree (consorcio_id, periodo, numero_revision);
CREATE INDEX idx_liquidaciones_estado ON public.liquidaciones USING btree (estado);
CREATE INDEX idx_liquidaciones_consorcio ON public.liquidaciones USING btree (consorcio_id);
CREATE INDEX idx_liquidaciones_periodo ON public.liquidaciones USING btree (periodo);
CREATE INDEX idx_liquidaciones_admin ON public.liquidaciones USING btree (admin_id);
CREATE INDEX idx_medios_pago_consorcio ON public.medios_pago USING btree (consorcio_id);
CREATE INDEX idx_mensajes_hilo ON public.mensajes USING btree (consorcio_id, vecino_id, created_at);
CREATE INDEX idx_mensajes_sin_leer ON public.mensajes USING btree (vecino_id, autor, leido_at);
CREATE INDEX idx_proveedores_admin ON public.proveedores USING btree (admin_id);
CREATE INDEX idx_push_suscripciones_usuario ON public.push_suscripciones USING btree (usuario_tipo, usuario_id);
CREATE INDEX idx_reclamo_mensajes_hilo ON public.reclamo_mensajes USING btree (reclamo_id, created_at);
CREATE INDEX idx_reclamos_vecino ON public.reclamos USING btree (vecino_id);
CREATE INDEX idx_reclamos_consorcio ON public.reclamos USING btree (consorcio_id);
CREATE INDEX idx_reclamos_estado ON public.reclamos USING btree (estado);
CREATE INDEX idx_reservas_amenities_vecino ON public.reservas_amenities USING btree (vecino_id);
CREATE INDEX idx_reservas_amenities_amenity ON public.reservas_amenities USING btree (amenity_id);
CREATE INDEX idx_reservas_amenities_fecha ON public.reservas_amenities USING btree (fecha);
CREATE INDEX idx_resumen_envios_liq_estado ON public.resumen_envios USING btree (liquidacion_id, estado);
CREATE INDEX idx_resumen_envios_estado ON public.resumen_envios USING btree (estado);
CREATE INDEX idx_resumen_envios_unidad ON public.resumen_envios USING btree (unidad_id);
CREATE INDEX idx_resumen_envios_liquidacion ON public.resumen_envios USING btree (liquidacion_id);
CREATE INDEX idx_solicitudes_vecino ON public.solicitudes_vinculacion USING btree (vecino_id);
CREATE INDEX idx_solicitudes_estado ON public.solicitudes_vinculacion USING btree (estado);
CREATE INDEX idx_solicitudes_consorcio ON public.solicitudes_vinculacion USING btree (consorcio_id);
CREATE INDEX idx_auditoria_target ON public.superadmin_auditoria USING btree (target_id);
CREATE INDEX idx_auditoria_created ON public.superadmin_auditoria USING btree (created_at DESC);
CREATE INDEX idx_ufs_consorcio ON public.unidades_funcionales USING btree (consorcio_id);
CREATE INDEX idx_vecino_auth0_id ON public.vecinos USING btree (auth0_id);
CREATE INDEX idx_vecinos_unidad_id ON public.vecinos USING btree (unidad_id);
CREATE INDEX idx_vecinos_created ON public.vecinos USING btree (created_at);
CREATE INDEX idx_vecino_email ON public.vecinos USING btree (email);
CREATE INDEX idx_vecinos_solicitud_pendiente ON public.vecinos USING btree (consorcio_solicitado_id) WHERE (estado_asociacion = 'pendiente'::text);
CREATE INDEX idx_vecinos_unidades_consorcio ON public.vecinos_unidades USING btree (consorcio_id);
CREATE INDEX idx_vecinos_unidades_vecino ON public.vecinos_unidades USING btree (vecino_id);
CREATE INDEX idx_vecinos_unidades_unidad ON public.vecinos_unidades USING btree (unidad_id);
CREATE INDEX idx_votaciones_consorcio ON public.votaciones USING btree (consorcio_id);
CREATE INDEX idx_votaciones_estado ON public.votaciones USING btree (estado);
CREATE INDEX idx_votos_votacion ON public.votos USING btree (votacion_id);
CREATE INDEX idx_votos_vecino ON public.votos USING btree (vecino_id);
