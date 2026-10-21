# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Post-migración 18.0.3.0.4 -- certificado digital de nómina electrónica
consolidado con certificate.certificate nativo (doc 17: elimina
l10n_co_ne_cert_file/_filename/_password en favor de
l10n_co_ne_certificate_id).

A diferencia de 18.0.3.0.3 (embargo híbrido), acá no hace falta
pre-migrate: l10n_co_ne_cert_file tenía attachment=True, así que nunca
tuvo columna propia en res_company (el contenido, si existía, vivía en
ir_attachment) -- no hay columna que dropear ni vista huérfana que
bloquee la carga.

Verificado por SSH en staging_produccion antes de escribir este script:
0 filas en ir_attachment con res_model='res.company' AND
res_field='l10n_co_ne_cert_file', 0 compañías con l10n_co_ne_cert_password
no nulo. En ese ambiente este script no encuentra nada que loguear, pero
se mantiene defensivo para otros clientes donde sí pueda haber datos --
no es seguro migrar automáticamente un .p12 viejo a un
certificate.certificate: el certificado real de facturación electrónica
puede no coincidir con el que se había cargado aparte para nómina, y no
hay forma de recuperar la contraseña PKCS12 desde la BD para intentarlo.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # OR con l10n_co_ne_cert_password IS NOT NULL: cubre tambien el caso
    # (poco probable pero posible en otro cliente) de una compania con
    # contrasena seteada pero que nunca llego a cargar el archivo .p12
    # -- hallazgo de completitud de Tech Lead, sin datos reales en este
    # ambiente (0 en ambas condiciones), pero el script debe ser
    # defensivo para otros clientes.
    cr.execute("""
        SELECT DISTINCT c.id, c.name
        FROM res_company c
        WHERE EXISTS (
            SELECT 1 FROM ir_attachment a
            WHERE a.res_model = 'res.company'
              AND a.res_field = 'l10n_co_ne_cert_file'
              AND a.res_id = c.id
        )
        OR c.l10n_co_ne_cert_password IS NOT NULL
    """)
    companies_with_data = cr.fetchall()

    if companies_with_data:
        _logger.warning(
            'Post-migración 18.0.3.0.4: %d compañía(s) tenían datos de '
            'certificado .p12 propio de nómina (archivo en '
            'l10n_co_ne_cert_file y/o contraseña en '
            'l10n_co_ne_cert_password, ambos campos eliminados): %s. '
            'Confirmar manualmente con el cliente cuál '
            'certificate.certificate (Ajustes > Técnico > Certificados) '
            'corresponde a cada una -- lo más probable es que ya exista '
            'uno por facturación electrónica -- y asignarlo en '
            'res.company.l10n_co_ne_certificate_id. El archivo .p12 '
            'viejo (si lo había) queda huérfano en ir_attachment, sin '
            'limpiar automáticamente (no se puede recuperar el '
            'certificado real sin la contraseña en texto plano).',
            len(companies_with_data), companies_with_data,
        )
    else:
        _logger.info(
            'Post-migración 18.0.3.0.4: ninguna compañía tenía datos de '
            'certificado .p12 propio de nómina (ni archivo ni '
            'contraseña) -- nada que reportar.'
        )
