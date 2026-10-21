# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Modo de Operación de Nómina Electrónica DIAN -- doc 22 §1.

Reemplaza los campos planos `l10n_co_ne_software_id`/`_software_pin`/
`_test_set_id` que vivían directo en res.company, con una tabla propia
que replica visualmente "Modos de Operación" de Facturación Electrónica
(CO) (`l10n_co_dian.operation_mode`).

A diferencia de DIAN (que sí necesita una fila por tipo de documento --
Facturas, Documentos Soporte, etc., cada uno con su propio registro ante
la DIAN), Nómina Electrónica usa SIEMPRE el mismo Software ID/PIN/TestSetID
para Nómina Individual y Nota de Ajuste -- confirmado contra la guía
operativa propia del módulo (`guia_configuracion_y_envio_nomina_electronica.md`
§6: "Un Software ID y PIN para tu software... Un Test Set ID para el
ciclo de pruebas", singular) y contra el envío real (SendTestSetAsync
manda los 3 tipos de documento juntos en un solo lote). Por eso este
modelo NO tiene un campo `operation_mode`/Selection como el de DIAN --
la tabla siempre tiene como máximo 1 fila por compañía
(UNIQUE(company_id)), fingir un Selection de "tipo de documento" aquí
sería una opción que nunca tendría un segundo valor real.
"""

from odoo import fields, models


class L10nCoNeOperationMode(models.Model):
    _name = 'l10n.co.ne.operation_mode'
    _description = 'Modo de Operación de Nómina Electrónica DIAN'

    software_id = fields.Char(
        string='Software ID',
        required=True,
        help='Identificador del software asignado por la DIAN para '
             'nómina electrónica. Se obtiene en el portal de habilitación.',
    )
    software_pin = fields.Char(
        string='Software PIN',
        required=True,
        help='PIN del software de nómina electrónica asignado por la DIAN.',
    )
    test_set_id = fields.Char(
        string='ID de Pruebas',
        help='Identificador del set de pruebas (TestSetID) asignado por '
             'la DIAN durante el proceso de habilitación. Solo aplica en '
             'ambiente de Habilitación (Pruebas).',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
    )

    _sql_constraints = [
        (
            'uniq_operation_mode_company',
            'UNIQUE(company_id)',
            'Solo puede haber un modo de operación de nómina electrónica '
            'por compañía.',
        ),
    ]

    def _compute_display_name(self):
        for record in self:
            record.display_name = 'Modo de Operación Nómina Electrónica'
