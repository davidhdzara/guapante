# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Asistente para generar el archivo plano PILA.

Permite seleccionar el período de cotización, recopila los datos
de las nóminas confirmadas del período y genera el archivo TXT
con formato de planilla PILA para carga en el operador de información.
"""

import base64
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..services import pila_generator
from ..services import dian_utils


class L10nCoHrPilaWizard(models.TransientModel):
    """Asistente para generar el archivo plano PILA.

    Genera un archivo TXT con separador pipe (|) compatible con
    los operadores de información PILA (SuAporte, SOI, Mi Planilla).
    """

    _name = 'l10n.co.hr.pila.wizard'
    _description = 'Asistente para Generar Archivo Plano PILA'

    # ──────────────────────────────────────────────────────────────────
    # Campos
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
            ('E', 'E - Empleados'),
            ('Y', 'Y - Independientes'),
            ('A', 'A - Cotizantes con novedad de ingreso'),
            ('I', 'I - Independientes'),
            ('S', 'S - Servicio doméstico'),
            ('N', 'N - Corrección'),
        ],
        string='Tipo Planilla',
        required=True,
        default='E',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )

    # Resultado
    file_data = fields.Binary(
        string='Archivo PILA',
        readonly=True,
    )
    file_name = fields.Char(
        string='Nombre Archivo',
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('done', 'Generado'),
        ],
        default='draft',
    )

    # ──────────────────────────────────────────────────────────────────
    # Acción principal
    # ──────────────────────────────────────────────────────────────────
    def action_generate_pila(self):
        """Genera el archivo plano PILA para el período seleccionado.

        Flujo:
        1. Busca nóminas confirmadas del período.
        2. Recopila datos del aportante (empresa).
        3. Recopila datos de cada cotizante (empleado + nómina).
        4. Genera el archivo TXT con pila_generator.
        5. Almacena el resultado como attachment descargable.

        Returns:
            dict: Acción de ventana que recarga el wizard con el
            archivo generado listo para descargar.

        Raises:
            UserError: Si no hay nóminas confirmadas en el período
            o faltan datos de configuración.
        """
        self.ensure_one()

        company = self.company_id
        year = int(self.year)
        month = int(self.month)

        # ── Buscar nóminas del período ──
        date_from = date(year, month, 1)
        if month == 12:
            date_to = date(year + 1, 1, 1)
        else:
            date_to = date(year, month + 1, 1)

        payslips = self.env['hr.payslip'].search([
            ('company_id', '=', company.id),
            ('state', '=', 'done'),
            ('date_from', '>=', date_from),
            ('date_from', '<', date_to),
        ])

        if not payslips:
            raise UserError(_(
                'No se encontraron nóminas confirmadas para el período '
                '%s/%s en la compañía "%s".',
                self.month, self.year, company.name,
            ))

        # ── Datos del aportante (Tipo 1) ──
        periodo_str = '%s-%s' % (self.year, self.month)
        aportante = self._build_aportante_data(company, payslips, periodo_str)

        # ── Datos de cotizantes (Tipo 2) ──
        cotizantes = []
        seq = 1
        for payslip in payslips:
            cotizante = self._build_cotizante_data(payslip, seq)
            cotizantes.append(cotizante)
            seq += 1

        # ── Generar archivo ──
        file_content = pila_generator.generate_pila_file(
            aportante, cotizantes,
        )

        # ── Almacenar resultado ──
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
            'state': 'done',
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ──────────────────────────────────────────────────────────────────
    # Builders de datos
    # ──────────────────────────────────────────────────────────────────
    def _build_aportante_data(self, company, payslips, periodo_str):
        """Construye el diccionario de datos del aportante (Tipo 1).

        Args:
            company: res.company recordset.
            payslips: hr.payslip recordset (nóminas del período).
            periodo_str: Período como 'YYYY-MM'.

        Returns:
            dict con los 22 campos del registro Tipo 1.
        """
        vat = dian_utils.clean_nit(company.vat, strip_dv=False)
        nit_clean = dian_utils.clean_nit(company.vat, strip_dv=True)
        dv = dian_utils.compute_dv(nit_clean) if nit_clean else '0'

        # Tipo doc: NI si es empresa, CC si persona natural
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
            'tipo_registro': '1',
            'modalidad': '1',
            'secuencia': '1',
            'razon_social': company.name or '',
            'tipo_documento': tipo_doc,
            'numero_documento': nit_clean,
            'digito_verificacion': dv,
            'tipo_planilla': self.tipo_planilla,
            'num_planilla_asociada': '',
            'fecha_pago_asociada': '',
            'forma_presentacion': company.l10n_co_pila_forma_presentacion
            or 'U',
            'codigo_sucursal': company.l10n_co_pila_codigo_sucursal or '',
            'nombre_sucursal': company.l10n_co_pila_nombre_sucursal or '',
            'codigo_arl': company.l10n_co_pila_arl_code or '',
            'periodo_pago_otros': periodo_str,
            'periodo_pago_salud': periodo_str,
            'numero_planilla': '',
            'fecha_pago': '',
            'total_cotizantes': len(payslips),
            'valor_total_nomina': total_nomina,
            'tipo_aportante': company.l10n_co_pila_tipo_aportante or '1',
            'codigo_operador': company.l10n_co_pila_operador_code or '',
        }

    def _build_cotizante_data(self, payslip, seq):
        """Construye el diccionario de datos de un cotizante (Tipo 2).

        Args:
            payslip: hr.payslip recordset (una nómina).
            seq: int, número de secuencia.

        Returns:
            dict con los 98 campos del registro Tipo 2.
        """
        employee = payslip.employee_id
        contract = payslip.contract_id

        # Nombre
        name_parts = dian_utils.split_name(employee.name or '')

        # Tipo documento
        doc_type_code = dian_utils.get_doc_type_code(
            getattr(employee, 'l10n_co_document_type', None)
            or 'id_card'
        )
        # Mapear código numérico DIAN a código PILA (CC, CE, etc.)
        PILA_DOC_MAP = {
            '13': 'CC', '31': 'NI', '22': 'CE', '41': 'PA',
            '42': 'CD', '11': 'RC', '91': 'CC',
        }
        tipo_doc_pila = PILA_DOC_MAP.get(doc_type_code, 'CC')

        # Municipio y departamento
        dept_code = ''
        city_code = ''
        if hasattr(employee, 'address_home_id') and employee.address_home_id:
            partner = employee.address_home_id
            dept_code = dian_utils.get_department_code(
                partner.state_id) if partner.state_id else ''
            city_code = dian_utils.get_city_code(
                getattr(partner, 'city_id', None))

        # Líneas de nómina — obtener valores por código
        def get_line(code):
            line = payslip.line_ids.filtered(lambda l: l.code == code)
            return abs(line.total) if line else 0.0

        RuleParameter = self.env['hr.rule.parameter']

        def _p(code):
            return RuleParameter._get_parameter_from_code(
                code, payslip.date_from)

        salario = contract.wage or 0
        integral = bool(
            getattr(contract, 'l10n_co_ne_integral_salary', False))

        # IBC
        ibc_sal = get_line('CO_BRUTO') or salario
        if integral:
            ibc_sal = salario * _p('l10n_co_factor_integral_salary')

        # Días trabajados
        dias = _p('l10n_co_dias_mes_comercial')  # Default mensual
        worked = payslip.worked_days_line_ids.filtered(
            lambda w: w.code == 'WORK100')
        if worked:
            dias = int(worked.number_of_days)

        # Aportes
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
        tarifa_arl = _p('l10n_co_pct_arl_default') / 100  # Default riesgo I
        tarifa_ccf = _p('l10n_co_pct_ccf') / 100
        tarifa_sena = _p('l10n_co_pct_sena') / 100
        tarifa_icbf = _p('l10n_co_pct_icbf') / 100

        # Novedades (detectar de hr.leave del período)
        novedades = self._detect_novedades(payslip)

        # Exonerado (Art. 114-1 ET) -- mismo criterio centralizado que usan
        # las reglas salariales CO_SENA_CIA/CO_ICBF_CIA/CO_SALUD_CIA, para
        # que PILA y nómina no puedan divergir para el mismo empleado.
        exonerado = 'S' if self.company_id._is_exonerado_parafiscales(
            ibc_sal, payslip.date_from) else 'N'

        return {
            'tipo_registro': '2',
            'secuencia': str(seq).zfill(5),
            'tipo_documento': tipo_doc_pila,
            'numero_documento': employee.identification_id or '',
            'tipo_cotizante': getattr(
                contract, 'l10n_co_pila_tipo_cotizante', '01') or '01',
            'subtipo_cotizante': getattr(
                contract, 'l10n_co_pila_subtipo_cotizante', '00') or '00',
            'extranjero': 'X' if getattr(
                employee, 'l10n_co_ne_foreigner_no_pension', False
            ) else '',
            'colombiano_exterior': 'X' if getattr(
                employee, 'l10n_co_pila_colombiano_exterior', False
            ) else '',
            'departamento': dept_code,
            'municipio': city_code,
            'primer_apellido': name_parts['primer_apellido'],
            'segundo_apellido': name_parts['segundo_apellido'],
            'primer_nombre': name_parts['primer_nombre'],
            'segundo_nombre': name_parts['otros_nombres'],
            # Novedades
            **novedades,
            # Administradoras
            'afp': getattr(employee, 'l10n_co_pila_afp_code', '') or '',
            'afp_traslado': getattr(
                employee, 'l10n_co_pila_afp_traslado', '') or '',
            'eps': getattr(employee, 'l10n_co_pila_eps_code', '') or '',
            'eps_traslado': getattr(
                employee, 'l10n_co_pila_eps_traslado', '') or '',
            'ccf': getattr(employee, 'l10n_co_pila_ccf_code', '') or '',
            # Días
            'dias_afp': dias,
            'dias_eps': dias,
            'dias_arl': dias,
            'dias_ccf': dias,
            # Salario
            'salario_basico': salario,
            'tipo_salario': 'X' if integral else '',
            # IBC
            'ibc_afp': ibc_sal,
            'ibc_eps': ibc_sal,
            'ibc_arl': ibc_sal,
            'ibc_ccf': ibc_sal,
            # Pensión
            'tarifa_afp': tarifa_afp,
            'cotizacion_afp': round(ibc_sal * tarifa_afp),
            'avp_afiliado': get_line('CO_PENSION_VOL'),
            'avp_aportante': 0,
            'total_afp': round(ibc_sal * tarifa_afp)
            + round(fsp) + get_line('CO_PENSION_VOL'),
            'aporte_fsp': round(fsp),
            'aporte_fsps': 0,
            'valor_no_retenido': 0,
            # Salud
            'tarifa_eps': tarifa_eps,
            'cotizacion_eps': round(ibc_sal * tarifa_eps),
            'valor_upc': 0,
            'numero_ige': '',
            'valor_ige': 0,
            'numero_lma': '',
            'valor_lma': 0,
            # ARL
            'tarifa_arl': tarifa_arl,
            'centro_trabajo': getattr(
                contract, 'l10n_co_pila_centro_trabajo', '') or '',
            'cotizacion_arl': round(arl) if arl else round(
                ibc_sal * tarifa_arl),
            # Parafiscales
            'tarifa_ccf': tarifa_ccf,
            'aporte_ccf': round(ccf) if ccf else round(
                ibc_sal * tarifa_ccf),
            'tarifa_sena': tarifa_sena,
            'aporte_sena': round(sena) if sena else round(
                ibc_sal * tarifa_sena),
            'tarifa_icbf': tarifa_icbf,
            'aporte_icbf': round(icbf) if icbf else round(
                ibc_sal * tarifa_icbf),
            'tarifa_esap': 0,
            'aporte_esap': 0,
            'tarifa_men': 0,
            'aporte_men': 0,
            # UPC
            'tipo_documento_upc': '',
            'documento_upc': '',
            'exonerado': exonerado,
            # ARL details
            'arl': getattr(
                self.company_id, 'l10n_co_pila_arl_code', '') or '',
            'clase_riesgo': getattr(
                contract, 'l10n_co_pila_clase_riesgo', '1') or '1',
            'tarifa_especial_afp': getattr(
                contract, 'l10n_co_pila_tarifa_especial_afp', '') or '',
            # Final
            'ibc_otros_parafiscales': ibc_sal,
            'numero_horas_laboradas': dias * 8,
            'fecha_radicacion_exterior': '',
            'actividad_economica_arl': getattr(
                contract, 'l10n_co_pila_actividad_economica', '') or '',
        }

    def _detect_novedades(self, payslip):
        """Detecta novedades del período desde hr.leave y contrato.

        Args:
            payslip: hr.payslip recordset.

        Returns:
            dict con las claves de novedades para el registro Tipo 2.
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

        # Buscar ausencias del empleado en el período
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', payslip.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', payslip.date_to),
            ('date_to', '>=', payslip.date_from),
        ])

        for leave in leaves:
            leave_type = leave.holiday_status_id
            # Mapear por código o nombre del tipo de ausencia
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

        # AVP
        avp_line = payslip.line_ids.filtered(
            lambda l: l.code == 'CO_PENSION_VOL')
        if avp_line and abs(avp_line.total) > 0:
            nov['avp'] = 'X'

        return nov
