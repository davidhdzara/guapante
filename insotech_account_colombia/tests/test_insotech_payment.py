from odoo.tests.common import TransactionCase

class TestInsotechPayment(TransactionCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Setup basic data for tests
        cls.env = cls.env
        cls.company = cls.env.user.company_id
        
        # Create a test account
        cls.account = cls.env['account.account'].create({
            'name': 'Test Account 1355',
            'code': '135599',
            'account_type': 'asset_current',
            'company_id': cls.company.id,
        })
        
        # Create a retention concept
        cls.retention_concept = cls.env['insotech.retention.concept'].create({
            'name': 'Test RteFte 11%',
            'type': 'fuente',
            'direction': 'both',
            'percentage': 11.0,
            'base_uvt': 0.0,
            'account_id': cls.account.id,
            'active': True,
        })

    def test_payment_register_initialization(self) -> None:
        """Prueba básica para asegurar que el modelo temporal se inicializa correctamente."""
        # Se verifica que el modelo existe y se puede instanciar sin error
        payment_register = self.env['account.payment.register'].create({
            'amount': 1000.0,
            'payment_date': '2026-01-01',
            'payment_method_line_id': self.env.ref('account.account_payment_method_manual_in').id,
        })
        
        # Agregar una línea de retención InSoTech
        retention_line = self.env['insotech.payment.retention.line'].create({
            'payment_register_id': payment_register.id,
            'retention_concept_id': self.retention_concept.id,
            'amount': 110.0,
        })
        
        self.assertEqual(len(payment_register.insotech_retention_line_ids), 1)
        self.assertEqual(payment_register.insotech_total_retentions, 110.0)
