from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestInsotechRetentions(TransactionCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.uvt_model = cls.env['insotech.uvt']
        cls.concept_model = cls.env['insotech.retention.concept']
        
        # Obtenemos la compañía y configuramos un entorno básico
        cls.company = cls.env.company
        
        # Aseguramos que haya una cuenta contable disponible
        cls.test_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.id),
            ('deprecated', '=', False)
        ], limit=1)
        
        if not cls.test_account:
            # Si no hay cuentas, la creamos para el test (comportamiento aislado)
            cls.test_account = cls.env['account.account'].create({
                'code': '135599',
                'name': 'Cuenta Test Retenciones',
                'account_type': 'asset_current',
                'company_ids': [(4, cls.company.id)],
            })

        # Creamos una UVT de prueba
        cls.uvt_2026 = cls.uvt_model.create({
            'year': 2026,
            'value': 52374.0,
        })

    def test_01_uvt_creation_and_compute(self) -> None:
        """Prueba la correcta creación de una UVT y su nombre computado."""
        self.assertEqual(self.uvt_2026.name, 'UVT 2026')
        self.assertEqual(self.uvt_2026.value, 52374.0)

    def test_02_uvt_unique_constraint(self) -> None:
        """Prueba que no se puedan crear dos UVTs para el mismo año."""
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.uvt_model.create({
                    'year': 2026,
                    'value': 55000.0,
                })

    def test_03_concept_creation(self) -> None:
        """Prueba la creación de un concepto de retención básico."""
        concept = self.concept_model.create({
            'name': 'Test Retención Agrícola',
            'type': 'retefuente',
            'base_uvt': 70.0,
            'percentage': 1.5,
            'account_id': self.test_account.id,
        })
        self.assertTrue(concept.id)
        self.assertEqual(concept.percentage, 1.5)
        self.assertEqual(concept.type, 'retefuente')
