# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.contract para Nómina Electrónica DIAN.

Agrega los campos requeridos por el nodo ``<Trabajador>`` del XML de nómina
electrónica que dependen del contrato laboral: tipo de contrato y si el
salario es integral.

Referencia: Anexo Técnico – Documento Soporte de Pago de Nómina Electrónica
V1.0, sección 6.2.8, atributos TipoContrato y SalarioIntegral.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round
from odoo.tools.misc import format_amount

from .res_company import NE_CLASES_RIESGO


class HrContract(models.Model):
    """Campos del contrato laboral para Nómina Electrónica DIAN."""

    _inherit = 'hr.contract'

    # ──────────────────────────────────────────────────────────────────
    # Tipo de Contrato (codificación DIAN)
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_contract_type = fields.Selection(
        selection=[
            ('1', 'Término Fijo'),
            ('2', 'Término Indefinido'),
            ('3', 'Obra o Labor'),
            ('4', 'Aprendizaje'),
            ('5', 'Prácticas o Pasantía'),
        ],
        string='Tipo de Contrato DIAN',
        help='Tipo de contrato laboral según la codificación del anexo '
             'técnico de nómina electrónica de la DIAN.\n'
             '• 1 - Término Fijo: con fecha de terminación definida.\n'
             '• 2 - Término Indefinido: sin fecha de terminación.\n'
             '• 3 - Obra o Labor: duración atada a una obra específica.\n'
             '• 4 - Aprendizaje: contrato de aprendizaje SENA.\n'
             '• 5 - Prácticas o Pasantía: vinculación por práctica académica.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Salario Integral
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_integral_salary = fields.Boolean(
        string='Salario Integral',
        default=False,
        help='Indica si el trabajador devenga salario integral '
             '(Art. 132 CST). El salario integral incluye el factor '
             'prestacional y no genera derecho a auxilio de transporte, '
             'cesantías, intereses a las cesantías ni prima de servicios.\n'
             'Se refleja en el atributo SalarioIntegral del nodo '
             '<Trabajador> del XML.',
    )


    # ──────────────────────────────────────────────────────────────────
    # PILA — Datos de Cotización
    # ──────────────────────────────────────────────────────────────────
    l10n_co_pila_tipo_cotizante = fields.Selection(
        selection=[
            ('01', '01 - Dependiente'),
            ('02', '02 - Servicio Doméstico'),
            ('03', '03 - Independiente'),
            ('04', '04 - Madre Comunitaria'),
            ('12', '12 - Aprendiz del SENA en etapa lectiva'),
            ('19', '19 - Aprendiz del SENA en etapa productiva'),
            ('21', '21 - Estudiante (Ley 789/2002)'),
            ('22', '22 - Profesor de establecimiento particular'),
            ('30', '30 - Dependiente entidades o universidades públicas'),
            ('31', '31 - Cooperado o precooperativa'),
            ('51', '51 - Trabajador de tiempo parcial'),
        ],
        string='Tipo Cotizante',
        help='Tipo de cotizante según tabla PILA.',
    )
    l10n_co_pila_subtipo_cotizante = fields.Selection(
        selection=[
            ('00', '00 - No aplica'),
            ('01', '01 - Dependiente pensionado por vejez activo'),
            ('02', '02 - Independiente pensionado por vejez activo'),
        ],
        string='Subtipo Cotizante',
    )
    l10n_co_pila_salario_variable = fields.Boolean(
        string='Salario Variable',
        default=False,
        help='Marcar si el trabajador tiene salario variable.',
    )
    l10n_co_pila_clase_riesgo = fields.Selection(
        selection=NE_CLASES_RIESGO,
        string='Clase de Riesgo ARL',
        help='Solo si este contrato tiene una clase distinta de la general de la empresa '
             '(Nómina > Configuración > Ajustes). Vacío: se usa la general.',
    )
    l10n_co_pila_centro_trabajo = fields.Char(
        string='Centro de Trabajo',
        help='Código del centro de trabajo para ARL. Vacío: se usa el general de la empresa '
             '(Nómina > Configuración > Ajustes).',
    )
    l10n_co_pila_actividad_economica = fields.Many2one(
        'l10n.co.pila.ciiu',
        string='Actividad Económica ARL',
        domain="['|', ('date_end', '=', False), ('date_end', '>=', context_today().strftime('%Y-%m-%d'))]",
        help='Actividad económica del Decreto 768 de 2022 (busque por código o por descripción). '
             'Al elegirla se propone la Clase de Riesgo ARL de esa actividad.',
    )
    l10n_co_pila_indicador_alto_riesgo = fields.Boolean(
        string='Alto Riesgo Pensional',
        default=False,
        help='Indica si el empleado aplica para pensión de alto riesgo.',
    )
    l10n_co_pila_tarifa_especial_afp = fields.Char(
        string='Tarifa Especial AFP',
        help='Tarifa especial de AFP si aplica.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Piso del salario integral (CST art. 132 num. 2)
    # ──────────────────────────────────────────────────────────────────
    def _ne_validar_piso_integral(self, fecha=None):
        """Un contrato de salario integral no puede pagar menos del piso: l10n_co_piso_salario_
        integral_smmlv (13 SMMLV, 10 de salario + 30 % de factor prestacional) x SMMLV de la
        fecha. fecha: la del SMMLV; sin ella, la de inicio del contrato."""
        Parametro = self.env['hr.rule.parameter']
        for contrato in self.filtered(
                lambda c: c.l10n_co_ne_integral_salary and c.company_id._ne_es_colombia()):
            fecha_smmlv = fecha or contrato.date_start
            if not fecha_smmlv:
                continue
            veces = Parametro._get_parameter_from_code(
                'l10n_co_piso_salario_integral_smmlv', fecha_smmlv)
            smmlv = Parametro._get_parameter_from_code('l10n_co_smmlv', fecha_smmlv)
            piso = veces * smmlv
            moneda = contrato.company_id.currency_id
            if contrato.wage < piso:
                raise ValidationError(_(
                    "El contrato '%(contrato)s' de %(empleado)s es de salario integral con un "
                    "salario de %(salario)s, por debajo del piso de %(piso)s (%(veces)s SMMLV de "
                    "%(smmlv)s, vigente el %(fecha)s; CST art. 132). Corrija el Salario del "
                    "contrato o quite la marca \"Salario Integral\".",
                    contrato=contrato.name, empleado=contrato.employee_id.name,
                    salario=format_amount(self.env, contrato.wage, moneda),
                    piso=format_amount(self.env, piso, moneda), veces=veces,
                    smmlv=format_amount(self.env, smmlv, moneda), fecha=fecha_smmlv))

    @api.model_create_multi
    def create(self, vals_list):
        contratos = super().create(vals_list)
        contratos._ne_validar_piso_integral()
        return contratos

    def _ne_validar_cambio_de_etapa(self, vals):
        """H-F1-09 (D3, doc 88; Decreto 223 de 2026, art. 2.2.6.3.3.6, par. 3: solo la fase práctica o la formación dual cuentan como tiempo de servicio). La antigüedad para prima, cesantías y vacaciones sale de la
        fecha de inicio del contrato: un contrato con recibos confirmados de una etapa de aprendiz SIN prestaciones no puede pasar a NINGÚN régimen que las cause (práctica, formación dual o empleado). Un
        contrato por etapa. Se mira ANTES de escribir: la etapa de cada recibo confirmado con los datos actuales del contrato y el régimen nuevo con los datos que llegan, hoy."""
        Recibo = self.env['hr.payslip'].sudo()      # quien edita contratos (Empleados) no tiene por qué leer recibos ni parámetros de nómina: solo se usa para decidir y dar el error
        for contrato in self.filtered(lambda c: c.company_id._ne_es_colombia()):
            actual = (contrato.l10n_co_pila_tipo_cotizante or '', contrato.l10n_co_ne_contract_type or '')
            nuevo = (vals.get('l10n_co_pila_tipo_cotizante', actual[0]) or '', vals.get('l10n_co_ne_contract_type', actual[1]) or '')
            if nuevo == actual:
                continue
            if not Recibo._ne_regimen_de(nuevo[0], nuevo[1], fields.Date.context_today(contrato), contrato.employee_id.name)['causa_prestaciones']:
                continue
            for recibo in Recibo.search([('contract_id', '=', contrato.id), ('state', 'in', ('done', 'paid'))]):
                anterior = recibo._ne_regimen_cotizante()
                if anterior['es_aprendiz'] and not anterior['causa_prestaciones']:
                    raise UserError(_(
                        'El contrato «%(contrato)s» de %(empleado)s tiene recibos confirmados de una etapa de aprendiz sin prestaciones (por ejemplo «%(recibo)s») y no puede pasar a un régimen que las causa '
                        '(práctica, formación dual o empleado): la antigüedad para prima, cesantías y vacaciones sale de la fecha de inicio del contrato y contaría esa etapa (Decreto 223 de 2026, art. '
                        '2.2.6.3.3.6, parágrafo 3). Cierre este contrato y cree un contrato nuevo, con su fecha de inicio y el sueldo que le corresponde (en la práctica, el apoyo de esa etapa).',
                        contrato=contrato.name, empleado=contrato.employee_id.name, recibo=recibo.name))

    def write(self, vals):
        if {'l10n_co_pila_tipo_cotizante', 'l10n_co_ne_contract_type'} & set(vals):
            self._ne_validar_cambio_de_etapa(vals)
        resultado = super().write(vals)
        if {'wage', 'l10n_co_ne_integral_salary', 'date_start'} & set(vals):
            # Un cambio solo de salario se valida con el SMMLV de hoy; si se toca el ingreso o
            # la marca de integral, con el SMMLV de la fecha de inicio del contrato.
            solo_salario = 'wage' in vals and not {'l10n_co_ne_integral_salary', 'date_start'} & set(vals)
            self._ne_validar_piso_integral(fields.Date.context_today(self) if solo_salario else None)
        return resultado

    def _ne_valor_obligatorio(self, campo):
        """Valor de un campo que el contrato debe tener: sin el, error claro (nunca se asume un
        tipo de contrato o de cotizante por defecto)."""
        self.ensure_one()
        valor = self[campo]
        if not valor:
            raise UserError(_(
                'El contrato "%(contrato)s" de %(empleado)s no tiene "%(campo)s". Elíjalo en el '
                'contrato (nunca se asume un valor por defecto).',
                contrato=self.name, empleado=self.employee_id.name,
                campo=self._fields[campo].string))
        return valor

    _NE_CAMPOS_OBLIGATORIOS_EN_PROCESO = (
        'l10n_co_ne_contract_type', 'l10n_co_pila_tipo_cotizante', 'l10n_co_pila_subtipo_cotizante')

    @api.constrains('state', *_NE_CAMPOS_OBLIGATORIOS_EN_PROCESO)
    def _check_tipos_obligatorios_en_proceso(self):
        """Un contrato colombiano 'En proceso' exige tipo de contrato DIAN, tipo y subtipo de
        cotizante: no tienen valor por defecto (antes salian 'indefinido', 'dependiente')."""
        for contrato in self:
            if contrato.state != 'open' or not contrato.company_id._ne_es_colombia():
                continue
            faltan = [contrato._fields[c].string for c in self._NE_CAMPOS_OBLIGATORIOS_EN_PROCESO
                      if not contrato[c]]
            if faltan:
                raise ValidationError(_(
                    'El contrato "%(contrato)s" de %(empleado)s no puede pasar a "En proceso" sin: '
                    '%(faltan)s. Complételos en el contrato (Detalles del contrato y pestaña PILA).',
                    contrato=contrato.name, empleado=contrato.employee_id.name,
                    faltan=', '.join(faltan)))

    def _ne_clase_riesgo(self):
        """Clase de riesgo ARL efectiva: la del contrato y, si no tiene, la general de la
        empresa. Única fuente para el aporte ARL y para PILA. Sin ninguna: UserError."""
        self.ensure_one()
        clase = self.l10n_co_pila_clase_riesgo or self.company_id.l10n_co_pila_clase_riesgo
        if not clase:
            raise UserError(_(
                'No hay Clase de Riesgo ARL para el contrato de %(employee)s: ni el contrato '
                '(pestaña PILA) ni la empresa %(company)s (Nómina > Configuración > Ajustes, '
                'bloque PILA) la tienen configurada.',
                employee=self.employee_id.name, company=self.company_id.name))
        return clase

    def _ne_horas_semanales(self):
        """Horas semanales del HORARIO DE TRABAJO del contrato: la suma de las asistencias de trabajo de UNA semana (``resource.calendar._get_global_attendances``: sin la pausa del almuerzo, sin las secciones y sin las
        asistencias con fechas propias ni de un recurso); en un horario de dos semanas, la suma de las dos dividida por 2. Cero si el contrato no tiene horario o es de horas flexibles (sin jornada que sumar). Odoo 18 no
        trae un campo de horas semanales en el calendario (``hours_per_day`` es el promedio por día con jornada y ``full_time_required_hours`` es la jornada completa de la compañía)."""
        self.ensure_one()
        calendario = self.resource_calendar_id
        if not calendario or calendario.flexible_hours:
            return 0.0
        horas = sum(asistencia.hour_to - asistencia.hour_from for asistencia in calendario._get_global_attendances())
        return horas / 2 if calendario.two_weeks_calendar else horas

    def _ne_horas_laboradas_pila(self, dias, fecha):
        """Número de horas laboradas del registro tipo 2 de la PILA (campo 96; H-F2-02, decisión del TL del 22-nov, corregida por él mismo): UNA sola fuente, sin el 8 fijo de antes. Son las horas SEMANALES del horario de
        trabajo del contrato (``_ne_horas_semanales``) / 7 por los días cotizados ``dias`` (los de CCF/SENA/ICBF, ``CO_DIAS_PARAF``), redondeado a entero: la misma jornada de 42 h da 180 en 30 días trabaje 5 o 6 días a la
        semana (una fórmula de horas por día × días cotizados cuenta como trabajados los días de descanso). Sin horario, o con horario de horas flexibles, el campo va VACÍO: es opcional para la mayoría de los tipos
        de cotizante y no se inventa un valor. Si el tipo de cotizante del contrato es de los que lo exigen (parámetro ``l10n_co_pila_horas_laboradas_tipos``, p. ej. el 51 de tiempo parcial) y no hay de dónde sacarlo, error
        claro que nombra al empleado y qué completar. Devuelve un entero o ``''``. NO VERIFICADO: la lista de tipos que lo exigen (Resolución 980 de 2017, art. 2; texto consolidado del Anexo Técnico 2 sin leer) y
        qué espera el operador PILA en el campo."""
        self.ensure_one()
        semanales = self._ne_horas_semanales()
        if semanales > 0:
            return int(float_round(semanales / 7 * dias, precision_digits=0))
        try:
            exigidos = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_co_pila_horas_laboradas_tipos', fecha)
        except UserError:
            raise UserError(_(
                'Falta el parámetro de nómina «Colombia: Tipos de Cotizante que Exigen las Horas Laboradas en la PILA» (código l10n_co_pila_horas_laboradas_tipos) para el %(fecha)s, que se necesita para '
                'armar el campo de horas laboradas de %(empleado)s. Actualice el módulo de nómina electrónica o créelo en Nómina > Configuración > Parámetros de reglas.',
                fecha=fecha, empleado=self.employee_id.name)) from None
        if self.l10n_co_pila_tipo_cotizante in exigidos:
            raise UserError(_(
                'El tipo de cotizante %(tipo)s de %(empleado)s exige el número de horas laboradas en la PILA (campo 96) y el contrato %(contrato)s no tiene un horario de trabajo con jornada: no hay horario '
                'o es de horas flexibles. Asigne al contrato un horario de trabajo con sus horas de la semana (no flexible).',
                tipo=self.l10n_co_pila_tipo_cotizante, empleado=self.employee_id.name, contrato=self.name))
        return ''

    def _ne_centro_trabajo(self):
        """Centro de trabajo ARL efectivo (contrato -> empresa). Sin ninguno: UserError."""
        self.ensure_one()
        centro = self.l10n_co_pila_centro_trabajo or self.company_id.l10n_co_pila_centro_trabajo
        if not centro:
            raise UserError(_(
                'No hay Centro de Trabajo ARL para el contrato de %(employee)s: ni el contrato '
                '(pestaña PILA) ni la empresa %(company)s (Nómina > Configuración > Ajustes, '
                'bloque PILA) lo tienen configurado.',
                employee=self.employee_id.name, company=self.company_id.name))
        return centro

    @api.onchange('l10n_co_pila_actividad_economica')
    def _onchange_pila_actividad_economica(self):
        """Propone la Clase de Riesgo de la actividad elegida; el campo sigue editable."""
        actividad = self.l10n_co_pila_actividad_economica
        if actividad:
            self.l10n_co_pila_clase_riesgo = actividad.risk_class

    @api.onchange('l10n_co_pila_clase_riesgo')
    def _onchange_pila_clase_riesgo_vs_actividad(self):
        """Avisa (sin bloquear) si la clase editada a mano no coincide con la de la actividad."""
        actividad = self.l10n_co_pila_actividad_economica
        if actividad and self.l10n_co_pila_clase_riesgo != actividad.risk_class:
            etiquetas = dict(self._fields['l10n_co_pila_clase_riesgo'].selection)
            return {'warning': {
                'title': _('Clase de riesgo distinta a la de la actividad'),
                'message': _(
                    'La actividad %(actividad)s está clasificada en %(esperada)s, pero el contrato '
                    'tiene %(actual)s. Puede guardar, pero verifique que sea correcto.',
                    actividad=actividad.display_name,
                    esperada=etiquetas.get(actividad.risk_class, actividad.risk_class),
                    actual=etiquetas.get(self.l10n_co_pila_clase_riesgo, self.l10n_co_pila_clase_riesgo or ''),
                ),
            }}
