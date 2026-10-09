# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.payslip – Modelo central de Nómina Electrónica DIAN.

Este es el módulo principal que orquesta todo el ciclo de vida de un
documento de soporte de pago de nómina electrónica:

1. **Generación del XML**: recopila datos del payslip, mapea las líneas
   salariales a la estructura Devengados/Deducciones, construye el XML
   según el anexo técnico V1.0, calcula el CUNE y firma digitalmente.

2. **Envío a la DIAN**: transmite el XML firmado al servicio web de la
   DIAN y almacena la respuesta (aceptado/rechazado).

3. **Notas de Ajuste**: permite crear documentos de ajuste (reemplazo o
   eliminación) referenciando el CUNE de la nómina original.

Referencia: Anexo Técnico – Documento Soporte de Pago de Nómina Electrónica
V1.0, Resolución DIAN 000013 de 2021.
"""

import base64
import calendar
import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from pytz import timezone as _pytz_timezone
from lxml import etree as _etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from ..services import (
    cune as cune_service,
    dian_utils,
    nomina_xml_builder,
    soap_client,
    xml_signer,
)

_logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────
# Mapeo de conceptos DIAN a la estructura XML de Devengados
# Cada clave es el valor de l10n_co_ne_dian_concept y el valor es la ruta
# dentro del dict que se envía a nomina_xml_builder.
# ──────────────────────────────────────────────────────────────────────────
DEVENGADO_SIMPLE_CONCEPTS = {
    'Dotacion': 'Dotacion',
    'ApoyoSost': 'ApoyoSost',
    'Teletrabajo': 'Teletrabajo',
    'BonifRetiro': 'BonifRetiro',
    'Indemnizacion': 'Indemnizacion',
    'Reintegro': 'Reintegro',
}

HORA_EXTRA_CONCEPTS = {'HED', 'HEN', 'HRN', 'HEDDF', 'HRDDF', 'HENDF', 'HRNDF'}

# H-013 (2026-10-08, QA Bloque 4, decisión de David): códigos de hr.work.entry.type de las
# ausencias colombianas que este módulo paga con su propia regla salarial (data/
# l10n_co_ausencias_data.xml). _ne_dias_pagables() las excluye SIEMPRE del básico (nunca
# dependen de hr.leave.type.unpaid, que es un eje distinto -- ver el comentario en esa
# función) y cada regla lee los mismos días -- una sola fuente para ambos lados, nunca
# doble pago.
#
# Dos grupos, con dos mecanismos de conteo distintos (H-014, 2026-10-08, QA Bloque 5,
# decisión de David basada en CST Art. 186/227/236 mod. Ley 2114/2021 y Concepto
# Mintrabajo 63044901/2022):
#
# - CO_VAC/CO_LIC_REM/CO_LIC_NR: días HÁBILES según el calendario laboral del contrato
#   (L-V, L-S o el de la compañía) -- cuentan vía worked_days (_ne_dias_novedad()), el
#   mecanismo nativo de hr.work.entry ya hace esta cuenta correctamente.
# - CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL: días CALENDARIO corridos (lunes a
#   domingo, festivos incluidos -- el empleado no puede quedar subpagado). worked_days NO
#   alcanza para esto: los work entries solo existen en los días que el calendario del
#   contrato define como laborables (confirmado contra hr_work_entry_contract.
#   _get_contract_work_entries_values -- un día sin asistencia en ese calendario, ej. el
#   lunes en un calendario martes-a-domingo, nunca genera NINGÚN work entry). Por eso estos
#   4 cuentan directamente desde las fechas de la hr.leave validada
#   (_ne_ausencia_calendario()), no desde worked_days.
_NOVEDAD_AUSENCIA_WORKED_DAYS_CODES = {'CO_VAC', 'CO_LIC_REM', 'CO_LIC_NR'}
_NOVEDAD_AUSENCIA_CALENDARIO_CODES = {
    'CO_LIC_MAT', 'CO_LIC_PAT', 'CO_INC_COMUN', 'CO_INC_LABORAL',
}

DEDUCTION_SIMPLE_CONCEPTS = {
    'PensionVoluntaria': 'PensionVoluntaria',
    'RetencionFuente': 'RetencionFuente',
    'AFC': 'AFC',
    'Cooperativa': 'Cooperativa',
    'EmbargoFiscal': 'EmbargoFiscal',
    'PlanComplementarios': 'PlanComplementarios',
    'Educacion': 'Educacion',
    'ReintegroDed': 'Reintegro',
    'Deuda': 'Deuda',
}

# Tope de documentos 'sent' que _cron_recheck_sent_status() reconsulta por
# compañía en cada ejecución -- un lote acotado, no todo el histórico
# pendiente de una sola vez (ver data/ir_cron_dian_status_recheck.xml, cuyo
# intervalo SÍ es un dato editable en Ajustes, no una constante de código).
_CRON_RECHECK_BATCH_LIMIT = 200

# H-012 (2026-10-06): plazo máximo (horas) que un documento 'sent' se reconsulta
# automáticamente antes de marcarse 'uncertain' y salir del cron -- valor por defecto,
# overridable vía ir.config_parameter (ver data/ir_config_parameter_dian_data.xml). Evidencia
# real (NA0000000049, payslip 944, ZipKey 98e2fdc3): un documento puede quedar "sent" para
# siempre si la DIAN nunca vuelve a dar un veredicto del documento -- sin este límite el cron
# lo reconsulta cada 10 minutos sin fin.
_CRON_RECHECK_MAX_HOURS_DEFAULT = 72


class HrPayslip(models.Model):
    """Nómina electrónica – modelo central con ciclo DIAN completo."""

    _inherit = 'hr.payslip'

    # ──────────────────────────────────────────────────────────────────
    # Campos de estado y trazabilidad DIAN
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('generated', 'XML Generado'),
            ('sent', 'Enviado a DIAN'),
            ('uncertain', 'Envío incierto - requiere conciliación'),
            ('accepted', 'Aceptado por DIAN'),
            ('rejected', 'Rechazado por DIAN'),
        ],
        string='Estado DIAN',
        default='draft',
        copy=False,
        tracking=True,
        help='Estado del documento de nómina electrónica ante la DIAN.\n'
             '• Borrador: aún no se ha generado el XML.\n'
             '• XML Generado: XML construido, firmado y listo para envío.\n'
             '• Enviado a DIAN: transmitido al web service, pendiente respuesta.\n'
             '• Envío incierto: no hubo acuse válido; requiere conciliación.\n'
             '• Aceptado por DIAN: la DIAN validó y aceptó el documento.\n'
             '• Rechazado por DIAN: la DIAN rechazó el documento.',
    )
    l10n_co_ne_cune = fields.Char(
        string='CUNE',
        readonly=True,
        copy=False,
        index=True,
        help='Código Único de Nómina Electrónica. Identificador único '
             'e irrepetible del documento calculado según el algoritmo '
             'SHA-384 definido en el anexo técnico.',
    )
    l10n_co_ne_xml_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='XML Firmado',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='Adjunto que contiene el XML de nómina electrónica firmado '
             'digitalmente con el certificado .p12 de la empresa.',
    )
    l10n_co_ne_dian_request = fields.Text(
        string='Solicitud DIAN',
        readonly=True,
        copy=False,
        help='Petición SOAP/XML completa enviada al servicio web de la '
             'DIAN (SendTestSetAsync/GetStatusZip), guardada ANTES de '
             'enviarla. Sin esto, diagnosticar un rechazo real requiere '
             'reconstruir a ciegas qué se mandó a partir de la '
             'respuesta de error (incidente real 2026-10-04: bug de '
             'TestSetId solo se detectó indirectamente).',
    )
    l10n_co_ne_dian_response = fields.Text(
        string='Respuesta DIAN',
        readonly=True,
        copy=False,
        help='Respuesta completa del servicio web de la DIAN tras el '
             'envío del documento de nómina electrónica.',
    )
    l10n_co_ne_zip_key = fields.Char(
        string='ZipKey DIAN',
        readonly=True,
        copy=False,
        help='Identificador (ZipKey/trackId) devuelto por la DIAN al '
             'enviar el documento. Se usa para consultar el estado del '
             'procesamiento (GetStatusZip).',
    )
    l10n_co_ne_exchange_ids = fields.Many2many(
        comodel_name='l10n.co.ne.exchange',
        relation='l10n_co_ne_exchange_payslip_rel',
        column1='payslip_id', column2='exchange_id',
        string='Historial de intercambios DIAN', readonly=True, copy=False,
    )

    def _ne_response_text(self, value):
        # AUD-DIAN-34 (2026-10-04): este campo es un resumen para la vista
        # del formulario, no evidencia -- la evidencia completa (sobre SOAP
        # y ZIP de respuesta íntegros, sin truncar) vive en
        # l10n.co.ne.exchange. Un SendTestSetAsync de 4 nóminas puede traer
        # un ZIP base64 de varios MB; meterlo entero aquí infla el registro
        # del payslip sin necesidad.
        if isinstance(value, bytes):
            value = value.decode('utf-8', errors='replace')
        return (value or '')[:5000]

    def _ne_store_exchange(self, operation, endpoint, response, manifest=None,
                           queried_zip_key=None, parent_exchange=None,
                           unidentified_count=0):
        """Guarda evidencia completa (siempre, un registro histórico por intento) y
        actualiza el resumen visible del documento SOLO si de verdad cambió.

        H-012 (2026-10-06): un documento 'sent' sin resolver que el cron reconsulta cada 10
        minutos escribía aquí sin condición -- aunque la respuesta de la DIAN fuera
        exactamente la misma de la reconsulta anterior, write_date se actualizaba igual.
        Eso hacía parecer que el documento se "tocaba" constantemente sin ningún cambio
        real, y ensuciaba el orden por write_date que usa _cron_recheck_sent_status() para
        priorizar el lote.
        """
        exchange = self.env['l10n.co.ne.exchange'].create_exchange(
            self.company_id, operation, endpoint, response, self, manifest,
            queried_zip_key=queried_zip_key, parent_exchange=parent_exchange,
            unidentified_count=unidentified_count,
        )
        new_request = self._ne_response_text(response.get('RawRequest'))
        new_response = self._ne_response_text(response.get('RawResponse'))
        changed = self.filtered(
            lambda slip: slip.l10n_co_ne_dian_request != new_request
            or slip.l10n_co_ne_dian_response != new_response
        )
        if changed:
            changed.write({
                'l10n_co_ne_dian_request': new_request,
                'l10n_co_ne_dian_response': new_response,
            })
        return exchange

    @staticmethod
    def _ne_cune_candidates(result):
        """Extrae candidatos de CUNE de un resultado, sin confundirlos con IDs SOAP.

        AUD-DIAN-34 (2026-10-04): evidencia real (GetStatusZip AUTORIZADO,
        nómina SME-10) confirma que el CUNE del documento original viaja en
        ``cac:DocumentResponse/cac:DocumentReference/cbc:UUID`` dentro del
        ApplicationResponse -- ver ``soap_client.extract_document_cunes``.
        """
        candidates = set()
        for key in ('XmlDocumentKey', 'CUNE', 'DocumentKey'):
            value = result.get(key)
            if value:
                candidates.add(value.strip())
        application = result.get('ApplicationResponse') or ''
        if application:
            candidates.update(soap_client.extract_document_cunes(application))
        return candidates

    @staticmethod
    def _ne_number_candidates(result):
        """Extrae el NÚMERO de negocio del documento original (no es CUNE).

        ``cac:DocumentResponse/cac:DocumentReference/cbc:ID`` -- solo se usa
        como respaldo cuando DIAN no entrega CUNE (ver
        ``soap_client.extract_document_numbers``).
        """
        application = result.get('ApplicationResponse') or ''
        if not application:
            return set()
        return soap_client.extract_document_numbers(application)

    @staticmethod
    def _ne_is_set_level_status(response):
        """True si la respuesta de GetStatusZip es sobre el SET de pruebas completo, no
        sobre el documento individual consultado.

        H-012 (2026-10-06): evidencia real (NA0000000049, payslip 944, ZipKey 98e2fdc3) --
        GetStatusZip respondió StatusCode="2", IsValid="false",
        StatusDescription="Set de prueba con identificador e07c1748... se encuentra
        Aceptado.", sin XmlDocumentKey ni ApplicationResponse (ningún dato que identifique
        el documento). Esa combinación (StatusCode 2 + IsValid false + cero datos de
        documento) es la FORMA de una respuesta de nivel set, no una hipótesis sobre por
        qué la DIAN respondió así -- no se asume la causa (Tech Lead: "mi hipótesis no está
        confirmada, el fix no debe depender de ella").
        """
        if str(response.get('StatusCode', '')).strip() != '2':
            return False
        if str(response.get('IsValid', '')).lower() == 'true':
            return False
        return not response.get('XmlDocumentKey') and not response.get('ApplicationResponse')

    def _ne_match_dian_results(self, results, manifest):
        """Asocia resultados solo cuando la evidencia identifica un documento.

        Reglas confirmadas con Tech Lead (2026-10-04 y 2026-10-05, esta
        última con evidencia real de una respuesta GetStatusZip AUTORIZADA
        de la DIAN -- nómina SME-10, StatusCode 00):
        (a) match estricto por CUNE (XmlDocumentKey o
            DocumentReference/UUID) cuando DIAN lo entrega -- nunca por
            nombre de archivo, que DIAN puede omitir o repetir;
        (b) si DIAN no entrega CUNE pero sí el NÚMERO del documento
            (DocumentReference/ID), se empareja por
            ``l10n_co_ne_consecutive`` SOLO si ese número identifica
            exactamente 1 documento en el manifiesto;
        (c) si DIAN no entrega NINGÚN identificador (ni CUNE ni número) y
            el manifiesto de este ZipKey tiene exactamente 1 documento, el
            resultado solo puede ser de ese documento -- se aplica;
        (d) en cualquier otro caso (identificador presente pero sin
            coincidencia única, o sin identificador con >1 documento), no
            se cambia ningún estado -- se cuenta como "sin identificar"
            (valor de retorno ``unidentified``) para que quede visible en
            vez de adivinar.
        Un identificador que DIAN sí entrega pero que no coincide con nada
        del manifiesto NUNCA cae al siguiente nivel -- sería una
        contradicción, no una ausencia de dato.
        """
        by_cune = {}
        by_number = {}
        for line in manifest:
            if line.cune:
                by_cune.setdefault(line.cune, []).append(line)
            number = line.payslip_id.l10n_co_ne_consecutive
            if number:
                by_number.setdefault(number, []).append(line)
        matched = {}
        ambiguous = set()
        unidentified = 0
        for result in results:
            cune_candidates = self._ne_cune_candidates(result)
            number_candidates = self._ne_number_candidates(result)
            has_identifier = bool(cune_candidates or number_candidates)
            if cune_candidates:
                lines = [line for candidate in cune_candidates for line in by_cune.get(candidate, [])]
            elif number_candidates:
                lines = [line for candidate in number_candidates for line in by_number.get(candidate, [])]
            elif len(manifest) == 1:
                lines = list(manifest)
            else:
                unidentified += 1
                continue
            if len(lines) != 1:
                if has_identifier:
                    unidentified += 1
                continue
            line = lines[0]
            target = line.payslip_id
            # El resultado aplica exclusivamente a la misma versión firmada.
            current_xml = base64.b64decode(target.l10n_co_ne_xml_attachment_id.datas) if target.l10n_co_ne_xml_attachment_id else b''
            if target.l10n_co_ne_cune != line.cune or hashlib.sha256(current_xml).hexdigest() != line.sha256:
                continue
            if target.id in matched:
                ambiguous.add(target.id)
            else:
                matched[target.id] = result
        return matched, ambiguous, unidentified

    l10n_co_ne_is_salarial = fields.Boolean(
        string='Es Salarial (Bonificaciones)',
        default=True,
        help='Determina si las bonificaciones de esta nomina constituyen salario '
             'para el calculo de seguridad social y deducciones.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Campos para Notas de Ajuste
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_is_adjustment = fields.Boolean(
        string='Es Nota de Ajuste',
        default=False,
        copy=False,
        help='Indica si este documento es una nota de ajuste (reemplazo '
             'o eliminación) de una nómina electrónica previamente '
             'aceptada por la DIAN.',
    )
    l10n_co_ne_hab_set_id = fields.Char(
        string='Set de Habilitación DIAN',
        copy=False,
        index=True,
        help='TestSetId con el que se preparó este documento durante la habilitación '
             'automática. Permite que un set nuevo ignore los documentos de sets anteriores.',
    )
    l10n_co_ne_adjustment_ref_cune = fields.Char(
        string='CUNE Nómina Original',
        copy=False,
        help='CUNE del documento de nómina electrónica original al que '
             'hace referencia esta nota de ajuste.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Consecutivo de nómina electrónica
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_consecutive = fields.Char(
        string='Consecutivo NE',
        readonly=True,
        copy=False,
        help='Consecutivo interno del documento de nómina electrónica '
             'asignado automáticamente al generar el XML. Formato: '
             'PREFIJO + número secuencial.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Liquidación de Contrato (doc 20 §6)
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_liquidacion_cause = fields.Selection(
        selection=[
            ('justa_causa', 'Despido con Justa Causa'),
            ('sin_justa_causa', 'Despido sin Justa Causa'),
            ('renuncia', 'Renuncia Voluntaria'),
            ('mutuo_acuerdo', 'Mutuo Acuerdo'),
            ('fin_obra', 'Terminación de Obra o Labor'),
            ('muerte', 'Muerte del Trabajador'),
        ],
        string='Causa de Retiro',
        copy=False,
        help='Causa de terminación del contrato laboral, solo aplicable a '
             'payslips de estructura Liquidación de Contrato. La lee '
             'directamente CO_LIQ_INDEMNIZACION (condition_python: solo '
             'aplica indemnización si es "sin_justa_causa") -- también se '
             'guarda para trazabilidad y reportes.',
    )

    # ──────────────────────────────────────────────────────────────────
    # SQL Constraints
    # ──────────────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'l10n_co_ne_cune_unique',
            'UNIQUE(l10n_co_ne_cune)',
            'El CUNE debe ser único. Ya existe un documento de nómina '
            'electrónica con este CUNE.',
        ),
        (
            'l10n_co_ne_consecutive_company_unique',
            'UNIQUE(l10n_co_ne_consecutive, company_id)',
            'El consecutivo de nómina electrónica debe ser único por empresa.',
        ),
    ]

    # ──────────────────────────────────────────────────────────────────
    # Validaciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('l10n_co_ne_is_adjustment', 'l10n_co_ne_adjustment_ref_cune')
    def _check_adjustment_ref_cune(self):
        """Si es nota de ajuste, el CUNE de referencia es obligatorio."""
        for payslip in self:
            if (
                payslip.l10n_co_ne_is_adjustment
                and not payslip.l10n_co_ne_adjustment_ref_cune
            ):
                raise ValidationError(_(
                    'Para una nota de ajuste debe indicar el CUNE de la '
                    'nómina electrónica original. Nómina: %s',
                    payslip.number or payslip.name,
                ))

    # ══════════════════════════════════════════════════════════════════
    # ACCIONES PRINCIPALES
    # ══════════════════════════════════════════════════════════════════

    def action_generate_ne_xml(self):
        """
        Genera el XML de nómina electrónica firmado.

        Flujo:
        1. Valida prerequisitos (nómina confirmada, datos completos).
        2. Asigna consecutivo NE si no existe.
        3. Recopila datos del payslip (``_collect_payslip_data``).
        4. Construye el XML con ``nomina_xml_builder``.
        5. Calcula el CUNE con ``cune_service``.
        6. Inserta el CUNE en el XML.
        7. Firma digitalmente con ``xml_signer``.
        8. Crea ``ir.attachment`` con el XML firmado.
        9. Actualiza estado a ``generated``.
        """
        self.ensure_one()
        self._validate_ne_prerequisites()

        # Asignar consecutivo oficial si no tiene uno, si es el temporal
        # PRE-NOM, o si tiene un prefijo que no corresponde a este tipo de
        # documento (AUD-DIAN-34 2026-10-04: ver _ne_expected_prefix()).
        expected_prefix = self._ne_expected_prefix()
        if (
            not self.l10n_co_ne_consecutive
            or not self.l10n_co_ne_consecutive.startswith(expected_prefix)
        ):
            self.l10n_co_ne_consecutive = self._get_next_ne_consecutive()


        # Recopilar datos
        payslip_data = self._collect_payslip_data()

        # Construir XML sin firmar
        # NOTA (doc 24 §17): corte a builder v2 (dict_to_xml) restaurado e
        # instalado en staging_produccion 2026-09-12 por decisión explícita
        # de David -- riesgo aceptado conscientemente de usar este builder
        # para los envíos reales de habilitación ante la DIAN, ANTES de que
        # ese proceso ocurra. Ver 00_ESTADO_ACTUAL.md y doc 24 §17.
        if self.l10n_co_ne_is_adjustment:
            xml_bytes = nomina_xml_builder.build_nota_ajuste_v2(payslip_data)
        else:
            xml_bytes = nomina_xml_builder.build_nomina_individual_v2(payslip_data)

        # Calcular CUNE (11 campos según Anexo Técnico, incluye Software-Pin)
        company = self.company_id
        cune_value, _raw = cune_service.compute_cune(
            num_ne=self.l10n_co_ne_consecutive,
            fec_ne=payslip_data['informacion_general']['FechaGen'],
            hor_ne=payslip_data['informacion_general']['HoraGen'],
            val_dev=payslip_data['totales']['DevengadosTotal'],
            val_ded=payslip_data['totales']['DeduccionesTotal'],
            val_tol=payslip_data['totales']['ComprobanteTotal'],
            nit_ne=dian_utils.clean_nit(company.vat),
            doc_trab=self.employee_id.identification_id or '',
            cl_ne='103' if self.l10n_co_ne_is_adjustment else '102',
            software_pin=company.l10n_co_ne_operation_mode_ids.software_pin or '',
            tipo_amb=company.l10n_co_ne_environment or '2',
        )
        self.l10n_co_ne_cune = cune_value

        # Insertar CUNE y CodigoQR en el XML
        xml_bytes = self._ne_insert_cune_and_qr(xml_bytes, cune_value)

        # Firmar XML con XAdES-BES
        private_key, cert_pem, cert_der, cert_obj, cert_chain = (
            xml_signer.load_from_certificate(company._get_ne_certificate())
        )
        signed_xml = xml_signer.sign_xml(
            xml_bytes=xml_bytes,
            private_key=private_key,
            cert_pem=cert_pem,
            cert_der=cert_der,
            cert_obj=cert_obj,
            cert_chain=cert_chain,
        )

        # Crear attachment (signed_xml ya es bytes)
        filename = self._get_ne_xml_filename()
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(signed_xml),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/xml',
        })
        self.l10n_co_ne_xml_attachment_id = attachment
        self.l10n_co_ne_state = 'generated'

        _logger.info(
            'XML de nómina electrónica generado para %s (CUNE: %s)',
            self.number or self.name,
            cune_value,
        )
        return True

    def action_payslip_done(self):
        """
        Sobrescribe la confirmación de la nómina para asignar el consecutivo
        temporal PRE-NOM al número del payslip en Odoo.
        """
        res = super(HrPayslip, self).action_payslip_done()
        for rec in self:
            company = rec.company_id
            if company.l10n_co_ne_pre_sequence_id:
                if not rec.l10n_co_ne_consecutive or rec.l10n_co_ne_consecutive.startswith('PRE-NOM'):
                    temporal_number = company.l10n_co_ne_pre_sequence_id.next_by_id()
                    rec.number = temporal_number
                    rec.l10n_co_ne_consecutive = temporal_number
        return res

    def action_send_ne_dian(self):

        """
        Envía el XML firmado al servicio web de la DIAN.

        Flujo:
        1. Valida que el XML esté generado.
        2. Lee el certificado digital de la empresa.
        3. Llama a ``soap_client.send_nomina_sync()`` para transmitir.
        4. Almacena la respuesta de la DIAN.
        5. Actualiza estado según resultado (accepted/rejected).
        """
        self.ensure_one()
        if self.l10n_co_ne_state not in ('generated', 'rejected'):
            raise UserError(_(
                'Solo puede enviar a la DIAN documentos en estado '
                '"XML Generado" o "Rechazado". Estado actual: %s',
                dict(self._fields['l10n_co_ne_state'].selection).get(
                    self.l10n_co_ne_state, self.l10n_co_ne_state
                ),
            ))

        if not self.l10n_co_ne_xml_attachment_id:
            raise UserError(_(
                'No se encontró el XML firmado. Genere el XML antes de '
                'intentar el envío a la DIAN.'
            ))

        company = self.company_id
        self._validate_company_ne_config(company)

        if company.l10n_co_ne_demo_mode:
            # Doc 37: Modo Demo -- equivalente a _send_bill_sync() del
            # l10n_co_dian nativo (Facturación). El XML ya se construyó,
            # calculó su CUNE y se firmó localmente en
            # action_generate_ne_xml() -- este modo únicamente evita la
            # transmisión real SendNominaSync al webservice de la DIAN.
            # No aplica a action_send_test_set() (habilitación real).
            self.l10n_co_ne_state = 'accepted'
            if self.l10n_co_ne_consecutive:
                self.number = self.l10n_co_ne_consecutive
            self.message_post(
                body=_(
                    'Nómina electrónica %s validada localmente en Modo '
                    'Demo (sin transmisión real a la DIAN).',
                    self.number or self.name,
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            return True

        # Leer XML firmado del attachment (como bytes)
        xml_content = base64.b64decode(
            self.l10n_co_ne_xml_attachment_id.datas
        )

        # Cargar certificado para firmar el sobre SOAP
        private_key, cert_pem, cert_der, _cert_obj, _cert_chain = (
            xml_signer.load_from_certificate(company._get_ne_certificate())
        )

        # Determinar endpoint según ambiente -- único punto, ver ResCompany._ne_dian_endpoint()
        endpoint = company._ne_dian_endpoint()

        # Enviar a DIAN vía SendNominaSync
        filename = self._get_ne_xml_filename()
        response = soap_client.send_nomina_sync(
            xml_bytes=xml_content,
            filename=filename,
            private_key=private_key,
            cert_pem=cert_pem,
            endpoint=endpoint,
            timeout=company._ne_config_int_param(
                'l10n_co_nomina_electronica.soap_timeout_seconds', soap_client.SOAP_TIMEOUT),
        )

        # Procesar respuesta DIAN y preservar el payload exacto del intento.
        self._ne_store_exchange('send_sync', endpoint, response, [{
            'payslip': self, 'filename': filename, 'xml': xml_content,
        }])
        zip_key = response.get('ZipKey', '')
        if zip_key:
            self.l10n_co_ne_zip_key = zip_key
        is_valid = response.get('IsValid', '') == 'true'

        if is_valid:
            self.l10n_co_ne_state = 'accepted'
            if self.l10n_co_ne_consecutive:
                self.number = self.l10n_co_ne_consecutive
            _logger.info(
                'Nómina electrónica %s ACEPTADA por DIAN (CUNE: %s)',
                self.number or self.name,
                self.l10n_co_ne_cune,
            )

        else:
            self.l10n_co_ne_state = 'rejected'
            error_messages = response.get('ErrorMessages', [])
            detail = '; '.join(error_messages) if error_messages else response.get('ErrorMessage', 'Sin detalle')
            _logger.warning(
                'Nómina electrónica %s RECHAZADA por DIAN. Errores: %s',
                self.number or self.name,
                detail,
            )
            
            # Diagnóstico Inteligente para el Chatter
            diagnosis = "Ocurrió un error general de validación con el webservice de la DIAN."
            links = ""
            detail_lower = detail.lower()
            
            if 'nit' in detail_lower or 'documento' in detail_lower or 'identificacion' in detail_lower:
                diagnosis = "El número o tipo de identificación del trabajador o del empleador contiene caracteres inválidos o no está registrado."
                links = f'<br/>🔗 <a href="/odoo/hr.employee/{self.employee_id.id}">Abrir ficha del empleado para corregir</a>'
            elif 'correo' in detail_lower or 'email' in detail_lower:
                diagnosis = "El correo electrónico de trabajo del empleado falta o tiene un formato incorrecto."
                links = f'<br/>🔗 <a href="/odoo/hr.employee/{self.employee_id.id}">Corregir correo en ficha de empleado</a>'
            elif 'cuenta' in detail_lower or 'banco' in detail_lower or 'metodo' in detail_lower:
                diagnosis = "La información bancaria o método de pago del trabajador contiene datos erróneos o incompletos."
                links = f'<br/>🔗 <a href="/odoo/hr.contract/{self.contract_id.id}">Revisar contrato para corregir información bancaria</a>'
            elif 'salario' in detail_lower or 'ibc' in detail_lower or 'minimo' in detail_lower:
                diagnosis = "El salario base o el ingreso base de cotización (IBC) reportado presenta discrepancias matemáticas o de ley."
                links = f'<br/>🔗 <a href="/odoo/hr.contract/{self.contract_id.id}">Revisar salario en el contrato</a>'

            body = (
                f'❌ <b>Nómina rechazada por la DIAN</b><br/>'
                f'Consecutivo utilizado: <b>{self.l10n_co_ne_consecutive}</b><br/><br/>'
                f'📋 <b>Diagnóstico de Corrección:</b><br/>'
                f'{diagnosis}{links}<br/><br/>'
                f'<details>'
                f'<summary>🔧 Detalle técnico de la DIAN</summary>'
                f'<pre>{detail}</pre>'
                f'</details><br/>'
                f'Por favor corrija el dato y use <b>"Enviar y Procesar"</b> para retransmitir con el mismo consecutivo.'
            )
            
            self.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_note'
            )

        return True

    def action_send_payslip_email(self, template=None):
        """Genera el PDF del comprobante y lo envía por correo al empleado.

        Args:
            template: Plantilla de correo (mail.template). Si es omitido,
                      busca la primera plantilla disponible para el modelo hr.payslip.
        """
        self.ensure_one()
        if not self.employee_id.work_email:
            raise UserError(_('El empleado %s no tiene correo electrónico de trabajo configurado.') % self.employee_id.name)

        if not template:
            template = self.env['mail.template'].search([('model', '=', 'hr.payslip')], limit=1)
            if not template:
                raise UserError(_('No se encontró ninguna plantilla de correo configurada para el modelo de nómina.'))

        # 1. Renderizar el reporte PDF del recibo
        report = self.env.ref('l10n_co_nomina_electronica.action_report_payslip_ne', raise_if_not_found=False)
        if not report:
            report = self.env.ref('hr_payroll.action_report_payslip', raise_if_not_found=False)

        attachment_ids = []
        if report:
            pdf_content, _report_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report.id, [self.id])
            pdf_name = f"{self.number or self.name or 'Recibo_Nomina'}.pdf"
            attachment = self.env['ir.attachment'].create({
                'name': pdf_name,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'hr.payslip',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            attachment_ids.append(attachment.id)

        # 2. Enviar el correo electrónico con el PDF adjunto
        email_values = {
            'email_to': self.employee_id.work_email,
            'attachment_ids': [(6, 0, attachment_ids)] if attachment_ids else False,
        }
        template.send_mail(self.id, force_send=True, email_values=email_values)

        _logger.info(
            'Comprobante de nomina %s enviado por correo electrónico al empleado %s (%s).',
            self.number or self.name,
            self.employee_id.name,
            self.employee_id.work_email,
        )
        return True

    def action_create_adjustment(self):
        """
        Abre el asistente para crear una nota de ajuste referenciando
        el CUNE de esta nómina electrónica.

        Solo disponible si la nómina fue aceptada por la DIAN.
        """
        self.ensure_one()
        if self.l10n_co_ne_state != 'accepted':
            raise UserError(_(
                'Solo puede crear notas de ajuste para nóminas aceptadas '
                'por la DIAN.'
            ))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Crear Nota de Ajuste de Nómina'),
            'res_model': 'hr.payslip',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_l10n_co_ne_is_adjustment': True,
                'default_l10n_co_ne_adjustment_ref_cune': self.l10n_co_ne_cune,
                'default_employee_id': self.employee_id.id,
                'default_contract_id': self.contract_id.id,
                'default_struct_id': self.struct_id.id,
                'default_date_from': str(self.date_from),
                'default_date_to': str(self.date_to),
            },
        }

    # ──────────────────────────────────────────────────────────────────
    # Procesamiento masivo
    # ──────────────────────────────────────────────────────────────────

    def action_mass_generate_ne_xml(self):
        """Genera XML de nómina electrónica para múltiples nóminas."""
        records = self.filtered(
            lambda p: p.state == 'done'
            and p.l10n_co_ne_state in ('draft', False)
        )
        if not records:
            raise UserError(_('No hay nóminas confirmadas pendientes de generar XML.'))

        errors = []
        for payslip in records:
            try:
                payslip.action_generate_ne_xml()
            except Exception as e:
                errors.append(f'{payslip.number or payslip.name}: {e}')

        if errors:
            raise UserError(_(
                'Se generaron %d de %d XMLs. Errores:\n%s',
                len(records) - len(errors),
                len(records),
                '\n'.join(errors),
            ))
        return True

    def action_mass_send_ne_dian(self):
        """Envía múltiples XMLs firmados a la DIAN."""
        records = self.filtered(
            lambda p: p.l10n_co_ne_state in ('generated', 'rejected')
        )
        if not records:
            raise UserError(_('No hay nóminas con XML generado pendientes de envío.'))

        errors = []
        for payslip in records:
            try:
                payslip.action_send_ne_dian()
            except Exception as e:
                errors.append(f'{payslip.number or payslip.name}: {e}')

        if errors:
            raise UserError(_(
                'Se enviaron %d de %d nóminas. Errores:\n%s',
                len(records) - len(errors),
                len(records),
                '\n'.join(errors),
            ))
        return True

    # ──────────────────────────────────────────────────────────────────
    # Integración SendTestSetAsync / GetStatusZip
    # ──────────────────────────────────────────────────────────────────

    def action_send_test_set(self):
        """Envía el set de pruebas a la DIAN (SendTestSetAsync).

        Agrupa las nóminas en 'generated' (primer envío) o 'uncertain'
        (envío previo sin acuse válido -- el XML firmado ya existe y es
        reenviable tal cual, sin regenerar) y las envía como un set de
        pruebas al endpoint de habilitación.
        """
        records = self.filtered(
            lambda p: p.l10n_co_ne_state in ('generated', 'uncertain')
        )
        if not records:
            raise UserError(_(
                'No hay nóminas con XML generado, ni en envío incierto, '
                'para enviar como set de pruebas.'
            ))

        # La DIAN solo procesa UN documento por ZIP (Anexo 9.2; verificado 2026-10-04: de un
        # ZIP con 4 XML solo evaluó el primero y los otros nunca quedaron registrados).
        # Cada documento viaja en su propio ZIP y queda con su propio ZipKey.
        if len(records) > 1:
            results = [record.action_send_test_set() for record in records]
            sent = records.filtered(lambda p: p.l10n_co_ne_state == 'sent')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Set de Pruebas Enviado'),
                    'message': _('Se enviaron %(sent)d de %(total)d documentos (un ZIP por documento).',
                                 sent=len(sent), total=len(records)),
                    'type': 'success' if len(sent) == len(records) else 'warning',
                    'sticky': True,
                },
            }

        company = records[0].company_id
        self._validate_company_ne_config(company)

        if not company.l10n_co_ne_certification_process:
            raise UserError(_(
                'Debe activar "Proceso de Certificación" en Ajustes > '
                'Nómina antes de enviar el set de pruebas a la DIAN.'
            ))

        if not company.l10n_co_ne_operation_mode_ids.test_set_id:
            raise UserError(_('Debe configurar el ID de Pruebas en el Modo de Operación de la compañía para enviar el set de pruebas.'))

        # Collect all signed XMLs
        # AUD-DIAN-34 (2026-10-04): si el SoftwareID/TestSetId de la
        # compañía cambió (ej. David se re-registró en el portal DIAN)
        # DESPUÉS de que el XML ya se generó y firmó, el SoftwareID
        # embebido queda desactualizado -- enviarlo igual mezcla un
        # SoftwareID viejo con un TestSetId nuevo, combinación inválida
        # que la DIAN rechaza (StatusCode 2). Pasó real hoy: costó
        # varios ciclos manuales de regenerar antes de notarlo.
        current_software_id = (
            company.l10n_co_ne_operation_mode_ids.software_id or ''
        ).encode()
        xml_files = {}
        manifest = []
        stale = []
        for payslip in records:
            if payslip.l10n_co_ne_xml_attachment_id:
                filename = payslip._get_ne_xml_filename()
                xml_bytes = base64.b64decode(payslip.l10n_co_ne_xml_attachment_id.datas)
                if current_software_id and current_software_id not in xml_bytes:
                    stale.append(payslip.name)
                    continue
                xml_files[filename] = xml_bytes
                manifest.append({
                    'payslip': payslip,
                    'filename': filename,
                    'xml': xml_bytes,
                })

        if stale:
            raise UserError(_(
                'El SoftwareID/TestSetId de la compañía cambió desde '
                'que se generó el XML de estas nóminas -- regénerelas '
                'antes de enviar (botón "Generar XML" o reiniciar el '
                'proceso de habilitación):\n%s',
                '\n'.join(stale),
            ))

        if not xml_files:
            raise UserError(_('No se encontraron XMLs firmados en las nóminas seleccionadas.'))

        # Load certificate
        private_key, cert_pem, cert_der, _cert_obj, _cert_chain = (
            xml_signer.load_from_certificate(company._get_ne_certificate())
        )

        # Send test set -- SIEMPRE habilitación (el set de pruebas es un concepto propio de
        # ese ambiente), sin importar l10n_co_ne_environment de la compañía.
        endpoint = company._ne_dian_endpoint(environment='2')
        response = soap_client.send_test_set_async(
            xml_files=xml_files,
            test_set_id=company.l10n_co_ne_operation_mode_ids.test_set_id,
            private_key=private_key,
            cert_pem=cert_pem,
            endpoint=endpoint,
            timeout=company._ne_config_int_param(
                'l10n_co_nomina_electronica.soap_timeout_seconds', soap_client.SOAP_TIMEOUT),
        )

        zip_key = response.get('ZipKey', '')
        ack_valid = bool(zip_key and zip_key.strip()) and response.get('HttpStatus', 0) < 400 \
            and response.get('HttpStatus', 0) >= 200 and not response.get('SOAPFault') \
            and response.get('StatusCode') not in ('CONNECTION_ERROR', 'PARSE_ERROR', 'ERROR', '99') \
            and not response.get('TransportError')
        records._ne_store_exchange(
            'send_test_set', endpoint, response, manifest,
        )
        # Un timeout o acuse sin ZipKey es incierto: queda evidencia, pero no
        # se simula un envío exitoso ni se programa reintento automático.
        if not ack_valid:
            records.write({'l10n_co_ne_state': 'uncertain'})
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'title': _('Set de Pruebas no confirmado'),
                    'message': _('La DIAN no confirmó un ZipKey válido. El intento quedó registrado para conciliación.'),
                    'type': 'warning', 'sticky': True,
                },
            }
        # AUD-DIAN-34 (2026-09-14): antes no se persistia el ZipKey real
        # devuelto por SendTestSetAsync ni se marcaba 'sent' -- accion_
        # check_dian_status() caia a usar el CUNE como trackId (formato
        # distinto), y GetStatusZip lo rechazaba con StatusCode 89
        # "Formato trackId invalido" en el 100% de los casos reales.
        records.write({
            'l10n_co_ne_zip_key': zip_key,
            'l10n_co_ne_state': 'sent',
        })
        _logger.info(
            'Set de pruebas enviado: %d documentos. ZipKey: %s',
            len(xml_files), zip_key,
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Set de Pruebas Enviado'),
                'message': _('Se enviaron %d documentos. ZipKey: %s') % (len(xml_files), zip_key),
                'type': 'success',
                'sticky': True,
            },
        }

    def action_regenerate_ne_xml(self):
        """Regenera el XML con consecutivo y CUNE nuevos (no para documentos enviados/aceptados).

        Un documento rechazado o con el SoftwareID/TestSetId desactualizado no se puede reenviar
        tal cual: la DIAN devolvería el mismo veredicto viejo (regla 90, "procesado anteriormente").
        """
        for slip in self:
            if slip.l10n_co_ne_state in ('sent', 'accepted'):
                raise UserError(_(
                    'No se puede regenerar el XML de %s: ya fue enviado o aceptado por la DIAN.',
                    slip.name,
                ))
            slip.write({
                'l10n_co_ne_state': 'draft',
                'l10n_co_ne_consecutive': False,
                'l10n_co_ne_cune': False,
                'l10n_co_ne_zip_key': False,
                'l10n_co_ne_xml_attachment_id': False,
            })
            slip.action_generate_ne_xml()
        return True

    def action_check_dian_status(self):
        """Consulta una vez por ZipKey y distribuye solo resultados inequívocos."""
        if not self:
            return True
        companies = self.mapped('company_id')
        if len(companies) != 1:
            raise UserError(_('Seleccione nóminas de una sola compañía para consultar DIAN.'))
        company = companies
        missing = self.filtered(lambda slip: not slip.l10n_co_ne_zip_key)
        if missing:
            raise UserError(_('Hay nóminas sin ZipKey; no se consultan por CUNE porque no es un trackId válido.'))
        private_key, cert_pem, cert_der, _cert_obj, _cert_chain = (
            xml_signer.load_from_certificate(company._get_ne_certificate())
        )

        endpoint = company._ne_dian_endpoint()
        timeout = company._ne_config_int_param(
            'l10n_co_nomina_electronica.soap_timeout_seconds', soap_client.SOAP_TIMEOUT)

        summaries = []
        for track_id in set(self.mapped('l10n_co_ne_zip_key')):
            records = self.filtered(lambda slip: slip.l10n_co_ne_zip_key == track_id)
            response = soap_client.get_status_zip(
                track_id=track_id, private_key=private_key, cert_pem=cert_pem,
                endpoint=endpoint, timeout=timeout,
            )
            # Consultas usan el manifiesto del último envío del mismo ZipKey;
            # nunca se reconstruye desde el XML actual de la nómina.
            sent = self.env['l10n.co.ne.exchange'].search([
                ('company_id', '=', company.id), ('operation', '=', 'send_test_set'),
                ('zip_key', '=', track_id)], order='id desc', limit=1)
            manifest = sent.document_ids
            # El emparejamiento se calcula ANTES de guardar la evidencia
            # para que "sin identificar" quede visible también en el
            # historial, no solo en la notificación de la sesión actual.
            matches, ambiguous, unidentified = records._ne_match_dian_results(
                response.get('DianResponses', []), manifest)
            # H-012 (2026-10-06): una respuesta de nivel SET (ver
            # _ne_is_set_level_status) nunca resuelve un documento, aunque
            # _ne_match_dian_results la haya emparejado por la regla "manifiesto de 1
            # documento, sin identificador" (pensada para un resultado genuino del
            # documento sin CUNE, no para un mensaje que ni siquiera es sobre el
            # documento) -- se descarta el match explícitamente, nunca se infiere
            # accepted/rejected de ella.
            set_level = self._ne_is_set_level_status(response)
            if set_level:
                matches = {}
            records._ne_store_exchange('get_status_zip', endpoint, response,
                queried_zip_key=track_id, parent_exchange=sent,
                unidentified_count=unidentified)
            for slip in records:
                result = matches.get(slip.id)
                if not result or slip.id in ambiguous:
                    continue
                valid = str(result.get('IsValid', '')).lower() == 'true'
                # AUD-DIAN-34 (2026-10-04): no existe en el Anexo Técnico
                # una tabla exhaustiva de StatusCode de GetStatusZip -- solo
                # el ejemplo real de rechazo que sí documenta (IsValid=false,
                # StatusCode=99, con ErrorMessage poblado de reglas NIE/ZB).
                # No se supone ningún otro código como rechazo: "fuera de
                # ('','00','0','90')" degradaba a 'rejected' estados que
                # solo estaban pendientes/incompletos, sin evidencia de
                # rechazo real de la DIAN.
                is_rejection = (
                    str(result.get('StatusCode', '')).strip() == '99'
                    or bool(result.get('ErrorMessages'))
                )
                # Una consulta pendiente/no identificada nunca degrada un
                # accepted. Rechazo terminal individual sí queda registrado.
                if valid and slip.l10n_co_ne_state != 'accepted':
                    slip.l10n_co_ne_state = 'accepted'
                    if slip.l10n_co_ne_consecutive:
                        slip.number = slip.l10n_co_ne_consecutive
                elif not valid and is_rejection and slip.l10n_co_ne_state != 'accepted':
                    slip.l10n_co_ne_state = 'rejected'
            summary = response.get('StatusDescription') or response.get('StatusMessage') or _('Sin respuesta')
            if set_level:
                # H-012 (2026-10-06, confirmado con el portal DIAN por David): esta
                # respuesta no es un estado transitorio que una reconsulta futura vaya a
                # resolver -- el set de pruebas ya quedó "Habilitado" y la DIAN no procesa
                # más documentos de él. Se marca 'uncertain' de inmediato (nunca se espera
                # al plazo de _CRON_RECHECK_MAX_HOURS_DEFAULT para un motivo ya conocido);
                # un 'accepted' ya confirmado antes nunca se degrada.
                to_mark = records.filtered(lambda slip: slip.l10n_co_ne_state == 'sent')
                for slip in to_mark:
                    slip.message_post(body=_(
                        'La DIAN respondió sobre el SET de pruebas, no sobre este '
                        'documento: "%(desc)s". El set ya está "Habilitado" y no procesa '
                        'más documentos de prueba -- este documento no se va a resolver '
                        'en este set. Revise el estado de habilitación de la compañía '
                        '(Ajustes > Nómina) antes de seguir reintentando.',
                        desc=summary,
                    ))
                to_mark.write({'l10n_co_ne_state': 'uncertain'})
                summary = _(
                    '%(summary)s (respuesta del SET de pruebas: ya está "Habilitado" y '
                    'no va a resolver este documento -- marcado "Envío incierto")',
                    summary=summary,
                )
            elif unidentified:
                summary = _(
                    '%(summary)s (%(n)d resultado(s) sin identificar -- '
                    'requieren conciliación manual, ver Historial DIAN)',
                    summary=summary, n=unidentified,
                )
            summaries.append(summary)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Estado DIAN'),
                'message': ' | '.join(summaries),
                'type': 'success' if any(s.l10n_co_ne_state == 'accepted' for s in self) else 'warning',
                'sticky': True,
            },
        }

    @api.model
    def _cron_recheck_sent_status(self):
        """Reconsulta documentos 'sent' que nadie volvió a consultar a mano (Ronda 1 DIAN,
        2026-10-05): 5 nóminas aceptadas en segundos quedaron en 'sent' durante 15 min porque
        nadie hizo clic en "Consultar Estado". El motor de habilitación sí reconsulta lo suyo
        (su propio cron en l10n_co_ne_habilitacion.py); el envío normal no tenía nada equivalente.

        No duplica la lógica SOAP: reutiliza action_check_dian_status() tal cual, agrupado por
        ZipKey para no repetir una misma consulta por cada nómina del mismo envío. Aislamiento:
        por compañía (ya lo exige action_check_dian_status), por lote acotado
        (_CRON_RECHECK_BATCH_LIMIT), y un ZipKey con error se registra y no frena a los demás.

        H-012 (2026-10-06): un documento que la DIAN nunca resuelve (evidencia real:
        NA0000000049) se reconsultaba cada 10 minutos para siempre. Dos ajustes:
        (1) pasado _CRON_RECHECK_MAX_HOURS_DEFAULT (u override), el documento sale del cron
        y queda 'uncertain' -- el botón "Consultar Estado" sigue disponible para revisarlo a
        mano en cualquier momento (ver su invisible en hr_payslip_views.xml).
        (2) el lote se procesa en orden de envío ascendente -- el que más tiempo lleva
        esperando entra primero, tanto al tope del lote como al orden de los grupos por
        ZipKey.

        H-012 (2026-10-07, hallazgo de Tech Lead corriendo esto en servidor real): "desde
        cuándo espera" NO se puede medir con write_date -- ese campo lo toca CUALQUIER
        escritura sobre el payslip, no solo esta integración DIAN (evidencia real: documentos
        de una copia de BD llevaban 'sent' desde hace tiempo, pero su write_date marcaba
        "hoy" por motivos ajenos a la DIAN -- con ese campo, el plazo nunca vencería). La
        fecha estable es la del envío real: create_date del l10n.co.ne.exchange
        ('send_sync'/'send_test_set') que produjo el ZipKey actual -- un registro histórico
        que ya existe y nunca se reescribe después de creado.
        """
        now = fields.Datetime.now()
        companies = self.env['res.company'].sudo().search([
            ('l10n_co_ne_hab_state', '!=', 'running'),
        ])
        for company in companies:
            # El motor de habilitación ya reconsulta sus propios 'sent' en su propio cron
            # (l10n_co_ne_habilitacion.py, paso 2 de _step()) -- consultarlos aquí también
            # duplicaría la consulta sobre el mismo ZipKey al mismo tiempo.
            pending = self.sudo().search([
                ('company_id', '=', company.id),
                ('l10n_co_ne_state', '=', 'sent'),
                ('l10n_co_ne_zip_key', '!=', False),
            ])
            if not pending:
                continue

            zip_keys = list(set(pending.mapped('l10n_co_ne_zip_key')))
            sends = self.env['l10n.co.ne.exchange'].sudo().search([
                ('company_id', '=', company.id),
                ('operation', 'in', ('send_sync', 'send_test_set')),
                ('zip_key', 'in', zip_keys),
            ], order='create_date desc')
            sent_since = {}
            for send in sends:
                sent_since.setdefault(send.zip_key, send.create_date)

            def _waiting_since(slip, _sent_since=sent_since):
                # Respaldo defensivo si no hay exchange (no debería pasar: zip_key solo se
                # asigna junto con el exchange que lo produjo) -- nunca por write_date.
                return _sent_since.get(slip.l10n_co_ne_zip_key) or slip.create_date

            pending = pending.sorted(key=_waiting_since)[:_CRON_RECHECK_BATCH_LIMIT]

            max_hours = company._ne_config_int_param(
                'l10n_co_nomina_electronica.recheck_max_hours',
                _CRON_RECHECK_MAX_HOURS_DEFAULT,
            )
            expired = pending.filtered(
                lambda slip: now - _waiting_since(slip) >= timedelta(hours=max_hours))
            if expired:
                for slip in expired:
                    slip.message_post(body=_(
                        'Reconsulta automática DIAN suspendida: pasaron más de '
                        '%(h)d horas sin que la DIAN diera un veredicto de este '
                        'documento. Queda marcado "Envío incierto -- requiere '
                        'conciliación" y ya no entra a la reconsulta automática -- '
                        'use "Consultar Estado" para revisarlo a mano cuando quiera.',
                        h=max_hours,
                    ))
                expired.write({'l10n_co_ne_state': 'uncertain'})
                self._cron_recheck_commit()
            pending = pending - expired
            if not pending:
                continue

            # dict.fromkeys en vez de sorted(set(...)) -- conserva el orden de llegada de
            # `pending` (ya viene ordenado por fecha de envío ascendente de arriba) en vez
            # de reordenar alfabéticamente por ZipKey.
            for zip_key in dict.fromkeys(pending.mapped('l10n_co_ne_zip_key')):
                group = pending.filtered(lambda slip: slip.l10n_co_ne_zip_key == zip_key)
                try:
                    group.action_check_dian_status()
                except Exception:  # noqa: BLE001 -- un ZipKey con error nunca debe frenar a los demás
                    _logger.exception(
                        'Reconsulta automática DIAN: error consultando ZipKey %s (compañía %s)',
                        zip_key, company.display_name,
                    )
                    self._cron_recheck_rollback()
                    continue
                self._cron_recheck_commit()

    def _cron_recheck_commit(self):
        """Confirma lo consultado hasta aquí (un ZipKey ya resuelto no puede perderse por un
        fallo posterior). Aislado para que las pruebas lo reemplacen -- mismo motivo y mismo
        patrón que l10n_co_ne_habilitacion._commit(): Odoo prohíbe cr.commit() en un test."""
        self.env.cr.commit()

    def _cron_recheck_rollback(self):
        """Deshace lo que haya quedado a medias tras un error en un ZipKey. Aislado por el mismo
        motivo que _cron_recheck_commit(): permite a las pruebas ejercer esta rama sin tocar la
        transacción real de la prueba."""
        self.env.cr.rollback()
        self.env.invalidate_all()

    # ══════════════════════════════════════════════════════════════════
    # MÉTODOS DE RECOPILACIÓN DE DATOS
    # ══════════════════════════════════════════════════════════════════

    def _collect_payslip_data(self):
        """
        Construye el diccionario completo de datos que ``nomina_xml_builder``
        espera para generar el XML de nómina electrónica.

        Retorna:
            dict: Estructura con todas las secciones del XML:
                - informacion_general
                - empleador
                - trabajador
                - pago
                - periodo
                - numero_secuencia
                - lugar_generacion
                - proveedor_xml
                - devengados
                - deducciones
                - totales
                - novedad (si es nota de ajuste)
        """
        self.ensure_one()
        company = self.company_id
        employee = self.employee_id
        contract = self.contract_id

        # Construir estructura de Devengados y Deducciones
        devengados, deducciones = self._map_salary_rules_to_xml()

        # Calcular totales
        total_devengados = sum(
            line.total for line in self.line_ids
            if line.salary_rule_id.l10n_co_ne_dian_concept
            and not line.salary_rule_id.l10n_co_ne_is_deduction
        )
        total_deducciones = sum(
            abs(line.total) for line in self.line_ids
            if line.salary_rule_id.l10n_co_ne_dian_concept
            and line.salary_rule_id.l10n_co_ne_is_deduction
        )

        # AUD-DIAN-34 (2026-10-04): el contenedor Odoo.sh corre en UTC --
        # datetime.now() devolvia la hora naive del servidor (UTC) con un
        # sufijo "-05:00" pegado encima sin convertir, declarando
        # FechaGen/HoraGen (y, via el mismo bug en xml_signer.py,
        # SigningTime) ~5h en el futuro respecto al instante real. La DIAN
        # rechazaba la firma (ZE02) por eso, de forma idéntica en cada
        # intento sin importar el contenido. Se calca el patrón nativo de
        # l10n_co_dian (account_edi_xml_ubl_dian.py): hora tz-aware
        # America/Bogota via pytz.
        now = datetime.now(_pytz_timezone('America/Bogota'))
        company_nit, company_dv = self._ne_company_nit_dv()

        # AUD-DIAN-34 (2026-09-14): NumeroSecuenciaXML/@Numero debe ser
        # Prefijo+Consecutivo (ej. "NE00000001"), pero @Consecutivo debe
        # ser SOLO el numero elegido por el emisor, sin el prefijo (regla
        # NIE011) -- l10n_co_ne_consecutive ya viene con el prefijo
        # incluido (lo arma ir.sequence.next_by_id()), asi que hay que
        # separarlos aqui para los 2 atributos.
        ne_prefix = (
            company.l10n_co_ne_adjust_prefix
            if self.l10n_co_ne_is_adjustment
            else company.l10n_co_ne_payroll_prefix
        ) or ''
        ne_numero = self.l10n_co_ne_consecutive or ''
        ne_consecutivo = (
            ne_numero[len(ne_prefix):]
            if ne_prefix and ne_numero.startswith(ne_prefix)
            else ne_numero
        )

        data = {
            'informacion_general': {
                # AUD-DIAN-34 (2026-09-14): NIE022 exige este literal EXACTO
                # -- no el consecutivo del documento (ese ya va en CUNE/
                # NumeroSecuenciaXML). El valor anterior ("V1.0: NumNom: ...")
                # nunca fue el literal que pide el Anexo Tecnico.
                # NIAE022 (nota de ajuste) exige el literal propio del ajuste.
                'Version': (
                    'V1.0: Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica'
                    if self.l10n_co_ne_is_adjustment
                    else 'V1.0: Documento Soporte de Pago de Nómina Electrónica'
                ),
                'Ambiente': company.l10n_co_ne_environment,
                'TipoXML': '103' if self.l10n_co_ne_is_adjustment else '102',
                'FechaGen': now.strftime('%Y-%m-%d'),
                'HoraGen': now.strftime('%H:%M:%S-05:00'),
                'PeriodoNomina': dian_utils.get_periodo_nomina(
                    self.date_from, self.date_to
                ),
                'TipoMoneda': nomina_xml_builder.NE_TIPO_MONEDA,
                'TRM': '0',
            },
            'numero_secuencia': {
                'Prefijo': ne_prefix,
                'Consecutivo': ne_consecutivo,
                'Numero': ne_numero,
                'CodigoTrabajador': str(employee.id),
            },
            'lugar_generacion': {
                'Pais': company.partner_id.country_id.code,
                'DepartamentoEstado': dian_utils.get_department_code(
                    company.partner_id.state_id
                ),
                'MunicipioCiudad': dian_utils.get_city_code(company.partner_id.city_id),
                'Idioma': nomina_xml_builder.NE_IDIOMA,
            },
            'proveedor_xml': {
                'RazonSocial': company.name or '',
                'NIT': company_nit,
                'DV': company_dv,
                'SoftwareID': company.l10n_co_ne_operation_mode_ids.software_id or '',
                'SoftwareSC': dian_utils.compute_software_security_code(
                    company.l10n_co_ne_operation_mode_ids.software_id,
                    company.l10n_co_ne_operation_mode_ids.software_pin,
                    self.l10n_co_ne_consecutive,
                ),
            },
            'empleador': {
                'RazonSocial': company.name or '',
                'NIT': company_nit,
                'DV': company_dv,
                'Pais': company.partner_id.country_id.code,
                'DepartamentoEstado': dian_utils.get_department_code(
                    company.partner_id.state_id
                ),
                'MunicipioCiudad': dian_utils.get_city_code(company.partner_id.city_id),
                'Direccion': company.partner_id.street or '',
            },

        }
        data['trabajador'] = self._ne_trabajador()
        data['pago'] = {
                'Forma': '1',  # 1=Contado
                'Metodo': employee.l10n_co_ne_payment_method or '1',
                'Banco': employee.l10n_co_ne_bank_name or '',
                'TipoCuenta': (
                    'Ahorro' if employee.l10n_co_ne_bank_account_type == 'ahorro'
                    else 'Corriente'
                ) if employee.l10n_co_ne_bank_account_type else '',
                'NumeroCuenta': employee.l10n_co_ne_bank_account or '',
        }
        data['periodo'] = {
                'FechaIngreso': str(contract.date_start) if contract.date_start else '',
                'FechaRetiro': str(contract.date_end) if contract.date_end else '',
                'FechaLiquidacionInicio': str(self.date_from),
                'FechaLiquidacionFin': str(self.date_to),
                'TiempoLaborado': str(
                    dian_utils.compute_worked_time(contract.date_start, self.date_to)
                ),
                'FechaGen': now.strftime('%Y-%m-%d'),
        }
        data['fechas_pagos'] = [str(self.date_to)]
        data['devengados'] = devengados
        data['deducciones'] = deducciones
        data['totales'] = {
                'DevengadosTotal': '%.2f' % total_devengados,
                'DeduccionesTotal': '%.2f' % total_deducciones,
                'ComprobanteTotal': '%.2f' % (total_devengados - total_deducciones),
        }
        # Top-level keys for nomina_xml_builder
        data['devengados_total'] = total_devengados
        data['deducciones_total'] = total_deducciones
        data['comprobante_total'] = total_devengados - total_deducciones

        # Información de ajuste si aplica
        if self.l10n_co_ne_is_adjustment:
            data['novedad'] = {
                'CUNENov': self.l10n_co_ne_adjustment_ref_cune,
                'value': True,
            }
            data['tipo_nota'] = '1'  # Reemplazar by default
            data['reemplazar'] = self._ne_reemplazar(data)

        return data

    def _ne_company_nit_dv(self):
        """NIT limpio (sin DV ni separadores) y su DV verificador.

        Fuente única para empleador y proveedor del XML, de modo que el
        NIT coincida siempre con el usado en el CUNE.
        """
        nit = dian_utils.clean_nit(self.company_id.vat)
        dv = dian_utils.compute_dv(nit) if self.company_id.vat else ''
        return nit, dv

    def _ne_trabajador(self):
        """Sección <Trabajador> del XML de nómina electrónica."""
        employee = self.employee_id
        contract = self.contract_id
        company = self.company_id
        _name_parts = dian_utils.split_name(employee.name or '')
        return {
            'TipoTrabajador': employee.l10n_co_ne_worker_type or '01',
            'SubTipoTrabajador': employee.l10n_co_ne_worker_subtype or '00',
            'AltoRiesgoPension': (
                'true' if employee.l10n_co_ne_high_risk_pension else 'false'
            ),
            'TipoDocumento': employee.l10n_co_ne_document_type or '13',
            'NumeroDocumento': employee.identification_id or '',
            'PrimerApellido': _name_parts.get('primer_apellido', ''),
            'SegundoApellido': _name_parts.get('segundo_apellido', ''),
            'PrimerNombre': _name_parts.get('primer_nombre', ''),
            'OtrosNombres': _name_parts.get('otros_nombres', ''),
            # AUD-DIAN-34 (2026-10-05): a diferencia de Idioma/TipoMoneda, el Anexo Técnico
            # NO fija LugarTrabajoPais a Colombia (NIE050: admite cualquier código alfa-2,
            # "país actual donde se encontraba ubicado el trabajador") -- mismo criterio de
            # LugarTrabajoDireccion/MunicipioCiudad: dato real del trabajador si lo hay
            # (work_contact_id), si no la ubicación de la compañía.
            'LugarTrabajoPais': (
                employee.work_contact_id.country_id.code
                or company.partner_id.country_id.code
            ),
            'LugarTrabajoDepartamentoEstado': dian_utils.get_department_code(
                employee.l10n_co_ne_dane_city_id.state_id
                if employee.l10n_co_ne_dane_city_id
                else company.partner_id.state_id
            ),
            'LugarTrabajoMunicipioCiudad': dian_utils.get_city_code(
                employee.l10n_co_ne_dane_city_id
            ) if employee.l10n_co_ne_dane_city_id else dian_utils.get_city_code(
                company.partner_id.city_id
            ),
            'LugarTrabajoDireccion': employee.work_contact_id.street or company.partner_id.street or '',

            'SalarioIntegral': (
                'true' if contract.l10n_co_ne_integral_salary else 'false'
            ),
            'TipoContrato': contract.l10n_co_ne_contract_type or '2',
            'Sueldo': '%.2f' % contract.wage,
            'CodigoTrabajador': str(employee.id),
        }

    def _ne_insert_cune_and_qr(self, xml_bytes, cune_value):
        """Escribe CUNE/EncripCUNE en ``InformacionGeneral`` y la URL en ``CodigoQR``.

        En las Notas de Ajuste ambos elementos viven dentro de ``<Reemplazar>`` (o
        ``<Eliminar>``), no como hijos directos de la raiz: se buscan en todo el arbol. Si
        no se encuentran el XML sale con ``CUNE=""`` y la DIAN rechaza con NIAE024.
        """
        company = self.company_id
        tree = _etree.fromstring(xml_bytes)
        ns = tree.nsmap.get(None, '')
        info_gen = tree.find('.//{%s}InformacionGeneral' % ns)
        if info_gen is not None:
            info_gen.set('CUNE', cune_value)
            info_gen.set('EncripCUNE', 'CUNE-SHA384')
        # AUD-DIAN-34 (2026-09-14, consolidado 2026-10-05): el host del QR cambia segun el
        # ambiente (Anexo Tecnico, seccion QRCode) -- unico punto, ver ResCompany.
        # _ne_dian_qr_host() / dian_utils.get_qr_catalog_host().
        qr_host = company._ne_dian_qr_host()
        qr_url = 'https://%s/document/searchqr?documentkey=%s' % (qr_host, cune_value)
        qr_el = tree.find('.//{%s}CodigoQR' % ns)
        if qr_el is None and info_gen is not None:
            parent = info_gen.getparent()
            qr_el = _etree.Element('{%s}CodigoQR' % ns)
            parent.insert(list(parent).index(info_gen) + 1, qr_el)
        if qr_el is not None:
            qr_el.text = qr_url
        return _etree.tostring(tree, xml_declaration=True, encoding='UTF-8')

    def _ne_predecessor_values(self):
        """(NumeroPred, FechaGenPred) del documento que reemplaza esta nota de ajuste.

        Anexo DIAN NIAE190/NIAE192: ``NumeroPred`` es el NUMERO del documento a reemplazar
        (prefijo + consecutivo, no un trozo del CUNE) y ``FechaGenPred`` la fecha de emision
        de ese documento (su ``InformacionGeneral/@FechaGen``), no el fin del periodo.
        """
        self.ensure_one()
        ref = self.l10n_co_ne_adjustment_ref_cune
        if not ref:
            return '', ''
        pred = self.search([
            ('l10n_co_ne_cune', '=', ref),
            ('l10n_co_ne_is_adjustment', '=', False),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not pred:
            return '', ''
        fecha = ''
        if pred.l10n_co_ne_xml_attachment_id:
            root = _etree.fromstring(base64.b64decode(pred.l10n_co_ne_xml_attachment_id.datas))
            info = root.find('.//{*}InformacionGeneral')
            if info is not None:
                fecha = info.get('FechaGen', '')
        return pred.l10n_co_ne_consecutive or '', fecha

    def _ne_reemplazar(self, data):
        """Sección <Reemplazar> de la nota de ajuste, reutilizando ``data``."""
        numero_pred, fecha_gen_pred = self._ne_predecessor_values()
        return {
            'predecesor': {
                'NumeroPred': numero_pred,
                'CUNEPred': self.l10n_co_ne_adjustment_ref_cune or '',
                'FechaGenPred': fecha_gen_pred,
            },
            # Include all the same sections
            'periodo': data['periodo'],
            'numero_secuencia': data['numero_secuencia'],
            'lugar_generacion': data['lugar_generacion'],
            'proveedor_xml': data['proveedor_xml'],
            'informacion_general': data['informacion_general'],
            'empleador': data['empleador'],
            'trabajador': data['trabajador'],
            'pago': data['pago'],
            'fechas_pagos': data['fechas_pagos'],
            'devengados': data['devengados'],
            'deducciones': data['deducciones'],
            'devengados_total': data['devengados_total'],
            'deducciones_total': data['deducciones_total'],
            'comprobante_total': data['comprobante_total'],
        }

    def _map_salary_rules_to_xml(self):
        """
        Mapea las líneas de la nómina (hr.payslip.line) a la estructura
        de Devengados y Deducciones del XML de nómina electrónica.

        Agrupa las líneas según su ``l10n_co_ne_dian_concept`` y construye
        los diccionarios correspondientes para el XML builder.

        Retorna:
            tuple: (devengados_dict, deducciones_dict) listos para el
                   nomina_xml_builder.
        """
        self.ensure_one()
        concept_lines = self._group_lines_by_concept()
        devengados = self._build_devengados(concept_lines)
        deducciones = self._build_deducciones(concept_lines)
        return devengados, deducciones

    def _group_lines_by_concept(self):
        """Agrupa las líneas de nómina por concepto DIAN (omite total=0)."""
        concept_lines = defaultdict(list)
        for line in self.line_ids:
            concept = line.salary_rule_id.l10n_co_ne_dian_concept
            if concept and line.total != 0:
                concept_lines[concept].append(line)
        return concept_lines

    def _build_devengados(self, concept_lines):
        """Construye el dict <Devengados> del XML a partir de concept_lines."""
        devengados = {}
        self._dev_basico_y_transporte(concept_lines, devengados)
        self._dev_horas_extra(concept_lines, devengados)
        self._dev_prestaciones(concept_lines, devengados)
        self._dev_novedades(concept_lines, devengados)
        self._dev_complementarios(concept_lines, devengados)
        self._dev_bonos_y_pagos(concept_lines, devengados)
        return devengados

    @staticmethod
    def _ne_dias_en_mes_calendario(year, month):
        """Días reales de un mes calendario -- compartido por toda la aritmética de "mes
        comercial" de 30 días (_ne_dia_comercial, _ne_dias_corridos_en_tramo).

        Tech Lead (2026-10-08, revisión .77): usa calendar.monthrange() en vez de un
        cálculo manual de año bisiesto -- misma regla gregoriana, sin reimplementarla."""
        return calendar.monthrange(year, month)[1]

    def _ne_dia_comercial(self, d, dias_mes):
        """Mapea un día calendario real a su "día comercial" (convención colombiana de mes
        de 30 días): el último día calendario REAL de cualquier mes (28/29-feb, 30 o 31)
        siempre equivale al día comercial 30 -- no solo cuando el mes tiene exactamente 30
        días. Compartido por _ne_dias_pagables() y _ne_dias_corridos_en_tramo() (H-014)."""
        ultimo_dia_mes = self._ne_dias_en_mes_calendario(d.year, d.month)
        if d.day == ultimo_dia_mes:
            return dias_mes
        return min(d.day, dias_mes)

    def _ne_tramo_pagable_periodo(self):
        """(periodo_ini, periodo_fin) -- el tramo del período de la nómina que realmente es
        pagable bajo la convención de mes comercial de 30 días.

        H-009 (2026-10-06, QA Bloque 2): en Liquidación, date_from es contract.date_start y
        date_to la fecha de retiro -- un período que puede abarcar meses o años. Cuando el
        período cruza más de un mes calendario, el tramo pagable se restringe al mes
        calendario de date_to (los meses anteriores ya se pagaron en nóminas regulares);
        dentro de un mismo mes (el caso normal mensual) el resultado es el período completo
        tal cual. Compartido por _ne_dias_pagables() y _ne_ausencia_calendario() (H-014) --
        ambos deben recortar al mismo tramo para no descontar/pagar fuera de él.
        """
        periodo_ini = self.date_from
        periodo_fin = self.date_to
        if (periodo_fin.year, periodo_fin.month) != (periodo_ini.year, periodo_ini.month):
            periodo_ini = max(periodo_ini, periodo_fin.replace(day=1))
        return periodo_ini, periodo_fin

    def _ne_dias_corridos_en_tramo(self, fecha_ini, fecha_fin, tramo_ini, tramo_fin, dias_mes):
        """Días CALENDARIO corridos (lunes a domingo) de [fecha_ini, fecha_fin] que caen
        dentro de [tramo_ini, tramo_fin], bajo la convención de mes comercial de 30 días
        (_ne_dia_comercial) -- 0 si no hay solapamiento. Usada por _ne_ausencia_calendario()
        para los 4 conceptos de "días corridos" (H-014)."""
        ini = max(fecha_ini, tramo_ini)
        fin = min(fecha_fin, tramo_fin)
        if ini > fin:
            return 0
        return self._ne_dia_comercial(fin, dias_mes) - self._ne_dia_comercial(ini, dias_mes) + 1

    def _ne_dias_pagables(self):
        """Días pagables del período -- misma convención de "mes comercial" colombiano que ya
        usa la regla salarial CO_BASICO (hr_salary_rule_co_basico, data/hr_payroll_structure_
        data.xml) y CO_AUX_TRANS para calcular el sueldo/auxilio. Única fuente para el sueldo
        Y para DiasTrabajados, sin importar si la estructura es mensual o de liquidación.

        AUD-DIAN-34 (2026-10-05, Ronda 1 DIAN): hallazgo real -- un básico de mes completo
        generaba DiasTrabajados="19" (conteo de líneas WORK100, calendario lun-vie) junto a
        SueldoTrabajado del mes completo (30 días comerciales): dos fuentes de días distintas
        para el mismo devengado. El Anexo Técnico (NIE069/NIE070) define SueldoTrabajado como
        "el Sueldo Trabajado por los días laborados" -- ambos deben contar exactamente lo
        mismo. Esta función es esa única fuente; CO_BASICO/CO_AUX_TRANS la llaman en vez de
        recalcular.
        """
        self.ensure_one()
        contract = self.contract_id
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self.date_from)
        periodo_ini, periodo_fin = self._ne_tramo_pagable_periodo()
        contrato_ini = contract.date_start
        contrato_fin = contract.date_end or periodo_fin

        activo_ini = max(periodo_ini, contrato_ini)
        activo_fin = min(periodo_fin, contrato_fin)

        if activo_ini > activo_fin:
            dias_bajo_contrato = 0
        else:
            dias_bajo_contrato = (
                self._ne_dia_comercial(activo_fin, dias_mes)
                - self._ne_dia_comercial(activo_ini, dias_mes) + 1
            )

        unpaid_types = self.env['hr.leave.type'].search([('unpaid', '=', True)])
        unpaid_codes = set(unpaid_types.mapped('work_entry_type_id.code')) - {False}
        # H-013 (2026-10-08, QA Bloque 4): vacaciones/licencias/incapacidades entraban como
        # novedades manuales (inputs CO_VAC/CO_LIC_REM/CO_LIC_NR/CO_INC_COMUN/CO_INC_LABORAL)
        # y el básico no descontaba esos días -- doble pago real (vacaciones 15 días: básico
        # de 30 días completo + vacaciones aparte). "unpaid" en Odoo no sirve para detectar
        # esto: significa "sin continuidad de pago del empleador", mientras que vacaciones/
        # incapacidad/licencia remunerada SÍ se pagan en Colombia, solo que por un concepto
        # distinto al básico (Art. 186 CST, Ley 100/1993, etc.). Por eso se excluyen SIEMPRE
        # estos códigos (data/l10n_co_ausencias_data.xml), sin importar su unpaid real.
        dias_excluidos_codes = unpaid_codes | _NOVEDAD_AUSENCIA_WORKED_DAYS_CODES
        dias_excluidos = sum(
            wd.number_of_days
            for wd in self.worked_days_line_ids
            if wd.work_entry_type_id.code in dias_excluidos_codes
        )
        # H-014 (2026-10-08, QA Bloque 5): CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL
        # se pagan en días CALENDARIO corridos (ver _ne_ausencia_calendario) -- se excluyen
        # del básico por la misma cuenta, nunca por worked_days (ahí solo existirían los
        # días que el calendario del contrato ya define como laborables, subcontando un
        # festivo o un día no laboral dentro de la ausencia).
        for codigo in _NOVEDAD_AUSENCIA_CALENDARIO_CODES:
            dias_excluidos += self._ne_ausencia_calendario(codigo)[0]
        return dias_bajo_contrato - dias_excluidos

    def _ne_ausencia_calendario(self, work_entry_code):
        """Única fuente de días CALENDARIO corridos (lunes a domingo, festivos incluidos)
        para un concepto de ausencia -- CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL
        (H-014, 2026-10-08, decisión de David: CST Art. 186/227/236 mod. Ley 2114/2021,
        Concepto Mintrabajo 63044901/2022). A diferencia de CO_VAC/CO_LIC_REM/CO_LIC_NR
        (H-013, días HÁBILES vía worked_days), estos 4 no pueden contarse desde worked_days:
        los work entries solo existen en los días que el calendario del contrato define
        como laborables (confirmado contra hr_work_entry_contract.
        _get_contract_work_entries_values -- un día sin asistencia en ese calendario, ej.
        el lunes en un calendario martes-a-domingo, nunca genera NINGÚN work entry, sea
        cual sea el tipo de ausencia).

        Recorta cada hr.leave validada al mismo tramo pagable del período
        (_ne_tramo_pagable_periodo(), la misma restricción de mes comercial de 30 días que
        usa _ne_dias_pagables() para Liquidación) y a la actividad del contrato.

        Devuelve (dias_totales, detalle) -- dias_totales es la única fuente para la regla
        de pago (_ne_dias_novedad_calendario()) Y para la exclusión del básico
        (_ne_dias_pagables()); detalle es [(leave, dias, fecha_ini_recortada,
        fecha_fin_recortada)] para quien necesite el desglose por ausencia
        (_dev_novedades(), y el futuro corte de incapacidad en el día 90 del paso 3 de
        H-013, que puede reusar esto mismo con las fechas ya recortadas).
        """
        self.ensure_one()
        contract = self.contract_id
        dias_mes = self._rule_parameter('l10n_co_dias_mes_comercial', self.date_from)
        periodo_ini, periodo_fin = self._ne_tramo_pagable_periodo()
        contrato_ini = contract.date_start
        contrato_fin = contract.date_end or periodo_fin
        tramo_ini = max(periodo_ini, contrato_ini)
        tramo_fin = min(periodo_fin, contrato_fin)

        # Tech Lead (2026-10-08, revisión .77): date_from/date_to son datetimes en UTC: una
        # ausencia que termina de noche en Colombia (UTC-5, ej. el calendario Mar-Dom de
        # Guapante) cae en la madrugada del día siguiente en UTC, y .date() contaría un día
        # de más. request_date_from/request_date_to son las fechas puras que el usuario
        # pidió (sin conversión de huso horario) -- misma lección ya aplicada a hr.leave en
        # otras partes del módulo.
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('holiday_status_id.work_entry_type_id.code', '=', work_entry_code),
            ('request_date_from', '<=', self.date_to),
            ('request_date_to', '>=', self.date_from),
        ])

        detalle = []
        dias_totales = 0
        for leave in leaves:
            leave_ini = leave.request_date_from
            leave_fin = leave.request_date_to
            dias = self._ne_dias_corridos_en_tramo(leave_ini, leave_fin, tramo_ini, tramo_fin, dias_mes)
            if dias > 0:
                detalle.append((leave, dias, max(leave_ini, tramo_ini), min(leave_fin, tramo_fin)))
                dias_totales += dias
        return dias_totales, detalle

    def _ne_dias_novedad_ausencia_e_input(self, work_entry_code, input_code, inputs, worked_days):
        """(días desde Ausencias, días desde el input manual) para un concepto de novedad en
        días HÁBILES (CO_VAC/CO_LIC_REM/CO_LIC_NR -- H-013).

        No decide ni falla -- eso lo hace el llamador: condition_python solo necesita saber
        si hay algo (cualquiera de los dos > 0); amount_python_compute (vía
        _ne_dias_novedad()) necesita el valor final y el chequeo de conflicto."""
        worked_days_line = worked_days.get(work_entry_code)
        dias_ausencia = worked_days_line.number_of_days if worked_days_line else 0
        input_line = inputs.get(input_code)
        dias_input = input_line.amount if input_line else 0
        return dias_ausencia, dias_input

    def _ne_ausencia_calendario_dias_e_input(self, work_entry_code, input_code, inputs):
        """Igual que _ne_dias_novedad_ausencia_e_input() pero para los 4 conceptos de días
        CALENDARIO corridos (H-014) -- mismo rol (condition_python), fuente de días distinta
        (_ne_ausencia_calendario() en vez de worked_days)."""
        dias_ausencia, _detalle = self._ne_ausencia_calendario(work_entry_code)
        input_line = inputs.get(input_code)
        dias_input = input_line.amount if input_line else 0
        return dias_ausencia, dias_input

    def _ne_resolver_dias_novedad(self, dias_ausencia, input_code, inputs, work_entry_code):
        """Combina los días que vienen de Ausencias con el input manual de respaldo para un
        concepto de novedad -- nunca los dos a la vez. Compartido por _ne_dias_novedad()
        (días hábiles, H-013) y _ne_dias_novedad_calendario() (días corridos, H-014): ambos
        ya calcularon dias_ausencia por su propio mecanismo, y de aquí en adelante el
        conflicto con el input manual se resuelve igual.

        H-013 (2026-10-08, decisión de David): prioriza el módulo de Ausencias (hr.leave
        validada -> ... -> esta función). El input manual CO_XXX sigue existiendo como
        respaldo para lo que Ausencias no haya capturado, pero NUNCA junto con una ausencia
        real del mismo concepto en la misma nómina: sumar los dos sería doble conteo, y
        elegir uno en silencio escondería un error de captura real. Nunca un default
        silencioso -- mismo principio que _dias_trabajados_requerido()/_pais_requerido()
        en services/nomina_xml_builder.py.
        """
        input_line = inputs.get(input_code)
        dias_input = input_line.amount if input_line else 0
        if dias_ausencia > 0 and dias_input > 0:
            raise UserError(_(
                'Hay %(dias_ausencia)s día(s) de "%(code)s" ya registrados en Ausencias '
                'y además un input manual "%(input_code)s" con %(dias_input)s día(s) en '
                'la misma nómina de %(employee)s. Use solo una fuente: borre el input '
                'manual si la ausencia ya está en el sistema, o elimine la ausencia si el '
                'dato manual es el correcto.',
                dias_ausencia=dias_ausencia, code=work_entry_code, input_code=input_code,
                dias_input=dias_input, employee=self.employee_id.name,
            ))
        return dias_ausencia or dias_input

    def _ne_dias_novedad(self, work_entry_code, input_code, inputs, worked_days):
        """Única fuente de días para las reglas de ausencias en días HÁBILES (CO_VAC/
        CO_LIC_REM/CO_LIC_NR, H-013) -- los mismos días que _ne_dias_pagables() excluye del
        básico (_NOVEDAD_AUSENCIA_WORKED_DAYS_CODES)."""
        dias_ausencia, _dias_input = self._ne_dias_novedad_ausencia_e_input(
            work_entry_code, input_code, inputs, worked_days)
        return self._ne_resolver_dias_novedad(dias_ausencia, input_code, inputs, work_entry_code)

    def _ne_dias_novedad_calendario(self, work_entry_code, input_code, inputs):
        """Única fuente de días para las reglas de ausencias en días CALENDARIO corridos
        (CO_LIC_MAT/CO_LIC_PAT/CO_INC_COMUN/CO_INC_LABORAL, H-014) -- los mismos días que
        _ne_dias_pagables() excluye del básico (_NOVEDAD_AUSENCIA_CALENDARIO_CODES)."""
        dias_ausencia, _detalle = self._ne_ausencia_calendario(work_entry_code)
        return self._ne_resolver_dias_novedad(dias_ausencia, input_code, inputs, work_entry_code)

    def _dev_basico_y_transporte(self, concept_lines, devengados):
        """Devengados: sueldo básico, transporte y viáticos."""
        # Sueldo básico
        if 'Sueldo' in concept_lines:
            sueldo_lines = concept_lines['Sueldo']
            dias_pagables = self._ne_dias_pagables()
            if dias_pagables <= 0:
                raise UserError(_(
                    'No se pudo determinar DiasTrabajados de %(employee)s para el período '
                    '%(ini)s a %(fin)s (contrato no activo en el período, o los días no '
                    'remunerados cubren todo el período). Revise las fechas del contrato y '
                    'las novedades antes de generar el XML.',
                    employee=self.employee_id.name, ini=self.date_from, fin=self.date_to,
                ))
            devengados['Basico'] = {
                'DiasTrabajados': str(int(dias_pagables)),
                'SueldoTrabajado': '%.2f' % sum(l.total for l in sueldo_lines),
            }

        # Transporte
        if 'Transporte' in concept_lines:
            devengados['Transporte'] = {
                'AuxilioTransporte': '%.2f' % sum(
                    l.total for l in concept_lines['Transporte']
                ),
                'ViaticoManuAlojS': '0.00',
                'ViaticoManuAlojNS': '0.00',
            }

        # Viáticos
        if 'ViaticoS' in concept_lines:
            transport = devengados.setdefault('Transporte', {
                'AuxilioTransporte': '0.00',
                'ViaticoManuAlojS': '0.00',
                'ViaticoManuAlojNS': '0.00',
            })
            transport['ViaticoManuAlojS'] = '%.2f' % sum(
                l.total for l in concept_lines['ViaticoS']
            )
        if 'ViaticoNS' in concept_lines:
            transport = devengados.setdefault('Transporte', {
                'AuxilioTransporte': '0.00',
                'ViaticoManuAlojS': '0.00',
                'ViaticoManuAlojNS': '0.00',
            })
            transport['ViaticoManuAlojNS'] = '%.2f' % sum(
                l.total for l in concept_lines['ViaticoNS']
            )

    def _dev_horas_extra(self, concept_lines, devengados):
        """Devengados: horas extras y recargos."""
        for he_concept in HORA_EXTRA_CONCEPTS:
            if he_concept in concept_lines:
                container_key = he_concept + 's'  # HEDs, HENs, etc.
                items = []
                for line in concept_lines[he_concept]:
                    items.append({
                        'HoraInicio': '',
                        'HoraFin': '',
                        'Cantidad': str(int(line.quantity)) if line.quantity else '0',
                        'Porcentaje': '%.2f' % (line.rate if line.rate else 0),
                        'Pago': '%.2f' % line.total,
                    })
                devengados[container_key] = items

    def _get_overlapping_leaves_data(self):
        """Busca ausencias validadas del empleado en el periodo y las organiza por categoria."""
        def get_leave_category(leave):
            code = (leave.holiday_status_id.work_entry_type_id.code or leave.holiday_status_id.name or '').strip().upper()
            if hasattr(self, '_LEAVE_CODE_MAP'):
                return self._LEAVE_CODE_MAP.get(code)
            # Copia defensiva de HrPayslipLeaveIntegration._LEAVE_CODE_MAP (hr_leave_ne.py)
            # -- nunca se ejercita en producción porque ese mixin siempre está presente en
            # este modelo heredado, pero debe quedar sincronizada para no divergir (H-014,
            # revisión .78: se agregaron los 7 códigos CO_ al mapa real, ver ese archivo).
            local_map = {
                'INCAPACIDAD': 'incapacidad', 'SICK': 'incapacidad', 'INC_COMUN': 'incapacidad', 'INC_LABORAL': 'incapacidad',
                'CO_INC_COMUN': 'incapacidad', 'CO_INC_LABORAL': 'incapacidad',
                'MATERNIDAD': 'licencia_mat', 'MATERNITY': 'licencia_mat', 'PATERNIDAD': 'licencia_mat', 'PATERNITY': 'licencia_mat', 'LIC_MAT': 'licencia_mat', 'LIC_PAT': 'licencia_mat',
                'CO_LIC_MAT': 'licencia_mat', 'CO_LIC_PAT': 'licencia_mat',
                'VACACIONES': 'vacaciones', 'VACATION': 'vacaciones', 'VAC': 'vacaciones', 'CO_VAC': 'vacaciones',
                'LICENCIA_REM': 'licencia_rem', 'LIC_REM': 'licencia_rem', 'PERMISO': 'licencia_rem', 'CO_LIC_REM': 'licencia_rem',
                'LICENCIA_NR': 'licencia_nr', 'LIC_NR': 'licencia_nr', 'UNPAID': 'licencia_nr', 'SIN_SUELDO': 'licencia_nr', 'CO_LIC_NR': 'licencia_nr',
            }
            return local_map.get(code)

        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
        ])

        category_leaves = defaultdict(list)
        category_leave_days = defaultdict(dict)  # leave.id -> days in period
        category_total_days = defaultdict(int)    # category -> total days in period
        
        for leave in leaves:
            leave_start = leave.date_from.date() if isinstance(leave.date_from, datetime) else leave.date_from
            leave_end = leave.date_to.date() if isinstance(leave.date_to, datetime) else leave.date_to
            period_start = max(leave_start, self.date_from)
            period_end = min(leave_end, self.date_to)
            days = (period_end - period_start).days + 1
            if days > 0:
                category = get_leave_category(leave)
                if category:
                    category_leaves[category].append(leave)
                    category_leave_days[category][leave.id] = days
                    category_total_days[category] += days

        return category_leaves, category_leave_days, category_total_days

    def _dev_prestaciones(self, concept_lines, devengados):
        """Devengados: vacaciones, primas, cesantías e intereses.

        Revisión .79 (2026-10-08, decisión de David): un pago de VacacionesComunes
        (CO_VAC) sin ninguna hr.leave validada que lo respalde (típicamente el input
        manual de respaldo usado solo, sin registrar la ausencia) se detiene con
        UserError en vez de emitir las fechas del período completo en silencio -- mismo
        criterio que Incapacidades/LicenciaMP/LicenciaR. VacacionesCompensadas (CO_VAC_COMP)
        no lleva FechaInicio/FechaFin en el XML (ver más abajo, Pago/Cantidad solamente) --
        no hay fecha que inventar, y por su naturaleza (pago en dinero de días NO
        disfrutados) tampoco hay una ausencia que la respalde, así que no entra en este
        mismo tratamiento.
        """
        # Vacaciones
        vac_comunes = concept_lines.get('VacacionesComunes', [])
        vac_compensadas = concept_lines.get('VacacionesCompensadas', [])
        if vac_comunes or vac_compensadas:
            vacaciones = {}
            if vac_comunes:
                category_leaves, category_leave_days, category_total_days = self._get_overlapping_leaves_data()
                actual_vac_leaves = category_leaves.get('vacaciones', [])
                if actual_vac_leaves:
                    items = []
                    total_pago = sum(l.total for l in vac_comunes)
                    total_days = category_total_days['vacaciones']
                    for leave in actual_vac_leaves:
                        days = category_leave_days['vacaciones'][leave.id]
                        pago = total_pago * (days / total_days) if total_days > 0 else 0.0
                        leave_start = leave.date_from.date() if isinstance(leave.date_from, datetime) else leave.date_from
                        leave_end = leave.date_to.date() if isinstance(leave.date_to, datetime) else leave.date_to
                        period_start = max(leave_start, self.date_from)
                        period_end = min(leave_end, self.date_to)
                        items.append({
                            'FechaInicio': str(period_start),
                            'FechaFin': str(period_end),
                            'Cantidad': str(int(days)),
                            'Pago': '%.2f' % pago,
                        })
                    vacaciones['VacacionesComunes'] = items
                else:
                    # H-014 (revisión .79, decisión de David): mismo criterio que
                    # Incapacidad/LicenciaMP/LicenciaR -- sin ausencia validada no hay
                    # fechas reales que reportar, y aquí SÍ hay dinero real de por medio
                    # (CO_VAC). Antes se emitían las fechas del período completo en
                    # silencio.
                    raise UserError(_(
                        'Hay un pago de Vacaciones (%(pago)s) en la nómina de '
                        '%(employee)s sin ninguna ausencia (CO_VAC) validada en '
                        'Ausencias que lo respalde con fechas reales -- la DIAN exige '
                        'las fechas reales de las vacaciones, no las del período '
                        'completo. Registre la ausencia en Ausencias antes de generar '
                        'el XML.',
                        pago='%.2f' % sum(l.total for l in vac_comunes),
                        employee=self.employee_id.name,
                    ))
            if vac_compensadas:
                vacaciones['VacacionesCompensadas'] = [{
                    'Cantidad': str(int(sum(l.quantity for l in vac_compensadas))),
                    'Pago': '%.2f' % sum(l.total for l in vac_compensadas),
                }]
            devengados['Vacaciones'] = vacaciones

        # Primas
        if 'Primas' in concept_lines:
            devengados['Primas'] = {
                'Cantidad': str(int(sum(
                    l.quantity for l in concept_lines['Primas']
                ))),
                'Pago': '%.2f' % sum(l.total for l in concept_lines['Primas']),
                'PagoNS': '0.00',
            }

        # Cesantías e intereses
        cesantias_lines = concept_lines.get('Cesantias', [])
        intereses_lines = concept_lines.get('InteresesCesantias', [])
        if cesantias_lines or intereses_lines:
            devengados['Cesantias'] = {
                'Pago': '%.2f' % sum(l.total for l in cesantias_lines),
                'Porcentaje': '12.00' if intereses_lines else '0.00',
                'PagoIntereses': '%.2f' % sum(
                    l.total for l in intereses_lines
                ),
            }

    def _dev_novedades(self, concept_lines, devengados):
        """Devengados: incapacidades y licencias.

        H-014 (2026-10-08): Incapacidades (CO_INC_COMUN/CO_INC_LABORAL) y LicenciaMP
        (CO_LIC_MAT/CO_LIC_PAT) se formatean desde _ne_ausencia_calendario() -- la MISMA
        fuente que ya paga la regla y descuenta el básico (días calendario corridos), para
        no tener 3 cálculos distintos de lo mismo. LicenciaR/LicenciaNR siguen igual que
        antes (días hábiles vía worked_days, _get_overlapping_leaves_data()).

        Revisión .79 (2026-10-08, decisión de David): si hay un pago/registro de
        Incapacidad, LicenciaMP o LicenciaR SIN ninguna hr.leave validada que lo respalde
        (típicamente el input manual de respaldo usado solo, sin registrar la ausencia),
        se detiene con UserError en vez de emitir las fechas del período completo en
        silencio -- la DIAN exige las fechas reales de la ausencia (los nodos del XSD
        V1.0.6 son minOccurs=0: sin ausencia simplemente no se emite el nodo, nunca un
        dato inventado). LicenciaNR NUNCA llega a este camino: su amount_python_compute
        es siempre 0 (no genera pago, por diseño) y _group_lines_by_concept() omite del
        concept_lines cualquier línea con total=0 -- lo único que se pierde ahí es el
        detalle de cuántos días hubo, si nadie registra la ausencia (límite conocido, sin
        resolver). Vacaciones (CO_VAC) recibe el mismo tratamiento en _dev_prestaciones().
        """
        category_leaves, category_leave_days, category_total_days = self._get_overlapping_leaves_data()

        # Incapacidades (común + laboral, cada una con su Tipo -- ya no por substring del
        # código, por cuál de las 2 llamadas la produjo)
        if 'Incapacidad' in concept_lines:
            _dias_comun, detalle_comun = self._ne_ausencia_calendario('CO_INC_COMUN')
            _dias_laboral, detalle_laboral = self._ne_ausencia_calendario('CO_INC_LABORAL')
            detalle_inc = (
                [(leave, dias, ini, fin, '1') for leave, dias, ini, fin in detalle_comun]
                + [(leave, dias, ini, fin, '3') for leave, dias, ini, fin in detalle_laboral]
            )
            if detalle_inc:
                items = []
                total_pago = sum(l.total for l in concept_lines['Incapacidad'])
                total_dias = sum(dias for _leave, dias, _ini, _fin, _tipo in detalle_inc)
                for _leave, dias, ini, fin, tipo in detalle_inc:
                    pago = total_pago * (dias / total_dias) if total_dias > 0 else 0.0
                    items.append({
                        'FechaInicio': str(ini),
                        'FechaFin': str(fin),
                        'Cantidad': str(int(dias)),
                        'Tipo': tipo,
                        'Pago': '%.2f' % pago,
                    })
                devengados['Incapacidades'] = items
            else:
                # H-014 (revisión .79, decisión de David): la DIAN exige las fechas reales
                # de la incapacidad -- un pago sin ninguna hr.leave validada que lo
                # respalde (ej. solo el input manual CO_INC_COMUN/CO_INC_LABORAL de
                # respaldo, sin registrar la ausencia) no tiene de dónde sacar esas fechas.
                # Antes se emitían las fechas del período completo en silencio; ahora se
                # detiene con un error claro en vez de mandar un dato inventado a la DIAN.
                raise UserError(_(
                    'Hay un pago de Incapacidad (%(pago)s) en la nómina de %(employee)s '
                    'sin ninguna ausencia de Incapacidad (CO_INC_COMUN/CO_INC_LABORAL) '
                    'validada en Ausencias que lo respalde con fechas reales -- la DIAN '
                    'exige las fechas reales de la incapacidad, no las del período '
                    'completo. Registre la ausencia en Ausencias antes de generar el XML.',
                    pago='%.2f' % sum(l.total for l in concept_lines['Incapacidad']),
                    employee=self.employee_id.name,
                ))

        # Licencias
        licencias = {}

        # LicenciaMP (maternidad + paternidad): días calendario corridos, misma fuente que
        # la regla y el descuento del básico (H-014).
        if 'LicenciaMP' in concept_lines:
            _dias_mat, detalle_mat = self._ne_ausencia_calendario('CO_LIC_MAT')
            _dias_pat, detalle_pat = self._ne_ausencia_calendario('CO_LIC_PAT')
            detalle_mp = detalle_mat + detalle_pat
            if detalle_mp:
                items = []
                total_pago = sum(l.total for l in concept_lines['LicenciaMP'])
                total_dias = sum(dias for _leave, dias, _ini, _fin in detalle_mp)
                for _leave, dias, ini, fin in detalle_mp:
                    pago = total_pago * (dias / total_dias) if total_dias > 0 else 0.0
                    items.append({
                        'FechaInicio': str(ini),
                        'FechaFin': str(fin),
                        'Cantidad': str(int(dias)),
                        'Pago': '%.2f' % pago,
                    })
                licencias['LicenciaMP'] = items
            else:
                # H-014 (revisión .79, decisión de David): mismo criterio que Incapacidad
                # -- maternidad/paternidad SON licencias (LicenciaMP), no incapacidades, y
                # ya están separadas en el código; sin ausencia no hay fechas reales que
                # reportar.
                raise UserError(_(
                    'Hay un pago de Licencia de Maternidad/Paternidad (%(pago)s) en la '
                    'nómina de %(employee)s sin ninguna ausencia (CO_LIC_MAT/CO_LIC_PAT) '
                    'validada en Ausencias que lo respalde con fechas reales -- la DIAN '
                    'exige las fechas reales de la licencia, no las del período completo. '
                    'Registre la ausencia en Ausencias antes de generar el XML.',
                    pago='%.2f' % sum(l.total for l in concept_lines['LicenciaMP']),
                    employee=self.employee_id.name,
                ))

        # LicenciaR / LicenciaNR: días hábiles, sin cambio (H-013, worked_days vía
        # _get_overlapping_leaves_data()).
        licencia_concepts = {
            'LicenciaR': 'LicenciaR',
            'LicenciaNR': 'LicenciaNR',
        }
        lic_concept_to_category = {
            'LicenciaR': 'licencia_rem',
            'LicenciaNR': 'licencia_nr',
        }
        for concept_key, xml_key in licencia_concepts.items():
            category = lic_concept_to_category[concept_key]
            actual_leaves = category_leaves.get(category, [])

            if actual_leaves:
                items = []
                total_pago = sum(l.total for l in concept_lines.get(concept_key, []))
                total_days = category_total_days[category]
                
                for leave in actual_leaves:
                    days = category_leave_days[category][leave.id]
                    pago = total_pago * (days / total_days) if total_days > 0 else 0.0
                    
                    leave_start = leave.date_from.date() if isinstance(leave.date_from, datetime) else leave.date_from
                    leave_end = leave.date_to.date() if isinstance(leave.date_to, datetime) else leave.date_to
                    period_start = max(leave_start, self.date_from)
                    period_end = min(leave_end, self.date_to)
                    
                    lic_data = {
                        'FechaInicio': str(period_start),
                        'FechaFin': str(period_end),
                        'Cantidad': str(int(days)),
                    }
                    if concept_key != 'LicenciaNR':
                        lic_data['Pago'] = '%.2f' % pago
                    items.append(lic_data)
                licencias[xml_key] = items
            elif concept_key == 'LicenciaR' and concept_key in concept_lines:
                # H-014 (revisión .79, decisión de David): sin ausencia no hay fechas
                # reales que reportar -- mismo criterio que Incapacidad/LicenciaMP/
                # Vacaciones. LicenciaNR NUNCA entra aquí: su amount_python_compute es
                # siempre 0 (no genera pago, por diseño -- ver data/hr_payroll_structure_
                # data.xml) y _group_lines_by_concept() omite del concept_lines cualquier
                # línea con total=0, así que una rama "elif 'LicenciaNR' in concept_lines"
                # sería código muerto que nada prueba (Tech Lead, revisión .79). Lo único
                # que se pierde en ese caso es el detalle de cuántos días de licencia no
                # remunerada hubo, si nadie registra la ausencia -- límite conocido, no se
                # resuelve aquí (ver test_xml_licencia_no_remunerada_solo_input_no_emite_
                # nodo_ni_error).
                raise UserError(_(
                    'Hay un registro de Licencia Remunerada (%(cantidad)s día(s)) en la '
                    'nómina de %(employee)s sin ninguna ausencia validada en Ausencias '
                    'que lo respalde con fechas reales -- la DIAN exige las fechas reales '
                    'de la licencia, no las del período completo. Registre la ausencia en '
                    'Ausencias antes de generar el XML.',
                    cantidad=str(int(sum(
                        l.quantity for l in concept_lines[concept_key]
                    ))),
                    employee=self.employee_id.name,
                ))
        if licencias:
            devengados['Licencias'] = licencias

    def _dev_complementarios(self, concept_lines, devengados):
        """Devengados: bonificaciones, auxilios, huelgas, otros y compensaciones."""
        # Bonificaciones
        bonif_s = concept_lines.get('BonificacionS', [])
        bonif_ns = concept_lines.get('BonificacionNS', [])
        if bonif_s or bonif_ns:
            devengados['Bonificaciones'] = [{
                'BonificacionS': '%.2f' % sum(l.total for l in bonif_s),
                'BonificacionNS': '%.2f' % sum(l.total for l in bonif_ns),
            }]

        # Auxilios
        aux_s = concept_lines.get('AuxilioS', [])
        aux_ns = concept_lines.get('AuxilioNS', [])
        if aux_s or aux_ns:
            devengados['Auxilios'] = [{
                'AuxilioS': '%.2f' % sum(l.total for l in aux_s),
                'AuxilioNS': '%.2f' % sum(l.total for l in aux_ns),
            }]

        # Huelga Legal
        if 'HuelgaLegal' in concept_lines:
            devengados['HuelgasLegales'] = [{
                'FechaInicio': str(self.date_from),
                'FechaFin': str(self.date_to),
                'Cantidad': str(int(sum(
                    l.quantity for l in concept_lines['HuelgaLegal']
                ))),
            }]

        # Otros conceptos salariales y no salariales
        otros_s = concept_lines.get('OtroConceptoS', [])
        otros_ns = concept_lines.get('OtroConceptoNS', [])
        if otros_s or otros_ns:
            otros = []
            for line in otros_s:
                otros.append({
                    'DescripcionConcepto': line.name or '',
                    'ConceptoS': '%.2f' % line.total,
                    'ConceptoNS': '0.00',
                })
            for line in otros_ns:
                otros.append({
                    'DescripcionConcepto': line.name or '',
                    'ConceptoS': '0.00',
                    'ConceptoNS': '%.2f' % line.total,
                })
            devengados['OtrosConceptos'] = otros

        # Compensaciones
        comp_o = concept_lines.get('CompensacionO', [])
        comp_e = concept_lines.get('CompensacionE', [])
        if comp_o or comp_e:
            devengados['Compensaciones'] = [{
                'CompensacionO': '%.2f' % sum(l.total for l in comp_o),
                'CompensacionE': '%.2f' % sum(l.total for l in comp_e),
            }]

    def _dev_bonos_y_pagos(self, concept_lines, devengados):
        """Devengados: bonos EPCTV, comisiones, pagos a terceros, anticipos y conceptos simples."""
        # Bonos EPCTV
        bono_keys = {
            'BonoEPCTVS': 'PagoS',
            'BonoEPCTVNS': 'PagoNS',
            'BonoAlimS': 'PagoAlimentacionS',
            'BonoAlimNS': 'PagoAlimentacionNS',
        }
        bono_data = {}
        for concept_key, xml_attr in bono_keys.items():
            if concept_key in concept_lines:
                bono_data[xml_attr] = '%.2f' % sum(
                    l.total for l in concept_lines[concept_key]
                )
        if bono_data:
            for attr in ['PagoS', 'PagoNS', 'PagoAlimentacionS', 'PagoAlimentacionNS']:
                bono_data.setdefault(attr, '0.00')
            devengados['BonoEPCTVs'] = [bono_data]

        # Comisiones
        if 'Comision' in concept_lines:
            devengados['Comisiones'] = [
                '%.2f' % l.total for l in concept_lines['Comision']
            ]

        # Pagos a terceros (devengado)
        if 'PagoTercero' in concept_lines:
            devengados['PagosTerceros'] = [
                '%.2f' % l.total for l in concept_lines['PagoTercero']
            ]

        # Anticipos (devengado)
        if 'Anticipo' in concept_lines:
            devengados['Anticipos'] = [
                '%.2f' % l.total for l in concept_lines['Anticipo']
            ]

        # Conceptos simples de devengado
        for concept_key, xml_key in DEVENGADO_SIMPLE_CONCEPTS.items():
            if concept_key in concept_lines:
                devengados[xml_key] = '%.2f' % sum(
                    l.total for l in concept_lines[concept_key]
                )

    def _build_deducciones(self, concept_lines):
        """Construye el dict <Deducciones> del XML a partir de concept_lines."""
        deducciones = {}
        # Salud
        if 'Salud' in concept_lines:
            deducciones['Salud'] = {
                'Porcentaje': '4.00',
                'Deduccion': '%.2f' % abs(sum(
                    l.total for l in concept_lines['Salud']
                )),
            }

        # Fondo de Pensión
        if 'FondoPension' in concept_lines:
            deducciones['FondoPension'] = {
                'Porcentaje': '4.00',
                'Deduccion': '%.2f' % abs(sum(
                    l.total for l in concept_lines['FondoPension']
                )),
            }

        # Fondo de Solidaridad Pensional
        if 'FondoSP' in concept_lines:
            deducciones['FondoSP'] = {
                'Porcentaje': '1.00',
                'DeduccionSP': '%.2f' % abs(sum(
                    l.total for l in concept_lines['FondoSP']
                )),
                'PorcentajeSub': '0.00',
                'DeduccionSub': '0.00',
            }

        # Sindicatos
        if 'Sindicato' in concept_lines:
            deducciones['Sindicatos'] = [{
                'Porcentaje': '%.2f' % (
                    concept_lines['Sindicato'][0].rate or 0
                ),
                'Deduccion': '%.2f' % abs(sum(
                    l.total for l in concept_lines['Sindicato']
                )),
            }]

        # Sanciones
        if 'Sancion' in concept_lines:
            deducciones['Sanciones'] = [{
                'SancionPublic': '0.00',
                'SancionPriv': '%.2f' % abs(sum(
                    l.total for l in concept_lines['Sancion']
                )),
            }]

        # Libranzas
        if 'Libranza' in concept_lines:
            deducciones['Libranzas'] = []
            for line in concept_lines['Libranza']:
                deducciones['Libranzas'].append({
                    'Descripcion': line.name or 'Libranza',
                    'Deduccion': '%.2f' % abs(line.total),
                })

        # Pagos a terceros (deducción)
        if 'PagoTerceroDed' in concept_lines:
            deducciones['PagosTerceros'] = [
                '%.2f' % abs(l.total) for l in concept_lines['PagoTerceroDed']
            ]

        # Anticipos (deducción)
        if 'AnticipoDed' in concept_lines:
            deducciones['Anticipos'] = [
                '%.2f' % abs(l.total) for l in concept_lines['AnticipoDed']
            ]

        # Otras deducciones
        if 'OtraDeduccion' in concept_lines:
            deducciones['OtrasDeducciones'] = [
                '%.2f' % abs(l.total) for l in concept_lines['OtraDeduccion']
            ]

        # Deducciones simples (valor único)
        for concept_key, xml_key in DEDUCTION_SIMPLE_CONCEPTS.items():
            if concept_key in concept_lines:
                deducciones[xml_key] = '%.2f' % abs(sum(
                    l.total for l in concept_lines[concept_key]
                ))

        return deducciones

    # ══════════════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES PRIVADOS
    # ══════════════════════════════════════════════════════════════════

    def _validate_ne_prerequisites(self):
        """Valida que la nómina cumpla los prerequisitos para generar XML."""
        self.ensure_one()

        if self.state != 'done':
            raise UserError(_(
                'La nómina debe estar confirmada (estado "Hecho") antes '
                'de generar el XML de nómina electrónica.'
            ))

        if self.l10n_co_ne_state not in ('draft', 'rejected'):
            raise UserError(_(
                'Solo puede generar XML para nóminas en estado DIAN '
                '"Borrador" o "Rechazado".'
            ))

        company = self.company_id
        self._validate_company_ne_config(company)

        employee = self.employee_id
        if not employee.identification_id:
            raise UserError(_(
                'El empleado %s no tiene número de identificación configurado.',
                employee.name,
            ))

        contract = self.contract_id
        if not contract:
            raise UserError(_(
                'La nómina %s no tiene contrato asociado.',
                self.number or self.name,
            ))

    def _validate_company_ne_config(self, company):
        """Valida la configuración de nómina electrónica de la empresa."""
        missing = []
        mode = company.l10n_co_ne_operation_mode_ids
        if not mode or not mode.software_id:
            missing.append(_('ID Software Nómina'))
        if not mode or not mode.software_pin:
            missing.append(_('PIN Software Nómina'))
        if not company._get_ne_certificate():
            missing.append(_('Certificado Digital'))
        if missing:
            raise UserError(_(
                'Faltan los siguientes datos de configuración de nómina '
                'electrónica en la empresa %s:\n• %s',
                company.name,
                '\n• '.join(missing),
            ))

        certificate = company._get_ne_certificate()
        if certificate and certificate.date_end and certificate.date_end < fields.Datetime.now():
            raise UserError(_(
                'El certificado digital de la empresa %s está vencido '
                '(venció el %s). Cargue o seleccione un certificado '
                'vigente antes de continuar.',
                company.name,
                certificate.date_end,
            ))

        # AUD-DIAN-34 (2026-10-05): el Anexo Técnico (NIE030) es explícito -- "Para Colombia
        # se debe colocar 'COP'" en TipoMoneda, sin excepción. No se parametriza: es una
        # constante del Anexo (nomina_xml_builder.NE_TIPO_MONEDA), así que una compañía en
        # otra moneda debe fallar aquí, antes de generar un XML inválido, en vez de enviar
        # "COP" por encima de montos que en realidad están en otra moneda.
        if company.currency_id.name != nomina_xml_builder.NE_TIPO_MONEDA:
            raise UserError(_(
                'La compañía %(company)s tiene moneda "%(currency)s" configurada, pero la '
                'Nómina Electrónica DIAN exige TipoMoneda="%(cop)s" (Anexo Técnico, NIE030: '
                '"Para Colombia se debe colocar \'%(cop)s\'"). Configure la compañía en '
                'pesos colombianos antes de generar nómina electrónica.',
                company=company.name, currency=company.currency_id.name,
                cop=nomina_xml_builder.NE_TIPO_MONEDA,
            ))

    def _ne_expected_prefix(self):
        """Prefijo que DEBE tener un consecutivo oficial de este payslip.

        AUD-DIAN-34 (2026-10-04): incidente real en Guapante -- la
        secuencia temporal (``l10n_co_ne_pre_sequence_id``) quedó mal
        configurada apuntando a la de Notas de Ajuste, así que una
        nómina INDIVIDUAL terminó con consecutivo "NA..." (prefijo de
        ajuste). El único chequeo que existía ("no empieza por
        PRE-NOM") no detecta esto -- un valor con el prefijo *equivocado*
        pero que no es PRE-NOM pasaba como si fuera válido. Defensa en
        profundidad: el consecutivo solo se considera válido si tiene
        el prefijo que corresponde a este tipo de documento.
        """
        self.ensure_one()
        company = self.company_id
        if self.l10n_co_ne_is_adjustment:
            return company.l10n_co_ne_adjust_prefix or 'NA'
        return company.l10n_co_ne_payroll_prefix or 'NE'

    def _get_next_ne_consecutive(self):
        """
        Genera el siguiente consecutivo de nómina electrónica para la empresa
        utilizando las secuencias configuradas en la compañía.
        """
        self.ensure_one()
        company = self.company_id

        # Si ya tiene un consecutivo asignado con el prefijo correcto para
        # este tipo de documento, lo reutilizamos -- cualquier otro caso
        # (temporal PRE-NOM, o el prefijo de ajuste/nómina equivocado) se
        # reasigna.
        expected_prefix = self._ne_expected_prefix()
        if self.l10n_co_ne_consecutive and self.l10n_co_ne_consecutive.startswith(expected_prefix):
            return self.l10n_co_ne_consecutive

        if self.l10n_co_ne_is_adjustment:
            seq = self.env['ir.sequence'].search([
                ('code', '=', 'l10n_co_nomina.ajuste'),
                ('|'),
                ('company_id', '=', company.id),
                ('company_id', '=', False)
            ], limit=1)
            if seq:
                return seq.next_by_id()
            prefix = company.l10n_co_ne_adjust_prefix or 'NA'
        else:
            if company.l10n_co_ne_sequence_id:
                return company.l10n_co_ne_sequence_id.next_by_id()
            prefix = company.l10n_co_ne_payroll_prefix or 'NE'

        # Fallback manual por si no hay secuencia configurada
        last_payslip = self.search(
            [
                ('company_id', '=', company.id),
                ('l10n_co_ne_consecutive', '!=', False),
                ('l10n_co_ne_consecutive', '=like', prefix + '%'),
            ],
            order='l10n_co_ne_consecutive desc',
            limit=1,
        )
        if last_payslip and last_payslip.l10n_co_ne_consecutive and not last_payslip.l10n_co_ne_consecutive.startswith('PRE-NOM'):
            last_num_str = last_payslip.l10n_co_ne_consecutive[len(prefix):]
            try:
                next_num = int(last_num_str) + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1

        return '%s%s' % (prefix, str(next_num).zfill(8))


    def _get_ne_xml_filename(self):
        """Genera el nombre del archivo XML de nómina electrónica."""
        company = self.company_id
        nit = (company.vat or 'SIN_NIT').replace('-', '').strip()
        return 'ne_%s_%s.xml' % (nit, self.l10n_co_ne_consecutive or 'DRAFT')
