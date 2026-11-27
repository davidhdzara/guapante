# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Pacto de desalarización del EMPLEADO (.302, doc 76 §2.3, decisión del TL del 22-nov por la revisión v19 del consultor).

Un pago no salarial «por pacto» (``hr.salary.rule.l10n_co_pila_origen_no_salarial = 'pacto'``: auxilio de alimentación, bonificación no salarial) solo deja de
sumar al IBC si empleador y trabajador lo PACTARON por escrito (art. 128 CST y art. 17 Ley 344/1996) y el empleador puede probarlo: sentencia de unificación del
Consejo de Estado 25185 de 2021, reglas 2, 4 y 5 (doc 75 §1). Este modelo registra ese pacto: UNA fila por empleado y concepto, con la fecha de firma, la fecha de
fin (opcional) y el documento firmado.

Cuelga del EMPLEADO y no del contrato: al renovar el contrato (un ``hr.contract`` nuevo) el pacto no se pierde y en Odoo 19 ``hr.contract`` no existe (pasa a
``hr.version``). Cubre los recibos cuyo ``date_to`` cae entre la fecha de firma y la de fin (fin vacía = vigente) SIEMPRE QUE tenga el documento firmado adjunto: se puede guardar sin
documento (para cargarlo y escanearlo después) pero mientras no lo tenga NO cubre («pacto sin soporte»), porque el pacto debe estar probado y la carga de la prueba es del
empleador (SU 25185 de 2021, reglas 4 y 5; decisión del TL del 22-nov). El concepto se compara por ``code``: las reglas se duplican por estructura.

Sin pacto el recibo AVISA siempre (``HrPayslip.l10n_co_ne_aviso_pacto``) y se rechaza al CONFIRMAR solo si el interruptor ``l10n_co_exigir_pacto_no_salarial``
(``hr.rule.parameter``, 0 de fábrica) vale 1: así instalar el módulo no bloquea los recibos hasta que se carguen los pactos. NO EJECUTADO EN ODOO al escribirlo."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class L10nCoEmployeePacto(models.Model):
    _name = 'l10n.co.employee.pacto'
    _inherit = ['l10n.co.adjunto.vinculado']      # H-F1-07: la vinculacion del documento firmado es la misma del dia de descanso pactado
    _description = 'Pacto de desalarización del empleado'
    _order = 'employee_id, salary_rule_id, fecha_firma desc, id'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, ondelete='cascade', index=True)
    salary_rule_id = fields.Many2one(
        'hr.salary.rule', string='Concepto', required=True, ondelete='restrict',
        domain="[('l10n_co_pila_origen_no_salarial', '=', 'pacto')]",
        help='Concepto no salarial cubierto por el pacto: solo los pagos no salariales por pacto de desalarización (origen «Por pacto»). El pacto cubre al concepto '
             'por su código, en cualquier estructura.')
    fecha_firma = fields.Date(string='Fecha de firma', required=True)
    fecha_fin = fields.Date(
        string='Fecha de fin', help='Opcional. Vacía = el pacto sigue vigente. Cubre los recibos cuyo «Hasta» cae entre la fecha de firma y esta fecha.')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'l10n_co_employee_pacto_attachment_rel', 'pacto_id', 'attachment_id', string='Documento firmado',
        help='El pacto debe estar plenamente probado y la carga de la prueba es del empleador (Consejo de Estado, SU 25185 de 2021): adjunte el documento firmado. Se puede '
             'guardar el pacto sin documento, pero mientras no lo tenga NO cubre ningún recibo (el recibo avisa «pacto sin soporte»).')

    @api.constrains('fecha_firma', 'fecha_fin')
    def _check_fechas(self):
        for pacto in self:
            if pacto.fecha_fin and pacto.fecha_firma and pacto.fecha_fin < pacto.fecha_firma:
                raise ValidationError(_('La fecha de fin del pacto de «%(concepto)s» de %(empleado)s no puede ser anterior a la fecha de firma.',
                                        concepto=pacto.salary_rule_id.name, empleado=pacto.employee_id.name))

    @api.constrains('salary_rule_id')
    def _check_concepto_por_pacto(self):
        for pacto in self:
            if pacto.salary_rule_id.l10n_co_pila_origen_no_salarial != 'pacto':
                raise ValidationError(_(
                    'El concepto «%(concepto)s» no es un pago no salarial por pacto de desalarización: solo esos conceptos necesitan un pacto escrito.',
                    concepto=pacto.salary_rule_id.name))

    # ── qué recibos cubre ────────────────────────────────────────────────────────────────────────────────────────────────────────
    @api.model
    def _lineas_sin_cobertura(self, recibo):
        """``[(línea, motivo)]`` de un pago no salarial POR PACTO del recibo (categoría ``DEV_NOSAL``, origen «pacto», con valor) que ningún pacto cubre. El pacto debe ser del
        mismo empleado, de un concepto con el mismo ``code``, con una vigencia que incluya el ``date_to`` del recibo y CON el documento firmado. Motivo ``'sin_pacto'``: no hay
        ningún pacto vigente; ``'sin_soporte'``: hay pacto vigente pero ninguno trae documento (decisión del TL, 22-nov: el pacto debe estar probado, SU 25185). Los pagos no
        salariales por naturaleza no exigen pacto. Se lee con ``sudo`` solo para saber si hay cobertura (el aviso se calcula al abrir el formulario con cualquier usuario de
        nómina)."""
        recibo.ensure_one()
        lineas = recibo.line_ids.filtered(
            lambda l: l.total and l.salary_rule_id.category_id.code == 'DEV_NOSAL' and l.salary_rule_id.l10n_co_pila_origen_no_salarial == 'pacto')
        if not lineas or not recibo.employee_id or not recibo.date_to:
            return []
        vigentes = self.sudo().search([
            ('employee_id', '=', recibo.employee_id.id), ('fecha_firma', '<=', recibo.date_to),
            '|', ('fecha_fin', '=', False), ('fecha_fin', '>=', recibo.date_to)])
        con_soporte = set(vigentes.filtered('attachment_ids').mapped('salary_rule_id.code'))
        con_pacto = set(vigentes.mapped('salary_rule_id.code'))
        return [(linea, 'sin_soporte' if linea.code in con_pacto else 'sin_pacto') for linea in lineas if linea.code not in con_soporte]

    @api.model
    def _textos_sin_pacto(self, recibo):
        """Un texto por concepto sin cobertura (los mismos del aviso del borrador y del error al confirmar): «sin pacto» o «pacto sin soporte»."""
        textos, puestos = [], set()
        for linea, motivo in sorted(self._lineas_sin_cobertura(recibo), key=lambda par: (par[0].sequence, par[0].id)):
            if linea.code in puestos:
                continue
            puestos.add(linea.code)
            if motivo == 'sin_soporte':
                textos.append(_(
                    'El concepto «%(concepto)s» es un pago no salarial por pacto de desalarización (art. 128 CST y art. 17 Ley 344/1996) y el pacto de %(empleado)s está registrado '
                    'sin el documento firmado (pacto sin soporte): el pacto debe estar probado y la carga de la prueba es del empleador (Consejo de Estado, SU 25185 de 2021). '
                    'Adjunte el documento en la ficha del empleado, pestaña Nómina > Pactos de desalarización.',
                    concepto=linea.salary_rule_id.name, empleado=recibo.employee_id.name))
            else:
                textos.append(_(
                    'El concepto «%(concepto)s» es un pago no salarial por pacto de desalarización (art. 128 CST y art. 17 Ley 344/1996) y %(empleado)s no tiene registrado el pacto. '
                    'Complete en la ficha del empleado, pestaña Nómina > Pactos de desalarización: el concepto, la fecha de firma (y la de fin si el pacto terminó) y el documento firmado.',
                    concepto=linea.salary_rule_id.name, empleado=recibo.employee_id.name))
        return textos

    @api.model
    def _exigir_pacto(self, recibo):
        """Interruptor ``l10n_co_exigir_pacto_no_salarial`` (``hr.rule.parameter``, 0 de fábrica): ¿se rechaza al confirmar un recibo con un pago por pacto sin pacto?
        OBLIGATORIO: si falta el parámetro hay un error claro que dice dónde crearlo; nunca se asume un valor."""
        fecha = recibo._ne_fecha_parametros()
        try:
            return bool(recibo._rule_parameter('l10n_co_exigir_pacto_no_salarial', fecha))
        except UserError:
            raise UserError(_(
                'Falta el parámetro de nómina «Colombia: Exigir el Pacto de los Pagos No Salariales» (código l10n_co_exigir_pacto_no_salarial) para el %(fecha)s, que se '
                'necesita para confirmar el recibo de %(empleado)s con un pago no salarial por pacto. Actualice el módulo de nómina electrónica o créelo en Nómina > '
                'Configuración > Parámetros de reglas (0 = solo avisar, 1 = exigir el pacto al confirmar).',
                fecha=fecha, empleado=recibo.employee_id.name)) from None

    @api.model
    def _validar_recibos(self, recibos):
        """Al CONFIRMAR: con el interruptor en 1, un pago no salarial por pacto sin pacto lanza el error que dice qué completar. Solo se lee el parámetro si algún recibo tiene
        un pago de esos sin cubrir (un recibo sin ellos no depende de él)."""
        for recibo in recibos:
            textos = self._textos_sin_pacto(recibo)
            if textos and self._exigir_pacto(recibo):
                raise UserError('\n'.join(textos))
