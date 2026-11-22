# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F2-03 (doc 94, aprobado por el TL el 22-nov): seguridad multicompañia con usuarios REALES de dos companias (``with_user`` y ``allowed_company_ids``): el usuario de A no VE, no LEE, no ESCRIBE, no CREA
y no BORRA lo de B (y al reves), por cada rol del modulo: administrador de nomina, oficial de nomina y oficial que solo tiene Ausencias. Antes las pruebas de aislamiento solo hacian ``search`` con administradores
y solo en los modelos con ``company_id``.

Cada prueba trae su control POSITIVO (el mismo usuario si ve/lee/escribe lo de su compania) para que no pase en vacio. Premisas por confirmar en la N2 (SSH cerrado, nada ejecutado): que las reglas nativas
del recibo, el empleado, el contrato y la ausencia de ``hr``/``hr_payroll``/``hr_holidays`` filtran por compania (doc 51 §1.2), que ``ir.attachment`` sigue la regla del registro (``check``), y los fixtures de los
modelos derivados (documento, intento, intercambio, manifiesto, cálculo, concepto, ajuste, tercero)."""

from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.service.model import get_public_method
from odoo.tests.common import TransactionCase, tagged

CLAVES = ('a', 'b')
CODIGO_NE = 'NE-H-F2-03'


@tagged('post_install', '-at_install')
class TestMultiempresaSeguridad(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        co = env.ref('base.co')
        datos = {'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.compania = {c: env['res.company'].create(dict(datos, name='Seguridad %s' % c.upper(), country_id=co.id)) for c in CLAVES}
        cls.a, cls.b = cls.compania['a'], cls.compania['b']
        grupos = {
            'usuario': env.ref('base.group_user'), 'admin_nomina': env.ref('hr_payroll.group_hr_payroll_manager'), 'oficial': env.ref('hr_payroll.group_hr_payroll_user'),
            'ausencias': env.ref('hr_holidays.group_hr_holidays_user'), 'sistema': env.ref('base.group_system'), 'contactos': env.ref('base.group_partner_manager')}

        def usuario(login, companias, *nombres_de_grupo):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': login, 'login': login, 'email': '%s@example.com' % login, 'company_id': companias[0].id, 'company_ids': [(6, 0, companias.ids)],
                'groups_id': [(6, 0, [grupos[n].id for n in ('usuario',) + nombres_de_grupo])]})

        cls.admin = {c: usuario('seg_admin_%s' % c, cls.compania[c], 'admin_nomina') for c in CLAVES}
        cls.oficial = {c: usuario('seg_oficial_%s' % c, cls.compania[c], 'oficial') for c in CLAVES}
        cls.ausencias = {c: usuario('seg_ausencias_%s' % c, cls.compania[c], 'ausencias') for c in CLAVES}
        cls.contador = {c: usuario('seg_contador_%s' % c, cls.compania[c], 'contactos') for c in CLAVES}
        cls.sistema = usuario('seg_sistema', cls.a | cls.b, 'admin_nomina', 'sistema')
        cls.multi = usuario('seg_multi', cls.a | cls.b, 'admin_nomina')

        cls.structure_type = env['hr.payroll.structure.type'].create({'name': 'Prueba Seguridad', 'country_id': co.id})
        cls.nomina = env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.regla = env['hr.salary.rule'].search([('code', '=', 'CO_BONIF_NOSAL')], limit=1)
        cls.tipo_incapacidad = env.ref('l10n_co_nomina_electronica.hr_leave_type_co_inc_comun')
        cls.d = {c: cls._sembrar(c) for c in CLAVES}
        cls.uvt_compartida = env['l10n.co.retefuente.uvt'].create({'year': '2032', 'company_id': False, 'procedure': '1'})

    @classmethod
    def _sembrar(cls, clave):
        """Un registro de cada modelo propio en la compañia ``clave`` (con el superusuario de la transaccion)."""
        env, compania = cls.env, cls.compania[clave]
        d = type('Sembrado', (), {})()
        d.compania = compania
        d.empleado = env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Seguridad %s' % clave, 'company_id': compania.id, 'l10n_co_ne_payment_method': '10'})
        d.contrato = env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato Seguridad %s' % clave, 'employee_id': d.empleado.id,
            'company_id': compania.id, 'structure_type_id': cls.structure_type.id, 'wage': 3000000.0, 'date_start': date(2025, 1, 1), 'state': 'open'})
        d.recibo = env['hr.payslip'].create({
            'name': 'Recibo Seguridad %s' % clave, 'employee_id': d.empleado.id, 'contract_id': d.contrato.id, 'company_id': compania.id, 'struct_id': cls.nomina.id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})
        d.uvt = env['l10n.co.retefuente.uvt'].create({'year': '2031', 'company_id': compania.id, 'procedure': '1'})
        d.procedure2 = env['l10n.co.retefuente.procedure2'].create({'contract_id': d.contrato.id, 'semester_start': date(2026, 7, 1)})
        d.descanso = env['l10n.co.employee.descanso'].create({'employee_id': d.empleado.id, 'dia_semana': '0', 'fecha_firma': date(2026, 1, 1)})
        d.pacto = env['l10n.co.employee.pacto'].create({'employee_id': d.empleado.id, 'salary_rule_id': cls.regla.id, 'fecha_firma': date(2026, 1, 1)})
        d.ibc = env['l10n.co.ibc.mensual'].create({'company_id': compania.id, 'employee_id': d.empleado.id, 'period': date(2026, 3, 1)})
        d.planilla = env['l10n.co.pila.planilla'].create({'company_id': compania.id, 'period': date(2026, 3, 1), 'tipo_planilla': 'E', 'operador_code': 'X'})
        d.ugpp = env['l10n_co_nomina.ugpp'].create({'company_id': compania.id, 'year': 2026, 'month': '3', 'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})
        d.modo = env['l10n.co.ne.operation_mode'].create({'company_id': compania.id, 'software_id': 'SOFT-%s' % clave, 'software_pin': 'PIN-%s' % clave, 'test_set_id': 'TS'})
        d.documento = env['l10n.co.ne.documento'].create({'company_id': compania.id, 'employee_id': d.empleado.id, 'period': date(2026, 3, 1)})
        d.intento = env['l10n.co.ne.documento.intento'].create({'documento_id': d.documento.id, 'state': 'invoice_accepted', 'numero': '%s-INT-1' % CODIGO_NE})
        d.intercambio = env['l10n.co.ne.exchange'].create_exchange(compania, 'send_sync', 'https://dian.example/%s' % clave, {'RawRequest': b'x', 'RawResponse': b'y'}, d.recibo)
        d.manifiesto = env['l10n.co.ne.exchange.document'].create({
            'exchange_id': d.intercambio.id, 'payslip_id': d.recibo.id, 'file_name': 'ne_900_%s.xml' % clave, 'numero': '%s-MAN-1' % CODIGO_NE, 'ambiente': 'habilitacion'})
        d.calculo = env['l10n.co.payslip.calculo'].with_context(ne_regenerar_calculo=True).create({'slip_id': d.recibo.id})
        d.concepto = env['l10n.co.payslip.concepto'].with_context(ne_regenerar_conceptos=True).create({'slip_id': d.recibo.id})
        d.ajuste = env['l10n.co.payslip.ajuste'].with_context(ne_registro_sugeridos=True).create({'slip_id': d.recibo.id, 'salary_rule_id': cls.regla.id})
        d.tercero = env['l10n.co.payslip.tercero'].create({'slip_id': d.recibo.id, 'rule_code': 'CO_LIBRANZAS'})
        d.ausencia = env['hr.leave'].create({
            'employee_id': d.empleado.id, 'holiday_status_id': cls.tipo_incapacidad.id, 'request_date_from': date(2026, 3, 2), 'request_date_to': date(2026, 3, 6)})
        return d

    # ── utilidades ──────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _como(self, modelo, usuario, *companias):
        """El modelo visto por ``usuario`` con SOLO esas companias activas (por defecto, las suyas)."""
        activas = [c.id for c in companias] or usuario.company_ids.ids
        return self.env[modelo].with_user(usuario).with_context(allowed_company_ids=activas)

    def _propios(self):
        """(nombre del modelo, atributo del sembrado) de los modelos persistentes que el modulo define, salvo el catalogo y la vista SQL."""
        return [
            ('l10n.co.retefuente.uvt', 'uvt'), ('l10n.co.retefuente.procedure2', 'procedure2'), ('l10n.co.employee.descanso', 'descanso'), ('l10n.co.employee.pacto', 'pacto'),
            ('l10n.co.ibc.mensual', 'ibc'), ('l10n.co.pila.planilla', 'planilla'), ('l10n_co_nomina.ugpp', 'ugpp'), ('l10n.co.ne.operation_mode', 'modo'),
            ('l10n.co.ne.documento', 'documento'), ('l10n.co.ne.documento.intento', 'intento'), ('l10n.co.ne.exchange', 'intercambio'), ('l10n.co.ne.exchange.document', 'manifiesto'),
            ('l10n.co.payslip.calculo', 'calculo'), ('l10n.co.payslip.concepto', 'concepto'), ('l10n.co.payslip.ajuste', 'ajuste'), ('l10n.co.payslip.tercero', 'tercero')]

    def _roles(self):
        return (('administrador de nomina', self.admin), ('oficial de nomina', self.oficial))

    def test_se_prueban_todos_los_modelos_propios_persistentes(self):
        """Si un modelo propio nuevo no esta en la lista de esta prueba, falla y lo nombra (junto al catalogo y la vista SQL, que tienen su prueba)."""
        from .test_multiempresa_descubrimiento import CATALOGOS_SIN_COMPANIA, _modelos_propios
        cubiertos = {m for m, _a in self._propios()} | set(CATALOGOS_SIN_COMPANIA) | {'l10n.co.ne.consecutivo'}
        self.assertFalse(set(_modelos_propios(self.env)) - cubiertos, 'Modelos propios sin prueba de seguridad multicompania: %s' % sorted(set(_modelos_propios(self.env)) - cubiertos))

    # ── no ve y no lee ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_no_ve_ni_lee_lo_de_la_otra_compania_y_si_lo_de_la_suya(self):
        for modelo, atributo in self._propios():
            for rol, usuarios in self._roles():
                for propia, ajena in (('a', 'b'), ('b', 'a')):
                    usuario = usuarios[propia]
                    mio, ajeno = getattr(self.d[propia], atributo), getattr(self.d[ajena], atributo)
                    Modelo = self._como(modelo, usuario)
                    etiqueta = '%s / %s / %s' % (modelo, rol, usuario.login)
                    if not Modelo.has_access('read'):
                        with self.assertRaises(AccessError, msg=etiqueta):
                            Modelo.search([('id', '=', ajeno.id)])                      # sin permiso de acceso: tampoco ve
                        continue
                    self.assertEqual(Modelo.search([('id', '=', mio.id)]), mio, 'Control positivo: ve lo de su compania. ' + etiqueta)
                    self.assertFalse(Modelo.search([('id', '=', ajeno.id)]), 'No ve lo de la otra compania. ' + etiqueta)
                    self.assertFalse(Modelo.search([]).filtered(lambda r: r.id == ajeno.id), etiqueta)
                    with self.assertRaises(AccessError, msg='No lee lo de la otra compania. ' + etiqueta):
                        Modelo.browse(ajeno.id).read(['id'])

    def test_no_escribe_ni_borra_lo_de_la_otra_compania(self):
        for modelo, atributo in self._propios():
            for rol, usuarios in self._roles():
                for propia, ajena in (('a', 'b'), ('b', 'a')):
                    usuario = usuarios[propia]
                    mio, ajeno = getattr(self.d[propia], atributo), getattr(self.d[ajena], atributo)
                    Modelo = self._como(modelo, usuario)
                    etiqueta = '%s / %s / %s' % (modelo, rol, usuario.login)
                    for operacion in ('write', 'unlink'):
                        self.assertFalse(Modelo.browse(ajeno.id).has_access(operacion), 'No %s lo de la otra compania. %s' % (operacion, etiqueta))
                        if Modelo.has_access(operacion):
                            self.assertTrue(Modelo.browse(mio.id).has_access(operacion), 'Control positivo: %s lo de su compania. %s' % (operacion, etiqueta))

    def test_no_crea_en_la_otra_compania_y_si_en_la_suya(self):
        """Un registro por modelo con valores validos; ``ajeno`` apunta a la compania/empleado de B y debe fallar con AccessError para A (y al reves)."""
        for propia, ajena in (('a', 'b'), ('b', 'a')):
            usuario = self.admin[propia]
            suyo, otro = self.d[propia], self.d[ajena]

            def valores(sembrado, periodo):
                return {
                    'l10n.co.retefuente.uvt': {'year': str(2040 + periodo.month), 'company_id': sembrado.compania.id, 'procedure': '1'},      # un año distinto por intento: la llave unica (año, compañia) no debe tapar la regla
                    'l10n.co.employee.descanso': {'employee_id': sembrado.empleado.id, 'dia_semana': '1', 'fecha_firma': date(2027, 1, 1)},
                    'l10n.co.employee.pacto': {'employee_id': sembrado.empleado.id, 'salary_rule_id': self.regla.id, 'fecha_firma': date(2027, 1, 1)},
                    'l10n.co.ibc.mensual': {'company_id': sembrado.compania.id, 'employee_id': sembrado.empleado.id, 'period': periodo},
                    'l10n.co.pila.planilla': {'company_id': sembrado.compania.id, 'period': periodo, 'tipo_planilla': 'E', 'operador_code': 'X'},
                    'l10n.co.ne.documento': {'company_id': sembrado.compania.id, 'employee_id': sembrado.empleado.id, 'period': periodo}}
            for modelo, vals in valores(otro, date(2026, 4, 1)).items():
                with self.assertRaises(AccessError, msg='%s: %s no crea en %s' % (modelo, usuario.login, otro.compania.name)):
                    self._como(modelo, usuario).create(vals)
            for modelo, vals in valores(suyo, date(2026, 5, 1)).items():
                creado = self._como(modelo, usuario).create(vals)
                self.assertTrue(creado, 'Control positivo: %s crea en su compania (%s)' % (usuario.login, modelo))

    # ── retencion compartida (G1) ───────────────────────────────────────────────────────────────────────────────────────────
    def test_uvt_la_fila_compartida_la_leen_todos_y_solo_el_sistema_la_escribe_crea_y_borra(self):
        compartida = self.uvt_compartida
        for propia in CLAVES:
            admin = self.admin[propia]
            Uvt = self._como('l10n.co.retefuente.uvt', admin)
            self.assertIn(compartida, Uvt.search([]), 'Todos leen la compartida')
            self.assertEqual(Uvt.browse(compartida.id).read(['year'])[0]['year'], '2032')
            for operacion, accion in (('write', lambda: Uvt.browse(compartida.id).write({'notes': 'cambio'})), ('unlink', lambda: Uvt.browse(compartida.id).unlink()),
                                      ('create', lambda: Uvt.create({'year': '2033', 'company_id': False, 'procedure': '1'}))):
                with self.assertRaises(AccessError, msg='El administrador de nomina de %s no hace %s sobre la compartida' % (propia, operacion)) as exc:
                    accion()
                self.assertIn('administrador del sistema', str(exc.exception), 'El mensaje dice quien puede editarla')
            propia_fila = getattr(self.d[propia], 'uvt')
            propia_fila.with_user(admin).with_context(allowed_company_ids=admin.company_ids.ids).write({'notes': 'la edita su compania'})
            self.assertEqual(propia_fila.notes, 'la edita su compania', 'Control positivo: edita la de su compania')
        with self.assertRaises(AccessError):                                          # la propia de A no la edita B
            self.d['a'].uvt.with_user(self.admin['b']).with_context(allowed_company_ids=self.b.ids).write({'notes': 'ajena'})
        sistema = self._como('l10n.co.retefuente.uvt', self.sistema, self.a)
        sistema.browse(compartida.id).write({'notes': 'la edita el sistema'})
        self.assertEqual(compartida.notes, 'la edita el sistema')
        creada = sistema.create({'year': '2034', 'company_id': False, 'procedure': '1'})
        self.assertTrue(creada)
        creada.with_user(self.sistema).with_context(allowed_company_ids=self.a.ids).unlink()
        self.assertFalse(creada.exists())

    def test_uvt_mover_una_fila_propia_a_compartida_tambien_exige_al_sistema(self):
        with self.assertRaises(AccessError) as exc:
            self.d['a'].uvt.with_user(self.admin['a']).with_context(allowed_company_ids=self.a.ids).write({'company_id': False})
        self.assertIn('administrador del sistema', str(exc.exception))

    # ── PIN del software (G3) ───────────────────────────────────────────────────────────────────────────────────────────────
    def test_el_pin_lo_lee_el_administrador_de_nomina_y_no_el_oficial_ni_sale_en_vistas_ni_chatter(self):
        modo = self.d['a'].modo
        Oficial = self._como('l10n.co.ne.operation_mode', self.oficial['a'])
        Admin = self._como('l10n.co.ne.operation_mode', self.admin['a'])
        self.assertEqual(Oficial.browse(modo.id).read(['software_id'])[0]['software_id'], 'SOFT-a', 'El oficial sigue leyendo el resto del modo de operacion')
        with self.assertRaises(AccessError):
            Oficial.browse(modo.id).read(['software_pin'])
        self.assertNotIn('software_pin', Oficial.fields_get())
        self.assertEqual(Admin.browse(modo.id).read(['software_pin'])[0]['software_pin'], 'PIN-a', 'El administrador de nomina si lo lee')
        self.assertIn('software_pin', Admin.fields_get())
        for tipo in ('form', 'list'):
            self.assertNotIn('software_pin', Oficial.get_view(view_type=tipo)['arch'], 'La vista %s del oficial no lo muestra' % tipo)
            self.assertIn('software_pin', Admin.get_view(view_type=tipo)['arch'], 'La vista %s del administrador si' % tipo)
        self.assertNotIn('message_ids', self.env['l10n.co.ne.operation_mode']._fields, 'Sin chatter ni tracking: el PIN no queda en el historial')
        self.assertEqual(Oficial.browse(modo.id)._ne_pin_del_software(), 'PIN-a', 'El sistema lo sigue leyendo para el CUNE y el codigo de seguridad aunque genere un oficial')

    def test_el_oficial_calcula_el_cune_con_el_pin_sin_error_de_acceso_y_un_rpc_suyo_no_devuelve_el_pin(self):
        """Condicion del TL (C4): ``_ne_pin_del_software`` es privado (``odoo/service/model.py:29-45``, ``get_public_method``: un metodo con «_» no se llama por RPC) y lee con ``sudo`` solo para el CUNE y
        el codigo de seguridad. El oficial genera el CUNE del documento (``_ne_calcular_cune``) sin ``AccessError`` y con el mismo resultado que el sistema; el CUNE cambia con el PIN (se usa de verdad);
        y por RPC ``read``/``search_read`` del oficial sobre el modo de operacion NO devuelven el PIN."""
        d, oficial = self.d['a'], self.oficial['a']
        datos = {'informacion_general': {'FechaGen': '2026-04-01', 'HoraGen': '10:00:00-05:00'},
                 'totales': {'DevengadosTotal': '1000000.00', 'DeduccionesTotal': '80000.00', 'ComprobanteTotal': '920000.00'}}
        d.documento.consecutive = 'NE1000'
        como_oficial = d.documento.with_user(oficial).with_context(allowed_company_ids=self.a.ids)
        cune = como_oficial._ne_calcular_cune(datos)                                       # con el PIN leido directo daria AccessError
        self.assertTrue(cune)
        self.assertEqual(cune, d.documento._ne_calcular_cune(datos), 'El oficial obtiene el mismo CUNE que el sistema')
        d.modo.software_pin = 'OTRO-PIN'
        self.assertNotEqual(como_oficial._ne_calcular_cune(datos), cune, 'El PIN entra al CUNE')
        d.modo.software_pin = 'PIN-a'
        Modo = self._como('l10n.co.ne.operation_mode', oficial)
        self.assertNotIn('software_pin', Modo.browse(d.modo.id).read()[0], 'read sin campos no devuelve el PIN')
        self.assertNotIn('software_pin', Modo.search_read([('id', '=', d.modo.id)])[0], 'search_read sin campos no devuelve el PIN')
        with self.assertRaises(AccessError):
            Modo.search_read([('id', '=', d.modo.id)], ['software_id', 'software_pin'])
        with self.assertRaises(AccessError):
            get_public_method(Modo.browse(d.modo.id), '_ne_pin_del_software')
        self.assertTrue(get_public_method(Modo.browse(d.modo.id), 'read'), 'Control positivo: read si es publico')

    # ── pacto y dia de descanso con la visibilidad del recibo (G4) ─────────────────────────────────────────────────────────
    def test_el_oficial_solo_ve_pactos_y_descansos_de_los_empleados_que_ve_en_el_recibo_y_el_administrador_todos_los_de_su_compania(self):
        jefe = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Jefe Seguridad', 'company_id': self.a.id, 'user_id': self.admin['a'].id, 'l10n_co_ne_payment_method': '10'})
        departamento = self.env['hr.department'].create({'name': 'Departamento Seguridad', 'company_id': self.a.id, 'manager_id': jefe.id})
        con_departamento = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': 'Empleado Con Departamento', 'company_id': self.a.id, 'department_id': departamento.id, 'l10n_co_ne_payment_method': '10'})
        pacto = self.env['l10n.co.employee.pacto'].create({'employee_id': con_departamento.id, 'salary_rule_id': self.regla.id, 'fecha_firma': date(2026, 1, 1)})
        descanso = self.env['l10n.co.employee.descanso'].create({'employee_id': con_departamento.id, 'dia_semana': '0', 'fecha_firma': date(2026, 1, 1)})
        for modelo, restringido, libre in (('l10n.co.employee.pacto', pacto, self.d['a'].pacto), ('l10n.co.employee.descanso', descanso, self.d['a'].descanso)):
            Oficial, Admin = self._como(modelo, self.oficial['a']), self._como(modelo, self.admin['a'])
            self.assertIn(libre, Oficial.search([]), '%s: el oficial ve el de un empleado sin departamento (lo ve en el recibo)' % modelo)
            self.assertNotIn(restringido, Oficial.search([]), '%s: el oficial no ve el de un empleado de un departamento que no gerencia' % modelo)
            self.assertIn(restringido, Admin.search([]), '%s: el administrador de nomina ve todos los de su compania' % modelo)
            self.assertIn(libre, Admin.search([]))
            self.assertFalse(self._como(modelo, self.admin['b']).search([('id', 'in', (restringido | libre).ids)]), '%s: el de la otra compania no ve ninguno' % modelo)

    def test_los_adjuntos_siguen_la_regla_del_registro_de_su_compania(self):
        """B3 (doc 59): el documento firmado del pacto y el XML/respuesta del documento mensual de B no los ve el usuario de A; el de B si."""
        Adjunto = self.env['ir.attachment']
        casos = (('l10n.co.employee.pacto', self.d['b'].pacto), ('l10n.co.ne.documento', self.d['b'].documento), ('l10n.co.ne.documento.intento', self.d['b'].intento))
        for modelo, registro in casos:
            adjunto = Adjunto.create({'name': 'Prueba %s.xml' % modelo, 'raw': b'<x/>', 'res_model': modelo, 'res_id': registro.id})
            self.assertFalse(Adjunto.with_user(self.admin['a']).with_context(allowed_company_ids=self.a.ids).search([('id', '=', adjunto.id)]), '%s: el adjunto de B no lo ve A' % modelo)
            self.assertTrue(Adjunto.with_user(self.admin['b']).with_context(allowed_company_ids=self.b.ids).search([('id', '=', adjunto.id)]), '%s: el adjunto de B lo ve B' % modelo)

    # ── vista SQL de los consecutivos ───────────────────────────────────────────────────────────────────────────────────────
    def test_la_vista_de_consecutivos_solo_trae_los_de_la_compania_del_usuario(self):
        for propia, ajena in (('a', 'b'), ('b', 'a')):
            for rol, usuarios in self._roles():
                Vista = self._como('l10n.co.ne.consecutivo', usuarios[propia])
                visibles = Vista.search([('numero', 'like', CODIGO_NE)])
                self.assertEqual(set(visibles.mapped('company_id').ids), {self.compania[propia].id}, '%s de %s ve solo lo de su compania' % (rol, propia))
                self.assertEqual(len(visibles), 2, 'Control positivo: el manifiesto y el intento de su compania (%s)' % rol)
                self.assertFalse(visibles.filtered(lambda r: r.company_id == self.compania[ajena]))
                self.assertEqual(Vista.search_count([('company_id', '=', self.compania[ajena].id)]), 0)

    # ── asistentes ──────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_el_usuario_de_b_no_procesa_recibos_de_a_en_el_asistente_de_envio(self):
        """``hr.payslip.send`` (CRUD a ``user``, patron nativo): el asistente corre con los permisos del usuario y los recibos de A los filtra la regla del recibo."""
        for rol, usuarios in self._roles():
            usuario = usuarios['b']
            with self.assertRaises(AccessError, msg=rol):
                asistente = self._como('hr.payslip.send', usuario).create({'payslip_ids': [(6, 0, self.d['a'].recibo.ids)]})
                asistente.action_send_and_print()

    def test_un_asistente_de_pila_con_la_compania_de_b_creado_por_a_no_genera_nada_de_b(self):
        Planilla = self.env['l10n.co.pila.planilla']
        antes = Planilla.search_count([('company_id', '=', self.b.id)])
        try:
            asistente = self._como('l10n.co.hr.pila.wizard.v2', self.admin['a']).create({'year': '2026', 'month': '03', 'tipo_planilla': 'E', 'company_id': self.b.id})
            asistente.action_generate_pila()
        except UserError:
            pass                                                                    # sin recibos visibles de B el asistente se detiene: es lo esperado
        self.assertEqual(Planilla.search_count([('company_id', '=', self.b.id)]), antes, 'No se creo ninguna planilla de B')

    # ── solo Ausencias ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_el_oficial_de_ausencias_no_vincula_una_prorroga_con_una_ausencia_de_otra_compania(self):
        usuario = self.ausencias['a']
        propia, ajena = self.d['a'].ausencia, self.d['b'].ausencia
        Ausencia = self._como('hr.leave', usuario)
        self.assertIn(propia, Ausencia.search([]), 'Control positivo: ve las ausencias de su compania')
        self.assertFalse(Ausencia.search([('id', '=', ajena.id)]), 'No ve las de la otra compania')
        self.assertEqual(Ausencia._ne_interrupcion_maxima_prorroga(date(2026, 3, 1)), 30, 'Sin grupo de nomina sigue leyendo el parametro (sudo de H-F1-01)')
        with self.assertRaises(UserError):
            propia.with_user(usuario).with_context(allowed_company_ids=self.a.ids).l10n_co_ne_prorroga_de_id = ajena
        self.assertFalse(propia.l10n_co_ne_prorroga_de_id, 'La prorroga con una ausencia de otra compania no queda guardada')

    # ── check_company (G5) ──────────────────────────────────────────────────────────────────────────────────────────────────
    def test_no_se_mezclan_companias_en_intercambios_manifiestos_documentos_y_terceros(self):
        a, b = self.d['a'], self.d['b']
        with self.assertRaises(UserError):                                          # recibo de B en un intercambio de A
            self.env['l10n.co.ne.exchange'].sudo().create({
                'company_id': self.a.id, 'operation': 'send_sync', 'endpoint': 'https://dian.example/x', 'payslip_ids': [(6, 0, b.recibo.ids)]})
        with self.assertRaises(UserError):                                          # intercambio de B en un documento de A
            a.documento.write({'exchange_ids': [(4, b.intercambio.id)]})
        with self.assertRaises(UserError):                                          # recibo de B en un documento de A
            a.documento.write({'payslip_ids': [(4, b.recibo.id)]})
        contacto_b = self.env['res.partner'].create({'name': 'Tercero de B', 'company_id': self.b.id})
        with self.assertRaises(UserError):                                          # tercero de B en la distribucion de un recibo de A
            a.tercero.write({'partner_id': contacto_b.id})
        contacto_a = self.env['res.partner'].create({'name': 'Tercero de A', 'company_id': self.a.id})
        a.tercero.write({'partner_id': contacto_a.id})                              # control positivo
        self.assertEqual(a.tercero.partner_id, contacto_a)

    # ── sudo de res.partner (G6) ────────────────────────────────────────────────────────────────────────────────────────────
    def test_editar_el_nit_de_un_contacto_sincroniza_solo_los_empleados_de_las_companias_del_usuario(self):
        compartido = self.env['res.partner'].create({'name': 'Contacto compartido'})
        a, b = self.d['a'].empleado, self.d['b'].empleado
        (a | b).write({'work_contact_id': compartido.id})
        compartido.with_user(self.contador['a']).with_context(allowed_company_ids=self.a.ids).write({'vat': '700123'})
        self.assertEqual(a.identification_id, '700123', 'Control positivo: el empleado de su compania se sincroniza (el contador no tiene permisos de empleados: sudo)')
        self.assertNotEqual(b.identification_id, '700123', 'El empleado de la otra compania NO se toca')
        compartido.with_user(self.contador['b']).with_context(allowed_company_ids=self.b.ids).write({'vat': '700456'})
        self.assertEqual(b.identification_id, '700456')
        self.assertEqual(a.identification_id, '700123')

    # ── multicompania ───────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_el_usuario_multicompania_ve_solo_las_activas(self):
        for modelo, atributo in (('l10n.co.ibc.mensual', 'ibc'), ('l10n.co.pila.planilla', 'planilla'), ('l10n.co.employee.pacto', 'pacto')):
            registros = getattr(self.d['a'], atributo) | getattr(self.d['b'], atributo)
            self.assertEqual(self._como(modelo, self.multi, self.a).search([('id', 'in', registros.ids)]), getattr(self.d['a'], atributo))
            self.assertEqual(self._como(modelo, self.multi, self.b).search([('id', 'in', registros.ids)]), getattr(self.d['b'], atributo))
            self.assertEqual(self._como(modelo, self.multi, self.a, self.b).search([('id', 'in', registros.ids)]), registros)
