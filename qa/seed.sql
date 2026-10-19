-- ══════════════════════════════════════════════════════════════════════════════
-- Niddo — datos ficticios para el ambiente de pruebas (QA)
-- ══════════════════════════════════════════════════════════════════════════════
--
-- Se aplica DESPUÉS de schema.sql sobre una base vacía. Todo es inventado: los
-- emails usan el dominio reservado .test, que nunca entrega correo.
-- Los auth0_id 'qa|…' coinciden con QA_USUARIOS en app.py (/qa/login/<quien>).
-- Nunca correr esto contra la base de producción.

BEGIN;

-- ── Administradores ──────────────────────────────────────────────────────────
INSERT INTO administradores (id, auth0_id, email, nombre, estado, es_superadmin,
                             nombre_contacto, telefono, email_contacto, cuit, matricula, direccion,
                             solicitud_completada_at, resuelto_at)
VALUES
  ('a0000000-0000-4000-8000-000000000001', 'qa|admin', 'admin.qa@niddo.test', 'Admin QA',
   'aprobado', false, 'Admin QA', '11 5555-0001', 'admin.qa@niddo.test',
   '20-11111111-1', 'RPA-0001', 'Av. Ficticia 100, CABA', now(), now()),
  ('a0000000-0000-4000-8000-000000000002', 'qa|superadmin', 'superadmin.qa@niddo.test', 'Superadmin QA',
   'aprobado', true, 'Superadmin QA', '11 5555-0002', 'superadmin.qa@niddo.test',
   '20-22222222-2', 'RPA-0002', 'Av. Ficticia 200, CABA', now(), now()),
  ('a0000000-0000-4000-8000-000000000003', 'qa|pendiente', 'pendiente.qa@niddo.test', 'Admin Pendiente QA',
   'pendiente', false, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);

-- ── Consorcios ───────────────────────────────────────────────────────────────
INSERT INTO consorcios (id, nombre, direccion, cuit, pisos, unidades_totales, admin_id,
                        encargado_nombre, encargado_tel, banco_nombre, banco_cbu, banco_alias,
                        banco_titular, tasa_interes_mora, dias_gracia_mora, metodo_prorrateo)
VALUES
  ('c0000000-0000-4000-8000-000000000001', 'Edificio QA Libertador', 'Av. del Libertador 9999, CABA',
   '30-99999999-1', 3, 4, 'a0000000-0000-4000-8000-000000000001',
   'Encargado QA', '11 5555-0100', 'Banco Ficticio', '0000000000000000000001', 'EDIF.QA.LIBERTADOR',
   'Consorcio Edificio QA Libertador', 3, 5, 'm2'),
  ('c0000000-0000-4000-8000-000000000002', 'Torre QA Belgrano', 'Cabildo 9999, CABA',
   '30-99999999-2', 2, 2, 'a0000000-0000-4000-8000-000000000001',
   NULL, NULL, NULL, NULL, NULL, NULL, 0, 0, 'partes_iguales');

-- ── Unidades funcionales ─────────────────────────────────────────────────────
INSERT INTO unidades_funcionales (id, consorcio_id, numero, piso, tipo, superficie_m2, ambientes,
                                  porcentaje_a, vecino_nombre, vecino_email, vecino_id)
VALUES
  ('d0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', '1A', '1', 'departamento', 60, 2, 20, 'Vecina Uno QA', 'vecino1.qa@niddo.test', NULL),
  ('d0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', '1B', '1', 'departamento', 80, 3, 30, 'Vecino Dos QA', 'vecino2.qa@niddo.test', NULL),
  ('d0000000-0000-4000-8000-000000000003', 'c0000000-0000-4000-8000-000000000001', '2A', '2', 'departamento', 60, 2, 20, NULL, NULL, NULL),
  ('d0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000001', 'PB', '0', 'local', 90, 1, 30, NULL, NULL, NULL),
  ('d0000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000002', '1', '1', 'departamento', 50, 2, 50, NULL, NULL, NULL),
  ('d0000000-0000-4000-8000-000000000006', 'c0000000-0000-4000-8000-000000000002', '2', '2', 'departamento', 50, 2, 50, NULL, NULL, NULL);

-- ── Vecinos ──────────────────────────────────────────────────────────────────
INSERT INTO vecinos (id, auth0_id, email, nombre, unidad, consorcio_id, unidad_id, estado_asociacion, telefono)
VALUES
  ('b0000000-0000-4000-8000-000000000001', 'qa|vecino1', 'vecino1.qa@niddo.test', 'Vecina Uno QA', '1A',
   'c0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'aprobado', '11 5555-0201'),
  ('b0000000-0000-4000-8000-000000000002', 'qa|vecino2', 'vecino2.qa@niddo.test', 'Vecino Dos QA', '1B',
   'c0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000002', 'aprobado', '11 5555-0202');

UPDATE unidades_funcionales SET vecino_id = 'b0000000-0000-4000-8000-000000000001'
 WHERE id = 'd0000000-0000-4000-8000-000000000001';
UPDATE unidades_funcionales SET vecino_id = 'b0000000-0000-4000-8000-000000000002'
 WHERE id = 'd0000000-0000-4000-8000-000000000002';

-- ── Gastos del mes ───────────────────────────────────────────────────────────
INSERT INTO gastos (consorcio_id, admin_id, descripcion, categoria, monto, fecha_gasto,
                    fecha_vencimiento, pagado, coeficiente)
VALUES
  ('c0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001',
   'Abono mantenimiento ascensor', 'mantenimiento', 85000, current_date - 10, current_date + 5, false, 'A'),
  ('c0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001',
   'Limpieza de áreas comunes', 'limpieza', 120000, current_date - 8, current_date + 7, true, 'A'),
  ('c0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001',
   'Luz espacios comunes', 'electricidad', 45500.50, current_date - 5, current_date + 10, false, 'A');

-- ── Amenities ────────────────────────────────────────────────────────────────
INSERT INTO amenities (consorcio_id, nombre, descripcion, capacidad_maxima, max_reservas_mes, precio_uso)
VALUES
  ('c0000000-0000-4000-8000-000000000001', 'SUM', 'Salón de usos múltiples', 30, 2, 15000),
  ('c0000000-0000-4000-8000-000000000001', 'Parrilla', 'Parrilla de la terraza', 10, 4, 0);

-- ── Medios de pago ───────────────────────────────────────────────────────────
INSERT INTO medios_pago (consorcio_id, admin_id, nombre, descripcion, activo)
VALUES
  ('c0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001',
   'Transferencia bancaria', 'Alias EDIF.QA.LIBERTADOR · CBU 0000000000000000000001', true),
  ('c0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001',
   'Efectivo en administración', 'Lunes a viernes de 10 a 13', true);

COMMIT;
