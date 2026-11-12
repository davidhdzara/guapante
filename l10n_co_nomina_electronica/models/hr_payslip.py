# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.payslip – Modelo central de Nómina Electrónica DIAN.

Este es el módulo principal que orquesta todo el ciclo de vida de un
documento de soporte de pago de nómina electrónica:

1. **Generación del XML**: recopila datos del payslip, mapea las líneas
   salariales a la estructura Devengados/Deducciones, construye el XML
   según el anexo técnico V1.0, calcula el CUNE y firma digitalmente.

2. **Envío a la DIAN**: transmite el XML firmado al servicio web de la
   DIAN y almacena la respuesta (aceptado/rechazado).

3. **Notas de Ajuste**: permite crear documentos de ajuste (reemplazo o
   eliminación) referenciando el CUNE de la nómina original.

Referencia: Anexo Técnico – Documento Soporte de Pago de Nómina Electrónica
V1.0, Resolución DIAN 000013 de 2021.
"""

import base64
import calendar
import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from pytz import timezone as _pytz_timezone
from lxml import etree as _etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_round

from ..services import (
    cune as cune_service,
    dian_utils,
    nomina_xml_builder,
    soap_client,
    xml_signer,
)

_logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────
# Mapeo de conceptos DIAN a la estructura XML de Devengados
# Cada clave es el valor de l10n_co_ne_dian_concept y el valor es la ruta
# dentro del dict que se envía a nomina_xml_builder.
# ──────────────────────────────────────────────────────────────────────────
DEVENGADO_SIMPLE_CONCEPTS = {
    'Dotacion': 'Dotacion',
    'ApoyoSost': 'ApoyoSost',
    'Teletrabajo': 'Teletrabajo',
    'BonifRetiro': 'BonifRetiro',
    'Indemnizacion': 'Indemnizacion',
    'Reintegro': 'Reintegro',
}

HORA_EXTRA_CONCEPTS = {'HED', 'HEN', 'HRN', 'HEDDF', 'HRDDF', 'HENDF', 'HRNDF'}

# H-013 (2026-10-08, QA Bloque 4, decisión de David): códigos de hr.work.entry.type de las
# ausencias colombianas que este módulo paga con su propia regla salarial (data/
# l10n_co_ausencias_data.xml). _ne_dias_pagables() las excluye SIEMPRE del básico (nunca
# dependen de hr.leave.type.unpaid, que es un eje distinto -- ver el comentario en esa
# función) y cada regla lee los mismos días -- una sola fuente para ambos lados, nunca
# doble pago.
#
# Dos grupos, con dos mecanismos de conteo distintos (H-014, 2026-10-08, QA Bloque 5,
# decisión de David basada en CST Art. 186/227/236 mod. Ley 2114/2021 y Concepto
# Mintrabajo 63044901/2022):
#
# - CO_VAC/CO_LIC_REM/CO_LIC_NR: días HÁBILES según el calendario laboral del contrato
#   (L-V, L-S o el de la compañía) -- cuentan vía worked_days (_ne_dias_novedad()), el
#   mecanismo nativo de hr.work.entry ya hace esta cuenta correctamente.
# - CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL: días CALENDARIO corridos (lunes a
#   domingo, festivos incluidos -- el empleado no puede quedar subpagado). worked_days NO
#   alcanza para esto: los work entries solo existen en los días que el calendario del
#   contrato define como laborables (confirmado contra hr_work_entry_contract.
#   _get_contract_work_entries_values -- un día sin asistencia en ese calendario, ej. el
#   lunes en un calendario martes-a-domingo, nunca genera NINGÚN work entry). Por eso estos
#   4 cuentan directamente desde las fechas de la hr.leave validada
#   (_ne_ausencia_calendario()), no desde worked_days.
_NOVEDAD_AUSENCIA_WORKED_DAYS_CODES = {'CO_VAC', 'CO_LIC_REM', 'CO_LIC_NR'}
_NOVEDAD_AUSENCIA_CALENDARIO_CODES = {
    'CO_LIC_MAT', 'CO_LIC_PAT', 'CO_INC_COMUN', 'CO_INC_LABORAL',
}

DEDUCTION_SIMPLE_CONCEPTS = {
    'PensionVoluntaria': 'PensionVoluntaria',
    'RetencionFuente': 'RetencionFuente',
    'AFC': 'AFC',
    'Cooperativa': 'Cooperativa',
    'EmbargoFiscal': 'EmbargoFiscal',
    'PlanComplementarios': 'PlanComplementarios',
    'Educacion': 'Educacion',
    'ReintegroDed': 'Reintegro',
    'Deuda': 'Deuda',
}




class HrPayslip(models.Model):
    """Nómina electrónica – modelo central con ciclo DIAN completo."""

    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'l10n.co.ne.documento.mixin']








    l10n_co_ne_is_salarial = fields.Boolean(
        string='Es Salarial (Bonificaciones)',
        default=True,
        help='Determina si las bonificaciones de esta nomina constituyen salario '
             'para el calculo de seguridad social y deducciones.',
    )



    # ──────────────────────────────────────────────────────────────────
    # Liquidación de Contrato (doc 20 §6)
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_liquidacion_cause = fields.Selection(
        selection=[
            ('justa_causa', 'Despido con Justa Causa'),
            ('sin_justa_causa', 'Despido sin Justa Causa'),
            ('renuncia', 'Renuncia Voluntaria'),
            ('mutuo_acuerdo', 'Mutuo Acuerdo'),
            ('fin_obra', 'Terminación de Obra o Labor'),
            ('muerte', 'Muerte del Trabajador'),
        ],
        string='Causa de Retiro',
        copy=False,
        help='Causa de terminación del contrato laboral, solo aplicable a '
             'payslips de estructura Liquidación de Contrato. La lee '
             'directamente CO_LIQ_INDEMNIZACION (condition_python: solo '
             'aplica indemnización si es "sin_justa_causa") -- también se '
             'guarda para trazabilidad y reportes.',
    )



    # ══════════════════════════════════════════════════════════════════
    # ACCIONES PRINCIPALES
    # ══════════════════════════════════════════════════════════════════


    # Deduccion (codigo de regla) -> campo del contrato con su tercero.
    _NE_TERCERO_DEDUCCION_CONTRATO = {
        'CO_SINDICATO': 'l10n_co_ne_sindicato_partner_id',
        'CO_AFC': 'l10n_co_ne_afc_partner_id',
        'CO_PENSION_VOL': 'l10n_co_ne_pension_voluntaria_partner_id',
        'CO_PLAN_COMP': 'l10n_co_ne_plan_complementario_partner_id',
        'CO_COOPERATIVA': 'l10n_co_ne_cooperativa_partner_id',
        'CO_EDUCACION': 'l10n_co_ne_educacion_partner_id',
    }

    def _ne_validar_terceros_deducciones(self):
        """Sin valores por defecto silenciosos: una deduccion calculada
        (desde el contrato o desde un input manual) exige el contacto al que
        se paga lo retenido, definido en el contrato."""
        for slip in self:
            for line in slip.line_ids:
                campo = self._NE_TERCERO_DEDUCCION_CONTRATO.get(line.code)
                if not campo or not line.total:
                    continue
                contract = slip.contract_id
                if not contract[campo]:
                    raise UserError(_(
                        'La nomina "%(nomina)s" calcula la deduccion '
                        '"%(regla)s", pero el contrato "%(contrato)s" no '
                        'tiene el contacto de la entidad. Complete el campo '
                        '"%(campo)s" en el contrato (pestana Deducciones '
                        'Fijas).',
                        nomina=slip.display_name,
                        regla=line.name,
                        contrato=contract.display_name,
                        campo=contract._fields[campo].string,
                    ))

    # ──────────────────────────────────────────────────────────────────
    # Libranzas (Ley 1527/2012) -- lineas en hr.salary.attachment
    # ──────────────────────────────────────────────────────────────────
    def _ne_libranzas_vigentes(self):
        """Asignaciones salariales de libranza abiertas y vigentes en el
        periodo, por antiguedad (date_start, id)."""
        self.ensure_one()
        return self.employee_id.salary_attachment_ids.filtered(
            lambda a: a.state == 'open'
            and a.other_input_type_id.code == 'L10N_CO_LIBRANZA'
            and a.date_start <= self.date_to
            and (not a.date_end or a.date_end >= self.date_from)
        ).sorted(key=lambda a: (a.date_start, a.id))

    def _ne_libranzas_aplican(self):
        self.ensure_one()
        return bool(self._ne_libranzas_vigentes())

    def _ne_libranzas_calcular(self, neto_ley, embargo):
        """Total a descontar por libranzas y su reparto por asignacion.

        Tope sobre la SUMA de las libranzas (Ley 1527/2012, Art. 3 num. 5):
            cupo = pct_tope x neto_de_ley - embargos   (pct = parametro)
        Orden de imputacion (decision Tech Lead, principio general de
        imputacion de pagos, Art. 1654 Codigo Civil): primero el saldo
        pendiente de periodos anteriores, del mas antiguo al mas reciente, y
        luego la cuota del periodo con el cupo que quede. Lo que no cabe en
        el cupo no se pierde: queda como `deferred` y suma al saldo pendiente
        de la asignacion al confirmar la nomina.
        Persiste el reparto en l10n.co.payslip.tercero y devuelve el total.
        """
        self.ensure_one()
        pct = self._rule_parameter('l10n_co_pct_tope_libranzas', self._ne_fecha_parametros())
        cupo = max(0.0, neto_ley * pct / 100.0 - embargo)
        rows = {}
        for att in self._ne_libranzas_vigentes():
            if not att.l10n_co_partner_id:
                raise UserError(_(
                    'La libranza "%(libranza)s" del empleado %(empleado)s no '
                    'tiene el contacto de la entidad. Complete "Juzgado / '
                    'Entidad" en Asignaciones Salariales.',
                    libranza=att.display_name, empleado=self.employee_id.name))
            rows[att] = {'arrears_paid': 0.0, 'paid': 0.0, 'deferred': 0.0}
        for att, r in rows.items():  # 1) atrasado, mas antiguo primero
            r['arrears_paid'] = min(att.l10n_co_saldo_pendiente, cupo)
            cupo -= r['arrears_paid']
        for att, r in rows.items():  # 2) cuota del periodo con el cupo restante
            cuota = att.monthly_amount
            if att.has_total_amount:
                cuota = min(cuota, max(
                    0.0, att.remaining_amount - att.l10n_co_saldo_pendiente))
            r['paid'] = min(cuota, cupo)
            cupo -= r['paid']
            r['deferred'] = cuota - r['paid']
        self._ne_guardar_reparto('CO_LIBRANZAS', [{
            'partner_id': att.l10n_co_partner_id.id, 'attachment_id': att.id,
            'amount': r['arrears_paid'] + r['paid'],
            'arrears_paid': r['arrears_paid'], 'deferred': r['deferred'],
        } for att, r in rows.items()])
        return sum(r['arrears_paid'] + r['paid'] for r in rows.values())

    def _ne_guardar_reparto(self, rule_code, filas):
        """Reemplaza el reparto por tercero (aun no aplicado) de una regla."""
        self.ensure_one()
        Tercero = self.env['l10n.co.payslip.tercero'].sudo()
        Tercero.search([('slip_id', '=', self.id), ('rule_code', '=', rule_code),
                        ('applied', '=', False)]).unlink()
        Tercero.create([dict(f, slip_id=self.id, rule_code=rule_code) for f in filas])

    # Prelacion legal de embargos: alimentos/cooperativa (Art. 156 CST) antes
    # que civil/ordinario (Art. 155 CST).
    _NE_PRIORIDAD_EMBARGO = {
        'L10N_CO_EMBARGO_ALIMENTOS': 0,
        'L10N_CO_EMBARGO_COOPERATIVA': 1,
        'L10N_CO_EMBARGO_CIVIL': 2,
    }

    def _ne_embargos_calcular(self, salario_neto, smmlv, manual=0.0):
        """Total de embargos a descontar y su reparto por asignacion.

        Misma logica que tenia la regla CO_EMBARGO en linea: cada embargo con
        su tope (Art. 155/156 CST), en orden de prelacion, reducido hasta que
        el remanente no baje del SMMLV (piso de minimo vital). El input manual
        `manual` tambien respeta el piso; como no tiene juzgado, si excede lo
        que reparten las asignaciones con tercero se rechaza (sin tercero no
        hay asiento por tercero).
        """
        self.ensure_one()
        activos = self.employee_id.salary_attachment_ids.filtered(
            lambda a: a.state == 'open'
            and a.other_input_type_id.code in self._NE_PRIORIDAD_EMBARGO)
        ordenados = activos.sorted(
            key=lambda a: self._NE_PRIORIDAD_EMBARGO.get(a.other_input_type_id.code, 99))
        factor = self._rule_parameter('l10n_co_factor_embargo_civil', self._ne_fecha_parametros())
        pct = self._rule_parameter('l10n_co_pct_tope_embargo_alimentos', self._ne_fecha_parametros())
        total = 0.0
        filas = []
        for emb in ordenados:
            individual = emb._l10n_co_compute_embargo_amount(
                salario_neto, smmlv, self.date_from,
                factor_embargo_civil=factor, pct_tope_embargo_alimentos=pct)
            espacio = max(0.0, (salario_neto - total) - smmlv)
            aplicado = min(individual, espacio)
            total += aplicado
            filas.append({
                'partner_id': emb.l10n_co_partner_id.id,
                'attachment_id': emb.id, 'amount': aplicado})
        if manual and manual > 0:
            manual_topado = min(manual, max(0.0, salario_neto - smmlv))
            if manual_topado > total + 0.005:
                raise UserError(_(
                    'El ajuste manual de embargo (%(manual).2f) de la nomina '
                    '"%(nomina)s" excede lo que reparten las asignaciones '
                    'salariales con juzgado/entidad (%(total).2f). Registre el '
                    'embargo en Asignaciones Salariales con su "Juzgado / '
                    'Entidad".',
                    manual=manual_topado, nomina=self.display_name, total=total))
        self._ne_guardar_reparto('CO_EMBARGO', filas)
        return total

    # ──────────────────────────────────────────────────────────────────
    # Liquidacion: embargos y libranzas por tipo de concepto
    # (CST arts. 154-156 y 344; Ley 1527/2012; SL3208-2022)
    # ──────────────────────────────────────────────────────────────────
    def _ne_liq_montos(self, result_rules):
        """Valor positivo de cada tipo de concepto de la liquidacion, segun
        el tratamiento (l10n_co_liq_tratamiento) de las reglas de la estructura."""
        self.ensure_one()
        montos = dict.fromkeys(
            ('salario', 'vacaciones', 'prestacion', 'indemnizacion'), 0.0)
        for regla in self.struct_id.rule_ids:
            if regla.l10n_co_liq_tratamiento:
                montos[regla.l10n_co_liq_tratamiento] += abs(
                    result_rules[regla.code]['total'])
        return montos

    def _ne_liq_embargos_vigentes(self):
        self.ensure_one()
        return self.employee_id.salary_attachment_ids.filtered(
            lambda a: a.state == 'open'
            and a.other_input_type_id.code in self._NE_PRIORIDAD_EMBARGO
            and a.date_start <= self.date_to
            and (not a.date_end or a.date_end >= self.date_from)
        ).sorted(key=lambda a: self._NE_PRIORIDAD_EMBARGO[a.other_input_type_id.code])

    def _ne_liq_libranzas_autorizadas(self):
        self.ensure_one()
        return self._ne_libranzas_vigentes().filtered(
            lambda a: a.l10n_co_autoriza_liquidacion
            and (a.remaining_amount if a.has_total_amount else a.l10n_co_saldo_pendiente) > 0)

    def _ne_liq_embargos_aplican(self):
        return bool(self._ne_liq_embargos_vigentes())

    def _ne_liq_libranzas_aplican(self):
        return bool(self._ne_liq_libranzas_autorizadas())

    def _ne_liq_embargos_distribuir(self, montos, legal):
        """Reparto de embargos sobre la liquidacion (sin persistir).

        Salario y vacaciones compensadas forman un solo grupo (las vacaciones
        se tratan como salario). Civil: 1/5 del excedente sobre el SMMLV y
        solo sobre ese grupo. Alimentos/cooperativa: hasta el 50% del grupo y,
        si la orden alcanza prestaciones (Art. 344), hasta el 50% de ellas,
        limitado a la deuda si tiene monto total. La indemnizacion solo si la
        orden la alcanza. Piso de minimo vital solo sobre el grupo salarial.
        Devuelve (filas, disponible) con lo que queda por concepto.
        """
        self.ensure_one()
        smmlv = self._rule_parameter('l10n_co_smmlv', self._ne_fecha_parametros())
        factor = self._rule_parameter('l10n_co_factor_embargo_civil', self._ne_fecha_parametros())
        pct = self._rule_parameter('l10n_co_pct_tope_embargo_alimentos', self._ne_fecha_parametros())
        sal, vac = montos['salario'], montos['vacaciones']
        pres, ind = montos['prestacion'], montos['indemnizacion']
        # descuentos de ley: primero contra salario, el resto contra vacaciones
        sal_ley = max(0.0, sal - legal)
        vac_ley = max(0.0, vac - max(0.0, legal - sal))
        base_grupo = sal_ley + vac_ley
        usado_grupo = usado_ind = usado_pres = 0.0
        filas = []
        for emb in self._ne_liq_embargos_vigentes():
            con_ind = emb.l10n_co_alcanza_indemnizacion
            base = base_grupo + (ind if con_ind else 0.0)
            individual = emb._l10n_co_compute_embargo_amount(
                base, smmlv, self.date_from,
                factor_embargo_civil=factor, pct_tope_embargo_alimentos=pct)
            espacio = max(0.0, (base - usado_grupo - usado_ind) - smmlv)
            aplicado = min(individual, espacio)
            en_grupo = min(aplicado, max(0.0, base_grupo - usado_grupo))
            en_ind = aplicado - en_grupo
            usado_grupo += en_grupo
            usado_ind += en_ind
            en_pres = 0.0
            if emb.other_input_type_id.code != 'L10N_CO_EMBARGO_CIVIL' \
                    and emb.l10n_co_alcanza_prestaciones and pres:
                en_pres = max(0.0, min(pres * pct / 100.0 - usado_pres, pres - usado_pres))
                if emb.has_total_amount:
                    en_pres = min(en_pres, max(0.0, emb.remaining_amount - aplicado))
                usado_pres += en_pres
            filas.append({
                'partner_id': emb.l10n_co_partner_id.id,
                'attachment_id': emb.id, 'amount': aplicado + en_pres})
        emb_sal = min(usado_grupo, sal_ley)
        disponible = {
            'salario_ley': sal_ley, 'emb_salario': emb_sal,
            'salario': sal_ley - emb_sal,
            'vacaciones': vac_ley - (usado_grupo - emb_sal),
            'prestacion': pres - usado_pres,
            'indemnizacion': ind - usado_ind,
        }
        return filas, disponible

    def _ne_liq_embargos_calcular(self, result_rules, legal):
        self.ensure_one()
        filas, _disp = self._ne_liq_embargos_distribuir(
            self._ne_liq_montos(result_rules), abs(legal))
        self._ne_guardar_reparto('CO_LIQ_EMBARGO', filas)
        return sum(f['amount'] for f in filas)

    def _ne_liq_libranzas_calcular(self, result_rules, legal):
        """Libranzas autorizadas contra la liquidacion, despues de embargos.

        Deuda a cubrir: saldo insoluto si la libranza tiene monto total; si
        no, el saldo pendiente. Orden de toma: salario (con el tope de la Ley
        1527: 50% del neto de ley menos embargo), vacaciones, prestaciones e
        indemnizacion (estas sin tope, SL3208-2022). Lo que no alcance queda
        a cargo del trabajador frente a la entidad.
        """
        self.ensure_one()
        montos = self._ne_liq_montos(result_rules)
        _filas, disp = self._ne_liq_embargos_distribuir(montos, abs(legal))
        pct = self._rule_parameter('l10n_co_pct_tope_libranzas', self._ne_fecha_parametros())
        cupo_salario = max(0.0, pct / 100.0 * disp['salario_ley'] - disp['emb_salario'])
        buckets = [
            ['salario', min(disp['salario'], cupo_salario)],
            ['vacaciones', disp['vacaciones']],
            ['prestacion', disp['prestacion']],
            ['indemnizacion', disp['indemnizacion']],
        ]
        filas = []
        for att in self._ne_liq_libranzas_autorizadas():
            if not att.l10n_co_partner_id:
                raise UserError(_(
                    'La libranza "%(libranza)s" del empleado %(empleado)s no '
                    'tiene el contacto de la entidad. Complete "Juzgado / '
                    'Entidad" en Asignaciones Salariales.',
                    libranza=att.display_name, empleado=self.employee_id.name))
            deuda = att.remaining_amount if att.has_total_amount else att.l10n_co_saldo_pendiente
            tomado = 0.0
            for b in buckets:
                t = max(0.0, min(b[1], deuda - tomado))
                b[1] -= t
                tomado += t
            filas.append({
                'partner_id': att.l10n_co_partner_id.id, 'attachment_id': att.id,
                'amount': tomado,
                'arrears_paid': min(tomado, att.l10n_co_saldo_pendiente),
                'deferred': 0.0})
        self._ne_guardar_reparto('CO_LIQ_LIBRANZAS', filas)
        return sum(f['amount'] for f in filas)

    def _ne_aplicar_libranzas(self, revertir=False):
        """Refleja (o revierte) lo descontado en pagado y saldo pendiente."""
        signo = -1 if revertir else 1
        for row in self.env['l10n.co.payslip.tercero'].sudo().search([
                ('slip_id', 'in', self.ids),
                ('rule_code', 'in', ('CO_LIBRANZAS', 'CO_LIQ_LIBRANZAS')),
                ('applied', '=', revertir)]):
            att = row.attachment_id
            att.write({
                'paid_amount': att.paid_amount + signo * row.amount,
                'l10n_co_saldo_pendiente':
                    att.l10n_co_saldo_pendiente + signo * (row.deferred - row.arrears_paid),
            })
            row.applied = not revertir
            if row.rule_code == 'CO_LIQ_LIBRANZAS':
                self._ne_cerrar_libranza_liquidada(att, revertir)
                continue
            if not revertir and att.has_total_amount and not att.remaining_amount \
                    and att.state == 'open' and att.employee_count == 1:
                att.action_done()

    def _ne_cerrar_libranza_liquidada(self, att, revertir):
        """Al confirmar la liquidacion la libranza se cierra y deja constancia
        del saldo que el trabajador sigue debiendo a la entidad."""
        if revertir:
            if att.state == 'close':
                att.action_open()
            return
        debe = att.remaining_amount if att.has_total_amount else att.l10n_co_saldo_pendiente
        if debe > 0:
            att.message_post(body=_(
                'Liquidación confirmada: saldo no cubierto de %(saldo).2f. El '
                'trabajador queda debiendo ese valor directamente a la entidad.',
                saldo=debe))
        if att.state == 'open':
            att.action_done()

    def _ne_refrescar_ibc_mensual(self):
        """Recalcula el IBC consolidado de cada empleado/mes afectado (idempotente)."""
        Consolidado = self.env['l10n.co.ibc.mensual']
        for clave in {(s.company_id, s.employee_id, s.date_to.replace(day=1)) for s in self}:
            Consolidado._refrescar(*clave)

    def _ne_validar_terceros_attachments(self):
        """Embargos y libranzas exigen el contacto (juzgado / entidad)."""
        for slip in self:
            for att in slip.salary_attachment_ids:
                code = att.other_input_type_id.code
                if (att.l10n_co_es_embargo or att.l10n_co_es_libranza) \
                        and not att.l10n_co_partner_id:
                    raise UserError(_(
                        'La asignación salarial "%(att)s" (%(tipo)s) del '
                        'empleado %(empleado)s no tiene "Juzgado / Entidad". '
                        'Complételo en Asignaciones Salariales.',
                        att=att.display_name, tipo=code,
                        empleado=slip.employee_id.name))

    def _ne_solo_colombia(self):
        """Los recibos de companias colombianas (ver res.company._ne_es_colombia)."""
        return self.filtered(lambda s: s.company_id._ne_es_colombia())

    def compute_sheet(self):
        colombia = self._ne_solo_colombia()
        colombia._ne_validar_terceros_attachments()
        # Cada recibo se calcula en el contexto de SU compania: los parametros (hr.rule.parameter,
        # por pais) y env.company salen de la compania del recibo, no de la activa en el selector.
        res = True
        for company in self.company_id:
            recibos = self.filtered(lambda s, c=company: s.company_id == c).with_company(company)
            res = super(HrPayslip, recibos).compute_sheet()
        colombia._ne_validar_terceros_deducciones()
        return res

    # ──────────────────────────────────────────────────────────────────
    # Asiento contable por tercero
    # ──────────────────────────────────────────────────────────────────
    _NE_TERCERO_ORIGEN_CAMPO = {
        'employee_eps': ('employee_id', 'l10n_co_pila_eps_id'),
        'employee_afp': ('employee_id', 'l10n_co_pila_afp_id'),
        'employee_ccf': ('employee_id', 'l10n_co_pila_ccf_id'),
        'company_arl': ('company_id', 'l10n_co_pila_arl_id'),
        'company_sena': ('company_id', 'l10n_co_sena_partner_id'),
        'company_icbf': ('company_id', 'l10n_co_icbf_partner_id'),
        'company_dian': ('company_id', 'l10n_co_dian_partner_id'),
        'contract_sindicato': ('contract_id', 'l10n_co_ne_sindicato_partner_id'),
        'contract_afc': ('contract_id', 'l10n_co_ne_afc_partner_id'),
        'contract_pension_voluntaria': ('contract_id', 'l10n_co_ne_pension_voluntaria_partner_id'),
        'contract_plan_complementario': ('contract_id', 'l10n_co_ne_plan_complementario_partner_id'),
        'contract_cooperativa': ('contract_id', 'l10n_co_ne_cooperativa_partner_id'),
        'contract_educacion': ('contract_id', 'l10n_co_ne_educacion_partner_id'),
    }

    def _ne_repartos_tercero(self, line):
        """[(partner, peso)] del tercero de una linea de nomina segun el
        origen configurado en su regla. Sin tercero resoluble: UserError."""
        origen = line.salary_rule_id.l10n_co_tercero_origen
        if origen == 'distribution':
            filas = self.env['l10n.co.payslip.tercero'].sudo().search([
                ('slip_id', '=', self.id), ('rule_code', '=', line.code)])
            filas = filas.filtered(lambda f: f.amount)
            if any(not f.partner_id for f in filas):
                raise UserError(_(
                    'La nomina "%(nomina)s" tiene un reparto de "%(regla)s" '
                    'sin contacto. Complete "Juzgado / Entidad".',
                    nomina=self.display_name, regla=line.name))
            if abs(sum(filas.mapped('amount')) - abs(line.total)) > 0.01:
                raise UserError(_(
                    'El reparto por tercero de "%(regla)s" (%(reparto).2f) no '
                    'coincide con el valor de la linea (%(linea).2f) en la '
                    'nomina "%(nomina)s". Recalcule la nomina.',
                    regla=line.name, reparto=sum(filas.mapped('amount')),
                    linea=abs(line.total), nomina=self.display_name))
            return [(f.partner_id, f.amount) for f in filas]
        if origen == 'employee_ccf':
            return [(self.employee_id._ne_caja_compensacion(), 1.0)]
        modelo, campo = self._NE_TERCERO_ORIGEN_CAMPO[origen]
        partner = self[modelo][campo]
        if not partner:
            raise UserError(_(
                'No se puede generar el asiento de la nomina "%(nomina)s": '
                'la regla "%(regla)s" paga a un tercero y falta el campo '
                '"%(campo)s" en %(donde)s "%(nombre)s".',
                nomina=self.display_name, regla=line.name,
                campo=self[modelo]._fields[campo].string,
                donde=self[modelo]._description, nombre=self[modelo].display_name))
        return [(partner, 1.0)]

    def _prepare_slip_lines(self, date, line_ids):
        new_lines = super()._prepare_slip_lines(date, line_ids)
        precision = self.company_id.currency_id.decimal_places
        procesadas = []
        for line in self.line_ids.filtered(lambda l: l.category_id):
            regla = line.salary_rule_id
            if not regla.l10n_co_tercero_origen or not line.total:
                continue
            cuenta = regla._l10n_co_cuenta_pasivo()
            if not cuenta:
                continue
            if self.company_id.batch_payroll_move_lines:
                raise UserError(_(
                    'El asiento por tercero no es compatible con el ajuste '
                    '"Agrupar líneas de asiento de nómina" (lote). '
                    'Desactívelo para generar asientos de la nomina "%s".',
                    self.display_name))
            nombre = line.name if regla.split_move_lines else regla.name
            candidatas = [
                e for e in new_lines
                if e['name'] == nombre and e['account_id'] == cuenta.id
                and id(e) not in procesadas]
            if not candidatas:
                continue  # monto neteado a cero por el nativo
            entrada = candidatas[0]
            reparto = self._ne_repartos_tercero(line)
            pesos = sum(p for _p, p in reparto)
            if not pesos:
                continue
            posicion = new_lines.index(entrada)
            nuevas = []
            acum_d = acum_c = 0.0
            for i, (partner, peso) in enumerate(reparto):
                nueva = dict(entrada, partner_id=partner.id)
                if len(reparto) == 1:
                    pass  # un solo tercero: la entrada nativa queda intacta
                elif i == len(reparto) - 1:
                    nueva['debit'] = round(entrada['debit'] - acum_d, precision)
                    nueva['credit'] = round(entrada['credit'] - acum_c, precision)
                else:
                    nueva['debit'] = round(entrada['debit'] * peso / pesos, precision)
                    nueva['credit'] = round(entrada['credit'] * peso / pesos, precision)
                acum_d += nueva['debit']
                acum_c += nueva['credit']
                nuevas.append(nueva)
                procesadas.append(id(nueva))
            new_lines[posicion:posicion + 1] = nuevas
        return new_lines

    def action_payslip_done(self):
        """
        Sobrescribe la confirmación de la nómina para asignar el consecutivo
        temporal PRE-NOM al número del payslip en Odoo.
        """
        colombia = self._ne_solo_colombia()
        colombia._ne_validar_sin_solape()
        res = super(HrPayslip, self).action_payslip_done()
        colombia._ne_aplicar_libranzas()
        colombia._ne_refrescar_ibc_mensual()
        for rec in colombia:
            company = rec.company_id
            if company.l10n_co_ne_pre_sequence_id:
                if not rec.l10n_co_ne_consecutive or rec.l10n_co_ne_consecutive.startswith('PRE-NOM'):
                    temporal_number = company.l10n_co_ne_pre_sequence_id.next_by_id()
                    rec.number = temporal_number
                    rec.l10n_co_ne_consecutive = temporal_number
        return res

    def _ne_validar_sin_solape(self):
        """Límite conocido "recibos solapados": dos recibos confirmados del mismo empleado y
        la MISMA estructura con periodos que se cruzan duplicarían días e IBC en el
        consolidado. Estructuras distintas (liquidación, prima, bonificaciones) pueden
        cruzarse con la nómina regular por diseño; notas de ajuste y notas crédito se cruzan
        con su original. Solo valida al confirmar (hacia adelante)."""
        vigentes = self.filtered(
            lambda s: not s.l10n_co_ne_is_adjustment and not s.credit_note)
        for slip in vigentes:
            otros = self.search([
                ('id', '!=', slip.id),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('struct_id', '=', slip.struct_id.id),
                ('state', 'in', ('done', 'paid')),
                ('credit_note', '=', False),
                ('l10n_co_ne_is_adjustment', '=', False),
                ('date_from', '<=', slip.date_to),
                ('date_to', '>=', slip.date_from),
            ])
            # Recibos del mismo lote que se confirman a la vez.
            otros |= (vigentes - slip).filtered(
                lambda o: o.employee_id == slip.employee_id
                and o.company_id == slip.company_id and o.struct_id == slip.struct_id
                and o.date_from <= slip.date_to and o.date_to >= slip.date_from)
            if otros:
                otro = otros[0]
                raise UserError(_(
                    'No se puede confirmar "%(slip)s" (%(desde)s a %(hasta)s): el periodo se '
                    'cruza con "%(otro)s" (%(o_desde)s a %(o_hasta)s) del mismo empleado '
                    '%(employee)s y la misma estructura, y duplicaría días e IBC. Corrija las '
                    'fechas o cancele uno de los dos recibos.',
                    slip=slip.number or slip.name, desde=slip.date_from, hasta=slip.date_to,
                    otro=otro.number or otro.name, o_desde=otro.date_from,
                    o_hasta=otro.date_to, employee=slip.employee_id.name))


    def action_send_payslip_email(self, template=None):
        """Genera el PDF del comprobante y lo envía por correo al empleado.

        Args:
            template: Plantilla de correo (mail.template). Si es omitido,
                      busca la primera plantilla disponible para el modelo hr.payslip.
        """
        self.ensure_one()
        if not self.employee_id.work_email:
            raise UserError(_('El empleado %s no tiene correo electrónico de trabajo configurado.') % self.employee_id.name)

        if not template:
            template = self.env['mail.template'].search([('model', '=', 'hr.payslip')], limit=1)
            if not template:
                raise UserError(_('No se encontró ninguna plantilla de correo configurada para el modelo de nómina.'))

        # 1. Renderizar el reporte PDF del recibo
        report = self.env.ref('l10n_co_nomina_electronica.action_report_payslip_ne', raise_if_not_found=False)
        if not report:
            report = self.env.ref('hr_payroll.action_report_payslip', raise_if_not_found=False)

        attachment_ids = []
        if report:
            pdf_content, _report_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report.id, [self.id])
            pdf_name = f"{self.number or self.name or 'Recibo_Nomina'}.pdf"
            attachment = self.env['ir.attachment'].create({
                'name': pdf_name,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'hr.payslip',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            attachment_ids.append(attachment.id)

        # 2. Enviar el correo electrónico con el PDF adjunto
        email_values = {
            'email_to': self.employee_id.work_email,
            'attachment_ids': [(6, 0, attachment_ids)] if attachment_ids else False,
        }
        template.send_mail(self.id, force_send=True, email_values=email_values)

        _logger.info(
            'Comprobante de nomina %s enviado por correo electrónico al empleado %s (%s).',
            self.number or self.name,
            self.employee_id.name,
            self.employee_id.work_email,
        )
        return True




    # ──────────────────────────────────────────────────────────────────
    # Procesamiento masivo
    # ──────────────────────────────────────────────────────────────────



    # ──────────────────────────────────────────────────────────────────
    # Integración SendTestSetAsync / GetStatusZip
    # ──────────────────────────────────────────────────────────────────







    # ══════════════════════════════════════════════════════════════════
    # MÉTODOS DE RECOPILACIÓN DE DATOS
    # ══════════════════════════════════════════════════════════════════

    def _collect_payslip_data(self):
        """
        Construye el diccionario completo de datos que ``nomina_xml_builder``
        espera para generar el XML de nómina electrónica.

        Retorna:
            dict: Estructura con todas las secciones del XML:
                - informacion_general
                - empleador
                - trabajador
                - pago
                - periodo
                - numero_secuencia
                - lugar_generacion
                - proveedor_xml
                - devengados
                - deducciones
                - totales
                - novedad (si es nota de ajuste)
        """
        self.ensure_one()
        company = self.company_id
        employee = self.employee_id
        contract = self.contract_id

        # Construir estructura de Devengados y Deducciones
        devengados, deducciones = self._map_salary_rules_to_xml()

        # Calcular totales
        total_devengados = sum(
            line.total for line in self.line_ids
            if line.salary_rule_id.l10n_co_ne_dian_concept
            and not line.salary_rule_id.l10n_co_ne_is_deduction
        )
        total_deducciones = sum(
            abs(line.total) for line in self.line_ids
            if line.salary_rule_id.l10n_co_ne_dian_concept
            and line.salary_rule_id.l10n_co_ne_is_deduction
        )

        # AUD-DIAN-34 (2026-10-04): el contenedor Odoo.sh corre en UTC --
        # datetime.now() devolvia la hora naive del servidor (UTC) con un
        # sufijo "-05:00" pegado encima sin convertir, declarando
        # FechaGen/HoraGen (y, via el mismo bug en xml_signer.py,
        # SigningTime) ~5h en el futuro respecto al instante real. La DIAN
        # rechazaba la firma (ZE02) por eso, de forma idéntica en cada
        # intento sin importar el contenido. Se calca el patrón nativo de
        # l10n_co_dian (account_edi_xml_ubl_dian.py): hora tz-aware
        # America/Bogota via pytz.
        now = datetime.now(_pytz_timezone('America/Bogota'))
        company_nit, company_dv = self._ne_company_nit_dv()

        # AUD-DIAN-34 (2026-09-14): NumeroSecuenciaXML/@Numero debe ser
        # Prefijo+Consecutivo (ej. "NE00000001"), pero @Consecutivo debe
        # ser SOLO el numero elegido por el emisor, sin el prefijo (regla
        # NIE011) -- l10n_co_ne_consecutive ya viene con el prefijo
        # incluido (lo arma ir.sequence.next_by_id()), asi que hay que
        # separarlos aqui para los 2 atributos.
        ne_prefix = (
            company.l10n_co_ne_adjust_prefix
            if self.l10n_co_ne_is_adjustment
            else company.l10n_co_ne_payroll_prefix
        ) or ''
        ne_numero = self.l10n_co_ne_consecutive or ''
        ne_consecutivo = (
            ne_numero[len(ne_prefix):]
            if ne_prefix and ne_numero.startswith(ne_prefix)
            else ne_numero
        )

        data = {
            'informacion_general': {
                # AUD-DIAN-34 (2026-09-14): NIE022 exige este literal EXACTO
                # -- no el consecutivo del documento (ese ya va en CUNE/
                # NumeroSecuenciaXML). El valor anterior ("V1.0: NumNom: ...")
                # nunca fue el literal que pide el Anexo Tecnico.
                # NIAE022 (nota de ajuste) exige el literal propio del ajuste.
                'Version': (
                    'V1.0: Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica'
                    if self.l10n_co_ne_is_adjustment
                    else 'V1.0: Documento Soporte de Pago de Nómina Electrónica'
                ),
                'Ambiente': company.l10n_co_ne_environment,
                'TipoXML': '103' if self.l10n_co_ne_is_adjustment else '102',
                'FechaGen': now.strftime('%Y-%m-%d'),
                'HoraGen': now.strftime('%H:%M:%S-05:00'),
                'PeriodoNomina': dian_utils.get_periodo_nomina(
                    self.date_from, self.date_to
                ),
                'TipoMoneda': nomina_xml_builder.NE_TIPO_MONEDA,
                'TRM': '0',
            },
            'numero_secuencia': {
                'Prefijo': ne_prefix,
                'Consecutivo': ne_consecutivo,
                'Numero': ne_numero,
                'CodigoTrabajador': str(employee.id),
            },
            'lugar_generacion': {
                'Pais': company.partner_id.country_id.code,
                'DepartamentoEstado': dian_utils.get_department_code(
                    company.partner_id.state_id
                ),
                'MunicipioCiudad': dian_utils.get_city_code(company.partner_id.city_id),
                'Idioma': nomina_xml_builder.NE_IDIOMA,
            },
            'proveedor_xml': {
                'RazonSocial': company.name or '',
                'NIT': company_nit,
                'DV': company_dv,
                'SoftwareID': company.l10n_co_ne_operation_mode_ids.software_id or '',
                'SoftwareSC': dian_utils.compute_software_security_code(
                    company.l10n_co_ne_operation_mode_ids.software_id,
                    company.l10n_co_ne_operation_mode_ids.software_pin,
                    self.l10n_co_ne_consecutive,
                ),
            },
            'empleador': {
                'RazonSocial': company.name or '',
                'NIT': company_nit,
                'DV': company_dv,
                'Pais': company.partner_id.country_id.code,
                'DepartamentoEstado': dian_utils.get_department_code(
                    company.partner_id.state_id
                ),
                'MunicipioCiudad': dian_utils.get_city_code(company.partner_id.city_id),
                'Direccion': company.partner_id.street or '',
            },

        }
        data['trabajador'] = self._ne_trabajador()
        data['pago'] = self._ne_pago()
        data['periodo'] = {
                'FechaIngreso': str(contract.date_start) if contract.date_start else '',
                'FechaRetiro': str(contract.date_end) if contract.date_end else '',
                'FechaLiquidacionInicio': str(self.date_from),
                'FechaLiquidacionFin': str(self.date_to),
                'TiempoLaborado': str(
                    dian_utils.compute_worked_time(contract.date_start, self.date_to)
                ),
                'FechaGen': now.strftime('%Y-%m-%d'),
        }
        data['fechas_pagos'] = [str(self.date_to)]
        data['devengados'] = devengados
        data['deducciones'] = deducciones
        data['totales'] = {
                'DevengadosTotal': '%.2f' % total_devengados,
                'DeduccionesTotal': '%.2f' % total_deducciones,
                'ComprobanteTotal': '%.2f' % (total_devengados - total_deducciones),
        }
        # Top-level keys for nomina_xml_builder
        data['devengados_total'] = total_devengados
        data['deducciones_total'] = total_deducciones
        data['comprobante_total'] = total_devengados - total_deducciones

        # Información de ajuste si aplica
        if self.l10n_co_ne_is_adjustment:
            data['novedad'] = {
                'CUNENov': self.l10n_co_ne_adjustment_ref_cune,
                'value': True,
            }
            if self.l10n_co_ne_adjustment_type == '2':
                data['tipo_nota'] = '2'
                data['eliminar'] = self._ne_eliminar(data)
            else:
                data['tipo_nota'] = '1'
                data['reemplazar'] = self._ne_reemplazar(data)

        return data

    def _ne_company_nit_dv(self):
        """NIT limpio (sin DV ni separadores) y su DV verificador.

        Fuente única para empleador y proveedor del XML, de modo que el
        NIT coincida siempre con el usado en el CUNE.
        """
        nit = dian_utils.clean_nit(self.company_id.vat)
        dv = dian_utils.compute_dv(nit) if self.company_id.vat else ''
        return nit, dv

    def _ne_lugar_trabajo_partner(self):
        """Único partner fuente de los 4 atributos LugarTrabajo* del nodo <Trabajador>
        (H-018, 2026-10-11, decisión de David + Tech Lead).

        Antes mezclaba orígenes: LugarTrabajoPais/LugarTrabajoDireccion salían de
        employee.work_contact_id (la ficha de contacto del empleado -- nombre/correo/
        teléfono, NO una dirección; puede no tener país ni calle) o, de respaldo, de la
        compañía; LugarTrabajoDepartamentoEstado/LugarTrabajoMunicipioCiudad salían de un
        campo propio (l10n_co_ne_dane_city_id, removido en este cambio) que, vacío, caía
        en silencio al municipio de la compañía. Resultado posible: un empleado con la
        calle de su casa y el municipio de la compañía en el mismo nodo.

        Ahora los 4 salen del MISMO partner: employee.address_id ("Dirección de Trabajo",
        campo nativo de hr.employee -- por defecto la dirección de la compañía, editable
        por empleado para un teletrabajador vía Contactos). Sin dato por defecto
        silencioso: si falta país, departamento o municipio, UserError explícito.

        Limitación de diseño conocida, documentada a propósito (Tech Lead, 2026-10-11,
        nota en el pool de deuda técnica -- NO es un olvido): esto exige departamento y
        municipio SIEMPRE, incluso si LugarTrabajoPais no es Colombia. Un trabajador real
        en el exterior (escenario que AUD-DIAN-34 protegió explícitamente: el Anexo
        Técnico admite cualquier código alfa-2 en LugarTrabajoPais, NIE050) necesitaría un
        res.country.state/res.city cargado para ese país, que puede no existir en la base.
        Decisión explícita: se deja estricto así -- Guapante no tiene hoy ningún
        trabajador en el exterior. Si eso cambia, revisar esta función antes de dar por
        hecho que un trabajador en el exterior puede generar nómina.
        """
        self.ensure_one()
        employee = self.employee_id
        partner = employee.address_id
        faltantes = []
        if not partner.country_id:
            faltantes.append(_('país'))
        if not partner.state_id:
            faltantes.append(_('departamento'))
        if not partner.city_id:
            faltantes.append(_('municipio'))
        if faltantes:
            raise UserError(_(
                'La Dirección de Trabajo de %(employee)s no tiene %(campos)s '
                'configurado(s) (ficha del empleado, campo "Dirección de Trabajo", o el '
                'contacto que apunte -- en Contactos). Complete esos datos antes de '
                'generar la nómina electrónica: los 4 atributos LugarTrabajo* del XML '
                'deben salir del mismo lugar, nunca de un valor inventado.',
                employee=employee.name, campos=', '.join(faltantes),
            ))
        return partner

    def _ne_tipo_documento(self):
        """Código DIAN (TipoDocumento del nodo <Trabajador>) del tipo de identificación
        del empleado (UX-02, 2026-10-11, decisión de David + Tech Lead).

        Antes era un Selection propio en hr.employee, duplicando el tipo de
        identificación que Contactos ya guarda en work_contact_id.l10n_latam_
        identification_type_id (el mismo partner que exige el dominio nativo de
        bank_account_id). Ahora sale de ahí, vía l10n_latam.identification.type.
        l10n_co_ne_dian_document_code (dato del módulo, data/l10n_latam_identification_
        type_dian_code_data.xml). Sin tipo configurado, o con un tipo sin equivalente
        DIAN (ej. los genéricos "Cédula Extranjera"/"VAT" de otros países LATAM, que
        deliberadamente no tienen registro en esos datos): UserError que nombra al
        empleado, nunca un '13' inventado como hacía el default silencioso anterior.
        """
        self.ensure_one()
        employee = self.employee_id
        tipo = employee.work_contact_id.l10n_latam_identification_type_id
        codigo = tipo.l10n_co_ne_dian_document_code
        if not codigo:
            raise UserError(_(
                'El empleado %(employee)s no tiene un Tipo de Documento con '
                'equivalente DIAN configurado (Información privada > Tipo de '
                'Documento). Complete ese dato antes de generar la nómina '
                'electrónica.',
                employee=employee.name,
            ))
        return codigo

    # Salario neto / bruto (2026-11-09, hallazgo de QA, decisión de Tech Lead): net_wage y
    # gross_wage nativos suman líneas con código 'NET'/'GROSS', creadas por las reglas que Odoo
    # agrega por defecto a cada estructura con fórmulas sobre sus categorías nativas
    # (BASIC/ALW/DED), a las que nuestras categorías (DEV, DEDU, ...) nunca se enlazaron: el neto
    # nativo quedaba igual al básico. NO se enlazan las categorías (doble conteo del básico, y
    # DEV_SAL es la base del IBC/PILA/UGPP); se corrige el cálculo del campo nativo.
    # Cada estructura propia tiene su regla de neto; solo la general tiene "Total Devengados".
    _NE_NETO_CODES = ('CO_NETO', 'CO_PRIMA_NETO', 'CO_LIQ_NETO', 'CO_BON_NETO')
    _NE_BRUTO_CODES = ('CO_BRUTO',)
    # Lineas que Odoo agrega por defecto a cada estructura (BASIC/GROSS/NET); no son conceptos
    # del recibo y su valor es el de las categorias nativas, no el neto real.
    _NE_NATIVOS_SIN_PDF = ('BASIC', 'GROSS', 'NET')

    def _ne_pdf_lineas(self):
        """Lineas que se imprimen como conceptos en el PDF del recibo: las que aparecen en el
        recibo, sin las nativas BASIC/GROSS/NET ni las filas de total (bruto y neto de cada
        estructura propia), que no son conceptos y sumarlas duplica el neto."""
        self.ensure_one()
        excluir = (set(self._NE_NATIVOS_SIN_PDF) | set(self._NE_NETO_CODES)
                   | set(self._NE_BRUTO_CODES))
        return self.line_ids.filtered(
            lambda l: l.appears_on_payslip and l.code not in excluir)

    def _ne_pdf_neto(self):
        """NETO A PAGAR del PDF: el total de la linea de neto de la estructura del recibo
        (CO_NETO, CO_PRIMA_NETO, CO_LIQ_NETO o CO_BON_NETO) -- la misma fuente de net_wage
        (_compute_basic_net). Sin esa linea no hay neto confiable: error, nunca un valor por
        defecto."""
        self.ensure_one()
        neto = self.line_ids.filtered(lambda l: l.code in self._NE_NETO_CODES)
        if not neto:
            raise UserError(_(
                'El recibo "%(recibo)s" no tiene línea de neto: calcule la nómina '
                '(botón Calcular) antes de imprimirla.', recibo=self.display_name))
        return sum(neto.mapped('total'))


    @api.depends('line_ids.total')
    def _compute_basic_net(self):
        super()._compute_basic_net()
        for payslip in self:
            neto = payslip.line_ids.filtered(lambda l: l.code in self._NE_NETO_CODES)
            if neto:
                payslip.net_wage = sum(neto.mapped('total'))
            bruto = payslip.line_ids.filtered(lambda l: l.code in self._NE_BRUTO_CODES)
            if bruto:
                payslip.gross_wage = sum(bruto.mapped('total'))

    # H-005 (2026-11-09): parámetro hr.rule.parameter de la tarifa ARL por Clase de Riesgo del
    # contrato (l10n_co_pila_clase_riesgo). Los CÓDIGOS de parámetro viven aquí; los
    # porcentajes, en data/l10n_co_rule_parameters_data.xml (cero hardcoded normativo).
    _NE_ARL_PARAMETRO_POR_CLASE = {
        '1': 'l10n_co_pct_arl_default',
        '2': 'l10n_co_pct_arl_clase_2',
        '3': 'l10n_co_pct_arl_clase_3',
        '4': 'l10n_co_pct_arl_clase_4',
        '5': 'l10n_co_pct_arl_clase_5',
    }

    def _ne_pct_arl(self):
        """Porcentaje (p. ej. 1.044) de la tarifa ARL del empleador según la Clase de Riesgo
        ARL del contrato (H-005). Única fuente para CO_ARL_CIA y para PILA, de modo que no
        puedan divergir. Sin clase en el contrato: UserError que nombra al empleado (nunca se
        asume la Clase I en silencio)."""
        self.ensure_one()
        contract = self.contract_id
        clase = contract._ne_clase_riesgo()
        codigo = self._NE_ARL_PARAMETRO_POR_CLASE.get(clase)
        if not codigo:
            raise UserError(_(
                'El contrato de %(employee)s no tiene Clase de Riesgo ARL configurada '
                '(pestaña de PILA del contrato). Complétela antes de calcular el aporte a ARL.',
                employee=self.employee_id.name,
            ))
        return self._rule_parameter(codigo, self._ne_fecha_parametros())


    def _ne_validar_cuenta_transferencia(self):
        """H-021 (2026-11-09): única validación de "Transferencia exige cuenta bancaria".

        Antes era un @api.constrains en hr.employee que corría en cada guardado y le impedía
        guardar un empleado nuevo (el método por defecto es Transferencia). La cuenta solo
        hace falta para armar <Pago>, así que se exige aquí, donde se usa. La llaman
        _ne_pago() y _validate_ne_prerequisites() (esta última, antes de asignar el
        consecutivo, para no gastar uno en un documento que no se puede armar)."""
        self.ensure_one()
        employee = self.employee_id
        metodo = employee._ne_medio_pago()
        if metodo == '1' and not employee.bank_account_id:
            raise UserError(_(
                'El empleado %(employee)s no tiene una Cuenta Bancaria configurada '
                '(Información privada > Contacto privado) y el método de pago es '
                'Transferencia Bancaria. Configure la cuenta o cambie el método de '
                'pago antes de generar la nómina electrónica.',
                employee=employee.name,
            ))

    def _ne_pago(self):
        """Sección <Pago> del XML de nómina electrónica (UX-02, 2026-10-11, decisión de
        David + Tech Lead).

        Antes Banco/TipoCuenta/NumeroCuenta salían de 3 campos propios
        (l10n_co_ne_bank_name/bank_account_type/bank_account), duplicando la cuenta
        bancaria nativa del empleado (employee.bank_account_id, res.partner.bank, ya
        visible en "Información privada" > grupo "Contacto privado"). Ahora Banco =
        bank_account_id.bank_id.name, NumeroCuenta = bank_account_id.acc_number.

        TipoCuenta (Ahorro/Corriente) se OMITE a propósito: no existe ningún campo
        nativo de community ni de l10n_co que represente ese concepto -- acc_type
        nativo (account/base_iban) es una clasificación de FORMATO del número de
        cuenta ('bank'/'iban', para decidir si validar con el algoritmo IBAN), no
        tiene nada que ver con Ahorros/Corriente. l10n_co_account_type sí existe,
        pero viene de l10n_co_bank_payment_export (módulo propio de InSoTech, fuera
        de este repo) -- David decidió no depender de él ni crear un campo propio
        para esto. Tech Lead verificó en el Anexo Técnico (NIE067) que la regla de
        TipoCuenta es de tipo "N" (notificación), no "R" (rechazo): omitirlo no
        rechaza el documento, puede generar una notificación de la DIAN -- QA debe
        confirmar en staging si llega alguna. El XML builder (nomina_xml_builder.py)
        ya trata Banco/TipoCuenta/NumeroCuenta como opcionales (omite la llave si no
        hay valor), consistente con el XSD V1.0.6 (Forma/Metodo obligatorios).

        Metodo (l10n_co_ne_payment_method) se queda como el único campo propio de
        esta sección -- sin equivalente nativo verificado (no hay nada en
        account.payment.method que mapee a los 3 códigos DIAN 1/2/10 de nómina).

        Si el método es transferencia (código '1') y no hay bank_account_id:
        UserError explícito, nunca un Banco/NumeroCuenta vacíos enviados a la DIAN.
        """
        self.ensure_one()
        employee = self.employee_id
        metodo = employee._ne_medio_pago()
        cuenta = employee.bank_account_id
        self._ne_validar_cuenta_transferencia()
        return {
            'Forma': '1',  # 1=Contado
            'Metodo': metodo,
            'Banco': (cuenta.bank_id.name or '') if cuenta else '',
            'NumeroCuenta': (cuenta.acc_number or '') if cuenta else '',
        }

    def _ne_trabajador(self):
        """Sección <Trabajador> del XML de nómina electrónica."""
        employee = self.employee_id
        contract = self.contract_id
        _name_parts = employee._l10n_co_nombre_dian()
        lugar_trabajo = self._ne_lugar_trabajo_partner()
        return {
            'TipoTrabajador': employee._ne_valor_obligatorio('l10n_co_ne_worker_type'),
            'SubTipoTrabajador': employee._ne_valor_obligatorio('l10n_co_ne_worker_subtype'),
            'AltoRiesgoPension': (
                'true' if employee.l10n_co_ne_high_risk_pension else 'false'
            ),
            'TipoDocumento': self._ne_tipo_documento(),
            'NumeroDocumento': employee.identification_id or '',
            'PrimerApellido': _name_parts.get('primer_apellido', ''),
            'SegundoApellido': _name_parts.get('segundo_apellido', ''),
            'PrimerNombre': _name_parts.get('primer_nombre', ''),
            'OtrosNombres': _name_parts.get('otros_nombres', ''),
            # AUD-DIAN-34 (2026-10-05): a diferencia de Idioma/TipoMoneda, el Anexo Técnico
            # NO fija LugarTrabajoPais a Colombia (NIE050: admite cualquier código alfa-2,
            # "país actual donde se encontraba ubicado el trabajador"). H-018 (2026-10-11):
            # los 4 atributos LugarTrabajo* salen del mismo partner -- ver
            # _ne_lugar_trabajo_partner().
            'LugarTrabajoPais': lugar_trabajo.country_id.code,
            'LugarTrabajoDepartamentoEstado': dian_utils.get_department_code(
                lugar_trabajo.state_id),
            'LugarTrabajoMunicipioCiudad': dian_utils.get_city_code(lugar_trabajo.city_id),
            'LugarTrabajoDireccion': lugar_trabajo.street or '',

            'SalarioIntegral': (
                'true' if contract.l10n_co_ne_integral_salary else 'false'
            ),
            'TipoContrato': contract._ne_valor_obligatorio('l10n_co_ne_contract_type'),
            'Sueldo': '%.2f' % contract.wage,
            'CodigoTrabajador': str(employee.id),
        }







    def _map_salary_rules_to_xml(self):
        """
        Mapea las líneas de la nómina (hr.payslip.line) a la estructura
        de Devengados y Deducciones del XML de nómina electrónica.

        Agrupa las líneas según su ``l10n_co_ne_dian_concept`` y construye
        los diccionarios correspondientes para el XML builder.

        Retorna:
            tuple: (devengados_dict, deducciones_dict) listos para el
                   nomina_xml_builder.
        """
        self.ensure_one()
        concept_lines = self._group_lines_by_concept()
        devengados = self._build_devengados(concept_lines)
        deducciones = self._build_deducciones(concept_lines)
        return devengados, deducciones

    def _group_lines_by_concept(self):
        """Agrupa las líneas de nómina por concepto DIAN (omite total=0)."""
        concept_lines = defaultdict(list)
        for line in self.line_ids:
            concept = line.salary_rule_id.l10n_co_ne_dian_concept
            if concept and line.total != 0:
                concept_lines[concept].append(line)
        return concept_lines

    def _build_devengados(self, concept_lines):
        """Construye el dict <Devengados> del XML a partir de concept_lines."""
        devengados = {}
        self._dev_basico_y_transporte(concept_lines, devengados)
        self._dev_horas_extra(concept_lines, devengados)
        self._dev_prestaciones(concept_lines, devengados)
        self._dev_novedades(concept_lines, devengados)
        self._dev_complementarios(concept_lines, devengados)
        self._dev_bonos_y_pagos(concept_lines, devengados)
        return devengados

    @staticmethod
    def _ne_dias_en_mes_calendario(year, month):
        """Días reales de un mes calendario -- compartido por toda la aritmética de "mes
        comercial" de 30 días (_ne_dia_comercial, _ne_dias_corridos_en_tramo).

        Tech Lead (2026-10-08, revisión .77): usa calendar.monthrange() en vez de un
        cálculo manual de año bisiesto -- misma regla gregoriana, sin reimplementarla."""
        return calendar.monthrange(year, month)[1]

    def _ne_dia_comercial(self, d, dias_mes):
        """Mapea un día calendario real a su "día comercial" (convención colombiana de mes
        de 30 días): el último día calendario REAL de cualquier mes (28/29-feb, 30 o 31)
        siempre equivale al día comercial 30 -- no solo cuando el mes tiene exactamente 30
        días. Compartido por _ne_dias_pagables() y _ne_dias_corridos_en_tramo() (H-014)."""
        ultimo_dia_mes = self._ne_dias_en_mes_calendario(d.year, d.month)
        if d.day == ultimo_dia_mes:
            return dias_mes
        return min(d.day, dias_mes)

    def _ne_dias_prestacion(self, fecha_ini, fecha_fin):
        """Dias de [fecha_ini, fecha_fin] (extremos incluidos) para prima, cesantias, intereses,
        indemnizacion y vacaciones causadas de la liquidacion. El divisor del anio sigue siendo
        360 (hr.rule.parameter l10n_co_dias_anio_comercial); aqui solo se cuentan los dias.

        El tratamiento de febrero es un parametro de la compania (Ajustes > Nomina,
        l10n_co_ne_febrero_modo), sin valor por defecto:
        - 'real' (decision de David, Guapante): los dias reales que se tienen, ni mas ni menos:
          febrero cuenta 28 (29 si es bisiesto), completo o parcial; el dia 31 de los meses de
          31 dias no cuenta (se "regala"). Un semestre ene-jun = 178, jul-dic = 180, un anio = 358
          (359 si es bisiesto).
        - '30': mes comercial de 30 dias (el ultimo dia real de cada mes cuenta como 30; febrero
          completo = 30; un semestre = 180, un anio = 360), con _ne_dia_comercial.
        NO afecta al sueldo mensual ni a los dias de PILA (_ne_dias_bajo_contrato): ahi febrero
        sigue siendo 30. 0 si el rango esta invertido. Sin el parametro: UserError."""
        self.ensure_one()
        modo = self.company_id.l10n_co_ne_febrero_modo
        if not modo:
            raise UserError(_(
                'La empresa %(company)s no tiene configurado el tratamiento de febrero en las '
                'prestaciones (Nómina > Configuración > Ajustes, bloque Parámetros Nómina '
                'Colombia, "Febrero en prestaciones"). Se necesita para calcular la nómina '
                '"%(nomina)s".', company=self.company_id.name, nomina=self.display_name))
        if fecha_fin < fecha_ini:
            return 0
        if modo == 'real':
            dias = (fecha_fin - fecha_ini).days + 1
            anio, mes = fecha_ini.year, fecha_ini.month
            while (anio, mes) <= (fecha_fin.year, fecha_fin.month):
                if self._ne_dias_en_mes_calendario(anio, mes) == 31 \
                        and fecha_ini <= fecha_fin.replace(year=anio, month=mes, day=31) <= fecha_fin:
                    dias -= 1
                mes += 1
                if mes == 13:
                    anio, mes = anio + 1, 1
            return dias
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        meses = (fecha_fin.year - fecha_ini.year) * 12 + (fecha_fin.month - fecha_ini.month)
        return (meses * dias_mes + self._ne_dia_comercial(fecha_fin, dias_mes)
                - self._ne_dia_comercial(fecha_ini, dias_mes) + 1)

    def _ne_retefuente_config(self):
        """Configuracion de retencion en la fuente (l10n.co.retefuente.uvt) del anio de la
        nomina (anio de _ne_fecha_parametros: la fecha de retiro en la liquidacion). Primero la de
        la compania del recibo; si no hay, la del anio sin compania propia (mismo criterio de
        siempre). Sin configuracion: UserError que nombra anio y compania -- antes las reglas
        de retencion se omitian en silencio y la nomina salia sin retencion (.167)."""
        self.ensure_one()
        anio = str(self._ne_fecha_parametros().year)
        config = self.env['l10n.co.retefuente.uvt']._ne_config_del_anio(anio, self.company_id)
        if not config:
            raise UserError(_(
                'No hay configuración de retención en la fuente para el año %(anio)s de la '
                'empresa %(company)s (Nómina > Configuración > Nómina Colombia > Retención en la '
                'Fuente). Cárguela antes de calcular la nómina "%(nomina)s": sin ella no se '
                'puede calcular la retención.',
                anio=anio, company=self.company_id.name, nomina=self.display_name))
        return config

    def _ne_fecha_parametros(self):
        """Fecha con la que se resuelven los hr.rule.parameter (SMMLV, auxilio, topes, divisores).

        Liquidacion: la fecha de retiro (date_to). En ella date_from es contract.date_start, que
        puede ser de anos atras y traeria el SMMLV/auxilio del ingreso (o ningun valor, si es
        anterior al primer parametro cargado). Es tambien el criterio del nativo
        (hr.payslip._rule_parameter sin fecha usa date_to). Demas estructuras: date_from, igual
        que antes -- no se altera la nomina mensual (p. ej. el cambio de jornada del 15-jul-2026
        cae dentro de un mismo recibo mensual)."""
        self.ensure_one()
        if self.struct_id == self.env.ref(
                'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion',
                raise_if_not_found=False):
            return self.date_to
        return self.date_from

    def _ne_validar_inicio_liquidacion(self):
        """En la estructura de liquidacion el recibo va de inicio de contrato a retiro.

        Las reglas que dependen del tramo contractual (vacaciones causadas y tomadas, tramo
        pagable) asumen date_from = contract.date_start. Con otra fecha las vacaciones de meses
        anteriores no se descuentan y el valor sale inflado SIN aviso (QA, recibo 12954).
        No se corrige en silencio: se detiene con un error que dice que corregir."""
        self.ensure_one()
        if self.struct_id != self.env.ref(
                'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion',
                raise_if_not_found=False):
            return
        inicio = self.contract_id.date_start
        desde = self.date_from
        if hasattr(desde, 'date'):
            desde = desde.date()
        if inicio and desde != inicio:
            raise UserError(_(
                "El recibo de liquidación '%(recibo)s' (empleado %(empleado)s) debe iniciar en "
                "la fecha de inicio del contrato (%(esperada)s) y tiene %(actual)s. Con otra "
                "fecha las vacaciones y demás conceptos de los meses anteriores no se descuentan "
                "y el valor sale errado. Corrija el campo \"Desde\" del recibo a %(esperada)s "
                "(o genere la liquidación con el asistente de liquidación del contrato); si "
                "cambia la fecha, revise que la fecha \"Hasta\" siga siendo la de retiro.",
                recibo=self.name or self.display_name, empleado=self.employee_id.display_name,
                esperada=inicio, actual=desde))

    def _ne_liq_vacaciones_dias(self):
        """Dias de vacaciones causadas, ya tomadas y pendientes del contrato al retiro.

        Causadas: dias de prestacion (_ne_dias_prestacion) de inicio de contrato a date_to x dias_mes / divisor_vacaciones (15 dias
        habiles por 360 de servicio, Art. 186 CST; con los parametros 30 y 720 = dias / 24).
        Ya tomadas, de las mismas fuentes que paga la nomina mensual (una sola fuente):
        - disfrutadas: hr.leave validadas CO_VAC en dias HABILES del calendario del contrato
          (_ne_ausencia_habil; el recibo de liquidacion va de inicio de contrato a retiro) y
          dias del input CO_VAC en recibos confirmados del mismo contrato (respaldo manual;
          nunca coexiste con una ausencia en un mismo recibo, ver _ne_resolver_dias_novedad);
        - compensadas en dinero: lineas CO_VAC_COMP (monto) de recibos confirmados, a
          valor-dia salario/dias_mes.
        Pendientes = max(0, causadas - disfrutadas - compensadas): quien tomo mas de lo causado
        no genera valor negativo. Solo ve lo registrado en el sistema."""
        self.ensure_one()
        self._ne_validar_inicio_liquidacion()
        contract = self.contract_id
        fecha = self._ne_fecha_parametros()
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', fecha)
        divisor = self._rule_parameter('l10n_co_divisor_vacaciones', fecha)
        dias_servicio = self._ne_dias_prestacion(contract.date_start, self.date_to)
        causados = dias_servicio * dias_mes / divisor

        disfrutados, _detalle = self._ne_ausencia_habil('CO_VAC')
        compensado_dinero = 0.0
        previos = self.env['hr.payslip'].search([
            ('contract_id', '=', contract.id),
            ('id', '!=', self.id),
            ('state', 'in', ('done', 'paid')),
            ('struct_id', '!=', self.struct_id.id),
            ('credit_note', '=', False),
            ('l10n_co_ne_is_adjustment', '=', False),
        ])
        for previo in previos:
            disfrutados += sum(
                previo.input_line_ids.filtered(lambda i: i.code == 'CO_VAC').mapped('amount'))
            compensado_dinero += sum(
                previo.line_ids.filtered(lambda l: l.code == 'CO_VAC_COMP').mapped('total'))
        valor_dia = contract.wage / dias_mes
        compensados = compensado_dinero / valor_dia if valor_dia else 0.0
        pendientes = max(0.0, causados - disfrutados - compensados)
        return {
            'causados': causados, 'disfrutados': disfrutados,
            'compensados': compensados, 'pendientes': pendientes,
            'valor_dia': valor_dia,
        }

    def _ne_tramo_pagable_periodo(self):
        """(periodo_ini, periodo_fin) -- el tramo del período de la nómina que realmente es
        pagable bajo la convención de mes comercial de 30 días.

        H-009 (2026-10-06, QA Bloque 2): en Liquidación, date_from es contract.date_start y
        date_to la fecha de retiro -- un período que puede abarcar meses o años. Cuando el
        período cruza más de un mes calendario, el tramo pagable se restringe al mes
        calendario de date_to (los meses anteriores ya se pagaron en nóminas regulares);
        dentro de un mismo mes (el caso normal mensual) el resultado es el período completo
        tal cual. Compartido por _ne_dias_pagables() y _ne_ausencia_calendario() (H-014) --
        ambos deben recortar al mismo tramo para no descontar/pagar fuera de él.
        """
        self._ne_validar_inicio_liquidacion()
        periodo_ini = self.date_from
        periodo_fin = self.date_to
        if (periodo_fin.year, periodo_fin.month) != (periodo_ini.year, periodo_ini.month):
            periodo_ini = max(periodo_ini, periodo_fin.replace(day=1))
        return periodo_ini, periodo_fin

    def _ne_dias_corridos_en_tramo(self, fecha_ini, fecha_fin, tramo_ini, tramo_fin, dias_mes):
        """Días CALENDARIO corridos (lunes a domingo) de [fecha_ini, fecha_fin] que caen
        dentro de [tramo_ini, tramo_fin], bajo la convención de mes comercial de 30 días
        (_ne_dia_comercial) -- 0 si no hay solapamiento. Usada por _ne_ausencia_calendario()
        para los 4 conceptos de "días corridos" (H-014)."""
        ini = max(fecha_ini, tramo_ini)
        fin = min(fecha_fin, tramo_fin)
        if ini > fin:
            return 0
        return self._ne_dia_comercial(fin, dias_mes) - self._ne_dia_comercial(ini, dias_mes) + 1

    def _ne_dias_bajo_contrato(self):
        """Dias (mes comercial) del tramo pagable en que el contrato estuvo vigente.
        Delimita ING/RET: la fecha de ingreso y de retiro recortan el rango."""
        self.ensure_one()
        contract = self.contract_id
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        periodo_ini, periodo_fin = self._ne_tramo_pagable_periodo()
        contrato_ini = contract.date_start
        contrato_fin = contract.date_end or periodo_fin
        activo_ini = max(periodo_ini, contrato_ini)
        activo_fin = min(periodo_fin, contrato_fin)
        if activo_ini > activo_fin:
            return 0
        return (self._ne_dia_comercial(activo_fin, dias_mes)
                - self._ne_dia_comercial(activo_ini, dias_mes) + 1)

    def _ne_dias_pagables(self):
        """Días pagables del período -- misma convención de "mes comercial" colombiano que ya
        usa la regla salarial CO_BASICO (hr_salary_rule_co_basico, data/hr_payroll_structure_
        data.xml) y CO_AUX_TRANS para calcular el sueldo/auxilio. Única fuente para el sueldo
        Y para DiasTrabajados, sin importar si la estructura es mensual o de liquidación.

        AUD-DIAN-34 (2026-10-05, Ronda 1 DIAN): hallazgo real -- un básico de mes completo
        generaba DiasTrabajados="19" (conteo de líneas WORK100, calendario lun-vie) junto a
        SueldoTrabajado del mes completo (30 días comerciales): dos fuentes de días distintas
        para el mismo devengado. El Anexo Técnico (NIE069/NIE070) define SueldoTrabajado como
        "el Sueldo Trabajado por los días laborados" -- ambos deben contar exactamente lo
        mismo. Esta función es esa única fuente; CO_BASICO/CO_AUX_TRANS la llaman en vez de
        recalcular.
        """
        self.ensure_one()
        dias_bajo_contrato = self._ne_dias_bajo_contrato()

        unpaid_types = self.env['hr.leave.type'].search([('unpaid', '=', True)])
        unpaid_codes = set(unpaid_types.mapped('work_entry_type_id.code')) - {False}
        # H-013 (2026-10-08, QA Bloque 4): vacaciones/licencias/incapacidades entraban como
        # novedades manuales (inputs CO_VAC/CO_LIC_REM/CO_LIC_NR/CO_INC_COMUN/CO_INC_LABORAL)
        # y el básico no descontaba esos días -- doble pago real (vacaciones 15 días: básico
        # de 30 días completo + vacaciones aparte). "unpaid" en Odoo no sirve para detectar
        # esto: significa "sin continuidad de pago del empleador", mientras que vacaciones/
        # incapacidad/licencia remunerada SÍ se pagan en Colombia, solo que por un concepto
        # distinto al básico (Art. 186 CST, Ley 100/1993, etc.). Por eso se excluyen SIEMPRE
        # estos códigos (data/l10n_co_ausencias_data.xml), sin importar su unpaid real.
        dias_excluidos_codes = unpaid_codes | _NOVEDAD_AUSENCIA_WORKED_DAYS_CODES
        dias_excluidos = self._ne_dias_habiles_excluidos(dias_excluidos_codes)
        # H-014 (2026-10-08, QA Bloque 5): CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL
        # se pagan en días CALENDARIO corridos (ver _ne_ausencia_calendario) -- se excluyen
        # del básico por la misma cuenta, nunca por worked_days (ahí solo existirían los
        # días que el calendario del contrato ya define como laborables, subcontando un
        # festivo o un día no laboral dentro de la ausencia).
        for codigo in _NOVEDAD_AUSENCIA_CALENDARIO_CODES:
            dias_excluidos += self._ne_ausencia_calendario(codigo)[0]
        return dias_bajo_contrato - dias_excluidos

    def _ne_pago_ausencia_calendario(self, codigo, dias, previos=None):
        """Valor a pagar por `dias` calendario corridos de una ausencia de pago por el empleador
        o por terceros: CO_INC_COMUN, CO_INC_LABORAL, CO_LIC_MAT, CO_LIC_PAT. Unico lugar del
        calculo, compartido por las reglas de la nomina general y de la liquidacion.

        - CO_INC_COMUN (Decreto 780/2016 Art. 3.2.1.10 par. 1; H-013 paso 3): por tramos --
          los primeros dias_incapacidad_empleador al pct_incapacidad_empleador (66,67 %); hasta
          el limite 3-90 el pct_incapacidad_3_90 (EPS); mas alla el pct_incapacidad_91_mas.
        - CO_INC_LABORAL: ARL al 100 % desde el primer dia. CO_LIC_MAT y CO_LIC_PAT: 100 % del
          salario, a cargo de la EPS (H-014, CST Art. 236 mod. Ley 2114/2021).
        Parametros normativos desde hr.rule.parameter a la fecha de _ne_fecha_parametros().
        CO_INC_COMUN tiene piso de 1 SMMLV por dia (H-163, CST Art. 227): ver abajo. Su tramo se
        cuenta desde el INICIO de la incapacidad y sus prorrogas (H-170): `previos` = dias de la
        misma incapacidad anteriores al periodo; sin darlo, se deduce de Ausencias."""
        self.ensure_one()
        if codigo not in _NOVEDAD_AUSENCIA_CALENDARIO_CODES:
            raise UserError(_(
                'Código de ausencia "%(codigo)s" sin fórmula de pago (solo %(validos)s).',
                codigo=codigo, validos=', '.join(sorted(_NOVEDAD_AUSENCIA_CALENDARIO_CODES))))
        if dias <= 0:
            return 0.0
        fecha = self._ne_fecha_parametros()
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', fecha)
        valor_dia = self.contract_id.wage / dias_mes
        if codigo != 'CO_INC_COMUN':
            return valor_dia * dias
        dias_emp = self._rule_parameter('l10n_co_dias_incapacidad_empleador', fecha)
        pct_emp = self._rule_parameter('l10n_co_pct_incapacidad_empleador', fecha) / 100
        pct_3_90 = self._rule_parameter('l10n_co_pct_incapacidad_3_90', fecha) / 100
        pct_91_mas = self._rule_parameter('l10n_co_pct_incapacidad_91_mas', fecha) / 100
        limite_3_90 = self._rule_parameter('l10n_co_dias_incapacidad_limite_3_90', fecha)
        # H-163 (CST art. 227; T-468/2010): los porcentajes aplican "siempre y cuando el valor
        # liquido a pagar no sea inferior al SMMLV": valor por dia = max(valor_dia x pct del
        # tramo, SMMLV / dias_mes), en todos los tramos. Con salario de 1 SMMLV se paga el 100 %.
        # LIMITE CONOCIDO: con salario MENOR a 1 SMMLV (jornada parcial) el piso diario pagaria mas
        # del 100 % de su sueldo; no ocurre en Guapante y no se modela (decision pendiente).
        smmlv_dia = self._rule_parameter('l10n_co_smmlv', fecha) / dias_mes

        def _por_dia(pct):
            return max(valor_dia * pct, smmlv_dia)

        def _pago_posiciones(previos, cantidad):
            """Pago de los dias que ocupan las posiciones previos+1 .. previos+cantidad DENTRO de
            la incapacidad (H-170): el tramo se cuenta desde su inicio, no desde el recibo."""
            ini, fin = previos, previos + cantidad

            def _solape(a, b):
                return max(0, min(fin, b) - max(ini, a))
            return (_solape(0, dias_emp) * _por_dia(pct_emp)
                    + _solape(dias_emp, limite_3_90) * _por_dia(pct_3_90)
                    + max(0, fin - max(ini, limite_3_90)) * _por_dia(pct_91_mas))

        if previos is not None:
            return _pago_posiciones(previos, dias)
        cadenas = self._ne_incapacidad_cadenas()
        if not cadenas or sum(en_periodo for _previos, en_periodo in cadenas) != dias:
            # Sin ausencias que lo respalden (p. ej. input manual): la incapacidad empieza aqui.
            cadenas = [(0, dias)]
        return sum(_pago_posiciones(prev, en_periodo) for prev, en_periodo in cadenas)

    def _ne_incapacidad_cadenas(self):
        """[(dias_previos, dias_en_periodo)] de cada incapacidad comun -- con sus prorrogas -- que
        cae en el periodo del recibo (H-170). Las incapacidades validadas del empleado se encadenan
        cuando la siguiente empieza a mas tardar l10n_co_dias_interrupcion_prorroga + 1 dias despues
        del fin de la anterior (con 0, solo contiguas). dias_previos = dias CALENDARIO reales de
        la cadena anteriores al inicio del tramo del recibo: ocupan las posiciones 1..previos, y los
        del recibo las siguientes (el dia 93 de una incapacidad es el 1-jun si empezo el 1-mar)."""
        self.ensure_one()
        _dias, detalle = self._ne_ausencia_calendario('CO_INC_COMUN')
        if not detalle:
            return []
        interrupcion = int(self._rule_parameter(
            'l10n_co_dias_interrupcion_prorroga', self._ne_fecha_parametros()))
        periodo_ini = self._ne_tramo_pagable_periodo()[0]
        tramo_ini = max(periodo_ini, self.contract_id.date_start)
        todas = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('holiday_status_id.work_entry_type_id.code', '=', 'CO_INC_COMUN'),
        ], order='request_date_from, id')
        cadenas, actual = [], []
        for leave in todas:
            if actual and leave.request_date_from <= actual[-1].request_date_to + timedelta(
                    days=1 + interrupcion):
                actual.append(leave)
            else:
                if actual:
                    cadenas.append(actual)
                actual = [leave]
        if actual:
            cadenas.append(actual)
        en_periodo = {leave.id: dias for leave, dias, _ini, _fin in detalle}
        resultado = []
        for cadena in cadenas:
            dias_periodo = sum(en_periodo.get(leave.id, 0) for leave in cadena)
            if not dias_periodo:
                continue
            previos = 0
            for leave in cadena:
                fin = min(leave.request_date_to, tramo_ini - timedelta(days=1))
                if fin >= leave.request_date_from:
                    previos += (fin - leave.request_date_from).days + 1
            resultado.append((previos, dias_periodo))
        return resultado

    def _ne_ausencia_calendario(self, work_entry_code):
        """Única fuente de días CALENDARIO corridos (lunes a domingo, festivos incluidos)
        para un concepto de ausencia -- CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL
        (H-014, 2026-10-08, decisión de David: CST Art. 186/227/236 mod. Ley 2114/2021,
        Concepto Mintrabajo 63044901/2022). A diferencia de CO_VAC/CO_LIC_REM/CO_LIC_NR
        (H-013, días HÁBILES vía worked_days), estos 4 no pueden contarse desde worked_days:
        los work entries solo existen en los días que el calendario del contrato define
        como laborables (confirmado contra hr_work_entry_contract.
        _get_contract_work_entries_values -- un día sin asistencia en ese calendario, ej.
        el lunes en un calendario martes-a-domingo, nunca genera NINGÚN work entry, sea
        cual sea el tipo de ausencia).

        Recorta cada hr.leave validada al mismo tramo pagable del período
        (_ne_tramo_pagable_periodo(), la misma restricción de mes comercial de 30 días que
        usa _ne_dias_pagables() para Liquidación) y a la actividad del contrato.

        Devuelve (dias_totales, detalle) -- dias_totales es la única fuente para la regla
        de pago (_ne_dias_novedad_calendario()) Y para la exclusión del básico
        (_ne_dias_pagables()); detalle es [(leave, dias, fecha_ini_recortada,
        fecha_fin_recortada)] para quien necesite el desglose por ausencia
        (_dev_novedades(), y el futuro corte de incapacidad en el día 90 del paso 3 de
        H-013, que puede reusar esto mismo con las fechas ya recortadas).
        """
        self.ensure_one()
        contract = self.contract_id
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        periodo_ini, periodo_fin = self._ne_tramo_pagable_periodo()
        contrato_ini = contract.date_start
        contrato_fin = contract.date_end or periodo_fin
        tramo_ini = max(periodo_ini, contrato_ini)
        tramo_fin = min(periodo_fin, contrato_fin)

        # Tech Lead (2026-10-08, revisión .77): date_from/date_to son datetimes en UTC: una
        # ausencia que termina de noche en Colombia (UTC-5, ej. el calendario Mar-Dom de
        # Guapante) cae en la madrugada del día siguiente en UTC, y .date() contaría un día
        # de más. request_date_from/request_date_to son las fechas puras que el usuario
        # pidió (sin conversión de huso horario) -- misma lección ya aplicada a hr.leave en
        # otras partes del módulo.
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('holiday_status_id.work_entry_type_id.code', '=', work_entry_code),
            ('request_date_from', '<=', self.date_to),
            ('request_date_to', '>=', self.date_from),
        ])

        detalle = []
        dias_totales = 0
        for leave in leaves:
            leave_ini = leave.request_date_from
            leave_fin = leave.request_date_to
            dias = self._ne_dias_corridos_en_tramo(leave_ini, leave_fin, tramo_ini, tramo_fin, dias_mes)
            if dias > 0:
                detalle.append((leave, dias, max(leave_ini, tramo_ini), min(leave_fin, tramo_fin)))
                dias_totales += dias
        return dias_totales, detalle

    def _ne_dias_habiles_excluidos(self, codigos):
        """Dias HABILES de las ausencias de worked_days (CO_VAC, CO_LIC_REM, CO_LIC_NR y tipos
        'unpaid') que se excluyen del sueldo, acotados al tramo pagable.

        Un recibo de un solo mes: suma de worked_days, como siempre. Un recibo que cruza meses
        (Liquidacion: date_from = inicio de contrato, el sueldo es solo del ultimo mes):
        worked_days cubre toda la vida del contrato y restaria ausencias de meses ya pagados;
        se cuentan solo las del tramo (_ne_ausencia_habil con desde/hasta)."""
        self.ensure_one()
        tramo_ini, tramo_fin = self._ne_tramo_pagable_periodo()
        if tramo_ini == self.date_from:
            return sum(wd.number_of_days for wd in self.worked_days_line_ids
                       if wd.work_entry_type_id.code in codigos)
        return sum(self._ne_ausencia_habil(codigo, tramo_ini, tramo_fin)[0]
                   for codigo in sorted(codigos))

    def _ne_ausencia_habil_tramo(self, work_entry_code):
        """Ausencias en dias HABILES acotadas al tramo pagable del recibo: lo que este documento
        paga y reporta. Un recibo de un solo mes: el periodo completo (igual que
        _ne_ausencia_habil()); Liquidacion (date_from = inicio de contrato): solo el ultimo mes,
        porque los meses anteriores ya se pagaron y reportaron en sus propios documentos."""
        self.ensure_one()
        tramo_ini, tramo_fin = self._ne_tramo_pagable_periodo()
        return self._ne_ausencia_habil(work_entry_code, tramo_ini, tramo_fin)

    def _ne_ausencia_habil(self, work_entry_code, desde=None, hasta=None):
        """Única fuente de días HÁBILES (vía worked_days/hr.work.entry) para Vacaciones/
        LicenciaR/LicenciaNR (H-016, 2026-10-08, QA en staging -- NE0000000099).

        H-016, causa confirmada por QA: _get_overlapping_leaves_data() (el mecanismo que
        formateaba estos 3 conceptos en el XML antes de esta revisión) cuenta días
        CALENDARIO puros entre las fechas de la hr.leave, mientras que CO_VAC/CO_LIC_REM/
        CO_LIC_NR pagan y descuentan el básico en días HÁBILES del calendario del contrato
        (worked_days_line_ids, vía _ne_dias_novedad()). Un lunes no laborable o un festivo
        dentro del rango de la ausencia hacía que "Cantidad" (calendario) y "Pago" (hábil)
        del mismo nodo XML no cuadraran -- ej. vacaciones 5-11/ene con un lunes no laboral:
        Cantidad="7" (calendario) junto a Pago de solo 6 días (hábil).

        Por cada hr.leave validada de este código, agrupa sus hr.work.entry generados
        (ligados vía leave_id, mecanismo nativo de hr_work_entry_holidays -- confirmado
        contra hr_work_entry_contract._get_contract_work_entries_values(): solo se genera
        un work entry por cada intervalo de asistencia real del calendario que cae dentro
        de la ausencia, nunca uno para un día sin asistencia) y cuenta los días calendario
        DISTINTOS que esos work entries realmente cubren dentro del período de esta
        nómina -- el mismo criterio "hay o no hay work entry ese día" que ya determina el
        pago, nunca un conteo de fechas sin pasar por el calendario del contrato.

        Tech Lead (revisión .81): SOLO la CANTIDAD viene de los work entries -- FechaInicio/
        FechaFin son las fechas REALES de la ausencia (leave.request_date_from/
        request_date_to, recortadas al período de esta nómina), igual que
        _ne_ausencia_calendario(). Usar el primer/último work entry para las fechas (como
        hacía esta función antes de .81) recorta la fecha cuando la ausencia empieza o
        termina en un día sin work entry (festivo, sábado, lunes no laborable) -- a la DIAN
        va la fecha real de la ausencia, no la del primer/último día efectivamente pagado.

        desde/hasta (opcionales, por defecto date_from/date_to del recibo) acotan la cuenta a
        una ventana: en Liquidacion date_from es el inicio de contrato y el sueldo pendiente es
        solo el tramo del ultimo mes (_ne_tramo_pagable_periodo()).

        Devuelve (dias_totales, detalle) -- detalle = [(leave, dias, fecha_ini, fecha_fin)],
        mismo shape que _ne_ausencia_calendario() para que _dev_novedades()/
        _dev_prestaciones() los traten igual.
        """
        self.ensure_one()
        desde = desde or self.date_from
        hasta = hasta or self.date_to
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('holiday_status_id.work_entry_type_id.code', '=', work_entry_code),
            ('request_date_from', '<=', hasta),
            ('request_date_to', '>=', desde),
        ])
        if not leaves:
            return 0, []

        periodo_ini_dt = datetime.combine(desde, datetime.min.time())
        periodo_fin_dt = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
        work_entries = self.env['hr.work.entry'].search([
            ('employee_id', '=', self.employee_id.id),
            ('leave_id', 'in', leaves.ids),
            ('date_start', '<', periodo_fin_dt),
            ('date_stop', '>', periodo_ini_dt),
        ])

        entries_by_leave = defaultdict(list)
        for entry in work_entries:
            entries_by_leave[entry.leave_id.id].append(entry)

        detalle = []
        dias_totales = 0
        for leave in leaves:
            entries = entries_by_leave.get(leave.id)
            if not entries:
                continue
            dias = len({entry.date_start.date() for entry in entries})
            if dias > 0:
                ini = max(leave.request_date_from, desde)
                fin = min(leave.request_date_to, hasta)
                detalle.append((leave, dias, ini, fin))
                dias_totales += dias
        return dias_totales, detalle

    def _ne_dias_novedad_ausencia_e_input(self, work_entry_code, input_code, inputs, worked_days):
        """(días desde Ausencias, días desde el input manual) para un concepto de novedad en
        días HÁBILES (CO_VAC/CO_LIC_REM/CO_LIC_NR -- H-013).

        No decide ni falla -- eso lo hace el llamador: condition_python solo necesita saber
        si hay algo (cualquiera de los dos > 0); amount_python_compute (vía
        _ne_dias_novedad()) necesita el valor final y el chequeo de conflicto."""
        worked_days_line = worked_days.get(work_entry_code)
        dias_ausencia = worked_days_line.number_of_days if worked_days_line else 0
        input_line = inputs.get(input_code)
        dias_input = input_line.amount if input_line else 0
        return dias_ausencia, dias_input

    def _ne_ausencia_calendario_dias_e_input(self, work_entry_code, input_code, inputs):
        """Igual que _ne_dias_novedad_ausencia_e_input() pero para los 4 conceptos de días
        CALENDARIO corridos (H-014) -- mismo rol (condition_python), fuente de días distinta
        (_ne_ausencia_calendario() en vez de worked_days)."""
        dias_ausencia, _detalle = self._ne_ausencia_calendario(work_entry_code)
        input_line = inputs.get(input_code)
        dias_input = input_line.amount if input_line else 0
        return dias_ausencia, dias_input

    def _ne_resolver_dias_novedad(self, dias_ausencia, input_code, inputs, work_entry_code):
        """Combina los días que vienen de Ausencias con el input manual de respaldo para un
        concepto de novedad -- nunca los dos a la vez. Compartido por _ne_dias_novedad()
        (días hábiles, H-013) y _ne_dias_novedad_calendario() (días corridos, H-014): ambos
        ya calcularon dias_ausencia por su propio mecanismo, y de aquí en adelante el
        conflicto con el input manual se resuelve igual.

        H-013 (2026-10-08, decisión de David): prioriza el módulo de Ausencias (hr.leave
        validada -> ... -> esta función). El input manual CO_XXX sigue existiendo como
        respaldo para lo que Ausencias no haya capturado, pero NUNCA junto con una ausencia
        real del mismo concepto en la misma nómina: sumar los dos sería doble conteo, y
        elegir uno en silencio escondería un error de captura real. Nunca un default
        silencioso -- mismo principio que _dias_trabajados_requerido()/_pais_requerido()
        en services/nomina_xml_builder.py.
        """
        input_line = inputs.get(input_code)
        dias_input = input_line.amount if input_line else 0
        if dias_ausencia > 0 and dias_input > 0:
            raise UserError(_(
                'Hay %(dias_ausencia)s día(s) de "%(code)s" ya registrados en Ausencias '
                'y además un input manual "%(input_code)s" con %(dias_input)s día(s) en '
                'la misma nómina de %(employee)s. Use solo una fuente: borre el input '
                'manual si la ausencia ya está en el sistema, o elimine la ausencia si el '
                'dato manual es el correcto.',
                dias_ausencia=dias_ausencia, code=work_entry_code, input_code=input_code,
                dias_input=dias_input, employee=self.employee_id.name,
            ))
        return dias_ausencia or dias_input

    def _ne_dias_novedad(self, work_entry_code, input_code, inputs, worked_days):
        """Única fuente de días para las reglas de ausencias en días HÁBILES (CO_VAC/
        CO_LIC_REM/CO_LIC_NR, H-013) -- los mismos días que _ne_dias_pagables() excluye del
        básico (_NOVEDAD_AUSENCIA_WORKED_DAYS_CODES)."""
        dias_ausencia, _dias_input = self._ne_dias_novedad_ausencia_e_input(
            work_entry_code, input_code, inputs, worked_days)
        return self._ne_resolver_dias_novedad(dias_ausencia, input_code, inputs, work_entry_code)

    def _ne_dias_novedad_calendario(self, work_entry_code, input_code, inputs):
        """Única fuente de días para las reglas de ausencias en días CALENDARIO corridos
        (CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL, H-014) -- los mismos días que
        _ne_dias_pagables() excluye del básico (_NOVEDAD_AUSENCIA_CALENDARIO_CODES)."""
        dias_ausencia, _detalle = self._ne_ausencia_calendario(work_entry_code)
        return self._ne_resolver_dias_novedad(dias_ausencia, input_code, inputs, work_entry_code)

    def _ne_ultimo_ibc_anterior(self, contract, estructura=None, antes_de=None):
        """Último IBC de seguridad social confirmado antes de esta nómina (H-017a,
        2026-10-11, punto a del diseño -- decisión de David + Tech Lead).

        Mismo patrón que Procedure2.action_calculate_retention_procedure2()
        (hr_contract_retefuente.py): última nómina 'done' del mismo contrato y
        estructura, antes del date_from de esta nómina, leyendo su línea
        invisible CO_SS_BASE_IBC. Sin historial (primera nómina del contrato):
        fallback a contract.wage -- confirmado el caso real de los 18 empleados
        de Guapante hoy (ninguno tiene nómina previa).

        Lectura literal (Tech Lead, 2026-10-11): si hubo un cambio de salario
        entre el mes anterior y el de la novedad, se usa el IBC real del mes
        anterior tal cual, NUNCA un valor prorrateado al salario nuevo.
        """
        self.ensure_one()
        # estructura / antes_de (opcionales): la liquidacion no tiene historial propio; su "ultimo
        # IBC anterior" es el de la nomina general del contrato antes del tramo.
        payslip_anterior = self.env['hr.payslip'].search([
            ('contract_id', '=', contract.id),
            ('struct_id', '=', (estructura or self.struct_id).id),
            ('state', '=', 'done'),
            ('date_from', '<', antes_de or self.date_from),
        ], order='date_from desc', limit=1)
        if not payslip_anterior:
            return contract.wage
        linea_ibc = payslip_anterior.line_ids.filtered(lambda l: l.code == 'CO_SS_BASE_IBC')
        return linea_ibc.total if linea_ibc else contract.wage

    def _ne_factor_dias_integral(self):
        """Fraccion del mes comercial que cubre este recibo, para prorratear el salario
        integral (que no sale de lineas de devengado sino del contrato). Con ella, dos
        recibos del mismo mes (nomina + liquidacion) suman UN IBC, no dos (H-017b)."""
        self.ensure_one()
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        return min(self._ne_dias_bajo_contrato(), dias_mes) / dias_mes

    def _ne_ibc_salarial(self, categories, contract, inputs, worked_days):
        """Parte SALARIAL del IBC (H-017a): DEV_SAL + vacaciones y licencia remunerada
        (base = ultimo IBC anterior, prorrateado por dias). Salario integral:
        factor (70%) x salario. Ver _ne_ibc_seguridad_social para el alcance H-017a."""
        self.ensure_one()
        if contract.l10n_co_ne_integral_salary:
            return contract.wage * self._rule_parameter(
                'l10n_co_factor_integral_salary', self._ne_fecha_parametros()) * self._ne_factor_dias_integral()
        ibc = categories['DEV_SAL']
        dias_mes_comercial = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        ultimo_ibc = None
        for work_entry_code in ('CO_VAC', 'CO_LIC_REM'):
            dias_ausencia, dias_input = self._ne_dias_novedad_ausencia_e_input(
                work_entry_code, work_entry_code, inputs, worked_days)
            dias = dias_ausencia or dias_input
            if dias > 0:
                if ultimo_ibc is None:
                    ultimo_ibc = self._ne_ultimo_ibc_anterior(contract)
                ibc += (ultimo_ibc / dias_mes_comercial) * dias
        return ibc

    def _ne_ibc_incap(self, contract, result_rules, codigos=None):
        """Base de las ausencias de pago por tercero (maternidad/paternidad e
        incapacidades): el valor del auxilio que la novedad ya pago (Decreto 780/2016
        Art. 3.2.5.1; decision de David, 2026-11-10). Solo cuenta a salud y pension,
        no a ARL ni parafiscales; el descuento al empleado es el normal (Art.
        3.2.1.10), a diferencia de SLN. Integral: 0 (como H-017a).
        `codigos` permite acotar; por defecto los 4 de ausencia calendario."""
        if contract.l10n_co_ne_integral_salary:
            return 0.0
        if codigos is None:
            codigos = _NOVEDAD_AUSENCIA_CALENDARIO_CODES
        return sum(
            result_rules.get(codigo, {}).get('total', 0.0) for codigo in sorted(codigos))

    def _ne_ibc_seguridad_social(self, categories, contract, inputs, worked_days, result_rules):
        """Base que guarda CO_SS_BASE_IBC y que _ne_ultimo_ibc_anterior() lee el mes
        siguiente para prorratear vacaciones/licencia remunerada/SLN (H-017a): salario
        ordinario + maternidad/paternidad, SIN el auxilio de incapacidad (IGE/IRL), que no
        es salario (CST Art. 192; decision de David, 2026-11-10). El IBC de APORTES vive
        en CO_IBC_SP y si incluye la incapacidad."""
        return (self._ne_ibc_salarial(categories, contract, inputs, worked_days)
                + self._ne_ibc_incap(
                    contract, result_rules, codigos=('CO_LIC_MAT', 'CO_LIC_PAT')))

    def _ne_ibc_salarial_liquidacion(self, categories, contract):
        """Parte salarial del IBC en la liquidacion: el salario pendiente del tramo
        (DEV_SAL = CO_LIQ_SALARIOS) o, con salario integral, factor x salario. No cotizan
        (CST Art. 127/128, Ley 1393): vacaciones compensadas, prima, cesantias, intereses
        e indemnizacion."""
        self.ensure_one()
        if contract.l10n_co_ne_integral_salary:
            return contract.wage * self._rule_parameter(
                'l10n_co_factor_integral_salary', self._ne_fecha_parametros()) * self._ne_factor_dias_integral()
        # Vacaciones disfrutadas y licencia remunerada del tramo (se pagan en CO_LIQ_VAC_DISFRUTADAS
        # y CO_LIQ_LIC_REM): cotizan con el mismo criterio de _ne_ibc_salarial -- ultimo IBC
        # anterior (de la nomina general, antes del tramo) prorrateado por dias.
        ibc = categories['DEV_SAL']
        tramo_ini = self._ne_tramo_pagable_periodo()[0]
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        ultimo_ibc = None
        for work_entry_code in ('CO_VAC', 'CO_LIC_REM'):
            dias = self._ne_ausencia_habil_tramo(work_entry_code)[0]
            if dias > 0:
                if ultimo_ibc is None:
                    ultimo_ibc = self._ne_ultimo_ibc_anterior(
                        contract,
                        estructura=self.env.ref(
                            'l10n_co_nomina_electronica.hr_payroll_structure_co_nomina'),
                        antes_de=tramo_ini)
                ibc += (ultimo_ibc / dias_mes) * dias
        return ibc

    def _ne_ibc_remuneracion(self, contract, salarial):
        """Base del 40%: remuneracion total. Integral: 100% del salario pactado."""
        if contract.l10n_co_ne_integral_salary:
            return contract.wage * self._ne_factor_dias_integral()
        return salarial

    def _ne_ibc_pactados(self, result_rules):
        """Suma de los pagos no salariales POR PACTO (regla del 40%). Un concepto no
        salarial con valor y sin clasificar es error (sin default silencioso)."""
        self.ensure_one()
        total = 0.0
        for regla in self.struct_id.rule_ids:
            if regla.category_id.code != 'DEV_NOSAL':
                continue
            valor = abs(result_rules[regla.code]['total'])
            if not valor:
                continue
            if not regla.l10n_co_pila_origen_no_salarial:
                raise UserError(_(
                    'La regla "%(regla)s" es un pago no salarial con valor en la '
                    'nomina "%(nomina)s", pero no tiene "Origen del Pago No '
                    'Salarial (IBC)". Defina si es por naturaleza o por pacto '
                    'de desalarizacion en la regla salarial.',
                    regla=regla.name, nomina=self.display_name))
            if regla.l10n_co_pila_origen_no_salarial == 'pacto':
                total += valor
        return total

    def _ne_dias_sln(self):
        """Dias de suspension / licencia no remunerada (SLN) desde Ausencias: tipos
        'unpaid' de hr.leave.type y CO_LIC_NR."""
        self.ensure_one()
        unpaid = self.env['hr.leave.type'].search([('unpaid', '=', True)])
        codigos = set(unpaid.mapped('work_entry_type_id.code')) - {False}
        codigos.add('CO_LIC_NR')
        codigos -= {'CO_VAC', 'CO_LIC_REM'}
        return self._ne_dias_habiles_excluidos(codigos)

    def _ne_dias_cotizados(self):
        """Dias cotizados por subsistema (tabla de David, 2026-11-09).

        Total del tramo = dias bajo contrato (mes comercial, tope 30; ING/RET lo
        delimitan) -> salud y pension: incluye laborados, VAC, licencia remunerada,
        incapacidades (IGE, IRL), maternidad/paternidad (LMA) y SLN.
        ARL y parafiscales: solo laborados + VAC + licencia remunerada, es decir el
        total menos IGE, IRL, LMA y SLN. Mismas fuentes de dias que
        _ne_dias_pagables() (no se recalcula nada aparte)."""
        self.ensure_one()
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        total = min(self._ne_dias_bajo_contrato(), dias_mes)
        sin_arl = self._ne_dias_sln()
        for codigo in _NOVEDAD_AUSENCIA_CALENDARIO_CODES:
            sin_arl += self._ne_ausencia_calendario(codigo)[0]
        con_arl = max(0, total - sin_arl)
        return {'sp': total, 'arl': con_arl, 'paraf': con_arl}

    def _ne_ibc_sln(self, contract):
        """Base de los dias SLN: IBC del mes anterior prorrateado por esos dias (solo
        salud y pension; el empleador asume el 100%, por lo que no se descuenta al
        empleado)."""
        self.ensure_one()
        dias = self._ne_dias_sln()
        if dias <= 0:
            return 0.0
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        tramo_ini = self._ne_tramo_pagable_periodo()[0]
        if tramo_ini != self.date_from:
            # Liquidacion (H-168): no tiene historial propio; la base es el ultimo IBC de la
            # nomina general del contrato antes del tramo (mismo criterio que sus vacaciones).
            ultimo_ibc = self._ne_ultimo_ibc_anterior(
                contract,
                estructura=self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina'),
                antes_de=tramo_ini)
        else:
            ultimo_ibc = self._ne_ultimo_ibc_anterior(contract)
        return ultimo_ibc / dias_mes * dias

    def _ne_ibc_limites(self, salarial, incap, remuneracion, pactados, dias):
        """IBC del recibo con regla del 40%, techo (sin prorratear) y piso (prorrateado
        por dias). Ley 1393/2010 Art. 30; Ley 797/2003; SU 25185/2021."""
        self.ensure_one()
        smmlv = self._rule_parameter('l10n_co_smmlv', self._ne_fecha_parametros())
        pct = self._rule_parameter('l10n_co_pct_tope_no_salarial', self._ne_fecha_parametros())
        minimo = self._rule_parameter('l10n_co_ibc_min_smmlv', self._ne_fecha_parametros())
        maximo = self._rule_parameter('l10n_co_ibc_max_smmlv', self._ne_fecha_parametros())
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        excedente = max(0.0, pactados - pct / 100.0 * (remuneracion + pactados))
        ibc = min(salarial + incap + excedente, maximo * smmlv)
        if dias > 0:
            ibc = max(ibc, minimo * smmlv / dias_mes * dias)
        return ibc

    def _ne_dias_xml(self, valor):
        """Entero para los campos de DIAS del XML (DiasTrabajados, Cantidad de vacaciones, primas,
        incapacidades, licencias y huelga: el XSD v1.0.6 los exige enteros). Un valor que ya es
        entero pasa tal cual. Uno fraccionario se redondea con el modo que la compania configura
        (l10n_co_ne_redondeo_dias, vocabulario nativo de float_round / account.cash.rounding:
        HALF-UP, UP, DOWN); sin configurar es un error claro: antes se truncaba en silencio."""
        self.ensure_one()
        if float_is_zero(valor - round(valor), precision_digits=6):
            return int(round(valor))
        modo = self.company_id.l10n_co_ne_redondeo_dias
        if not modo:
            raise UserError(_(
                'La empresa %(company)s no tiene configurado el redondeo de días del XML '
                '(Nómina > Configuración > Ajustes, bloque Parámetros Nómina Colombia, '
                '"Redondeo de días del XML"). Se necesita para el valor %(valor)s de la nómina '
                '"%(nomina)s": la DIAN exige días enteros.',
                company=self.company_id.name, valor=valor, nomina=self.display_name))
        return int(float_round(valor, precision_rounding=1.0, rounding_method=modo))

    def _dev_basico_y_transporte(self, concept_lines, devengados):
        """Devengados: sueldo básico, transporte y viáticos."""
        # Sueldo básico
        if 'Sueldo' in concept_lines:
            sueldo_lines = concept_lines['Sueldo']
            dias_pagables = self._ne_dias_pagables()
            if dias_pagables <= 0:
                raise UserError(_(
                    'No se pudo determinar DiasTrabajados de %(employee)s para el período '
                    '%(ini)s a %(fin)s (contrato no activo en el período, o los días no '
                    'remunerados cubren todo el período). Revise las fechas del contrato y '
                    'las novedades antes de generar el XML.',
                    employee=self.employee_id.name, ini=self.date_from, fin=self.date_to,
                ))
            devengados['Basico'] = {
                'DiasTrabajados': str(self._ne_dias_xml(dias_pagables)),
                'SueldoTrabajado': '%.2f' % sum(l.total for l in sueldo_lines),
            }

        # Transporte
        if 'Transporte' in concept_lines:
            devengados['Transporte'] = {
                'AuxilioTransporte': '%.2f' % sum(
                    l.total for l in concept_lines['Transporte']
                ),
                'ViaticoManuAlojS': '0.00',
                'ViaticoManuAlojNS': '0.00',
            }

        # Viáticos
        if 'ViaticoS' in concept_lines:
            transport = devengados.setdefault('Transporte', {
                'AuxilioTransporte': '0.00',
                'ViaticoManuAlojS': '0.00',
                'ViaticoManuAlojNS': '0.00',
            })
            transport['ViaticoManuAlojS'] = '%.2f' % sum(
                l.total for l in concept_lines['ViaticoS']
            )
        if 'ViaticoNS' in concept_lines:
            transport = devengados.setdefault('Transporte', {
                'AuxilioTransporte': '0.00',
                'ViaticoManuAlojS': '0.00',
                'ViaticoManuAlojNS': '0.00',
            })
            transport['ViaticoManuAlojNS'] = '%.2f' % sum(
                l.total for l in concept_lines['ViaticoNS']
            )

    # Porcentaje (tabla 5.5.5 del Anexo) de cada hora extra/recargo, derivado del MISMO factor
    # hr.rule.parameter con el que se calcula el pago: (factor - 1) x 100 en las extras (el
    # factor incluye la hora ordinaria) y factor x 100 en el recargo nocturno (solo el recargo).
    # PENDIENTE (decision de David): los 4 conceptos dominicales/festivos (HEDDF, HRDDF, HENDF,
    # HRNDF) -- la tabla 5.5.5 y la Ley 2466/2025 no coinciden; mientras tanto conservan line.rate.
    _NE_PORCENTAJE_HORA_FACTOR = {
        'HED': ('l10n_co_factor_hed', -1.0),
        'HEN': ('l10n_co_factor_hen', -1.0),
        'HRN': ('l10n_co_factor_hrn', 0.0),
    }

    def _ne_porcentaje_hora(self, concepto, line):
        self.ensure_one()
        parametro = self._NE_PORCENTAJE_HORA_FACTOR.get(concepto)
        if not parametro:
            return line.rate or 0.0
        codigo, ajuste = parametro
        factor = self._rule_parameter(codigo, self._ne_fecha_parametros())
        return round((factor + ajuste) * 100.0, 2)

    def _dev_horas_extra(self, concept_lines, devengados):
        """Devengados: horas extras y recargos."""
        for he_concept in HORA_EXTRA_CONCEPTS:
            if he_concept in concept_lines:
                container_key = he_concept + 's'  # HEDs, HENs, etc.
                items = []
                for line in concept_lines[he_concept]:
                    items.append({
                        'HoraInicio': '',
                        'HoraFin': '',
                        # Anexo/XSD v1.0.6: Cantidad de las horas extra es xsd:decimal.
                        'Cantidad': '%.2f' % line.quantity,
                        'Porcentaje': '%.2f' % self._ne_porcentaje_hora(he_concept, line),
                        'Pago': '%.2f' % line.total,
                    })
                devengados[container_key] = items

    def _get_overlapping_leaves_data(self):
        """Busca ausencias validadas del empleado en el periodo y las organiza por categoria."""
        def get_leave_category(leave):
            code = (leave.holiday_status_id.work_entry_type_id.code or leave.holiday_status_id.name or '').strip().upper()
            if hasattr(self, '_LEAVE_CODE_MAP'):
                return self._LEAVE_CODE_MAP.get(code)
            # Copia defensiva de HrPayslipLeaveIntegration._LEAVE_CODE_MAP (hr_leave_ne.py)
            # -- nunca se ejercita en producción porque ese mixin siempre está presente en
            # este modelo heredado, pero debe quedar sincronizada para no divergir (H-014,
            # revisión .78: se agregaron los 7 códigos CO_ al mapa real, ver ese archivo).
            local_map = {
                'INCAPACIDAD': 'incapacidad', 'SICK': 'incapacidad', 'INC_COMUN': 'incapacidad', 'INC_LABORAL': 'incapacidad',
                'CO_INC_COMUN': 'incapacidad', 'CO_INC_LABORAL': 'incapacidad',
                'MATERNIDAD': 'licencia_mat', 'MATERNITY': 'licencia_mat', 'PATERNIDAD': 'licencia_mat', 'PATERNITY': 'licencia_mat', 'LIC_MAT': 'licencia_mat', 'LIC_PAT': 'licencia_mat',
                'CO_LIC_MAT': 'licencia_mat', 'CO_LIC_PAT': 'licencia_mat',
                'VACACIONES': 'vacaciones', 'VACATION': 'vacaciones', 'VAC': 'vacaciones', 'CO_VAC': 'vacaciones',
                'LICENCIA_REM': 'licencia_rem', 'LIC_REM': 'licencia_rem', 'PERMISO': 'licencia_rem', 'CO_LIC_REM': 'licencia_rem',
                'LICENCIA_NR': 'licencia_nr', 'LIC_NR': 'licencia_nr', 'UNPAID': 'licencia_nr', 'SIN_SUELDO': 'licencia_nr', 'CO_LIC_NR': 'licencia_nr',
            }
            return local_map.get(code)

        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
        ])

        category_leaves = defaultdict(list)
        category_leave_days = defaultdict(dict)  # leave.id -> days in period
        category_total_days = defaultdict(int)    # category -> total days in period
        
        for leave in leaves:
            leave_start = leave.date_from.date() if isinstance(leave.date_from, datetime) else leave.date_from
            leave_end = leave.date_to.date() if isinstance(leave.date_to, datetime) else leave.date_to
            period_start = max(leave_start, self.date_from)
            period_end = min(leave_end, self.date_to)
            days = (period_end - period_start).days + 1
            if days > 0:
                category = get_leave_category(leave)
                if category:
                    category_leaves[category].append(leave)
                    category_leave_days[category][leave.id] = days
                    category_total_days[category] += days

        return category_leaves, category_leave_days, category_total_days

    def _dev_prestaciones(self, concept_lines, devengados):
        """Devengados: vacaciones, primas, cesantías e intereses.

        Revisión .79 (2026-10-08, decisión de David): un pago de VacacionesComunes
        (CO_VAC) sin ninguna hr.leave validada que lo respalde (típicamente el input
        manual de respaldo usado solo, sin registrar la ausencia) se detiene con
        UserError en vez de emitir las fechas del período completo en silencio -- mismo
        criterio que Incapacidades/LicenciaMP/LicenciaR. VacacionesCompensadas (CO_VAC_COMP)
        no lleva FechaInicio/FechaFin en el XML (ver más abajo, Pago/Cantidad solamente) --
        no hay fecha que inventar, y por su naturaleza (pago en dinero de días NO
        disfrutados) tampoco hay una ausencia que la respalde, así que no entra en este
        mismo tratamiento.
        """
        # Vacaciones
        vac_comunes = concept_lines.get('VacacionesComunes', [])
        vac_compensadas = concept_lines.get('VacacionesCompensadas', [])
        if vac_comunes or vac_compensadas:
            vacaciones = {}
            if vac_comunes:
                # H-016 (revisión .80, decisión de David): fuente única con la regla/el
                # básico -- días HÁBILES vía worked_days/hr.work.entry
                # (_ne_ausencia_habil()), no días calendario puros
                # (_get_overlapping_leaves_data(), causa real del defecto reportado por QA
                # en NE0000000099).
                dias_totales, detalle = self._ne_ausencia_habil_tramo('CO_VAC')
                if detalle:
                    items = []
                    total_pago = sum(l.total for l in vac_comunes)
                    for _leave, dias, ini, fin in detalle:
                        pago = total_pago * (dias / dias_totales) if dias_totales > 0 else 0.0
                        items.append({
                            'FechaInicio': str(ini),
                            'FechaFin': str(fin),
                            'Cantidad': str(self._ne_dias_xml(dias)),
                            'Pago': '%.2f' % pago,
                        })
                    vacaciones['VacacionesComunes'] = items
                else:
                    # H-014 (revisión .79, decisión de David): mismo criterio que
                    # Incapacidad/LicenciaMP/LicenciaR -- sin ausencia validada no hay
                    # fechas reales que reportar, y aquí SÍ hay dinero real de por medio
                    # (CO_VAC). Antes se emitían las fechas del período completo en
                    # silencio.
                    raise UserError(_(
                        'Hay un pago de Vacaciones (%(pago)s) en la nómina de '
                        '%(employee)s sin ninguna ausencia (CO_VAC) validada en '
                        'Ausencias que lo respalde con fechas reales -- la DIAN exige '
                        'las fechas reales de las vacaciones, no las del período '
                        'completo. Registre la ausencia en Ausencias antes de generar '
                        'el XML.',
                        pago='%.2f' % sum(l.total for l in vac_comunes),
                        employee=self.employee_id.name,
                    ))
            if vac_compensadas:
                vacaciones['VacacionesCompensadas'] = [{
                    'Cantidad': str(self._ne_dias_xml(sum(l.quantity for l in vac_compensadas))),
                    'Pago': '%.2f' % sum(l.total for l in vac_compensadas),
                }]
            devengados['Vacaciones'] = vacaciones

        # Primas
        if 'Primas' in concept_lines:
            devengados['Primas'] = {
                'Cantidad': str(self._ne_dias_xml(sum(
                    l.quantity for l in concept_lines['Primas']
                ))),
                'Pago': '%.2f' % sum(l.total for l in concept_lines['Primas']),
                'PagoNS': '0.00',
            }

        # Cesantías e intereses
        cesantias_lines = concept_lines.get('Cesantias', [])
        intereses_lines = concept_lines.get('InteresesCesantias', [])
        if cesantias_lines or intereses_lines:
            devengados['Cesantias'] = {
                'Pago': '%.2f' % sum(l.total for l in cesantias_lines),
                'Porcentaje': '12.00' if intereses_lines else '0.00',
                'PagoIntereses': '%.2f' % sum(
                    l.total for l in intereses_lines
                ),
            }

    def _dev_novedades(self, concept_lines, devengados):
        """Devengados: incapacidades y licencias.

        H-014 (2026-10-08): Incapacidades (CO_INC_COMUN/CO_INC_LABORAL) y LicenciaMP
        (CO_LIC_MAT/CO_LIC_PAT) se formatean desde _ne_ausencia_calendario() -- la MISMA
        fuente que ya paga la regla y descuenta el básico (días calendario corridos), para
        no tener 3 cálculos distintos de lo mismo.

        H-016 (revisión .80): LicenciaR/LicenciaNR ahora se formatean desde
        _ne_ausencia_habil() (días HÁBILES vía worked_days/hr.work.entry) -- ya no desde
        _get_overlapping_leaves_data() (días calendario puros, causa del defecto de QA en
        NE0000000099: Cantidad/Pago del mismo nodo no cuadraban cuando la ausencia cruzaba
        un lunes no laborable o un festivo). _get_overlapping_leaves_data() queda SIN
        ningún llamador en todo el módulo tras este cambio -- no se eliminó, reportado a
        Tech Lead para que decida su retiro.

        Revisión .79 (2026-10-08, decisión de David): si hay un pago/registro de
        Incapacidad, LicenciaMP o LicenciaR SIN ninguna hr.leave validada que lo respalde
        (típicamente el input manual de respaldo usado solo, sin registrar la ausencia),
        se detiene con UserError en vez de emitir las fechas del período completo en
        silencio -- la DIAN exige las fechas reales de la ausencia (los nodos del XSD
        V1.0.6 son minOccurs=0: sin ausencia simplemente no se emite el nodo, nunca un
        dato inventado). LicenciaNR NUNCA llega a este camino: su amount_python_compute
        es siempre 0 (no genera pago, por diseño) y _group_lines_by_concept() omite del
        concept_lines cualquier línea con total=0 -- lo único que se pierde ahí es el
        detalle de cuántos días hubo, si nadie registra la ausencia (límite conocido, sin
        resolver). Vacaciones (CO_VAC) recibe el mismo tratamiento en _dev_prestaciones().
        """
        # Incapacidades (común + laboral, cada una con su Tipo -- ya no por substring del
        # código, por cuál de las 2 llamadas la produjo)
        if 'Incapacidad' in concept_lines:
            _dias_comun, detalle_comun = self._ne_ausencia_calendario('CO_INC_COMUN')
            _dias_laboral, detalle_laboral = self._ne_ausencia_calendario('CO_INC_LABORAL')
            detalle_inc = (
                [(leave, dias, ini, fin, '1') for leave, dias, ini, fin in detalle_comun]
                + [(leave, dias, ini, fin, '3') for leave, dias, ini, fin in detalle_laboral]
            )
            if detalle_inc:
                items = []
                total_pago = sum(l.total for l in concept_lines['Incapacidad'])
                total_dias = sum(dias for _leave, dias, _ini, _fin, _tipo in detalle_inc)
                for _leave, dias, ini, fin, tipo in detalle_inc:
                    pago = total_pago * (dias / total_dias) if total_dias > 0 else 0.0
                    items.append({
                        'FechaInicio': str(ini),
                        'FechaFin': str(fin),
                        'Cantidad': str(self._ne_dias_xml(dias)),
                        'Tipo': tipo,
                        'Pago': '%.2f' % pago,
                    })
                devengados['Incapacidades'] = items
            else:
                # H-014 (revisión .79, decisión de David): la DIAN exige las fechas reales
                # de la incapacidad -- un pago sin ninguna hr.leave validada que lo
                # respalde (ej. solo el input manual CO_INC_COMUN/CO_INC_LABORAL de
                # respaldo, sin registrar la ausencia) no tiene de dónde sacar esas fechas.
                # Antes se emitían las fechas del período completo en silencio; ahora se
                # detiene con un error claro en vez de mandar un dato inventado a la DIAN.
                raise UserError(_(
                    'Hay un pago de Incapacidad (%(pago)s) en la nómina de %(employee)s '
                    'sin ninguna ausencia de Incapacidad (CO_INC_COMUN/CO_INC_LABORAL) '
                    'validada en Ausencias que lo respalde con fechas reales -- la DIAN '
                    'exige las fechas reales de la incapacidad, no las del período '
                    'completo. Registre la ausencia en Ausencias antes de generar el XML.',
                    pago='%.2f' % sum(l.total for l in concept_lines['Incapacidad']),
                    employee=self.employee_id.name,
                ))

        # Licencias
        licencias = {}

        # LicenciaMP (maternidad + paternidad): días calendario corridos, misma fuente que
        # la regla y el descuento del básico (H-014).
        if 'LicenciaMP' in concept_lines:
            _dias_mat, detalle_mat = self._ne_ausencia_calendario('CO_LIC_MAT')
            _dias_pat, detalle_pat = self._ne_ausencia_calendario('CO_LIC_PAT')
            detalle_mp = detalle_mat + detalle_pat
            if detalle_mp:
                items = []
                total_pago = sum(l.total for l in concept_lines['LicenciaMP'])
                total_dias = sum(dias for _leave, dias, _ini, _fin in detalle_mp)
                for _leave, dias, ini, fin in detalle_mp:
                    pago = total_pago * (dias / total_dias) if total_dias > 0 else 0.0
                    items.append({
                        'FechaInicio': str(ini),
                        'FechaFin': str(fin),
                        'Cantidad': str(self._ne_dias_xml(dias)),
                        'Pago': '%.2f' % pago,
                    })
                licencias['LicenciaMP'] = items
            else:
                # H-014 (revisión .79, decisión de David): mismo criterio que Incapacidad
                # -- maternidad/paternidad SON licencias (LicenciaMP), no incapacidades, y
                # ya están separadas en el código; sin ausencia no hay fechas reales que
                # reportar.
                raise UserError(_(
                    'Hay un pago de Licencia de Maternidad/Paternidad (%(pago)s) en la '
                    'nómina de %(employee)s sin ninguna ausencia (CO_LIC_MAT/CO_LIC_PAT) '
                    'validada en Ausencias que lo respalde con fechas reales -- la DIAN '
                    'exige las fechas reales de la licencia, no las del período completo. '
                    'Registre la ausencia en Ausencias antes de generar el XML.',
                    pago='%.2f' % sum(l.total for l in concept_lines['LicenciaMP']),
                    employee=self.employee_id.name,
                ))

        # LicenciaR / LicenciaNR: días HÁBILES, misma fuente que la regla y el descuento
        # del básico (H-016, revisión .80: _ne_ausencia_habil(), ya no
        # _get_overlapping_leaves_data() -- causa del defecto de QA en NE0000000099, ver
        # docstring de _ne_ausencia_habil()).
        licencia_concepts = {
            'LicenciaR': 'CO_LIC_REM',
            'LicenciaNR': 'CO_LIC_NR',
        }
        for xml_key, work_entry_code in licencia_concepts.items():
            concept_key = xml_key
            dias_totales, detalle = self._ne_ausencia_habil_tramo(work_entry_code)

            if detalle:
                items = []
                total_pago = sum(l.total for l in concept_lines.get(concept_key, []))

                for _leave, dias, ini, fin in detalle:
                    pago = total_pago * (dias / dias_totales) if dias_totales > 0 else 0.0

                    lic_data = {
                        'FechaInicio': str(ini),
                        'FechaFin': str(fin),
                        'Cantidad': str(self._ne_dias_xml(dias)),
                    }
                    if concept_key != 'LicenciaNR':
                        lic_data['Pago'] = '%.2f' % pago
                    items.append(lic_data)
                licencias[xml_key] = items
            elif concept_key == 'LicenciaR' and concept_key in concept_lines:
                # H-014 (revisión .79, decisión de David): sin ausencia no hay fechas
                # reales que reportar -- mismo criterio que Incapacidad/LicenciaMP/
                # Vacaciones. LicenciaNR NUNCA entra aquí: su amount_python_compute es
                # siempre 0 (no genera pago, por diseño -- ver data/hr_payroll_structure_
                # data.xml) y _group_lines_by_concept() omite del concept_lines cualquier
                # línea con total=0, así que una rama "elif 'LicenciaNR' in concept_lines"
                # sería código muerto que nada prueba (Tech Lead, revisión .79). Lo único
                # que se pierde en ese caso es el detalle de cuántos días de licencia no
                # remunerada hubo, si nadie registra la ausencia -- límite conocido, no se
                # resuelve aquí (ver test_xml_licencia_no_remunerada_solo_input_no_emite_
                # nodo_ni_error).
                raise UserError(_(
                    'Hay un registro de Licencia Remunerada (%(cantidad)s día(s)) en la '
                    'nómina de %(employee)s sin ninguna ausencia validada en Ausencias '
                    'que lo respalde con fechas reales -- la DIAN exige las fechas reales '
                    'de la licencia, no las del período completo. Registre la ausencia en '
                    'Ausencias antes de generar el XML.',
                    cantidad=str(self._ne_dias_xml(sum(
                        l.quantity for l in concept_lines[concept_key]
                    ))),
                    employee=self.employee_id.name,
                ))
        if licencias:
            devengados['Licencias'] = licencias

    def _dev_complementarios(self, concept_lines, devengados):
        """Devengados: bonificaciones, auxilios, huelgas, otros y compensaciones."""
        # Bonificaciones
        bonif_s = concept_lines.get('BonificacionS', [])
        bonif_ns = concept_lines.get('BonificacionNS', [])
        if bonif_s or bonif_ns:
            devengados['Bonificaciones'] = [{
                'BonificacionS': '%.2f' % sum(l.total for l in bonif_s),
                'BonificacionNS': '%.2f' % sum(l.total for l in bonif_ns),
            }]

        # Auxilios
        aux_s = concept_lines.get('AuxilioS', [])
        aux_ns = concept_lines.get('AuxilioNS', [])
        if aux_s or aux_ns:
            devengados['Auxilios'] = [{
                'AuxilioS': '%.2f' % sum(l.total for l in aux_s),
                'AuxilioNS': '%.2f' % sum(l.total for l in aux_ns),
            }]

        # Huelga Legal
        if 'HuelgaLegal' in concept_lines:
            devengados['HuelgasLegales'] = [{
                'FechaInicio': str(self.date_from),
                'FechaFin': str(self.date_to),
                'Cantidad': str(self._ne_dias_xml(sum(
                    l.quantity for l in concept_lines['HuelgaLegal']
                ))),
            }]

        # Otros conceptos salariales y no salariales
        otros_s = concept_lines.get('OtroConceptoS', [])
        otros_ns = concept_lines.get('OtroConceptoNS', [])
        if otros_s or otros_ns:
            otros = []
            for line in otros_s:
                otros.append({
                    'DescripcionConcepto': line.name or '',
                    'ConceptoS': '%.2f' % line.total,
                    'ConceptoNS': '0.00',
                })
            for line in otros_ns:
                otros.append({
                    'DescripcionConcepto': line.name or '',
                    'ConceptoS': '0.00',
                    'ConceptoNS': '%.2f' % line.total,
                })
            devengados['OtrosConceptos'] = otros

        # Compensaciones
        comp_o = concept_lines.get('CompensacionO', [])
        comp_e = concept_lines.get('CompensacionE', [])
        if comp_o or comp_e:
            devengados['Compensaciones'] = [{
                'CompensacionO': '%.2f' % sum(l.total for l in comp_o),
                'CompensacionE': '%.2f' % sum(l.total for l in comp_e),
            }]

    def _dev_bonos_y_pagos(self, concept_lines, devengados):
        """Devengados: bonos EPCTV, comisiones, pagos a terceros, anticipos y conceptos simples."""
        # Bonos EPCTV
        bono_keys = {
            'BonoEPCTVS': 'PagoS',
            'BonoEPCTVNS': 'PagoNS',
            'BonoAlimS': 'PagoAlimentacionS',
            'BonoAlimNS': 'PagoAlimentacionNS',
        }
        bono_data = {}
        for concept_key, xml_attr in bono_keys.items():
            if concept_key in concept_lines:
                bono_data[xml_attr] = '%.2f' % sum(
                    l.total for l in concept_lines[concept_key]
                )
        if bono_data:
            for attr in ['PagoS', 'PagoNS', 'PagoAlimentacionS', 'PagoAlimentacionNS']:
                bono_data.setdefault(attr, '0.00')
            devengados['BonoEPCTVs'] = [bono_data]

        # Comisiones
        if 'Comision' in concept_lines:
            devengados['Comisiones'] = [
                '%.2f' % l.total for l in concept_lines['Comision']
            ]

        # Pagos a terceros (devengado)
        if 'PagoTercero' in concept_lines:
            devengados['PagosTerceros'] = [
                '%.2f' % l.total for l in concept_lines['PagoTercero']
            ]

        # Anticipos (devengado)
        if 'Anticipo' in concept_lines:
            devengados['Anticipos'] = [
                '%.2f' % l.total for l in concept_lines['Anticipo']
            ]

        # Conceptos simples de devengado
        for concept_key, xml_key in DEVENGADO_SIMPLE_CONCEPTS.items():
            if concept_key in concept_lines:
                devengados[xml_key] = '%.2f' % sum(
                    l.total for l in concept_lines[concept_key]
                )

    def _build_deducciones(self, concept_lines):
        """Construye el dict <Deducciones> del XML a partir de concept_lines."""
        deducciones = {}
        # Salud
        if 'Salud' in concept_lines:
            deducciones['Salud'] = {
                'Porcentaje': '4.00',
                'Deduccion': '%.2f' % abs(sum(
                    l.total for l in concept_lines['Salud']
                )),
            }

        # Fondo de Pensión
        if 'FondoPension' in concept_lines:
            deducciones['FondoPension'] = {
                'Porcentaje': '4.00',
                'Deduccion': '%.2f' % abs(sum(
                    l.total for l in concept_lines['FondoPension']
                )),
            }

        # Fondo de Solidaridad Pensional
        if 'FondoSP' in concept_lines:
            deducciones['FondoSP'] = {
                'Porcentaje': '1.00',
                'DeduccionSP': '%.2f' % abs(sum(
                    l.total for l in concept_lines['FondoSP']
                )),
                'PorcentajeSub': '0.00',
                'DeduccionSub': '0.00',
            }

        # Sindicatos
        if 'Sindicato' in concept_lines:
            deducciones['Sindicatos'] = [{
                'Porcentaje': '%.2f' % (
                    concept_lines['Sindicato'][0].rate or 0
                ),
                'Deduccion': '%.2f' % abs(sum(
                    l.total for l in concept_lines['Sindicato']
                )),
            }]

        # Sanciones
        if 'Sancion' in concept_lines:
            deducciones['Sanciones'] = [{
                'SancionPublic': '0.00',
                'SancionPriv': '%.2f' % abs(sum(
                    l.total for l in concept_lines['Sancion']
                )),
            }]

        # Libranzas
        if 'Libranza' in concept_lines:
            deducciones['Libranzas'] = []
            for line in concept_lines['Libranza']:
                deducciones['Libranzas'].append({
                    'Descripcion': line.name or 'Libranza',
                    'Deduccion': '%.2f' % abs(line.total),
                })

        # Pagos a terceros (deducción)
        if 'PagoTerceroDed' in concept_lines:
            deducciones['PagosTerceros'] = [
                '%.2f' % abs(l.total) for l in concept_lines['PagoTerceroDed']
            ]

        # Anticipos (deducción)
        if 'AnticipoDed' in concept_lines:
            deducciones['Anticipos'] = [
                '%.2f' % abs(l.total) for l in concept_lines['AnticipoDed']
            ]

        # Otras deducciones
        if 'OtraDeduccion' in concept_lines:
            deducciones['OtrasDeducciones'] = [
                '%.2f' % abs(l.total) for l in concept_lines['OtraDeduccion']
            ]

        # Deducciones simples (valor único)
        for concept_key, xml_key in DEDUCTION_SIMPLE_CONCEPTS.items():
            if concept_key in concept_lines:
                deducciones[xml_key] = '%.2f' % abs(sum(
                    l.total for l in concept_lines[concept_key]
                ))

        return deducciones

    # ══════════════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES PRIVADOS
    # ══════════════════════════════════════════════════════════════════







    def action_payslip_draft(self):
        colombia = self._ne_solo_colombia()
        colombia._ne_aplicar_libranzas(revertir=True)
        res = super().action_payslip_draft()
        colombia._ne_refrescar_ibc_mensual()
        return res

    def action_payslip_cancel(self):
        colombia = self._ne_solo_colombia()
        colombia._ne_aplicar_libranzas(revertir=True)
        res = super().action_payslip_cancel()
        colombia._ne_refrescar_ibc_mensual()
        return res
