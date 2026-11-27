# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Asistente mejorado para generar el archivo plano PILA (v2).

Wizard de múltiples pasos que:
1. Paso 'draft': Seleccionar período y parámetros.
2. Paso 'validated': Validar datos de empleados, mostrar resumen.
3. Paso 'generated': Descargar archivo generado.

Genera el archivo PILA completo con registros Tipo 01 (encabezado)
+ Tipo 02 (detalle por cotizante).
"""

import base64
import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..services import pila_generator_v2
from ..services import dian_utils

_logger = logging.getLogger(__name__)


class L10nCoHrPilaWizardV2(models.TransientModel):
    """Asistente mejorado para generar el archivo plano PILA (v2).

    Genera un archivo TXT con separador pipe (|) compatible con
    los operadores de información PILA (SuAporte, SOI, Mi Planilla).
    Incluye registros Tipo 01 (encabezado) + Tipo 02 (detalle).
    """

    _name = 'l10n.co.hr.pila.wizard.v2'
    _description = 'Asistente PILA Completo (Tipo 1 + Tipo 2)'

    # ──────────────────────────────────────────────────────────────────
    # Campos de selección de período
    # ──────────────────────────────────────────────────────────────────
    year = fields.Char(
        string='Año',
        required=True,
        default=lambda self: str(fields.Date.context_today(self).year),
    )
    month = fields.Selection(
        selection=[
            ('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'),
            ('04', 'Abril'), ('05', 'Mayo'), ('06', 'Junio'),
            ('07', 'Julio'), ('08', 'Agosto'), ('09', 'Septiembre'),
            ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
        ],
        string='Mes',
        required=True,
        default=lambda self: '%02d' % fields.Date.context_today(self).month,
    )
    tipo_planilla = fields.Selection(
        selection=[
            ('E', 'E - Empleados empresa privada'),
            ('Y', 'Y - Independientes'),
            ('A', 'A - Cotizantes con novedad de ingreso'),
            ('I', 'I - Independientes'),
            ('S', 'S - Servicio domestico'),
            ('N', 'N - Correccion'),
            ('F', 'F - Pago Simple'),
            ('M', 'M - Mora'),
            ('H', 'H - Madres sustitutas'),
            ('T', 'T - Empleados entidad beneficiaria del SGP'),
            ('X', 'X - Planilla exclusiva CTA'),
            ('U', 'U - Planilla de uso UGPP'),
            ('K', 'K - Estudiantes ley 789/2002'),
            ('J', 'J - Pago acompanamiento juvenil'),
        ],
        string='Tipo Planilla',
        required=True,
        default='E',
    )
    modalidad_planilla = fields.Selection(
        selection=[
            ('1', '1 - Planilla única'),
            ('2', '2 - Planilla acumulada'),
        ],
        string='Modalidad Planilla',
        default='1',
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
    )

    # Planilla corregida (solo tipo N): el numero, la fecha de pago y el operador salen de
    # la planilla original registrada (l10n.co.pila.planilla), no se digitan.
    planilla_original_id = fields.Many2one(
        'l10n.co.pila.planilla', string='Planilla a Corregir',
        domain="[('company_id', '=', company_id), ('period', '=', periodo_date)]",
        help='Planilla original del MISMO mes que corrige esta planilla tipo N. Debe tener su número de '
             'planilla y fecha de pago, y haberse generado con el mismo operador.')
    periodo_date = fields.Date(
        string='Período (primer día)', compute='_compute_periodo_date',
        help='Primer día del mes cotizado; filtra la planilla a corregir.')
    numero_planilla_asociada = fields.Char(
        string='No. Planilla Asociada', related='planilla_original_id.numero_planilla')
    fecha_pago_asociada = fields.Date(
        string='Fecha Pago Asociada', related='planilla_original_id.fecha_pago')

    # ──────────────────────────────────────────────────────────────────
    # Estado del wizard (multi-step)
    # ──────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('validated', 'Validado'),
            ('generated', 'Generado'),
        ],
        default='draft',
        string='Estado',
    )

    # ──────────────────────────────────────────────────────────────────
    # Resultado de validación
    # ──────────────────────────────────────────────────────────────────
    validation_errors = fields.Text(
        string='Errores de Validacion',
        readonly=True,
    )
    validation_ok = fields.Boolean(
        string='Validacion Correcta',
        default=False,
    )

    # ──────────────────────────────────────────────────────────────────
    # Resumen (step 2)
    # ──────────────────────────────────────────────────────────────────
    summary_total_employees = fields.Integer(
        string='Total Empleados',
        readonly=True,
    )
    summary_total_ibc = fields.Monetary(
        string='Total IBC Pension',
        currency_field='currency_id',
        readonly=True,
    )
    summary_total_pension = fields.Monetary(
        string='Total Aporte Pension',
        currency_field='currency_id',
        readonly=True,
    )
    summary_total_salud = fields.Monetary(
        string='Total Aporte Salud',
        currency_field='currency_id',
        readonly=True,
    )
    summary_total_arl = fields.Monetary(
        string='Total Aporte ARL',
        currency_field='currency_id',
        readonly=True,
    )
    summary_total_ccf = fields.Monetary(
        string='Total Aporte CCF',
        currency_field='currency_id',
        readonly=True,
    )
    summary_total_sena = fields.Monetary(
        string='Total Aporte SENA',
        currency_field='currency_id',
        readonly=True,
    )
    summary_total_icbf = fields.Monetary(
        string='Total Aporte ICBF',
        currency_field='currency_id',
        readonly=True,
    )
    summary_total_general = fields.Monetary(
        string='Total General Aportes',
        currency_field='currency_id',
        readonly=True,
    )
    summary_total_nomina = fields.Monetary(
        string='Valor total de la nómina',
        help='Campo 20 del encabezado de la planilla: suma del IBC de Caja de Compensación de los cotizantes del archivo. No es el neto pagado.',
        currency_field='currency_id',
        readonly=True,
    )

    # ──────────────────────────────────────────────────────────────────
    # Resultado (archivo generado)
    # ──────────────────────────────────────────────────────────────────
    file_data = fields.Binary(
        string='Archivo PILA',
        readonly=True,
    )
    file_name = fields.Char(
        string='Nombre Archivo',
        readonly=True,
    )

    # ──────────────────────────────────────────────────────────────────
    # Computed display name
    # ──────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        wizards.company_id._ne_exigir_colombia()
        return wizards

    @api.depends('year', 'month', 'company_id')
    def _compute_display_name(self):
        """Calcula el nombre para mostrar del wizard."""
        for rec in self:
            rec.display_name = 'PILA %s-%s %s' % (
                rec.year or '',
                rec.month or '',
                rec.company_id.name or '',
            )

    # ──────────────────────────────────────────────────────────────────
    # Paso 1 → 2: Validar datos de empleados
    # ──────────────────────────────────────────────────────────────────
    @api.depends('year', 'month')
    def _compute_periodo_date(self):
        for rec in self:
            try:
                rec.periodo_date = date(int(rec.year), int(rec.month), 1)
            except (TypeError, ValueError):
                rec.periodo_date = False

    def _validar_planilla_correccion(self):
        """E (y las demas) no llevan planilla original; N la exige, completa y del mismo
        operador (restriccion del operador: la correccion va con el mismo operador)."""
        self.ensure_one()
        original = self.planilla_original_id
        if self.tipo_planilla != 'N':
            if original:
                raise UserError(_(
                    'Solo la planilla tipo N (corrección) lleva "Planilla a Corregir". '
                    'Quite la planilla original o cambie el tipo.'))
            return
        if not original:
            raise UserError(_('La planilla tipo N exige elegir la "Planilla a Corregir".'))
        if not original.numero_planilla or not original.fecha_pago:
            raise UserError(_(
                'La planilla "%s" no tiene número de planilla o fecha de pago. Complételos '
                'en Nómina > Reportes > Planillas PILA antes de corregirla.',
                original.display_name))
        if original.period != date(int(self.year), int(self.month), 1):
            raise UserError(_(
                'La planilla "%(orig)s" es del mes %(mes_orig)s; una planilla N corrige '
                'la presentación de ESE mes y esta es del %(mes)s-%(anio)s.',
                orig=original.display_name, mes_orig=original.period.strftime('%Y-%m'),
                mes=self.month, anio=self.year))
        operador = self.company_id.l10n_co_pila_operador_code
        if not operador:
            raise UserError(_('Defina el Código Operador PILA de la compañía.'))
        if original.operador_code != operador:
            raise UserError(_(
                'La corrección debe presentarse con el MISMO operador de la planilla '
                'original (%(orig)s), y la compañía tiene configurado %(actual)s.',
                orig=original.operador_code, actual=operador))

    def action_validate(self):
        """Valida que los empleados tengan todos los datos PILA requeridos.

        Verifica:
        - Que existan nóminas confirmadas en el período.
        - Que cada empleado tenga código EPS, AFP y CCF configurado.
        - Que la compañía tenga código ARL configurado.
        - Que los contratos tengan tipo/subtipo de cotizante.

        Si la validación es correcta, avanza al paso 'validated'
        con el resumen de totales.

        Returns:
            dict: Acción de ventana que recarga el wizard.

        Raises:
            UserError: Si no hay nóminas en el período.
        """
        self.ensure_one()
        self._validar_planilla_correccion()
        _logger.info(
            'Validando datos PILA para %s/%s - %s',
            self.month, self.year, self.company_id.name,
        )

        company = self.company_id
        year = int(self.year)
        month = int(self.month)

        # Buscar nóminas confirmadas del período
        payslips = self._get_period_payslips(company, year, month)

        if not payslips:
            raise UserError(_(
                'No se encontraron nominas confirmadas para el periodo '
                '%s/%s en la compania "%s".',
                self.month, self.year, company.name,
            ))

        # Validar datos de la compañía
        errors = []
        if not company.l10n_co_pila_arl_code:
            errors.append(
                '- Compania: Falta configurar la ARL (con su codigo PILA) '
                '(Configuracion > Nomina > PILA).'
            )
        if not company.vat:
            errors.append(
                '- Compania: Falta configurar el NIT/VAT de la compania.'
            )

        # Validar datos de cada empleado
        employees_checked = set()
        for payslip in payslips:
            emp = payslip.employee_id
            if emp.id in employees_checked:
                continue
            employees_checked.add(emp.id)

            contract = payslip.contract_id
            emp_name = emp.name or 'Sin nombre'

            # Validar código EPS
            if not getattr(emp, 'l10n_co_pila_eps_code', None):
                errors.append(
                    '- %s: Falta EPS o el contacto no tiene Codigo PILA.' % emp_name
                )

            # Validar código AFP
            if not getattr(emp, 'l10n_co_pila_afp_code', None):
                # Permitir vacío si es extranjero no obligado a pensión
                if not getattr(
                    emp, 'l10n_co_ne_foreigner_no_pension', False
                ):
                    errors.append(
                        '- %s: Falta AFP o el contacto no tiene Codigo PILA.' % emp_name
                    )

            # Validar código CCF
            try:
                ccf = emp._ne_caja_compensacion()
            except UserError as err:
                errors.append('- %s: %s' % (emp_name, err.args[0]))
            else:
                if not ccf.l10n_co_pila_entity_code:
                    errors.append(
                        '- %s: La Caja de Compensación no tiene Codigo PILA.' % emp_name
                    )

            # Validar la ubicación laboral (campos 9 y 10): mismo patrón que la CCF (H-F4-08, doc 99 §2; decisión del TL, Q2). Un
            # empleado sin ciudad o departamento con código DANE, o con una ciudad que no es de su departamento, se nombra aquí.
            try:
                payslip._ne_ubicacion_laboral_pila()
            except UserError as err:
                errors.append('- %s: %s' % (emp_name, err.args[0]))

            # Validar número de identificación
            if not emp.identification_id:
                errors.append(
                    '- %s: Falta numero de identificacion.' % emp_name
                )

            # Validar contrato activo
            if not contract:
                errors.append(
                    '- %s: No tiene contrato asociado a la nomina.'
                    % emp_name
                )

        # Calcular resumen sobre los mismos registros que lleva el archivo (.330)
        cotizantes = self._ne_cotizantes_pila(payslips)
        resumen = pila_generator_v2.compute_summary(cotizantes)

        # Preparar valores de actualización
        vals = {
            'validation_ok': len(errors) == 0,
            'validation_errors': '\n'.join(errors) if errors else '',
            'state': 'validated',
            'summary_total_employees': resumen['total_cotizantes'],
            'summary_total_ibc': resumen['total_ibc_pension'],
            'summary_total_pension': resumen['total_aporte_pension'],
            'summary_total_salud': resumen['total_aporte_salud'],
            'summary_total_arl': resumen['total_aporte_arl'],
            'summary_total_ccf': resumen['total_aporte_ccf'],
            'summary_total_sena': resumen['total_aporte_sena'],
            'summary_total_icbf': resumen['total_aporte_icbf'],
            'summary_total_general': resumen['total_general'],
            'summary_total_nomina': self._ne_valor_total_nomina(cotizantes),
        }
        self.write(vals)

        _logger.info(
            'Validacion PILA completada: %d errores, %d cotizantes',
            len(errors), resumen['total_cotizantes'],
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ──────────────────────────────────────────────────────────────────
    # Paso 2 → 3: Generar archivo PILA
    # ──────────────────────────────────────────────────────────────────
    def action_generate_pila(self):
        """Genera el archivo plano PILA completo (Tipo 01 + Tipo 02).

        Flujo:
        1. Busca nóminas confirmadas del período.
        2. Construye datos del aportante (Tipo 01).
        3. Construye datos de cada cotizante (Tipo 02).
        4. Genera el archivo TXT con pila_generator_v2.
        5. Almacena resultado como descargable.

        Returns:
            dict: Acción de ventana que recarga el wizard.

        Raises:
            UserError: Si hay errores de validación pendientes.
        """
        self.ensure_one()

        # Verificar que la validación fue exitosa
        if not self.validation_ok:
            raise UserError(_(
                'Existen errores de validacion pendientes. '
                'Corrija los errores antes de generar el archivo.'
            ))

        _logger.info(
            'Generando archivo PILA para %s/%s - %s',
            self.month, self.year, self.company_id.name,
        )

        company = self.company_id
        year = int(self.year)
        month = int(self.month)

        # Buscar nóminas del período
        payslips = self._get_period_payslips(company, year, month)

        if not payslips:
            raise UserError(_(
                'No se encontraron nominas confirmadas para el periodo '
                '%s/%s en la compania "%s".',
                self.month, self.year, company.name,
            ))

        # Construir datos de cotizantes (Tipo 02); el encabezado suma sus valores
        cotizantes = self._ne_cotizantes_pila(payslips)

        # Construir datos del aportante (Tipo 01)
        periodo_str = '%s-%s' % (self.year, self.month)
        aportante = self._build_aportante_data(
            company, payslips, periodo_str, cotizantes,
        )

        # Generar archivo completo
        file_content = pila_generator_v2.generate_pila_file_v2(
            aportante, cotizantes,
        )

        # Almacenar resultado
        filename = 'PILA_%s_%s_%s.txt' % (
            company.vat or 'COMPANY',
            self.year,
            self.month,
        )
        self._validar_planilla_correccion()
        self.write({
            'file_data': base64.b64encode(
                file_content.encode('utf-8'),
            ),
            'file_name': filename,
            'state': 'generated',
        })
        self._registrar_planilla(payslips)

        _logger.info(
            'Archivo PILA generado: %s (%d cotizantes)',
            filename, len(cotizantes),
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ──────────────────────────────────────────────────────────────────
    # Volver al paso anterior
    # ──────────────────────────────────────────────────────────────────
    def action_back_to_draft(self):
        """Regresa al paso de selección de período."""
        self.ensure_one()
        self.write({
            'state': 'draft',
            'validation_errors': '',
            'validation_ok': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_validated(self):
        """Regresa al paso de resumen/validación."""
        self.ensure_one()
        self.write({
            'state': 'validated',
            'file_data': False,
            'file_name': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ──────────────────────────────────────────────────────────────────
    # Búsqueda de nóminas del período
    # ──────────────────────────────────────────────────────────────────
    def _registrar_planilla(self, payslips):
        """Deja constancia de la planilla generada y de los IBC consolidados que uso."""
        self.ensure_one()
        periodo = date(int(self.year), int(self.month), 1)
        planilla = self.env['l10n.co.pila.planilla'].create({
            'company_id': self.company_id.id, 'period': periodo,
            'tipo_planilla': self.tipo_planilla,
            'operador_code': self.company_id.l10n_co_pila_operador_code or '',
            'planilla_original_id': self.planilla_original_id.id,
            'file_name': self.file_name,
        })
        for consolidado in self.env['l10n.co.ibc.mensual'].search([
                ('company_id', '=', self.company_id.id), ('period', '=', periodo),
                ('employee_id', 'in', payslips.mapped('employee_id').ids)]):
            consolidado.write({
                'planilla_id': planilla.id, 'ibc_sp_planilla': consolidado.ibc_sp,
                'ibc_arl_planilla': consolidado.ibc_arl,
                'ibc_paraf_planilla': consolidado.ibc_paraf})
        return planilla

    def _get_period_payslips(self, company, year, month):
        """Busca nóminas confirmadas del período indicado.

        Args:
            company: res.company recordset.
            year: int, año del período.
            month: int, mes del período.

        Returns:
            hr.payslip recordset filtrado por período y compañía.
        """
        date_from = date(year, month, 1)
        if month == 12:
            date_to = date(year + 1, 1, 1)
        else:
            date_to = date(year, month + 1, 1)

        return self.env['hr.payslip'].search([
            ('company_id', '=', company.id),
            ('state', 'in', ('done', 'paid')),
            # date_to y no date_from: la liquidacion tiene date_from = inicio de contrato.
            ('date_to', '>=', date_from),
            ('date_to', '<', date_to),
            # doc 39 (2026-10-04): excluir empleados sintéticos del
            # wizard de habilitación DIAN -- nunca son personal real,
            # no deben contarse en un reporte PILA real.
            ('employee_id.l10n_co_ne_is_habilitacion_test', '=', False),
        ])

    # ──────────────────────────────────────────────────────────────────
    # Builder: Datos del aportante (Tipo 01)
    # ──────────────────────────────────────────────────────────────────
    def _build_aportante_data(self, company, payslips, periodo_str, cotizantes):
        """Construye el diccionario de datos del aportante (Tipo 01).

        Lee los datos de configuración de la compañía y calcula
        totales de la planilla.

        Args:
            company: res.company recordset.
            payslips: hr.payslip recordset (nóminas del período).
            periodo_str: Período como 'YYYY-MM'.
            cotizantes: lista de registros tipo 2 del mismo archivo.

        Returns:
            dict con los campos del registro Tipo 01.
        """
        # Extraer NIT y DV
        nit_clean = dian_utils.clean_nit(company.vat, strip_dv=True)
        dv = dian_utils.compute_dv(nit_clean) if nit_clean else '0'

        # Tipo de documento del aportante
        tipo_doc = 'NI'
        if company.partner_id and hasattr(
                company.partner_id, 'l10n_co_document_type'):
            doc_type = company.partner_id.l10n_co_document_type
            if doc_type and doc_type != 'rut':
                tipo_doc = dian_utils.get_doc_type_code(doc_type)

        return {
            'tipo_registro': '01',
            'modalidad_planilla': self.modalidad_planilla or '1',
            'secuencia': '0001',
            'razon_social': company.name or '',
            'tipo_documento_aportante': tipo_doc,
            'numero_documento_aportante': nit_clean,
            'digito_verificacion': dv,
            'tipo_planilla': self.tipo_planilla,
            'numero_planilla_asociada': self.numero_planilla_asociada or '',
            'fecha_pago_asociada': str(self.fecha_pago_asociada)
            if self.fecha_pago_asociada else '',
            'forma_presentacion': company._ne_valor_obligatorio('l10n_co_pila_forma_presentacion'),
            'codigo_sucursal': company.l10n_co_pila_codigo_sucursal or '',
            'nombre_sucursal': company.l10n_co_pila_nombre_sucursal or '',
            'codigo_arl': company.l10n_co_pila_arl_code or '',
            'periodo_cotizacion_salud': periodo_str,
            'periodo_cotizacion_pension': periodo_str,
            'numero_total_cotizantes': len(payslips.mapped('employee_id')),          # .330: cotizantes, no recibos (igual que los registros tipo 2)
            'valor_total_nomina': self._ne_valor_total_nomina(cotizantes),
            'tipo_aportante': company._ne_valor_obligatorio('l10n_co_pila_tipo_aportante'),
            'codigo_operador': company.l10n_co_pila_operador_code or '',
            'fecha_pago': '',
            'numero_planilla': '',
        }

    # ──────────────────────────────────────────────────────────────────
    # Cotizantes del mes: uno por empleado
    # ──────────────────────────────────────────────────────────────────
    def _ne_cotizantes_pila(self, payslips):
        """Los registros tipo 2 del mes. H-017b: la PILA reporta UNA línea por cotizante y mes; sus recibos (quincenas, liquidación parcial, bonificación) se agrupan por empleado y el IBC y los días
        salen del consolidado mensual (``l10n.co.ibc.mensual``). Fuente única del resumen de la validación y del archivo (.330: el resumen contaba un cotizante por recibo y repetía su IBC del mes)."""
        cotizantes = []
        for secuencia, employee in enumerate(payslips.mapped('employee_id'), start=1):
            slips = payslips.filtered(lambda s: s.employee_id == employee)
            cotizantes.append(self._build_cotizante_data(self._ne_recibo_mas_reciente(slips), secuencia, slips))
        return cotizantes

    @api.model
    def _ne_valor_total_nomina(self, cotizantes):
        """Campo 20 del encabezado (Anexo Técnico 2 de la Res. 2388/2016, num. 2.1.1.1): suma del campo 45 «IBC CCF» de los registros tipo 2 del mismo archivo, redondeado como cada línea; quien no aporta a
        Caja lo lleva en cero. No es el neto pagado."""
        return sum(int(round(float(cotizante.get('ibc_ccf') or 0))) for cotizante in cotizantes)

    @api.model
    def _ne_recibo_mas_reciente(self, recibos):
        """H-F1-10: la línea PILA toma los datos del cotizante del recibo MÁS RECIENTE del mes (el orden nativo de ``hr.payslip`` es ``date_to desc``: ``[-1]`` daba el más antiguo). Igual que v19."""
        return recibos.sorted(lambda slip: (slip.date_to, slip.date_from, slip.id))[-1]

    # ──────────────────────────────────────────────────────────────────
    # Builder: Datos de cotizante (Tipo 02)
    # ──────────────────────────────────────────────────────────────────
    def _aportes_salud_pension(self, ibc_sp, ibc_sln, dias_sp, dias_sln, tarifa_afp, tarifa_eps, _p,
                               exonerado=False):
        """Salud y pensión del cotizante con la regla de SLN.

        Sobre los días de suspensión o licencia no remunerada el trabajador no paga su cuota;
        el empleador paga solo su tarifa de salud y, si la compañía lo decide (opcional en el
        sector privado: Concepto Min. Protección Social 134658, CST art. 53), su tarifa de
        pensión. Si el cotizante está exonerado del aporte patronal en salud, la tarifa patronal
        de salud sobre los días SLN es cero (guía del Min. Salud a los operadores, "Cotizante
        exonerado aporte patronal en salud y reporte de la novedad SLN"). Sin pensión SLN, IBC
        y días de pensión excluyen los días SLN."""
        cotiza = self.company_id.l10n_co_ne_pension_patronal_sln
        ibc_normal = ibc_sp - ibc_sln
        return {
            'ibc_pension': ibc_sp if cotiza else ibc_normal,
            'dias_pension': dias_sp if cotiza else dias_sp - dias_sln,
            'cotizacion_pension': round(
                ibc_normal * tarifa_afp
                + (ibc_sln * _p('l10n_co_pct_pension_empleador') / 100 if cotiza else 0.0)),
            'cotizacion_salud': round(
                ibc_normal * tarifa_eps
                + (0.0 if exonerado else ibc_sln * _p('l10n_co_pct_salud_empleador') / 100)),
        }

    def _build_cotizante_data(self, payslip, seq, payslips=None):
        """Construye el diccionario de datos de un cotizante (Tipo 02).

        Lee datos del empleado, contrato y líneas de nómina para
        generar los 98 campos del registro Tipo 02.

        Args:
            payslip: hr.payslip recordset (la nómina más reciente del mes).
            seq: int, número de secuencia.
            payslips: todos los recibos del empleado en el mes (por defecto, solo `payslip`).

        Returns:
            dict con todos los campos del registro Tipo 02.
        """
        employee = payslip.employee_id
        contract = payslip.contract_id
        payslips = payslips or payslip

        # IBC y dias consolidados del empleado en el mes (H-017b): unica fuente.
        consolidado = self.env['l10n.co.ibc.mensual']._refrescar(
            payslip.company_id, employee, payslip.date_to)
        if not consolidado:
            raise UserError(_(
                'No hay IBC consolidado para %(empleado)s en %(mes)s: ningun recibo '
                'confirmado trae las lineas de IBC. Recalcule y confirme la nomina.',
                empleado=employee.name, mes=payslip.date_to.strftime('%Y-%m')))

        # Separar nombre completo en componentes
        name_parts = employee._l10n_co_nombre_dian()

        # Mapeo tipo de documento al formato PILA
        doc_type_code = dian_utils.get_doc_type_code(
            getattr(employee, 'l10n_co_document_type', None)
            or 'id_card'
        )
        # Convertir código numérico DIAN a código PILA
        PILA_DOC_MAP = {
            '13': 'CC', '31': 'NI', '22': 'CE', '41': 'PA',
            '42': 'CD', '11': 'RC', '12': 'TI', '91': 'CC',
            '47': 'PE', '48': 'PT', '50': 'NI',
        }
        tipo_doc_pila = PILA_DOC_MAP.get(doc_type_code, 'CC')

        # Campos 9 y 10: departamento y municipio de la UBICACIÓN LABORAL (no del domicilio) del cotizante, Anexo Técnico 2 de la
        # Res. 2388/2016. Misma fuente que los LugarTrabajo* del XML (la Dirección de Trabajo); sin dato, error que nombra al empleado.
        # H-F4-08 (doc 99): antes leía ``address_home_id``, que no existe en Odoo 18, y salían en blanco para todos.
        dept_code, city_code = payslip._ne_ubicacion_laboral_pila()

        # Función auxiliar para obtener valor de línea de nómina
        def get_line(code):
            """Valor del concepto en el mes, en positivo: las líneas de todos los recibos se suman CON su signo (un reembolso resta lo del recibo que anula)."""
            lines = payslips.line_ids.filtered(lambda l: l.code == code)
            return abs(sum(lines.mapped('total')))

        RuleParameter = self.env['hr.rule.parameter']

        def _p(code):
            return RuleParameter._get_parameter_from_code(
                code, payslip._ne_fecha_parametros())          # en la liquidación «Desde» es el inicio del contrato

        # Datos del contrato
        salario = contract.wage or 0
        integral = bool(
            getattr(contract, 'l10n_co_ne_integral_salary', False))

        # IBC y dias por subsistema: del consolidado mensual (40%, piso, techo ya aplicados)
        ibc_sp = consolidado.ibc_sp
        ibc_arl = consolidado.ibc_arl
        ibc_paraf = consolidado.ibc_paraf
        dias_sp = consolidado.dias_sp
        dias_arl = consolidado.dias_arl
        dias_paraf = consolidado.dias_paraf

        # Aportes desde líneas de nómina
        salud_emp = get_line('CO_SALUD_EMP')
        pension_emp = get_line('CO_PENSION_EMP')
        fsp = get_line('CO_FSP')
        arl = get_line('CO_ARL_CIA')
        salud_cia = get_line('CO_SALUD_CIA')
        pension_cia = get_line('CO_PENSION_CIA')
        sena = get_line('CO_SENA_CIA')
        icbf = get_line('CO_ICBF_CIA')
        ccf = get_line('CO_CCF_CIA')

        # Tarifas (hr.rule.parameter, doc 13)
        tarifa_afp = (
            _p('l10n_co_pct_pension_empleado')
            + _p('l10n_co_pct_pension_empleador')
        ) / 100
        tarifa_eps = (
            _p('l10n_co_pct_salud_empleado')
            + _p('l10n_co_pct_salud_empleador')
        ) / 100
        # H-005: tarifa según la Clase de Riesgo ARL del contrato (misma fuente que CO_ARL_CIA).
        tarifa_arl = payslip._ne_pct_arl() / 100
        tarifa_ccf = _p('l10n_co_pct_ccf') / 100
        tarifa_sena = _p('l10n_co_pct_sena') / 100
        tarifa_icbf = _p('l10n_co_pct_icbf') / 100

        # Detectar novedades del período
        novedades = self._detect_novedades(payslip, payslips)

        # Indicador de exoneración parafiscales (Art. 114-1 ET, Ley 1607/2012)
        # -- mismo criterio centralizado que usan las reglas salariales
        # CO_SENA_CIA/CO_ICBF_CIA/CO_SALUD_CIA, para que PILA y nómina no
        # puedan divergir para el mismo empleado.
        ibc_sln = min(consolidado.ibc_sln, ibc_sp)
        dias_sln = min(consolidado.dias_sln, dias_sp)
        # La base SLN no es remuneracion devengada: no cuenta para el umbral de exoneracion.
        exonerado = 'S' if self.company_id._is_exonerado_parafiscales(
            ibc_sp - ibc_sln, payslip._ne_fecha_parametros()) else 'N'

        # Cálculos de aportes
        # Sobre el IBC consolidado (lo que realmente se paga en la planilla). Las lineas de
        # los recibos pueden diferir en meses con varios documentos; la diferencia queda
        # auditable en l10n.co.ibc.mensual (ajuste patronal), no se reescribe el recibo.
        sp = self._aportes_salud_pension(
            ibc_sp, ibc_sln, dias_sp, dias_sln, tarifa_afp, tarifa_eps, _p,
            exonerado=exonerado == 'S')
        ibc_pension = sp['ibc_pension']
        dias_pension = sp['dias_pension']
        cotizacion_pension = sp['cotizacion_pension']
        cotizacion_salud = sp['cotizacion_salud']
        cotizacion_arl = round(ibc_arl * tarifa_arl)
        aporte_ccf_val = round(ibc_paraf * tarifa_ccf)
        aporte_sena_val = round(ibc_paraf * tarifa_sena)
        aporte_icbf_val = round(ibc_paraf * tarifa_icbf)
        avp_afiliado = get_line('CO_PENSION_VOL')
        total_pension = cotizacion_pension + round(fsp) + avp_afiliado

        return {
            # Identificación
            'tipo_registro': '02',
            'secuencia': str(seq).zfill(5),
            'tipo_documento': tipo_doc_pila,
            'numero_documento': employee.identification_id or '',
            'tipo_cotizante': contract._ne_valor_obligatorio('l10n_co_pila_tipo_cotizante'),
            'subtipo_cotizante': contract._ne_valor_obligatorio('l10n_co_pila_subtipo_cotizante'),
            'extranjero_no_pension': 'X' if getattr(
                employee, 'l10n_co_ne_foreigner_no_pension', False
            ) else '',
            'colombiano_exterior': 'X' if getattr(
                employee, 'l10n_co_pila_colombiano_exterior', False
            ) else '',
            'codigo_departamento': dept_code,
            'codigo_municipio': city_code,
            'primer_apellido': name_parts['primer_apellido'],
            'segundo_apellido': name_parts['segundo_apellido'],
            'primer_nombre': name_parts['primer_nombre'],
            'segundo_nombre': name_parts['otros_nombres'],

            # Novedades
            'nov_ing': novedades.get('ing', ''),
            'nov_ret': novedades.get('ret', ''),
            'nov_tde': novedades.get('tde', ''),
            'nov_tae': novedades.get('tae', ''),
            'nov_tdp': novedades.get('tdp', ''),
            'nov_tap': novedades.get('tap', ''),
            'nov_vsp': novedades.get('vsp', ''),
            'nov_correcciones': novedades.get('linea', ''),
            'nov_vst': novedades.get('vst', ''),
            'nov_sln': novedades.get('sln', ''),
            'nov_ige': novedades.get('ige', ''),
            'nov_lma': novedades.get('lma', ''),
            'nov_vac': novedades.get('vac_lr', ''),
            'nov_avp': novedades.get('avp', ''),
            'nov_vct': novedades.get('vct', ''),
            'nov_irl': novedades.get('irl', 0),

            # Administradoras
            'codigo_afp': getattr(
                employee, 'l10n_co_pila_afp_code', '') or '',
            'codigo_afp_traslado': getattr(
                employee, 'l10n_co_pila_afp_traslado', '') or '',
            'codigo_eps': getattr(
                employee, 'l10n_co_pila_eps_code', '') or '',
            'codigo_eps_traslado': getattr(
                employee, 'l10n_co_pila_eps_traslado', '') or '',
            'codigo_ccf': employee._ne_caja_compensacion().l10n_co_pila_entity_code or '',

            # Días cotizados
            'dias_pension': dias_pension,
            'dias_salud': dias_sp,
            'dias_arl': dias_arl,
            'dias_ccf': dias_paraf,

            # Salario
            'salario_basico': salario,
            'salario_integral': 'X' if integral else '',

            # IBC por subsistema
            'ibc_pension': ibc_pension,
            'ibc_salud': ibc_sp,
            'ibc_arl': ibc_arl,
            'ibc_ccf': ibc_paraf,

            # Pensión
            'tarifa_pension': tarifa_afp,
            'cotizacion_pension': cotizacion_pension,
            'avp_afiliado': avp_afiliado,
            'avp_aportante': 0,
            'total_cotizacion_pension': total_pension,
            'aporte_fsp_subcuenta': round(fsp),
            'aporte_fsp_subsistencia': 0,
            'valor_no_retenido': 0,

            # Salud
            'tarifa_salud': tarifa_eps,
            'cotizacion_salud': cotizacion_salud,
            'valor_upc': 0,
            'numero_autorizacion_ige': '',
            'valor_incapacidad_ige': 0,
            'numero_autorizacion_lma': '',
            'valor_licencia_lma': 0,

            # ARL
            'tarifa_arl': tarifa_arl,
            'centro_trabajo': contract._ne_centro_trabajo(),
            'cotizacion_arl': cotizacion_arl,

            # Parafiscales
            'tarifa_ccf': tarifa_ccf,
            'aporte_ccf': aporte_ccf_val,
            'tarifa_sena': tarifa_sena,
            'aporte_sena': aporte_sena_val,
            'tarifa_icbf': tarifa_icbf,
            'aporte_icbf': aporte_icbf_val,
            'tarifa_esap': 0,
            'aporte_esap': 0,
            'tarifa_men': 0,
            'aporte_men': 0,

            # UPC / Exoneración
            'tipo_documento_upc': '',
            'numero_documento_upc': '',
            'exonerado_parafiscales': exonerado,

            # ARL detalle
            'codigo_arl': getattr(
                self.company_id, 'l10n_co_pila_arl_code', '') or '',
            'clase_riesgo': contract._ne_clase_riesgo(),
            'tarifa_especial_pension': getattr(
                contract, 'l10n_co_pila_tarifa_especial_afp', '') or '',

            # Fechas de novedades
            'fecha_ingreso': novedades.get('fecha_ing', ''),
            'fecha_retiro': novedades.get('fecha_ret', ''),
            'fecha_inicio_vsp': novedades.get('fecha_inicio_vsp', ''),
            'fecha_inicio_sln': novedades.get('fecha_inicio_sln', ''),
            'fecha_fin_sln': novedades.get('fecha_fin_sln', ''),
            'fecha_inicio_ige': novedades.get('fecha_inicio_ige', ''),
            'fecha_fin_ige': novedades.get('fecha_fin_ige', ''),
            'fecha_inicio_lma': novedades.get('fecha_inicio_lma', ''),
            'fecha_fin_lma': novedades.get('fecha_fin_lma', ''),
            'fecha_inicio_vac': novedades.get('fecha_inicio_vac_lr', ''),
            'fecha_fin_vac': novedades.get('fecha_fin_vac_lr', ''),
            'fecha_inicio_vct': novedades.get('fecha_inicio_vct', ''),
            'fecha_fin_vct': novedades.get('fecha_fin_vct', ''),
            'fecha_inicio_irl': novedades.get('fecha_inicio_irl', ''),
            'fecha_fin_irl': novedades.get('fecha_fin_irl', ''),

            # Campos finales
            'ibc_otros_parafiscales': ibc_paraf,
            'horas_laboradas': contract._ne_horas_laboradas_pila(dias_paraf, payslip._ne_fecha_parametros()),      # H-F2-02: del horario del contrato; vacio si no hay (opcional)
            'fecha_radicacion_exterior': str(
                getattr(employee, 'l10n_co_pila_fecha_radicacion_ext', '')
                or '') if getattr(
                employee, 'l10n_co_pila_colombiano_exterior', False
            ) else '',
            'actividad_economica_arl': (
                contract.l10n_co_pila_actividad_economica.code or ''),
        }

    # ──────────────────────────────────────────────────────────────────
    # Detección de novedades
    # ──────────────────────────────────────────────────────────────────
    # Código del tipo de entrada de trabajo -> (novedad, marca) del registro tipo 2 (Anexo Técnico 2 de la Res. 2388/2016, campos 24 SLN, 25 IGE, 26 LMA, 27 VAC-LR y 30 IRL). Son códigos internos del
    # módulo y letras del formato, no valores que cambie la ley. IRL no lleva letra: el campo es el número de días.
    _NE_MARCA_PILA_POR_CODIGO = {
        'CO_LIC_NR': ('sln', 'X'),
        'CO_INC_COMUN': ('ige', 'X'),
        'CO_LIC_MAT': ('lma', 'X'),
        'CO_LIC_PAT': ('lma', 'X'),
        'CO_VAC': ('vac_lr', 'X'),
        'CO_LIC_REM': ('vac_lr', 'L'),
        'CO_INC_LABORAL': ('irl', None),
    }

    def _detect_novedades(self, payslip, recibos=None):
        """Detecta las novedades PILA del MES desde los contratos, hr.leave y los recibos.

        Analiza los contratos (fechas de ingreso/retiro), las
        ausencias validadas (incapacidades, maternidad, vacaciones,
        etc.) y el aporte voluntario de TODOS los recibos del mes
        (.330: antes solo se miraba el recibo de la línea).

        Args:
            payslip: hr.payslip del que sale la línea (el más reciente del mes).
            recibos: todos los recibos del mes del cotizante; sin él, solo ``payslip``.

        Returns:
            dict con las claves de novedades para el registro Tipo 02.
        """
        recibos = recibos or payslip
        contract = payslip.contract_id
        # El mes sale del «Hasta»: en la liquidación «Desde» es el inicio del contrato.
        inicio_mes = payslip.date_to.replace(day=1)
        siguiente = (inicio_mes + timedelta(days=32)).replace(day=1)
        fin_mes = siguiente - timedelta(days=1)
        nov = {
            'ing': '', 'fecha_ing': '',
            'ret': '', 'fecha_ret': '',
            'tde': '', 'tae': '',
            'tdp': '', 'tap': '',
            'vsp': '', 'linea': '', 'fecha_inicio_vsp': '',
            'vst': '',
            'sln': '', 'fecha_inicio_sln': '', 'fecha_fin_sln': '',
            'ige': '', 'fecha_inicio_ige': '', 'fecha_fin_ige': '',
            'lma': '', 'fecha_inicio_lma': '', 'fecha_fin_lma': '',
            'vac_lr': '', 'fecha_inicio_vac_lr': '', 'fecha_fin_vac_lr': '',
            'avp': '',
            'vct': '', 'fecha_inicio_vct': '', 'fecha_fin_vct': '',
            'irl': 0, 'fecha_inicio_irl': '', 'fecha_fin_irl': '',          # campo 30: numérico, días de incapacidad por riesgo laboral
        }

        # Ingreso: el contrato más antiguo de los recibos del mes empezó en el mes (un otrosí no es un ingreso)
        ingreso = min(recibos.mapped('contract_id').filtered('date_start').mapped('date_start'), default=False)
        if ingreso and inicio_mes <= ingreso < siguiente:
            nov['ing'] = 'X'
            nov['fecha_ing'] = str(ingreso)

        # Retiro: el contrato del recibo más reciente termina en el mes (el que termina para seguir con otro no es un retiro)
        if contract.date_end and inicio_mes <= contract.date_end < siguiente:
            nov['ret'] = 'X'
            nov['fecha_ret'] = str(contract.date_end)

        # Ausencias validadas del empleado que tocan el mes, en orden: con dos del mismo campo quedan la marca y las fechas de la última (la línea por novedad aún no existe)
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', payslip.employee_id.id),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', fin_mes),
            ('request_date_to', '>=', inicio_mes),
        ], order='request_date_from, id')

        dias_irl = 0
        for leave in leaves:
            # La marca sale del código del tipo de entrada de trabajo (el mismo que usa la nómina), nunca del nombre de la ausencia
            campo, marca = self._NE_MARCA_PILA_POR_CODIGO.get(leave.holiday_status_id.work_entry_type_id.code, (False, False))
            if not campo:
                continue
            if campo == 'irl':
                dias_irl += payslip._ne_dias_comerciales(max(leave.request_date_from, inicio_mes), min(leave.request_date_to, fin_mes))
            else:
                nov[campo] = marca
            nov['fecha_inicio_%s' % campo] = str(leave.request_date_from)
            nov['fecha_fin_%s' % campo] = str(leave.request_date_to)
        if dias_irl:
            nov['irl'] = int(min(dias_irl, payslip._rule_parameter('l10n_co_dias_mes_comercial', payslip._ne_fecha_parametros())))

        # Aporte voluntario a pensión: lo que queda en el mes sumando los recibos con su signo (un aporte reembolsado no se marca)
        aporte_voluntario = sum(recibos.line_ids.filtered(lambda l: l.code == 'CO_PENSION_VOL').mapped('total'))
        if not payslip.company_id.currency_id.is_zero(aporte_voluntario):
            nov['avp'] = 'X'

        return nov
