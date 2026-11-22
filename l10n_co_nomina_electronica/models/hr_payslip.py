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
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta

from pytz import timezone as _pytz_timezone
from lxml import etree as _etree

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_round
from odoo.tools.misc import format_amount, format_date

from .hr_employee import NE_EMPLEADO_GRUPO_AFILIACION, NE_EMPLEADO_PESTANA, NE_UBICACION_AJUSTES_PILA

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
_NOVEDAD_INCAPACIDAD_CODES = ('CO_INC_COMUN', 'CO_INC_LABORAL')       # incapacidades: no entran a CO_SS_BASE_IBC (H-F1-11)
_NOVEDAD_AUSENCIA_CALENDARIO_CODES = {
    'CO_LIC_MAT', 'CO_LIC_PAT', 'CO_INC_COMUN', 'CO_INC_LABORAL',
}

# Secciones de «Conceptos de pago» (E11 pieza 3, .289) y de la colilla (pieza 5a, .291): UNA sola fuente para la pestaña y el informe. Las claves
# son valores de ``hr.salary.rule.category.l10n_co_ne_seccion_concepto``; el orden es el de impresión.
NE_SECCIONES_CONCEPTO = (('devengados', 'Devengados'), ('deducciones', 'Deducciones'))

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

    # Documento mensual DIAN al que pertenece el recibo (doc 53 §3.2, etapa 1b). El ciclo DIAN por recibo
    # (campos del mixin) sigue intacto hasta la etapa 5; esto solo agrega el enlace.
    l10n_co_ne_documento_id = fields.Many2one(
        'l10n.co.ne.documento', string='Documento DIAN mensual', copy=False, index=True,
        ondelete='restrict', check_company=True,
        help='Documento mensual de nómina electrónica (uno por empleado y mes) que incluye este recibo.')
    l10n_co_ne_documento_state = fields.Selection(
        related='l10n_co_ne_documento_id.state', string='Estado DIAN del documento', store=True)
    l10n_co_ne_documento_message = fields.Html(
        related='l10n_co_ne_documento_id.message', string='Motivo DIAN', readonly=True)

    def _ne_historia_solo_habilitacion(self):
        """True si lo que el recibo transmitió fue SOLO del proceso de habilitación (set de pruebas), no un reporte real.

        Criterio (doc 53 §28.6): el marcador propio ``l10n_co_ne_hab_set_id`` (TestSetId con el que se envió en el set
        de pruebas) O, sin marcador, intercambios que NO incluyen ningún ``send_sync`` (envío real síncrono). Se mira
        el TIPO de intercambio y no la URL (el endpoint es un parámetro del sistema). Un recibo sin intercambios ni
        marcador no es "de habilitación": puede ser un recibo real nuevo."""
        self.ensure_one()
        if self.l10n_co_ne_hab_set_id:
            return True
        intercambios = self.l10n_co_ne_exchange_ids
        return bool(intercambios) and not any(op == 'send_sync' for op in intercambios.mapped('operation'))

    l10n_co_ne_en_produccion = fields.Boolean(
        string='Compañía en producción (nómina electrónica)', compute='_compute_ne_en_produccion',
        help='Solo para las vistas: en producción el recibo no se transmite por su cuenta, se reporta en el documento '
             'mensual.')

    l10n_co_ne_aviso_periodicidad = fields.Char(
        string='Aviso de periodicidad', compute='_compute_ne_aviso_periodicidad',
        help='Solo para las vistas: aviso (no bloquea) cuando el recibo cubre 7 días y el contrato no es semanal.')

    @api.depends('date_from', 'date_to', 'struct_id', 'employee_id', 'contract_id.schedule_pay',
                 'contract_id.structure_type_id.default_schedule_pay', 'company_id')
    def _compute_ne_aviso_periodicidad(self):
        """E-2 (doc 59 §19.1): un recibo de la estructura general de exactamente 7 días con un contrato que no es `weekly` se
        calcularia con dias comerciales (un semanal mal configurado daria 6 dias al cruzar un mes de 31 dias). Aviso sin bloquear,
        con el nombre del empleado y como corregirlo. Decision de David: el pago semanal cuenta 7 dias calendario (texto
        normativo NO VERIFICADO)."""
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina', raise_if_not_found=False)
        for recibo in self:
            recibo.l10n_co_ne_aviso_periodicidad = False
            if not (recibo.date_from and recibo.date_to and recibo.struct_id == general and recibo.company_id
                    and recibo.company_id._ne_es_colombia() and recibo.contract_id):
                continue
            if (recibo.date_to - recibo.date_from).days + 1 != 7 or recibo._ne_es_semanal():
                continue
            contrato = recibo.contract_id
            periodicidad = contrato.schedule_pay or contrato.structure_type_id.default_schedule_pay
            etiqueta = dict(contrato._fields['schedule_pay'].selection).get(periodicidad) or _('(sin periodicidad)')
            recibo.l10n_co_ne_aviso_periodicidad = _(
                'El recibo de %(empleado)s cubre exactamente 7 días pero la periodicidad de su contrato es "%(periodicidad)s", no '
                '"Semanal". Si se le paga por semana, cambie la periodicidad a Semanal en el contrato o en el tipo de estructura '
                '(Nómina > Configuración > Tipos de estructura) y calcule de nuevo: un semanal sin esa periodicidad se calcula con '
                'días comerciales y una semana que cruza un mes de 31 días saldría de 6 días.',
                empleado=recibo.employee_id.name, periodicidad=etiqueta)

    l10n_co_ne_aviso_dias = fields.Char(
        string='Aviso de días trabajados', compute='_compute_ne_aviso_dias',
        help='Solo para las vistas: aviso (no bloquea) con las fechas del recibo que no tienen entrada de trabajo y se pagan con el horario del contrato.')

    @api.depends('worked_days_line_ids', 'worked_days_line_ids.number_of_days', 'date_from', 'date_to', 'contract_id', 'state')
    def _compute_ne_aviso_dias(self):
        """.284 (E2a, doc 68 §12): regla de David «si falta la entrada manda el horario del contrato»: la fecha se paga como laborada y aquí se
        avisa cuál es, para que se genere o corrija la entrada. Solo recibos en borrador o en espera que se desglosan por fecha.

        .300 (E2b): además, aviso de «líneas desactualizadas»: los días de una vacación o licencia de la pestaña no coinciden con las fechas de las entradas
        (``_ne_avisos_ausencias_desactualizadas``: un recibo calculado antes de .300 o cuyas entradas cambiaron). Los avisos se juntan en el mismo campo; un
        error al leerlos (p. ej. sin el parámetro de fracciones) no se lanza al abrir el formulario: sale al calcular."""
        for recibo in self:
            recibo.l10n_co_ne_aviso_dias = False
            if not (isinstance(recibo.id, int) and recibo.state in ('draft', 'verify') and recibo.worked_days_line_ids and recibo.contract_id):
                continue
            avisos = []
            if recibo._ne_desglosa_por_fecha():
                try:
                    clasificacion = recibo._ne_clasificar_fechas()
                except UserError:
                    clasificacion = None    # sin el tipo «Asistencia» no hay desglose: el error ya sale al calcular los días, no al abrir el formulario
                if clasificacion and clasificacion['sin_entrada']:
                    fechas = ', '.join(dia.strftime('%d/%m/%Y') for dia in sorted(clasificacion['sin_entrada']))
                    avisos.append(_(
                        'No hay entrada de trabajo de %(empleado)s en: %(fechas)s. Esos días se pagan como laborados con el horario del contrato. '
                        'Revise las entradas de trabajo de esas fechas (Nómina > Entradas de trabajo) y use «Recalcular la hoja entera» en el menú Acciones.',
                        empleado=recibo.employee_id.name, fechas=fechas))
            if recibo._ne_aplica_dias_por_asistencia():
                try:
                    avisos.extend(recibo._ne_avisos_ausencias_desactualizadas())
                except UserError:
                    pass
            recibo.l10n_co_ne_aviso_dias = ' '.join(avisos) or False

    l10n_co_ne_aviso_no_salarial = fields.Char(
        string='Aviso de habitualidad de pagos no salariales', compute='_compute_ne_aviso_no_salarial',
        help='Solo para las vistas: aviso (no bloquea ni cambia el cálculo) cuando un concepto no salarial vigilado se pagó en cada uno de los últimos N meses calendario.')

    @api.depends('line_ids', 'line_ids.total', 'date_to', 'employee_id', 'company_id', 'state')
    def _compute_ne_aviso_no_salarial(self):
        """.301 (doc 76 §2.2): ver ``_ne_avisos_habitualidad``. Un parámetro que falta NO se calla (sería un valor por defecto silencioso) ni bloquea el formulario: el
        aviso dice qué falta."""
        for recibo in self:
            recibo.l10n_co_ne_aviso_no_salarial = False
            if not (isinstance(recibo.id, int) and recibo.date_to and recibo.employee_id and recibo.line_ids):
                continue
            try:
                recibo.l10n_co_ne_aviso_no_salarial = ' '.join(recibo._ne_avisos_habitualidad()) or False
            except UserError as error:
                recibo.l10n_co_ne_aviso_no_salarial = error.args[0]

    l10n_co_ne_aviso_pacto = fields.Char(
        string='Aviso del pacto de desalarización', compute='_compute_ne_aviso_pacto',
        help='Solo para las vistas: aviso cuando el recibo trae un pago no salarial por pacto de desalarización y el empleado no tiene registrado el pacto o lo tiene sin el documento firmado.')

    @api.depends('line_ids', 'line_ids.total', 'date_to', 'employee_id', 'employee_id.l10n_co_pacto_ids', 'employee_id.l10n_co_pacto_ids.fecha_firma',
                 'employee_id.l10n_co_pacto_ids.fecha_fin', 'employee_id.l10n_co_pacto_ids.salary_rule_id', 'employee_id.l10n_co_pacto_ids.attachment_ids')
    def _compute_ne_aviso_pacto(self):
        """.302 (doc 76 §2.3): ver ``l10n.co.employee.pacto``. SIEMPRE avisa, aunque el interruptor ``l10n_co_exigir_pacto_no_salarial`` esté en 0: así el dato
        que falta se ve sin bloquear a nadie. No lee el interruptor."""
        Pacto = self.env['l10n.co.employee.pacto']
        for recibo in self:
            recibo.l10n_co_ne_aviso_pacto = False
            if not (isinstance(recibo.id, int) and recibo.date_to and recibo.employee_id and recibo.line_ids):
                continue
            recibo.l10n_co_ne_aviso_pacto = ' '.join(Pacto._textos_sin_pacto(recibo)) or False

    def _ne_validar_pacto_no_salarial(self):
        """.302: al confirmar, un pago no salarial por pacto sin pacto del empleado es un error si el interruptor ``l10n_co_exigir_pacto_no_salarial`` vale 1."""
        self.env['l10n.co.employee.pacto']._validar_recibos(self)

    # ──────────────────────────────────────────────────────────────────
    # H-F1-06 (doc 87): validación EXPLÍCITA de la afiliación (EPS, AFP, Caja, ARL), independiente de la contabilidad
    # ──────────────────────────────────────────────────────────────────
    _NE_ESTADOS_AVISO_AFILIACION = ('draft', 'verify')       # estados del recibo en que se avisa (v18); el consultor v19 verifica los estados

    l10n_co_ne_aviso_afiliacion = fields.Char(
        string='Aviso de afiliación incompleta', compute='_compute_ne_aviso_afiliacion',
        help='Solo para las vistas: aviso (no bloquea) con lo que falta de la afiliación (EPS, AFP, Caja de Compensación y ARL) del empleado. Al confirmar el recibo es un error.')

    @api.depends('state', 'employee_id', 'contract_id', 'date_from', 'company_id',
                 'employee_id.l10n_co_pila_eps_id', 'employee_id.l10n_co_pila_afp_id', 'employee_id.l10n_co_pila_ccf_id',
                 'contract_id.l10n_co_pila_tipo_cotizante', 'contract_id.l10n_co_pila_subtipo_cotizante',
                 'company_id.l10n_co_pila_arl_id', 'company_id.l10n_co_pila_ccf_id', 'company_id.l10n_co_pila_ccf_por_empleado')
    def _compute_ne_aviso_afiliacion(self):
        """Aviso en el recibo en borrador o en espera de un empleado de una compañía colombiana. Un parámetro que falta NO se calla ni bloquea el formulario: el aviso dice qué falta."""
        for recibo in self:
            recibo.l10n_co_ne_aviso_afiliacion = False
            if not (isinstance(recibo.id, int) and recibo.state in self._NE_ESTADOS_AVISO_AFILIACION and recibo.employee_id and recibo.contract_id and recibo._ne_solo_colombia()):
                continue
            try:
                faltan = recibo._ne_afiliaciones_faltantes()
            except UserError as error:
                recibo.l10n_co_ne_aviso_afiliacion = error.args[0]
                continue
            recibo.l10n_co_ne_aviso_afiliacion = recibo._ne_texto_afiliacion([(recibo.employee_id.name, faltan)], ' ') if faltan else False

    # Lineas que se pagan o cotizan con la base «IBC del mes anterior» (H-F1-11, doc 89): vacaciones y licencia remunerada de la nomina y de la liquidacion, y los dias de suspension (SLN); y la
    # incapacidad comun (H-F1-08), cuyo valor del dia sale del IBC del mes anterior al inicio de la inicial de su cadena.
    _NE_CODIGOS_BASE_IBC_MES_ANTERIOR = ('CO_VAC', 'CO_LIC_REM', 'CO_LIQ_VAC_DISFRUTADAS', 'CO_LIQ_LIC_REM', 'CO_IBC_SLN')
    _NE_CODIGO_INCAPACIDAD_COMUN = 'CO_INC_COMUN'

    l10n_co_ne_aviso_ibc_anterior = fields.Char(
        string='Aviso de IBC del mes anterior', compute='_compute_ne_aviso_ibc_anterior',
        help='Solo para las vistas: aviso (no bloquea) cuando el recibo trae vacaciones, licencia remunerada o días de suspensión y el empleado no tiene IBC del mes anterior (recibos confirmados): '
             'la base es el sueldo de la ficha del empleado.')

    def _ne_fechas_base_ibc_mes_anterior(self):
        """Fechas ``antes_de`` con las que este recibo consulta el IBC del mes anterior segun las lineas que trae (H-F1-11, H-F1-08): el inicio del tramo si paga vacaciones, licencia remunerada o SLN, y
        el inicio de la INICIAL de cada cadena de incapacidad comun (que puede ser de un mes anterior al del recibo)."""
        self.ensure_one()
        con_valor = {linea.code for linea in self.line_ids if linea.total}
        fechas = set()
        if con_valor & set(self._NE_CODIGOS_BASE_IBC_MES_ANTERIOR):
            fechas.add(self._ne_tramo_pagable_periodo()[0])
        if self._NE_CODIGO_INCAPACIDAD_COMUN in con_valor:
            # Sin cadenas (p. ej. una incapacidad por novedad manual, sin ausencia) el pago cuenta desde el inicio del recibo: la misma fecha que usa _ne_pago_ausencia_calendario.
            fechas.update(inicio for _previos, _dias, inicio in self._ne_incapacidad_cadenas() or [(0, 0, self._ne_tramo_pagable_periodo()[0])])
        return sorted(fechas)

    @api.depends('state', 'employee_id', 'contract_id', 'date_from', 'company_id', 'line_ids.code', 'line_ids.total')
    def _compute_ne_aviso_ibc_anterior(self):
        """H-F1-11 (doc 89, D-89-3): sin IBC del mes anterior la base de vacaciones, licencia remunerada, SLN e incapacidad comun (H-F1-08) es el sueldo de la ficha del empleado, y eso se AVISA (nunca
        en silencio). Solo en el recibo en borrador o en espera y solo si ya se calculo con alguna de esas lineas: el aviso refleja lo que el calculo uso. Una cadena de incapacidad con una anterior no
        aprobada no rompe el formulario: el aviso dice el error."""
        for recibo in self:
            recibo.l10n_co_ne_aviso_ibc_anterior = False
            if not (isinstance(recibo.id, int) and recibo.state in self._NE_ESTADOS_AVISO_AFILIACION and recibo.employee_id and recibo.contract_id and recibo._ne_solo_colombia()):
                continue
            try:
                recibo._ne_validar_inicio_liquidacion()
            except UserError:
                continue                  # una liquidacion mal fechada ya da su error al calcular: el aviso no lo repite ni lo pisa
            try:
                fechas = recibo._ne_fechas_base_ibc_mes_anterior()
            except UserError as error:
                recibo.l10n_co_ne_aviso_ibc_anterior = error.args[0]
                continue
            sin_base = {}
            for fecha in fechas:
                ibc, mes, con_base = recibo._ne_ibc_mes_anterior_datos(recibo.contract_id, antes_de=fecha)
                if not con_base:
                    sin_base[mes] = ibc
            if sin_base:
                recibo.l10n_co_ne_aviso_ibc_anterior = _(
                    'No hay IBC del mes anterior (%(meses)s) para el empleado %(empleado)s: la base de sus vacaciones, licencia remunerada, días de suspensión o incapacidad en este recibo es el '
                    'sueldo de la ficha del empleado (%(sueldo)s). Si el empleado tuvo recibos confirmados en ese mes, confírmelos y calcule este recibo de nuevo; si es su primer mes, es lo esperado.',
                    meses=', '.join(mes.strftime('%Y-%m') for mes in sorted(sin_base)), empleado=recibo.employee_id.name,
                    sueldo=format_amount(self.env, sin_base[min(sin_base)], recibo.company_id.currency_id))

    def _ne_afiliaciones_faltantes(self):
        """``[(etiqueta, nivel)]`` de lo que falta de la afiliación del empleado de este recibo (ver ``HrEmployee._ne_afiliaciones_faltantes``), con el tipo y el subtipo de cotizante del contrato y la fecha con que se resuelven los parámetros."""
        self.ensure_one()
        return self.employee_id._ne_afiliaciones_faltantes(self.contract_id, self._ne_fecha_parametros())

    def _ne_no_cotiza_pension(self):
        """¿En este recibo el empleado NO cotiza a pension? Verdadero si es un extranjero no obligado (marca de la ficha, ``l10n_co_ne_foreigner_no_pension``) o si la AFP no se exige para el tipo y el
        subtipo de cotizante de su contrato segun el parametro versionado ``l10n_co_afiliaciones_no_exigidas`` (pensionado: Ley 100/1993 art. 17, mod. Ley 797/2003 art. 4; aprendiz en etapa lectiva: solo
        salud y riesgos, Decreto 223/2026 art. 2.2.6.3.3.6). UNA sola decision para el aviso de afiliacion y para las reglas de pension del empleado y de la empresa, el FSP y los descuentos de pension de la
        liquidacion, la prima y la bonificacion (H-F1-06): no hay una segunda lista en las condiciones de las reglas, y quitar la fila del parametro vuelve a calcularlas. El IBC de salud y de las
        demas administradoras no cambia."""
        self.ensure_one()
        return bool(self.employee_id.l10n_co_ne_foreigner_no_pension) or not self.employee_id._ne_entidad_exigida('afp', self.contract_id, self._ne_fecha_parametros())

    @api.model
    def _ne_texto_afiliacion(self, por_empleado, separador):
        """Texto (traducible) de lo que falta: ``por_empleado`` = ``[(nombre, [(etiqueta, nivel)])]``. Una línea por empleado con TODOS sus campos y, al final, DÓNDE completarlos según el nivel
        de lo que falta (ficha del empleado o ajustes de la compañía). Único texto del aviso, del error al confirmar y del mensaje del asiento."""
        lineas = [_('%(empleado)s: falta %(campos)s.', empleado=nombre, campos=', '.join(etiqueta for etiqueta, _nivel in faltan)) for nombre, faltan in por_empleado]
        niveles = {nivel for _nombre, faltan in por_empleado for _etiqueta, nivel in faltan}
        dondes = []
        if 'empleado' in niveles:
            dondes.append(_('Complete lo del empleado en su ficha, pestaña %(pestana)s, grupo «%(grupo)s».', pestana=NE_EMPLEADO_PESTANA, grupo=NE_EMPLEADO_GRUPO_AFILIACION))
        if 'compañía' in niveles:
            dondes.append(_('Complete lo de la compañía en %(ubicacion)s.', ubicacion=NE_UBICACION_AJUSTES_PILA))
        return separador.join([_('Afiliación incompleta a la seguridad social.')] + lineas + dondes)

    def _ne_validar_afiliaciones(self):
        """Al confirmar: error si a algún empleado de una compañía colombiana le falta algo de la afiliación (aun cuando las reglas no tengan cuenta contable). Un solo error con una línea por
        empleado (un lote de recibos), con TODOS los campos que faltan y dónde completarlos."""
        por_empleado, vistos = [], set()
        for recibo in self._ne_solo_colombia():
            if recibo.employee_id.id in vistos:
                continue
            vistos.add(recibo.employee_id.id)
            faltan = recibo._ne_afiliaciones_faltantes()
            if faltan:
                por_empleado.append((recibo.employee_id.name, faltan))
        if por_empleado:
            raise UserError(self._ne_texto_afiliacion(por_empleado, '\n'))

    def _ne_meses_habitualidad(self):
        """Parámetro ``l10n_co_no_salarial_meses_habitualidad`` (``hr.rule.parameter``, 3 de fábrica, decisión del TL del 22-nov; 0 apaga el aviso). OBLIGATORIO: si falta hay
        un error claro que dice dónde crearlo; nunca se asume un valor."""
        self.ensure_one()
        fecha = self._ne_fecha_parametros()
        try:
            return int(self._rule_parameter('l10n_co_no_salarial_meses_habitualidad', fecha))
        except UserError:
            raise UserError(_(
                'Falta el parámetro de nómina «Colombia: Meses de Habitualidad de Pagos No Salariales» (código l10n_co_no_salarial_meses_habitualidad) para el %(fecha)s, '
                'que se necesita para avisar de los pagos no salariales que se repiten mes a mes. Actualice el módulo de nómina electrónica o créelo en Nómina > '
                'Configuración > Parámetros de reglas (cantidad de meses; 0 apaga el aviso).', fecha=fecha)) from None

    def _ne_avisos_habitualidad(self):
        """.301 (doc 76 §2.2, decisión del TL del 22-nov): avisos de los conceptos no salariales VIGILADOS (``DEV_NOSAL`` con ``l10n_co_ne_vigilar_habitualidad``) del recibo que
        se pagaron en cada uno de los últimos N meses calendario, contando el mes del recibo. El mes de un recibo es el de su ``date_to`` (un solo criterio de mes con el
        IBC mensual y la UGPP); un concepto cuenta en un mes si está en CUALQUIER recibo de ese mes (da igual que el pago sea quincenal o mensual), de cualquier
        estructura, del mismo empleado y compañía. Los meses anteriores y los otros recibos del mes cuentan solo hechos o pagados; el recibo que se mira cuenta en el estado
        en que esté. Solo informa: no cambia el cálculo. No hay norma que fije N (criterio del TL); lo que mueve el aviso es el art. 127 CST (el salario es lo que
        retribuye el servicio, se llame como se llame)."""
        self.ensure_one()
        vigiladas = self.line_ids.filtered(
            lambda l: l.total and l.salary_rule_id.category_id.code == 'DEV_NOSAL' and l.salary_rule_id.l10n_co_ne_vigilar_habitualidad)
        if not vigiladas:
            return []
        n = self._ne_meses_habitualidad()
        if n <= 0:
            return []
        indice = self.date_to.year * 12 + self.date_to.month - 1
        requeridos = [indice - k for k in range(n - 1, -1, -1)]               # de más antiguo a más reciente
        primero = date(requeridos[0] // 12, requeridos[0] % 12 + 1, 1)
        ultimo = date(self.date_to.year, self.date_to.month, calendar.monthrange(self.date_to.year, self.date_to.month)[1])
        codigos = vigiladas.mapped('code')
        lineas = self.env['hr.payslip.line'].sudo().search([
            ('slip_id.employee_id', '=', self.employee_id.id), ('slip_id.company_id', '=', self.company_id.id),
            ('code', 'in', codigos), ('total', '!=', 0),
            ('slip_id.date_to', '>=', primero), ('slip_id.date_to', '<=', ultimo),
            '|', ('slip_id', '=', self.id), ('slip_id.state', 'in', ('done', 'paid'))])
        meses_por_codigo = defaultdict(set)
        for linea in lineas:
            fecha = linea.slip_id.date_to
            meses_por_codigo[linea.code].add(fecha.year * 12 + fecha.month - 1)
        nombres = [format_date(self.env, date(i // 12, i % 12 + 1, 1), date_format='MMMM y') for i in requeridos]
        meses = nombres[0] if len(nombres) == 1 else _('%(lista)s y %(ultimo)s', lista=', '.join(nombres[:-1]), ultimo=nombres[-1])
        avisos, puestos = [], set()
        for linea in vigiladas.sorted(lambda l: (l.sequence, l.id)):
            if linea.code in puestos or not set(requeridos) <= meses_por_codigo[linea.code]:
                continue
            puestos.add(linea.code)
            avisos.append(_(
                'El concepto «%(concepto)s» (no salarial) se pagó a %(empleado)s en cada uno de los últimos %(n)s meses (%(meses)s).',
                concepto=linea.salary_rule_id.name, empleado=self.employee_id.name, n=n, meses=meses))
        if avisos:
            avisos.append(_('Un pago habitual que retribuye el servicio puede ser salario aunque se llame no salarial (art. 127 CST) y entrar al IBC. Revise su naturaleza.'))
        return avisos

    @api.depends('company_id.l10n_co_ne_environment', 'company_id.l10n_co_ne_certification_process')
    def _compute_ne_en_produccion(self):
        for slip in self:
            slip.l10n_co_ne_en_produccion = slip.company_id._ne_en_produccion() if slip.company_id else False

    def _ne_bloquear_si_va_en_documento(self, consulta=False):
        """El ciclo DIAN por recibo (generar, enviar, regenerar, consultar, ajustar) no corre en estos casos:

        1. El recibo se reporta en un documento mensual no migrado: sin esto el mismo pago se transmitiría dos veces,
           solo y dentro del mes (doc 53 §23.6).
        2. La compañía está en PRODUCCIÓN (D-5h/D-26c, doc 53 §27.1): en producción se reporta por documento mensual;
           el ciclo por recibo queda solo para habilitación. Excepción (D-R1): ``consulta=True`` (solo consultar, no
           transmite) se permite para un recibo de un documento *legacy* (ya transmitido por recibo) que siga pendiente.

        Un recibo sin documento o con documento *legacy* en habilitación sigue igual."""
        for slip in self:
            doc = slip.l10n_co_ne_documento_id
            if doc and not doc.legacy:
                raise UserError(_(
                    'El recibo "%(recibo)s" se reporta en el documento mensual "%(doc)s": se genera, se envía y se '
                    'consulta desde el documento, no por recibo.',
                    recibo=slip.display_name, doc=doc.display_name))
            if slip.company_id._ne_en_produccion() and not (consulta and doc and doc.legacy):
                raise UserError(_(
                    'La compañía "%(compania)s" está en Producción: la nómina electrónica se reporta por documento '
                    'mensual (acción "Enviar y Procesar" desde el documento), no por recibo. El recibo "%(recibo)s" no '
                    'se transmite por su cuenta.', compania=slip.company_id.name, recibo=slip.display_name))

    @api.constrains('l10n_co_ne_documento_id', 'company_id', 'employee_id', 'credit_note')
    def _check_documento_coherente(self):
        """Un recibo del documento mensual es de la misma compañía y empleado, y no es nota de crédito. Los
        documentos legacy (1:1 con lo ya transmitido) quedan fuera: conservan lo que hubo."""
        for slip in self:
            doc = slip.l10n_co_ne_documento_id
            if not doc or doc.legacy:
                continue
            if slip.company_id != doc.company_id or slip.employee_id != doc.employee_id:
                raise ValidationError(_(
                    'El recibo "%(recibo)s" no es de la compañía y el empleado del documento "%(doc)s".',
                    recibo=slip.display_name, doc=doc.display_name))
            if slip.credit_note:
                raise ValidationError(_(
                    'El recibo "%(recibo)s" es una nota de crédito y no puede ir en un documento mensual.',
                    recibo=slip.display_name))








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


    def _ne_validar_terceros_deducciones(self):
        """Sin valores por defecto silenciosos: una deduccion calculada
        (desde el contrato o desde un input manual) exige el contacto al que
        se paga lo retenido, definido en el contrato. E11 pieza 1A (.285): el
        campo del contrato sale del origen del tercero que la propia regla
        declara (``l10n_co_tercero_origen`` = ``contract_*``, tabla unica
        ``_NE_TERCERO_ORIGEN_CAMPO``); ya no hay una tabla por codigo de regla."""
        for slip in self:
            for line in slip.line_ids:
                origen = line.salary_rule_id.l10n_co_tercero_origen
                modelo, campo = self._NE_TERCERO_ORIGEN_CAMPO.get(origen, (None, None))
                if modelo != 'contract_id' or not line.total:
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

    def _ne_nombre_embargo(self):
        """Nombre de la línea de la regla ``CO_EMBARGO`` (``result_name`` nativo, ``hr_payroll/models/hr_salary_rule.py:92``): una sola línea suma todos los embargos del empleado, así que
        lleva el nombre del TIPO real (el del tipo de entrada: «Embargo - Civil / Comercial», «Embargo - Alimentos…», «Embargo - Cooperativa / Fondo») cuando solo hay uno abierto, y
        ``False`` (la regla usa su nombre neutro, «Embargo judicial») cuando hay varios o solo el ajuste manual. Antes se llamaba «Embargo Fiscal» siempre, que es el nombre del NODO
        del XML de la DIAN (``EmbargoFiscal``, que no cambia) y no de un embargo civil o de alimentos."""
        self.ensure_one()
        tipos = self.employee_id.salary_attachment_ids.filtered(
            lambda a: a.state == 'open' and a.other_input_type_id.code in self._NE_PRIORIDAD_EMBARGO).mapped('other_input_type_id')
        if len(tipos) != 1:
            return False
        return tipos.with_context(lang=self.employee_id.lang or self.env.lang).name

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

    # E-4 (doc 59 §21): guarda contra periodos de recibo demasiado largos. Desde M1-1 un periodo regular se paga completo (ya no
    # se recorta al mes de date_to), asi que un periodo mal digitado (p. ej. 04-ene a 15-abr por dia y mes invertidos) se
    # pagaria en silencio. Topes ESTRUCTURALES (no valores de decreto) por periodicidad del contrato, en dias calendario; es un
    # tope, no una igualdad: un periodo mas corto (ingreso o retiro a mitad de periodo) sigue pasando. LIMITE CONOCIDO: un
    # periodo de mes completo (1 a 30) en un contrato `semi-monthly`/quincenal pasa en un tipo `monthly` por diseno.
    _NE_MAX_DIAS_PERIODO = {
        'daily': 1, 'weekly': 7, 'bi-weekly': 16, 'semi-monthly': 16, 'monthly': 31, 'bi-monthly': 62,
        'quarterly': 92, 'semi-annually': 184, 'annually': 366}

    def _ne_validar_duracion_periodo(self):
        """UserError si un recibo de la estructura general (compania colombiana) cubre mas dias que el maximo de la
        periodicidad de su contrato. La liquidacion, la prima y la bonificacion quedan fuera (su periodo es otro)."""
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina', raise_if_not_found=False)
        for recibo in self._ne_solo_colombia().filtered(lambda s: s.struct_id == general and s.date_from and s.date_to):
            contrato = recibo.contract_id
            periodicidad = contrato.schedule_pay or contrato.structure_type_id.default_schedule_pay or 'monthly'
            maximo = self._NE_MAX_DIAS_PERIODO.get(periodicidad)
            dias = (recibo.date_to - recibo.date_from).days + 1
            if maximo and dias > maximo:
                etiqueta = dict(contrato._fields['schedule_pay'].selection).get(periodicidad, periodicidad)
                raise UserError(_(
                    'El recibo "%(recibo)s" de %(empleado)s va del %(desde)s al %(hasta)s (%(dias)s días) y la periodicidad de su '
                    'contrato es "%(periodicidad)s" (máximo %(maximo)s días por recibo). Revise las fechas "Desde" y "Hasta" del '
                    'recibo: lo más probable es que el día y el mes estén invertidos. Si el periodo es correcto, cambie la '
                    'periodicidad en el contrato o en el tipo de estructura.',
                    recibo=recibo.name or recibo.display_name, empleado=recibo.employee_id.name, desde=recibo.date_from,
                    hasta=recibo.date_to, dias=dias, periodicidad=etiqueta, maximo=maximo))

    def compute_sheet(self):
        self._ne_validar_duracion_periodo()
        colombia = self._ne_solo_colombia()
        colombia._ne_validar_terceros_attachments()
        # Cada recibo se calcula en el contexto de SU compania: los parametros (hr.rule.parameter,
        # por pais) y env.company salen de la compania del recibo, no de la activa en el selector.
        res = True
        for company in self.company_id:
            recibos = self.filtered(lambda s, c=company: s.company_id == c).with_company(company)
            # E11 pieza 2b (.288): el gancho de ``hr.salary.rule._compute_rule`` anota en este diccionario lo que SUGIRIÓ cada regla ajustada;
            # al terminar el cálculo se registra en cada ajuste (sugerido, aviso de cambio, «sin línea»).
            sugeridos = {}
            # .290: ``ne_calculo`` (token único por cálculo) NO es decoración. ``Environment.__new__`` (``odoo/api.py:570``) recorre
            # ``transaction.envs`` y devuelve el entorno que ya existe si ``(cr, uid, su, uid_origin, context)`` es IGUAL POR VALOR (``:584-587``): un
            # ``{}`` nuevo es igual a un ``{}`` viejo. Sin el token, el cálculo recibía el entorno del cálculo anterior con SU diccionario vacío: el
            # gancho de ``_compute_rule`` escribía lo sugerido allí y ``_ne_registrar_ajustes`` leía este ``sugeridos`` (vacío), así que el ajuste
            # quedaba «sin línea» aunque sí se aplicaba (N2 «co» de .289: test_02 y test_03). Con el token el contexto nunca coincide con el de otro
            # cálculo y el diccionario que lee el gancho es siempre este.
            res = super(HrPayslip, recibos.with_context(ne_sugeridos=sugeridos, ne_calculo=uuid.uuid4().hex)).compute_sheet()
            recibos._ne_registrar_ajustes(sugeridos)
            recibos._ne_regenerar_conceptos()
        colombia._ne_validar_terceros_deducciones()
        return res

    # ── Ajustes de la empresa (E11 pieza 2b, .288, doc 71c) ──────────────────────────────────────────────────────────────────────
    l10n_co_ajuste_ids = fields.One2many(
        'l10n.co.payslip.ajuste', 'slip_id', string='Ajustes de la empresa', copy=False,
        help='Ajustes que la empresa hizo a conceptos de este recibo. Se aplican dentro del cálculo y se conservan al recalcular. '
             'No se copian a otro recibo.')

    # ── «Conceptos de pago» (E11 pieza 3, .289, doc 71c §4 y §5) ─────────────────────────────────────────────────────────────────
    l10n_co_concepto_ids = fields.One2many(
        'l10n.co.payslip.concepto', 'slip_id', string='Conceptos de pago', copy=False,
        help='Vista de lo calculado: se regenera al final de cada cálculo. Editar una fila cambia su fuente (ajuste o novedad).')
    l10n_co_ne_usa_conceptos = fields.Boolean(
        related='struct_id.l10n_co_ne_conceptos_de_pago', string='La estructura usa «Conceptos de pago»', readonly=True)
    # E11 pieza 4a (.294, doc 74 §3): «Cálculo del salario» por secciones, de SOLO LECTURA (soporte de auditoría); se regenera junto a los conceptos.
    l10n_co_calculo_ids = fields.One2many(
        'l10n.co.payslip.calculo', 'slip_id', string='Cálculo del salario', copy=False,
        help='Vista de solo lectura de lo calculado que no está en «Conceptos de pago»: bases de cotización, aportes de la empresa y provisiones. Se '
             'regenera al final de cada cálculo. No se copia a otro recibo.')
    l10n_co_total_devengado = fields.Float(string='Total devengado', digits='Payroll', compute='_compute_l10n_co_totales')
    l10n_co_total_deducciones = fields.Float(string='Total deducciones', digits='Payroll', compute='_compute_l10n_co_totales')
    l10n_co_costo_empresa = fields.Float(
        string='Costo empresa', digits='Payroll', compute='_compute_l10n_co_totales',
        help='Aportes de la empresa y provisiones del recibo (las categorías con sección «Costo empresa»).')

    @api.depends('line_ids.total', 'line_ids.category_id', 'line_ids.appears_on_payslip')
    def _compute_l10n_co_totales(self):
        """Totales del pie de «Conceptos de pago», sobre las LÍNEAS del recibo (no sobre las filas): devengados y deducciones de las categorías
        con esa sección que se imprimen en el recibo, y costo de la empresa de las categorías con sección «costo_empresa»."""
        for recibo in self:
            devengado = deducciones = costo = 0.0
            for linea in recibo.line_ids:
                seccion = linea.category_id.l10n_co_ne_seccion_concepto
                if seccion == 'devengados' and linea.appears_on_payslip:
                    devengado += linea.total
                elif seccion == 'deducciones' and linea.appears_on_payslip:
                    deducciones += linea.total
                elif seccion == 'costo_empresa':
                    costo += linea.total
            recibo.l10n_co_total_devengado = devengado
            recibo.l10n_co_total_deducciones = deducciones
            recibo.l10n_co_costo_empresa = costo

    def _ne_regenerar_conceptos(self):
        """Regenera las filas de «Conceptos de pago» y de «Cálculo del salario» de estos recibos (solo los de estructuras que usan «Conceptos de pago»)."""
        self.env['l10n.co.payslip.concepto']._regenerar_de_recibos(self)
        self.env['l10n.co.payslip.calculo']._regenerar_de_recibos(self)

    def _ne_filas_de_concepto(self):
        """Filas de conceptos del recibo, en el orden de impresión (E11 pieza 5a, .291, doc 74 §4.2): FUENTE ÚNICA de la pestaña «Conceptos de pago»
        (``l10n.co.payslip.concepto._valores_del_recibo``) y de la colilla (``_ne_colilla``), para que no puedan diferir. Solo lee: no escribe ni
        recalcula nada.

        Una fila por línea del recibo que se imprime (``appears_on_payslip``), cuya categoría tiene sección ``devengados`` o ``deducciones``
        (``NE_SECCIONES_CONCEPTO``) y que tiene valor, o que la empresa ajustó (una línea ajustada a 0 sigue visible). Orden: la sección y,
        dentro de ella, la secuencia de la línea. Cada fila trae la sección, la línea y la regla, el ajuste de la empresa (si hay), la novedad que
        la origina (la i-ésima línea de un código se enlaza a la i-ésima novedad de ese código) y los valores ya resueltos: nombre, cantidad,
        unidad (la del tipo de novedad si lleva cantidad; si no, la de la regla), porcentaje, importe y total."""
        self.ensure_one()
        ajustes = {a.salary_rule_id.id: a for a in self.l10n_co_ajuste_ids}
        entradas = defaultdict(list)
        for entrada in self.input_line_ids.sorted(lambda i: (i.sequence, i.id)):
            entradas[entrada.code].append(entrada)
        secciones = dict(NE_SECCIONES_CONCEPTO)
        lineas = self.line_ids.filtered(
            lambda l: l.appears_on_payslip and l.category_id.l10n_co_ne_seccion_concepto in secciones
            and (l.total or l.salary_rule_id.id in ajustes)).sorted(lambda l: (l.sequence, l.id))
        vistos_por_codigo = defaultdict(int)
        filas = []
        for seccion in secciones:
            for linea in lineas.filtered(lambda l: l.category_id.l10n_co_ne_seccion_concepto == seccion):
                regla = linea.salary_rule_id
                posicion = vistos_por_codigo[regla.code]
                vistos_por_codigo[regla.code] += 1
                candidatas = entradas.get(regla.code, [])
                entrada = candidatas[posicion] if posicion < len(candidatas) else False
                tipo = entrada.input_type_id if entrada else self.env['hr.payslip.input.type']
                unidad = (tipo.l10n_co_ne_unidad if (tipo and tipo.is_quantity) else False) or regla.l10n_co_ne_unidad or False
                filas.append({
                    'seccion': seccion, 'linea': linea, 'regla': regla, 'ajuste': ajustes.get(regla.id), 'entrada': entrada, 'tipo': tipo,
                    'nombre': linea.name, 'cantidad': linea.quantity, 'unidad': unidad, 'porcentaje': linea.rate, 'importe': linea.amount,
                    'total': linea.total})
        return filas

    def _ne_colilla(self):
        """Datos de la tabla de la colilla (E11 pieza 5a, .291, doc 74 §4): las secciones «Devengados» y «Deducciones» con sus filas, los totales por
        sección y el neto. Sale de las LÍNEAS ya calculadas (``_ne_filas_de_concepto``) y del neto de la estructura (``_ne_pdf_neto``, que sin línea de
        neto lanza un error claro): no recalcula ni escribe. Es un comprobante INTERNO: no lleva el ajuste de la empresa (ni su nota de sugerido) ni
        el costo de la empresa; lo ajustado se imprime con su valor.

        Reglas de impresión (el diseño de «Conceptos de pago»): cantidad y unidad solo si la fila tiene unidad (un concepto monetario las deja
        vacías: ``False``); el porcentaje solo si es distinto de 100; las deducciones van con su signo (negativas). ``diferencia`` = neto - total
        devengado - total de deducciones (0 si la tabla cuadra con el neto, o si difiere en menos de un peso: redondeo): si no cuadra NO se oculta ni
        se bloquea la impresión (criterio del Frente 5: ``_ne_desglose()['diferencia']``), la plantilla la imprime como una fila «Diferencia sin
        clasificar»."""
        self.ensure_one()
        neto = self._ne_pdf_neto()
        unidades = dict(self.env['hr.salary.rule']._fields['l10n_co_ne_unidad']._description_selection(self.env))
        titulos = {'devengados': _('Devengados'), 'deducciones': _('Deducciones')}
        filas = self._ne_filas_de_concepto()
        secciones = []
        for seccion, _titulo in NE_SECCIONES_CONCEPTO:
            de_la_seccion = [f for f in filas if f['seccion'] == seccion]
            if not de_la_seccion:
                continue
            secciones.append({'seccion': seccion, 'titulo': titulos[seccion], 'filas': [{
                'nombre': f['nombre'],
                'cantidad': f['cantidad'] if f['unidad'] else False,
                'unidad': unidades.get(f['unidad'], '') if f['unidad'] else '',
                'porcentaje': False if float_is_zero(f['porcentaje'] - 100.0, precision_digits=4) else f['porcentaje'],
                'importe': f['importe'],
                'total': f['total'],
            } for f in de_la_seccion]})
        total_devengado = sum(f['total'] for f in filas if f['seccion'] == 'devengados')
        total_deducciones = sum(f['total'] for f in filas if f['seccion'] == 'deducciones')
        diferencia = self.company_id.currency_id.round(neto - total_devengado - total_deducciones)
        if abs(diferencia) < self.env['l10n.co.ne.documento']._NE_UMBRAL_CONCILIACION:
            diferencia = 0.0      # menos de un peso es redondeo (mismo umbral que la conciliación C4): no se imprime
        return {
            'secciones': secciones,
            'total_devengado': total_devengado,
            'total_deducciones': total_deducciones,
            'neto': neto,
            'diferencia': diferencia,
        }

    @api.model
    def _ne_generar_conceptos_pendientes(self):
        """Función de datos (corre en cada ``-u``): genera las filas de los recibos YA calculados de estructuras con «Conceptos de pago» que
        todavía no las tienen (los creados antes de .289 y los de una estructura recién activada). No recalcula ni cambia ningún valor: las
        filas son una vista de las líneas; un recibo hecho o pagado también las recibe, de solo lectura. Las de «Cálculo del salario» se regeneran además en los
        recibos en borrador o en espera (H-QA-040)."""
        recibos = self.sudo().with_context(active_test=False).search([
            ('struct_id.l10n_co_ne_conceptos_de_pago', '=', True), ('line_ids', '!=', False), ('l10n_co_concepto_ids', '=', False)])
        recibos._ne_regenerar_conceptos()
        # .294: los recibos que YA tienen sus conceptos (hechos con .289-.293) y todavía no las filas de «Cálculo del salario».
        # H-QA-040 (QA sobre .298, pedido del TL): además, los recibos en BORRADOR o EN ESPERA se regeneran siempre: una versión anterior de «Cálculo del salario» (la de
        # .294-.297 traía devengados y deducciones, la de .298 solo Bases, aportes y provisiones) quedaba con sus filas viejas porque ya tenía alguna. Regenerar solo lee las
        # líneas (no recalcula ni cambia un valor). Los HECHOS y PAGADOS son históricos: se quedan como están, salvo que no tengan ninguna fila.
        sin_calculo = self.sudo().with_context(active_test=False).search([
            ('struct_id.l10n_co_ne_conceptos_de_pago', '=', True), ('line_ids', '!=', False), '|', ('l10n_co_calculo_ids', '=', False),
            ('state', 'in', ('draft', 'verify'))])
        self.env['l10n.co.payslip.calculo']._regenerar_de_recibos(sin_calculo)
        # .298: los ajustes que quedaron sobre reglas que ya no son ajustables (la decisión de David del 21-nov por el riesgo UGPP): se retiran en los recibos
        # en borrador o en espera, con nota; los de recibos confirmados no se tocan. Corre DESPUÉS de cargar las reglas con su valor sembrado (manifest).
        self.env['l10n.co.payslip.ajuste']._retirar_de_reglas_no_ajustables()
        return True

    @api.model
    def _ne_comandos_cambian_conceptos(self, comandos):
        """¿Los comandos de ``l10n_co_concepto_ids`` de un ``write`` cambian lo que calcula la hoja? Altas, bajas, vínculos y reemplazos sí; un
        cambio solo de orden o de campos que no son valores (comando UPDATE) no."""
        for comando in comandos or ():
            if comando[0] == Command.UPDATE:
                if {'quantity', 'rate', 'amount', 'name', 'input_type_id'} & set(comando[2] or ()):
                    return True
            else:
                return True
        return False

    def _ne_estado_documento_ajuste(self):
        """Estado del documento DIAN del recibo (``False`` si no tiene). Una sola lectura para el bloqueo de ajustes (Q6 de TL)."""
        self.ensure_one()
        return self.l10n_co_ne_documento_state

    def _ne_registrar_ajustes(self, sugeridos):
        """Después de ``compute_sheet``: cada ajuste de estos recibos guarda lo sugerido de ese cálculo (``l10n.co.payslip.ajuste._registrar_calculo``)."""
        for recibo in self:
            for ajuste in recibo.sudo().l10n_co_ajuste_ids:
                ajuste._registrar_calculo(sugeridos)

    @api.model
    def _ne_comandos_cambian_novedades(self, comandos):
        """¿Los comandos de ``input_line_ids`` de un ``write`` cambian lo que calcula la hoja? Altas, bajas, vínculos y reemplazos sí; un cambio
        de ``name`` o ``sequence`` (comando UPDATE) no: los mismos campos que ``hr.payslip.input._NE_CAMPOS_QUE_RECALCULAN``."""
        campos = self.env['hr.payslip.input']._NE_CAMPOS_QUE_RECALCULAN
        for comando in comandos or ():
            if comando[0] == Command.UPDATE:
                if campos & set(comando[2] or ()):
                    return True
            else:
                return True
        return False

    def write(self, vals):
        """.286: el formulario guarda las novedades con ``write({'input_line_ids': [...]})``; durante ese ``write`` el campo está protegido y el
        recálculo de ``hr.payslip.input`` se salta (ver ``_ne_recalcular_hoja_por_novedad``). Se recalcula aquí, una vez, al terminar el
        ``write``. Las novedades creadas por el ORM directo (fuera de este ``write``) siguen recalculando desde ``hr.payslip.input``."""
        res = super().write(vals)
        if ('input_line_ids' in vals and self._ne_comandos_cambian_novedades(vals['input_line_ids'])) or (
                'l10n_co_concepto_ids' in vals and self._ne_comandos_cambian_conceptos(vals['l10n_co_concepto_ids'])):
            self._ne_recalcular_hoja_por_novedad()
        return res

    def _ne_recalcular_hoja_por_novedad(self):
        """Recalcula la hoja de los recibos cuya novedad (``hr.payslip.input``) se creó, cambió o borró (.283, doc 68 §14; orden de David).

        Solo los recibos de compañía colombiana, en borrador o en espera (``compute_sheet`` ya exige eso, ``nat:597-614``), no editados a mano
        (``edited``: las copias de reembolso traen las líneas negadas y recalcularlas las borraría) y con la hoja YA calculada (``line_ids``):
        un borrador sin calcular no tiene nada viejo, y calcularlo lo pasaría a «en espera», gastaría un número de la secuencia y correría
        dentro de la creación del propio recibo (las novedades nacen en el ``create`` del recibo, en el asistente de liquidación y en
        ``_compute_input_line_ids``). Los días NO se tocan (``action_refresh_from_work_entries`` no se usa: no dependen de las novedades).

        No se recalcula con el contexto ``ne_sin_recalculo_hoja`` (cargas masivas; se enciende solo mientras se calcula aquí, contra la
        re-entrada), con ``import_file`` (importación: el lote queda sin recalcular, se calcula al final con «Calcular hoja») ni mientras Odoo
        calcula ``input_line_ids`` del recibo (embargos de ``hr.salary.attachment``).

        .286: ``input_line_ids`` también está PROTEGIDO durante el ``write`` del recibo que trae ese campo (``odoo/models.py:4774-4785``,
        ``:4798``), que es lo que manda el formulario (``web_save`` -> ``write``). Por eso las novedades guardadas desde el formulario no
        recalculaban: sus ``create``/``write``/``unlink`` caían dentro de ese ``write``, con el campo protegido. Ese camino lo cubre
        ``HrPayslip.write`` (abajo): recalcula UNA vez, después de ``super()``, cuando la protección ya terminó.

        Un error de ``compute_sheet`` (periodo inválido, terceros de embargos, reparto que no cuadra...) NO impide guardar la novedad: el
        recálculo corre en un savepoint, se revierte, la novedad se conserva y el recibo recibe una nota con el error y la instrucción de pulsar
        «Calcular hoja» (decisión de TL: así se puede corregir el monto que arreglaría el reparto)."""
        contexto = self.env.context
        if contexto.get('ne_sin_recalculo_hoja') or contexto.get('import_file'):
            return
        recibos = self.exists()._ne_solo_colombia().filtered(
            lambda r: r.state in ('draft', 'verify') and not r.edited and r.line_ids
            and not self.env.is_protected(r._fields['input_line_ids'], r))
        for recibo in recibos:
            try:
                with self.env.cr.savepoint():
                    recibo.with_context(ne_sin_recalculo_hoja=True).compute_sheet()
            except UserError as error:
                self.env.invalidate_all()
                recibo.message_post(
                    body=_('La hoja de cálculo no se pudo recalcular al cambiar una novedad: %(error)s. Hoja sin recalcular: corrija lo indicado '
                           'y pulse «Calcular hoja».', error=error.args[0] if error.args else error),
                    message_type='notification', subtype_xmlid='mail.mt_note')
                recibo._ne_regenerar_conceptos()          # las filas vuelven a mostrar lo que SÍ está en la hoja

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
            if origen in ('employee_eps', 'employee_afp', 'company_arl'):
                self._ne_validar_afiliaciones()      # H-F1-06: el MISMO error completo de la afiliación (empleado, TODOS los campos, dónde completarlos)
            # Si la afiliación está exceptuada o el origen es de otra entidad (contrato, compañía): mensaje en español con «empleado» o «compañía» y el nombre, no el modelo en inglés.
            if modelo == 'contract_id':
                donde = _('el contrato del empleado "%s"', self.employee_id.name)
            elif modelo == 'employee_id':
                donde = _('la ficha del empleado "%s"', self.employee_id.name)
            else:
                donde = _('la compañía "%s"', self.company_id.name)
            raise UserError(_(
                'No se puede generar el asiento de la nomina "%(nomina)s": '
                'la regla "%(regla)s" paga a un tercero y falta el campo '
                '"%(campo)s" en %(donde)s.',
                nomina=self.display_name, regla=line.name,
                campo=self[modelo]._fields[campo].string, donde=donde))
        return [(partner, 1.0)]

    def _ne_validar_cuenta_neto(self):
        """E-10 (doc 64, H-QA-030): la cuenta del neto va SOLO en la regla nativa ``NET`` de la estructura (el nativo identifica el neto
        por ese codigo: partner del empleado en la linea del asiento y boton «Pagar»); la regla del modulo (``CO_NETO``,
        ``CO_LIQ_NETO``, ``CO_PRIMA_NETO`` o ``CO_BON_NETO``) queda SIN cuenta. Con cuenta en las dos el asiento llevaria el neto dos
        veces (descuadre real): error claro que dice cual vaciar. Con cuenta solo en la regla del modulo (configuracion anterior) no se
        bloquea: el asiento sale como siempre y «Pagar» sigue sin habilitarse."""
        for recibo in self._ne_solo_colombia():
            reglas = recibo.struct_id.rule_ids.with_company(recibo.company_id)
            con_cuenta = reglas.filtered(lambda r: r.account_debit or r.account_credit)
            nativa = con_cuenta.filtered(lambda r: r.code == 'NET')
            del_modulo = con_cuenta.filtered(lambda r: r.code in recibo._NE_NETO_CODES)
            if nativa and del_modulo:
                raise UserError(_(
                    'La cuenta del neto está configurada en DOS reglas de la estructura "%(estructura)s" de la compañía '
                    '"%(compania)s": la regla nativa %(nativa)s («%(nombre_nativa)s») y la del módulo %(modulo)s («%(nombre_modulo)s»). '
                    'El asiento llevaría el neto dos veces. Deje la cuenta SOLO en la regla NET y vacíe la de %(modulo)s '
                    '(Nómina > Configuración > Nómina Colombia > Cuentas Contables).',
                    estructura=recibo.struct_id.name, compania=recibo.company_id.name,
                    nativa=nativa[0].code, nombre_nativa=nativa[0].name,
                    modulo=del_modulo[0].code, nombre_modulo=del_modulo[0].name))

    def _prepare_slip_lines(self, date, line_ids):
        self._ne_validar_cuenta_neto()
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
        colombia._ne_validar_duracion_periodo()
        colombia._ne_validar_sin_solape()
        colombia._ne_validar_cuenta_neto()
        colombia._ne_validar_pacto_no_salarial()
        colombia._ne_validar_afiliaciones()       # H-F1-06: la afiliación completa, aun sin cuenta contable en las reglas
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


    # Plantilla nativa de la colilla (hr_payroll): se resuelve SIEMPRE por xmlid, nunca "la primera" que devuelva la
    # base (doc 53 §23.17, 8b / D-G).
    NE_MAIL_TEMPLATE_XMLID = 'hr_payroll.mail_template_new_payslip'
    NE_REPORT_COMPROBANTE_XMLID = 'l10n_co_nomina_electronica.action_report_comprobante_pago'
    NE_MARCA_CORREO_COMPROBANTE = 'Comprobante de pago enviado por correo'

    @api.model
    def _ne_plantilla_colilla(self):
        """Plantilla de correo por defecto de la colilla (por xmlid). Si falta, error que nombra el xmlid."""
        plantilla = self.env.ref(self.NE_MAIL_TEMPLATE_XMLID, raise_if_not_found=False)
        if not plantilla:
            raise UserError(_(
                'No se encontró la plantilla de correo "%s" (la de la colilla de nómina). Instale o restaure la '
                'plantilla, o elija otra en el asistente.', self.NE_MAIL_TEMPLATE_XMLID))
        return plantilla

    def _ne_pdf_comprobante(self):
        """Adjunto PDF del comprobante de pago del GRUPO (``self`` = recibos del mismo pago): se REUTILIZA el existente
        (mismo nombre: fecha de pago y recibos del grupo) y, si no hay, se genera una sola vez. Se guarda en el primer
        recibo del grupo. Un grupo que cambia de recibos tiene otro nombre y por tanto otro PDF."""
        primero = self.sorted(lambda s: (s.date_to, s.id))[:1]
        fecha = primero._ne_fecha_pago()
        nombre = 'Comprobante_de_pago_%s_%s.pdf' % (fecha, '-'.join(str(i) for i in sorted(self.ids)))
        adjunto = self.env['ir.attachment'].search([
            ('res_model', '=', 'hr.payslip'), ('res_id', '=', primero.id), ('name', '=', nombre),
            ('mimetype', '=', 'application/pdf')], limit=1)
        if adjunto:
            return adjunto
        reporte = self.env.ref(self.NE_REPORT_COMPROBANTE_XMLID, raise_if_not_found=False)
        if not reporte:
            raise UserError(_(
                'No se encontró el reporte del comprobante de pago (%(xmlid)s): no se genera el PDF del recibo '
                '"%(recibo)s".', xmlid=self.NE_REPORT_COMPROBANTE_XMLID, recibo=primero.display_name))
        pdf, _tipo = self.env['ir.actions.report'].sudo()._render_qweb_pdf(reporte.id, self.ids)
        return self.env['ir.attachment'].create({
            'name': nombre, 'type': 'binary', 'datas': base64.b64encode(pdf), 'res_model': 'hr.payslip',
            'res_id': primero.id, 'mimetype': 'application/pdf'})

    def action_send_comprobante_email(self, template=None):
        """Envía UN correo con el comprobante de pago del grupo (``self`` = los recibos de UN mismo pago: mismo
        empleado y misma fecha de pago, ver ``_ne_comprobantes``) al correo del contacto de trabajo del empleado, por la
        cola nativa de correo. Independiente del estado DIAN: solo exige los recibos confirmados (hechos o pagados)."""
        self.company_id._ne_exigir_colombia()
        if len(self.employee_id) != 1:
            raise UserError(_('El comprobante de pago se envía por empleado: los recibos son de %s empleados.',
                              len(self.employee_id)))
        for recibo in self:
            if recibo.state not in ('done', 'paid'):
                raise UserError(_('El recibo "%s" no está confirmado (hecho o pagado): no se envía el comprobante.',
                                  recibo.display_name))
        empleado = self.employee_id
        correo = empleado.work_contact_id.email
        if not correo:
            raise UserError(_('El empleado %s no tiene correo en su contacto de trabajo.', empleado.name))
        template = template or self._ne_plantilla_colilla()
        adjunto = self._ne_pdf_comprobante()
        referencia = self.sorted(lambda s: (s.date_to, s.id))[:1]
        mail_id = template.send_mail(referencia.id, force_send=False, email_values={
            'email_to': correo, 'attachment_ids': [(6, 0, adjunto.ids)]})
        correo_en_cola = self.env['mail.mail'].sudo().browse(mail_id).exists()
        if not correo_en_cola:
            raise UserError(_('La plantilla "%(plantilla)s" no generó el correo del comprobante de pago de "%(recibo)s".',
                              plantilla=template.display_name, recibo=referencia.display_name))
        for recibo in self:
            recibo.message_post(
                body=_('%(marca)s a %(correo)s con la plantilla "%(plantilla)s".', marca=self.NE_MARCA_CORREO_COMPROBANTE,
                       correo=correo, plantilla=template.display_name),
                message_type='comment', subtype_xmlid='mail.mt_note')
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
                # Anexo §8.3.1: 360/30; el día de ingreso cuenta (D19, David 2026-11-11).
                'TiempoLaborado': str(
                    dian_utils.compute_worked_time_360(contract.date_start, self.date_to, inclusive=True)
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
    _NE_BASICO_CODES = ('CO_BASICO', 'CO_LIQ_SALARIOS')     # prima y bonificacion no tienen linea de sueldo: basic_wage queda en el nativo
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


    # Desglose del recibo para el comprobante de pago (Frente 5, C1): clasificación por el CONCEPTO DIAN de la regla
    # (``l10n_co_ne_dian_concept``, una sola fuente: el mismo dato que arma el XML; E11 pieza 1A, .285), ya no por lista de códigos.
    # Lo que no cae en ninguna columna va a "otras deducciones" (negativo) o queda en el devengado (positivo), de modo que
    # devengado - deducciones siempre se explica completo. Las claves son las columnas del desglose; los valores, los conceptos
    # del anexo técnico (valores de la selección ``l10n_co_ne_dian_concept``, no códigos de regla).
    _NE_DESGLOSE_CONCEPTO_DIAN = {
        'salud': 'Salud', 'pension': 'FondoPension', 'fsp': 'FondoSP', 'retencion': 'RetencionFuente'}

    def _ne_fecha_pago_o_falso(self):
        """Primera fecha de pago del recibo o False si no se puede resolver (sin fecha, sin fuente configurada o sin
        recibo hecho). No lanza: sirve para agrupar y para el desglose; quien exige la fecha usa ``_ne_fecha_pago``."""
        self.ensure_one()
        if self.state not in ('done', 'paid'):
            return False
        try:
            return self._ne_fecha_pago()
        except UserError:
            return False

    def _ne_grupo_de_pago(self):
        """Todos los recibos del MISMO pago que este: misma compañía, mismo empleado y misma primera fecha de pago
        (Frente 5, C2). No supone calendarios ni origen: quincena, prima, bonificación y liquidación pagadas el mismo
        día van juntas; pagadas otro día, aparte. Excluye notas de crédito y notas de ajuste por recibo (no son
        pagos). Un recibo sin fecha de pago no pertenece a ningún grupo."""
        self.ensure_one()
        fecha = self._ne_fecha_pago_o_falso()
        if not fecha:
            return self.browse()
        dominio = [('company_id', '=', self.company_id.id), ('employee_id', '=', self.employee_id.id),
                   ('state', 'in', ('done', 'paid')), ('credit_note', '=', False),
                   ('l10n_co_ne_is_adjustment', '=', False)]
        if self.company_id.l10n_co_ne_fuente_fecha_pago == 'recibo':
            candidatos = self.search(dominio + [('paid_date', '=', fecha)])
        else:
            candidatos = self.search(dominio)
        return candidatos.filtered(lambda s: s._ne_fecha_pago_o_falso() == fecha).sorted(
            lambda s: (s.date_to, s.id))

    @api.model
    def _ne_comprobantes(self, recibos):
        """Agrupa ``recibos`` en comprobantes de pago por (compañía, empleado, primera fecha de pago): cada grupo trae
        TODOS los recibos de ese pago, no solo los seleccionados (imprimir desde cualquiera trae el grupo completo).
        Devuelve ``{'grupos': [{'empleado', 'fecha_pago', 'recibos'}], 'sin_fecha': [(recibo, motivo)]}``: los recibos
        sin confirmar o sin fecha de pago no tienen comprobante agrupado (no se inventa una fecha; su colilla
        individual sí se imprime)."""
        resultado = {'grupos': [], 'sin_fecha': []}
        vistos = set()
        for recibo in recibos.sorted(lambda s: (s.company_id.id, s.employee_id.name or '', s.date_to, s.id)):
            if recibo.state not in ('done', 'paid'):
                resultado['sin_fecha'].append((recibo, _('El recibo "%s" no está confirmado (hecho o pagado).',
                                                         recibo.display_name)))
                continue
            fecha = recibo._ne_fecha_pago_o_falso()
            if not fecha:
                resultado['sin_fecha'].append((recibo, _(
                    'El recibo "%(recibo)s" (%(empleado)s) no tiene fecha de pago: registre la fecha de pago o '
                    'imprima su colilla individual.', recibo=recibo.display_name, empleado=recibo.employee_id.name)))
                continue
            clave = (recibo.company_id.id, recibo.employee_id.id, fecha)
            if clave in vistos:
                continue
            vistos.add(clave)
            resultado['grupos'].append({
                'empleado': recibo.employee_id, 'fecha_pago': fecha, 'recibos': recibo._ne_grupo_de_pago()})
        return resultado

    def _ne_desglose(self):
        """Desglose del recibo (Frente 5, C1): ``{recibo, origen, paid_date, devengado, deducciones, salud, pension, fsp,
        retencion, otras_deducciones, neto, diferencia}``. Todo sale de las líneas YA calculadas que imprime la colilla
        (``_ne_pdf_lineas``) y del neto de la estructura (``_ne_pdf_neto``): no recalcula nada ni escribe. Los importes
        de deducciones van en positivo. ``origen`` es el nombre de la estructura salarial. ``diferencia`` =
        devengado - deducciones - neto (0 si el recibo cuadra; si no, es lo que la conciliación debe explicar)."""
        self.ensure_one()
        lineas = self._ne_pdf_lineas()

        def deducido(columna):
            concepto = self._NE_DESGLOSE_CONCEPTO_DIAN[columna]
            return -sum(l.total for l in lineas if l.salary_rule_id.l10n_co_ne_dian_concept == concepto)

        devengado = sum(l.total for l in lineas if l.total > 0)
        deducciones = -sum(l.total for l in lineas if l.total < 0)
        salud = deducido('salud')
        pension = deducido('pension')
        fsp = deducido('fsp')
        retencion = deducido('retencion')
        neto = self._ne_pdf_neto()
        return {
            'recibo': self,
            'origen': self.struct_id.name,
            'paid_date': self._ne_fecha_pago_o_falso(),
            'devengado': devengado,
            'deducciones': deducciones,
            'salud': salud,
            'pension': pension,
            'fsp': fsp,
            'retencion': retencion,
            'otras_deducciones': deducciones - salud - pension - fsp - retencion,
            'neto': neto,
            'diferencia': devengado - deducciones - neto,
        }

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
            # E-3a (doc 59 §20.2): «Salario basico» de la lista = la linea de sueldo del modulo (convencion de 30 dias), no el
            # paid_amount nativo (que reparte el salario mensual entre las horas del periodo y solo coincide en un mes completo).
            sueldo = payslip.line_ids.filtered(lambda l: l.code in self._NE_BASICO_CODES)
            if sueldo:
                payslip.basic_wage = sum(sueldo.mapped('total'))

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

    def _ne_dias_comerciales(self, ini, fin):
        """Dias comerciales (mes de 30 dias) de [ini, fin] con extremos incluidos, para un tramo de UN mes o de VARIOS
        (M1-1, doc 61): suma por segmento de mes calendario de ``comercial(fin) - comercial(ini) + 1``. Dentro de un solo mes
        da lo mismo que antes; el 21-mar a 5-abr da 10 + 5 = 15. 0 si ini > fin. Unica fuente de la cuenta de dias
        comerciales de un periodo."""
        if ini > fin:
            return 0
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        total = 0
        anio, mes = ini.year, ini.month
        while (anio, mes) <= (fin.year, fin.month):
            primero = date(anio, mes, 1)
            ultimo = date(anio, mes, self._ne_dias_en_mes_calendario(anio, mes))
            seg_ini, seg_fin = max(ini, primero), min(fin, ultimo)
            total += self._ne_dia_comercial(seg_fin, dias_mes) - self._ne_dia_comercial(seg_ini, dias_mes) + 1
            anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        return total

    def _ne_es_liquidacion(self):
        """El recibo es de la estructura de liquidacion (date_from = inicio de contrato)."""
        self.ensure_one()
        return self.struct_id == self.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion', raise_if_not_found=False)

    def _ne_es_semanal(self):
        """El empleado se paga por semana (periodicidad nativa del contrato o, sin ella, la de su tipo de estructura)."""
        self.ensure_one()
        contrato = self.contract_id
        return (contrato.schedule_pay or contrato.structure_type_id.default_schedule_pay) == 'weekly'

    def _ne_contar_dias(self, ini, fin):
        """Dias de [ini, fin] segun la periodicidad: SEMANAL = dias calendario (7 por semana; David 2026-11-14, valor del dia =
        salario / 30), el resto mes comercial de 30 dias (``_ne_dias_comerciales``). La liquidacion siempre cuenta dias
        comerciales (un mes completo = 30). Unica fuente de dias de un tramo."""
        self.ensure_one()
        if ini > fin:
            return 0
        if self._ne_es_semanal() and not self._ne_es_liquidacion():
            return (fin - ini).days + 1
        return self._ne_dias_comerciales(ini, fin)

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

    def _ne_resultado_retefuente(self, categories):
        """Resultado de la depuracion de la retencion en la fuente de la NOMINA GENERAL (el dict de ``l10n.co.retefuente.uvt.compute_retefuente``): UN solo lugar que arma las entradas -- ingreso bruto
        (categoria GROSS o el sueldo), IBC de pension y salud (DEV_SAL, o el sueldo por el factor del integral) -- y llama a la depuracion. Lo usan las reglas CO_RETEFUENTE, CO_EXENTO_PENSION_AFC y
        CO_RETEFUENTE_EXCESO_LIMITE (antes cada una copiaba las entradas: H-F1-02). Sin configuracion de retencion del anio, el error de ``_ne_retefuente_config``."""
        self.ensure_one()
        contract = self.contract_id
        gross = categories['GROSS'] if categories.get('GROSS') else contract.wage
        ibc = categories.get('DEV_SAL', contract.wage)
        if contract.l10n_co_ne_integral_salary:
            ibc = contract.wage * self._rule_parameter('l10n_co_factor_integral_salary', self.date_from)
        return self._ne_retefuente_config().compute_retefuente(
            self.employee_id, gross, ibc, ibc, self.employee_id.company_id, contract=contract, payslip=self)

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

    def _ne_fechas_pago(self):
        """Fechas de pago del recibo (ordenadas y distintas): UNICO accesor del módulo (doc 53 §20.3).

        La fuente es un ajuste de la COMPAÑÍA, nunca por registro (Ajustes > Nómina, sin valor por defecto):
        'recibo' -> la fecha de pago del recibo (acción Registrar fecha de pago); 'contabilidad' -> las fechas de los pagos
        conciliados del asiento del recibo. Sin fecha no se supone ninguna: error claro."""
        self.ensure_one()
        fuente = self.company_id.l10n_co_ne_fuente_fecha_pago
        if not fuente:
            raise UserError(_(
                'La compañía "%(compania)s" no tiene definida la fuente de la fecha de pago. Elíjala en Ajustes > '
                'Nómina > "Fuente de la fecha de pago".', compania=self.company_id.name))
        if fuente == 'recibo':
            if not self.paid_date:
                raise UserError(_(
                    'El recibo "%(recibo)s" (%(empleado)s) no tiene fecha de pago. Regístrela con la acción '
                    '"Registrar fecha de pago".', recibo=self.display_name, empleado=self.employee_id.display_name))
            return [fields.Date.to_date(self.paid_date)]
        fechas = self._ne_fechas_pagos_contables()
        if not fechas:
            raise UserError(_(
                'El recibo "%(recibo)s" (%(empleado)s) no tiene pagos conciliados en Contabilidad: no se puede '
                'saber su fecha de pago. El pago debe conciliar la línea del neto del asiento (la cuenta del neto va en la regla '
                'NET, con el empleado como tercero).', recibo=self.display_name, empleado=self.employee_id.display_name))
        return fechas

    def _ne_fecha_pago(self):
        """Primera fecha de pago: define el mes del documento (Oficio DIAN 901476: pago o abono, lo primero)."""
        return self._ne_fechas_pago()[0]

    def _ne_lineas_del_neto(self):
        """Línea(s) del asiento del recibo que son el neto del empleado (E-10, doc 64): las de la cuenta de la regla nativa ``NET`` de
        la estructura con el empleado como tercero (``work_contact_id``; el nativo solo lo pone a la línea de la regla ``NET``). Sin
        cuenta en ``NET`` (configuración anterior, cuenta en ``CO_NETO``) no hay línea del neto identificable: vacío."""
        self.ensure_one()
        nativas = self.struct_id.rule_ids.with_company(self.company_id).filtered(lambda r: r.code == 'NET')
        cuentas = nativas.account_credit | nativas.account_debit
        if not cuentas:
            return self.move_id.line_ids.browse()
        contacto = self.employee_id.work_contact_id
        return self.move_id.line_ids.filtered(lambda l: l.account_id in cuentas and l.partner_id == contacto)

    def _ne_fechas_pagos_contables(self):
        """Fechas de los pagos contables (account.payment) conciliados con la LÍNEA DEL NETO del asiento del recibo (E-10, doc 64): un
        pago a un tercero del mismo asiento (EPS, AFP, DIAN) nunca fija la fecha de pago del recibo. Camino nativo por
        conciliaciones parciales (``matched_*``). Se verificó con un pago real en la compañía de prueba 2841 (QA, recibo 63693)."""
        self.ensure_one()
        lineas = self._ne_lineas_del_neto()
        contrapartes = lineas.matched_debit_ids.debit_move_id | lineas.matched_credit_ids.credit_move_id
        pagos = contrapartes.payment_id.filtered(lambda p: p.move_id.state == 'posted')
        return sorted({p.date for p in pagos})

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
        # M1-1 (doc 61): el recorte al mes de date_to es SOLO de la liquidacion (los meses anteriores ya se pagaron en
        # nominas regulares). Un periodo regular que cruza de mes (pagos los 5 y 20, semana que cruza) se paga completo.
        if self._ne_es_liquidacion() and (periodo_fin.year, periodo_fin.month) != (periodo_ini.year, periodo_ini.month):
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
        return self._ne_contar_dias(ini, fin)

    def _ne_rango_activo(self):
        """(ini, fin) del tramo pagable en que el contrato estuvo vigente (ini > fin si no hay ninguno). La fecha de ingreso y la de retiro
        recortan el rango. Fuente única de ``_ne_dias_bajo_contrato`` y del desglose por fecha (.284)."""
        self.ensure_one()
        contract = self.contract_id
        periodo_ini, periodo_fin = self._ne_tramo_pagable_periodo()
        contrato_fin = contract.date_end or periodo_fin
        return max(periodo_ini, contract.date_start), min(periodo_fin, contrato_fin)

    def _ne_dias_bajo_contrato(self):
        """Dias (mes comercial) del tramo pagable en que el contrato estuvo vigente.
        Delimita ING/RET: la fecha de ingreso y de retiro recortan el rango."""
        self.ensure_one()
        activo_ini, activo_fin = self._ne_rango_activo()
        if activo_ini > activo_fin:
            return 0
        return self._ne_contar_dias(activo_ini, activo_fin)

    def _ne_codigos_tipos_no_remunerados(self):
        """Códigos de tipo de entrada de trabajo de los tipos de ausencia marcados ``unpaid`` (sin continuidad de pago del empleador):
        ``_ne_dias_pagables`` los excluye siempre del básico, leyendo sus líneas de días. Fuente única de ese conjunto (.281)."""
        unpaid_types = self.env['hr.leave.type'].search([('unpaid', '=', True)])
        return set(unpaid_types.mapped('work_entry_type_id.code')) - {False}

    def _ne_dias_pagables(self, valores=None):
        """Días pagables del período -- misma convención de "mes comercial" colombiano que ya
        usa la regla salarial CO_BASICO (hr_salary_rule_co_basico, data/hr_payroll_structure_
        data.xml) y CO_AUX_TRANS para calcular el sueldo/auxilio. Única fuente para el sueldo
        Y para DiasTrabajados, sin importar si la estructura es mensual o de liquidación.

        ``valores`` (.280, solo lo pasa ``_ne_ajustar_dias_por_asistencia``): los diccionarios de las líneas de días que el nativo
        ACABA de calcular, antes de guardarlas. Sin él las ausencias se leen de ``worked_days_line_ids`` (lo de siempre); al generar
        las líneas ese campo está recién vaciado, así que la línea «Asistencia» necesita contar las ausencias desde la lista en
        construcción. Mismo cálculo, otra fuente de las ausencias: con las líneas guardadas el resultado es idéntico.

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

        unpaid_codes = self._ne_codigos_tipos_no_remunerados()
        # H-013 (2026-10-08, QA Bloque 4): vacaciones/licencias/incapacidades entraban como
        # novedades manuales (inputs CO_VAC/CO_LIC_REM/CO_LIC_NR/CO_INC_COMUN/CO_INC_LABORAL)
        # y el básico no descontaba esos días -- doble pago real (vacaciones 15 días: básico
        # de 30 días completo + vacaciones aparte). "unpaid" en Odoo no sirve para detectar
        # esto: significa "sin continuidad de pago del empleador", mientras que vacaciones/
        # incapacidad/licencia remunerada SÍ se pagan en Colombia, solo que por un concepto
        # distinto al básico (Art. 186 CST, Ley 100/1993, etc.). Por eso se excluyen SIEMPRE
        # estos códigos (data/l10n_co_ausencias_data.xml), sin importar su unpaid real.
        dias_excluidos_codes = unpaid_codes | _NOVEDAD_AUSENCIA_WORKED_DAYS_CODES
        dias_excluidos = self._ne_dias_habiles_excluidos(dias_excluidos_codes, valores=valores)
        # H-014 (2026-10-08, QA Bloque 5): CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL
        # se pagan en días CALENDARIO corridos (ver _ne_ausencia_calendario) -- se excluyen
        # del básico por la misma cuenta, nunca por worked_days (ahí solo existirían los
        # días que el calendario del contrato ya define como laborables, subcontando un
        # festivo o un día no laboral dentro de la ausencia).
        for codigo in _NOVEDAD_AUSENCIA_CALENDARIO_CODES:
            dias_excluidos += self._ne_ausencia_calendario(codigo)[0]
        return dias_bajo_contrato - dias_excluidos

    # ──────────────────────────────────────────────────────────────────────
    # .280 (doc 68, Fase 1): pestaña «Días trabajados» desde los días PAGADOS, no desde las horas de las entradas de trabajo
    # ──────────────────────────────────────────────────────────────────────
    # Defecto (QA, prenomina de abril de 2026 de Guapante, quincenal): el nativo reparte las horas de TODAS las entradas de trabajo del
    # periodo por tipo (``contract.get_work_hours``) y la pestaña mostraba «Festivo 2,05 + Descanso 2,05 + Asistencia 10,98 = 15,07
    # días» mientras el recibo pagaba 15 (``_ne_dias_pagables``). David pidió que «Asistencia» sea los días pagados y que el festivo y
    # el descanso NO trabajados no aparezcan. Las demás líneas (vacaciones, licencias, incapacidades, OUT) quedan como las calcula el
    # nativo: ``_ne_dias_habiles_excluidos`` y la UGPP las leen por código.
    def _ne_aplica_dias_por_asistencia(self):
        """True si las líneas de días de este recibo se rearman desde los días pagados: compañía colombiana, estructura general y sin
        crédito de tiempo (el crédito de tiempo del nativo mezcla dos calendarios y no aplica a Colombia). Las demás estructuras
        (liquidación, prima, bonificación) no usan líneas de días o no se tocan."""
        self.ensure_one()
        general = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina', raise_if_not_found=False)
        return bool(general and self.struct_id == general and self.company_id and self.company_id._ne_es_colombia()
                    and not self.contract_id.time_credit)

    def _ne_codigos_dias_ocultos(self):
        """Códigos de tipo de entrada de trabajo cuyas líneas NO se muestran en «Días trabajados» (parámetro
        ``l10n_co_dias_trabajados_ocultar``: «FEST» festivo y «DESCANSO» descanso). El código lo pone quien crea el tipo en cada base
        (el tipo «Festivo» no trae identificador de datos), así que no puede ir fijo en el código."""
        self.ensure_one()
        return set(self._rule_parameter('l10n_co_dias_trabajados_ocultar', self._ne_fecha_parametros()))

    def _ne_tipo_asistencia(self):
        """El tipo de entrada de trabajo «Asistencia» del nativo (código WORK100). Primero su identificador de datos (NO VERIFICADO en
        el servidor: no está en la copia de lectura) y, si no existe, el código WORK100, que es el que el nativo documenta para
        ``worked_days['WORK100']``. Sin ninguno hay un error claro: no se inventa una línea."""
        tipo = self.env.ref('hr_work_entry.work_entry_type_attendance', raise_if_not_found=False)
        if not tipo:
            tipo = self.env['hr.work.entry.type'].search([('code', '=', 'WORK100')], limit=1)
        if not tipo:
            raise UserError(_(
                'No existe el tipo de entrada de trabajo «Asistencia» (código WORK100), con el que se muestran los días pagados del '
                'recibo de %(empleado)s. Créelo en los tipos de entrada de trabajo (Configuración de Nómina).',
                empleado=self.employee_id.name))
        return tipo

    def _ne_tipos_dias_de_asistencia(self):
        """Ajuste de David a «Conceptos de pago» (22-nov, decisión del TL: opción B): los tipos de las líneas de días que, JUNTAS, son los días PAGADOS con el sueldo
        (``_ne_desglose_por_fecha``: «Asistencia» (WORK100), «Festivos trabajados», «Descansos remunerados» y «Ajuste mes comercial»; Σ días = ``_ne_dias_pagables``). La pestaña
        de días trabajados los sigue mostrando por separado; «Conceptos de pago» los junta en UNA fila «Asistencia». Los tipos de ausencia (vacaciones, licencias,
        incapacidades) NO entran. Sin valores por defecto silenciosos: un tipo que no existe en la base simplemente no suma."""
        self.ensure_one()
        tipos = self.env['hr.work.entry.type']
        try:
            tipos |= self._ne_tipo_asistencia()
        except UserError:
            pass                                   # sin el tipo «Asistencia» no hay desglose por fecha: el error ya sale al calcular los días
        for xmlid in ('hr_work_entry_type_co_festivo_trabajado', 'hr_work_entry_type_co_descanso_remunerado', 'hr_work_entry_type_co_ajuste_mes_comercial'):
            tipos |= self.env.ref('l10n_co_nomina_electronica.%s' % xmlid, raise_if_not_found=False) or tipos.browse()
        return tipos

    def _ne_nombre_dias_de_asistencia(self):
        """Nombre de la fila única «Asistencia» de «Conceptos de pago» (N2 «cu», 22-nov): el del TIPO «Asistencia» (WORK100), que Odoo traduce al idioma del usuario, sin importar
        qué tipos junte la fila ni cuál sea la primera línea: el nombre de una línea de días puede ser el nativo con « (Half-Day)» (``hr_payslip_worked_days.py:49-53``) o el de
        «Festivos trabajados»/«Descansos remunerados» si «Asistencia» no tiene días. Sin el tipo en la base (no hay desglose por fecha: ``_ne_tipos_dias_de_asistencia``) se usa
        el texto traducible «Asistencia»."""
        self.ensure_one()
        try:
            return self._ne_tipo_asistencia().name
        except UserError:
            return _('Asistencia')

    def _ne_ajustar_dias_por_asistencia(self, valores):
        """Rearma la lista de líneas de días que calculó el nativo (``valores``: diccionarios con ``work_entry_type_id``, ``sequence``,
        ``number_of_days`` y ``number_of_hours``):

        1. «Asistencia» (WORK100) pasa a ser UNA sola línea, la primera, con los días PAGADOS (``_ne_dias_pagables``: lo mismo que paga
           CO_BASICO y que va al XML como DiasTrabajados) y como HORAS las que el nativo ya tenía en «Asistencia» MÁS las de los tipos
           ocultos (festivo, descanso). Así el total de horas del recibo (``sum_worked_hours``, el denominador de ``amount``) y la suma de
           los importes de las líneas (= ``BASIC``, que alimenta ``GROSS`` y la base de retención) quedan IDÉNTICOS a los del nativo, con y
           sin línea OUT: lo que se corrige es lo que se MUESTRA (días y nombres de líneas), no la plata. La línea lleva ``name`` explícito:
           el nombre nativo agrega « (Half-Day)» cuando horas/días < horas por día (``hr_payslip_worked_days.py:49-53``) y aquí lo hace
           casi siempre. Sin días pagados pero con horas (festivo o descanso en un periodo de ausencias) la línea se conserva con 0 días
           para no cambiar el total de horas; sin ninguno de los dos no hay línea.
        2. Los tipos del parámetro ``l10n_co_dias_trabajados_ocultar`` (festivo, descanso) se quitan.
        3. Las líneas de las 4 ausencias de días CALENDARIO (incapacidad común y laboral, maternidad, paternidad: ``_NOVEDAD_AUSENCIA_
           CALENDARIO_CODES``) muestran los días que realmente se pagan (``_ne_ausencia_calendario``, recortados al periodo), no horas ÷
           horas por día del nativo (3,07 en vez de 3; 1,98 si la ausencia cruza el día de descanso); solo se muestra: el pago sale de las
           fechas de la ausencia y estas líneas no se leen (.281). Las horas no se tocan, así que ``amount`` y ``BASIC`` no cambian. No se
           reemplaza la línea si no hay ausencia validada (entradas de trabajo sueltas) ni si el tipo es ``unpaid`` (su código SÍ entra a
           ``_ne_dias_habiles_excluidos`` y el cambio movería el pago).
        4. .300 (E2b): las vacaciones, licencias remuneradas y sin sueldo (y los tipos sin sueldo) cuentan sus días por FECHA con entrada de la ausencia
           (``_ne_dias_ausencia_por_fecha``), no horas ÷ horas por día del nativo (un domingo de 7 h en un horario de 44 h en 6 días se pagaba 0,95 días);
           las horas no se tocan. Todo lo demás se conserva igual y en su orden.

        .284 (E2a): en un recibo que se desglosa por fecha (``_ne_desglosa_por_fecha``) el punto 1 se reparte en «Asistencia» (días laborados),
        «Festivos trabajados», «Descansos remunerados» y «Ajuste mes comercial» (``_ne_desglose_por_fecha``); los días siguen sumando los
        pagados y las horas, las mismas. Con otra fuente de entradas queda UNA línea como en .282.

        La línea «OUT» (ingreso o retiro a mitad del periodo) la agrega el nativo DESPUÉS de este método y no se toca."""
        self.ensure_one()
        tipos = self.env['hr.work.entry.type'].browse([valor['work_entry_type_id'] for valor in valores])
        codigo_por_tipo = {tipo.id: tipo.code for tipo in tipos}
        nombre_por_tipo = {tipo.id: tipo.name for tipo in tipos}
        asistencia = self._ne_tipo_asistencia()
        ocultos = self._ne_codigos_dias_ocultos()
        no_remunerados = self._ne_codigos_tipos_no_remunerados()
        # .300 (E2b): las ausencias de días hábiles se cuentan por FECHA ANTES de calcular los días pagables (que las resta leyendo estas líneas).
        valores = self._ne_dias_ausencia_por_fecha(valores, codigo_por_tipo, nombre_por_tipo, no_remunerados)
        pagables = max(self._ne_dias_pagables(valores=valores), 0)
        horas_asistencia = sum(valor['number_of_hours'] for valor in valores if valor['work_entry_type_id'] == asistencia.id)
        horas_ocultas = sum(valor['number_of_hours'] for valor in valores
                            if valor['work_entry_type_id'] != asistencia.id and codigo_por_tipo[valor['work_entry_type_id']] in ocultos)
        horas = horas_asistencia + horas_ocultas
        resto = []
        for valor in valores:
            tipo_id = valor['work_entry_type_id']
            codigo = codigo_por_tipo[tipo_id]
            if tipo_id == asistencia.id or codigo in ocultos:
                continue
            if codigo in _NOVEDAD_AUSENCIA_CALENDARIO_CODES and codigo not in no_remunerados:
                dias_calendario = self._ne_ausencia_calendario(codigo)[0]
                if dias_calendario > 0:
                    valor = dict(valor, number_of_days=dias_calendario, name=nombre_por_tipo[tipo_id])
            resto.append(valor)
        if not pagables and not horas:
            return resto
        # .282: la línea «Asistencia» va PRIMERA en la pestaña. El orden en pantalla es ``_order = 'payslip_id, sequence'`` del nativo
        # (``hr_payslip_worked_days.py:11``) y todos los tipos traen la misma ``sequence`` (25): con empate el orden depende del desempate. Una
        # ``sequence`` menor que la de todas las demás líneas lo fija; solo se usa para ordenar (``sequence`` es de la línea, no del tipo).
        clasificacion = self._ne_clasificar_fechas() if self._ne_desglosa_por_fecha() else None
        if clasificacion is None:
            desglose = [(asistencia, pagables, horas)]
        else:
            desglose = self._ne_desglose_por_fecha(asistencia, pagables, horas_asistencia, horas_ocultas, clasificacion)
        # .284: las líneas del desglose van juntas y primero, en su orden: cada una con una ``sequence`` consecutiva menor que la de las demás.
        secuencia = min([valor.get('sequence', asistencia.sequence) for valor in resto] + [asistencia.sequence]) - len(desglose)
        lineas = [{
            'name': tipo.name,
            'sequence': secuencia + orden,
            'work_entry_type_id': tipo.id,
            'number_of_days': dias,
            'number_of_hours': horas_linea,
        } for orden, (tipo, dias, horas_linea) in enumerate(desglose)]
        return lineas + resto

    # ──────────────────────────────────────────────────────────────────
    # .284 (E2a, doc 68 §12): «Días trabajados» desglosado por FECHA
    # ──────────────────────────────────────────────────────────────────
    # La línea única «Asistencia» de .280 se reparte en: «Asistencia» (días laborados), «Festivos trabajados», «Descansos remunerados» y
    # «Ajuste mes comercial». SOLO se reparte lo que ya se mostraba (los días pagados y las horas del nativo): los días siguen sumando
    # ``_ne_dias_pagables`` y las horas, las mismas de .280, así que ni el pago, ni DiasTrabajados del XML, ni la suma de los importes de las
    # líneas (= BASIC, GROSS, base de retención) cambian. «Asistencia» es el RESIDUO (pagables - ajuste - festivos - descansos): el desglose
    # nunca puede dejar de sumar los días pagados, aunque una ausencia se cuente por horas ÷ horas por día (E2b la pasará a fechas).
    def _ne_desglosa_por_fecha(self):
        """True si este recibo se desglosa por fecha: el que ya rearma los días pagados (``_ne_aplica_dias_por_asistencia``), de un contrato cuyas
        entradas salen del calendario (``work_entry_source == 'calendar'``, la única fuente que existe en la base de Guapante: con ``attendance``
        o ``planning`` un día sin entrada puede ser una falta y no un descanso) y con un calendario laboral para consultar el horario."""
        self.ensure_one()
        contrato = self.contract_id
        return bool(self._ne_aplica_dias_por_asistencia() and contrato.work_entry_source == 'calendar'
                    and (contrato.resource_calendar_id or self.company_id.resource_calendar_id))

    def _ne_zona_calendario(self):
        """Zona horaria con la que se pasan las fechas de las entradas de trabajo (UTC en la base de datos) a fecha local: la del calendario
        del contrato, como el nativo (``nat:1196``)."""
        self.ensure_one()
        return _pytz_timezone(self.contract_id.resource_calendar_id.tz or self.employee_id.tz
                              or self.company_id.resource_calendar_id.tz or 'UTC')

    def _ne_clasificar_fechas(self):
        """Clasifica CADA fecha del tramo pagable (con el contrato vigente) del recibo. Devuelve ``None`` si no hay calendario ni tramo, o un
        diccionario de conjuntos de fechas:

        - ``ausentes``: fechas de una ausencia (vacación, licencias, incapacidades, tipos sin sueldo): salen de «Asistencia» porque sus días
          ya se descuentan en ``_ne_dias_pagables``.
        - ``festivos_trabajados``: fecha en un festivo global del calendario (``resource.calendar.leaves`` sin recurso) CON entrada de trabajo
          (el usuario cambió el tipo de la entrada del festivo a «Asistencia»). Una entrada de tipo «ausencia» (``is_leave``) en un festivo global
          es la que el calendario genera del festivo: cuenta como descanso aunque su tipo no esté en el parámetro de tipos ocultos.
        - ``laborados``: fecha con entrada de asistencia que no es festivo.
        - ``descansos``: entrada de un tipo oculto (``l10n_co_dias_trabajados_ocultar``: festivo, descanso), o fecha SIN entrada en la que el
          calendario no tiene jornada (el lunes de Guapante) o que es festivo global (festivo no trabajado).
        - ``sin_entrada``: fecha SIN entrada en la que el calendario SÍ tiene jornada (regla de David: si falta la entrada manda el horario del
          contrato; se paga como laborada y se avisa). Generar las entradas no toca las existentes ni las que ya cubrió el contrato
          (``generate_work_entries``, ``hr_contract.py:392-413``), por eso puede faltar una fecha suelta.

        Además ``horas_festivos_trabajados`` (suma de ``duration`` de las entradas de ASISTENCIA de esas fechas), ``dias_reales`` (fechas del tramo) y ``dias_comerciales``
        (los que paga el mes comercial: el 31 no cuenta, febrero se completa a 30).

        Solo cuentan entradas ``draft`` y ``validated`` (los estados que cuenta el nativo, enterprise ``hr_contract.py:283-289``). La fecha de una
        entrada es la de su INICIO en la zona del calendario del contrato."""
        self.ensure_one()
        contrato = self.contract_id
        calendario = contrato.resource_calendar_id or self.company_id.resource_calendar_id
        activo_ini, activo_fin = self._ne_rango_activo()
        if not calendario or activo_ini > activo_fin:
            return None
        zona = self._ne_zona_calendario()
        utc = _pytz_timezone('UTC')
        inicio = zona.localize(datetime.combine(activo_ini, datetime.min.time()))
        fin = zona.localize(datetime.combine(activo_fin, datetime.max.time()))
        inicio_utc = inicio.astimezone(utc).replace(tzinfo=None)
        fin_utc = fin.astimezone(utc).replace(tzinfo=None)

        def fecha_local(momento):
            return utc.localize(momento).astimezone(zona).date()

        festivos = set()
        for festivo in self.env['resource.calendar.leaves'].search([
                ('resource_id', '=', False), ('time_type', '=', 'leave'), ('calendar_id', 'in', [calendario.id, False]),
                ('company_id', 'in', [self.company_id.id, False]), ('date_from', '<=', fin_utc), ('date_to', '>=', inicio_utc)]):
            dia = fecha_local(festivo.date_from)
            ultimo = fecha_local(festivo.date_to - timedelta(microseconds=1))
            while dia <= ultimo:
                festivos.add(dia)
                dia += timedelta(days=1)

        asistencia = self._ne_tipo_asistencia()
        ocultos = self._ne_codigos_dias_ocultos()
        codigos_ausencia = (self._ne_codigos_tipos_no_remunerados() | _NOVEDAD_AUSENCIA_WORKED_DAYS_CODES
                            | _NOVEDAD_AUSENCIA_CALENDARIO_CODES)
        por_fecha = {}
        for entrada in self.env['hr.work.entry'].search([
                ('contract_id', '=', contrato.id), ('state', 'in', ('draft', 'validated')),
                ('date_start', '>=', inicio_utc), ('date_start', '<=', fin_utc)]):
            tipo = entrada.work_entry_type_id
            fecha = fecha_local(entrada.date_start)
            datos = por_fecha.setdefault(fecha, {'ausencia': False, 'oculto': False, 'trabajo': False, 'horas': 0.0})
            if tipo.code in codigos_ausencia:
                datos['ausencia'] = True
            elif tipo.code in ocultos or (tipo.is_leave and fecha in festivos):
                # Tipo oculto por parámetro, o una entrada de tipo «ausencia» en un festivo global: es la entrada que el calendario genera
                # del festivo (``hr_contract.py:49-53``, :66-77), no un día trabajado, aunque el tipo no esté en el parámetro.
                datos['oculto'] = True
            else:
                datos['trabajo'] = True
                if tipo == asistencia:
                    datos['horas'] += entrada.duration

        # Las 4 ausencias de días calendario cubren TODAS sus fechas (lunes a domingo, festivos incluidos): son las que ``_ne_dias_pagables``
        # descuenta con ``_ne_ausencia_calendario``.
        ausencia_calendario = set()
        for codigo in _NOVEDAD_AUSENCIA_CALENDARIO_CODES:
            for _ausencia, _dias, desde, hasta in self._ne_ausencia_calendario(codigo)[1]:
                ausencia_calendario.update(desde + timedelta(days=n) for n in range((hasta - desde).days + 1))

        # Fechas con jornada en el horario (sin descontar festivos). Misma forma de llamar al calendario que ``_ne_dias_habiles`` del documento.
        con_jornada = {a.astimezone(zona).date() for a, _b, _rec in calendario.with_company(self.company_id)._attendance_intervals_batch(
            inicio, fin)[False]}

        resultado = {clave: set() for clave in ('ausentes', 'festivos_trabajados', 'laborados', 'descansos', 'sin_entrada')}
        horas_festivos = 0.0
        dia = activo_ini
        while dia <= activo_fin:
            datos = por_fecha.get(dia)
            if dia in ausencia_calendario or (datos and datos['ausencia']):
                resultado['ausentes'].add(dia)
            elif datos and datos['trabajo']:
                if dia in festivos:
                    resultado['festivos_trabajados'].add(dia)
                    horas_festivos += datos['horas']
                else:
                    resultado['laborados'].add(dia)
            elif (datos and datos['oculto']) or dia in festivos or dia not in con_jornada:
                resultado['descansos'].add(dia)
            else:
                resultado['sin_entrada'].add(dia)
            dia += timedelta(days=1)
        resultado['horas_festivos_trabajados'] = horas_festivos
        resultado['dias_reales'] = (activo_fin - activo_ini).days + 1
        resultado['dias_comerciales'] = self._ne_dias_bajo_contrato()
        return resultado

    def _ne_desglose_por_fecha(self, asistencia, pagables, horas_asistencia, horas_ocultas, clasificacion):
        """Reparte los días pagados y las horas de «Asistencia» (las de .280) en líneas ``[(tipo, días, horas)]``, omitiendo las vacías:

        1. «Asistencia» (WORK100): los días laborados = pagables - ajuste - festivos trabajados - descansos (RESIDUO), con las horas de la
           asistencia menos las de los festivos trabajados.
        2. «Festivos trabajados»: una fecha por festivo con entrada de asistencia; horas = ``duration`` de esas entradas (sin pasar de las horas
           de asistencia del nativo).
        3. «Descansos remunerados»: descansos del horario y festivos no trabajados; horas = las de los tipos ocultos (festivo, descanso).
        4. «Ajuste mes comercial»: lo que separa las fechas reales del mes comercial (31 de mes: -1; febrero hasta el 28: +2). Sin horas.

        Σ días = ``pagables`` y Σ horas = ``horas_asistencia + horas_ocultas`` SIEMPRE. Si el residuo saliera negativo (más descansos y festivos
        que días pagables: una ausencia contada por horas ÷ horas por día en un periodo casi todo de ausencias) se recortan primero los descansos,
        luego los festivos y por último se mueve lo que falte al ajuste; así «Asistencia» nunca queda con días negativos."""
        self.ensure_one()
        ref = self.env.ref
        festivos = float(len(clasificacion['festivos_trabajados']))
        descansos = float(len(clasificacion['descansos']))
        ajuste = float(clasificacion['dias_comerciales'] - clasificacion['dias_reales'])
        horas_festivos = max(min(clasificacion['horas_festivos_trabajados'], horas_asistencia), 0.0)
        laborados = pagables - ajuste - festivos - descansos
        if laborados < 0:
            exceso = -laborados
            quitar = min(descansos, exceso)
            descansos -= quitar
            exceso -= quitar
            quitar = min(festivos, exceso)
            festivos -= quitar
            exceso -= quitar
            ajuste -= exceso
            laborados = 0.0
        lineas = (
            (asistencia, laborados, horas_asistencia - horas_festivos),
            (ref('l10n_co_nomina_electronica.hr_work_entry_type_co_festivo_trabajado'), festivos, horas_festivos),
            (ref('l10n_co_nomina_electronica.hr_work_entry_type_co_descanso_remunerado'), descansos, horas_ocultas),
            (ref('l10n_co_nomina_electronica.hr_work_entry_type_co_ajuste_mes_comercial'), ajuste, 0.0),
        )
        return [(tipo, dias, horas) for tipo, dias, horas in lineas if dias or horas]

    def _get_worked_day_lines_values(self, domain=None):
        """Punto de extensión nativo de las líneas de días (``hr.payslip._get_worked_day_lines_values``): ver
        ``_ne_ajustar_dias_por_asistencia``. Con ``domain`` (solo lo usa el crédito de tiempo del nativo) no se toca."""
        valores = super()._get_worked_day_lines_values(domain=domain)
        if domain or not self._ne_aplica_dias_por_asistencia():
            return valores
        return self._ne_ajustar_dias_por_asistencia(valores)

    def _ne_base_prestacional(self, result_rules, campo):
        """.303 (doc 78): base devengada de las provisiones de prestaciones = suma de lo que pagan en ESTE recibo las reglas ya calculadas con la marca ``campo``
        (``l10n_co_ne_base_prima_cesantias`` o ``l10n_co_ne_base_vacaciones``; datos planos por regla, sembrados en el XML: sin lista de códigos aquí). La fracción del periodo
        (mes, quincena, semana, ingreso a mitad de mes), las ausencias sin pago y el auxilio de transporte por días ya vienen en lo devengado: reemplaza al factor de periodo de
        .279 (``_ne_factor_provision_periodo``), que provisionaba sobre el sueldo del contrato. Los ajustes de la empresa suman por la cascada del motor (``result_rules``).

        Una regla de la estructura que aún no se calcula (o que no aplica) no suma: según el motor ``result_rules`` trae el código o no."""
        self.ensure_one()
        # La estructura NO hereda (en Odoo 18 ``hr.payroll.structure`` no tiene ``parent_id``: la N2 «ct» dio 280 errores por ``AttributeError`` al subir por padres, igual que
        # la regresión «bu» del 16-nov): las reglas con la marca son las de la estructura del recibo.
        total = 0.0
        for regla in self.struct_id.rule_ids.filtered(lambda r: r[campo]):
            try:
                total += result_rules[regla.code]['total']
            except (KeyError, TypeError):
                continue
        return total

    def _ne_pago_ausencia_calendario(self, codigo, dias, previos=None):
        """Valor a pagar por `dias` calendario corridos de una ausencia de pago por el empleador
        o por terceros: CO_INC_COMUN, CO_INC_LABORAL, CO_LIC_MAT, CO_LIC_PAT. Unico lugar del
        calculo, compartido por las reglas de la nomina general y de la liquidacion.

        - CO_INC_COMUN (Decreto 780/2016 Art. 3.2.1.10 par. 1; H-013 paso 3): por tramos --
          los primeros dias_incapacidad_empleador al pct_incapacidad_empleador (66,67 %); hasta
          el limite 3-90 el pct_incapacidad_3_90 (EPS); mas alla el pct_incapacidad_91_mas.
          H-F1-08 (doc 84/89; Decreto 1427 de 2022, art. 2.2.3.3.1): el valor del dia sale del IBC del
          MES ANTERIOR al inicio de la incapacidad INICIAL de la cadena (``_ne_ibc_mes_anterior``), el
          mismo en todas sus prorrogas, NO del sueldo actual en cada recibo; sin IBC de ese mes, el
          sueldo (con aviso en el recibo).
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
        if codigo != 'CO_INC_COMUN':
            return self.contract_id.wage / dias_mes * dias
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

        def _por_dia(valor_dia, pct):
            return max(valor_dia * pct, smmlv_dia)

        def _pago_posiciones(previos, cantidad, inicio):
            """Pago de los dias que ocupan las posiciones previos+1 .. previos+cantidad DENTRO de
            la incapacidad (H-170): el tramo se cuenta desde su inicio, no desde el recibo. El valor
            del dia es el del IBC del mes anterior a ``inicio`` (la fecha de inicio de la INICIAL
            de la cadena; H-F1-08)."""
            valor_dia = self._ne_ibc_mes_anterior(self.contract_id, antes_de=inicio) / dias_mes
            ini, fin = previos, previos + cantidad

            def _solape(a, b):
                return max(0, min(fin, b) - max(ini, a))
            return (_solape(0, dias_emp) * _por_dia(valor_dia, pct_emp)
                    + _solape(dias_emp, limite_3_90) * _por_dia(valor_dia, pct_3_90)
                    + max(0, fin - max(ini, limite_3_90)) * _por_dia(valor_dia, pct_91_mas))

        inicio_recibo = self._ne_tramo_pagable_periodo()[0]
        if previos is not None:
            return _pago_posiciones(previos, dias, inicio_recibo)
        cadenas = self._ne_incapacidad_cadenas()
        if not cadenas or sum(en_periodo for _previos, en_periodo, _inicio in cadenas) != dias:
            # Sin ausencias que lo respalden (p. ej. input manual): la incapacidad empieza aqui.
            cadenas = [(0, dias, inicio_recibo)]
        return sum(_pago_posiciones(prev, en_periodo, inicio) for prev, en_periodo, inicio in cadenas)

    def _ne_incapacidad_cadenas(self):
        """[(dias_previos, dias_en_periodo, inicio_de_la_inicial)] de cada incapacidad comun -- con sus prorrogas -- que cae en el periodo del recibo (H-170; H-F1-01, doc 84; el inicio de la
        inicial es la fecha con la que se busca el IBC del mes anterior, H-F1-08).
        La cadena sale del vinculo EXPLICITO ``Prórroga de`` (``hr.leave.l10n_co_ne_prorroga_de_id``) que marca quien registra la incapacidad con el certificado de la EPS: ya NO se encadena por
        fechas, porque que dos incapacidades sean «la misma enfermedad o una relacionada» (Decreto 1427 de 2022, art. 2.2.3.3.2, par. 1) es un juicio medico que el modulo no puede hacer.
        Una incapacidad sin vinculo es la inicial de su propia cadena. dias_previos = dias CALENDARIO reales de la cadena anteriores al inicio del tramo del recibo: ocupan las posiciones
        1..previos, y los del recibo las siguientes (el dia 93 de una incapacidad es el 1-jun si empezo el 1-mar). Una prorroga cuya anterior NO esta aprobada no tiene posicion cierta: error claro."""
        self.ensure_one()
        _dias, detalle = self._ne_ausencia_calendario('CO_INC_COMUN')
        if not detalle:
            return []
        periodo_ini = self._ne_tramo_pagable_periodo()[0]
        tramo_ini = max(periodo_ini, self.contract_id.date_start)
        en_periodo = {leave.id: dias for leave, dias, _ini, _fin in detalle}
        cadenas = {}                # id de la inicial -> {'miembros': {id: leave}, 'inicial': leave} (la cadena es una lista: la inicial es el ultimo de la subida)
        for leave, _dias_leave, _ini, _fin in detalle:
            miembros, actual = [leave], leave
            while actual.l10n_co_ne_prorroga_de_id:
                actual = actual.l10n_co_ne_prorroga_de_id
                if actual.state != 'validate':
                    raise UserError(_(
                        'La incapacidad de %(empleado)s del %(desde)s al %(hasta)s es prórroga de la del %(a_desde)s al %(a_hasta)s, que no está aprobada (estado «%(estado)s»). '
                        'Sin la anterior no se sabe en qué posición de la cadena empieza esta (2 días del empleador, 3 a 90, 91 en adelante). Apruebe la anterior o quite el vínculo '
                        '«Prórroga de» de la ausencia (Ausencias > la incapacidad).',
                        empleado=self.employee_id.name, desde=leave.request_date_from, hasta=leave.request_date_to,
                        a_desde=actual.request_date_from, a_hasta=actual.request_date_to,
                        estado=dict(actual._fields['state']._description_selection(self.env)).get(actual.state, actual.state)))
                miembros.append(actual)
            cadena = cadenas.setdefault(miembros[-1].id, {'miembros': {}, 'inicial': miembros[-1]})
            for miembro in miembros:
                cadena['miembros'][miembro.id] = miembro
        resultado = []
        for cadena in cadenas.values():
            dias_periodo = sum(en_periodo.get(leave_id, 0) for leave_id in cadena['miembros'])
            previos = 0
            for leave in cadena['miembros'].values():
                fin = min(leave.request_date_to, tramo_ini - timedelta(days=1))
                if fin >= leave.request_date_from:
                    previos += (fin - leave.request_date_from).days + 1
            resultado.append((previos, dias_periodo, cadena['inicial'].request_date_from))
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

    def _ne_dias_habiles_excluidos(self, codigos, valores=None):
        """Dias HABILES de las ausencias de worked_days (CO_VAC, CO_LIC_REM, CO_LIC_NR y tipos
        'unpaid') que se excluyen del sueldo, acotados al tramo pagable.

        ``valores`` (.280): lista de diccionarios de líneas de días aún sin guardar (ver ``_ne_dias_pagables``); si se da, se suman
        esos en vez de ``worked_days_line_ids``. Solo cambia la fuente de la suma del recibo de un solo mes: el tramo de la
        liquidación sigue saliendo de ``_ne_ausencia_habil`` (hr.leave + hr.work.entry), que no lee las líneas.

        Un recibo de un solo mes: suma de worked_days, como siempre. Un recibo que cruza meses
        (Liquidacion: date_from = inicio de contrato, el sueldo es solo del ultimo mes):
        worked_days cubre toda la vida del contrato y restaria ausencias de meses ya pagados;
        se cuentan solo las del tramo (_ne_ausencia_habil con desde/hasta)."""
        self.ensure_one()
        tramo_ini, tramo_fin = self._ne_tramo_pagable_periodo()
        if tramo_ini == self.date_from:
            if valores is not None:
                codigo_por_tipo = {tipo.id: tipo.code for tipo in self.env['hr.work.entry.type'].browse(
                    [valor['work_entry_type_id'] for valor in valores])}
                return sum(valor['number_of_days'] for valor in valores
                           if codigo_por_tipo.get(valor['work_entry_type_id']) in codigos)
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

        .300 (E2b): es la ÚNICA fuente de los días de estas ausencias: las líneas de días del recibo (``_ne_dias_ausencia_por_fecha``), el pago, el IBC, la
        UGPP y el XML la leen. Cuenta FECHAS locales (zona del calendario) con entrada ``draft``/``validated`` de la ausencia; con el interruptor
        ``l10n_co_ausencia_fraccion_dia`` encendido, la fracción del día (horas de la ausencia ÷ horas de todas las entradas de esa fecha).
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

        # .300 (E2b, doc 72 §3): la fecha de una entrada es la de su INICIO en la zona del calendario del contrato (como ``_ne_clasificar_fechas``, E2a), no la
        # fecha UTC (un turno de 22:00 a 06:00 hora de Colombia cae en el día equivocado, y una entrada de las 22:00 del último día del periodo quedaba fuera), y solo
        # cuentan las entradas ``draft`` y ``validated`` (los estados que cuenta el nativo; una entrada ``conflict`` o ``cancelled`` de una ausencia validada ya no suma).
        por_fracciones = self._ne_ausencia_por_fracciones()
        zona = self._ne_zona_calendario()
        utc = _pytz_timezone('UTC')
        inicio_utc = zona.localize(datetime.combine(desde, datetime.min.time())).astimezone(utc).replace(tzinfo=None)
        fin_utc = zona.localize(datetime.combine(hasta, datetime.max.time())).astimezone(utc).replace(tzinfo=None)
        dominio = [
            ('employee_id', '=', self.employee_id.id), ('state', 'in', ('draft', 'validated')),
            ('date_start', '>=', inicio_utc), ('date_start', '<=', fin_utc)]
        WorkEntry = self.env['hr.work.entry']
        work_entries = WorkEntry.search(dominio + [('leave_id', 'in', leaves.ids)])

        def fecha_local(momento):
            return utc.localize(momento).astimezone(zona).date()

        # Solo con el interruptor de fracciones encendido: las horas de TODAS las entradas de cada fecha (el denominador de la fracción).
        horas_del_dia = defaultdict(float)
        if por_fracciones:
            for entry in WorkEntry.search(dominio):
                horas_del_dia[fecha_local(entry.date_start)] += entry.duration

        horas_de_la_ausencia = defaultdict(lambda: defaultdict(float))        # id de la ausencia -> {fecha local: horas de sus entradas}
        for entry in work_entries:
            horas_de_la_ausencia[entry.leave_id.id][fecha_local(entry.date_start)] += entry.duration

        detalle = []
        dias_totales = 0
        for leave in leaves:
            fechas = horas_de_la_ausencia.get(leave.id)
            if not fechas:
                continue
            if por_fracciones:
                dias = sum(min(1.0, horas / horas_del_dia[fecha]) if horas_del_dia[fecha] else 1.0 for fecha, horas in fechas.items())
            else:
                dias = len(fechas)                                           # días ENTEROS: una fecha con entrada de la ausencia es 1 día
            if dias > 0:
                ini = max(leave.request_date_from, desde)
                fin = min(leave.request_date_to, hasta)
                detalle.append((leave, dias, ini, fin))
                dias_totales += dias
        return dias_totales, detalle

    def _ne_ausencia_por_fracciones(self):
        """Interruptor ``l10n_co_ausencia_fraccion_dia`` (``hr.rule.parameter``, 0 de fábrica; .300, E2b): ¿las ausencias de días hábiles cuentan la FRACCIÓN
        de día? OBLIGATORIO: si falta el parámetro hay un error claro que dice dónde crearlo; nunca se asume un valor."""
        self.ensure_one()
        fecha = self._ne_fecha_parametros()
        try:
            return bool(self._rule_parameter('l10n_co_ausencia_fraccion_dia', fecha))
        except UserError:
            raise UserError(_(
                'Falta el parámetro de nómina «Colombia: Ausencias de Días Hábiles por Fracción de Día» (código l10n_co_ausencia_fraccion_dia) para el %(fecha)s, '
                'que se necesita para contar las vacaciones y licencias de %(empleado)s por fecha. Actualice el módulo de nómina electrónica o créelo en Nómina > '
                'Configuración > Parámetros de reglas (0 = días enteros, 1 = fracciones de día).',
                fecha=fecha, empleado=self.employee_id.name)) from None

    def _ne_dias_ausencia_por_fecha(self, valores, codigo_por_tipo, nombre_por_tipo, no_remunerados):
        """.300 (E2b, doc 72 §3): las líneas de vacaciones, licencias remuneradas y no remuneradas y tipos sin sueldo (los códigos que ``_ne_dias_pagables`` descuenta
        del básico leyendo sus líneas) cuentan los días por FECHA con entrada de la ausencia (``_ne_ausencia_habil_tramo``), no por horas ÷ horas por día del nativo.
        Solo cambian los DÍAS y el nombre de la línea (el nativo agrega « (Half-Day)» cuando horas/días < horas por día): las HORAS no se tocan, así que ``amount``, la
        suma de los importes (``BASIC``) y ``sum_worked_hours`` quedan idénticos. Sin una ausencia validada que respalde la línea (entradas sueltas o una novedad manual)
        queda como la calculó el nativo. ``CO_VAC``, ``CO_LIC_REM``, ``CO_BASICO``, ``CO_AUX_TRANS``, el IBC, la UGPP y el XML leen esta línea: quedan en fechas por herencia."""
        self.ensure_one()
        codigos = _NOVEDAD_AUSENCIA_WORKED_DAYS_CODES | no_remunerados
        resultado = []
        for valor in valores:
            tipo_id = valor['work_entry_type_id']
            codigo = codigo_por_tipo[tipo_id]
            if codigo in codigos:
                dias, detalle = self._ne_ausencia_habil_tramo(codigo)
                if detalle:
                    valor = dict(valor, number_of_days=dias, name=nombre_por_tipo[tipo_id])
            resultado.append(valor)
        return resultado

    def _ne_avisos_ausencias_desactualizadas(self):
        """.300 (E2b): textos de aviso (lista, vacía si todo coincide) cuando los días de una vacación o licencia de la pestaña «Días trabajados» no coinciden con las
        FECHAS de las entradas de trabajo (un recibo calculado antes de .300, o cuyas entradas cambiaron): hay que recalcular la hoja. Una consulta por código de ausencia."""
        self.ensure_one()
        avisos = []
        tipos = self.env['hr.work.entry.type']
        for codigo in sorted(_NOVEDAD_AUSENCIA_WORKED_DAYS_CODES | self._ne_codigos_tipos_no_remunerados()):
            dias, detalle = self._ne_ausencia_habil_tramo(codigo)
            if not detalle:
                continue
            en_la_pestana = sum(self.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.code == codigo).mapped('number_of_days'))
            if abs(en_la_pestana - dias) > 1e-6:
                tipo = tipos.search([('code', '=', codigo)], limit=1)
                avisos.append(_(
                    'Los días de «%(ausencia)s» en «Días trabajados» (%(pestana)s) no coinciden con las fechas de las entradas de trabajo de %(empleado)s (%(fechas)s). '
                    'Use «Recalcular la hoja entera» en el menú Acciones.',
                    ausencia=tipo.name or codigo, pestana='%g' % round(en_la_pestana, 4), fechas='%g' % round(dias, 4), empleado=self.employee_id.name))
        return avisos

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

    def _ne_sueldo_de_respaldo(self, contrato, fecha=None):
        """Sueldo MENSUAL con el que se reemplaza el IBC del mes anterior cuando el empleado no tiene IBC de ese mes (primer mes de contrato, base nueva o mes sin recibos confirmados).
        UNA sola funcion (consultor v19, doc 89): en v18 el sueldo vive en el contrato y ``fecha`` se ignora; en v19 sera el de la version vigente en esa fecha. Salario integral: el factor
        (``l10n_co_factor_integral_salary``, 70 %) del sueldo, como en ``_ne_ibc_salarial``. Quien lo use debe AVISAR (``_ne_aviso_ibc_mes_anterior``): nunca en silencio."""
        self.ensure_one()
        if contrato.l10n_co_ne_integral_salary:
            return contrato.wage * self._rule_parameter('l10n_co_factor_integral_salary', self._ne_fecha_parametros())
        return contrato.wage

    def _ne_ibc_mes_anterior_datos(self, contract, antes_de=None):
        """(ibc, mes, con_base): IBC del MES calendario anterior al mes de ``antes_de`` (por omision, el inicio de este recibo) -- H-F1-11, doc 89.
        Reemplaza a ``_ne_ultimo_ibc_anterior`` (H-017a), que leia la linea CO_SS_BASE_IBC de UN solo recibo: con nomina quincenal era medio mes y con semanal una semana, y la base de
        vacaciones, licencia remunerada y dias SLN salia de la mitad o menos. Decision del TL (22-nov, que conserva la de David del 10-nov: la incapacidad NO es salario, CST art. 192): la base es
        la SUMA de CO_SS_BASE_IBC de los recibos confirmados del empleado cuyo ultimo dia cae en ese mes, escalada a un mes comercial por los dias que la sustentan: ibc = suma x 30 / dias. Dias que la
        sustentan = dias de salud y pension (CO_DIAS_SP) menos los de suspension (SLN) y de incapacidad comun y laboral, que no entran a CO_SS_BASE_IBC (en el salario integral, que no los
        excluye, todos los dias). Asi un mes con incapacidad da el equivalente al salario y no al 66,67 %, y un mes incompleto (ingreso a mitad de mes) tambien se lleva a mes completo; la semanal
        (5 pagos de 7 = 35) se escala igual. NO usa ``ibc_sp`` del consolidado (que suma el valor pagado de la incapacidad, el exceso del 40 %, el piso y el techo). Sin base: el sueldo de
        respaldo y ``con_base`` en falso (el recibo muestra el aviso)."""
        self.ensure_one()
        referencia = antes_de or self.date_from
        mes = (referencia.replace(day=1) - timedelta(days=1)).replace(day=1)
        siguiente = (mes.replace(day=28) + timedelta(days=4)).replace(day=1)
        recibos = self.env['hr.payslip'].sudo().search([
            ('company_id', '=', self.company_id.id), ('employee_id', '=', self.employee_id.id), ('state', 'in', ('done', 'paid')),
            ('date_to', '>=', mes), ('date_to', '<', siguiente)])
        base = dias = 0.0
        for recibo in recibos:
            lineas_base = recibo.line_ids.filtered(lambda l: l.code == 'CO_SS_BASE_IBC')
            if not lineas_base:
                continue                              # p. ej. una liquidacion: su base salarial vive en otras reglas (hallazgo en la cola del F5)
            base += sum(lineas_base.mapped('total'))
            dias_recibo = sum(recibo.line_ids.filtered(lambda l: l.code == 'CO_DIAS_SP').mapped('total'))
            if not recibo.contract_id.l10n_co_ne_integral_salary:
                # Los dias de ESTE recibo ya confirmado, no los de las ausencias de hoy: una ausencia anulada o editada despues de confirmar no cambia la base que se pago. SLN: las worked_days
                # guardadas (``_ne_dias_sln``, un recibo de un solo mes); incapacidad: la CANTIDAD de las lineas CO_INC_COMUN y CO_INC_LABORAL (``result_qty = dias``, dias CALENDARIO que se
                # pagaron; las worked_days no sirven: cuentan dias habiles).
                dias_recibo -= recibo._ne_dias_sln() + sum(
                    recibo.line_ids.filtered(lambda l: l.code in _NOVEDAD_INCAPACIDAD_CODES).mapped('quantity'))
            dias += dias_recibo
        if base > 0 and dias > 0:
            return base * self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros()) / dias, mes, True
        return self._ne_sueldo_de_respaldo(contract, mes), mes, False

    def _ne_ibc_mes_anterior(self, contract, antes_de=None):
        """El IBC del mes anterior (ver ``_ne_ibc_mes_anterior_datos``): base de los dias de vacaciones, licencia remunerada y SLN (H-017a)."""
        return self._ne_ibc_mes_anterior_datos(contract, antes_de=antes_de)[0]

    def _ne_factor_dias_integral(self):
        """Fraccion del mes comercial que cubre este recibo, para prorratear el salario
        integral (que no sale de lineas de devengado sino del contrato). Con ella, dos
        recibos del mismo mes (nomina + liquidacion) suman UN IBC, no dos (H-017b)."""
        self.ensure_one()
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        return min(self._ne_dias_bajo_contrato(), dias_mes) / dias_mes

    def _ne_ibc_salarial(self, categories, contract, inputs, worked_days):
        """Parte SALARIAL del IBC (H-017a): DEV_SAL + vacaciones y licencia remunerada
        (base = IBC del mes anterior, prorrateado por dias). Salario integral:
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
                    ultimo_ibc = self._ne_ibc_mes_anterior(contract)
                ibc += (ultimo_ibc / dias_mes_comercial) * dias
        return ibc

    def _ne_ibc_incap(self, contract, result_rules, codigos=None):
        """Base de las ausencias de pago por tercero (maternidad/paternidad e
        incapacidades): el valor del auxilio que la novedad ya pago (Decreto 780/2016
        Art. 3.2.5.1; decision de David, 2026-11-10). Solo cuenta a salud y pension,
        no a ARL ni parafiscales; el descuento al empleado es el normal (Art.
        3.2.1.10), a diferencia de SLN. Integral: 0 (como H-017a).
        `codigos` permite acotar; por defecto los 4 de ausencia calendario.

        Lee SIN mutar (.275): ``result_rules.get(codigo, {})`` insertaba un ``{}`` en el ``DefaultDictPayroll`` del motor
        (``hr_payroll/models/hr_payslip.py:23-27``) para cada ausencia no evaluada, y el neto de E-8 fallaba con
        ``KeyError: 'total'``. El resultado numérico es el mismo que antes (0.0 si no se evaluó)."""
        if contract.l10n_co_ne_integral_salary:
            return 0.0
        if codigos is None:
            codigos = _NOVEDAD_AUSENCIA_CALENDARIO_CODES
        return sum(self._ne_total_regla(result_rules, codigo) for codigo in sorted(codigos))

    def _ne_ibc_seguridad_social(self, categories, contract, inputs, worked_days, result_rules):
        """Base que guarda CO_SS_BASE_IBC (visible en «Calculo del salario»; hasta .305 la leia
        el «ultimo IBC anterior» de vacaciones/licencia remunerada/SLN, hoy la SUMA de esta base del mes anterior escalada a 30 dias, H-F1-11): salario
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
                    ultimo_ibc = self._ne_ibc_mes_anterior(contract, antes_de=tramo_ini)
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
        # La liquidacion (H-168) no tiene historial propio: la base es el IBC del mes anterior al inicio del tramo (el mismo criterio que sus vacaciones); en la nomina general el tramo empieza
        # con el recibo.
        tramo_ini = self._ne_tramo_pagable_periodo()[0]
        return self._ne_ibc_mes_anterior(contract, antes_de=tramo_ini) / dias_mes * dias

    def _ne_exceso_no_salarial(self, remuneracion, pactados):
        """Exceso del 40% (Ley 1393/2010 Art. 30; SU 25185/2021): la parte de los pagos no salariales POR PACTO (``pactados``) que supera el porcentaje del
        parámetro ``l10n_co_pct_tope_no_salarial`` del total de la remuneración (``remuneracion`` + ``pactados``). Ese exceso suma al IBC de salud, pensión
        y ARL. .299: se extrajo de ``_ne_ibc_limites`` SIN cambiar su resultado, para mostrarlo en «Cálculo del salario» con la misma cuenta."""
        self.ensure_one()
        pct = self._rule_parameter('l10n_co_pct_tope_no_salarial', self._ne_fecha_parametros())
        return max(0.0, pactados - pct / 100.0 * (remuneracion + pactados))

    def _ne_ibc_parafiscales(self, salarial):
        """IBC de CCF, SENA e ICBF (.299, decisión del TL del 22-nov): SOLO lo salarial. Sin el excedente del 40%, sin el piso de 1 SMMLV y sin el techo
        de 25 SMMLV. Ley 21/1982 art. 17 («nómina mensual de salarios»: los pagos por los elementos integrantes del salario, más los descansos
        remunerados) y Ley 344/1996 art. 17 (los acuerdos sobre pagos que no constituyen salario, CST art. 128, y el auxilio de transporte no hacen parte de
        la base de SENA, ICBF, ESAP y subsidio familiar, sin tope porcentual). El 40% del art. 30 de la Ley 1393/2010 es de salud, pensión y riesgos
        laborales (``_ne_ibc_limites``), no de parafiscales. El salario integral entra por ``salarial`` con su 70% (``_ne_ibc_salarial``)."""
        self.ensure_one()
        return salarial

    def _ne_ibc_limites(self, salarial, incap, remuneracion, pactados, dias):
        """IBC del recibo con regla del 40%, techo (sin prorratear) y piso (prorrateado
        por dias). Ley 1393/2010 Art. 30; Ley 797/2003; SU 25185/2021. Es la base de salud, pensión y ARL; la de parafiscales es
        ``_ne_ibc_parafiscales`` (.299)."""
        self.ensure_one()
        smmlv = self._rule_parameter('l10n_co_smmlv', self._ne_fecha_parametros())
        minimo = self._rule_parameter('l10n_co_ibc_min_smmlv', self._ne_fecha_parametros())
        maximo = self._rule_parameter('l10n_co_ibc_max_smmlv', self._ne_fecha_parametros())
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self._ne_fecha_parametros())
        excedente = self._ne_exceso_no_salarial(remuneracion, pactados)
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

    # Porcentaje (tabla 5.5.5 del Anexo) de cada hora extra/recargo, derivado del MISMO factor hr.rule.parameter con el que se calcula el pago: (factor - 1) x 100 en las extras y en los 4
    # conceptos dominicales/festivos (el factor incluye la hora ordinaria) y factor x 100 en el recargo nocturno (solo el recargo).
    # H-F1-05 (decision del TL con la doctrina DIAN): los 4 conceptos dominicales/festivos (HEDDF, HRDDF, HENDF, HRNDF) salian con ``line.rate`` (100). El Concepto DIAN 13840 de 2025 dice que HRDDF
    # informa el porcentaje de la tabla 5.5.5 (75 %) «que debe leerse en consonancia con la normatividad vigente» -- el 80 % de la Ley 2466/2025 desde 2025-07-01, 90 % desde 2026-07-01, 100 % desde
    # 2027-07-01 -- y que varios porcentajes en un mismo mes no impiden generar ni validar el documento. Abril 2026: HEDDF 105, HRDDF 80, HENDF 155, HRNDF 115; desde 2026-07-01: 115, 90, 165, 125.
    # La FECHA es la del pago, no una «fecha del trabajo» (no existe: las horas entran por novedad, sin fecha): las reglas CO_HED...CO_HRNDF leen el factor en ``payslip.date_from`` y el XML usa
    # exactamente el mismo factor y la misma fecha, asi Porcentaje y Pago nunca difieren. Las vigencias cambian el dia 1 del mes: en recibos quincenales y mensuales no hay cruce. LIMITE CONOCIDO: un
    # recibo semanal (u otro periodo irregular) que cruce el 1-jul usa el factor del dia de inicio para todas sus horas, en el pago y en el XML por igual (como la jornada del 15-jul, doc 67).
    # Cambia el XML, NO el pago ni el neto.
    _NE_PORCENTAJE_HORA_FACTOR = {
        'HED': ('l10n_co_factor_hed', -1.0),
        'HEN': ('l10n_co_factor_hen', -1.0),
        'HRN': ('l10n_co_factor_hrn', 0.0),
        'HEDDF': ('l10n_co_factor_heddf', -1.0),
        'HRDDF': ('l10n_co_factor_hrddf', -1.0),
        'HENDF': ('l10n_co_factor_hendf', -1.0),
        'HRNDF': ('l10n_co_factor_hrndf', -1.0),
    }

    def _ne_porcentaje_hora_en(self, concepto, fecha):
        """Porcentaje (tabla 5.5.5) del ``concepto`` de horas extra o recargo (uno de los 7 de ``HORA_EXTRA_CONCEPTS``) con el factor que ``hr.rule.parameter`` tiene en ``fecha``. UNICO lugar
        del calculo: ``_ne_porcentaje_hora`` lo llama con la fecha del pago (``date_from`` del recibo)."""
        self.ensure_one()
        codigo, ajuste = self._NE_PORCENTAJE_HORA_FACTOR[concepto]
        return round((self._rule_parameter(codigo, fecha) + ajuste) * 100.0, 2)

    def _ne_porcentaje_hora(self, concepto, line):
        """Porcentaje del XML de una linea de horas extra o recargo: el del factor vigente en ``date_from`` del recibo, la misma fecha con que las reglas calculan el pago (ver arriba)."""
        self.ensure_one()
        return self._ne_porcentaje_hora_en(concepto, self.date_from)

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
            return self._LEAVE_CODE_MAP.get(code)

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
