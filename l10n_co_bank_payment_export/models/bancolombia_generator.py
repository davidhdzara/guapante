"""
Generador de archivos planos para Bancolombia.

Formatos soportados:
  - PAB (Pagos Automaticos Bancolombia): 264 chars/linea — recomendado
  - SAP (Sistema de Aplicacion de Pagos):  95 chars/linea — legacy

Estructura PAB:
  Registro Tipo 1: Control de Lote     (264 chars) — 1 por archivo
  Registro Tipo 6: Detalle             (264 chars) — 1 por pago
  Registro Tipo 3: Adenda estructurada (264 chars) — opcional, facturas
  Registro Tipo 4: Adenda libre        (264 chars) — opcional, descripcion
  Registro Tipo 4&: Adenda conceptos   (264 chars) — opcional, nomina
  Registro Tipo 5: Pensiones           (264 chars) — solo clase 229

Estructura SAP:
  Registro Tipo 1: Control de Lote (95 chars) — 1 por archivo
  Registro Tipo 6: Detalle         (95 chars) — 1 por pago
  Registro Tipo 3: Adenda refs     (95 chars) — opcional

Referencias:
  Clase 220 = Pago a Proveedores
  Clase 225 = Pago de Nomina
  Tipo transaccion 27 = Abono Cuenta Corriente
  Tipo transaccion 37 = Abono Cuenta de Ahorros
  Tipo transaccion 52 = Abono Deposito Electronico
"""

from odoo.exceptions import UserError, ValidationError
from odoo import _, fields

import unicodedata


# ---------------------------------------------------------------------------
# Helpers internos de formato
# ---------------------------------------------------------------------------

def _n(value, length):
    """Campo numerico: alineado derecha, ceros izquierda, truncado."""
    return str(int(value or 0)).rjust(length, '0')[-length:]


def _x(value, length):
    """Campo alfanumerico: alineado izquierda, espacios derecha, truncado."""
    text = (value or '').strip()
    # Eliminar tildes y caracteres no ASCII
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.ljust(length)[:length]


def _amount_to_str(amount, length=17):
    """
    Convierte monto a string sin separador de miles ni punto decimal.
    Las dos ultimas posiciones son los centavos.
    Ej: 5000.50 -> '00000000000500050' (17 chars)
    """
    centavos = int(round(amount * 100))
    return str(centavos).rjust(length, '0')[-length:]


def _amount_to_str_sap(amount, length=10):
    """SAP: valor entero, sin decimales explicitos (el banco interpreta los 2 ultimos como decimales)."""
    centavos = int(round(amount * 100))
    return str(centavos).rjust(length, '0')[-length:]


def _sanitize_digits(text, max_len=15):
    """Extrae solo digitos con limite de longitud."""
    return ''.join(filter(str.isdigit, text or ''))[:max_len]


# ---------------------------------------------------------------------------
# Clases de transaccion Bancolombia
# ---------------------------------------------------------------------------

CLASE_PROVEEDOR = '220'
CLASE_NOMINA    = '225'

# Tipos de transaccion segun tipo de cuenta destino
TIPO_TX_CORRIENTE   = '27'
TIPO_TX_AHORROS     = '37'
TIPO_TX_DEPOSITO    = '52'
TIPO_TX_ELECTRONICO = '52'

# Mapeo l10n_co_account_type -> tipo de transaccion Bancolombia
BCOL_TX_TYPE_MAP = {
    'CA':  TIPO_TX_AHORROS,
    'CC':  TIPO_TX_CORRIENTE,
    'DE':  TIPO_TX_DEPOSITO,
}

# Tipo cuenta pagadora
BCOL_SRC_ACCOUNT_MAP = {
    'CA': 'S',   # Savings/Ahorros
    'CC': 'D',   # Debito/Corriente
}


# ---------------------------------------------------------------------------
# Generador PAB  (264 chars/linea)
# ---------------------------------------------------------------------------

class BancolombiaGeneratorPAB:
    """
    Genera archivos en formato PAB (Pagos Automaticos Bancolombia).
    Longitud de registro: 264 caracteres.
    """

    LINE_LEN = 264

    def __init__(self, export_record):
        self.rec = export_record
        self.company = export_record.company_id
        self.today = fields.Date.today()

    # -- Punto de entrada ------------------------------------------------

    def generate(self):
        if not self.company.l10n_co_dispersal_account:
            raise UserError(_(
                'Configure la cuenta dispersora de la empresa antes de generar '
                'el archivo de Bancolombia. '
                'Vaya a Configuracion > Empresas > pestana "Pagos Colombia".'
            ))
        rows = self._collect_rows()
        if not rows:
            raise UserError(_('No se encontraron registros válidos para exportar.'))

        total_amount = sum(r['amount'] for r in rows)
        n_records = len(rows)

        lines = []
        lines.append(self._build_control(n_records, total_amount))
        for row in rows:
            lines.append(self._build_detail(row))

        content = '\r\n'.join(lines).encode('latin-1', errors='replace')
        return content, n_records

    # -- Control de Lote Tipo 1  (264 chars) -----------------------------

    def _build_control(self, n_records, total_amount):
        """
        Campo  1: Tipo registro          1  Num  = "1"
        Campo  2: NIT entidad origen    15  Num  ceros izq
        Campo  3: Aplicacion             1  Alfa ' ' (usar config banco)
        Campo  4: Filler                15  Alfa blancos
        Campo  5: Clase transaccion      3  Num  220=Prov / 225=Nom
        Campo  6: Descripcion proposito 10  Alfa
        Campo  7: Fecha transmision      8  Num  AAAAMMDD
        Campo  8: Secuencia lote         2  Alfa 'A1'
        Campo  9: Fecha aplicacion       8  Num  AAAAMMDD
        Campo 10: Numero registros       6  Num
        Campo 11: Sumatoria debitos     17  Num  siempre 0
        Campo 12: Sumatoria creditos    17  Num  (15,2) sin punto
        Campo 13: Cuenta debitar        11  Num  ceros izq
        Campo 14: Tipo cuenta debitar    1  Alfa S=Ahorros D=Corriente C=Contable
        Campo 15: Filler               149  Alfa blancos
        TOTAL: 264
        """
        rec = self.rec
        payment_source = rec.payment_source

        clase = CLASE_NOMINA if payment_source == 'payroll' else CLASE_PROVEEDOR
        nit   = _sanitize_digits(self.company.vat or '', 15)
        fecha = self.today.strftime('%Y%m%d')

        # Cuenta y tipo de cuenta dispersora configurados en la empresa
        disp_account = _sanitize_digits(self.company.l10n_co_dispersal_account or '', 11)
        disp_type = self.company.l10n_co_dispersal_account_type or 'S'

        line  = ''
        line += '1'                               # Campo 1: Tipo (1)
        line += _n(nit, 15)                       # Campo 2: NIT (15)
        line += ' '                               # Campo 3: Aplicacion (1)
        line += ' ' * 15                          # Campo 4: Filler (15)
        line += clase                             # Campo 5: Clase (3)
        line += _x('ODOO', 10)                   # Campo 6: Descripcion (10)
        line += fecha                             # Campo 7: Fecha transmision (8)
        line += 'A1'                              # Campo 8: Secuencia lote (2)
        line += fecha                             # Campo 9: Fecha aplicacion (8)
        line += _n(n_records, 6)                  # Campo 10: Num registros (6)
        line += '0' * 17                          # Campo 11: Sumatoria debitos (17)
        line += _amount_to_str(total_amount, 17)  # Campo 12: Sumatoria creditos (17)
        line += _n(disp_account, 11)              # Campo 13: Cuenta debitar (11)
        line += disp_type                         # Campo 14: Tipo cuenta (1) S/D/C
        line += ' ' * 149                         # Campo 15: Filler (149)

        if len(line) != self.LINE_LEN:
            raise ValueError(f'Control PAB: {len(line)} chars, se esperaban {self.LINE_LEN}')
        return line

    # -- Detalle Tipo 6  (264 chars) -------------------------------------

    def _build_detail(self, row):
        """
        Campo  1: Tipo registro          1  Num  = "6"
        Campo  2: NIT beneficiario      15  Num  alineado izq + espacios der
        Campo  3: Nombre beneficiario   30  Alfa izq + espacios
        Campo  4: Banco destino          9  Num  ceros izq
        Campo  5: Numero cuenta         17  Alfa izq + espacios
        Campo  6: Indicador lugar pago   1  Alfa ' ' (inhabilitado)
        Campo  7: Tipo transaccion       2  Num  27=CC / 37=CA / 52=DE
        Campo  8: Valor transaccion     17  Num  (15,2) sin punto
        Campo  9: Fecha aplicacion       8  Num  AAAAMMDD o ceros
        Campo 10: Referencia            21  Alfa izq + espacios
        Campo 11: Tipo doc ID            1  Num  0=cero si no es ventanilla
        Campo 12: Oficina entrega        5  Alfa '00000'
        Campo 13: Celular               15  Alfa 10 digitos + 5 espacios
        Campo 14: Email                 80  Alfa
        Campo 15: ID autorizado         15  Alfa espacios (solo ventanilla)
        Campo 16: Filler                27  Alfa blancos
        TOTAL: 264
        """
        fecha = self.today.strftime('%Y%m%d')

        # Tipo de transaccion segun tipo de cuenta
        account_type = row.get('account_type', 'CA')
        tx_type = BCOL_TX_TYPE_MAP.get(account_type, TIPO_TX_AHORROS)

        # Banco destino (9 chars, codigo ACH con ceros izquierda)
        banco_destino = _sanitize_digits(row.get('ach_code', ''), 9)

        # Email y celular (opcionales)
        email   = (row.get('email', '') or '')[:80]
        celular = _sanitize_digits(row.get('phone', '') or '', 10)
        celular_field = celular.ljust(15)[:15] if celular else ' ' * 15

        # Referencia (21 chars)
        referencia = _x(row.get('reference', '') or '', 21)

        line  = ''
        line += '6'                                    # Campo 1: Tipo registro (1) = "6"
        # Campo 2: NIT beneficiario (15)
        # PDF: "Alineado a la IZQUIERDA con espacios a la derecha" → alfanumérico
        line += _sanitize_digits(row['vat'], 15).ljust(15)[:15]
        line += _x(row['nombre_completo'], 30)         # Campo 3: Nombre (30) alfa izq
        line += _n(banco_destino, 9)                   # Campo 4: Banco destino (9) num ceros izq
        line += _x(row['account_number'], 17)          # Campo 5: Número cuenta (17) alfa izq
        line += ' '                                    # Campo 6: Indicador lugar (1) = ' '
        line += tx_type                                # Campo 7: Tipo transacción (2)
        line += _amount_to_str(row['amount'], 17)      # Campo 8: Valor (17) (15,2) sin punto
        line += fecha                                  # Campo 9: Fecha aplicación (8) AAAAMMDD
        line += referencia                             # Campo 10: Referencia (21) alfa izq
        line += '0'                                    # Campo 11: Tipo doc ID (1) = '0'
        line += '00000'                                # Campo 12: Oficina entrega (5)
        line += celular_field                          # Campo 13: Celular (15)
        line += _x(email, 80)                         # Campo 14: Email (80) alfa
        line += ' ' * 15                               # Campo 15: ID autorizado (15)
        line += ' ' * 27                               # Campo 16: Filler (27)

        if len(line) != self.LINE_LEN:
            raise ValueError(f'Detalle PAB: {len(line)} chars, se esperaban {self.LINE_LEN}')
        return line

    # -- Recolector de filas -----------------------------------------------

    def _collect_rows(self):
        rows, errors = [], []
        rec = self.rec

        if rec.payment_source in ('vendor', 'both'):
            for pay in rec.payment_ids:
                try:
                    rows.append(self._row_from_payment(pay))
                except ValidationError as exc:
                    errors.append(exc.args[0])

        if rec.payment_source in ('payroll', 'both'):
            for slip in rec.payslip_ids:
                try:
                    rows.append(self._row_from_payslip(slip))
                except ValidationError as exc:
                    errors.append(exc.args[0])

        if errors:
            raise UserError(
                _('No es posible generar el archivo. '
                  'Corrija los siguientes errores:\n\n%s')
                % '\n'.join('- %s' % e for e in errors)
            )
        return rows

    def _row_from_payment(self, payment):
        partner  = payment.partner_id
        bank_acc = payment.partner_bank_id

        if not partner:
            raise ValidationError(
                _('El pago %s no tiene proveedor asignado.') % payment.name
            )
        if not bank_acc:
            raise ValidationError(
                _('El proveedor "%s" no tiene cuenta bancaria en el pago %s.')
                % (partner.name, payment.name)
            )

        vat = _sanitize_digits(partner.vat or '', 15)
        if not vat:
            raise ValidationError(
                _('El proveedor "%s" no tiene NIT/cédula configurado.') % partner.name
            )

        ach_code = (bank_acc.bank_id.l10n_co_ach_code or '').strip()
        if not ach_code:
            raise ValidationError(
                _('El banco del proveedor "%s" no tiene Código ACH. '
                  'Configúrelo en Contabilidad > Bancos.') % partner.name
            )

        acc_number = (bank_acc.acc_number or '').replace(' ', '').replace('-', '')
        if not acc_number:
            raise ValidationError(
                _('La cuenta bancaria de "%s" no tiene número.') % partner.name
            )

        if payment.amount <= 0:
            raise ValidationError(
                _('El pago %s tiene valor cero o negativo.') % payment.name
            )

        cop = payment.env.ref('base.COP', raise_if_not_found=False)
        if cop and payment.currency_id and payment.currency_id != cop:
            raise ValidationError(
                _('El pago %s está en %s. Bancolombia solo acepta COP.')
                % (payment.name, payment.currency_id.name)
            )

        account_type = getattr(bank_acc, 'l10n_co_account_type', 'CA') or 'CA'

        return {
            'vat':            vat,
            'nombre_completo': partner.name or '',
            'ach_code':       ach_code,
            'account_number': acc_number,
            'account_type':   account_type,
            'amount':         round(payment.amount, 2),
            'reference':      payment.name or '',
            'email':          partner.email or '',
            'phone':          partner.phone or '',
        }

    def _row_from_payslip(self, payslip):
        employee = payslip.employee_id
        if not employee:
            raise ValidationError(
                _('El recibo %s no tiene empleado.') % payslip.name
            )
        partner = employee.address_home_id
        if not partner:
            raise ValidationError(
                _('El empleado "%s" no tiene dirección privada.') % employee.name
            )
        bank_acc = employee.bank_account_id
        if not bank_acc:
            raise ValidationError(
                _('El empleado "%s" no tiene cuenta bancaria.') % employee.name
            )

        vat = _sanitize_digits(partner.vat or '', 15)
        if not vat:
            raise ValidationError(
                _('El empleado "%s" no tiene NIT/cédula en su dirección privada.')
                % employee.name
            )

        ach_code = (bank_acc.bank_id.l10n_co_ach_code or '').strip()
        if not ach_code:
            raise ValidationError(
                _('El banco del empleado "%s" no tiene Código ACH.') % employee.name
            )

        acc_number = (bank_acc.acc_number or '').replace(' ', '').replace('-', '')
        if not acc_number:
            raise ValidationError(
                _('La cuenta bancaria del empleado "%s" no tiene número.') % employee.name
            )

        net = round(payslip.net_wage, 2)
        if net <= 0:
            raise ValidationError(
                _('El recibo de "%s" tiene valor neto cero o negativo.') % employee.name
            )

        account_type = getattr(bank_acc, 'l10n_co_account_type', 'CA') or 'CA'

        return {
            'vat':            vat,
            'nombre_completo': employee.name or '',
            'ach_code':       ach_code,
            'account_number': acc_number,
            'account_type':   account_type,
            'amount':         net,
            'reference':      payslip.name or '',
            'email':          partner.email or employee.work_email or '',
            'phone':          partner.mobile or partner.phone or '',
        }


# ---------------------------------------------------------------------------
# Generador SAP  (95 chars/linea)
# ---------------------------------------------------------------------------

class BancolombiaGeneratorSAP:
    """
    Genera archivos en formato SAP (Sistema de Aplicacion de Pagos).
    Longitud de registro: 95 caracteres.
    Formato legacy, soportado por compatibilidad.
    """

    LINE_LEN = 95

    def __init__(self, export_record):
        self.rec = export_record
        self.company = export_record.company_id
        self.today = fields.Date.today()

    def generate(self):
        if not self.company.l10n_co_dispersal_account:
            raise UserError(_(
                'Configure la cuenta dispersora de la empresa antes de generar '
                'el archivo de Bancolombia. '
                'Vaya a Configuracion > Empresas > pestana "Pagos Colombia".'
            ))
        rows = self._collect_rows()
        if not rows:
            raise UserError(_('No se encontraron registros válidos para exportar.'))

        total_amount = sum(r['amount'] for r in rows)
        n_records = len(rows)

        lines = []
        lines.append(self._build_control(n_records, total_amount))
        for row in rows:
            lines.append(self._build_detail(row))

        content = '\r\n'.join(lines).encode('latin-1', errors='replace')
        return content, n_records

    def _build_control(self, n_records, total_amount):
        """
        Campo  1: Tipo registro           1  Num  = "1"
        Campo  2: NIT entidad            10  Num  ceros izq
        Campo  3: Nombre entidad         16  Alfa izq + espacios
        Campo  4: Clase transacciones     3  Num
        Campo  5: Descripcion proposito  10  Alfa
        Campo  6: Fecha transmision       6  Num  AAMMDD
        Campo  7: Secuencia lote          1  Alfa 'A'
        Campo  8: Fecha aplicacion        6  Num  AAMMDD
        Campo  9: Num registros           6  Num
        Campo 10: Sumatoria debitos      12  Num  siempre 0
        Campo 11: Sumatoria creditos     12  Num
        Campo 12: Cuenta debitar         11  Num
        Campo 13: Tipo cuenta             1  Alfa S/D
        TOTAL: 95
        """
        payment_source = self.rec.payment_source
        clase = CLASE_NOMINA if payment_source == 'payroll' else CLASE_PROVEEDOR
        nit   = _sanitize_digits(self.company.vat or '', 10)
        fecha = self.today.strftime('%y%m%d')  # AAMMDD — 6 chars

        # Cuenta y tipo de cuenta dispersora configurados en la empresa
        disp_account = _sanitize_digits(self.company.l10n_co_dispersal_account or '', 11)
        disp_type = self.company.l10n_co_dispersal_account_type or 'S'

        line  = ''
        line += '1'                                      # Campo 1 (1)
        line += _n(nit, 10)                              # Campo 2 (10)
        line += _x(self.company.name or '', 16)          # Campo 3 (16)
        line += clase                                    # Campo 4 (3)
        line += _x('ODOO', 10)                           # Campo 5 (10)
        line += fecha                                    # Campo 6 (6)
        line += 'A'                                      # Campo 7 (1)
        line += fecha                                    # Campo 8 (6)
        line += _n(n_records, 6)                         # Campo 9 (6)
        line += '0' * 12                                 # Campo 10 (12)
        line += _amount_to_str_sap(total_amount, 12)     # Campo 11 (12)
        line += _n(disp_account, 11)                     # Campo 12 (11)
        line += disp_type                                # Campo 13 (1) S/D/C

        if len(line) != self.LINE_LEN:
            raise ValueError(f'Control SAP: {len(line)} chars, se esperaban {self.LINE_LEN}')
        return line

    def _build_detail(self, row):
        """
        Campo  1: Tipo registro           1  Num  = "6"
        Campo  2: ID beneficiario        15  Num  ceros izq
        Campo  3: Nombre beneficiario    18  Alfa izq + espacios
        Campo  4: Banco destino           9  Num  ceros izq
        Campo  5: Numero cuenta          17  Num  ceros izq
        Campo  6: Indicador lugar pago    1  Alfa ' '
        Campo  7: Tipo transaccion        2  Num
        Campo  8: Valor transaccion      10  Num
        Campo  9: Concepto                9  Alfa
        Campo 10: Referencia             12  Alfa
        Campo 11: Relleno                 1  Alfa ' '
        TOTAL: 95
        """
        account_type = row.get('account_type', 'CA')
        tx_type = BCOL_TX_TYPE_MAP.get(account_type, TIPO_TX_AHORROS)
        banco_destino = _sanitize_digits(row.get('ach_code', ''), 9)

        line  = ''
        line += '6'                                         # Campo 1 (1)
        line += _n(row['vat'], 15)                          # Campo 2 (15)
        line += _x(row['nombre_completo'], 18)              # Campo 3 (18)
        line += _n(banco_destino, 9)                        # Campo 4 (9)
        line += _n(_sanitize_digits(row['account_number']), 17)  # Campo 5 (17)
        line += ' '                                         # Campo 6 (1)
        line += tx_type                                     # Campo 7 (2)
        line += _amount_to_str_sap(row['amount'], 10)       # Campo 8 (10)
        line += ' ' * 9                                     # Campo 9 concepto (9)
        line += _x(row.get('reference', ''), 12)            # Campo 10 (12)
        line += ' '                                         # Campo 11 relleno (1)

        if len(line) != self.LINE_LEN:
            raise ValueError(f'Detalle SAP: {len(line)} chars, se esperaban {self.LINE_LEN}')
        return line

    def _collect_rows(self):
        # Reutiliza el mismo recolector que PAB
        return BancolombiaGeneratorPAB(self.rec)._collect_rows()
