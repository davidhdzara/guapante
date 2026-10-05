"""Fixtures sin datos personales para el parser de respuestas DIAN."""

import base64
import importlib.util
from pathlib import Path
import unittest


_SERVICE = Path(__file__).parents[1] / 'services' / 'soap_client.py'
_SPEC = importlib.util.spec_from_file_location('ne_soap_client', _SERVICE)
soap_client = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(soap_client)


class TestDianResponseParser(unittest.TestCase):
    def test_error_message_list_and_soap_fault_are_not_document_results(self):
        response = soap_client._parse_response(
            '<Envelope><DianResponse><ErrorMessage><string>ZE02</string>'
            '<string>NIE072</string></ErrorMessage></DianResponse></Envelope>'
        )
        self.assertEqual(response['DianResponses'][0]['ErrorMessages'], ['ZE02', 'NIE072'])
        fault = soap_client._parse_response(
            '<Envelope><Fault><Reason><Text>SOAP failed</Text></Reason></Fault></Envelope>'
        )
        self.assertTrue(fault['SOAPFault'])
        self.assertEqual(fault['DianResponses'], [])

    def test_root_level_uuid_or_id_never_identifies_a_payslip(self):
        """El UUID/ID de nivel raíz es la identidad de la respuesta DIAN, no
        del documento referenciado -- ninguna de las 2 funciones debe leerlo."""
        app = '<ApplicationResponse><UUID>RESP-UUID</UUID><ID>RESP-ID</ID></ApplicationResponse>'
        self.assertEqual(soap_client.extract_document_cunes(app), set())
        self.assertEqual(soap_client.extract_document_numbers(app), set())

    def test_document_reference_number_requires_real_ubl_path(self):
        app = ('<ApplicationResponse xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
               'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
               '<cac:DocumentResponse><cac:DocumentReference><cbc:ID>NE0000000009</cbc:ID>'
               '</cac:DocumentReference></cac:DocumentResponse></ApplicationResponse>')
        self.assertEqual(soap_client.extract_document_numbers(app), {'NE0000000009'})
        self.assertEqual(soap_client.extract_document_cunes(app), set())

    def test_document_reference_cune_requires_real_ubl_path(self):
        """AUD-DIAN-34 (2026-10-04): cbc:UUID bajo DocumentReference es el
        CUNE/CUFE real -- confirmado con evidencia real (ver test del XML
        completo más abajo), no cbc:ID."""
        app = ('<ApplicationResponse xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
               'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
               '<cac:DocumentResponse><cac:DocumentReference>'
               '<cbc:UUID schemeName="CUNE-SHA384">abc123cune</cbc:UUID>'
               '</cac:DocumentReference></cac:DocumentResponse></ApplicationResponse>')
        self.assertEqual(soap_client.extract_document_cunes(app), {'abc123cune'})
        self.assertEqual(soap_client.extract_document_numbers(app), set())

    def test_real_authorized_getstatuszip_response_anonymized(self):
        """Fixture basado en una respuesta GetStatusZip AUTORIZADA real de la
        DIAN (habilitación, StatusCode 00, 2026-10-04) -- NIT y razón social
        reemplazados por valores de prueba; estructura UBL y nombres de
        elemento intactos. Confirma que ambas funciones leen el documento
        real correctamente: CUNE desde DocumentReference/UUID, número desde
        DocumentReference/ID (no al revés, que era el bug original)."""
        application_response = (
            '<?xml version="1.0" encoding="utf-8" standalone="no"?>'
            '<ApplicationResponse '
            'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
            'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
            'xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2">'
            '<cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID>'
            '<cbc:CustomizationID>1</cbc:CustomizationID>'
            '<cbc:ProfileID>DIAN 2.1</cbc:ProfileID>'
            '<cbc:ProfileExecutionID>2</cbc:ProfileExecutionID>'
            '<cbc:ID>58361168</cbc:ID>'
            '<cbc:UUID schemeName="CUDE-SHA384">RESPUESTA-UUID-ANONIMIZADO</cbc:UUID>'
            '<cbc:IssueDate>2026-10-04</cbc:IssueDate>'
            '<cbc:IssueTime>09:54:07-05:00</cbc:IssueTime>'
            '<cac:SenderParty><cac:PartyTaxScheme>'
            '<cbc:RegistrationName>Unidad Especial DIAN</cbc:RegistrationName>'
            '<cbc:CompanyID schemeID="4" schemeName="">800197268</cbc:CompanyID>'
            '<cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme>'
            '</cac:PartyTaxScheme></cac:SenderParty>'
            '<cac:ReceiverParty><cac:PartyTaxScheme>'
            '<cbc:RegistrationName>EMPRESA DE PRUEBA S.A.S.</cbc:RegistrationName>'
            '<cbc:CompanyID schemeID="1" schemeName="">900000000</cbc:CompanyID>'
            '<cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme>'
            '</cac:PartyTaxScheme></cac:ReceiverParty>'
            '<cac:DocumentResponse>'
            '<cac:Response>'
            '<cbc:ResponseCode>02</cbc:ResponseCode>'
            '<cbc:Description>Documento validado por la DIAN</cbc:Description>'
            '</cac:Response>'
            '<cac:DocumentReference>'
            '<cbc:ID>NE0000000009</cbc:ID>'
            '<cbc:UUID schemeName="CUFE-SHA384">cune-anonimizado-0000000009</cbc:UUID>'
            '</cac:DocumentReference>'
            '<cac:LineResponse><cac:LineReference><cbc:LineID>1</cbc:LineID></cac:LineReference>'
            '<cac:Response><cbc:ResponseCode>0000</cbc:ResponseCode><cbc:Description>0</cbc:Description></cac:Response>'
            '</cac:LineResponse>'
            '<cac:LineResponse><cac:LineReference><cbc:LineID>2</cbc:LineID></cac:LineReference>'
            '<cac:Response><cbc:ResponseCode>0</cbc:ResponseCode>'
            '<cbc:Description>La Nomina Individual NE0000000009, ha sido autorizada.</cbc:Description></cac:Response>'
            '</cac:LineResponse>'
            '</cac:DocumentResponse>'
            '</ApplicationResponse>'
        )
        # Envoltura GetStatusZipResponse real, con el ApplicationResponse
        # anterior codificado en base64 -- igual que lo entrega DIAN.
        encoded = base64.b64encode(application_response.encode('utf-8')).decode()
        envelope = (
            '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
            '<s:Body><GetStatusZipResponse xmlns="http://wcf.dian.colombia">'
            '<GetStatusZipResult xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse">'
            '<b:DianResponse>'
            '<b:IsValid>true</b:IsValid>'
            '<b:StatusCode>00</b:StatusCode>'
            '<b:StatusDescription>Procesado Correctamente.</b:StatusDescription>'
            '<b:StatusMessage>La Nomina Individual NE0000000009, ha sido autorizada.</b:StatusMessage>'
            '<b:XmlBase64Bytes>%s</b:XmlBase64Bytes>'
            '<b:XmlDocumentKey>cune-anonimizado-0000000009</b:XmlDocumentKey>'
            '<b:XmlFileName>ne900000000210001</b:XmlFileName>'
            '</b:DianResponse>'
            '</GetStatusZipResult></GetStatusZipResponse></s:Body></s:Envelope>'
        ) % encoded

        parsed = soap_client._parse_response(envelope)
        self.assertEqual(len(parsed['DianResponses']), 1)
        dian_response = parsed['DianResponses'][0]
        self.assertEqual(dian_response['IsValid'], 'true')

        app_decoded = dian_response['ApplicationResponse']
        self.assertEqual(
            soap_client.extract_document_cunes(app_decoded),
            {'cune-anonimizado-0000000009'},
        )
        self.assertEqual(
            soap_client.extract_document_numbers(app_decoded),
            {'NE0000000009'},
        )

    def test_large_payload_is_not_truncated(self):
        payload = base64.b64encode(b'x' * 6001).decode()
        parsed = soap_client._parse_response(
            '<Envelope><DianResponse><XmlBase64Bytes>%s</XmlBase64Bytes>'
            '</DianResponse></Envelope>' % payload
        )
        self.assertEqual(len(parsed['DianResponses'][0]['ApplicationResponse']), 6001)
