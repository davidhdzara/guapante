# -*- coding: utf-8 -*-
"""
Modelo principal del modulo l10n_co_bank_payment_export.

Este modulo implementa la generacion de archivos planos para los portales
de pago masivo de los principales bancos colombianos.

Arquitectura:
    BankPaymentExport (este archivo)
        |-- Modelo de auditoria. Almacena un registro por cada archivo generado.
        |-- Despacha la generacion al modulo del banco correspondiente.
        |
        |-- _generate_davivienda()   (definido aqui, formato Excel)
        |-- _generate_bogota()       (definido aqui, ASCII 250 chars)
        |-- _generate_bancolombia()  (delega a bancolombia_generator.py)

Para agregar un nuevo banco:
    1. Agregar opcion en BANK_SELECTION.
    2. Implementar _generate_<banco>() siguiendo el patron existente.
    3. Implementar validacion de filas en _row_<banco>_vendor() y
       _row_<banco>_payroll() que retornen una estructura de datos.
    4. Agregar el banco al despachador _generate_file().
    5. Agregar el banco a _row_for_validation() para el reporte previo.

Buenas practicas:
    - Cada banco tiene sus propias validaciones; no compartir validadores.
    - Las funciones _row_*() retornan datos limpios o levantan ValidationError.
    - El generador final (_generate_*) consume esos datos y construye el archivo.
    - Toda longitud fija debe verificarse con raise ValueError.
"""

import base64
import io
import unicodedata

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
except ImportError:
    raise ImportError(
        "La libreria openpyxl es requerida. "
        "Instale con: pip install openpyxl"
    )


# ===========================================================================
# Catalogos y mapeos por banco
# ===========================================================================

# --- Davivienda ------------------------------------------------------------
# Codigos numericos del tipo de identificacion segun el formato Davivienda.
DAVIVIENDA_ID_TYPE_MAP = {
    'CC':  '01',   # Cedula de Ciudadania
    'CE':  '02',   # Cedula de Extranjeria
    'NIT': '03',   # NIT
    'TI':  '04',   # Tarjeta de Identidad
    'PAS': '05',   # Pasaporte
    'RC':  '13',   # Registro Civil
}


# --- Banco de Bogota -------------------------------------------------------
# Codigos alfabeticos del tipo de identificacion segun el formato del banco.
BOGOTA_ID_TYPE_MAP = {
    'CC':  'C',   # Cedula de Ciudadania
    'CE':  'E',   # Cedula de Extranjeria
    'NIT': 'N',   # NIT Persona Juridica
    'TI':  'T',   # Tarjeta de Identidad
    'PAS': 'P',   # Pasaporte
    # Sin mapeo directo: 'L' = NIT Persona Natural (se infiere si is_company=False y vat parece NIT)
}

# Tipo de movimiento segun el origen del pago.
# Se usa en el Registro Tipo 1 (Header) del archivo Banco de Bogota.
BOGOTA_MOVEMENT_TYPE_MAP = {
    'vendor':  '002',  # Proveedores
    'payroll': '001',  # Nomina
    'both':    '003',  # Otros Terceros (mixto)
}

# Tipo de cuenta del beneficiario.
# El campo l10n_co_account_type (definido en res_partner_bank.py) usa
# las claves CA/CC/DP/TP/DE. Banco de Bogota usa codigos numericos.
BOGOTA_ACCOUNT_TYPE_MAP = {
    'CC': '1',  # Cuenta Corriente
    'CA': '2',  # Cuenta de Ahorros
    'DP': '9',  # DaviPlata - se trata como deposito electronico
    'DE': '9',  # Deposito Electronico
    'TP': '2',  # Tarjeta Prepago - se trata como ahorros
}

# Mapeo del tipo de cuenta dispersora de la empresa al codigo Banco de Bogota.
# Pos 34 del header: 1=Corriente, 2=Ahorros, 5=Credito/Sobregiro
BOGOTA_DISPERSAL_TYPE_MAP = {
    'D': '1',  # Corriente / Debito
    'S': '2',  # Ahorros
    'C': '5',  # Contable / Credito
}


# --- Catalogos generales del modulo ---------------------------------------

BANK_SELECTION = [
    ('davivienda',      'Banco Davivienda'),
    ('bogota',          'Banco de Bogota'),
    ('bancolombia_pab', 'Bancolombia - PAB (recomendado)'),
    ('bancolombia_sap', 'Bancolombia - SAP (legacy)'),
]

STATE_SELECTION = [
    ('draft',     'Borrador'),
    ('generated', 'Generado'),
    ('cancelled', 'Cancelado'),
]


# ===========================================================================
# Helpers - funciones puras sin dependencia de Odoo
# ===========================================================================

def _sanitize(text, max_len=40):
    """
    Limpia un texto para que sea aceptado por los portales bancarios.

    Reglas aplicadas:
    - Elimina tildes (NFD + descarte de marcas combinatorias).
    - Reemplaza por espacio cualquier caracter no ASCII basico.
    - Colapsa espacios multiples.
    - Trunca a max_len caracteres.

    Esta funcion es compartida por todos los bancos porque todos
    rechazan caracteres especiales y tildes.
    """
    if not text:
        return ''
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    allowed = (
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        'abcdefghijklmnopqrstuvwxyz'
        '0123456789 '
    )
    text = ''.join(c if c in allowed else ' ' for c in text)
    return ' '.join(text.split())[:max_len]


def _only_digits(text, max_len=16):
    """Extrae unicamente los digitos de una cadena con limite de longitud."""
    return ''.join(filter(str.isdigit, text or ''))[:max_len]


def _davivienda_id_type(partner):
    """Mapea el tipo de documento del partner al codigo numerico Davivienda."""
    doc = getattr(partner, 'l10n_co_document_type', '') or ''
    return DAVIVIENDA_ID_TYPE_MAP.get(doc, '03' if partner.is_company else '01')


def _bogota_id_type(partner):
    """Mapea el tipo de documento del partner al codigo alfabetico de Banco de Bogota."""
    doc = getattr(partner, 'l10n_co_document_type', '') or ''
    if doc in BOGOTA_ID_TYPE_MAP:
        return BOGOTA_ID_TYPE_MAP[doc]
    # Sin mapeo explicito: inferir por tipo de partner
    return 'N' if partner.is_company else 'C'


def _bogota_account_type(bank_account):
    """Mapea el tipo de cuenta del beneficiario al codigo numerico de Banco de Bogota."""
    account_type = getattr(bank_account, 'l10n_co_account_type', '') or 'CA'
    return BOGOTA_ACCOUNT_TYPE_MAP.get(account_type, '2')  # default ahorros


def _get_ach_code(bank_account):
    """
    Lee el codigo ACH Colombia del banco asociado a la cuenta.
    Este codigo identifica al banco destino en cualquier formato bancario.
    """
    if not bank_account or not bank_account.bank_id:
        return ''
    return (bank_account.bank_id.l10n_co_ach_code or '').strip()


def _get_account_type(bank_account):
    """Lee el tipo de cuenta colombiano (CA/CC/DP/TP/DE)."""
    return (getattr(bank_account, 'l10n_co_account_type', '') or 'CA')


# ===========================================================================
# Modelo principal de auditoria
# ===========================================================================

class BankPaymentExport(models.Model):
    """
    Registro de auditoria de cada archivo plano bancario generado.

    Caracteristicas:
    - Se crea exclusivamente desde el wizard; nunca manualmente.
    - Inmutable despues de generado (solo cancelable o reseteable).
    - Hereda mail.thread para trazabilidad completa.
    - Indexado por nombre, fecha y compania para reportes rapidos.
    """
    _name = 'bank.payment.export'
    _description = 'Archivo Plano Bancario'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _sql_constraints = [
        (
            'name_company_uniq',
            'UNIQUE(name, company_id)',
            'Ya existe una exportacion con esta referencia en esta compania.',
        ),
    ]

    # -- Identificacion ------------------------------------------------------

    name = fields.Char(
        string='Referencia',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('Nuevo'),
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compania',
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        index=True,
    )
    date = fields.Date(
        string='Fecha de Generacion',
        required=True,
        readonly=True,
        default=fields.Date.context_today,
        index=True,
    )

    # -- Configuracion -------------------------------------------------------

    bank = fields.Selection(
        selection=BANK_SELECTION,
        string='Banco',
        required=True,
        readonly=True,
        tracking=True,
        help='Banco y formato de archivo a generar.',
    )
    payment_source = fields.Selection(
        selection=[
            ('vendor',  'Pagos a Proveedores'),
            ('payroll', 'Nomina'),
            ('both',    'Proveedores y Nomina'),
        ],
        string='Origen del Pago',
        required=True,
        readonly=True,
        tracking=True,
    )

    # -- Relaciones ----------------------------------------------------------

    payment_ids = fields.Many2many(
        comodel_name='account.payment',
        relation='bank_export_payment_rel',
        column1='export_id',
        column2='payment_id',
        string='Pagos a Proveedores',
        readonly=True,
    )
    payslip_ids = fields.Many2many(
        comodel_name='hr.payslip',
        relation='bank_export_payslip_rel',
        column1='export_id',
        column2='payslip_id',
        string='Recibos de Nomina',
        readonly=True,
    )

    # -- Resultado -----------------------------------------------------------

    state = fields.Selection(
        selection=STATE_SELECTION,
        string='Estado',
        default='draft',
        tracking=True,
        copy=False,
        readonly=True,
        index=True,
    )
    # Nota: el campo se llama 'excel_file' por compatibilidad historica
    # con la version 1.0 que solo soportaba Davivienda (Excel).
    # Ahora almacena tanto .xlsx como .txt segun el banco.
    excel_file = fields.Binary(
        string='Archivo Generado',
        readonly=True,
        copy=False,
        attachment=True,
        help='Archivo binario del documento generado. '
             'Puede ser Excel (.xlsx) o texto plano (.txt) segun el banco.',
    )
    excel_filename = fields.Char(
        string='Nombre del Archivo',
        readonly=True,
        copy=False,
    )
    line_count = fields.Integer(
        string='Registros Exportados',
        readonly=True,
        help='Numero de pagos efectivamente incluidos en el archivo generado.',
    )
    warning_count = fields.Integer(
        string='Registros con Advertencias',
        readonly=True,
    )
    notes = fields.Text(string='Notas')

    # -- Secuencia -----------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Asigna automaticamente la referencia desde la secuencia."""
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'bank.payment.export'
                ) or _('Nuevo')
        return super().create(vals_list)

    # -- Acciones publicas ---------------------------------------------------

    def action_cancel(self):
        """Cancela una exportacion en borrador. No elimina el registro."""
        self.ensure_one()
        if self.state == 'generated':
            raise UserError(_(
                'No se puede cancelar una exportacion ya generada. '
                'Use "Restablecer a Borrador" si necesita regenerarla.'
            ))
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        """
        Permite regenerar el archivo desde el registro de auditoria.
        Util cuando el banco rechaza el archivo y se necesita corregir
        datos en Odoo y regenerar sin perder el historial.
        """
        self.ensure_one()
        self.write({
            'state':          'draft',
            'excel_file':     False,
            'excel_filename': False,
            'line_count':     0,
            'warning_count':  0,
        })
        self.message_post(body=_(
            'Exportacion restablecida a borrador para regeneracion.'
        ))

    def action_generate_file(self):
        """
        Punto de entrada para regenerar desde el formulario de auditoria.
        Solo disponible en estado borrador (visible mediante invisible="state != 'draft'").
        """
        self.ensure_one()
        self._generate_file()
        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   _('Archivo generado'),
                'message': _('%d registros exportados correctamente.') % self.line_count,
                'type':    'success',
                'sticky':  False,
            },
        }

    # -----------------------------------------------------------------------
    # Despachador central de generacion
    # -----------------------------------------------------------------------

    def _generate_file(self):
        """
        Punto de entrada principal de la generacion.
        Despacha al generador correcto segun self.bank.

        Para agregar un banco nuevo:
            1. Agregar elif self.bank == '<nuevo>':
            2. Implementar self._generate_<nuevo>()
        """
        self.ensure_one()
        if self.bank == 'davivienda':
            self._generate_davivienda()
        elif self.bank == 'bogota':
            self._generate_bogota()
        elif self.bank in ('bancolombia_pab', 'bancolombia_sap'):
            self._generate_bancolombia()
        else:
            raise UserError(_('Banco no soportado: %s') % self.bank)
        self.write({'state': 'generated'})

    # -----------------------------------------------------------------------
    # Validacion previa para el wizard
    # -----------------------------------------------------------------------

    def get_validation_report(self):
        """
        Retorna un reporte de validacion antes de generar el archivo.
        El wizard lo usa para mostrar al usuario que registros estan
        listos y cuales tienen errores.

        Estructura del retorno:
            {
                'ready':  ['nombre_pago_1', ...],
                'errors': [{'name': 'nombre_pago', 'error': 'mensaje'}, ...]
            }

        Importante: usa la funcion de validacion del BANCO correcto
        (no siempre Davivienda como en versiones anteriores).
        """
        self.ensure_one()
        ready, errors = [], []

        # Seleccionar el validador correcto segun el banco
        if self.bank == 'davivienda':
            validate_vendor  = self._row_vendor_davivienda
            validate_payroll = self._row_payroll_davivienda
        elif self.bank == 'bogota':
            validate_vendor  = self._row_bogota_vendor
            validate_payroll = self._row_bogota_payroll
        elif self.bank in ('bancolombia_pab', 'bancolombia_sap'):
            # Bancolombia tiene su validacion dentro del generator;
            # reutilizamos sus _row_from_payment / _row_from_payslip.
            from . import bancolombia_generator as bcol
            gen = bcol.BancolombiaGeneratorPAB(self)
            validate_vendor  = gen._row_from_payment
            validate_payroll = gen._row_from_payslip
        else:
            return {'ready': [], 'errors': [
                {'name': '-', 'error': _('Banco no soportado: %s') % self.bank}
            ]}

        if self.payment_source in ('vendor', 'both'):
            for pay in self.payment_ids:
                try:
                    validate_vendor(pay)
                    ready.append(pay.name)
                except ValidationError as exc:
                    errors.append({
                        'name':  pay.name or str(pay.id),
                        'error': exc.args[0],
                    })

        if self.payment_source in ('payroll', 'both'):
            for slip in self.payslip_ids:
                try:
                    validate_payroll(slip)
                    ready.append(slip.name)
                except ValidationError as exc:
                    errors.append({
                        'name':  slip.employee_id.name or slip.name or str(slip.id),
                        'error': exc.args[0],
                    })

        return {'ready': ready, 'errors': errors}

    # =======================================================================
    # GENERADOR DAVIVIENDA - Formato Excel (.xlsx)
    # =======================================================================
    # Davivienda usa un formato Excel con 11 columnas. El archivo debe tener
    # exactamente una hoja llamada "Hoja1", sin filas vacias y con la columna
    # G (Numero de Producto) en formato texto para preservar ceros iniciales.
    # =======================================================================

    def _generate_davivienda(self):
        """Construye el archivo Excel para Davivienda y lo guarda como binario."""
        rows, errors = self._collect_rows_davivienda()
        if errors:
            raise UserError(
                _('No es posible generar el archivo. '
                  'Corrija los siguientes errores:\n\n%s')
                % '\n'.join('- %s' % e for e in errors)
            )
        if not rows:
            raise UserError(_('No se encontraron registros validos para exportar.'))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Hoja1'
        # Davivienda exige exactamente una hoja
        for sheet_name in [s for s in wb.sheetnames if s != 'Hoja1']:
            del wb[sheet_name]

        self._write_davivienda_header(ws)
        self._write_davivienda_rows(ws, rows)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        filename = 'Davivienda_%s_%s.xlsx' % (
            self.name.replace('/', '_'),
            fields.Date.today().strftime('%Y%m%d'),
        )
        self.write({
            'excel_file':     base64.b64encode(buffer.read()),
            'excel_filename': filename,
            'line_count':     len(rows),
        })

    def _write_davivienda_header(self, ws):
        """Escribe los encabezados con formato visual (rojo y blanco)."""
        headers = [
            'Tipo de Identificacion',
            'Numero de Identificacion',
            'Nombre',
            'Apellido',
            'Codigo del Banco',
            'Tipo de Producto o Servicio',
            'Numero del Producto o Servicio',
            'Valor del pago o de la recarga',
            'Referencia',
            'Correo Electronico',
            'Descripcion o Detalle',
        ]
        widths = [22, 25, 30, 30, 18, 26, 32, 28, 18, 35, 30]

        font   = Font(name='Arial', bold=True, color='FFFFFF', size=10)
        fill   = PatternFill('solid', start_color='C0392B')
        align  = Alignment(horizontal='center', vertical='center', wrap_text=True)
        thin   = Side(style='thin', color='CCCCCC')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        ws.row_dimensions[1].height = 36
        for idx, (col, width) in enumerate(zip(headers, widths), start=1):
            cell           = ws.cell(row=1, column=idx, value=col)
            cell.font      = font
            cell.fill      = fill
            cell.alignment = align
            cell.border    = border
            ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = width

    def _write_davivienda_rows(self, ws, rows):
        """Escribe las filas de datos con formato adecuado por columna."""
        font   = Font(name='Arial', size=10)
        align  = Alignment(horizontal='left', vertical='center')
        thin   = Side(style='thin', color='CCCCCC')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for row_idx, row_data in enumerate(rows, start=2):
            ws.row_dimensions[row_idx].height = 18
            for col_idx, value in enumerate(row_data, start=1):
                # Columna G: numero de cuenta como texto (preserva ceros izq)
                if col_idx == 7:
                    cell = ws.cell(row=row_idx, column=col_idx, value=str(value))
                    cell.number_format = '@'
                else:
                    cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font      = font
                cell.alignment = align
                cell.border    = border
                # Columna H: valor numerico con 2 decimales
                if col_idx == 8:
                    cell.number_format = '0.00'

    def _collect_rows_davivienda(self):
        """Recolecta filas y errores sin levantar excepcion (devuelve ambas listas)."""
        rows, errors = [], []
        if self.payment_source in ('vendor', 'both'):
            for pay in self.payment_ids:
                try:
                    rows.append(self._row_vendor_davivienda(pay))
                except ValidationError as exc:
                    errors.append(exc.args[0])
        if self.payment_source in ('payroll', 'both'):
            for slip in self.payslip_ids:
                try:
                    rows.append(self._row_payroll_davivienda(slip))
                except ValidationError as exc:
                    errors.append(exc.args[0])
        return rows, errors

    def _row_vendor_davivienda(self, payment):
        """Valida un pago a proveedor y retorna la fila en formato Davivienda."""
        partner  = payment.partner_id
        bank_acc = payment.partner_bank_id

        if not partner:
            raise ValidationError(
                _('El pago %s no tiene proveedor asignado.') % payment.name
            )
        if not bank_acc:
            raise ValidationError(
                _('El proveedor "%s" no tiene cuenta bancaria asignada en el pago %s.')
                % (partner.name, payment.name)
            )

        cop = self.env.ref('base.COP', raise_if_not_found=False)
        if cop and payment.currency_id and payment.currency_id != cop:
            raise ValidationError(
                _('El pago %s esta en %s. Davivienda solo acepta pagos en COP.')
                % (payment.name, payment.currency_id.name)
            )

        vat = _only_digits(partner.vat, 16)
        if not vat:
            raise ValidationError(
                _('El proveedor "%s" no tiene NIT o cedula configurado.') % partner.name
            )

        ach_code = _get_ach_code(bank_acc)
        if not ach_code:
            raise ValidationError(
                _('El banco del proveedor "%s" no tiene Codigo ACH Colombia. '
                  'Configure el campo en Contabilidad > Configuracion > Bancos.')
                % partner.name
            )
        acc_number = (bank_acc.acc_number or '').replace(' ', '').replace('-', '')
        if not acc_number:
            raise ValidationError(
                _('La cuenta bancaria de "%s" no tiene numero de cuenta.') % partner.name
            )
        if payment.amount <= 0:
            raise ValidationError(
                _('El pago %s tiene un valor de cero o negativo.') % payment.name
            )

        if partner.is_company:
            nombre, apellido = _sanitize(partner.name, 40), ''
        else:
            parts    = (partner.name or '').strip().split(' ', 1)
            nombre   = _sanitize(parts[0], 40)
            apellido = _sanitize(parts[1], 40) if len(parts) > 1 else ''

        return [
            _davivienda_id_type(partner),
            vat,
            nombre,
            apellido,
            ach_code,
            _get_account_type(bank_acc),
            acc_number,
            round(payment.amount, 2),
            _only_digits(payment.name, 16),
            (partner.email or '')[:50],
            _sanitize('Pago %s' % (partner.name or ''), 40),
        ]

    def _row_payroll_davivienda(self, payslip):
        """Valida un recibo de nomina y retorna la fila en formato Davivienda."""
        employee = payslip.employee_id
        if not employee:
            raise ValidationError(
                _('El recibo %s no tiene empleado asignado.') % payslip.name
            )
        partner = employee.address_home_id
        if not partner:
            raise ValidationError(
                _('El empleado "%s" no tiene direccion privada configurada.')
                % employee.name
            )
        bank_acc = employee.bank_account_id
        if not bank_acc:
            raise ValidationError(
                _('El empleado "%s" no tiene cuenta bancaria configurada.') % employee.name
            )
        vat = _only_digits(partner.vat, 16)
        if not vat:
            raise ValidationError(
                _('El empleado "%s" no tiene numero de identificacion '
                  '(campo VAT en la direccion privada).') % employee.name
            )
        ach_code = _get_ach_code(bank_acc)
        if not ach_code:
            raise ValidationError(
                _('El banco del empleado "%s" no tiene Codigo ACH Colombia. '
                  'Configure el campo en Contabilidad > Configuracion > Bancos.')
                % employee.name
            )
        acc_number = (bank_acc.acc_number or '').replace(' ', '').replace('-', '')
        if not acc_number:
            raise ValidationError(
                _('La cuenta bancaria del empleado "%s" no tiene numero de cuenta.')
                % employee.name
            )
        net = round(payslip.net_wage, 2)
        if net <= 0:
            raise ValidationError(
                _('El recibo de nomina de "%s" tiene valor neto de cero o negativo.')
                % employee.name
            )

        parts    = (employee.name or '').strip().split(' ', 1)
        nombre   = _sanitize(parts[0], 40)
        apellido = _sanitize(parts[1], 40) if len(parts) > 1 else ''
        periodo  = payslip.date_from.strftime('%Y%m') if payslip.date_from else ''

        return [
            _davivienda_id_type(partner),
            vat,
            nombre,
            apellido,
            ach_code,
            _get_account_type(bank_acc),
            acc_number,
            net,
            _only_digits(payslip.name, 16),
            (partner.email or employee.work_email or '')[:50],
            _sanitize('Nomina %s %s' % (periodo, employee.name or ''), 40),
        ]

    # =======================================================================
    # GENERADOR BANCO DE BOGOTA - Formato ASCII ancho fijo 250 chars
    # =======================================================================
    # Banco de Bogota usa un archivo plano ASCII con registros de exactamente
    # 250 caracteres por linea. Estructura:
    #   - Registro Tipo 1 (Header): identificacion de la empresa
    #   - Registros Tipo 2: detalle de cada pago
    #   - Registros Tipo 3 (opcional): notificaciones email/SMS (no implementado)
    #
    # Reglas de alineacion:
    #   - Numericos: derecha, ceros izquierda
    #   - Alfabeticos: izquierda, espacios derecha
    # =======================================================================

    def _generate_bogota(self):
        """Construye el archivo plano de Banco de Bogota."""
        if not self.company_id.l10n_co_dispersal_account:
            raise UserError(_(
                'Configure la cuenta dispersora de la empresa antes de generar '
                'el archivo de Banco de Bogota. '
                'Vaya a Configuracion > Empresas > pestana "Pagos Colombia".'
            ))
        rows, errors = self._collect_rows_bogota()
        if errors:
            raise UserError(
                _('No es posible generar el archivo. '
                  'Corrija los siguientes errores:\n\n%s')
                % '\n'.join('- %s' % e for e in errors)
            )
        if not rows:
            raise UserError(_('No se encontraron registros validos para exportar.'))

        lines = [self._build_bogota_header()]
        for row_data in rows:
            lines.append(self._build_bogota_detail_line(row_data))

        # Banco de Bogota acepta UTF-8; usamos latin-1 para compatibilidad
        # con sistemas legacy que pudieran procesar el archivo.
        content = '\r\n'.join(lines).encode('latin-1', errors='replace')

        filename = 'Bogota_%s_%s.txt' % (
            self.name.replace('/', '_'),
            fields.Date.today().strftime('%Y%m%d'),
        )
        self.write({
            'excel_file':     base64.b64encode(content),
            'excel_filename': filename,
            'line_count':     len(rows),
        })

    def _build_bogota_header(self):
        """
        Construye el Registro Tipo 1 (Header) - 250 caracteres exactos.

        Estructura (todas las posiciones verificadas contra PDF oficial):
            Pos  1     Tipo Registro          = "1"
            Pos  2-9   Fecha Dispersion       AAAAMMDD
            Pos  10-33 Ceros (24)
            Pos  34    Tipo Cuenta Dispersora 1/2/5
            Pos  35-40 Ceros (6)
            Pos  41-51 Numero Cuenta Dispersora (11)
            Pos  52-91 Nombre Empresa (40)
            Pos  92-102 NIT Empresa (11)
            Pos  103-105 Tipo Movimiento (001/002/003)
            Pos  106-109 Codigo Ciudad (4)
            Pos  110-117 Fecha Elaboracion AAAAMMDD
            Pos  118-120 Codigo Oficina (3)
            Pos  121    Tipo ID Empresa (N/L/I)
            Pos  122-250 Espacios (129)
        """
        company = self.company_id
        today   = fields.Date.today()
        fecha   = today.strftime('%Y%m%d')

        movement_type = BOGOTA_MOVEMENT_TYPE_MAP.get(self.payment_source, '003')
        doc_type = getattr(company.partner_id, 'l10n_co_document_type', 'NIT') or 'NIT'
        id_type  = 'N' if doc_type == 'NIT' else 'L'
        nombre   = _sanitize(company.name or '', 40)
        nit      = _only_digits(company.vat or '', 11)

        # Cuenta dispersora: solo digitos, justificada a la derecha con ceros
        disp_digits = _only_digits(company.l10n_co_dispersal_account or '', 11)
        disp_account = disp_digits.rjust(11, '0')
        # Codigo oficina: primeros 3 digitos de la cuenta dispersora
        oficina = disp_digits[:3].rjust(3, '0') if disp_digits else '000'
        # Tipo cuenta dispersora: S->2 (Ahorros), D->1 (Corriente), C->5 (Credito)
        disp_type = BOGOTA_DISPERSAL_TYPE_MAP.get(
            company.l10n_co_dispersal_account_type or 'S', '2'
        )

        line = ''
        line += '1'                                # Pos 1
        line += fecha                              # Pos 2-9
        line += '0' * 24                          # Pos 10-33
        line += disp_type                          # Pos 34 (tipo cuenta dispersora)
        line += '0' * 6                           # Pos 35-40
        line += disp_account                       # Pos 41-51 (numero cuenta dispersora)
        line += nombre.ljust(40)[:40]             # Pos 52-91
        line += nit.rjust(11, '0')                # Pos 92-102
        line += movement_type                      # Pos 103-105
        line += '0000'                             # Pos 106-109
        line += fecha                              # Pos 110-117
        line += oficina                            # Pos 118-120 (primeros 3 digitos cuenta)
        line += id_type                            # Pos 121
        line += ' ' * 129                          # Pos 122-250

        if len(line) != 250:
            raise ValueError('Header Bogota: %d chars (esperados 250)' % len(line))
        return line

    def _build_bogota_detail_line(self, row_data):
        """
        Construye un Registro Tipo 2 (Detalle) - 250 caracteres exactos.
        row_data: lista [id_type, vat, nombre, apellido, account_type,
                         account_number, amount, reference, email, description, ach_code]

        Estructura (verificada campo por campo contra PDF oficial):
            Pos  1      Tipo Registro          = "2"
            Pos  2      Tipo ID                C/N/T/E/L/P
            Pos  3-13   Numero ID (11)
            Pos  14-53  Nombre (40)
            Pos  54     Cero
            Pos  55     Tipo Cuenta            1/2/5/9
            Pos  56-72  Numero Cuenta (17)
            Pos  73-90  Valor (18 - centavos)
            Pos  91     Forma Pago = "A"
            Pos  92-94  Ceros (3)
            Pos  95-97  Codigo Banco Destino
            Pos  98-101 Codigo Ciudad (4)
            Pos  102-181 Adenda (80)
            Pos  182    Cero
            Pos  183-192 Numero Factura (10)
            Pos  193    Indicador Notificacion = "N"
            Pos  194-241 Espacios (48)
            Pos  242    Indicador Envio Mensaje = "N"
            Pos  243-250 Espacios (8)
        """
        (id_type, vat, nombre, apellido, account_type, account_number,
         amount, reference, email, description, ach_code) = row_data

        line = ''
        line += '2'                                                # Pos 1
        line += id_type                                            # Pos 2
        line += vat.rjust(11, '0')                                 # Pos 3-13
        nombre_completo = (nombre + ' ' + apellido).strip()
        line += nombre_completo.ljust(40)[:40]                    # Pos 14-53
        line += '0'                                                # Pos 54
        line += account_type                                       # Pos 55
        line += account_number.ljust(17)[:17]                     # Pos 56-72
        line += str(int(round(amount * 100))).rjust(18, '0')      # Pos 73-90
        line += 'A'                                                # Pos 91
        line += '000'                                              # Pos 92-94
        line += ach_code.rjust(3, '0')[:3]                        # Pos 95-97
        line += '0000'                                             # Pos 98-101
        line += description.ljust(80)[:80]                        # Pos 102-181
        line += '0'                                                # Pos 182
        line += reference.rjust(10, '0')[:10]                     # Pos 183-192
        line += 'N'                                                # Pos 193
        line += ' ' * 48                                           # Pos 194-241
        line += 'N'                                                # Pos 242
        line += ' ' * 8                                            # Pos 243-250

        if len(line) != 250:
            raise ValueError('Detalle Bogota: %d chars (esperados 250)' % len(line))
        return line

    def _collect_rows_bogota(self):
        """Recolecta filas y errores para Banco de Bogota."""
        rows, errors = [], []
        if self.payment_source in ('vendor', 'both'):
            for pay in self.payment_ids:
                try:
                    rows.append(self._row_bogota_vendor(pay))
                except ValidationError as exc:
                    errors.append(exc.args[0])
        if self.payment_source in ('payroll', 'both'):
            for slip in self.payslip_ids:
                try:
                    rows.append(self._row_bogota_payroll(slip))
                except ValidationError as exc:
                    errors.append(exc.args[0])
        return rows, errors

    def _row_bogota_vendor(self, payment):
        """Valida y construye una fila para pago a proveedor en Banco de Bogota."""
        partner  = payment.partner_id
        bank_acc = payment.partner_bank_id

        if not partner:
            raise ValidationError(
                _('El pago %s no tiene proveedor asignado.') % payment.name
            )
        if not bank_acc:
            raise ValidationError(
                _('El proveedor "%s" no tiene cuenta bancaria asignada en el pago %s.')
                % (partner.name, payment.name)
            )

        cop = self.env.ref('base.COP', raise_if_not_found=False)
        if cop and payment.currency_id and payment.currency_id != cop:
            raise ValidationError(
                _('El pago %s esta en %s. Banco de Bogota solo acepta pagos en COP.')
                % (payment.name, payment.currency_id.name)
            )

        vat = _only_digits(partner.vat, 11)
        if not vat:
            raise ValidationError(
                _('El proveedor "%s" no tiene NIT o cedula configurado.')
                % partner.name
            )

        ach_code = _get_ach_code(bank_acc)
        if not ach_code:
            raise ValidationError(
                _('El banco del proveedor "%s" no tiene Codigo ACH Colombia. '
                  'Configure el campo en Contabilidad > Configuracion > Bancos.')
                % partner.name
            )

        acc_number = (bank_acc.acc_number or '').replace(' ', '').replace('-', '')
        if not acc_number:
            raise ValidationError(
                _('La cuenta bancaria de "%s" no tiene numero de cuenta.') % partner.name
            )

        if payment.amount <= 0:
            raise ValidationError(
                _('El pago %s tiene un valor de cero o negativo.') % payment.name
            )

        # Nombre/apellido
        if partner.is_company:
            nombre, apellido = _sanitize(partner.name, 40), ''
        else:
            parts    = (partner.name or '').strip().split(' ', 1)
            nombre   = _sanitize(parts[0], 40)
            apellido = _sanitize(parts[1], 40) if len(parts) > 1 else ''

        return [
            _bogota_id_type(partner),                                # 0: Tipo ID
            vat,                                                      # 1: VAT
            nombre,                                                   # 2: Nombre
            apellido,                                                 # 3: Apellido
            _bogota_account_type(bank_acc),                          # 4: Tipo cuenta
            _sanitize(acc_number, 17),                               # 5: Numero cuenta
            round(payment.amount, 2),                                # 6: Monto
            _only_digits(payment.name, 10),                          # 7: Referencia
            (partner.email or '')[:50],                              # 8: Email
            _sanitize('Pago %s' % (partner.name or ''), 80),         # 9: Descripcion
            ach_code,                                                 # 10: Codigo banco destino
        ]

    def _row_bogota_payroll(self, payslip):
        """Valida y construye una fila para pago de nomina en Banco de Bogota."""
        employee = payslip.employee_id
        if not employee:
            raise ValidationError(
                _('El recibo %s no tiene empleado asignado.') % payslip.name
            )
        partner = employee.address_home_id
        if not partner:
            raise ValidationError(
                _('El empleado "%s" no tiene direccion privada configurada.')
                % employee.name
            )
        bank_acc = employee.bank_account_id
        if not bank_acc:
            raise ValidationError(
                _('El empleado "%s" no tiene cuenta bancaria configurada.')
                % employee.name
            )
        vat = _only_digits(partner.vat, 11)
        if not vat:
            raise ValidationError(
                _('El empleado "%s" no tiene numero de identificacion '
                  '(campo VAT en la direccion privada).') % employee.name
            )
        ach_code = _get_ach_code(bank_acc)
        if not ach_code:
            raise ValidationError(
                _('El banco del empleado "%s" no tiene Codigo ACH Colombia.')
                % employee.name
            )
        acc_number = (bank_acc.acc_number or '').replace(' ', '').replace('-', '')
        if not acc_number:
            raise ValidationError(
                _('La cuenta bancaria del empleado "%s" no tiene numero de cuenta.')
                % employee.name
            )
        net = round(payslip.net_wage, 2)
        if net <= 0:
            raise ValidationError(
                _('El recibo de nomina de "%s" tiene valor neto de cero o negativo.')
                % employee.name
            )

        parts    = (employee.name or '').strip().split(' ', 1)
        nombre   = _sanitize(parts[0], 40)
        apellido = _sanitize(parts[1], 40) if len(parts) > 1 else ''
        periodo  = payslip.date_from.strftime('%Y%m') if payslip.date_from else ''

        return [
            _bogota_id_type(partner),                                # 0
            vat,                                                      # 1
            nombre,                                                   # 2
            apellido,                                                 # 3
            _bogota_account_type(bank_acc),                          # 4
            _sanitize(acc_number, 17),                               # 5
            net,                                                      # 6
            _only_digits(payslip.name, 10),                          # 7
            (partner.email or employee.work_email or '')[:50],       # 8
            _sanitize('Nomina %s' % periodo, 80),                    # 9
            ach_code,                                                 # 10
        ]

    # =======================================================================
    # GENERADOR BANCOLOMBIA - Formatos PAB y SAP
    # =======================================================================
    # Bancolombia tiene dos formatos historicos. La generacion completa esta
    # encapsulada en bancolombia_generator.py. Aqui solo delegamos.
    # =======================================================================

    def _generate_bancolombia(self):
        """
        Delega al generador especifico segun el formato (PAB o SAP).
        Ambos producen texto plano codificado en latin-1.
        """
        from . import bancolombia_generator as bcol

        if self.bank == 'bancolombia_pab':
            generator = bcol.BancolombiaGeneratorPAB(self)
            fmt_label = 'PAB'
        else:
            generator = bcol.BancolombiaGeneratorSAP(self)
            fmt_label = 'SAP'

        content, n_records = generator.generate()

        filename = 'Bancolombia_%s_%s_%s.txt' % (
            fmt_label,
            self.name.replace('/', '_'),
            fields.Date.today().strftime('%Y%m%d'),
        )
        self.write({
            'excel_file':     base64.b64encode(content),
            'excel_filename': filename,
            'line_count':     n_records,
        })
