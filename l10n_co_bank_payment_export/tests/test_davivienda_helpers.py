"""
Tests unitarios para las funciones helpers del modulo.
Estas funciones son puras (sin ORM) y se pueden testear sin base de datos.
"""
from odoo.tests import TransactionCase
from odoo.addons.l10n_co_bank_payment_export.models.bank_payment_export import (
    _sanitize,
    _only_digits,
)


class TestDaviviendaHelpers(TransactionCase):

    # -- _sanitize -----------------------------------------------------------

    def test_sanitize_removes_accents(self):
        self.assertEqual(_sanitize('Peña'), 'Pena')
        self.assertEqual(_sanitize('María'), 'Maria')
        self.assertEqual(_sanitize('José'), 'Jose')

    def test_sanitize_removes_special_chars(self):
        self.assertEqual(_sanitize('Empresa & Cia'), 'Empresa  Cia')
        self.assertEqual(_sanitize('S.A.S.'), 'S A S ')
        # El resultado colapsa espacios multiples
        result = _sanitize('A  B')
        self.assertEqual(result, 'A B')

    def test_sanitize_respects_max_len(self):
        long_text = 'A' * 100
        self.assertEqual(len(_sanitize(long_text, max_len=40)), 40)

    def test_sanitize_empty_returns_empty(self):
        self.assertEqual(_sanitize(''), '')
        self.assertEqual(_sanitize(None), '')
        self.assertEqual(_sanitize(False), '')

    def test_sanitize_collapses_spaces(self):
        self.assertEqual(_sanitize('  Juan   Pablo  '), 'Juan Pablo')

    # -- _only_digits --------------------------------------------------------

    def test_only_digits_extracts_correctly(self):
        self.assertEqual(_only_digits('900123456-1'), '9001234561')
        self.assertEqual(_only_digits('EXP/2024/0001'), '20240001')

    def test_only_digits_respects_max_len(self):
        self.assertEqual(_only_digits('12345678901234567890', max_len=16), '1234567890123456')

    def test_only_digits_empty(self):
        self.assertEqual(_only_digits(''), '')
        self.assertEqual(_only_digits(None), '')

    def test_only_digits_preserves_leading_zeros(self):
        # Critico: numeros de cuenta pueden empezar en cero
        self.assertEqual(_only_digits('00430012345'), '00430012345')
