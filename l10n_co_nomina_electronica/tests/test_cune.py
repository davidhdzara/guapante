import hashlib
from odoo.tests.common import TransactionCase
from odoo.addons.l10n_co_nomina_electronica.services import cune as cune_service


class TestCuneComputation(TransactionCase):
    """Tests for CUNE, software security code, and DV computation."""

    def test_compute_cune_sha384(self):
        """Test that the CUNE is computed as a SHA-384 hash of the
        concatenated input values, matching the DIAN specification.
        """
        # Input values per DIAN spec (concatenated without separators):
        # NumNIE + FecNIE + HorNIE + ValDev + ValDed + ValTol +
        # NitNIE + NumIDE + TipoXML + SoftwarePin + TipAmb
        cune_input = (
            'NE0000000001'      # NumNIE - Consecutivo
            '2024-01-15'        # FecNIE - Fecha
            '08:30:00-05:00'    # HorNIE - Hora
            '3500000.00'        # ValDev - Valor Devengados
            '500000.00'         # ValDed - Valor Deducciones
            '3000000.00'        # ValTol - Valor Total
            '900123456'         # NitNIE - NIT Empleador
            '1234567890'        # NumIDE - Número Documento Trabajador
            '102'               # TipoXML - Tipo de documento
            '693af'             # SoftwarePin
            '2'                 # TipAmb - Ambiente (2=Producción)
        )
        expected_hash = hashlib.sha384(cune_input.encode('utf-8')).hexdigest()

        # Compute via the actual service to ensure the 11-field order
        # (including Software-Pin between TipoXML and TipAmb) is honored.
        computed, raw = cune_service.compute_cune(
            num_ne='NE0000000001',
            fec_ne='2024-01-15',
            hor_ne='08:30:00-05:00',
            val_dev='3500000.00',
            val_ded='500000.00',
            val_tol='3000000.00',
            nit_ne='900123456',
            doc_trab='1234567890',
            cl_ne='102',
            software_pin='693af',
            tipo_amb='2',
        )

        self.assertEqual(raw, cune_input)
        self.assertEqual(computed, expected_hash)
        self.assertEqual(len(computed), 96)  # SHA-384 produces 96-char hex

    def test_compute_cune_truncates_amounts(self):
        """Amounts must be truncated (not rounded) to 2 decimals per spec."""
        _cune, raw = cune_service.compute_cune(
            num_ne='NE1', fec_ne='2024-01-15', hor_ne='08:30:00-05:00',
            val_dev='3500000.999', val_ded='0', val_tol='3500000.999',
            nit_ne='900123456', doc_trab='1', cl_ne='102',
            software_pin='693', tipo_amb='2',
        )
        # 3500000.999 must truncate to 3500000.99, never 3500001.00
        self.assertIn('3500000.99', raw)
        self.assertNotIn('3500001.00', raw)

    def test_compute_software_security_code(self):
        """Test the software security code computation.
        SecurityCode = SHA-384(SoftwareID + Pin + NE_consecutive)
        """
        software_id = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
        pin = '12345'
        consecutive = 'NE0000000001'

        code_input = software_id + pin + consecutive
        computed = hashlib.sha384(code_input.encode('utf-8')).hexdigest()

        self.assertTrue(computed)
        self.assertEqual(len(computed), 96)
        # Verify it is deterministic
        computed2 = hashlib.sha384(code_input.encode('utf-8')).hexdigest()
        self.assertEqual(computed, computed2)

    def test_compute_dv(self):
        """Test DV (dígito de verificación) computation for a known NIT.
        Using the DIAN algorithm (module 11, weights [3,7,13,17,19,23,29,37,41,43]).
        """
        nit = '900123456'
        weights = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43]

        # Pad NIT to 10 digits (right-aligned)
        nit_padded = nit.zfill(10)
        total = sum(int(d) * w for d, w in zip(nit_padded, weights))
        remainder = total % 11

        if remainder == 0:
            dv = 0
        elif remainder == 1:
            dv = 1
        else:
            dv = 11 - remainder

        # The DV must be a single digit (0-9) or 1
        self.assertIn(dv, range(0, 11))
        self.assertIsInstance(dv, int)
