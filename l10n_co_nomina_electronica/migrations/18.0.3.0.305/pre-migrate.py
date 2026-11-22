# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""H-F1-01 (doc 84, decision D-84-1 = B del TL): el encadenamiento de incapacidades comunes pasa de «por fechas» a «por vinculo explicito» (``Prórroga de``).

Hasta .304 el modulo encadenaba dos incapacidades validadas del empleado cuando la siguiente empezaba a mas tardar ``l10n_co_dias_interrupcion_prorroga`` + 1 dias despues del fin de la
anterior (el parametro valia 0: solo contiguas). Desde .305 solo se encadenan las que tienen el vinculo. Para que NINGUNA cifra calculada cambie, esta migracion CREA el vinculo en los
pares que hoy se encadenan por fechas: la siguiente apunta a la anterior de la cadena (la misma «anterior» que usaba el motor: la ultima de la cadena vigente).

Va en PRE-migrate porque la carga de datos de .305 sube el parametro de 0 a 30 y aqui se necesita el valor que regia hasta ahora, a la fecha de inicio de cada incapacidad. Respeta lo que ya hay:
- no sobrescribe un vinculo existente (puesto a mano);
- no vincula si la anterior ya tiene una prorroga (la cadena es una lista) ni si hay solape (la anterior no termina antes de que empiece la siguiente);
- no vincula si los dias libres superan el tope nuevo (30), para no violar la restriccion de .305: lo deja en el registro para decision del TL.
Idempotente: una segunda corrida no encuentra pares sin vinculo. Escribe en SQL (sin tracking ni restricciones del ORM) y deja la lista de lo hecho en el log."""

import logging
from ast import literal_eval
from datetime import timedelta

_logger = logging.getLogger(__name__)

TOPE_NUEVO = 30
CODIGO_PARAMETRO = 'l10n_co_dias_interrupcion_prorroga'


def _valores_del_parametro(cr):
    """[(date_from, dias)] del parametro vigente hasta .304, de la fecha mas reciente a la mas antigua."""
    cr.execute("""
        SELECT v.date_from, v.parameter_value
          FROM hr_rule_parameter_value v
          JOIN hr_rule_parameter p ON p.id = v.rule_parameter_id
         WHERE p.code = %s
         ORDER BY v.date_from DESC""", (CODIGO_PARAMETRO,))
    return [(fecha, int(literal_eval(valor))) for fecha, valor in cr.fetchall()]


def _interrupcion_a(valores, fecha):
    """Dias del parametro a ``fecha``; sin valor anterior a esa fecha, el codigo de .304 habria fallado: se toma 0 (solo contiguas, el valor entregado)."""
    for desde, dias in valores:
        if desde <= fecha:
            return dias
    return 0


def migrate(cr, version):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_leave' AND column_name = 'l10n_co_ne_prorroga_de_id'")
    if not cr.fetchone():
        return          # instalacion sin el campo (no hay nada que migrar)
    valores = _valores_del_parametro(cr)
    cr.execute("""
        SELECT l.id, l.employee_id, l.request_date_from, l.request_date_to, l.l10n_co_ne_prorroga_de_id
          FROM hr_leave l
          JOIN hr_leave_type t ON t.id = l.holiday_status_id
          JOIN hr_work_entry_type w ON w.id = t.work_entry_type_id
         WHERE l.state = 'validate' AND w.code = 'CO_INC_COMUN'
         ORDER BY l.employee_id, l.request_date_from, l.id""")
    filas = cr.fetchall()
    # ids que ya tienen una prorroga siguiente (vinculo existente): su «anterior» no admite otra
    con_siguiente = {anterior for _id, _emp, _ini, _fin, anterior in filas if anterior}
    vinculados, saltados_tope, saltados_otro = [], [], []
    actual = None           # (id, fin) de la ultima incapacidad de la cadena vigente, como `actual[-1]` del motor viejo
    empleado = None
    for id_leave, id_emp, ini, fin, vinculo in filas:
        if id_emp != empleado:
            empleado, actual = id_emp, None
        if actual:
            id_ant, fin_ant = actual
            interrupcion = _interrupcion_a(valores, ini)
            if ini <= fin_ant + timedelta(days=1 + interrupcion):         # el motor viejo la encadenaba
                libres = (ini - fin_ant).days - 1
                if vinculo:
                    pass                                                   # ya tiene vinculo (a mano): no se toca
                elif ini <= fin_ant:
                    saltados_otro.append((id_leave, 'solape con la anterior'))
                elif id_ant in con_siguiente:
                    saltados_otro.append((id_leave, 'la anterior ya tiene otra prorroga'))
                elif libres > TOPE_NUEVO:
                    saltados_tope.append((id_leave, libres))
                else:
                    vinculados.append((id_leave, id_ant))
                    con_siguiente.add(id_ant)
                actual = (id_leave, fin)                                   # igual que `actual[-1]` del motor viejo: la ultima agregada
                continue
        actual = (id_leave, fin)
    for id_leave, id_ant in vinculados:
        cr.execute("UPDATE hr_leave SET l10n_co_ne_prorroga_de_id = %s WHERE id = %s AND l10n_co_ne_prorroga_de_id IS NULL", (id_ant, id_leave))
    _logger.info('H-F1-01 (.305): %d incapacidades comunes quedaron vinculadas a su anterior (pares que ya se encadenaban por fechas); %d no se vincularon por superar el tope de %d dias '
                 'libres %s; %d por solape o porque la anterior ya tenia otra prorroga %s.',
                 len(vinculados), len(saltados_tope), TOPE_NUEVO, saltados_tope, len(saltados_otro), saltados_otro)
