# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-DIAN-01 (doc 105 §3; decisiones del TL Q-D2 y Q-D3): si la DIAN dice que el set de pruebas ya está Aceptado, la habilitación está completa aunque falte la meta de Ajustes y no se regenera ni reenvía
nada. Un rechazo y un envío incierto sin veredicto detienen el proceso, cada uno con su texto; solo lo rechazado se regenera. Sin red: la evidencia de la consulta se arma con una respuesta SOAP."""

import base64
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from . import test_habilitacion_engine as motor          # el modulo, no la clase: importarla la correria dos veces

_SET = 'Set de prueba con identificador e07c1748-0000-0000-0000-000000000000 se encuentra %s.'
_SOBRE = ('<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body><GetStatusZipResponse xmlns="http://wcf.dian.colombia"><GetStatusZipResult '
          'xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse"><b:DianResponse><b:IsValid>false</b:IsValid><b:StatusCode>2</b:StatusCode><b:StatusDescription>%s</b:StatusDescription>'
          '<b:XmlDocumentKey/></b:DianResponse></GetStatusZipResult></GetStatusZipResponse></s:Body></s:Envelope>')


@tagged('post_install', '-at_install')
class TestHabilitacionSetAceptado(TransactionCase):
    _slip = motor.TestHabilitacionEngine._slip

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Set Aceptado'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'Estructura Set Aceptado', 'country_id': cls.env.ref('base.co').id})
        cls.structure = cls.env['hr.payroll.structure'].create({'name': 'Nómina Set Aceptado', 'type_id': cls.structure_type.id})

    def setUp(self):
        super().setUp()
        self.company.write({'l10n_co_ne_certification_process': True, 'l10n_co_ne_environment': '2', 'l10n_co_ne_num_nomina_certificar': 3,
                            'l10n_co_ne_num_ajuste_certificar': 2, 'l10n_co_ne_hab_state': 'running'})
        self.env['l10n.co.ne.operation_mode'].create({'company_id': self.company.id, 'software_id': 'SOFTWARE-TEST-ID', 'software_pin': 'PIN-TEST', 'test_set_id': 'SET-ACTUAL'})
        commit = patch(motor._ENGINE + '._commit')
        commit.start()
        self.addCleanup(commit.stop)
        self.engine = self.env['l10n.co.ne.habilitacion'].with_company(self.company)

    def _incierto(self, nombre, descripcion=None):
        """Un recibo incierto; con ``descripcion``, su última consulta fue esa respuesta sobre el set."""
        recibo = self._slip(nombre, 'uncertain')
        recibo.write({'l10n_co_ne_consecutive': 'NE-%s' % nombre, 'l10n_co_ne_zip_key': 'ZIP-%s' % nombre})
        if descripcion:
            self.env['l10n.co.ne.exchange'].create({
                'company_id': self.company.id, 'operation': 'get_status_zip', 'endpoint': 'https://example.test/habilitacion', 'queried_zip_key': recibo.l10n_co_ne_zip_key,
                'response_payload': base64.b64encode((_SOBRE % descripcion).encode()), 'payslip_ids': [(6, 0, recibo.ids)]})
        return recibo

    def _rechazado(self, nombre):
        recibo = self._slip(nombre, 'rejected')
        recibo.l10n_co_ne_consecutive = 'NE-%s' % nombre
        return recibo

    def _paso(self):
        with patch(motor._ENGINE + '._rejection_reasons', return_value='Regla: NIE999'):
            self.assertTrue(self.engine._step(self.company))
        return self.company.l10n_co_ne_hab_state, self.company.l10n_co_ne_hab_message

    def _regenerados(self):
        with patch(motor._PAYSLIP + '.action_regenerate_ne_xml', autospec=True) as regenerar:
            cantidad = self.engine._replace_failed(self.company)
        return cantidad, [recibo for llamada in regenerar.call_args_list for recibo in llamada.args[0]]

    def test_el_set_aceptado_completa_la_habilitacion_aunque_falte_la_meta(self):
        self._slip('Aceptada', 'accepted')
        incierto = self._incierto('A', _SET % 'Aceptado')
        estado, mensaje = self._paso()
        self.assertEqual(estado, 'done')
        self.assertIn('e07c1748', mensaje)
        self.assertNotIn('no confirmó', mensaje)
        self.assertEqual((incierto.l10n_co_ne_state, incierto.l10n_co_ne_consecutive), ('uncertain', 'NE-A'))

    def test_con_el_set_aceptado_no_se_regenera_nada(self):
        self._incierto('A', _SET % 'Aceptado')
        self._rechazado('B')
        self.assertEqual(self._regenerados(), (0, []))
        estado, _mensaje = self._paso()
        self.assertEqual(estado, 'done')

    def test_un_incierto_sin_veredicto_detiene_y_pide_consultar(self):
        incierto = self._incierto('C')
        estado, mensaje = self._paso()
        self.assertEqual(estado, 'error')
        self.assertIn('NE-C', mensaje)
        self.assertIn('Consultar Estado', mensaje)
        self.assertNotIn('consecutivo nuevo', mensaje)
        self.assertEqual(self._regenerados(), (0, []))
        self.assertEqual(incierto.l10n_co_ne_state, 'uncertain')

    def test_rechazado_e_incierto_cada_uno_con_su_texto_y_solo_se_regenera_el_rechazado(self):
        rechazado = self._rechazado('D')
        self._incierto('E')
        estado, mensaje = self._paso()
        self.assertEqual(estado, 'error')
        for texto in ('NIE999', 'NE-D', 'NE-E', 'consecutivo nuevo', 'Consultar Estado'):
            self.assertIn(texto, mensaje)
        self.assertEqual(self._regenerados(), (1, [rechazado]))

    def test_otra_respuesta_sobre_el_set_no_completa_y_se_muestra(self):
        self._incierto('F', _SET % 'Rechazado')
        estado, mensaje = self._paso()
        self.assertEqual(estado, 'error')
        self.assertIn('se encuentra Rechazado', mensaje)
