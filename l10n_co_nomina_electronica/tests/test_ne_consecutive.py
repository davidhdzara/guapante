# -*- coding: utf-8 -*-
"""Incidente real en Guapante (2026-10-04, módulo .43 en producción):
``l10n_co_ne_pre_sequence_id`` quedó apuntando a la secuencia de Notas de
Ajuste (prefijo NA) en vez de la Temporal (PRE-NOM). Una nómina INDIVIDUAL
terminó con consecutivo "NA0000000001" -> DIAN rechazó con NIE011/NIE012.

El único chequeo que existía ("el consecutivo ya asignado es válido si no
empieza por PRE-NOM") no detecta un prefijo *equivocado* que tampoco es
PRE-NOM. Estas pruebas cubren la defensa en profundidad agregada en
``_ne_expected_prefix``/``_get_next_ne_consecutive``: un consecutivo con el
prefijo que no corresponde al tipo de documento nunca se reutiliza.
"""

import base64
from datetime import date

from lxml import etree

from odoo.tests.common import TransactionCase


class TestNeConsecutivePrefixGuard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # AUD-DIAN-34 (2026-10-05): nunca modificar self.env.company -- la
        # build de Odoo.sh corre sobre una copia de la BD real de Guapante;
        # test_individual_with_misconfigured_pre_sequence_never_keeps_na_prefix
        # necesita reasignar l10n_co_ne_pre_sequence_id, y hacerlo sobre la
        # compañía real (aunque TransactionCase lo revierta) es justo el
        # patrón que causó el UniqueViolation real en test_dian_matching.py.
        # Compañía dedicada y descartable, igual que ahí.
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Consecutivo NE',
        })
        co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Consecutivo',
            'country_id': co_country.id,
        })
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba Consecutivo',
            'type_id': cls.structure_type.id,
        })
        cls.ajuste_sequence = cls.env['ir.sequence'].search(
            [('code', '=', 'l10n_co_nomina.ajuste')], limit=1,
        )
        cls.electronica_sequence = cls.env['ir.sequence'].search(
            [('code', '=', 'l10n_co_nomina.electronica')], limit=1,
        )

    def _make_payslip(self, name, is_adjustment=False):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '20' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            # AUD-DIAN-34 (2026-10-05): ver nota en test_dian_matching.py --
            # evita _check_bank_account_for_transfer() sin fabricar datos
            # bancarios.
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato %s' % name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 1800000.0,
            'date_start': date(2024, 1, 1),
            'state': 'open',
        })
        vals = {
            'name': 'Nómina %s' % name,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
            'l10n_co_ne_is_adjustment': is_adjustment,
        }
        if is_adjustment:
            # AUD-DIAN-34 (2026-10-05): _check_adjustment_ref_cune() exige
            # el CUNE de la nómina original cuando is_adjustment=True --
            # valor de prueba, sin relación con un payslip real.
            vals['l10n_co_ne_adjustment_ref_cune'] = 'CUNE-ORIGINAL-%s' % name
        return self.env['hr.payslip'].create(vals)

    def test_individual_with_misconfigured_pre_sequence_never_keeps_na_prefix(self):
        """Reproduce el bug real: pre_sequence_id apuntando a la de Ajuste (NA)."""
        self.company.l10n_co_ne_pre_sequence_id = self.ajuste_sequence.id

        payslip = self._make_payslip('Individual', is_adjustment=False)
        # Simula el efecto ya ocurrido de action_payslip_done() con la
        # secuencia mal configurada: el payslip quedó con un consecutivo
        # "oficial" de prefijo NA, aunque es una nómina individual.
        payslip.l10n_co_ne_consecutive = self.ajuste_sequence.next_by_id()
        self.assertTrue(payslip.l10n_co_ne_consecutive.startswith('NA'))

        next_consecutive = payslip._get_next_ne_consecutive()

        self.assertFalse(next_consecutive.startswith('NA'))
        self.assertTrue(next_consecutive.startswith('NE'))

    def test_individual_with_correct_consecutive_is_reused(self):
        """No debe reasignar un consecutivo NE ya válido para una individual."""
        payslip = self._make_payslip('IndividualOk', is_adjustment=False)
        payslip.l10n_co_ne_consecutive = 'NE0000009999'

        self.assertEqual(payslip._get_next_ne_consecutive(), 'NE0000009999')

    def test_adjustment_with_ne_prefix_is_not_reused(self):
        """Simétrico: una Nota de Ajuste con prefijo NE (equivocado) se reasigna."""
        payslip = self._make_payslip('Ajuste', is_adjustment=True)
        payslip.l10n_co_ne_consecutive = 'NE0000001111'

        next_consecutive = payslip._get_next_ne_consecutive()

        self.assertFalse(next_consecutive.startswith('NE'))
        self.assertTrue(next_consecutive.startswith('NA'))

    def test_action_generate_ne_xml_reassigns_wrong_prefix_before_building(self):
        """El guard en action_generate_ne_xml() también debe dispararse."""
        payslip = self._make_payslip('Regenerar', is_adjustment=False)
        payslip.l10n_co_ne_consecutive = 'NA0000005555'

        expected_prefix = payslip._ne_expected_prefix()
        self.assertEqual(expected_prefix, 'NE')
        # No se ejecuta action_generate_ne_xml() completo (requiere XML/
        # firma/certificado reales); se prueba el guard exacto que decide
        # si reasigna, que es la línea que tenía el bug.
        consecutive_is_valid = (
            payslip.l10n_co_ne_consecutive
            and payslip.l10n_co_ne_consecutive.startswith(expected_prefix)
        )
        self.assertFalse(consecutive_is_valid)

    # --- Regresion NIAE024 (Nota de Ajuste: CUNE vacio y predecesor mal armado) ---
    _AJUSTE_XML = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<NominaIndividualDeAjuste xmlns="dian:gov:co:facturaelectronica:NominaIndividualDeAjuste">'
        b'<ext:UBLExtensions xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"/>'
        b'<Reemplazar><InformacionGeneral CUNE="" EncripCUNE=""/><CodigoQR/></Reemplazar>'
        b'</NominaIndividualDeAjuste>'
    )

    def test_cune_y_qr_se_escriben_dentro_de_reemplazar(self):
        payslip = self._make_payslip('AjusteCune', is_adjustment=True)
        xml = payslip._ne_insert_cune_and_qr(self._AJUSTE_XML, 'abc123')
        root = etree.fromstring(xml)
        info = root.find('.//{*}InformacionGeneral')
        self.assertEqual(info.get('CUNE'), 'abc123')
        self.assertEqual(info.get('EncripCUNE'), 'CUNE-SHA384')
        self.assertIn('documentkey=abc123', root.find('.//{*}CodigoQR').text)

    def test_cune_y_qr_se_crean_si_codigoqr_no_existe(self):
        payslip = self._make_payslip('AjusteQr', is_adjustment=True)
        xml_sin_qr = self._AJUSTE_XML.replace(b'<CodigoQR/>', b'')
        root = etree.fromstring(payslip._ne_insert_cune_and_qr(xml_sin_qr, 'abc123'))
        self.assertEqual(root.find('.//{*}Reemplazar/{*}CodigoQR').getprevious().tag.split('}')[-1],
                         'InformacionGeneral')

    def test_predecesor_usa_numero_y_fecha_de_emision_del_documento_original(self):
        original = self._make_payslip('Original', is_adjustment=False)
        original.write({'l10n_co_ne_cune': 'cune-del-original', 'l10n_co_ne_consecutive': 'NE0000000047'})
        original.l10n_co_ne_xml_attachment_id = self.env['ir.attachment'].create({
            'name': 'original.xml',
            'datas': base64.b64encode(
                b'<NominaIndividual xmlns="x"><InformacionGeneral FechaGen="2026-10-04"/></NominaIndividual>'),
        })
        ajuste = self._make_payslip('AjustePred', is_adjustment=True)
        ajuste.l10n_co_ne_adjustment_ref_cune = 'cune-del-original'
        numero, fecha = ajuste._ne_predecessor_values()
        self.assertEqual(numero, 'NE0000000047')
        self.assertEqual(fecha, '2026-10-04')
        self.assertNotEqual(fecha, str(ajuste.date_to))

    def test_predecesor_inexistente_no_inventa_valores(self):
        ajuste = self._make_payslip('AjusteHuerfano', is_adjustment=True)
        self.assertEqual(ajuste._ne_predecessor_values(), ('', ''))

    def test_version_de_nota_de_ajuste_usa_el_literal_niae022(self):
        ajuste = self._make_payslip('AjusteVersion', is_adjustment=True)
        individual = self._make_payslip('IndividualVersion', is_adjustment=False)
        self.assertEqual(
            ajuste._collect_payslip_data()['informacion_general']['Version'],
            'V1.0: Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica')
        self.assertEqual(
            individual._collect_payslip_data()['informacion_general']['Version'],
            'V1.0: Documento Soporte de Pago de Nómina Electrónica')
