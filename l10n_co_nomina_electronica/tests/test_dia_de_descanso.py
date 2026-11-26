# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-07 (doc 92; decisiones D-07 del TL del 22-nov): el dia de descanso del empleado pactado por escrito (Ley 2466 de 2025, art. 14, par. 3). Registro ``l10n.co.employee.descanso`` (vigencia + documento; sin
documento NO cubre), ``HrEmployee._ne_dia_de_descanso`` (el pactado o, sin pacto, el DOMINGO por la presuncion de la ley) y el aviso del recibo (``l10n_co_ne_aviso_descanso``): horas de recargo dominical sin fecha de
descanso o festivo trabajada, calendario con jornada el dia de descanso, pacto sin documento. Agosto de 2026: el 2, 9, 16, 23 y 30 son domingos; el 3, 10, 17, 24 y 31, lunes."""

from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

LUNES, DOMINGO = 0, 6


@tagged('post_install', '-at_install')
class TestDiaDeDescanso(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Día de Descanso', 'l10n_co_ne_pago_dominical_mensual': 'dia_mas_recargo'})
        cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'Prueba Estructura Descanso', 'country_id': cls.env.ref('base.co').id})
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.mar_dom = cls._calendario((1, 2, 3, 4, 5, 6))           # el de Guapante: martes a domingo, el lunes de descanso
        cls.lun_vie = cls._calendario((0, 1, 2, 3, 4))

    @classmethod
    def _calendario(cls, dias):
        lineas = []
        for dia in dias:
            lineas += [(0, 0, {'name': 'Mañana %s' % dia, 'dayofweek': str(dia), 'hour_from': 8.0, 'hour_to': 12.0}),
                       (0, 0, {'name': 'Tarde %s' % dia, 'dayofweek': str(dia), 'hour_from': 13.0, 'hour_to': 17.0})]
        return cls.env['resource.calendar'].create({'name': 'Calendario %s' % (dias,), 'tz': 'America/Bogota', 'attendance_ids': lineas})

    def _empleado(self, nombre='Empleado Descanso'):
        return self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': nombre, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})

    def _pacto(self, empleado, dia, desde=date(2026, 1, 1), hasta=False, con_documento=True):
        valores = {'employee_id': empleado.id, 'dia_semana': str(dia), 'fecha_firma': desde, 'fecha_fin': hasta}
        if con_documento:
            valores['attachment_ids'] = [(0, 0, {'name': 'otrosi.txt', 'raw': b'otrosi firmado'})]
        return self.env['l10n.co.employee.descanso'].create(valores)

    def _recibo(self, empleado, calendario, horas_dominicales=False):
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato %s' % empleado.name, 'employee_id': empleado.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'resource_calendar_id': calendario.id})
        contrato.generate_work_entries(date(2026, 8, 1), date(2026, 8, 31))
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo %s' % empleado.name, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id, 'struct_id': self.nomina.id,
            'date_from': date(2026, 8, 1), 'date_to': date(2026, 8, 31)})
        if horas_dominicales:
            tipo = self.env['hr.payslip.input.type'].search([('code', '=', 'CO_HRDDF')], limit=1)
            recibo.write({'input_line_ids': [(0, 0, {'input_type_id': tipo.id, 'amount': 8.0})]})
            recibo.compute_sheet()
        return recibo

    # ── el registro y la funcion ──
    def test_sin_registro_el_descanso_es_el_domingo_por_la_presuncion_de_la_ley(self):
        self.assertEqual(self._empleado()._ne_dia_de_descanso(date(2026, 8, 3)), DOMINGO)

    def test_con_pacto_y_documento_rige_el_dia_pactado_dentro_de_su_vigencia(self):
        empleado = self._empleado()
        self._pacto(empleado, LUNES, desde=date(2026, 2, 1), hasta=date(2026, 6, 30))
        self.assertEqual(empleado._ne_dia_de_descanso(date(2026, 2, 1)), LUNES)
        self.assertEqual(empleado._ne_dia_de_descanso(date(2026, 6, 30)), LUNES)
        self.assertEqual(empleado._ne_dia_de_descanso(date(2026, 1, 31)), DOMINGO)          # antes de la firma
        self.assertEqual(empleado._ne_dia_de_descanso(date(2026, 7, 1)), DOMINGO)           # despues de la fecha de fin

    def test_un_pacto_sin_documento_no_cubre_y_se_marca_sin_soporte(self):
        empleado = self._empleado()
        self._pacto(empleado, LUNES, con_documento=False)
        self.assertEqual(empleado._ne_dia_de_descanso(date(2026, 8, 3)), DOMINGO)
        self.assertTrue(empleado._ne_descanso_sin_soporte(date(2026, 8, 3)))
        self.assertFalse(self._empleado('Otro')._ne_descanso_sin_soporte(date(2026, 8, 3)))

    def test_la_fecha_de_fin_no_puede_ser_anterior_a_la_de_firma(self):
        with self.assertRaises(ValidationError):
            self._pacto(self._empleado(), LUNES, desde=date(2026, 3, 1), hasta=date(2026, 2, 1))

    def test_dos_pactos_del_mismo_empleado_no_pueden_cruzar_su_vigencia(self):
        empleado = self._empleado()
        self._pacto(empleado, LUNES, desde=date(2026, 1, 1), hasta=date(2026, 6, 30))
        with self.assertRaises(ValidationError):
            self._pacto(empleado, 5, desde=date(2026, 6, 30))                              # cruza el 30-jun
        self._pacto(empleado, 5, desde=date(2026, 7, 1))                                  # el siguiente dia si
        self.assertEqual(empleado._ne_dia_de_descanso(date(2026, 8, 3)), 5)

    def test_el_documento_subido_antes_de_guardar_se_vincula_al_registro(self):
        """Mismo mixin del pacto de desalarizacion: el adjunto sin res_id queda ligado al registro."""
        adjunto = self.env['ir.attachment'].create({'name': 'otrosi.txt', 'raw': b'x', 'res_model': 'l10n.co.employee.descanso', 'res_id': 0})
        registro = self.env['l10n.co.employee.descanso'].create({
            'employee_id': self._empleado().id, 'dia_semana': '0', 'fecha_firma': date(2026, 1, 1), 'attachment_ids': [(6, 0, adjunto.ids)]})
        self.assertEqual((adjunto.res_model, adjunto.res_id), ('l10n.co.employee.descanso', registro.id))

    # ── el aviso del recibo ──
    def test_calendario_lunes_a_viernes_sin_pacto_no_avisa(self):
        recibo = self._recibo(self._empleado('Estandar'), self.lun_vie)
        self.assertFalse(recibo.l10n_co_ne_aviso_descanso)

    def test_guapante_sin_el_pacto_cargado_avisa_que_se_presume_domingo(self):
        """Calendario martes a domingo y sin el pacto del lunes: el calendario tiene jornada el domingo, que se presume de descanso."""
        recibo = self._recibo(self._empleado('Guapante Sin Pacto'), self.mar_dom)
        self.assertIn('tiene jornada el domingo', recibo.l10n_co_ne_aviso_descanso)
        self.assertIn('presunción de la ley', recibo.l10n_co_ne_aviso_descanso)
        self.assertIn('Día de descanso pactado', recibo.l10n_co_ne_aviso_descanso)

    def test_guapante_con_el_pacto_del_lunes_y_el_documento_no_avisa(self):
        empleado = self._empleado('Guapante Con Pacto')
        self._pacto(empleado, LUNES)
        self.assertFalse(self._recibo(empleado, self.mar_dom).l10n_co_ne_aviso_descanso)

    def test_el_pacto_del_lunes_con_un_calendario_que_trabaja_el_lunes_avisa(self):
        empleado = self._empleado('Pacto Lunes Calendario Lunes')
        self._pacto(empleado, LUNES)
        self.assertIn('tiene jornada el lunes', self._recibo(empleado, self.lun_vie).l10n_co_ne_aviso_descanso)

    def test_el_pacto_sin_documento_avisa(self):
        empleado = self._empleado('Pacto Sin Documento')
        self._pacto(empleado, LUNES, con_documento=False)
        self.assertIn('sin el documento firmado', self._recibo(empleado, self.mar_dom).l10n_co_ne_aviso_descanso)

    def test_horas_dominicales_sin_fecha_de_descanso_ni_festivo_trabajada_avisa(self):
        """Calendario lunes a viernes (sin entradas en domingo) con horas de recargo dominical digitadas: ninguna fecha trabajada es festivo ni domingo."""
        recibo = self._recibo(self._empleado('Horas Sin Domingo'), self.lun_vie, horas_dominicales=True)
        self.assertIn('trae horas de recargo dominical o festivo', recibo.l10n_co_ne_aviso_descanso)
        self.assertIn('domingo', recibo.l10n_co_ne_aviso_descanso)

    def test_horas_dominicales_con_el_domingo_trabajado_y_sin_pacto_no_avisan_por_las_horas(self):
        """Calendario martes a domingo (hay entradas en domingo) y el descanso presumido es el domingo: las horas dominicales tienen fecha. Solo queda el aviso del calendario."""
        recibo = self._recibo(self._empleado('Horas Con Domingo'), self.mar_dom, horas_dominicales=True)
        self.assertNotIn('trae horas de recargo dominical o festivo', recibo.l10n_co_ne_aviso_descanso)

    def test_horas_dominicales_en_domingo_con_el_pacto_del_lunes_avisan(self):
        """Con el lunes pactado, el domingo es un dia ordinario: las horas de recargo dominical digitadas no tienen una fecha de descanso trabajada (el lunes no tiene entradas)."""
        empleado = self._empleado('Horas Domingo Pacto Lunes')
        self._pacto(empleado, LUNES)
        self.assertIn('trae horas de recargo dominical o festivo', self._recibo(empleado, self.mar_dom, horas_dominicales=True).l10n_co_ne_aviso_descanso)

    def test_la_vista_trae_el_aviso_y_la_lista_del_empleado(self):
        from lxml import etree
        recibo = etree.fromstring(self.env['hr.payslip'].get_view(view_type='form')['arch'].encode())
        self.assertTrue(recibo.xpath("//field[@name='l10n_co_ne_aviso_descanso']"))
        empleado = etree.fromstring(self.env['hr.employee'].get_view(view_type='form')['arch'].encode())
        self.assertTrue(empleado.xpath("//field[@name='l10n_co_descanso_ids']"))
