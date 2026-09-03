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
from datetime import date

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
            ('1', '1 - Planilla unica'),
            ('2', '2 - Planilla acumulada'),
        ],
        string='Modalidad Planilla',
        default='1',
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compania',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
    )

    # Número de planilla asociada (para correcciones)
    numero_planilla_asociada = fields.Char(
        string='No. Planilla Asociada',
        help='Numero de planilla asociada. Solo aplica para planillas '
             'de correccion (tipo N).',
    )
    fecha_pago_asociada = fields.Date(
        string='Fecha Pago Asociada',
        help='Fecha de pago de la planilla asociada. '
             'Solo para correcciones.',
    )

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
        string='Total Nomina',
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
                '- Compania: Falta configurar el codigo ARL '
                '(Configuracion > Compania > PILA).'
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
                    '- %s: Falta codigo EPS.' % emp_name
                )

            # Validar código AFP
            if not getattr(emp, 'l10n_co_pila_afp_code', None):
                # Permitir vacío si es extranjero no obligado a pensión
                if not getattr(
                    emp, 'l10n_co_ne_foreigner_no_pension', False
                ):
                    errors.append(
                        '- %s: Falta codigo AFP.' % emp_name
                    )

            # Validar código CCF
            if not getattr(emp, 'l10n_co_pila_ccf_code', None):
                errors.append(
                    '- %s: Falta codigo CCF.' % emp_name
                )

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

        # Construir datos de cotizantes para el resumen
        periodo_str = '%s-%s' % (self.year, self.month)
        cotizantes_data = []
        seq = 1
        for payslip in payslips:
            cotizante = self._build_cotizante_data(payslip, seq)
            cotizantes_data.append(cotizante)
            seq += 1

        # Calcular resumen
        resumen = pila_generator_v2.compute_summary(cotizantes_data)

        # Calcular total nómina
        total_nomina = sum(
            p.line_ids.filtered(
                lambda l: l.code == 'CO_NETO'
            ).mapped('total')
            for p in payslips
        )

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
            'summary_total_nomina': total_nomina,
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

        # Construir datos del aportante (Tipo 01)
        periodo_str = '%s-%s' % (self.year, self.month)
        aportante = self._build_aportante_data(
            company, payslips, periodo_str,
        )

        # Construir datos de cotizantes (Tipo 02)
        cotizantes = []
        seq = 1
        for payslip in payslips:
            cotizante = self._build_cotizante_data(payslip, seq)
            cotizantes.append(cotizante)
            seq += 1

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
        self.write({
            'file_data': base64.b64encode(
                file_content.encode('utf-8'),
            ),
            'file_name': filename,
            'state': 'generated',
        })

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
            ('state', '=', 'done'),
            ('date_from', '>=', date_from),
            ('date_from', '<', date_to),
        ])

    # ──────────────────────────────────────────────────────────────────
    # Builder: Datos del aportante (Tipo 01)
    # ──────────────────────────────────────────────────────────────────
    def _build_aportante_data(self, company, payslips, periodo_str):
        """Construye el diccionario de datos del aportante (Tipo 01).

        Lee los datos de configuración de la compañía y calcula
        totales de la planilla.

        Args:
            company: res.company recordset.
            payslips: hr.payslip recordset (nóminas del período).
            periodo_str: Período como 'YYYY-MM'.

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

        # Total nómina
        total_nomina = sum(
            p.line_ids.filtered(
                lambda l: l.code == 'CO_NETO'
            ).mapped('total')
            for p in payslips
        )

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
            'forma_presentacion': company.l10n_co_pila_forma_presentacion
            or 'U',
            'codigo_sucursal': company.l10n_co_pila_codigo_sucursal or '',
            'nombre_sucursal': company.l10n_co_pila_nombre_sucursal or '',
            'codigo_arl': company.l10n_co_pila_arl_code or '',
            'periodo_cotizacion_salud': periodo_str,
            'periodo_cotizacion_pension': periodo_str,
            'numero_total_cotizantes': len(payslips),
            'valor_total_nomina': total_nomina,
            'tipo_aportante': company.l10n_co_pila_tipo_aportante or '1',
            'codigo_operador': company.l10n_co_pila_operador_code or '',
            'fecha_pago': '',
            'numero_planilla': '',
        }

    # ──────────────────────────────────────────────────────────────────
    # Builder: Datos de cotizante (Tipo 02)
    # ──────────────────────────────────────────────────────────────────
    def _build_cotizante_data(self, payslip, seq):
        """Construye el diccionario de datos de un cotizante (Tipo 02).

        Lee datos del empleado, contrato y líneas de nómina para
        generar los 98 campos del registro Tipo 02.

        Args:
            payslip: hr.payslip recordset (una nómina).
            seq: int, número de secuencia.

        Returns:
            dict con todos los campos del registro Tipo 02.
        """
        employee = payslip.employee_id
        contract = payslip.contract_id

        # Separar nombre completo en componentes
        name_parts = dian_utils.split_name(employee.name or '')

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

        # Departamento y municipio del domicilio
        dept_code = ''
        city_code = ''
        if hasattr(employee, 'address_home_id') and employee.address_home_id:
            partner = employee.address_home_id
            dept_code = dian_utils.get_department_code(
                partner.state_id) if partner.state_id else ''
            city_code = dian_utils.get_city_code(
                getattr(partner, 'city_id', None))

        # Función auxiliar para obtener valor de línea de nómina
        def get_line(code):
            """Obtiene el valor absoluto de una línea de nómina por código."""
            line = payslip.line_ids.filtered(lambda l: l.code == code)
            return abs(line.total) if line else 0.0

        _params = self.company_id._get_co_payroll_params(payslip.date_from)

        # Datos del contrato
        salario = contract.wage or 0
        integral = bool(
            getattr(contract, 'l10n_co_ne_integral_salary', False))

        # Cálculo del IBC
        ibc_base = get_line('CO_BRUTO') or salario
        if integral:
            # Salario integral: IBC = factor_integral_salary del salario
            ibc_base = salario * _params.factor_integral_salary

        # Días trabajados
        dias = _params.dias_mes_comercial  # Default: mes completo
        worked = payslip.worked_days_line_ids.filtered(
            lambda w: w.code == 'WORK100')
        if worked:
            dias = min(int(worked.number_of_days), _params.dias_mes_comercial)

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

        # Tarifas (Parámetros Anuales)
        tarifa_afp = _params.pct_pension_total / 100
        tarifa_eps = _params.pct_salud_total / 100
        tarifa_arl = _params.pct_arl_default / 100  # Riesgo I por defecto
        tarifa_ccf = _params.pct_ccf / 100
        tarifa_sena = _params.pct_sena / 100
        tarifa_icbf = _params.pct_icbf / 100

        # Detectar novedades del período
        novedades = self._detect_novedades(payslip)

        # Indicador de exoneración parafiscales (Art. 114-1 ET, Ley 1607/2012)
        # -- mismo criterio centralizado que usan las reglas salariales
        # CO_SENA_CIA/CO_ICBF_CIA/CO_SALUD_CIA, para que PILA y nómina no
        # puedan divergir para el mismo empleado.
        exonerado = 'S' if self.company_id._is_exonerado_parafiscales(
            ibc_base, payslip.date_from) else 'N'

        # Cálculos de aportes
        cotizacion_pension = round(ibc_base * tarifa_afp)
        cotizacion_salud = round(ibc_base * tarifa_eps)
        cotizacion_arl = round(arl) if arl else round(ibc_base * tarifa_arl)
        aporte_ccf_val = round(ccf) if ccf else round(ibc_base * tarifa_ccf)
        aporte_sena_val = round(sena) if sena else round(
            ibc_base * tarifa_sena)
        aporte_icbf_val = round(icbf) if icbf else round(
            ibc_base * tarifa_icbf)
        avp_afiliado = get_line('CO_PENSION_VOL')
        total_pension = cotizacion_pension + round(fsp) + avp_afiliado

        return {
            # Identificación
            'tipo_registro': '02',
            'secuencia': str(seq).zfill(5),
            'tipo_documento': tipo_doc_pila,
            'numero_documento': employee.identification_id or '',
            'tipo_cotizante': getattr(
                contract, 'l10n_co_pila_tipo_cotizante', '01') or '01',
            'subtipo_cotizante': getattr(
                contract, 'l10n_co_pila_subtipo_cotizante', '00') or '00',
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
            'nov_irl': novedades.get('irl', ''),

            # Administradoras
            'codigo_afp': getattr(
                employee, 'l10n_co_pila_afp_code', '') or '',
            'codigo_afp_traslado': getattr(
                employee, 'l10n_co_pila_afp_traslado', '') or '',
            'codigo_eps': getattr(
                employee, 'l10n_co_pila_eps_code', '') or '',
            'codigo_eps_traslado': getattr(
                employee, 'l10n_co_pila_eps_traslado', '') or '',
            'codigo_ccf': getattr(
                employee, 'l10n_co_pila_ccf_code', '') or '',

            # Días cotizados
            'dias_pension': dias,
            'dias_salud': dias,
            'dias_arl': dias,
            'dias_ccf': dias,

            # Salario
            'salario_basico': salario,
            'salario_integral': 'X' if integral else '',

            # IBC por subsistema
            'ibc_pension': ibc_base,
            'ibc_salud': ibc_base,
            'ibc_arl': ibc_base,
            'ibc_ccf': ibc_base,

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
            'centro_trabajo': getattr(
                contract, 'l10n_co_pila_centro_trabajo', '') or '',
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
            'clase_riesgo': getattr(
                contract, 'l10n_co_pila_clase_riesgo', '1') or '1',
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
            'ibc_otros_parafiscales': ibc_base,
            'horas_laboradas': dias * 8,
            'fecha_radicacion_exterior': str(
                getattr(employee, 'l10n_co_pila_fecha_radicacion_ext', '')
                or '') if getattr(
                employee, 'l10n_co_pila_colombiano_exterior', False
            ) else '',
            'actividad_economica_arl': getattr(
                contract, 'l10n_co_pila_actividad_economica', '') or '',
        }

    # ──────────────────────────────────────────────────────────────────
    # Detección de novedades
    # ──────────────────────────────────────────────────────────────────
    def _detect_novedades(self, payslip):
        """Detecta novedades del período desde hr.leave y contrato.

        Analiza el contrato (fechas de ingreso/retiro) y las
        ausencias validadas (incapacidades, maternidad, vacaciones,
        etc.) para determinar las marcas de novedades PILA.

        Args:
            payslip: hr.payslip recordset.

        Returns:
            dict con las claves de novedades para el registro Tipo 02.
        """
        contract = payslip.contract_id
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
            'irl': '', 'fecha_inicio_irl': '', 'fecha_fin_irl': '',
        }

        # Ingreso: si fecha inicio del contrato está en el período
        if contract.date_start:
            cs = contract.date_start
            if (cs.year == payslip.date_from.year
                    and cs.month == payslip.date_from.month):
                nov['ing'] = 'X'
                nov['fecha_ing'] = str(cs)

        # Retiro: si contrato tiene fecha fin en el período
        if contract.date_end:
            ce = contract.date_end
            if (ce.year == payslip.date_from.year
                    and ce.month == payslip.date_from.month):
                nov['ret'] = 'X'
                nov['fecha_ret'] = str(ce)

        # Buscar ausencias validadas del empleado en el período
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', payslip.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', payslip.date_to),
            ('date_to', '>=', payslip.date_from),
        ])

        for leave in leaves:
            leave_type = leave.holiday_status_id
            code = getattr(leave_type, 'code', '') or ''
            name = (leave_type.name or '').upper()

            d_from = leave.date_from.date() if leave.date_from else ''
            d_to = leave.date_to.date() if leave.date_to else ''

            if 'IGE' in code or 'INCAPACIDAD' in name:
                nov['ige'] = 'X'
                nov['fecha_inicio_ige'] = str(d_from) if d_from else ''
                nov['fecha_fin_ige'] = str(d_to) if d_to else ''
            elif 'IRL' in code or 'LABORAL' in name or 'ARL' in name:
                nov['irl'] = 'X'
                nov['fecha_inicio_irl'] = str(d_from) if d_from else ''
                nov['fecha_fin_irl'] = str(d_to) if d_to else ''
            elif 'LMA' in code or 'MATERNIDAD' in name:
                nov['lma'] = 'X'
                nov['fecha_inicio_lma'] = str(d_from) if d_from else ''
                nov['fecha_fin_lma'] = str(d_to) if d_to else ''
            elif 'SLN' in code or 'NO REMUN' in name:
                nov['sln'] = 'X'
                nov['fecha_inicio_sln'] = str(d_from) if d_from else ''
                nov['fecha_fin_sln'] = str(d_to) if d_to else ''
            elif 'VAC' in code or 'VACACION' in name or 'LR' in code:
                nov['vac_lr'] = 'X'
                nov['fecha_inicio_vac_lr'] = str(d_from) if d_from else ''
                nov['fecha_fin_vac_lr'] = str(d_to) if d_to else ''

        # Aporte voluntario pensión
        avp_line = payslip.line_ids.filtered(
            lambda l: l.code == 'CO_PENSION_VOL')
        if avp_line and abs(avp_line.total) > 0:
            nov['avp'] = 'X'

        return nov
