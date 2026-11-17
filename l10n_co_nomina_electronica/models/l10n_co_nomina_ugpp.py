# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Modelo para generación de reportes UGPP – Storm User.

La UGPP (Unidad de Gestión Pensional y Parafiscales) requiere que las
empresas presenten información periódica sobre sus aportes a seguridad
social. Este modelo genera el archivo Excel con 3 hojas que alimenta
el aplicativo Storm User:

1. **nomina-aportante**: Información general del aportante (empresa).
2. **nomina-conceptos de pago**: Mapeo de reglas salariales a conceptos
   de pago UGPP con sus cuentas contables.
3. **nomina**: Detalle consolidado por empleado de los valores de nómina
   del período, con desglose de IBC y aportes.

Referencia: Manual Storm User – UGPP.
"""

import base64
import io
import logging
import re
import zipfile

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round

from ..services import dian_utils

_logger = logging.getLogger(__name__)

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
except ImportError:
    openpyxl = None
    _logger.warning(
        'La librería openpyxl no está instalada. No se podrán generar '
        'los reportes UGPP en formato Excel.'
    )

# ──────────────────────────────────────────────────────────────────────────
# Constantes UGPP
# ──────────────────────────────────────────────────────────────────────────
# SMMLV – valor de respaldo si no está configurado en la empresa.


# Marco del libro Storm User: copia de la plantilla oficial ``Anexo_1.xlsx`` de la UGPP (Guía V-20.1 §1.3: no se
# cambia el nombre ni la estructura del archivo). Por hoja: nombre, formulario (preámbulo C2), su descripción (D2) y
# el título de la fila 8. Los nombres de hoja son los de la plantilla (la 2.ª, truncada a 31 caracteres por Excel).
_UGPP_HOJAS = {
    'aportante': ('Formulario Nómina - Aportante', 7001, 'Formulario Nómina - Aportante',
                  '0 Formulario Nómina - Aportante'),
    'conceptos': ('Formulario Nómina - Concepto...', 7003, 'Formulario Nómina - Concepto Pago Aportante ',
                  '0 Formulario Nómina - Concepto Pago Aportante'),
    'nomina': ('Formulario Nómina', 7002, 'Formulario Nómina', '0 Formulario Nómina'),
}
# Código de columna (fila 9) de la hoja ``nomina`` para las 35 columnas fijas (las 3 últimas son las fechas de inicio de
# permiso, suspensión y huelga). Observaciones = 184; el concepto N de la plantilla = 276 + 4 × (N - 1).
_UGPP_COD_NOMINA = (8, 12, 16, 24, 28, 32, 36, 40, 52, 56, 60, 64, 68, 72, 76, 80, 84, 88, 92, 96, 100, 104, 108,
                    112, 116, 120, 124, 128, 132, 136, 140, 144, 148, 152, 156)
_UGPP_COD_OBSERVACIONES = 184
_UGPP_COD_CONCEPTO_1 = 276
_UGPP_PRIMERA_FILA = 11


# Listas de la Guía UGPP V-20.1 para el formulario del aportante (7001). Clave = valor del campo de la compañía.
_UGPP_NATURALEZA = {
    'publica': 1, 'privada': 2, 'mixta': 3, 'organismo_multilateral': 4, 'publica_extranjera': 5,
}
_UGPP_TIPO_APORTANTE = {
    'empleador': 1, 'entidad_publica_especial': 3, 'agremiacion': 4, 'cooperativa': 5, 'mision_diplomatica': 6,
    'hogares_bienestar': 7, 'pagador_concejales': 8, 'pagador_sindical': 9, 'pagador_reincorporacion': 10,
    'pagador_magisterio': 11, 'pagador_humanitaria': 12,
}
# Tipo de documento del aportante (Guía p. 14): código DIAN del tipo de identificación del contacto de la compañía →
# código UGPP. Los códigos CD y SC no tienen equivalente en el catálogo DIAN del módulo: no se mapean por conjetura.
_UGPP_DOC_APORTANTE = {'31': 'NI', '13': 'CC', '22': 'CE', '12': 'TI', '41': 'PA', '47': 'PE'}

# Tipo de pago (formulario 7003, columna 19) y clasificación de pagos no salariales (columna 20): texto EXACTO de las
# listas de la plantilla ``Anexo_1.xlsx`` (número + nombre). Los tipos 12 a 15 (ingreso bruto, independiente, contratista,
# contratista ARL) son de independientes y no se cargan.
_UGPP_TIPO_PAGO = {
    'tp_salarial': '1 TP SALARIAL',
    'tp_no_salarial': '2 TP NO SALARIAL',
    'tp_compensacion_ord': '3 TP COMPENSACIÓN ORDINARIA',
    'tp_compensacion_ext': '4 TP COMPENSACIÓN EXTRAORDINARIA',
    'tp_no_compensacion': '5 TP NO COMPENSACIÓN',
    'tp_descanso_anual': '6 TP DESCANSO ANUAL',
    'tp_incapacidad': '7 TP INCAPACIDAD',
    'tp_vacaciones': '8 TP VACACIONES',
    'tp_vacaciones_terminacion': '9 TP VACACIONES TERMINACION DE CONTRATO',
    'tp_licencia_remunerada': '10 TP LICENCIA REMUNERADA',
    'tp_estudiantes': '11 TP A ESTUDIANTES O APRENDICES',
    'tp_licencia_mat_pat': '16 TP LICENCIA MAT O PAT',
    'tp_prestaciones': '17 TP PRESTACIONES',
}
_UGPP_CLASE_NO_SALARIAL = {
    'mera_liberalidad': '1 Mera liberalidad',
    'pacto_colectivo': '2 Pacto colectivo',
    'contrato': '3 Contrato',
    'otrosi': '4 Otrosí',
}
# Guía §1.3: "No utilice caracteres especiales (¡!"#$%&) en ninguno de los campos".
_UGPP_CARACTERES_PROHIBIDOS = dict.fromkeys(map(ord, '¡!"”“#$%&'), None)
# Tipos de pago cuyo valor se reporta en el mes del PAGO (Guía V-20.1 §1.3, p. 13).
_UGPP_TIPOS_VACACIONES = ('tp_vacaciones', 'tp_vacaciones_terminacion')
_UGPP_MAX_CUENTAS = 200      # largo máximo del campo "cuenta contable" en la plantilla


# Tipo de documento del trabajador (Guía V-20.1 p. 14; formulario 7002, columna 36): código DIAN del tipo de identificación
# de Contactos → código UGPP. Sin equivalente (registro civil, tarjeta de extranjería, DIE, PPT, NUIP, NIT) no se asume
# otro: error que nombra al empleado (PPT y DIE están como pregunta abierta para la UGPP, doc 48).
_UGPP_DOC_TRABAJADOR = {'13': 'CC', '22': 'CE', '12': 'TI', '41': 'PA', '47': 'PE'}
# Tipo y subtipo de cotizante: tabla PILA del contrato → lista UGPP (Guía p. 19-21). El 21 de PILA (Estudiante, Ley 789
# de 2002) es el 20 de la UGPP; el 21 de la UGPP es otro (estudiantes de postgrado en salud).
_UGPP_TIPO_COTIZANTE = {'01': 1, '02': 2, '03': 3, '04': 4, '12': 12, '19': 19, '21': 20, '22': 22, '30': 30,
                        '31': 31, '51': 51}
_UGPP_SUBTIPO_COTIZANTE = {'00': 0, '01': 1, '02': 2}
# Declaración voluntaria (no es un requisito de la Guía, que pide informar solo si se liquida sobre 365 días; David,
# 2026-11-14). Va en "Observaciones aportante" (máx. 800 caracteres en la plantilla).
_UGPP_NOTA_360 = ('Las prestaciones sociales (prima, cesantías e intereses) se liquidan sobre un año de 360 días, '
                  'conforme a los artículos 249 y 306 del Código Sustantivo del Trabajo.')
# Las columnas de concepto de la plantilla son 133 (CONCEPTO 1 a 133).
_UGPP_MAX_CONCEPTOS = 133
# Documentos adicionales (Guía V-20.1 §2.3, Res. 858 art. 3): PDF, nombre de archivo de máx. 50 caracteres y el conjunto
# de máx. 100 MB (un archivo por enlace de Storm Web).
_UGPP_MAX_NOMBRE_ARCHIVO = 50
_UGPP_MAX_BYTES_SOPORTES = 100 * 1024 * 1024
# Oficio de respuesta (9006): párrafo sobre los ajustes. BORRADOR a validar por el representante legal / David (la Guía
# pide "explicar cómo se realizan los ajustes" y no trae modelo).
_UGPP_TEXTO_AJUSTES = ('Los ajustes de nómina se registran en el mes en que se conocen, mediante recibos de ajuste '
                       'o notas de ajuste, y el formato de pagos informa el valor mensual por concepto y trabajador.')


class L10nCoNominaUgpp(models.Model):
    """Generador de reportes UGPP para Storm User."""

    _name = 'l10n_co_nomina.ugpp'
    _check_company_auto = True
    _description = 'Reporte UGPP – Storm User'
    _order = 'year desc, month desc'

    # ──────────────────────────────────────────────────────────────────
    # Campos principales
    # ──────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
        help='Nombre descriptivo del reporte UGPP.',
    )
    year = fields.Integer(
        string='Año',
        required=True,
        default=lambda self: fields.Date.today().year,
        help='Año del período a reportar.',
    )
    month = fields.Selection(
        selection=[
            ('1', 'Enero'),
            ('2', 'Febrero'),
            ('3', 'Marzo'),
            ('4', 'Abril'),
            ('5', 'Mayo'),
            ('6', 'Junio'),
            ('7', 'Julio'),
            ('8', 'Agosto'),
            ('9', 'Septiembre'),
            ('10', 'Octubre'),
            ('11', 'Noviembre'),
            ('12', 'Diciembre'),
        ],
        string='Mes',
        required=True,
        help='Mes del período a reportar.',
    )
    date_from = fields.Date(
        string='Fecha Inicio',
        required=True,
        help='Fecha de inicio del período de reporte.',
    )
    date_to = fields.Date(
        string='Fecha Fin',
        required=True,
        help='Fecha de fin del período de reporte.',
    )
    soportes_file = fields.Binary(string='Soportes por trabajador (ZIP)', attachment=True)
    soportes_filename = fields.Char(string='Nombre del ZIP de soportes')
    soportes_resumen = fields.Text(string='Soportes: qué hay y qué falta', readonly=True)
    info_nomina_file = fields.Binary(string='Información del módulo de nómina (2.3.7)', attachment=True)
    info_nomina_filename = fields.Char(string='Nombre del archivo 2.3.7')
    requerimiento_radicado = fields.Char(
        string='Radicado del requerimiento',
        help='Número de radicado del requerimiento de información de la UGPP que se responde. Solo para el oficio de '
             'respuesta (9006).')
    requerimiento_fecha = fields.Date(
        string='Fecha del requerimiento',
        help='Fecha del requerimiento de información de la UGPP. Solo para el oficio de respuesta (9006).')
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
        help='Empresa para la que se genera el reporte UGPP.',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('generated', 'Generado'),
        ],
        string='Estado',
        default='draft',
        required=True,
        help='Estado del reporte. Cambia a "Generado" cuando se crea '
             'el archivo Excel exitosamente.',
    )
    excel_file = fields.Binary(
        string='Archivo Excel',
        readonly=True,
        help='Archivo Excel generado con las 3 hojas del reporte UGPP.',
    )
    excel_filename = fields.Char(
        string='Nombre Archivo Excel',
        readonly=True,
    )

    # ──────────────────────────────────────────────────────────────────
    # SQL Constraints
    # ──────────────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'unique_period_company',
            'UNIQUE(year, month, company_id)',
            'Ya existe un reporte UGPP para este período y empresa.',
        ),
    ]

    # ──────────────────────────────────────────────────────────────────
    # Campos computados
    # ──────────────────────────────────────────────────────────────────
    @api.depends('year', 'month', 'company_id')
    def _compute_name(self):
        """Genera nombre descriptivo: 'UGPP - Empresa - Mes Año'."""
        month_names = dict(self._fields['month'].selection)
        for record in self:
            company_name = record.company_id.name or ''
            month_name = month_names.get(record.month, '')
            record.name = 'UGPP - %s - %s %s' % (
                company_name, month_name, record.year or ''
            )

    # ──────────────────────────────────────────────────────────────────
    # Validaciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        """Valida que la fecha inicio sea anterior a la fecha fin."""
        for record in self:
            if record.date_from and record.date_to:
                if record.date_from > record.date_to:
                    raise UserError(_(
                        'La fecha de inicio debe ser anterior o igual a '
                        'la fecha de fin.'
                    ))

    # ══════════════════════════════════════════════════════════════════
    # ACCIÓN PRINCIPAL: Generar reporte Excel
    # ══════════════════════════════════════════════════════════════════

    def action_generate_report(self):
        """
        Genera el archivo Excel UGPP con 3 hojas para Storm User.

        Flujo:
        1. Busca las nóminas confirmadas del período.
        2. Genera la hoja 'Formulario Nómina - Aportante' con datos de la empresa.
        3. Genera la hoja 'Formulario Nómina - Concepto...' con el mapeo de
           reglas salariales a conceptos UGPP.
        4. Genera la hoja 'Formulario Nómina' con el detalle consolidado por
           empleado.
        5. Guarda el archivo Excel en el campo binario.
        """
        self.ensure_one()

        if not openpyxl:
            raise UserError(_(
                'La librería openpyxl no está instalada. Ejecute: '
                'pip install openpyxl'
            ))

        # Recibos del periodo (por date_to) y los de otros meses con vacaciones pagadas en él
        payslips = self._ugpp_recibos()

        if not payslips:
            raise UserError(_(
                'No se encontraron nóminas confirmadas para el período '
                '%s - %s en la empresa %s.',
                self.date_from, self.date_to, self.company_id.name,
            ))

        # Crear workbook
        wb = openpyxl.Workbook()

        # Estilos
        header_font = Font(bold=True, color='FFFFFF', size=11)
        header_fill = PatternFill(
            start_color='4472C4', end_color='4472C4', fill_type='solid'
        )
        header_alignment = Alignment(
            horizontal='center', vertical='center', wrap_text=True
        )
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin'),
        )

        # ── Hoja 1: nomina-aportante ─────────────────────────────────
        ws_aportante = wb.active
        ws_aportante.title = _UGPP_HOJAS['aportante'][0]
        self._generate_sheet_aportante(
            ws_aportante, header_font, header_fill,
            header_alignment, thin_border,
        )

        # ── Hoja 2: nomina-conceptos de pago ─────────────────────────
        ws_conceptos = wb.create_sheet(_UGPP_HOJAS['conceptos'][0])
        self._generate_sheet_conceptos(
            ws_conceptos, payslips, header_font, header_fill,
            header_alignment, thin_border,
        )

        # ── Hoja 3: nomina ───────────────────────────────────────────
        ws_nomina = wb.create_sheet(_UGPP_HOJAS['nomina'][0])
        self._generate_sheet_nomina(
            ws_nomina, payslips, header_font, header_fill,
            header_alignment, thin_border,
        )

        # Guardar en memoria
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # Almacenar archivo
        month_names = dict(self._fields['month'].selection)
        filename = 'UGPP_%s_%s_%s.xlsx' % (
            (self.company_id.vat or 'NIT').replace('-', ''),
            month_names.get(self.month, self.month),
            self.year,
        )

        self.write({
            'excel_file': base64.b64encode(output.read()),
            'excel_filename': filename,
            'state': 'generated',
        })

        _logger.info(
            'Reporte UGPP generado: %s (%d nóminas procesadas)',
            filename, len(payslips),
        )

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/excel_file/%s?download=true' % (
                self._name.replace('.', '_'), self.id, filename,
            ),
            'target': 'new',
        }

    # ══════════════════════════════════════════════════════════════════
    # GENERACIÓN DE HOJAS INDIVIDUALES
    # ══════════════════════════════════════════════════════════════════

    def _ugpp_marco(self, ws, clave, columnas, header_font, header_fill, header_alignment, thin_border):
        """Escribe el marco de la plantilla Storm User (``Anexo_1.xlsx``) en la hoja ``ws`` y devuelve la primera fila
        de datos.

        Filas 1-6: preámbulo (tipo de modalidad 7000, formulario, moneda 1, NIT del aportante SIN dígito de
        verificación, fecha de corte = último día del periodo, periodicidad 0 Ocasional); fila 8: título; fila 9:
        código de cada columna (``None`` si la columna aún no existe en el formato); fila 10: encabezados; datos
        desde la fila 11 con el número de fila en A y ``FILA_n`` en B, y los valores desde la columna C.
        ``columnas``: lista de ``(código, encabezado)``. Nivel de verificación: copia de la estructura leída de la
        plantilla; que Storm User acepte un libro generado se prueba solo con Storm real (piloto)."""
        self.ensure_one()
        _nombre, formulario, descripcion, titulo = _UGPP_HOJAS[clave]
        nit = dian_utils.clean_nit(self.company_id.vat)
        preambulo = (
            ('Tipo Modalidad', 7000, 'Informe Nomina - UGPP'),
            ('Formulario', formulario, descripcion),
            ('Moneda Informe', 1, None),
            ('Entidad', int(nit) if nit.isdigit() else nit, None),
            ('Fecha', self.date_to, None),
            ('Periodicidad', 0, 'Ocasional'),
        )
        for fila, (etiqueta, valor, detalle) in enumerate(preambulo, 1):
            ws.cell(row=fila, column=2, value=etiqueta)
            celda = ws.cell(row=fila, column=3, value=valor)
            if fila == 5:
                celda.number_format = 'dd/mm/yyyy'
            if detalle:
                ws.cell(row=fila, column=4, value=detalle)
        ws.cell(row=8, column=1, value='[1]')
        ws.cell(row=8, column=2, value=titulo)
        for col_num, (codigo, encabezado) in enumerate(columnas, 3):
            if codigo is not None:
                ws.cell(row=9, column=col_num, value=codigo)
            cell = ws.cell(row=10, column=col_num, value=encabezado)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        return _UGPP_PRIMERA_FILA

    def _ugpp_escribir_fila(self, ws, fila, valores, thin_border):
        """Una fila de datos del marco: número de fila en A, ``FILA_n`` en B y los valores desde la columna C."""
        n = fila - _UGPP_PRIMERA_FILA + 1
        ws.cell(row=fila, column=1, value=n)
        ws.cell(row=fila, column=2, value='FILA_%d' % n)
        for col_num, valor in enumerate(valores, 3):
            cell = ws.cell(row=fila, column=col_num, value=valor)
            cell.border = thin_border
            if isinstance(valor, float):
                cell.number_format = '#,##0.00'

    def _ugpp_datos_aportante(self):
        """Los 6 valores del aportante (formulario 7001) a partir de la compañía. Todos son obligatorios para la
        UGPP: lo que falte se pide con un error que nombra la compañía y dónde completarlo (sin valores por
        defecto)."""
        self.ensure_one()
        company = self.company_id
        faltan = []
        tipo_id = company.partner_id.l10n_latam_identification_type_id
        codigo_dian = tipo_id.l10n_co_ne_dian_document_code or ''
        tipo_doc = _UGPP_DOC_APORTANTE.get(codigo_dian)
        if not tipo_doc:
            faltan.append(_('un tipo de identificación del contacto de la compañía que tenga equivalente en la UGPP '
                            '(NIT, cédula, extranjería, tarjeta de identidad, pasaporte o PEP)'))
        numero = dian_utils.clean_nit(company.vat, strip_dv=(tipo_doc == 'NI'))
        if not numero:
            faltan.append(_('el número de identificación (NIT) de la compañía'))
        if company.l10n_co_ugpp_legal_nature not in _UGPP_NATURALEZA:
            faltan.append(_('la naturaleza jurídica'))
        if company.l10n_co_ugpp_contributor_type not in _UGPP_TIPO_APORTANTE:
            faltan.append(_('el tipo de aportante'))
        if faltan:
            raise UserError(_(
                'Para el reporte UGPP de la compañía "%(compania)s" falta: %(faltan)s. Complételo en Nómina > '
                'Configuración > Ajustes (bloque UGPP) o en el contacto de la compañía.',
                compania=company.display_name, faltan='; '.join(faltan)))
        return [
            tipo_doc,
            int(numero) if numero.isdigit() and tipo_doc in ('NI', 'CC', 'CE') else numero,
            company.name or '',
            _UGPP_NATURALEZA[company.l10n_co_ugpp_legal_nature],
            _UGPP_TIPO_APORTANTE[company.l10n_co_ugpp_contributor_type],
            self._ugpp_autoretencion(),
        ]

    def _ugpp_autoretencion(self):
        """'SI' o 'NO' del campo 28 del aportante (Guía p. 15: 'exonerado del pago de aportes parafiscales según el
        artículo 114-1 del ET'). Misma fuente que la exoneración de SENA/ICBF de la nómina y la PILA."""
        self.ensure_one()
        return 'SI' if self.company_id.l10n_co_ne_exoneration_1607 else 'NO'

    def _generate_sheet_aportante(
        self, ws, header_font, header_fill, header_alignment, thin_border
    ):
        """
        Genera la hoja del aportante (formulario 7001) con información de la empresa.

        Columnas:
        - Tipo Documento, Número Documento, Razón Social
        - Naturaleza Jurídica, Tipo Aportante
        - Autorretención Especial (exoneración del art. 114-1 ET)
        """
        # Los 6 campos del formulario 7001 (Guía V-20.1 §1.3.1) con el código de columna de la plantilla.
        headers = [
            (4, 'TIPO DOCUMENTO APORTANTE'),
            (8, 'NÚMERO DOCUMENTO APORTANTE'),
            (12, 'RAZÓN SOCIAL'),
            (16, 'NATURALEZA JURÍDICA'),
            (20, 'TIPO DE APORTANTE'),
            (28, 'AUTORRETENCIÓN ESPECIAL'),
        ]
        fila_datos = self._ugpp_marco(
            ws, 'aportante', headers, header_font, header_fill, header_alignment, thin_border)
        row_data = self._ugpp_datos_aportante()

        self._ugpp_escribir_fila(ws, fila_datos, row_data, thin_border)

        # Ajustar anchos
        for col in ws.columns:
            max_length = max(
                len(str(cell.value or '')) for cell in col
            )
            ws.column_dimensions[col[0].column_letter].width = (
                min(max_length + 2, 40)
            )

    def _ugpp_cuentas_regla(self, rule):
        """Códigos de las cuentas contables de la regla (débito y crédito, sin repetir) para la compañía del reporte,
        separados por ';'. Misma fuente que el asiento de nómina: no hay un campo aparte."""
        rule = rule.with_company(self.company_id)
        codigos = []
        for cuenta in (rule.account_debit, rule.account_credit):
            codigo = cuenta.with_company(self.company_id).code
            if codigo and codigo not in codigos:
                codigos.append(codigo)
        return ';'.join(codigos)

    def _ugpp_filas_conceptos(self, salary_rules):
        """Filas ``[concepto, nombre, cuentas, tipo de pago, clasificación]`` del formulario 7003. Todos los campos son
        obligatorios para la UGPP: las reglas a las que les falte algo se listan juntas en un solo error (sin valores
        por defecto)."""
        self.ensure_one()
        sin_cuenta, sin_clase, cuentas_largas = [], [], []
        filas = []
        for idx, rule in enumerate(salary_rules, 1):
            cuentas = self._ugpp_cuentas_regla(rule)
            if not cuentas:
                sin_cuenta.append(rule.display_name)
            elif len(cuentas) > _UGPP_MAX_CUENTAS:
                cuentas_largas.append(rule.display_name)
            clase = ''
            if rule.l10n_co_ugpp_payment_type == 'tp_no_salarial':
                clase = _UGPP_CLASE_NO_SALARIAL.get(rule.l10n_co_ugpp_non_salary_class, '')
                if not clase:
                    sin_clase.append(rule.display_name)
            filas.append([
                idx,
                (rule.name or '').translate(_UGPP_CARACTERES_PROHIBIDOS),
                cuentas,
                _UGPP_TIPO_PAGO[rule.l10n_co_ugpp_payment_type],
                clase,
            ])
        problemas = []
        if sin_cuenta:
            problemas.append(_('sin cuenta contable (débito o crédito) para la compañía "%(compania)s": %(reglas)s',
                               compania=self.company_id.display_name, reglas=', '.join(sin_cuenta)))
        if cuentas_largas:
            problemas.append(_('con las cuentas contables más largas de %(max)s caracteres: %(reglas)s',
                               max=_UGPP_MAX_CUENTAS, reglas=', '.join(cuentas_largas)))
        if sin_clase:
            problemas.append(_('TP NO Salarial sin clasificación: %s', ', '.join(sin_clase)))
        if problemas:
            raise UserError(_(
                'No se puede generar la hoja de conceptos del reporte UGPP. Reglas salariales con valor en el periodo %s. Corríjalo en '
                'Nómina > Configuración > Cuentas Contables por Regla y en la regla (Tipo de pago UGPP).',
                '; '.join(problemas)))
        return filas

    def _ugpp_soportes(self, payslips):
        """Por empleado del reporte, los PDF de soporte que YA existen (adjuntos del contrato, del empleado y de su
        contacto de trabajo, más los de las planillas PILA del mes) y lo que falta. Lo que falta NO es un error: es la
        lista de lo pendiente por conseguir. ``[{'empleado', 'adjuntos': [(tipo, ir.attachment)], 'faltan': [texto]}]``"""
        self.ensure_one()
        Adjunto = self.env['ir.attachment']
        resultado = []
        for empleado in payslips.employee_id.sorted('name'):
            contratos = payslips.filtered(lambda s: s.employee_id == empleado).contract_id | empleado.contract_ids
            fuentes = (('contrato', 'hr.contract', contratos.ids), ('empleado', 'hr.employee', empleado.ids),
                       ('contacto', 'res.partner', empleado.work_contact_id.ids))
            adjuntos = []
            for tipo, modelo, ids in fuentes:
                if ids:
                    for adjunto in Adjunto.search([('res_model', '=', modelo), ('res_id', 'in', ids),
                                                   ('mimetype', '=', 'application/pdf')], order='id'):
                        adjuntos.append((tipo, adjunto))
            faltan = []
            if not adjuntos:
                faltan.append(_('falta el contrato laboral: ningún PDF adjunto al contrato, al empleado ni a su contacto'))
            consolidados = self.env['l10n.co.ibc.mensual'].search([
                ('company_id', '=', self.company_id.id), ('employee_id', '=', empleado.id),
                ('period', '=', self.date_from)])
            planillas = consolidados.planilla_id
            if not planillas:
                faltan.append(_('sin planilla PILA registrada en el mes'))
            for planilla in planillas:
                for adjunto in Adjunto.search([('res_model', '=', 'l10n.co.pila.planilla'),
                                               ('res_id', '=', planilla.id), ('mimetype', '=', 'application/pdf')]):
                    adjuntos.append(('planilla', adjunto))
            resultado.append({'empleado': empleado, 'adjuntos': adjuntos, 'faltan': faltan})
        return resultado

    def _ugpp_nombre_soporte(self, empleado, tipo, indice):
        """Nombre de archivo del soporte: la identificación del trabajador + el tipo (máx. 50 caracteres, sin
        caracteres especiales)."""
        base = re.sub(r'[^A-Za-z0-9]', '', empleado.identification_id or '') or 'SIN_IDENTIFICACION'
        nombre = '%s_%s%s' % (base, tipo, '_%d' % indice if indice > 1 else '')
        return nombre[:_UGPP_MAX_NOMBRE_ARCHIVO - 4] + '.pdf'

    def action_generar_soportes(self):
        """ZIP con los PDF de soporte que existen, nombrados con la identificación del trabajador, y el resumen de lo
        que falta por empleado. Es una comodidad para subirlos de a uno a Storm Web (un archivo por enlace): el ZIP no
        se envía."""
        self.ensure_one()
        payslips = self._ugpp_recibos()
        if not payslips:
            raise UserError(_(
                'No se encontraron nóminas confirmadas para el período %s - %s en la empresa %s.',
                self.date_from, self.date_to, self.company_id.name))
        soportes = self._ugpp_soportes(payslips)
        salida = io.BytesIO()
        lineas = []
        total_bytes = 0
        with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in soportes:
                empleado = item['empleado']
                contador = {}
                for tipo, adjunto in item['adjuntos']:
                    contador[tipo] = contador.get(tipo, 0) + 1
                    zf.writestr(self._ugpp_nombre_soporte(empleado, tipo, contador[tipo]), adjunto.raw or b'')
                    total_bytes += adjunto.file_size or 0
                estado = '; '.join(item['faltan']) if item['faltan'] else _('completo')
                lineas.append('%s (%s): %d PDF; %s' % (
                    empleado.name, empleado.identification_id or _('sin identificación'), len(item['adjuntos']), estado))
        if total_bytes > _UGPP_MAX_BYTES_SOPORTES:
            lineas.append(_('AVISO: los soportes suman más de 100 MB (el límite de Storm Web); envíelos por partes.'))
        encabezado = _(
            'Que falten contratos no es un error del módulo: significa que no hay PDF adjuntos en Odoo (contrato, '
            'empleado o contacto). Adjúntelos y vuelva a generar. Soportes que existen y que se incluyen en el ZIP: '
            'solo PDF.')
        resumen = '\n'.join([encabezado, ''] + lineas)
        nombre = 'Soportes_UGPP_%s_%s_%s.zip' % (
            dian_utils.clean_nit(self.company_id.vat) or 'NIT', self.month, self.year)
        self.write({'soportes_file': base64.b64encode(salida.getvalue()), 'soportes_filename': nombre,
                    'soportes_resumen': resumen})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/soportes_file/%s?download=true' % (self._name, self.id, nombre),
            'target': 'new',
        }

    def _ugpp_filas_info_nomina(self, payslips):
        """Filas de la "Información módulo de nómina" (Res. 858 de 2021, art. 2.3.7, p. 4): cuenta contable asociada al
        concepto, nombre de la cuenta, código y nombre del concepto, documento y nombre del trabajador, año, mes y
        valor. Una fila por empleado y concepto con valor, del mismo agrupador de la hoja nómina (``_ugpp_valores``):
        mismo mes, mismas vacaciones por fecha de pago y mismo CONCEPTO N. La cuenta es la de DÉBITO de la regla (la
        norma no distingue cuenta de gasto o de pasivo: validar con Contabilidad/UGPP en el piloto); la de crédito solo
        si la regla no tiene débito. Sin cuenta: error que lista las reglas con valor."""
        self.ensure_one()
        reglas = self._get_ugpp_salary_rules(payslips)
        cuentas = {}
        sin_cuenta = []
        for regla in reglas:
            regla_cia = regla.with_company(self.company_id)
            cuenta = regla_cia.account_debit or regla_cia.account_credit
            if cuenta:
                cuentas[regla.id] = cuenta.with_company(self.company_id)
            else:
                sin_cuenta.append(regla.display_name)
        if sin_cuenta:
            raise UserError(_(
                'No se puede generar la información del módulo de nómina: reglas salariales con valor en el periodo '
                'sin cuenta contable (débito o crédito) para la compañía "%(compania)s": %(reglas)s. Corríjalo en '
                'Nómina > Configuración > Cuentas Contables por Regla.',
                compania=self.company_id.display_name, reglas=', '.join(sin_cuenta)))
        valores = self._ugpp_valores(payslips)
        filas = []
        for empleado in payslips.employee_id.sorted('name'):
            por_regla = valores.get(empleado.id, {})
            documento = (empleado.identification_id or '').strip()
            for numero, regla in enumerate(reglas, 1):
                valor = por_regla.get(regla.id, 0.0)
                if not valor:
                    continue
                cuenta = cuentas[regla.id]
                filas.append([
                    int(cuenta.code) if (cuenta.code or '').isdigit() else cuenta.code,
                    cuenta.name,
                    numero,
                    (regla.name or '').translate(_UGPP_CARACTERES_PROHIBIDOS),
                    int(documento) if documento.isdigit() else documento,
                    empleado.name,
                    self.year,
                    int(self.month),
                    self._ugpp_entero(valor, empleado, regla),
                ])
        return filas

    def action_generar_info_nomina(self):
        """Excel de una hoja con la información del módulo de nómina (art. 2.3.7), para los aportantes que no llevan en la
        contabilidad el detalle de los pagos por trabajador."""
        self.ensure_one()
        if not openpyxl:
            raise UserError(_('La librería openpyxl no está instalada. Ejecute: pip install openpyxl'))
        payslips = self._ugpp_recibos()
        if not payslips:
            raise UserError(_(
                'No se encontraron nóminas confirmadas para el período %s - %s en la empresa %s.',
                self.date_from, self.date_to, self.company_id.name))
        filas = self._ugpp_filas_info_nomina(payslips)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Informacion modulo de nomina'
        encabezados = ['Cuenta contable', 'Nombre de cuenta contable', 'Código del concepto de pago',
                       'Nombre del concepto de pago', 'Número de documento del trabajador',
                       'Nombre del trabajador', 'Año', 'Mes', 'Valor']
        ws.append(encabezados)
        for celda in ws[1]:
            celda.font = Font(bold=True)
        for fila in filas:
            ws.append(fila)
        salida = io.BytesIO()
        wb.save(salida)
        nombre = 'Informacion_modulo_nomina_%s_%s_%s.xlsx' % (
            dian_utils.clean_nit(self.company_id.vat) or 'NIT', self.month, self.year)
        self.write({'info_nomina_file': base64.b64encode(salida.getvalue()), 'info_nomina_filename': nombre})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/info_nomina_file/%s?download=true' % (self._name, self.id, nombre),
            'target': 'new',
        }

    def _ugpp_datos_oficio(self):
        """Datos del oficio de respuesta a la UGPP (código 9006, Guía V-20.1 §2.2). Todo sale de Contactos, de la
        compañía y del propio reporte; lo que falte se pide con un error que nombra la compañía (sin valores por
        defecto). El módulo NO firma ni radica: es un borrador para el representante legal."""
        self.ensure_one()
        company = self.company_id
        faltan = []
        partner = company.partner_id
        representante = company.l10n_co_ne_representante_legal_id
        if not representante:
            faltan.append(_('el representante legal (Ajustes > Nómina > UGPP)'))
        elif not representante.vat or not representante.l10n_latam_identification_type_id:
            faltan.append(_('el tipo y número de identificación del contacto "%s" (representante legal)',
                            representante.display_name))
        if not self.requerimiento_radicado or not self.requerimiento_fecha:
            faltan.append(_('el radicado y la fecha del requerimiento de la UGPP (en este reporte)'))
        if not (partner.email or partner.street):
            faltan.append(_('una dirección de notificaciones: correo o dirección en el contacto de la compañía'))
        if not partner.vat:
            faltan.append(_('el NIT de la compañía'))
        recibos = self._ugpp_recibos()
        if not recibos:
            faltan.append(_('recibos confirmados del periodo (nada que informar)'))
        if faltan:
            raise UserError(_(
                'Para el oficio de respuesta a la UGPP de la compañía "%(compania)s" falta: %(faltan)s.',
                compania=company.display_name, faltan='; '.join(faltan)))
        periodicidad = dict(self.env['hr.contract']._fields['schedule_pay'].selection)
        calendarios = sorted({periodicidad.get(c.schedule_pay or c.structure_type_id.default_schedule_pay, '')
                              for c in recibos.contract_id} - {''})
        meses = dict(self._fields['month'].selection)
        # Fechas de pago REALES de los recibos del reporte: la periodicidad nativa (``schedule_pay``) no puede expresar
        # "los días 5 y 20" ni "todos los viernes". Misma fuente de la fecha de pago del documento DIAN; un recibo sin
        # fecha de pago es un error que lo nombra (no se omite en silencio).
        fechas_pago = sorted({self._ugpp_fecha_pago(slip) for slip in recibos})
        return {
            'fechas_pago': [fecha.strftime('%d/%m/%Y') for fecha in fechas_pago],
            'nit': dian_utils.clean_nit(partner.vat, strip_dv=False),
            'direccion': ', '.join(filter(None, [partner.street, partner.city, partner.state_id.name])),
            'correo': partner.email or '',
            'representante': representante,
            'representante_documento': '%s %s' % (representante.l10n_latam_identification_type_id.name, representante.vat),
            'periodo': '%s de %s' % (meses.get(self.month, ''), self.year),
            'calendarios': calendarios,
            'texto_ajustes': _UGPP_TEXTO_AJUSTES,
            'nota_360': _UGPP_NOTA_360,
        }

    def action_imprimir_oficio(self):
        """Valida los datos y devuelve el PDF del oficio de respuesta (borrador)."""
        self.ensure_one()
        self._ugpp_datos_oficio()
        return self.env.ref('l10n_co_nomina_electronica.action_report_ugpp_oficio').report_action(self)

    def _ugpp_cotizante(self, employee, contract):
        """``(tipo, subtipo)`` de cotizante de la lista UGPP, desde los campos PILA del contrato (la misma fuente que
        la planilla PILA). Sin dato o sin equivalente: error que nombra al empleado (sin valores por defecto)."""
        tipo = _UGPP_TIPO_COTIZANTE.get(contract.l10n_co_pila_tipo_cotizante)
        subtipo = _UGPP_SUBTIPO_COTIZANTE.get(contract.l10n_co_pila_subtipo_cotizante)
        if tipo is None or subtipo is None:
            raise UserError(_(
                'El contrato de %(empleado)s no tiene tipo y subtipo de cotizante con equivalente en la UGPP. '
                'Complételos en el contrato (pestaña PILA).', empleado=employee.display_name))
        return tipo, subtipo

    def _ugpp_documento_trabajador(self, employee):
        """``(tipo UGPP, número)`` del documento del trabajador, del tipo de identificación de su contacto."""
        codigo = employee.work_contact_id.l10n_latam_identification_type_id.l10n_co_ne_dian_document_code or ''
        tipo = _UGPP_DOC_TRABAJADOR.get(codigo)
        numero = (employee.identification_id or '').strip()
        if not tipo or not numero:
            raise UserError(_(
                'El documento de %(empleado)s no tiene equivalente en la lista de la UGPP (CC, CE, TI, PA o PE) o '
                'falta el número.', empleado=employee.display_name))
        if tipo in ('CC', 'CE') and not (numero.isdigit() and len(numero) <= 10):
            raise UserError(_(
                'El número de documento de %(empleado)s debe tener hasta 10 dígitos para %(tipo)s.',
                empleado=employee.display_name, tipo=tipo))
        return tipo, numero

    def _ugpp_entero(self, valor, employee, rule):
        """Valor de un concepto como entero ≥ 0 (el formato UGPP lo exige): redondeo al peso del mismo método que usa
        Odoo para importes (mitad hacia arriba). Un valor negativo no es un pago y se rechaza nombrando al empleado y la
        regla."""
        if valor < 0:
            raise UserError(_(
                'El concepto "%(regla)s" de %(empleado)s suma un valor negativo (%(valor)s) en el periodo: el formato '
                'UGPP solo admite enteros mayores o iguales a cero. Revise los recibos del mes.',
                regla=rule.display_name, empleado=employee.display_name, valor=valor))
        return int(float_round(valor, precision_digits=0))

    def _ugpp_codigos_vacaciones(self):
        return ('CO_VAC',)

    def _ugpp_codigos_suspension(self):
        """Mismos tipos de ausencia que ``hr.payslip._ne_dias_sln`` (SLN): los 'unpaid' y CO_LIC_NR."""
        unpaid = self.env['hr.leave.type'].search([('unpaid', '=', True)])
        codigos = set(unpaid.mapped('work_entry_type_id.code')) - {False}
        codigos.add('CO_LIC_NR')
        return tuple(sorted(codigos - {'CO_VAC', 'CO_LIC_REM'}))

    def _ugpp_fechas_ausencia(self, employee, codigos, recortar=True):
        """``(inicio, fin)`` como 'dd/mm/aaaa' de las ausencias validadas del empleado con esos tipos de entrada de
        trabajo que tocan el mes del reporte; ('', '') si no hay. Permiso y suspensión van recortadas al mes (la
        plantilla pide que "la fecha corresponda al mes que se está registrando"); las vacaciones llevan las fechas
        reales de la ausencia (la plantilla no impone el mes)."""
        hojas = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id), ('state', '=', 'validate'),
            ('holiday_status_id.work_entry_type_id.code', 'in', list(codigos)),
            ('request_date_from', '<=', self.date_to), ('request_date_to', '>=', self.date_from)])
        if not hojas:
            return '', ''
        inicio = min(hojas.mapped('request_date_from'))
        fin = max(hojas.mapped('request_date_to'))
        if recortar:
            inicio, fin = max(inicio, self.date_from), min(fin, self.date_to)
        return inicio.strftime('%d/%m/%Y'), fin.strftime('%d/%m/%Y')

    def _ugpp_fecha_pago(self, slip):
        """Primera fecha de pago del recibo (la misma fuente del documento DIAN). Sin fecha no se supone ninguna: el
        error nombra el recibo y dice cómo corregirlo; solo afecta a los reportes que incluyen ese recibo."""
        try:
            return slip._ne_fecha_pago()
        except UserError as error:
            raise UserError(_(
                '%(error)s\n\nEl reporte UGPP necesita la fecha de pago del recibo "%(recibo)s" porque tiene valor '
                'de vacaciones (la Guía pide reportarlo en el mes en que se pagó). Corríjalo registrando la fecha de '
                'pago en ese recibo; solo afecta a los reportes que lo incluyan.',
                error=error.args[0], recibo=slip.display_name)) from error

    def _ugpp_recibos_del_mes(self, payslips):
        """Recibos del reporte cuyo ``date_to`` cae en el periodo (decisión de David: el mes es el del periodo
        trabajado). El resto de ``payslips`` son recibos de otros meses con vacaciones pagadas en este."""
        return payslips.filtered(lambda s: self.date_from <= s.date_to <= self.date_to)

    def _ugpp_recibos(self):
        """Recibos que alimentan el reporte: los del mes (por ``date_to``) más los de otros meses con valor de
        vacaciones cuyo pago cae en el mes (Guía V-20.1, numeral 1.3, p. 13: el valor de las vacaciones se reporta en
        el mes en que realmente se pagó). Excluye notas de crédito, notas de ajuste por recibo y empleados de
        habilitación."""
        self.ensure_one()
        base = [
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('done', 'paid')),
            # doc 39 (2026-10-04): los empleados sintéticos del asistente de habilitación DIAN no son personal real.
            ('employee_id.l10n_co_ne_is_habilitacion_test', '=', False),
        ]
        # date_to y no date_from: la liquidación tiene date_from = inicio de contrato (H-017b).
        del_mes = self.env['hr.payslip'].search(
            base + [('date_to', '>=', self.date_from), ('date_to', '<=', self.date_to)])
        con_vacaciones = self.env['hr.payslip'].search(base + [
            ('date_to', '<', self.date_from),
            ('line_ids.salary_rule_id.l10n_co_ugpp_payment_type', 'in', _UGPP_TIPOS_VACACIONES)])
        con_vacaciones = con_vacaciones.filtered(lambda s: any(
            l.total and l.salary_rule_id.l10n_co_ugpp_payment_type in _UGPP_TIPOS_VACACIONES for l in s.line_ids))
        pagadas_en_el_mes = con_vacaciones.filtered(
            lambda s: self.date_from <= self._ugpp_fecha_pago(s) <= self.date_to)
        return del_mes | pagadas_en_el_mes

    def _ugpp_valores(self, payslips):
        """``{employee_id: {rule_id: total}}`` con el valor de cada concepto UGPP en el mes: los conceptos de tipo
        vacaciones salen de los recibos pagados en el mes (el pago manda), todos los demás de los recibos del mes
        (``date_to``). Las vacaciones de un recibo del mes pagadas en otro mes no se cuentan aquí."""
        self.ensure_one()
        del_mes = self._ugpp_recibos_del_mes(payslips)
        valores = {}
        for slip in payslips:
            paga_en_el_mes = None
            for line in slip.line_ids:
                tipo = line.salary_rule_id.l10n_co_ugpp_payment_type
                if not tipo or not line.total:
                    continue
                if tipo in _UGPP_TIPOS_VACACIONES:
                    if paga_en_el_mes is None:
                        paga_en_el_mes = self.date_from <= self._ugpp_fecha_pago(slip) <= self.date_to
                    if not paga_en_el_mes:
                        continue
                elif slip not in del_mes:
                    continue
                por_regla = valores.setdefault(slip.employee_id.id, {})
                por_regla[line.salary_rule_id.id] = por_regla.get(line.salary_rule_id.id, 0.0) + line.total
        return valores

    def _ugpp_empleados(self, payslips):
        """``[(empleado, recibo de referencia)]`` ordenado por nombre: una fila por empleado y mes. El recibo de
        referencia (contrato, datos fijos) es el último del mes; si el empleado solo tiene vacaciones pagadas en el mes,
        el último recibo que las trae."""
        valores = self._ugpp_valores(payslips)
        del_mes = self._ugpp_recibos_del_mes(payslips)
        filas = []
        for empleado in payslips.employee_id.sorted('name'):
            propios = del_mes.filtered(lambda s: s.employee_id == empleado)
            if not propios and not valores.get(empleado.id):
                continue
            candidatos = propios or payslips.filtered(lambda s: s.employee_id == empleado)
            filas.append((empleado, candidatos.sorted(lambda s: (s.date_to, s.id))[-1]))
        return filas

    def _get_ugpp_salary_rules(self, payslips):
        """Reglas salariales con tipo de pago UGPP que tienen VALOR (total distinto de cero) en los recibos del
        reporte, ordenadas. Una regla sin uso en el periodo no es un concepto del reporte (ni hoja de conceptos ni
        columna de la hoja nómina): así no se exige cuenta contable a lo que no se pagó (doc 57, U3b). La hoja de
        conceptos y la de nómina usan esta misma lista, de modo que el CONCEPTO N coincide en las dos."""
        ids = {rid for por_regla in self._ugpp_valores(payslips).values()
               for rid, total in por_regla.items() if total}
        return self.env['hr.salary.rule'].browse(ids).sorted(key=lambda r: (r.sequence, r.code or ''))

    def _generate_sheet_conceptos(
        self, ws, payslips, header_font, header_fill, header_alignment, thin_border
    ):
        """
        Genera la hoja de conceptos de pago (formulario 7003) según la Guía UGPP V-20.1.

        Columnas:
        1. Concepto (auto-numerado)
        2. Nombre concepto
        3. Cuenta contable
        4. Tipo pago
        5. Clasificación TP NO SALARIAL
        """
        headers = [
            (4, 'Concepto'),
            (8, 'Nombre concepto'),
            (12, 'Cuenta contable'),
            (19, 'Tipo pago'),
            (20, 'Clasificación TP NO SALARIAL'),
        ]
        fila_datos = self._ugpp_marco(
            ws, 'conceptos', headers, header_font, header_fill, header_alignment, thin_border)

        salary_rules = self._get_ugpp_salary_rules(payslips)
        filas = self._ugpp_filas_conceptos(salary_rules)
        for idx, row_data in enumerate(filas, 1):
            self._ugpp_escribir_fila(ws, fila_datos + idx - 1, row_data, thin_border)

        # Ajustar anchos
        for col in ws.columns:
            max_length = max(
                len(str(cell.value or '')) for cell in col
            )
            ws.column_dimensions[col[0].column_letter].width = (
                min(max_length + 2, 50)
            )

    # ──────────────────────────────────────────────────────────────────
    # IBC Calculation
    # ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    # Hoja 3: nomina – UGPP Storm User V-20.1
    # ──────────────────────────────────────────────────────────────────

    @api.model
    def _dias_ugpp(self, consolidado):
        """Días del empleado-mes para las columnas 19-26 del reporte.

        Total = ``consolidado.dias_sp`` (misma fuente que PILA). Cada novedad se suma de las
        mismas funciones de días que usan las reglas de nómina y PILA, sobre los recibos del
        consolidado; los días trabajados son lo que resta del total (sin negativos).
        ``huelga`` no tiene fuente en el módulo y queda en 0."""
        dias = dict.fromkeys(
            ('incapacidad', 'lic_mat', 'lic_rem', 'suspension', 'vacaciones', 'huelga'), 0)
        for slip in consolidado.payslip_ids:
            for codigo in ('CO_INC_COMUN', 'CO_INC_LABORAL'):
                dias['incapacidad'] += slip._ne_ausencia_calendario(codigo)[0]
            for codigo in ('CO_LIC_MAT', 'CO_LIC_PAT'):
                dias['lic_mat'] += slip._ne_ausencia_calendario(codigo)[0]
            dias['suspension'] += slip._ne_dias_sln()
            for wd in slip.worked_days_line_ids:
                codigo = wd.work_entry_type_id.code
                if codigo == 'CO_LIC_REM':
                    dias['lic_rem'] += wd.number_of_days
                elif codigo == 'CO_VAC':
                    dias['vacaciones'] += wd.number_of_days
        dias = {k: int(v) for k, v in dias.items()}
        total = int(consolidado.dias_sp)
        dias['total'] = total
        dias['trabajados'] = max(0, total - sum(
            v for k, v in dias.items() if k != 'total'))
        return dias

    def _generate_sheet_nomina(
        self, ws, payslips, header_font, header_fill,
        header_alignment, thin_border
    ):
        """
        Genera la hoja 'nomina' según la guía UGPP Storm User V-20.1.

        Estructura de columnas:
        - 36 columnas fijas (datos del cotizante, novedades, días, fechas, observaciones)
        - N columnas dinámicas (una por regla salarial con tipo UGPP y valor en el periodo)
        """
        # ── Columnas fijas ───────────────────────────────────────────
        fixed_headers = [
            'Tipo cotizante',                           # 1
            'Subtipo cotizante',                        # 2
            'Condición especial empresa',               # 3
            'Extranjero no obligado pensión',           # 4
            'Colombiano en el exterior',                # 5
            'Actividad alto riesgo pensión',            # 6
            'Tipo documento cotizante',                 # 7
            'Número documento cotizante',               # 8
            'Nombre cotizante',                         # 9
            'Cargo del trabajador',                     # 10
            'Año',                                      # 11
            'Mes',                                      # 12
            'Salario integral',                         # 13
            'Novedad incapacidad',                      # 14
            'Novedad licencia mat o pat',               # 15
            'Novedad permiso o licencia remunerada',    # 16
            'Novedad de suspensión',                    # 17
            'Novedad vacaciones',                       # 18
            'Número días trabajados',                   # 19
            'Número días incapacidades',                # 20
            'Número días licencia mat o pat',           # 21
            'Número días permiso o lic remuneradas',    # 22
            'Número días suspensión/lic no remunerada', # 23
            'Número días vacaciones',                   # 24
            'Número días huelga',                       # 25
            'Total días reportados',                    # 26
            'Ingreso',                                  # 27
            'Fecha ingreso',                            # 28
            'Retiro',                                   # 29
            'Fecha retiro',                             # 30
            'Fecha inicio vacaciones',                  # 31
            'Fecha terminación vacaciones',             # 32
            'Fecha inicio permiso o licencia remunerada',  # 33
            'Fecha inicio suspensión o licencia no remunerada',  # 34
            'Fecha inicio huelga',                      # 35
            'Observaciones aportante',                  # 36
        ]

        # ── Columnas dinámicas (conceptos de pago) ───────────────────
        ugpp_rules = self._get_ugpp_salary_rules(payslips)
        concept_headers = [rule.name or rule.code or '' for rule in ugpp_rules]

        if len(concept_headers) > _UGPP_MAX_CONCEPTOS:
            raise UserError(_(
                'El formato UGPP admite %(max)s conceptos de pago y este periodo tiene %(n)s reglas con valor. '
                'Agrupe conceptos (reglas con el mismo tipo de pago) antes de generar el reporte.',
                max=_UGPP_MAX_CONCEPTOS, n=len(concept_headers)))

        # El formato no tiene columnas de IBC (la UGPP las rechaza): el IBC vive en PILA.
        all_headers = fixed_headers + concept_headers
        # Códigos de columna de la plantilla (fila 9).
        codigos = (list(_UGPP_COD_NOMINA) + [_UGPP_COD_OBSERVACIONES]
                   + [_UGPP_COD_CONCEPTO_1 + 4 * i for i in range(len(concept_headers))])
        fila_datos = self._ugpp_marco(
            ws, 'nomina', list(zip(codigos, all_headers)), header_font, header_fill, header_alignment, thin_border)

        # ── Preparar mapeos ──────────────────────────────────────────
        period_start = self.date_from
        period_end = self.date_to

        # ── Iterar nóminas ───────────────────────────────────────────
        row_num = fila_datos
        valores = self._ugpp_valores(payslips)
        for employee, payslip in self._ugpp_empleados(payslips):
            contract = payslip.contract_id
            # Valor de cada concepto del mes para el empleado (una fila por empleado y mes; vacaciones por fecha de pago).
            rule_totals = valores.get(employee.id, {})

            # -- Días e IBC: del consolidado mensual (H-017b / UGPP días) ----
            # El consolidado es por empleado y mes: PILA, nómina y este reporte comparten la misma fuente. Un empleado
            # sin recibos con ``date_to`` en el mes (solo vacaciones pagadas en él) va con días en 0, sin novedades.
            if payslip in self._ugpp_recibos_del_mes(payslips):
                consolidado = self.env['l10n.co.ibc.mensual']._refrescar(
                    payslip.company_id, employee, self.date_from)
                if not consolidado:
                    raise UserError(_(
                        'No hay IBC consolidado para %(empleado)s en %(mes)s: ningun '
                        'recibo confirmado trae las lineas de IBC. Recalcule y confirme '
                        'la nomina.',
                        empleado=employee.name, mes=self.date_from.strftime('%Y-%m')))
                dias = self._dias_ugpp(consolidado)
            else:
                dias = dict.fromkeys(
                    ('trabajados', 'incapacidad', 'lic_mat', 'lic_rem', 'suspension',
                     'vacaciones', 'huelga', 'total'), 0)

            dias_trabajados = dias['trabajados']
            dias_incapacidad = dias['incapacidad']
            dias_licencia_mat = dias['lic_mat']
            dias_lic_remunerada = dias['lic_rem']
            dias_suspension = dias['suspension']
            dias_vacaciones = dias['vacaciones']
            dias_huelga = dias['huelga']
            total_dias = dias['total']

            # -- Novedades (X / vacío) ---------------------------------
            nov_incapacidad = 'X' if dias_incapacidad > 0 else ''
            nov_lic_mat = 'X' if dias_licencia_mat > 0 else ''
            nov_lic_rem = 'X' if dias_lic_remunerada > 0 else ''
            nov_suspension = 'X' if dias_suspension > 0 else ''
            nov_vacaciones = 'X' if dias_vacaciones > 0 else ''

            # -- Nombre: APELLIDO1 APELLIDO2 NOMBRE1 NOMBRE2 -----------
            name_parts = employee._l10n_co_nombre_dian()
            nombre_cotizante = ' '.join(filter(None, [
                name_parts.get('primer_apellido', ''),
                name_parts.get('segundo_apellido', ''),
                name_parts.get('primer_nombre', ''),
                name_parts.get('otros_nombres', ''),
            ]))

            # -- Tipo y número de documento (lista UGPP) -------------------
            tipo_doc_ugpp, numero_doc = self._ugpp_documento_trabajador(employee)

            # -- Tipo y subtipo de cotizante (tabla PILA del contrato → lista UGPP) --
            tipo_cotizante, subtipo_cotizante = self._ugpp_cotizante(employee, contract)

            # -- Ingreso / Retiro en el período ------------------------
            es_ingreso = False
            fecha_ingreso = ''
            if contract and contract.date_start:
                if period_start <= contract.date_start <= period_end:
                    es_ingreso = True
                    fecha_ingreso = contract.date_start.strftime('%d/%m/%Y')

            es_retiro = False
            fecha_retiro = ''
            if contract and contract.date_end:
                if period_start <= contract.date_end <= period_end:
                    es_retiro = True
                    fecha_retiro = contract.date_end.strftime('%d/%m/%Y')

            # -- Fechas de las novedades (desde Ausencias validadas) ---------
            fecha_ini_vac, fecha_fin_vac = (
                self._ugpp_fechas_ausencia(employee, self._ugpp_codigos_vacaciones(), recortar=False)
                if dias_vacaciones else ('', ''))
            fecha_ini_lic_rem = (
                self._ugpp_fechas_ausencia(employee, ('CO_LIC_REM',))[0] if dias_lic_remunerada else '')
            fecha_ini_suspension = (
                self._ugpp_fechas_ausencia(employee, self._ugpp_codigos_suspension())[0] if dias_suspension else '')
            fecha_ini_huelga = ''      # sin fuente en el módulo (huelga queda en 0 días)

            # -- Cargo del trabajador ----------------------------------
            cargo = (
                employee.job_title
                or (employee.job_id.name if employee.job_id else '')
                or ''
            )

            # -- Salario integral --------------------------------------
            integral = (
                'X'
                if contract and contract.l10n_co_ne_integral_salary
                else ''
            )

            # ═════════════════════════════════════════════════════════
            # Construir fila de datos fijos (33 columnas)
            # ═════════════════════════════════════════════════════════
            fixed_data = [
                tipo_cotizante,                                     # 1
                subtipo_cotizante,                                  # 2
                '',                                                 # 3  Condición especial empresa
                'X' if employee.l10n_co_ne_foreigner_no_pension else '',  # 4
                'X' if employee.l10n_co_ne_colombian_abroad else '',      # 5
                'X' if employee.l10n_co_ne_high_risk_pension else '',     # 6
                tipo_doc_ugpp,                                      # 7
                numero_doc,                                         # 8
                nombre_cotizante,                                   # 9
                cargo,                                              # 10
                self.year,                                          # 11
                int(self.month),                                    # 12
                integral,                                           # 13
                nov_incapacidad,                                    # 14
                nov_lic_mat,                                        # 15
                nov_lic_rem,                                        # 16
                nov_suspension,                                     # 17
                nov_vacaciones,                                     # 18
                dias_trabajados,                                    # 19
                dias_incapacidad,                                   # 20
                dias_licencia_mat,                                  # 21
                dias_lic_remunerada,                                # 22
                dias_suspension,                                    # 23
                dias_vacaciones,                                    # 24
                dias_huelga,                                        # 25
                total_dias,                                         # 26
                'X' if es_ingreso else '',                          # 27
                fecha_ingreso,                                      # 28
                'X' if es_retiro else '',                           # 29
                fecha_retiro,                                       # 30
                fecha_ini_vac,                                      # 31
                fecha_fin_vac,                                      # 32
                fecha_ini_lic_rem,                                  # 33
                fecha_ini_suspension,                               # 34
                fecha_ini_huelga,                                   # 35
                _UGPP_NOTA_360,                                     # 36 Observaciones
            ]

            # ═════════════════════════════════════════════════════════
            # Columnas dinámicas: monto por regla salarial UGPP
            # ═════════════════════════════════════════════════════════
            concept_data = [
                self._ugpp_entero(rule_totals.get(rule.id, 0.0), employee, rule) for rule in ugpp_rules
            ]

            # ═════════════════════════════════════════════════════════
            # Escribir fila completa
            # ═════════════════════════════════════════════════════════
            row_data = fixed_data + concept_data

            self._ugpp_escribir_fila(ws, row_num, row_data, thin_border)

            row_num += 1

        # Ajustar anchos
        for col in ws.columns:
            max_length = max(
                len(str(cell.value or '')) for cell in col
            )
            ws.column_dimensions[col[0].column_letter].width = (
                min(max_length + 2, 40)
            )

        _logger.info(
            'Hoja "nomina" generada con %d filas (%d columnas: '
            '%d fijas + %d conceptos)',
            row_num - fila_datos,
            len(all_headers),
            len(fixed_headers),
            len(concept_headers),
        )
