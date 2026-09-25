-- ============================================================
--  Niddo — Supabase Schema v20 (Método de prorrateo por consorcio)
--  Ejecutar en: Supabase Dashboard → SQL Editor
--  Requiere haber ejecutado v1 → v19 antes
-- ============================================================
--
--  Hasta acá cada UF tenía cuatro porcentajes de copropiedad (A, B, C, E) y
--  cada gasto elegía por cuál se repartía. En la práctica nadie los cargaba:
--  quedaban en 0 y todo caía en reparto lineal. Lo que un administrador
--  espera es elegir UNA forma de repartir por edificio:
--
--    m2              superficie de la UF / superficie total   (el default)
--    ambientes       ambientes de la UF / ambientes totales
--    partes_iguales  lo mismo para todas las UFs
--    porcentaje      el % de participación cargado en cada UF (porcentaje_a)
--
--  Las columnas porcentaje_b/c/e y gastos.coeficiente no se borran: las
--  liquidaciones ya emitidas las siguen leyendo.
--
--  Es idempotente: se puede correr más de una vez sin romper nada.
-- ============================================================

alter table consorcios
  add column if not exists metodo_prorrateo text not null default 'm2';

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'consorcios_metodo_prorrateo_check') then
    alter table consorcios add constraint consorcios_metodo_prorrateo_check
      check (metodo_prorrateo in ('m2', 'ambientes', 'partes_iguales', 'porcentaje'));
  end if;
end $$;

-- La base del reparto por ambientes. NULL = no cargado.
alter table unidades_funcionales
  add column if not exists ambientes smallint;

-- Un consorcio que ya tenía sus porcentajes cargados (y que cierran en 100)
-- sigue repartiendo por esos porcentajes: pasarlo a m² le cambiaría las
-- expensas a todos sin que nadie lo pidiera.
update consorcios c
   set metodo_prorrateo = 'porcentaje'
 where metodo_prorrateo = 'm2'
   and exists (
     select 1 from unidades_funcionales u
      where u.consorcio_id = c.id
      group by u.consorcio_id
     having abs(sum(coalesce(u.porcentaje_a, 0)) - 100) <= 0.5
   );

notify pgrst, 'reload schema';
