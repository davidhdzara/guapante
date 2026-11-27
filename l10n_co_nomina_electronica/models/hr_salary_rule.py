# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.salary.rule para Nómina Electrónica DIAN y reportes UGPP.

Agrega el campo de mapeo ``l10n_co_ne_dian_concept`` que vincula cada regla
salarial con el concepto XML correspondiente del nodo ``<Devengados>`` o
``<Deducciones>`` del documento de nómina electrónica. Este mapeo es la pieza
clave que permite al sistema construir automáticamente el XML de nómina
a partir de las líneas de la nómina calculada.

También incluye campos para la clasificación UGPP del concepto, necesarios
para generar los reportes de Storm User.

Referencia: Anexo Técnico V1.0, secciones 6.2.12 (Devengados) y 6.2.13
(Deducciones).
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

# ──────────────────────────────────────────────────────────────────────────
# Constantes: conceptos de deducción según el XML DIAN
# ──────────────────────────────────────────────────────────────────────────
DEDUCTION_CONCEPTS = {
    'Salud', 'FondoPension', 'FondoSP', 'Sindicato', 'Sancion',
    'Libranza', 'PagoTerceroDed', 'AnticipoDed', 'PensionVoluntaria',
    'RetencionFuente', 'AFC', 'Cooperativa', 'EmbargoFiscal',
    'PlanComplementarios', 'Educacion', 'Deuda', 'OtraDeduccion',
    'ReintegroDed',
}


class HrSalaryRule(models.Model):
    """Mapeo de reglas salariales a conceptos DIAN y clasificación UGPP."""

    _inherit = 'hr.salary.rule'

    l10n_co_struct_country_code = fields.Char(
        related='struct_id.country_id.code', string='País de la estructura',
        help='Solo para ocultar en la vista lo colombiano fuera de Colombia.')

    # ──────────────────────────────────────────────────────────────────
    # Concepto DIAN para el XML de nómina electrónica
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_dian_concept = fields.Selection(
        selection=[
            # ── Devengados ──────────────────────────────────────────
            ('Sueldo', 'Sueldo Básico'),
            ('Transporte', 'Auxilio de Transporte'),
            ('ViaticoS', 'Viáticos Salariales'),
            ('ViaticoNS', 'Viáticos No Salariales'),
            ('HED', 'Hora Extra Diurna (HED)'),
            ('HEN', 'Hora Extra Nocturna (HEN)'),
            ('HRN', 'Hora Recargo Nocturno (HRN)'),
            ('HEDDF', 'Hora Extra Diurna Dom/Fest (HEDDF)'),
            ('HRDDF', 'Hora Recargo Diurno Dom/Fest (HRDDF)'),
            ('HENDF', 'Hora Extra Nocturna Dom/Fest (HENDF)'),
            ('HRNDF', 'Hora Recargo Nocturno Dom/Fest (HRNDF)'),
            ('VacacionesComunes', 'Vacaciones Comunes'),
            ('VacacionesCompensadas', 'Vacaciones Compensadas'),
            ('Primas', 'Prima de Servicios'),
            ('Cesantias', 'Cesantías'),
            ('InteresesCesantias', 'Intereses a las Cesantías'),
            ('Incapacidad', 'Incapacidad'),
            ('LicenciaMP', 'Licencia de Maternidad/Paternidad'),
            ('LicenciaR', 'Licencia Remunerada'),
            ('LicenciaNR', 'Licencia No Remunerada'),
            ('BonificacionS', 'Bonificación Salarial'),
            ('BonificacionNS', 'Bonificación No Salarial'),
            ('AuxilioS', 'Auxilio Salarial'),
            ('AuxilioNS', 'Auxilio No Salarial'),
            ('HuelgaLegal', 'Huelga Legal'),
            ('OtroConceptoS', 'Otro Concepto Salarial'),
            ('OtroConceptoNS', 'Otro Concepto No Salarial'),
            ('CompensacionO', 'Compensación Ordinaria'),
            ('CompensacionE', 'Compensación Extraordinaria'),
            ('BonoEPCTVS', 'Bono EPCTV Salarial'),
            ('BonoEPCTVNS', 'Bono EPCTV No Salarial'),
            ('BonoAlimS', 'Bono Alimentación Salarial'),
            ('BonoAlimNS', 'Bono Alimentación No Salarial'),
            ('Comision', 'Comisión'),
            ('PagoTercero', 'Pago a Terceros (Devengado)'),
            ('Anticipo', 'Anticipo (Devengado)'),
            ('Dotacion', 'Dotación'),
            ('ApoyoSost', 'Apoyo de Sostenimiento'),
            ('Teletrabajo', 'Teletrabajo'),
            ('BonifRetiro', 'Bonificación por Retiro'),
            ('Indemnizacion', 'Indemnización'),
            ('Reintegro', 'Reintegro (Devengado)'),
            # ── Deducciones ─────────────────────────────────────────
            ('Salud', 'Aporte Salud (Deducción)'),
            ('FondoPension', 'Aporte Fondo de Pensión (Deducción)'),
            ('FondoSP', 'Fondo de Solidaridad Pensional (Deducción)'),
            ('Sindicato', 'Sindicato (Deducción)'),
            ('Sancion', 'Sanción (Deducción)'),
            ('Libranza', 'Libranza (Deducción)'),
            ('PagoTerceroDed', 'Pago a Terceros (Deducción)'),
            ('AnticipoDed', 'Anticipo (Deducción)'),
            ('OtraDeduccion', 'Otra Deducción'),
            ('PensionVoluntaria', 'Pensión Voluntaria (Deducción)'),
            ('RetencionFuente', 'Retención en la Fuente'),
            ('AFC', 'AFC – Ahorro Fomento Construcción'),
            ('Cooperativa', 'Cooperativa (Deducción)'),
            ('EmbargoFiscal', 'Embargo Fiscal'),
            ('PlanComplementarios', 'Planes Complementarios de Salud'),
            ('Educacion', 'Educación (Deducción)'),
            ('ReintegroDed', 'Reintegro (Deducción)'),
            ('Deuda', 'Deuda (Deducción)'),
        ],
        string='Concepto DIAN Nómina',
        help='Concepto del anexo técnico de nómina electrónica al que '
             'se mapea esta regla salarial. Determina en qué nodo del '
             'XML (<Devengados> o <Deducciones>) se incluirá el valor '
             'calculado por esta regla.\n\n'
             'Si no se selecciona un concepto, la regla no se incluirá '
             'en el XML de nómina electrónica.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Campo computado: ¿Es deducción?
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_is_deduction = fields.Boolean(
        string='Es Deducción DIAN',
        compute='_compute_is_deduction',
        store=True,
        help='Indica si el concepto DIAN corresponde a una deducción. '
             'Se calcula automáticamente a partir del concepto seleccionado.',
    )

    @api.depends('l10n_co_ne_dian_concept')
    def _compute_is_deduction(self):
        """Determina si el concepto DIAN es una deducción basándose en la lista oficial."""
        for rule in self:
            rule.l10n_co_ne_is_deduction = (
                rule.l10n_co_ne_dian_concept in DEDUCTION_CONCEPTS
                if rule.l10n_co_ne_dian_concept
                else False
            )

    # ──────────────────────────────────────────────────────────────────
    # Campos UGPP – Clasificación para Storm User
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ugpp_payment_type = fields.Selection(
        selection=[
            ('tp_salarial', 'TP Salarial'),
            ('tp_no_salarial', 'TP NO Salarial'),
            ('tp_compensacion_ord', 'TP Compensación ordinaria'),
            ('tp_compensacion_ext', 'TP Compensación extraordinaria'),
            ('tp_no_compensacion', 'TP No compensación'),
            ('tp_estudiantes', 'TP A Estudiantes o aprendices'),
            ('tp_incapacidad', 'TP Incapacidad'),
            ('tp_licencia_mat_pat', 'TP Licencia mat o pat'),
            ('tp_licencia_remunerada', 'TP Licencia remunerada'),
            ('tp_vacaciones', 'TP Vacaciones'),
            ('tp_vacaciones_terminacion', 'TP Vacaciones terminación de contrato'),
            ('tp_descanso_anual', 'TP Descanso anual'),
            ('tp_prestaciones', 'TP Prestaciones'),
        ],
        string='Tipo Pago UGPP',
        help='Tipo de pago del concepto en el formato de pagos UGPP (Guía Storm User V-20.1, campo 19). El código '
             'de cada tipo sale de la lista de la plantilla; los tipos 12 a 15 son de independientes y no se cargan.',
    )
    l10n_co_ugpp_non_salary_class = fields.Selection(
        selection=[
            ('mera_liberalidad', 'Mera liberalidad'),
            ('pacto_colectivo', 'Pacto colectivo'),
            ('contrato', 'Contrato'),
            ('otrosi', 'Otrosí'),
        ],
        string='Clasificación TP NO SALARIAL',
        help='Subclasificación obligatoria cuando Tipo Pago = TP NO Salarial. '
             'Según guía UGPP Storm User V-20.1. La cuenta contable del concepto sale de las cuentas de la regla '
             '(pestaña Asiento Contable): no se digita aparte.',
    )

    @api.constrains('l10n_co_ugpp_payment_type', 'l10n_co_ugpp_non_salary_class')
    def _check_ugpp_clasificacion_no_salarial(self):
        for rule in self:
            if rule.l10n_co_ugpp_payment_type == 'tp_no_salarial' and not rule.l10n_co_ugpp_non_salary_class:
                raise ValidationError(_(
                    'La regla "%(regla)s" es TP NO Salarial para la UGPP: indique su clasificación (mera liberalidad, '
                    'pacto colectivo, contrato u otrosí).', regla=rule.display_name))

    # ──────────────────────────────────────────────────────────────────
    # Tercero del asiento contable (contacto al que se paga lo causado)
    # ──────────────────────────────────────────────────────────────────
    l10n_co_tercero_origen = fields.Selection(
        selection=[
            ('employee_eps', 'EPS del empleado'),
            ('employee_afp', 'AFP del empleado'),
            ('employee_ccf', 'Caja de compensación del empleado'),
            ('company_arl', 'ARL de la compañía'),
            ('company_sena', 'SENA de la compañía'),
            ('company_icbf', 'ICBF de la compañía'),
            ('company_dian', 'DIAN (compañía)'),
            ('contract_sindicato', 'Sindicato del contrato'),
            ('contract_afc', 'Entidad AFC del contrato'),
            ('contract_pension_voluntaria', 'Fondo de pensión voluntaria del contrato'),
            ('contract_plan_complementario', 'Plan complementario del contrato'),
            ('contract_cooperativa', 'Cooperativa del contrato'),
            ('contract_educacion', 'Entidad de educación del contrato'),
            ('distribution', 'Reparto por asignación salarial (embargos, libranzas)'),
        ],
        string='Tercero del Asiento',
        help='De dónde sale el contacto (partner) de la línea del asiento '
             'contable en la cuenta por pagar de esta regla. Vacío: la línea '
             'se genera sin tercero.',
    )

    l10n_co_pila_origen_no_salarial = fields.Selection(
        selection=[
            ('naturaleza', 'Por naturaleza (nunca entra al IBC ni al 40%)'),
            ('pacto', 'Por pacto de desalarización (cuenta para el 40%)'),
        ],
        string='Origen del Pago No Salarial (IBC)',
        help='Solo para conceptos no salariales. Por naturaleza: auxilio de '
             'transporte, viáticos ocasionales, prestaciones, etc. -- nunca '
             'entran al IBC (Consejo de Estado, SU 25185 de 2021). Por pacto: '
             'alimentación, vivienda, bonificaciones habituales pactadas como '
             'no salariales -- cuentan para la regla del 40% (Ley 1393/2010 '
             'Art. 30) y su excedente suma al IBC. Los pagos por pacto exigen '
             'prueba del acuerdo (contrato u otrosí). La UGPP mira la realidad '
             'económica: un pago habitual que retribuye el servicio puede ser '
             'reincorporado al IBC aunque esté marcado como no salarial.',
    )

    # ──────────────────────────────────────────────────────────────────────
    # E11 pieza 2a (.287, doc 71c §2 y §7): configuración de «Conceptos de pago». Sembrada en el XML de cada regla; nada en el código.
    # ──────────────────────────────────────────────────────────────────────
    # .298 (decisión de David, 21-nov, por el riesgo de inexactitud ante la UGPP: art. 179 Ley 1607/2012, mod. art. 314 Ley 1819/2016; Decreto 3033/2013): ya NO
    # se calcula por la sección de la categoría; es un dato PLANO de cada regla, sembrado explícito en el XML (``True`` solo en los conceptos de pago y las
    # deducciones voluntarias o pactadas; ``False`` en lo que sale de la ley o del cálculo) y ``False`` por defecto en una regla nueva. Un campo calculado se
    # recalcularía y pisaría la decisión en cada actualización o al cambiar la estructura. Mismo patrón que ``l10n_co_ne_unidad``.
    l10n_co_ne_ajustable = fields.Boolean(
        string='Permite ajuste de la empresa', default=False,
        help='Si está marcada, quien administra la nómina puede cambiar la cantidad, el porcentaje o el importe de esta regla en un recibo '
             'en borrador o en espera. El sistema conserva el valor sugerido y quién lo cambió; el ajuste es responsabilidad de la empresa. '
             'Solo se marcan los conceptos de pago (sueldo, horas, recargos, bonificaciones, auxilios) y las deducciones voluntarias o '
             'pactadas (libranzas, cooperativa, AFC, pensión voluntaria, sindicato). NO se marcan los aportes de salud, pensión y FSP del '
             'empleado, la retención en la fuente, los embargos, los aportes de la empresa, las provisiones, las bases, las incapacidades, '
             'las licencias ni las vacaciones disfrutadas: su valor sale de la ley o del cálculo y cambiarlo expone a la empresa a inexactitud ante la '
             'UGPP. En los recibos de prima y liquidación sí se marcan la prima, las cesantías, sus intereses y las vacaciones compensadas. Solo el administrador del sistema puede marcarla o desmarcarla. Si se desmarca una regla, los ajustes que tenía en recibos '
             'en borrador o en espera se retiran (con una nota en el recibo); los de recibos confirmados no se tocan. '
             'Esta marca se siembra desde el XML del módulo: cada actualización del módulo devuelve a su valor sembrado la de las reglas de la estructura '
             'general; las reglas propias del cliente no se tocan.')
    # .301 (decisión del TL, 22-nov): qué conceptos no salariales avisan cuando se repiten mes a mes (``HrPayslip._ne_avisos_habitualidad``). Dato PLANO sembrado
    # explícito en el XML de cada regla, igual que ``l10n_co_ne_ajustable``, y NO se deduce de «ajustable» (son dos cosas distintas: quién puede editar un concepto y
    # si su repetición es sospechosa) ni del origen (el auxilio de transporte y el de conectividad se pagan todos los meses por ley y avisarían siempre).
    l10n_co_ne_vigilar_habitualidad = fields.Boolean(
        string='Vigilar habitualidad', default=False,
        help='Solo para conceptos no salariales. Si está marcada y el concepto se paga en cada uno de los últimos N meses calendario (el parámetro «Colombia: Meses de '
             'Habitualidad de Pagos No Salariales», 3 de fábrica, contando el mes del recibo), el recibo muestra un aviso: un pago habitual que retribuye el servicio '
             'puede ser salario aunque se llame no salarial (art. 127 CST; los viáticos permanentes de manutención y alojamiento son salario, art. 130 CST) y entrar al '
             'IBC. Solo es un aviso: no cambia el cálculo. De fábrica se vigilan el auxilio de alimentación, las bonificaciones no salariales y los viáticos no '
             'salariales. NO se marcan los pagos que la ley hace todos los meses (auxilio de transporte, auxilio de conectividad del teletrabajo, apoyo de sostenimiento). '
             'Solo el administrador del sistema puede marcarla o desmarcarla. Esta marca se siembra desde el XML del módulo: cada actualización del módulo '
             'devuelve a su valor sembrado la de las reglas de la estructura general; las reglas propias del cliente no se tocan.')
    # .303 (doc 78, decisiones del TL del 22-nov): qué reglas entran a la base de las provisiones de prestaciones (``HrPayslip._ne_base_prestacional``). Datos PLANOS por
    # regla, sembrados explícitos en el XML como ``l10n_co_ne_ajustable`` (nada de listas de códigos en la fórmula; la categoría ``DEV_SAL`` mezcla cosas: las horas
    # extras entran a la prima y las cesantías pero no a las vacaciones). ``False`` por defecto; solo ``base.group_system`` las cambia.
    l10n_co_ne_base_prima_cesantias = fields.Boolean(
        string='Base de prima y cesantías', default=False,
        help='Si está marcada, lo que paga esta regla en el recibo suma a la base de las provisiones de prima de servicios y de cesantías (y de sus intereses): lo devengado '
             'como salario (CST art. 127), incluidas las horas extras y los recargos, más el auxilio de transporte (Ley 1/1963 art. 7). NO se marcan los pagos no salariales, '
             'las prestaciones, las vacaciones compensadas, las incapacidades ni las licencias de ley (decisión del TL del 22-nov: por prudencia, a revisar con datos reales). '
             'Solo el administrador del sistema puede marcarla o desmarcarla. Esta marca se siembra desde el XML del módulo: cada actualización del módulo devuelve a su valor '
             'sembrado la de las reglas de la estructura general; las reglas propias del cliente no se tocan.')
    l10n_co_ne_base_vacaciones = fields.Boolean(
        string='Base de vacaciones', default=False,
        help='Si está marcada, lo que paga esta regla en el recibo suma a la base de la provisión de vacaciones: el salario ordinario (CST art. 192): se excluyen las horas '
             'extras y el trabajo en días de descanso obligatorio (dominicales y festivos), y el auxilio de transporte (no es salario para las vacaciones). El recargo nocturno '
             'ordinario sí entra. Solo el administrador del sistema puede marcarla o desmarcarla. Esta marca se siembra desde el XML del módulo: cada actualización del módulo '
             'devuelve a su valor sembrado la de las reglas de la estructura general; las reglas propias del cliente no se tocan.')
    # Selector del concepto en «Agregar concepto» (22-nov, diseño aprobado por el TL; doc 74 §19): una regla «se alimenta de una novedad» si existe un tipo de novedad
    # (``hr.payslip.input.type``) con SU MISMO ``code``. Es la definición verificable (1 a 1 por ``code`` en la estructura general: 38 de 44 tipos; los otros 6 son de otras
    # estructuras o de las asignaciones salariales). Calculado y buscable: sin dato nuevo que mantener ni listas de códigos en el código.
    l10n_co_ne_alimentada_por_novedad = fields.Boolean(
        string='Se alimenta de una novedad', compute='_compute_ne_alimentada_por_novedad', search='_search_ne_alimentada_por_novedad',
        help='Verdadero si existe un tipo de novedad con el mismo código de esta regla: el usuario puede agregar ese concepto a mano en «Conceptos de pago» y el recibo lo '
             'calcula con la novedad. Calculado: no se marca.')

    def _compute_ne_alimentada_por_novedad(self):
        codigos = set(self.env['hr.payslip.input.type'].sudo().search([]).mapped('code'))
        for regla in self:
            regla.l10n_co_ne_alimentada_por_novedad = regla.code in codigos

    def _search_ne_alimentada_por_novedad(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError('Solo se busca con = o != y un booleano.')
        codigos = self.env['hr.payslip.input.type'].sudo().search([]).mapped('code')
        return [('code', 'in' if (operator == '=') == value else 'not in', codigos)]

    # Ajuste de David (22-nov, decisión del TL): las bases de la retención en la fuente solo se muestran en «Cálculo del salario» si el recibo tiene retención.
    l10n_co_ne_calculo_si_retencion = fields.Boolean(
        string='En «Cálculo del salario» solo con retención', default=False,
        help='Si está marcada, la línea de esta regla se muestra en «Cálculo del salario» solo cuando el recibo tiene retención en la fuente distinta de 0 (una línea con valor '
             'de una regla cuyo tercero es la DIAN). Es de presentación: no cambia el cálculo. De fábrica, las dos bases de la retención en la fuente: sin retención verlas '
             'confunde.')
    # Menor de QA sobre «cv» (22-nov, decisión del TL): en «Bases» salían tres filas con el mismo valor (IBC Salarial, IBC Remuneración Base 40 % y Base salarial del mes).
    l10n_co_ne_calculo_oculta = fields.Boolean(
        string='Oculta en «Cálculo del salario»', default=False,
        help='Si está marcada, la línea de esta regla NO se muestra en «Cálculo del salario» aunque tenga valor: es un acumulador intermedio de otra base que sí se muestra. '
             'Es de presentación: la regla se sigue calculando, otras reglas la leen y la línea sigue en el recibo. De fábrica, «IBC Salarial» y «IBC Remuneración Base 40 %», '
             'componentes de «Base salarial del mes».')
    l10n_co_ne_unidad = fields.Selection(
        selection=[('dias', 'Días'), ('horas', 'Horas')],
        string='Unidad de la cantidad',
        help='Unidad con la que se muestra la cantidad de esta regla en «Conceptos de pago». Vacío: la regla es un valor y no tiene unidad '
             '(«valor» no es una unidad).')

    def _compute_rule(self, localdict):
        """E11 pieza 2b (.288, doc 71c §3): si el recibo tiene un ajuste de la empresa para esta regla, devuelve la tupla ajustada en vez de la
        sugerida y guarda la sugerida en ``ne_sugeridos`` del contexto (la registra ``HrPayslip._ne_registrar_ajustes``). El bucle nativo
        (``hr_payroll/models/hr_payslip.py:944-1018``) usa lo que devuelve esta función para el total de la línea, ``localdict`` y las sumas por
        categoría, así que todo lo posterior (neto, bases, retención, IBC) sigue la cascada. Sin ajuste, o con un ``localdict`` mínimo (pruebas),
        devuelve exactamente lo de ``super()``."""
        resultado = super()._compute_rule(localdict)
        recibo = localdict.get('payslip') if isinstance(localdict, dict) else None
        if not recibo or not self.l10n_co_ne_ajustable or recibo.state not in ('draft', 'verify') or not recibo.id:
            return resultado
        if self.code in (localdict.get('same_type_input_lines') or {}):
            return resultado                      # varias novedades del mismo código: se editan las novedades, no la regla
        ajuste = recibo.l10n_co_ajuste_ids.filtered(lambda a: a.salary_rule_id == self)
        if not ajuste:
            return resultado
        sugeridos = self.env.context.get('ne_sugeridos')
        if sugeridos is not None:
            sugeridos[(recibo.id, self.id)] = tuple(resultado)
        return ajuste.amount, ajuste.quantity, ajuste.rate

    def _ne_exigir_administrador_para_ajustable(self):
        """Decisión de David (21-nov, riesgo UGPP): marcar o desmarcar «Permite ajuste de la empresa» es del administrador del sistema (``base.group_system``), no del
        gerente de nómina. El superusuario (carga de datos del módulo, ``-u``) no pasa por aquí. El campo NO usa ``groups=`` a nivel de modelo: el cálculo y las
        filas de «Conceptos de pago» lo leen con el usuario de nómina."""
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Solo un administrador del sistema puede marcar o desmarcar «Permite ajuste de la empresa» en una regla salarial: decide qué conceptos '
                'puede cambiar a mano la empresa y un cambio expone la nómina a inexactitud ante la UGPP.'))

    def _ne_exigir_administrador_para_habitualidad(self):
        """.301: marcar o desmarcar «Vigilar habitualidad» es del administrador del sistema, igual que «ajustable» (decisión del TL, 22-nov). El superusuario (carga de
        datos del módulo, ``-u``) no pasa por aquí. Sin ``groups=`` en el campo: el cálculo del aviso lo lee con el usuario de nómina."""
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Solo un administrador del sistema puede marcar o desmarcar «Vigilar habitualidad» en una regla salarial: decide de qué conceptos no salariales '
                'avisa el recibo cuando se pagan mes a mes.'))

    _NE_MARCAS_DE_LA_BASE_PRESTACIONAL = ('l10n_co_ne_base_prima_cesantias', 'l10n_co_ne_base_vacaciones')

    def _ne_exigir_administrador_para_base_prestacional(self):
        """.303: marcar o desmarcar las bases de las provisiones («Base de prima y cesantías», «Base de vacaciones») es del administrador del sistema, como «ajustable» y
        «Vigilar habitualidad» (``base.group_system``). El superusuario (carga de datos del módulo, ``-u``) no pasa por aquí. Sin ``groups=`` en el campo: el cálculo de
        las provisiones lo lee con el usuario de nómina."""
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError(_(
                'Solo un administrador del sistema puede marcar o desmarcar la base de prima, cesantías o vacaciones en una regla salarial: decide qué pagos entran a la base '
                'de las provisiones de prestaciones.'))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('l10n_co_ne_ajustable') for vals in vals_list):
            self._ne_exigir_administrador_para_ajustable()
        if any(vals.get('l10n_co_ne_vigilar_habitualidad') for vals in vals_list):
            self._ne_exigir_administrador_para_habitualidad()
        if any(vals.get(campo) for vals in vals_list for campo in self._NE_MARCAS_DE_LA_BASE_PRESTACIONAL):
            self._ne_exigir_administrador_para_base_prestacional()
        return super().create(vals_list)

    def write(self, vals):
        if 'l10n_co_ne_ajustable' in vals:
            self._ne_exigir_administrador_para_ajustable()
        if 'l10n_co_ne_vigilar_habitualidad' in vals:
            self._ne_exigir_administrador_para_habitualidad()
        if any(campo in vals for campo in self._NE_MARCAS_DE_LA_BASE_PRESTACIONAL):
            self._ne_exigir_administrador_para_base_prestacional()
        res = super().write(vals)
        if 'l10n_co_ne_ajustable' in vals and not vals['l10n_co_ne_ajustable']:
            self.env['l10n.co.payslip.ajuste']._retirar_de_reglas_no_ajustables(self)
        return res

    _L10N_CO_ORIGEN_NO_SALARIAL_POR_CODIGO = {
        'CO_AUX_TRANS': 'naturaleza', 'CO_VIATICOS_NOSAL': 'naturaleza',
        'CO_DOTACION': 'naturaleza', 'CO_TELETRABAJO': 'naturaleza',
        'CO_INDEMNIZ': 'naturaleza', 'CO_LIQ_INDEMNIZACION': 'naturaleza',
        'CO_BONIF_RET': 'naturaleza',
        # .299 (TL, 22-nov): el apoyo de sostenimiento del aprendiz (Ley 789/2002 art. 30) no es salario ni entra al IBC de esta forma (el aprendiz tiene su
        # propio régimen de cotización): origen «naturaleza» para que el 40 % no lo cuente y ``_ne_ibc_pactados`` no lance el UserError de «sin clasificar».
        'CO_APOYO_SOST': 'naturaleza',
        # H-F1-09: el apoyo de la fase PRACTICA tambien es «naturaleza» para el IBC: aunque es base de las prestaciones, el IBC del aprendiz es 1 SMMLV (Decreto 223/2026, art. 2.2.6.3.3.4 par. 2) y
        # ``_ne_ibc_pactados`` no debe lanzar el UserError de «sin clasificar».
        'CO_APOYO_SOST_PRAC': 'naturaleza',
        'CO_AUX_ALIM': 'pacto', 'CO_BONIF_NOSAL': 'pacto',
    }

    l10n_co_liq_tratamiento = fields.Selection(
        selection=[
            ('salario', 'Salario'),
            ('vacaciones', 'Vacaciones compensadas'),
            ('prestacion', 'Prestación social (prima, cesantías, intereses)'),
            ('indemnizacion', 'Indemnización'),
        ],
        string='Tratamiento en Liquidación',
        help='Clasifica el concepto de la liquidación para aplicar embargos y '
             'libranzas (CST arts. 154-156 y 344; Ley 1527/2012; SL3208-2022).',
    )

    _L10N_CO_LIQ_TRATAMIENTO_POR_CODIGO = {
        'CO_LIQ_SALARIOS': 'salario', 'CO_LIQ_VACACIONES': 'vacaciones',
        'CO_LIQ_PRIMA': 'prestacion', 'CO_LIQ_CESANTIAS': 'prestacion',
        'CO_LIQ_INT_CES': 'prestacion', 'CO_LIQ_INDEMNIZACION': 'indemnizacion',
        'CO_LIQ_VAC_DISFRUTADAS': 'salario', 'CO_LIQ_LIC_REM': 'salario',
    }

    # Codigo de regla (identificador interno del modulo, no un valor
    # normativo) -> origen del tercero. Solo se escribe donde el campo
    # esta vacio (no pisa lo que configure el usuario).
    _L10N_CO_TERCERO_ORIGEN_POR_CODIGO = {
        'CO_SALUD_EMP': 'employee_eps', 'CO_SALUD_CIA': 'employee_eps',
        'CO_PENSION_EMP': 'employee_afp', 'CO_PENSION_CIA': 'employee_afp',
        'CO_FSP': 'employee_afp',
        'CO_CCF_CIA': 'employee_ccf',
        'CO_ARL_CIA': 'company_arl',
        'CO_SENA_CIA': 'company_sena', 'CO_ICBF_CIA': 'company_icbf',
        'CO_RETEFUENTE': 'company_dian', 'CO_PRIMA_RETE': 'company_dian',
        'CO_LIQ_RETE': 'company_dian', 'CO_BON_RETE': 'company_dian',
        'CO_SINDICATO': 'contract_sindicato', 'CO_AFC': 'contract_afc',
        'CO_PENSION_VOL': 'contract_pension_voluntaria',
        'CO_PLAN_COMP': 'contract_plan_complementario',
        'CO_COOPERATIVA': 'contract_cooperativa',
        'CO_EDUCACION': 'contract_educacion',
        'CO_EMBARGO': 'distribution', 'CO_LIBRANZAS': 'distribution',
        'CO_LIQ_EMBARGO': 'distribution', 'CO_LIQ_LIBRANZAS': 'distribution',
        'CO_LIQ_SALUD': 'employee_eps', 'CO_LIQ_PENSION': 'employee_afp',
        'CO_LIQ_RETE': 'company_dian',
    }

    @api.model
    def _l10n_co_cargar_origen_tercero(self):
        """Asigna el origen del tercero a las reglas del modulo (todas las
        estructuras comparten codigo) que aun no lo tienen."""
        for code, origen in self._L10N_CO_TERCERO_ORIGEN_POR_CODIGO.items():
            self.search([
                ('code', '=', code), ('l10n_co_tercero_origen', '=', False),
            ]).write({'l10n_co_tercero_origen': origen})
        for code, origen in self._L10N_CO_ORIGEN_NO_SALARIAL_POR_CODIGO.items():
            self.search([
                ('code', '=', code), ('l10n_co_pila_origen_no_salarial', '=', False),
            ]).write({'l10n_co_pila_origen_no_salarial': origen})
        for code, trat in self._L10N_CO_LIQ_TRATAMIENTO_POR_CODIGO.items():
            self.search([
                ('code', '=', code), ('l10n_co_liq_tratamiento', '=', False),
            ]).write({'l10n_co_liq_tratamiento': trat})
        return True

    def _ne_cuenta_contable(self, total, compania):
        """Columna «Cuenta» de «Conceptos de pago» y «Cálculo del salario» (ajuste de David, 22-nov): la cuenta contable de la regla en la COMPAÑÍA del recibo, la que aplica
        al signo del valor (como en los apuntes: un valor positivo va por la cuenta de débito y uno negativo por la de crédito); si falta la que toca se muestra la otra. Sin cuenta, vacío:
        no se inventa. Las cuentas de la regla son por compañía (``company_dependent``) y las lee con ``sudo``: es solo un texto de presentación, sin el diario."""
        self.ensure_one()
        regla = self.sudo().with_company(compania)
        debito, credito = regla.account_debit, regla.account_credit
        cuenta = (debito or credito) if total >= 0 else (credito or debito)
        return cuenta.display_name if cuenta else False

    def _l10n_co_cuenta_pasivo(self):
        """Cuenta por pagar de la regla: account_credit si existe (aportes
        de empresa: gasto en debito, pasivo en credito); si no, account_debit
        (deducciones: el monto negativo hace caer el pasivo en credito)."""
        self.ensure_one()
        return self.account_credit or self.account_debit

    # ──────────────────────────────────────────────────────────────────────
    # E-3a (doc 59 §20.2): la regla nativa NET de nuestras estructuras da el neto real del modulo
    # ──────────────────────────────────────────────────────────────────────
    # Odoo crea solo, en cada estructura, las reglas BASIC/GROSS/NET (hr.payroll.structure._get_default_rule_ids): sin xmlid. NET =
    # BASIC + ALW + DED sale del salario por horas del nativo (paid_amount), no del neto real, y el informe nativo «Analisis de
    # nomina» lee esa linea. Se alinea con la regla de neto del modulo de cada estructura. BASIC y GROSS NO se tocan aqui: la
    # categoria GROSS alimenta la base de la retencion en la fuente (CO_RETEFUENTE*, categories['GROSS']): cambiarlas modifica el
    # calculo de la retencion y requiere decision (doc 59 §20.3).
    _NE_NETO_POR_ESTRUCTURA = {
        'hr_payroll_structure_co_nomina': 'CO_NETO',
        'hr_payroll_structure_co_liquidacion': 'CO_LIQ_NETO',
        'hr_payroll_structure_co_prima': 'CO_PRIMA_NETO',
        'hr_payroll_structure_co_bonificacion': 'CO_BON_NETO',
    }
    _NE_FORMULA_NETO = "result = result_rules['%(codigo)s']['total'] if '%(codigo)s' in result_rules else 0.0"

    @api.model
    def _ne_alinear_reglas_nativas(self):
        """Idempotente (corre en cada instalacion y actualizacion): fija la regla NET de cada estructura propia al neto del
        modulo y la ordena DESPUES de esa regla. Solo toca la formula nativa de Odoo o la que puso este metodo: una formula que un
        usuario edito a mano no se pisa."""
        for xmlid, codigo in self._NE_NETO_POR_ESTRUCTURA.items():
            estructura = self.env.ref('l10n_co_nomina_electronica.%s' % xmlid, raise_if_not_found=False)
            if not estructura:
                continue
            reglas = estructura.with_context(active_test=False).rule_ids
            neto, regla_modulo = reglas.filtered(lambda r: r.code == 'NET'), reglas.filtered(lambda r: r.code == codigo)
            if not neto or not regla_modulo:
                continue
            formula = self._NE_FORMULA_NETO % {'codigo': codigo}
            for regla in neto:
                actual = (regla.amount_python_compute or '').strip()
                if actual not in (formula, "result = categories['BASIC'] + categories['ALW'] + categories['DED']"):
                    continue          # editada a mano: se respeta
                regla.write({
                    'amount_select': 'code', 'amount_python_compute': formula,
                    'sequence': max(regla.sequence, max(regla_modulo.mapped('sequence')) + 1)})
