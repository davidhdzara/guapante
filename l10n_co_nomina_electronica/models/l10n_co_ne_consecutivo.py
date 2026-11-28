# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Consecutivos de nómina electrónica que VIAJARON a la DIAN (.304, doc 77 con las decisiones del TL del 22-nov): una vista SQL de solo lectura que une los dos ciclos.

- Ciclo por RECIBO (habilitación): un manifiesto (``l10n.co.ne.exchange.document``) por cada envío de un recibo, con el número y el ambiente (campos de .304). Un recibo
  rechazado se regenera con número y CUNE nuevos: el manifiesto anterior queda como «rechazado» y «reemplazado por» el siguiente.
- Documento MENSUAL (producción): un intento (``l10n.co.ne.documento.intento``) por cada envío, con su número, estado y ambiente. Un rechazado puede repetir número (.337): solo queda «reemplazado por»
  cuando el envío siguiente usa uno distinto.

Sirve de lista «Consecutivos de nómina» (justifica cada hueco ante la DIAN y la UGPP) y de ÚNICA fuente de los controles de consecutivo
(``res.company._ne_mayor_consecutivo_viajado``): lo que ve el auditor es lo mismo que lo que bloquea. Sin datos propios: no se escribe nada aquí."""

from odoo import fields, models


class L10nCoNeConsecutivo(models.Model):
    _name = 'l10n.co.ne.consecutivo'
    _description = 'Consecutivo de nómina electrónica que viajó a la DIAN (solo lectura)'
    _auto = False
    _order = 'company_id, ambiente, prefijo, valor desc, id desc'
    # Los campos de las tablas que lee la vista SQL: Odoo los escribe (flush) antes de cada búsqueda de este modelo (``_flush_search`` recorre ``_depends``). Sin esto, una búsqueda en la
    # MISMA transacción que cambió el estado de un recibo o creó un manifiesto no lo veía (N2 «cv»: los controles de «no se reenvía» y los contadores de rechazados).
    _depends = {
        'hr.payslip': ['employee_id', 'l10n_co_ne_state'],
        'l10n.co.ne.exchange': ['company_id'],
        'l10n.co.ne.exchange.document': ['exchange_id', 'payslip_id', 'numero', 'ambiente'],
        'l10n.co.ne.documento': ['company_id', 'employee_id'],
        'l10n.co.ne.documento.intento': ['documento_id', 'numero', 'state', 'test_environment', 'certification_process'],
    }

    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    ambiente = fields.Selection([('habilitacion', 'Habilitación'), ('produccion', 'Producción')], string='Ambiente', readonly=True)
    origen = fields.Selection([('recibo', 'Recibo'), ('documento', 'Documento mensual')], string='Origen', readonly=True)
    prefijo = fields.Char(string='Prefijo', readonly=True)
    valor = fields.Integer(string='Valor', readonly=True, help='Parte numérica del consecutivo.')
    numero = fields.Char(string='Consecutivo', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', readonly=True)
    payslip_id = fields.Many2one('hr.payslip', string='Recibo', readonly=True)
    documento_id = fields.Many2one('l10n.co.ne.documento', string='Documento', readonly=True)
    estado = fields.Selection([
        ('aceptado', 'Aceptado'), ('rechazado', 'Rechazado'), ('pendiente', 'Pendiente'), ('fallido', 'Envío fallido')], string='Estado DIAN', readonly=True)
    reemplazado_por = fields.Char(string='Reemplazado por', readonly=True, help='Número distinto con que se volvió a enviar el documento tras un rechazo; vacío si se envió otra vez con el mismo número.')

    def init(self):
        """La vista une ``l10n_co_ne_exchange_document`` (con ``numero`` y ``ambiente``, de .304) y ``l10n_co_ne_documento_intento``: este modelo se importa DESPUÉS de los dos."""
        self.env.cr.execute('DROP VIEW IF EXISTS l10n_co_ne_consecutivo')
        self.env.cr.execute("""
            CREATE VIEW l10n_co_ne_consecutivo AS (
                SELECT u.id, u.company_id, u.ambiente, u.origen,
                       COALESCE(substring(u.numero FROM '^(\\D*)'), '') AS prefijo,
                       COALESCE(NULLIF(substring(u.numero FROM '(\\d+)$'), '')::bigint, 0) AS valor,
                       u.numero, u.employee_id, u.payslip_id, u.documento_id, u.estado, u.reemplazado_por
                  FROM (
                    -- ciclo por recibo: un manifiesto por envío; los anteriores al último de cada recibo quedaron reemplazados (el rechazado se regenera con otro número)
                    SELECT ed.id * 2 AS id, ex.company_id AS company_id, COALESCE(ed.ambiente, 'habilitacion') AS ambiente, 'recibo' AS origen, ed.numero AS numero,
                           p.employee_id AS employee_id, ed.payslip_id AS payslip_id, NULL::integer AS documento_id,
                           CASE WHEN LEAD(ed.numero) OVER (PARTITION BY ed.payslip_id ORDER BY ed.id) IS NOT NULL THEN 'rechazado'
                                WHEN p.l10n_co_ne_state IN ('accepted', 'eliminated') THEN 'aceptado'    -- eliminado por una nota: el número ya había sido aceptado
                                WHEN p.l10n_co_ne_state = 'rejected' THEN 'rechazado'
                                ELSE 'pendiente' END AS estado,
                           LEAD(ed.numero) OVER (PARTITION BY ed.payslip_id ORDER BY ed.id) AS reemplazado_por
                      FROM l10n_co_ne_exchange_document ed
                      JOIN l10n_co_ne_exchange ex ON ex.id = ed.exchange_id
                      JOIN hr_payslip p ON p.id = ed.payslip_id
                     WHERE ed.numero IS NOT NULL
                    UNION ALL
                    -- documento mensual: un intento por envío, con su número, estado y ambiente
                    SELECT i.id * 2 + 1 AS id, d.company_id AS company_id,
                           CASE WHEN i.test_environment OR i.certification_process THEN 'habilitacion' ELSE 'produccion' END AS ambiente, 'documento' AS origen, i.numero AS numero,
                           d.employee_id AS employee_id, NULL::integer AS payslip_id, d.id AS documento_id,
                           CASE i.state WHEN 'invoice_accepted' THEN 'aceptado' WHEN 'invoice_rejected' THEN 'rechazado'
                                        WHEN 'invoice_pending' THEN 'pendiente' ELSE 'fallido' END AS estado,
                           CASE WHEN i.state = 'invoice_rejected' THEN NULLIF(LEAD(i.numero) OVER (PARTITION BY i.documento_id ORDER BY i.id), i.numero) END AS reemplazado_por
                      FROM l10n_co_ne_documento_intento i
                      JOIN l10n_co_ne_documento d ON d.id = i.documento_id
                     WHERE i.numero IS NOT NULL
                  ) u
            )""")
