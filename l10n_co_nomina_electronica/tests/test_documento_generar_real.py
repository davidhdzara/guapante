# -*- coding: utf-8 -*-
"""Etapa 3b, prueba "de verdad" (pedida por Tech Lead): documento mensual con recibos REALES de una quincena,
calculados por el motor (compute_sheet), preparados con _ne_preparar y generados con action_generar_xml SIN parchear
la recoleccion, la fusion, el constructor del XML ni el CUNE. Solo se simula lo que no se puede tener en una prueba:
el certificado y la firma (no hay certificado de prueba). Ademas el XML se valida contra el XSD v1.0.6 que viaja en
el modulo (DIAN/Caja-de-Herramientas-Nomina-Electronica-V1-0). NO envia nada a la DIAN."""

import base64
import logging
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lxml import etree

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services import xml_signer
from .common_dane import ciudad_con_dane

_logger = logging.getLogger(__name__)
CAJA = Path(__file__).resolve().parent.parent / 'DIAN' / 'Caja-de-Herramientas-Nomina-Electronica-V1-0'
NS_EXT = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'


@tagged('post_install', '-at_install')
class TestDocumentoGenerarReal(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        pais = env.ref('base.co')
        estado = env['res.country.state'].search([('country_id', '=', pais.id)], limit=1)
        ciudad = ciudad_con_dane(env, estado, 'Ciudad Prueba Generar Real')
        cls.company = env['res.company'].create({
            'name': 'Empresa Generar Real', 'country_id': pais.id, 'vat': '900123456-8',
            'street': 'Calle 1 # 2-3', 'state_id': estado.id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'l10n_co_ne_fuente_fecha_pago': 'recibo', 'l10n_co_ne_payroll_prefix': 'NE'})
        # El municipio de la compañía NO es un campo de res.company: el XML lo lee de su partner
        # (``company.partner_id.city_id``, hr_payslip._collect_payslip_data).
        cls.company.partner_id.write({
            'country_id': pais.id, 'state_id': estado.id, 'city_id': ciudad.id, 'street': 'Calle 1 # 2-3'})
        env['l10n.co.ne.operation_mode'].create({
            'company_id': cls.company.id, 'software_id': 'SOFT-REAL', 'software_pin': 'PIN-REAL', 'test_set_id': 'TS'})
        cls.company.l10n_co_ne_environment = '2'
        cls.company.l10n_co_ne_sequence_id = env['ir.sequence'].create({
            'name': 'Secuencia NE real', 'prefix': 'NE', 'padding': 8, 'number_next': 1,
            'implementation': 'no_gap', 'company_id': cls.company.id})
        tipo_id = env.ref('l10n_co.national_citizen_id')   # Cedula: un trabajador no se identifica con NIT (alerta tipo_documento_trabajador)
        tipo = env['hr.payroll.structure.type'].create({'name': 'Tipo Generar Real', 'country_id': pais.id})
        cls.empleado = env['hr.employee'].create({
            'name': 'Juan Perez', 'company_id': cls.company.id, 'identification_id': '1020304050',
            'l10n_co_ne_payment_method': '10', 'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00',
            'address_id': cls.company.partner_id.id})
        if tipo_id:
            cls.empleado.work_contact_id.l10n_latam_identification_type_id = tipo_id
        cls.contrato = env['hr.contract'].create({
            'name': 'Contrato Generar Real', 'employee_id': cls.empleado.id, 'company_id': cls.company.id,
            'structure_type_id': tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00'})
        estructura = env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.recibos = env['hr.payslip']
        for ini, fin in ((1, 15), (16, 31)):
            recibo = env['hr.payslip'].create({
                'name': 'Q %s-%s' % (ini, fin), 'employee_id': cls.empleado.id, 'contract_id': cls.contrato.id,
                'company_id': cls.company.id, 'struct_id': estructura.id,
                'date_from': date(2026, 3, ini), 'date_to': date(2026, 3, fin)})
            recibo.compute_sheet()
            recibo.write({'state': 'paid', 'paid_date': date(2026, 3, fin)})
            cls.recibos |= recibo

    def setUp(self):
        super().setUp()
        for objetivo, atributo, valor in (
                (type(self.company), '_get_ne_certificate', lambda s: SimpleNamespace(date_end=False)),
                (xml_signer, 'load_from_certificate', lambda cert: (None, b'', b'', None, None)),
                (xml_signer, 'sign_xml', lambda xml_bytes, **k: xml_bytes)):
            parche = patch.object(objetivo, atributo, valor)
            parche.start()
            self.addCleanup(parche.stop)

    def _validar_xsd(self, xml_bytes):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        (Path(tmp) / 'xsd').mkdir()
        xsd = CAJA / 'XSD' / 'NominaIndividualElectronicaXSDV1.0.6.xsd'
        shutil.copy(xsd, Path(tmp) / 'xsd' / xsd.name)
        shutil.copytree(CAJA / 'Schemes', Path(tmp) / 'common')
        esquema = etree.XMLSchema(etree.parse(str(Path(tmp) / 'xsd' / xsd.name)))
        raiz = etree.fromstring(xml_bytes)
        extensiones = raiz.find('{%s}UBLExtensions' % NS_EXT)
        if extensiones is not None and len(extensiones) == 0:   # la firma real lo llena; aqui, relleno
            for _i in range(2):
                ext = etree.SubElement(extensiones, '{%s}UBLExtension' % NS_EXT)
                etree.SubElement(etree.SubElement(ext, '{%s}ExtensionContent' % NS_EXT), '{urn:relleno}Firma')
        valido = esquema.validate(etree.ElementTree(raiz))
        return valido, [e.message[:200] for e in esquema.error_log]

    def test_dos_quincenas_reales_generan_un_documento_valido(self):
        resultado = self.env['l10n.co.ne.documento']._ne_preparar(self.recibos)
        self.assertFalse(resultado['sin_fecha'], resultado['sin_fecha'])
        doc = resultado['documentos']
        self.assertEqual(len(doc), 1)
        bloqueos = [a['message'] for a in (doc.alertas or []) if a['level'] == 'danger']
        self.assertFalse(bloqueos, 'bloqueos del documento real: %s' % bloqueos)
        self.assertEqual(doc.etapa, 'ready')
        self.assertFalse(doc.state)
        self.assertEqual(doc.payslip_ids, self.recibos)

        doc.action_generar_xml()
        self.assertTrue(doc.consecutive.startswith('NE'))
        self.assertRegex(doc.cune, r'^[0-9a-f]{96}$')
        xml_bytes = base64.b64decode(doc.xml_attachment_id.datas)
        valido, errores = self._validar_xsd(xml_bytes)
        self.assertTrue(valido, 'XML mensual real invalido contra el XSD v1.0.6: %s' % errores)

        # Totales del XML = suma de las lineas reales de los dos recibos
        raiz = etree.fromstring(xml_bytes)
        dev = Decimal(raiz.find('{*}DevengadosTotal').text)
        ded = Decimal(raiz.find('{*}DeduccionesTotal').text)
        esperado_dev = sum((Decimal(str(l.total)) for r in self.recibos for l in r.line_ids
                            if l.salary_rule_id.l10n_co_ne_dian_concept
                            and not l.salary_rule_id.l10n_co_ne_is_deduction), Decimal('0'))
        esperado_ded = sum((abs(Decimal(str(l.total))) for r in self.recibos for l in r.line_ids
                            if l.salary_rule_id.l10n_co_ne_dian_concept
                            and l.salary_rule_id.l10n_co_ne_is_deduction), Decimal('0'))
        self.assertEqual(dev, esperado_dev.quantize(Decimal('0.01')))
        self.assertEqual(ded, esperado_ded.quantize(Decimal('0.01')))
        periodo = raiz.find('{*}Periodo')
        self.assertEqual(periodo.get('TiempoLaborado'), '750')     # 2024-03-01 a 2026-03-31, D19
        self.assertEqual(periodo.get('FechaLiquidacionInicio'), '2026-03-01')
        self.assertEqual(periodo.get('FechaLiquidacionFin'), '2026-03-31')
        self.assertEqual([f.text for f in raiz.findall('.//{*}FechaPago')], ['2026-03-15', '2026-03-31'])
        self.assertEqual(raiz.find('{*}InformacionGeneral').get('PeriodoNomina'), '5')
        _logger.warning('GENERAR REAL: consecutivo=%s dev=%s ded=%s', doc.consecutive, dev, ded)

    # ── todas las listas del XML (.335, clase A) ─────────────────────
    _CONCEPTOS_DE_LINEA = (
        'HED', 'HEN', 'HRN', 'HEDDF', 'HRDDF', 'HENDF', 'HRNDF', 'BonificacionS', 'BonificacionNS', 'AuxilioS', 'AuxilioNS', 'HuelgaLegal', 'OtroConceptoS', 'OtroConceptoNS',
        'CompensacionO', 'CompensacionE', 'BonoEPCTVS', 'BonoEPCTVNS', 'BonoAlimS', 'BonoAlimNS', 'Comision', 'PagoTercero', 'Anticipo',
        'Sindicato', 'Sancion', 'Libranza', 'PagoTerceroDed', 'AnticipoDed', 'OtraDeduccion')
    _ELEMENTOS_POR_RECIBO = {          # (seccion, ruta): elementos que pone cada recibo
        ('Devengados', 'HEDs/HED'): 1, ('Devengados', 'HENs/HEN'): 1, ('Devengados', 'HRNs/HRN'): 1, ('Devengados', 'HEDDFs/HEDDF'): 1, ('Devengados', 'HRDDFs/HRDDF'): 1,
        ('Devengados', 'HENDFs/HENDF'): 1, ('Devengados', 'HRNDFs/HRNDF'): 1, ('Devengados', 'Vacaciones/VacacionesComunes'): 1, ('Devengados', 'Vacaciones/VacacionesCompensadas'): 1,
        ('Devengados', 'Incapacidades/Incapacidad'): 1, ('Devengados', 'Licencias/LicenciaMP'): 1, ('Devengados', 'Licencias/LicenciaR'): 1, ('Devengados', 'Licencias/LicenciaNR'): 1,
        ('Devengados', 'Bonificaciones/Bonificacion'): 1, ('Devengados', 'Auxilios/Auxilio'): 1, ('Devengados', 'HuelgasLegales/HuelgaLegal'): 1,
        ('Devengados', 'OtrosConceptos/OtroConcepto'): 2, ('Devengados', 'Compensaciones/Compensacion'): 1, ('Devengados', 'BonoEPCTVs/BonoEPCTV'): 1,
        ('Devengados', 'Comisiones/Comision'): 1, ('Devengados', 'PagosTerceros/PagoTercero'): 1, ('Devengados', 'Anticipos/Anticipo'): 1,
        ('Deducciones', 'Sindicatos/Sindicato'): 1, ('Deducciones', 'Sanciones/Sancion'): 1, ('Deducciones', 'Libranzas/Libranza'): 1,
        ('Deducciones', 'PagosTerceros/PagoTercero'): 1, ('Deducciones', 'Anticipos/Anticipo'): 1, ('Deducciones', 'OtrasDeducciones/OtraDeduccion'): 1}

    def _recibos_de_un_empleado_nuevo(self, quincenas):
        empleado = self.env['hr.employee'].create({
            'name': 'Listas %s' % len(quincenas), 'company_id': self.company.id, 'identification_id': '102030407%s' % len(quincenas), 'l10n_co_ne_payment_method': '10',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'address_id': self.company.partner_id.id})
        empleado.work_contact_id.l10n_latam_identification_type_id = self.env.ref('l10n_co.national_citizen_id')
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato Listas %s' % len(quincenas), 'employee_id': empleado.id, 'company_id': self.company.id, 'structure_type_id': self.contrato.structure_type_id.id,
            'wage': 3000000.0, 'date_start': date(2025, 1, 1), 'state': 'open', 'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00'})
        recibos = self.env['hr.payslip']
        for ini, fin in quincenas:
            recibo = self.env['hr.payslip'].create({
                'name': 'Listas %s-%s' % (ini, fin), 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
                'struct_id': self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id, 'date_from': date(2026, 3, ini), 'date_to': date(2026, 3, fin)})
            recibo.compute_sheet()
            recibo.write({'state': 'paid', 'paid_date': date(2026, 3, fin)})
            recibos |= recibo
        return recibos

    def _agregar_una_linea_por_concepto(self, recibos):
        estructura = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        for orden, concepto in enumerate(self._CONCEPTOS_DE_LINEA, 1):
            regla = self.env['hr.salary.rule'].create({
                'name': 'Lista %s' % concepto, 'code': 'T_LISTA_%s' % concepto.upper(), 'sequence': 900 + orden, 'struct_id': estructura.id,
                'category_id': self.env.ref('hr_payroll.ALW').id, 'condition_select': 'none', 'amount_select': 'fix', 'amount_fix': 0.0, 'l10n_co_ne_dian_concept': concepto})
            for recibo in recibos:
                valor = (-1000.0 if regla.l10n_co_ne_is_deduction else 1000.0) - orden
                self.env['hr.payslip.line'].create({
                    'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': regla.code, 'name': regla.name, 'contract_id': recibo.contract_id.id,
                    'employee_id': recibo.employee_id.id, 'sequence': regla.sequence, 'quantity': 1.0, 'rate': 100.0, 'amount': valor, 'total': valor})

    def _con_ausencias(self, recibos):
        """Incapacidades, vacaciones y licencias salen de las Ausencias; aqui se agregan a los datos del recibo con la forma que arma el constructor (pago 0: no cambian los totales)."""
        original = type(recibos)._collect_payslip_data

        def datos_con_ausencias(recibo):
            datos = original(recibo)
            tramo = {'FechaInicio': str(recibo.date_from), 'FechaFin': str(recibo.date_from), 'Cantidad': '1'}
            con_pago = dict(tramo, Pago='0.00')
            datos['devengados'].update({
                'Incapacidades': [dict(con_pago, Tipo='1')], 'Vacaciones': {'VacacionesComunes': [dict(con_pago)], 'VacacionesCompensadas': [{'Cantidad': '1', 'Pago': '0.00'}]},
                'Licencias': {'LicenciaMP': [dict(con_pago)], 'LicenciaR': [dict(con_pago)], 'LicenciaNR': [dict(tramo)]}})
            return datos
        parche = patch.object(type(recibos), '_collect_payslip_data', datos_con_ausencias)
        parche.start()
        self.addCleanup(parche.stop)

    def test_todas_las_listas_dan_un_xml_valido_con_un_recibo_y_con_dos(self):
        """.335 (clase A): con comisiones, pagos a terceros, anticipos u otras deducciones el documento mensual se caia con ValueError."""
        for quincenas in (((1, 15),), ((1, 15), (16, 31))):
            with self.subTest(recibos=len(quincenas)):
                recibos = self._recibos_de_un_empleado_nuevo(quincenas)
                self._agregar_una_linea_por_concepto(recibos)
                self._con_ausencias(recibos)
                documento = self.env['l10n.co.ne.documento']._ne_preparar(recibos)['documentos']
                self.assertEqual((len(documento), documento.payslip_ids), (1, recibos))
                self.assertFalse([a['message'] for a in (documento.alertas or []) if a['level'] == 'danger'])
                documento.action_generar_xml()
                xml_bytes = base64.b64decode(documento.xml_attachment_id.datas)
                valido, errores = self._validar_xsd(xml_bytes)
                self.assertTrue(valido, 'XML con todas las listas invalido contra el XSD v1.0.6: %s' % errores)
                raiz = etree.fromstring(xml_bytes)
                for (seccion, ruta), por_recibo in self._ELEMENTOS_POR_RECIBO.items():
                    camino = './/{*}%s/%s' % (seccion, '/'.join('{*}%s' % parte for parte in ruta.split('/')))
                    self.assertEqual(len(raiz.findall(camino)), por_recibo * len(quincenas), '%s/%s' % (seccion, ruta))
                for seccion, total in (('Devengados', 'DevengadosTotal'), ('Deducciones', 'DeduccionesTotal')):
                    esperado = sum((abs(Decimal(str(l.total))) for r in recibos for l in r.line_ids
                                    if l.salary_rule_id.l10n_co_ne_dian_concept and l.salary_rule_id.l10n_co_ne_is_deduction == (seccion == 'Deducciones')), Decimal('0'))
                    self.assertEqual(Decimal(raiz.find('{*}%s' % total).text), esperado.quantize(Decimal('0.01')), seccion)
                comisiones = [Decimal(e.text) for e in raiz.findall('.//{*}Comisiones/{*}Comision')]
                self.assertEqual(comisiones, [abs(Decimal(str(l.total))).quantize(Decimal('0.01')) for r in recibos for l in r.line_ids if l.salary_rule_id.code == 'T_LISTA_COMISION' and l.total])          # sin las de valor cero de la vuelta anterior: el XML no las lleva

    def test_el_documento_de_un_aprendiz_es_valido_con_basico_en_cero_y_el_apoyo(self):
        """H-F1-09 (doc 88, D1): el apoyo es el sueldo del contrato. El XML lleva ``Basico`` (obligatorio en el XSD) con los dias y SueldoTrabajado 0.00, y ``ApoyoSost`` con el valor; antes, con sueldo 0 y
        la novedad, salia sin ``Basico`` y no se podia generar. Practica y lectiva. La regla de negocio de la DIAN para SueldoTrabajado 0 NO esta verificada (habilitacion)."""
        estructura = self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        tipo = self.contrato.structure_type_id
        for nombre, documento, cotizante, trabajador, apoyo in (('Ana Practica', '1020304061', '01', '19', 1750905.0), ('Luis Lectiva', '1020304062', '19', '12', 1313180.0)):
            empleado = self.env['hr.employee'].create({
                'name': nombre, 'company_id': self.company.id, 'identification_id': documento, 'l10n_co_ne_payment_method': '10', 'l10n_co_ne_worker_type': trabajador,
                'l10n_co_ne_worker_subtype': '00', 'address_id': self.company.partner_id.id})
            empleado.work_contact_id.l10n_latam_identification_type_id = self.env.ref('l10n_co.national_citizen_id')
            contrato = self.env['hr.contract'].create({
                'name': 'Aprendizaje %s' % nombre, 'employee_id': empleado.id, 'company_id': self.company.id, 'structure_type_id': tipo.id, 'wage': apoyo, 'date_start': date(2026, 1, 1),
                'state': 'open', 'l10n_co_ne_contract_type': '4', 'l10n_co_pila_tipo_cotizante': cotizante, 'l10n_co_pila_subtipo_cotizante': '00'})
            recibos = self.env['hr.payslip']
            for ini, fin in ((1, 15), (16, 31)):
                recibo = self.env['hr.payslip'].create({
                    'name': '%s %s-%s' % (nombre, ini, fin), 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id, 'struct_id': estructura.id,
                    'date_from': date(2026, 3, ini), 'date_to': date(2026, 3, fin)})
                recibo.compute_sheet()
                recibo.write({'state': 'paid', 'paid_date': date(2026, 3, fin)})
                recibos |= recibo
            resultado = self.env['l10n.co.ne.documento']._ne_preparar(recibos)
            doc = resultado['documentos']
            self.assertEqual(len(doc), 1, resultado)
            bloqueos = [a['message'] for a in (doc.alertas or []) if a['level'] == 'danger']
            self.assertFalse(bloqueos, '%s: %s' % (nombre, bloqueos))
            doc.action_generar_xml()
            xml_bytes = base64.b64decode(doc.xml_attachment_id.datas)
            valido, errores = self._validar_xsd(xml_bytes)
            self.assertTrue(valido, '%s: XML del aprendiz invalido contra el XSD v1.0.6: %s' % (nombre, errores))
            raiz = etree.fromstring(xml_bytes)
            basico = raiz.find('.//{*}Devengados/{*}Basico')
            self.assertEqual((basico.get('DiasTrabajados'), basico.get('SueldoTrabajado')), ('30', '0.00'), nombre)
            self.assertEqual(Decimal(raiz.find('.//{*}Devengados/{*}ApoyoSost').text), Decimal(str(apoyo)).quantize(Decimal('0.01')), nombre)
            self.assertEqual(Decimal(raiz.find('.//{*}Trabajador').get('Sueldo')), Decimal(str(apoyo)).quantize(Decimal('0.01')), nombre)

