"""Cálculo de períodos para los gastos recurrentes.

Vive aparte de `app.py` a propósito: es la parte del feature que concentra el
riesgo (meses cortos, años bisiestos, atrasos de varios períodos) y es la única
que se puede testear sin una base de datos adelante. Todo lo de acá es
determinístico — se le pasa la fecha de hoy, no se la pregunta al reloj — así
que los tests no dependen del día en que se corran.
"""

from calendar import monthrange
from datetime import date

# Cuántos meses separan una ocurrencia de la siguiente.
MESES_POR_FRECUENCIA = {
    'mensual': 1,
    'bimestral': 2,
    'trimestral': 3,
    'anual': 12,
}

FRECUENCIA_POR_DEFECTO = 'mensual'

# Tope de seguridad del barrido. Una plantilla con una `fecha_gasto` cargada
# con el año mal (2019 en vez de 2029) generaría cientos de gastos de un saque
# y llenaría la liquidación de basura. Con el tope, el error se nota como
# "faltan meses" en vez de como una tabla inutilizable.
MAX_PERIODOS = 120


def ultimo_dia_del_mes(anio, mes):
    """Devuelve el último día de ese mes, contemplando años bisiestos."""
    return monthrange(anio, mes)[1]


def fecha_de_ocurrencia(anio, mes, dia_carga):
    """La fecha del gasto en ese mes, recortada si el mes es más corto.

    Un gasto con `dia_carga = 31` tiene que caer igual en febrero. Se recorta
    al último día en vez de pasar al 1 del mes siguiente, para que el gasto
    quede dentro del período que le corresponde: `fecha_gasto` es lo que usa la
    liquidación para decidir de qué mes es cada gasto, así que correrlo un día
    lo movería de liquidación.
    """
    return date(anio, mes, min(dia_carga, ultimo_dia_del_mes(anio, mes)))


def _sumar_meses(anio, mes, cantidad):
    total = (anio * 12 + (mes - 1)) + cantidad
    return total // 12, (total % 12) + 1


def periodo_de(fecha):
    """Formato `YYYY-MM`, el mismo que usa el resto de la app."""
    return f'{fecha.year:04d}-{fecha.month:02d}'


def periodos_pendientes(fecha_inicio, dia_carga, frecuencia, hoy, ya_generados=()):
    """Ocurrencias que deberían existir y todavía no existen.

    `fecha_inicio` es la `fecha_gasto` de la plantilla; su propio período no
    cuenta como pendiente, porque ese gasto ya está cargado — es la plantilla
    misma. La primera ocurrencia generada es un intervalo después.

    Devuelve una lista de `(periodo, fecha)` ordenada de más vieja a más nueva.
    Si el administrador no entró a la app en tres meses, vuelven los tres: un
    gasto fijo no deja de existir porque nadie haya abierto el navegador.

    `ya_generados` es el conjunto de períodos que ya tienen hijo. Filtrarlos acá
    evita el INSERT que va a rebotar contra el índice único, pero el índice
    sigue siendo la garantía real: entre este chequeo y la inserción puede
    entrar otra request.
    """
    if not dia_carga or not fecha_inicio:
        return []

    paso = MESES_POR_FRECUENCIA.get(
        (frecuencia or '').strip().lower(),
        MESES_POR_FRECUENCIA[FRECUENCIA_POR_DEFECTO],
    )

    ya_generados = set(ya_generados)
    pendientes = []
    anio, mes = fecha_inicio.year, fecha_inicio.month

    for _ in range(MAX_PERIODOS):
        anio, mes = _sumar_meses(anio, mes, paso)
        fecha = fecha_de_ocurrencia(anio, mes, dia_carga)
        if fecha > hoy:
            break
        periodo = periodo_de(fecha)
        if periodo not in ya_generados:
            pendientes.append((periodo, fecha))

    return pendientes
