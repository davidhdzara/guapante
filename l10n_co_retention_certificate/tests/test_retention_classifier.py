# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestRetentionClassifier(TransactionCase):
    """Pruebas del clasificador de account.tax -> l10n_co_retention_type.

    Ver ESPEC §4 Fase 1 para la justificación de cada regla y el orden
    en que deben evaluarse.

    Nota: estas pruebas corren tanto en una base de datos vacía (CI)
    como en clones de la base de datos real de Guapante (staging_dev),
    donde ya existen cuentas PUC e impuestos con nombres reales que
    coinciden con los que usa esta suite como ejemplo. Por eso:
    - las cuentas se obtienen con get-or-create (_get_or_create_account),
      no con create() directo, para no chocar con códigos ya usados;
    - todos los nombres de impuesto de prueba llevan el prefijo 'TEST '
      para no chocar con la restricción de nombre único por compañía.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

    def _get_or_create_account(self, code, account_type='liability_current'):
        account = self.env['account.account'].search([
            ('code', '=', code),
            ('company_ids', 'in', self.company.id),
        ], limit=1)
        if account:
            return account
        return self.env['account.account'].create({
            'name': 'Test Account %s' % code,
            'code': code,
            'account_type': account_type,
            'company_ids': [(6, 0, [self.company.id])],
        })

    def _create_purchase_tax(self, name, amount=-3.5, account=None):
        repartition_lines = [(0, 0, {'factor_percent': 100, 'repartition_type': 'base'})]
        repartition_lines.append((0, 0, {
            'factor_percent': 100,
            'repartition_type': 'tax',
            'account_id': account.id if account else False,
        }))
        return self.env['account.tax'].create({
            'name': 'TEST %s' % name,
            'amount_type': 'percent',
            'amount': amount,
            'type_tax_use': 'purchase',
            'company_id': self.company.id,
            'invoice_repartition_line_ids': repartition_lines,
        })

    # ------------------------------------------------------------------
    # Regla 2 — prefijo de cuenta PUC (caso de los impuestos nativos de
    # l10n_co, que no tienen concepto InSoTech vinculado).
    # ------------------------------------------------------------------

    def test_rule2_account_prefix_retefuente(self):
        account = self._get_or_create_account('23651517')
        tax = self._create_purchase_tax('RteFte General (1%)', amount=-1.0, account=account)
        tax._l10n_co_compute_retention_type()
        self.assertEqual(tax.l10n_co_retention_type, 'retefuente')

    def test_rule2_account_prefix_reteiva(self):
        account = self._get_or_create_account('236700')
        tax = self._create_purchase_tax('15% RteVAT 19%', amount=-2.85, account=account)
        tax._l10n_co_compute_retention_type()
        self.assertEqual(tax.l10n_co_retention_type, 'reteiva')

    def test_rule2_account_prefix_reteica(self):
        account = self._get_or_create_account('236800')
        tax = self._create_purchase_tax('0.966% RteICA', amount=-0.966, account=account)
        tax._l10n_co_compute_retention_type()
        self.assertEqual(tax.l10n_co_retention_type, 'reteica')

    def test_rule2_account_prefix_parafiscal(self):
        account = self._get_or_create_account('24601001')
        tax = self._create_purchase_tax('1% CFH Asohofrucol', amount=-1.0, account=account)
        tax._l10n_co_compute_retention_type()
        self.assertEqual(tax.l10n_co_retention_type, 'parafiscal')

    # ------------------------------------------------------------------
    # Regla 1 — el concepto InSoTech debe ganarle a la Regla 2 cuando
    # ambas aplican. Este es el caso real de Guapante: los impuestos
    # RteICA del motor InSoTech usan cuentas 2365xx, que por prefijo
    # (Regla 2) clasificarían como 'retefuente' — incorrecto.
    # ------------------------------------------------------------------

    def test_rule1_insotech_concept_overrides_account_prefix(self):
        if 'insotech.retention.concept' not in self.env:
            self.skipTest(
                'insotech_account_colombia no está instalado en este entorno de test'
            )

        account = self._get_or_create_account('23652501')
        tax = self._create_purchase_tax(
            'RteICA Comercio Bogotá (9.66x1000)', amount=-0.966, account=account
        )

        self.env['insotech.retention.concept'].create({
            'name': tax.name,
            'type': 'reteica',
            'direction': 'purchase',
            'percentage': 0.966,
            'purchase_account_id': account.id,
            'purchase_tax_id': tax.id,
        })

        tax._l10n_co_compute_retention_type()
        self.assertEqual(
            tax.l10n_co_retention_type, 'reteica',
            'La Regla 1 (concepto InSoTech) debe ganarle a la Regla 2 '
            '(prefijo de cuenta), que por sí sola clasificaría este '
            'impuesto como retefuente por estar en cuenta 2365xx.'
        )

    # ------------------------------------------------------------------
    # Regla 3 — patrón en el nombre, cuando no hay cuenta de repartición
    # o la cuenta no coincide con ningún prefijo conocido.
    # ------------------------------------------------------------------

    def test_rule3_name_pattern_parafiscal(self):
        tax = self._create_purchase_tax('Rte Paraf Fedepapa', amount=-1.0, account=None)
        tax._l10n_co_compute_retention_type()
        self.assertEqual(tax.l10n_co_retention_type, 'parafiscal')

    def test_rule3_name_pattern_reteica(self):
        tax = self._create_purchase_tax('Retención ICA Sin Cuenta', amount=-1.0, account=None)
        tax._l10n_co_compute_retention_type()
        self.assertEqual(tax.l10n_co_retention_type, 'reteica')

    def test_rule3_name_pattern_reteiva(self):
        tax = self._create_purchase_tax('15% RteVAT 19%', amount=-2.85, account=None)
        tax._l10n_co_compute_retention_type()
        self.assertEqual(tax.l10n_co_retention_type, 'reteiva')

    def test_rule3_name_pattern_retefuente(self):
        tax = self._create_purchase_tax('Retención en la Fuente Genérica', amount=-1.0, account=None)
        tax._l10n_co_compute_retention_type()
        self.assertEqual(
            tax.l10n_co_retention_type, 'retefuente',
            'Bug encontrado en staging_dev 2026-07-29: "Genérica" no debe '
            'clasificarse como reteica solo porque contiene la subcadena '
            '"ica" en minúsculas.'
        )

    # ------------------------------------------------------------------
    # Regla 4 — sin clasificar cuando nada aplica.
    # ------------------------------------------------------------------

    def test_rule4_unclassified_when_nothing_matches(self):
        tax = self._create_purchase_tax('Descuento Comercial', amount=-1.0, account=None)
        tax._l10n_co_compute_retention_type()
        self.assertFalse(tax.l10n_co_retention_type)

    # ------------------------------------------------------------------
    # Alcance — solo impuestos de compra con amount < 0.
    # ------------------------------------------------------------------

    def test_scope_sale_tax_is_never_classified(self):
        account = self._get_or_create_account('13551517')
        tax = self.env['account.tax'].create({
            'name': 'TEST RteFte General (1%) Ventas',
            'amount_type': 'percent',
            'amount': -1.0,
            'type_tax_use': 'sale',
            'company_id': self.company.id,
            'invoice_repartition_line_ids': [
                (0, 0, {'factor_percent': 100, 'repartition_type': 'base'}),
                (0, 0, {'factor_percent': 100, 'repartition_type': 'tax', 'account_id': account.id}),
            ],
        })
        tax._l10n_co_compute_retention_type()
        self.assertFalse(tax.l10n_co_retention_type)

    def test_scope_positive_amount_is_never_classified(self):
        account = self._get_or_create_account('23651517')
        tax = self._create_purchase_tax('RteFte Positivo (error de captura)', amount=1.0, account=account)
        tax._l10n_co_compute_retention_type()
        self.assertFalse(tax.l10n_co_retention_type)
