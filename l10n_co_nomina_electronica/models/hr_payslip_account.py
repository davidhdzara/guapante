# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.payslip para contabilización automática de nómina.

Al confirmar una nómina (action_payslip_done), se genera automáticamente un
asiento contable (account.move) con las líneas correspondientes a cada regla
salarial que tenga configuración contable en l10n.co.payroll.account.config.

Las líneas del asiento se agrupan por cuenta contable para mayor eficiencia
y claridad en la contabilidad. El asiento se publica automáticamente.

Al cancelar una nómina (action_payslip_cancel), se reversa o elimina el
asiento contable asociado.
"""

import logging
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrPayslipAccount(models.Model):
    """Extensión de hr.payslip con integración contable automática."""

    _inherit = 'hr.payslip'

    # ──────────────────────────────────────────────────────────────────
    # Campos contables
    # ──────────────────────────────────────────────────────────────────
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Asiento Contable',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='Asiento contable generado automaticamente al confirmar '
             'la nomina. Contiene las partidas de debito y credito '
             'segun la configuracion de cuentas contables.',
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario Contable',
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        help='Diario contable donde se registrara el asiento de nomina. '
             'Si no se selecciona, se buscara un diario de tipo general '
             'con nombre "Nomina" o se usara el primer diario general disponible.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Override: confirmar nómina -> crear asiento contable
    # ──────────────────────────────────────────────────────────────────
    def action_payslip_done(self):
        """Confirma la nómina. El asiento contable se genera automáticamente
        dentro de la llamada super().action_payslip_done() a través de _create_account_move.
        """
        return super().action_payslip_done()


    # ──────────────────────────────────────────────────────────────────
    # Override: cancelar nómina -> reversar/eliminar asiento
    # ──────────────────────────────────────────────────────────────────
    def action_payslip_cancel(self):
        """Cancela la nómina y reversa o elimina el asiento contable.

        Si el asiento está publicado, se reversa creando un contra-asiento.
        Si el asiento está en borrador, se elimina directamente.
        """
        for payslip in self:
            if payslip.move_id:
                payslip._reverse_account_move()
        return super().action_payslip_cancel()

    # ══════════════════════════════════════════════════════════════════
    # MÉTODOS DE CONTABILIZACIÓN
    # ══════════════════════════════════════════════════════════════════

    def _create_account_move(self, *args, **kwargs):

        """Crea el asiento contable a partir de las líneas de la nómina.

        Flujo:
        1. Obtiene o busca el diario contable de nómina.
        2. Lee las líneas de la nómina con monto != 0.
        3. Para cada línea, busca la configuración contable de la regla.
        4. Agrupa las líneas por cuenta contable (débito y crédito).
        5. Crea el account.move con las líneas agrupadas.
        6. Publica el asiento automáticamente.

        Si no hay líneas con configuración contable, no se crea asiento.
        """
        self.ensure_one()

        # Si ya tiene asiento, no crear otro
        if self.move_id:
            _logger.info(
                'La nomina %s ya tiene asiento contable %s, se omite la creacion.',
                self.number or self.name,
                self.move_id.name,
            )
            return self.move_id

        # Obtener diario contable
        journal = self._get_payroll_journal()
        if not journal:
            _logger.warning(
                'No se encontro diario contable para la nomina %s. '
                'No se creara asiento contable.',
                self.number or self.name,
            )
            return self.env['account.move']

        # Recopilar líneas contables agrupadas
        move_lines_data = self._prepare_account_move_lines()
        if not move_lines_data:
            _logger.info(
                'No hay lineas con configuracion contable para la nomina %s. '
                'No se creara asiento contable.',
                self.number or self.name,
            )
            return self.env['account.move']

        # Construir referencia del asiento
        ref = _('Nomina: %s - %s') % (
            self.number or self.name,
            self.employee_id.name or '',
        )

        # Crear el asiento contable
        move_vals = {
            'journal_id': journal.id,
            'date': self.date_to or fields.Date.context_today(self),
            'ref': ref,
            'company_id': self.company_id.id,
            'move_type': 'entry',
            'line_ids': [(0, 0, line) for line in move_lines_data],
        }

        move = self.env['account.move'].sudo().create(move_vals)
        self.move_id = move

        # Publicar el asiento automáticamente
        try:
            move.action_post()
            _logger.info(
                'Asiento contable %s creado y publicado para nomina %s '
                '(total lineas: %d).',
                move.name,
                self.number or self.name,
                len(move_lines_data),
            )
        except Exception as e:
            _logger.warning(
                'Asiento contable %s creado pero no se pudo publicar '
                'para nomina %s: %s',
                move.name,
                self.number or self.name,
                str(e),
            )
        return move


    def _prepare_account_move_lines(self):
        """Prepara las líneas del asiento contable agrupadas por cuenta.

        Recorre las líneas de la nómina, busca la configuración contable
        de cada regla salarial, y agrupa los montos por cuenta contable
        para generar líneas consolidadas.

        Returns:
            list[dict]: Lista de diccionarios con los datos de cada línea
                        del asiento contable (account.move.line).
                        Retorna lista vacía si no hay líneas configuradas.
        """
        self.ensure_one()

        AccountConfig = self.env['l10n.co.payroll.account.config']

        # Estructura para agrupar: {(account_id, analytic_id): amount}
        # Débitos con montos positivos, créditos con montos negativos
        grouped_lines = defaultdict(lambda: {
            'debit': 0.0,
            'credit': 0.0,
            'name': [],
            'analytic_distribution': False,
        })

        for line in self.line_ids:
            # Omitir líneas con monto cero
            if not line.total:
                continue

            # Buscar configuración contable para esta regla
            accounts = AccountConfig.get_accounts_for_rule(
                line.salary_rule_id.id,
                self.company_id.id,
            )
            if not accounts:
                # Sin configuración contable: omitir silenciosamente
                continue

            amount = abs(line.total)
            debit_account = accounts['debit_account_id']
            credit_account = accounts['credit_account_id']
            analytic_account_id = accounts.get('analytic_account_id', False)

            # Preparar distribución analítica si existe
            analytic_dist = False
            if analytic_account_id:
                analytic_dist = {str(analytic_account_id): 100.0}

            # Línea de débito
            debit_key = ('debit', debit_account, analytic_account_id or 0)
            grouped_lines[debit_key]['debit'] += amount
            grouped_lines[debit_key]['name'].append(line.name or line.salary_rule_id.name)
            if analytic_dist:
                grouped_lines[debit_key]['analytic_distribution'] = analytic_dist

            # Línea de crédito
            credit_key = ('credit', credit_account, analytic_account_id or 0)
            grouped_lines[credit_key]['credit'] += amount
            grouped_lines[credit_key]['name'].append(line.name or line.salary_rule_id.name)
            if analytic_dist:
                grouped_lines[credit_key]['analytic_distribution'] = analytic_dist

        if not grouped_lines:
            return []

        # Construir las líneas del asiento
        move_lines = []
        for key, data in grouped_lines.items():
            side, account_id, _analytic = key

            # Nombre consolidado (primeros 3 conceptos + "y N mas")
            names = list(set(data['name']))
            if len(names) > 3:
                label = ', '.join(names[:3]) + _(' y %d mas') % (len(names) - 3)
            else:
                label = ', '.join(names)

            line_vals = {
                'account_id': account_id,
                'name': label,
                'debit': round(data['debit'], 2) if side == 'debit' else 0.0,
                'credit': round(data['credit'], 2) if side == 'credit' else 0.0,
            }

            # Agregar distribución analítica si existe
            if data['analytic_distribution']:
                line_vals['analytic_distribution'] = data['analytic_distribution']

            move_lines.append(line_vals)

        # Verificar que el asiento esté balanceado (débito == crédito)
        total_debit = sum(l['debit'] for l in move_lines)
        total_credit = sum(l['credit'] for l in move_lines)
        diff = round(total_debit - total_credit, 2)
        if diff != 0.0:
            _logger.warning(
                'Asiento desbalanceado para nomina %s: '
                'debito=%.2f, credito=%.2f, diferencia=%.2f. '
                'Se ajustara la ultima linea de credito.',
                self.number or self.name,
                total_debit,
                total_credit,
                diff,
            )
            # Ajustar la última línea de crédito para balancear
            for line_vals in reversed(move_lines):
                if line_vals['credit'] > 0:
                    line_vals['credit'] = round(line_vals['credit'] + diff, 2)
                    break

        return move_lines

    def _get_payroll_journal(self):
        """Obtiene el diario contable para la nómina.

        Orden de búsqueda:
        1. El diario seleccionado en el campo journal_id de la nómina.
        2. Un diario tipo 'general' con nombre 'Nomina' en la compañía.
        3. El primer diario tipo 'general' disponible en la compañía.

        Returns:
            account.journal: Diario contable encontrado, o False si no hay ninguno.
        """
        self.ensure_one()

        # 1. Diario seleccionado en la nómina
        if self.journal_id:
            return self.journal_id

        Journal = self.env['account.journal']
        company_id = self.company_id.id

        # 2. Buscar diario "Nomina" de tipo general
        journal = Journal.search([
            ('type', '=', 'general'),
            ('company_id', '=', company_id),
            ('name', 'ilike', 'Nomina'),
        ], limit=1)
        if journal:
            return journal

        # 3. Buscar diario "Nómina" (con tilde) de tipo general
        journal = Journal.search([
            ('type', '=', 'general'),
            ('company_id', '=', company_id),
            ('name', 'ilike', 'Nómina'),
        ], limit=1)
        if journal:
            return journal

        # 4. Primer diario general disponible
        journal = Journal.search([
            ('type', '=', 'general'),
            ('company_id', '=', company_id),
        ], limit=1)
        if journal:
            _logger.info(
                'Usando diario general "%s" como diario de nomina '
                'para la compania %s (no se encontro diario "Nomina").',
                journal.name,
                self.company_id.name,
            )
            return journal

        return False

    def _reverse_account_move(self):
        """Reversa o elimina el asiento contable asociado a la nómina.

        Si el asiento está publicado, se reversa creando un contra-asiento.
        Si el asiento está en borrador, se elimina directamente.
        """
        self.ensure_one()
        move = self.move_id
        if not move:
            return

        move_name = move.name

        if move.state == 'posted':
            # Reversar asiento publicado
            try:
                reversal_move = move._reverse_moves(
                    default_values_list=[{
                        'ref': _('Reverso: %s - Cancelacion nomina %s') % (
                            move_name,
                            self.number or self.name,
                        ),
                        'date': fields.Date.context_today(self),
                    }],
                    cancel=True,
                )
                _logger.info(
                    'Asiento contable %s reversado para nomina %s. '
                    'Asiento de reverso: %s',
                    move_name,
                    self.number or self.name,
                    reversal_move.name if reversal_move else 'N/A',
                )
            except Exception as e:
                _logger.error(
                    'Error al reversar asiento %s de nomina %s: %s',
                    move_name,
                    self.number or self.name,
                    str(e),
                )
                raise UserError(_(
                    'No se pudo reversar el asiento contable %s: %s',
                    move_name,
                    str(e),
                ))
        else:
            # Eliminar asiento en borrador
            try:
                move.unlink()
                _logger.info(
                    'Asiento contable %s (borrador) eliminado para nomina %s.',
                    move_name,
                    self.number or self.name,
                )
            except Exception as e:
                _logger.error(
                    'Error al eliminar asiento %s de nomina %s: %s',
                    move_name,
                    self.number or self.name,
                    str(e),
                )

        # Limpiar referencia al asiento
        self.move_id = False
