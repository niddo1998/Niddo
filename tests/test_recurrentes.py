"""Tests del cálculo de períodos de gastos recurrentes.

Todo con fechas fijas: `hoy` se pasa como parámetro, así que estos tests dan lo
mismo el 1 de enero que el 29 de febrero.
"""

from datetime import date

import pytest

from recurrentes import (
    fecha_de_ocurrencia,
    periodo_de,
    periodos_pendientes,
    ultimo_dia_del_mes,
)


class TestMesesCortos:
    def test_dia_31_en_febrero_cae_el_28(self):
        assert fecha_de_ocurrencia(2026, 2, 31) == date(2026, 2, 28)

    def test_dia_31_en_febrero_bisiesto_cae_el_29(self):
        assert fecha_de_ocurrencia(2028, 2, 31) == date(2028, 2, 29)

    def test_dia_31_en_abril_cae_el_30(self):
        assert fecha_de_ocurrencia(2026, 4, 31) == date(2026, 4, 30)

    def test_dia_normal_no_se_toca(self):
        assert fecha_de_ocurrencia(2026, 2, 10) == date(2026, 2, 10)

    def test_febrero_bisiesto(self):
        assert ultimo_dia_del_mes(2028, 2) == 29
        assert ultimo_dia_del_mes(2026, 2) == 28


class TestGeneracionMensual:
    def test_el_periodo_de_la_plantilla_no_se_regenera(self):
        # La plantilla se cargó el 10 de agosto; agosto ya existe.
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 8, 10), dia_carga=10,
            frecuencia='mensual', hoy=date(2026, 8, 20),
        )
        assert pendientes == []

    def test_genera_el_mes_siguiente_cuando_llega_el_dia(self):
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 8, 10), dia_carga=10,
            frecuencia='mensual', hoy=date(2026, 9, 10),
        )
        assert pendientes == [('2026-09', date(2026, 9, 10))]

    def test_no_genera_antes_del_dia(self):
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 8, 10), dia_carga=10,
            frecuencia='mensual', hoy=date(2026, 9, 9),
        )
        assert pendientes == []

    def test_atraso_de_varios_meses_los_genera_todos(self):
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 5, 15), dia_carga=15,
            frecuencia='mensual', hoy=date(2026, 8, 20),
        )
        assert [p for p, _ in pendientes] == ['2026-06', '2026-07', '2026-08']

    def test_no_repite_los_ya_generados(self):
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 5, 15), dia_carga=15,
            frecuencia='mensual', hoy=date(2026, 8, 20),
            ya_generados=['2026-06', '2026-07'],
        )
        assert [p for p, _ in pendientes] == ['2026-08']

    def test_cruza_el_cambio_de_anio(self):
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 11, 5), dia_carga=5,
            frecuencia='mensual', hoy=date(2027, 1, 5),
        )
        assert [p for p, _ in pendientes] == ['2026-12', '2027-01']


class TestOtrasFrecuencias:
    def test_bimestral_saltea_un_mes(self):
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 1, 10), dia_carga=10,
            frecuencia='bimestral', hoy=date(2026, 7, 31),
        )
        assert [p for p, _ in pendientes] == ['2026-03', '2026-05', '2026-07']

    def test_trimestral(self):
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 1, 10), dia_carga=10,
            frecuencia='trimestral', hoy=date(2026, 12, 31),
        )
        assert [p for p, _ in pendientes] == ['2026-04', '2026-07', '2026-10']

    def test_anual(self):
        pendientes = periodos_pendientes(
            fecha_inicio=date(2024, 3, 1), dia_carga=1,
            frecuencia='anual', hoy=date(2026, 8, 16),
        )
        assert [p for p, _ in pendientes] == ['2025-03', '2026-03']

    def test_frecuencia_vacia_cae_en_mensual(self):
        # El formulario permite tildar "recurrente" sin elegir frecuencia.
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 6, 1), dia_carga=1,
            frecuencia='', hoy=date(2026, 8, 1),
        )
        assert [p for p, _ in pendientes] == ['2026-07', '2026-08']


class TestBordes:
    def test_sin_dia_de_carga_no_genera_nada(self):
        # Las plantillas viejas sin migrar no deben generar hasta tener día.
        assert periodos_pendientes(
            fecha_inicio=date(2026, 1, 1), dia_carga=None,
            frecuencia='mensual', hoy=date(2026, 8, 1),
        ) == []

    def test_plantilla_futura_no_genera_nada(self):
        assert periodos_pendientes(
            fecha_inicio=date(2027, 1, 1), dia_carga=1,
            frecuencia='mensual', hoy=date(2026, 8, 1),
        ) == []

    def test_dia_31_mes_a_mes_no_se_corre_de_periodo(self):
        # Cada ocurrencia se calcula desde el mes, no desde la fecha anterior:
        # que febrero caiga el 28 no tiene que arrastrar a marzo al 28.
        pendientes = periodos_pendientes(
            fecha_inicio=date(2026, 1, 31), dia_carga=31,
            frecuencia='mensual', hoy=date(2026, 4, 30),
        )
        assert pendientes == [
            ('2026-02', date(2026, 2, 28)),
            ('2026-03', date(2026, 3, 31)),
            ('2026-04', date(2026, 4, 30)),
        ]

    def test_tope_de_seguridad(self):
        # Una fecha con el año mal cargado no debe generar cientos de gastos.
        pendientes = periodos_pendientes(
            fecha_inicio=date(1999, 1, 1), dia_carga=1,
            frecuencia='mensual', hoy=date(2026, 8, 1),
        )
        assert len(pendientes) == 120

    @pytest.mark.parametrize('fecha,esperado', [
        (date(2026, 1, 5), '2026-01'),
        (date(2026, 12, 31), '2026-12'),
    ])
    def test_formato_de_periodo(self, fecha, esperado):
        assert periodo_de(fecha) == esperado
