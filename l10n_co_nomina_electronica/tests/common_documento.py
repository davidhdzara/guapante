# -*- coding: utf-8 -*-
"""Fixture compartido de las pruebas del documento mensual (no es un archivo de pruebas: no empieza por test_)."""

from datetime import date
from unittest.mock import patch

from odoo.addons.l10n_co_nomina_electronica.services import dian_utils


# Acciones planificadas de la cola de envío y de las reconsultas. En producción se PAUSAN a propósito (David, 17-nov-2026: ids 76, 77 y 78
# ``active = False``) y la regresión corre sobre una COPIA de esa base: las pruebas del documento mensual no pueden depender de ese estado.
CRONES_DE_ENVIO = ('ir_cron_ne_documento_send', 'ir_cron_ne_documento_recheck', 'ir_cron_ne_dian_status_recheck')


def activar_crons_de_envio(env):
    """Activa, DENTRO de la transacción de la prueba, las acciones planificadas de envío y reconsulta del módulo. El cambio se deshace con el
    rollback de la prueba: no toca la base ni dispara nada (el aviso al worker es posterior al commit, que una prueba nunca hace). Las pruebas
    que necesitan el cron ARCHIVADO (``test_cron_archivado_*``) lo apagan ellas mismas dentro de la prueba."""
    for nombre in CRONES_DE_ENVIO:
        env.ref('l10n_co_nomina_electronica.%s' % nombre).sudo().write({'active': True})


class DocumentoFixture:
    """Mixin para TransactionCase: crea una compañía colombiana y documentos con recibos pagados."""

    @classmethod
    def _fixture_documento(cls, nombre):
        activar_crons_de_envio(cls.env)
        cls.company = cls.env['res.company'].create({
            'name': nombre, 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_fuente_fecha_pago': 'recibo', 'l10n_co_ne_payroll_prefix': 'NE'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Estructura %s' % nombre, 'country_id': cls.env.ref('base.co').id})
        cls.struct = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.n = 0

    def _documento(self, ingreso, retiro=None, mes=3, pagos=((15, 15), (31, 31))):
        """Documento de ``mes`` de 2026 con un recibo por cada (dia de fin, dia de pago)."""
        propietario = self if isinstance(self, type) else type(self)    # acepta la clase (setUpClass) o la instancia
        propietario.n += 1
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado Doc %s' % self.n, 'company_id': self.company.id, 'identification_id': '1020304050',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato Doc %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.structure_type.id, 'l10n_co_ne_contract_type': '2',
            'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': ingreso, 'date_end': retiro, 'state': 'open'})
        doc = self.env['l10n.co.ne.documento'].create({
            'company_id': self.company.id, 'employee_id': empleado.id, 'contract_id': contrato.id,
            'period': date(2026, mes, 1)})
        for fin, pago in pagos:
            slip = self.env['hr.payslip'].create({
                'name': 'Recibo Doc', 'employee_id': empleado.id, 'contract_id': contrato.id,
                'company_id': self.company.id, 'struct_id': self.struct.id,
                'date_from': date(2026, mes, 1 if fin <= 15 else 16), 'date_to': date(2026, mes, fin)})
            slip.write({'state': 'paid', 'paid_date': date(2026, mes, pago), 'l10n_co_ne_documento_id': doc.id})
        return doc

    def _patch(self, objetivo, atributo, valor):
        patcher = patch.object(objetivo, atributo, valor)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch_recibos(self, fabrica):
        """Los datos por recibo salen de ``fabrica()`` (la forma de _collect_payslip_data) y SoftwareSC se simplifica."""
        self._patch(type(self.env['hr.payslip']), '_collect_payslip_data', lambda s: fabrica())
        self._patch(dian_utils, 'compute_software_security_code', lambda *a: 'SC')
