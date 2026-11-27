# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F4-08 (doc 99, aprobado por el TL el 23-nov): los campos 9 y 10 del registro tipo 2 de la PILA (departamento y municipio de la
UBICACION LABORAL, Anexo Tecnico 2 de la Res. 2388/2016) salian EN BLANCO para todos los empleados: el asistente leia ``address_home_id``,
que no existe en Odoo 18 (``hasattr`` daba ``False``). Ahora salen de la «Direccion de Trabajo» del empleado (``address_id``: la misma
fuente de los ``LugarTrabajo*`` del XML): el departamento con ``dian_utils.get_department_code`` y el municipio como el codigo DANE de la
ciudad menos el prefijo de su departamento (``dian_utils.get_pila_municipality_code``). Sin dato, un error que nombra al empleado.

- ``TestUbicacionPilaPura`` (``BaseCase``, sin base de datos): la funcion pura, con valores a mano.
- ``TestPilaUbicacionLaboral``: el asistente (``_build_cotizante_data``) y el metodo del recibo; los valores esperados salen de los
  registros de la fixture, no de literales de codigos. Las ubicaciones se toman de los datos reales de ``l10n_co`` (departamento y ciudad
  con codigo DANE consistente), no se inventan.

Premisas por confirmar en la N1/N2 (nada de esto se ejecuto en Odoo al escribirlo): ``hr.employee.private_*`` existe (lo verifico el TL
en ``ir_model_fields``); el asistente construye el registro con la fixture de ``test_pila_horas_laboradas``; la Direccion de Trabajo por
defecto del empleado es la del contacto de la compañia (como en ``test_aprendiz_regimen._lugar_de_trabajo_completo``)."""

from odoo.addons.l10n_co_nomina_electronica.services import dian_utils
from odoo.exceptions import UserError
from odoo.tests.common import BaseCase, tagged

from . import test_pension_no_exigida as pension


def ubicaciones_de_prueba(env, cantidad=2):
    """``cantidad`` pares ``(departamento, ciudad)`` de Colombia, de departamentos DISTINTOS, cuyo codigo DANE de ciudad es coherente con el
    de su departamento (datos de ``l10n_co``). Falla con un mensaje claro si la base no los trae: no se inventan codigos."""
    pais = env.ref('base.co')
    pares, departamentos = [], set()
    for ciudad in env['res.city'].search([('country_id', '=', pais.id)], order='id'):
        if not ciudad.state_id or not getattr(ciudad, 'l10n_co_edi_code', None):
            continue
        departamento = dian_utils.get_department_code(ciudad.state_id)
        try:
            dian_utils.get_pila_municipality_code(departamento, ciudad.l10n_co_edi_code)
        except ValueError:
            continue
        if departamento in departamentos:
            continue
        departamentos.add(departamento)
        pares.append((ciudad.state_id, ciudad))
        if len(pares) == cantidad:
            return pares
    raise AssertionError('La base no trae %s ciudades de Colombia de departamentos distintos con codigo DANE coherente (datos de l10n_co).' % cantidad)


def direccion_de_trabajo(env, nombre, departamento=None, ciudad=None):
    """Contacto que sirve de Direccion de Trabajo: pais Colombia y, si se dan, departamento y ciudad."""
    valores = {'name': nombre, 'country_id': env.ref('base.co').id, 'street': 'Calle de prueba # 1-1'}
    if departamento:
        valores['state_id'] = departamento.id
    if ciudad:
        valores['city_id'] = ciudad.id
    return env['res.partner'].create(valores)


@tagged('post_install', '-at_install')
class TestUbicacionPilaPura(BaseCase):
    """La funcion pura: del codigo DANE de la ciudad y el del departamento sale el municipio (campo 10)."""

    def test_el_municipio_es_el_codigo_dane_menos_el_prefijo_del_departamento(self):
        self.assertEqual(dian_utils.get_pila_municipality_code('11', '11001'), '001')
        self.assertEqual(dian_utils.get_pila_municipality_code('11', 11001), '001')

    def test_el_codigo_entero_sin_el_cero_a_la_izquierda_se_completa(self):
        """``l10n_co_edi_code`` es un entero: Itagui 5360 es ``05360`` de Antioquia (``05``)."""
        self.assertEqual(dian_utils.get_pila_municipality_code('05', 5360), '360')

    def test_el_largo_del_municipio_es_el_del_codigo_dane_menos_el_del_departamento(self):
        resto = dian_utils.get_pila_municipality_code('76', '76001')
        self.assertEqual(len(resto), dian_utils.DANE_MUNICIPIO_LONGITUD - len('76'))

    def test_sin_codigo_de_ciudad_es_error_y_no_un_blanco(self):
        for vacio in (None, False, 0, '', '   '):
            with self.assertRaises(ValueError, msg=repr(vacio)) as contexto:
                dian_utils.get_pila_municipality_code('11', vacio)
            self.assertEqual(contexto.exception.args[0], 'ciudad_sin_codigo', repr(vacio))

    def test_una_ciudad_de_otro_departamento_es_error(self):
        with self.assertRaises(ValueError) as contexto:
            dian_utils.get_pila_municipality_code('05', '11001')
        self.assertEqual(contexto.exception.args[0], 'ciudad_otro_departamento')

    def test_un_departamento_vacio_o_no_numerico_es_error(self):
        for departamento in ('', None, 'ANT', '1A'):
            with self.assertRaises(ValueError, msg=repr(departamento)) as contexto:
                dian_utils.get_pila_municipality_code(departamento, '05001')
            self.assertEqual(contexto.exception.args[0], 'departamento_sin_codigo', repr(departamento))

    def test_un_codigo_de_ciudad_que_no_es_dane_es_error(self):
        for invalido in ('ABCDE', '1100100', '11-001'):
            with self.assertRaises(ValueError, msg=invalido) as contexto:
                dian_utils.get_pila_municipality_code('11', invalido)
            self.assertEqual(contexto.exception.args[0], 'ciudad_codigo_invalido', invalido)


@tagged('post_install', '-at_install')
class TestPilaUbicacionLaboral(pension.TestPensionNoExigida):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.depto_a, cls.ciudad_a), (cls.depto_b, cls.ciudad_b) = ubicaciones_de_prueba(cls.env)
        # La Direccion de Trabajo por defecto de un empleado nuevo es la del contacto de su compañia (antes de crear a los empleados).
        cls.company.partner_id.write({'country_id': cls.env.ref('base.co').id, 'state_id': cls.depto_a.id, 'city_id': cls.ciudad_a.id,
                                      'street': 'Calle de prueba # 1-1'})

    # ── fixture ──────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _listo(self, nombre):
        """Empleado y recibo hecho, listos para construir el registro tipo 2 (mismo patron de ``test_pila_horas_laboradas``)."""
        empleado, recibo = self._calculado(nombre, eps=self.eps, afp=self.afp, ccf=self.ccf)
        empleado.write({'l10n_co_primer_nombre': 'Ubicacion', 'l10n_co_primer_apellido': 'Laboral'})
        recibo.contract_id.write({'l10n_co_pila_centro_trabajo': '1'})
        recibo.state = 'done'
        return empleado, recibo

    def _datos(self, recibo):
        return self.env['l10n.co.hr.pila.wizard.v2'].new({'company_id': self.company.id})._build_cotizante_data(recibo, 1)

    def _resto(self, ciudad, departamento):
        """Municipio esperado, calculado a mano desde el registro de la ciudad: su codigo DANE completo menos el prefijo del departamento."""
        return str(ciudad.l10n_co_edi_code).zfill(dian_utils.DANE_MUNICIPIO_LONGITUD)[len(departamento):]

    # ── 2. el asistente trae la Direccion de Trabajo ─────────────────────────────────────────────────────────────────────
    def test_el_asistente_trae_el_departamento_y_el_municipio_de_la_direccion_de_trabajo(self):
        empleado, recibo = self._listo('Ubic Trabajo')
        self.assertEqual(empleado.address_id, self.company.partner_id, 'Premisa: la Direccion de Trabajo por defecto es la de la compañia')
        datos = self._datos(recibo)
        departamento = dian_utils.get_department_code(self.depto_a)
        self.assertTrue(datos['codigo_departamento'], 'El campo 9 ya no sale en blanco')
        self.assertTrue(datos['codigo_municipio'], 'El campo 10 ya no sale en blanco')
        self.assertEqual(datos['codigo_departamento'], departamento)
        self.assertEqual(datos['codigo_municipio'], self._resto(self.ciudad_a, departamento))
        self.assertEqual((datos['codigo_departamento'], datos['codigo_municipio']), recibo._ne_ubicacion_laboral_pila())

    def test_la_direccion_de_trabajo_propia_del_empleado_gana_a_la_de_la_compania(self):
        empleado, recibo = self._listo('Ubic Propia')
        empleado.address_id = direccion_de_trabajo(self.env, 'Oficina de otro departamento', self.depto_b, self.ciudad_b)
        datos = self._datos(recibo)
        departamento = dian_utils.get_department_code(self.depto_b)
        self.assertEqual(datos['codigo_departamento'], departamento)
        self.assertEqual(datos['codigo_municipio'], self._resto(self.ciudad_b, departamento))

    # ── 3. no es el domicilio ────────────────────────────────────────────────────────────────────────────────────────────
    def test_no_es_el_domicilio_del_empleado(self):
        """El defecto leia el domicilio (``address_home_id``). El archivo sigue la Direccion de Trabajo aunque el empleado tenga otro domicilio privado."""
        empleado, recibo = self._listo('Ubic Domicilio')
        empleado.write({'private_country_id': self.env.ref('base.co').id, 'private_state_id': self.depto_b.id, 'private_city': self.ciudad_b.name,
                        'private_street': 'Carrera del domicilio # 2-2'})
        datos = self._datos(recibo)
        departamento = dian_utils.get_department_code(self.depto_a)
        self.assertEqual(datos['codigo_departamento'], departamento)
        self.assertEqual(datos['codigo_municipio'], self._resto(self.ciudad_a, departamento))
        self.assertNotEqual(datos['codigo_departamento'], dian_utils.get_department_code(self.depto_b))

    # ── 4. no mas blancos silenciosos ────────────────────────────────────────────────────────────────────────────────────
    def test_una_direccion_de_trabajo_incompleta_o_incoherente_es_un_error_que_nombra_al_empleado(self):
        ciudad_sin_codigo = self.env['res.city'].create({
            'name': 'Ciudad sin codigo DANE', 'state_id': self.depto_a.id, 'country_id': self.env.ref('base.co').id,
            'zipcode': dian_utils.get_department_code(self.depto_a) + '001'})        # un codigo postal que EMPIEZA por el departamento: no debe usarse
        ciudad_codigo_no_valido = self.env['res.city'].create({
            'name': 'Ciudad con codigo DANE no valido', 'state_id': self.depto_a.id, 'country_id': self.env.ref('base.co').id,
            'l10n_co_edi_code': 1100100})        # 7 digitos: un codigo DANE de ciudad tiene 5 (ejecuta el cuarto mensaje con **datos, el unico que ademas lleva ``longitud=``)
        casos = (
            ('sin ciudad', direccion_de_trabajo(self.env, 'Sin ciudad', self.depto_a, None)),
            ('sin departamento', direccion_de_trabajo(self.env, 'Sin departamento', None, self.ciudad_a)),
            ('ciudad sin codigo DANE', direccion_de_trabajo(self.env, 'Ciudad sin codigo', self.depto_a, ciudad_sin_codigo)),
            ('ciudad de otro departamento', direccion_de_trabajo(self.env, 'Ciudad ajena', self.depto_a, self.ciudad_b)),
            ('codigo DANE no valido', direccion_de_trabajo(self.env, 'Codigo no valido', self.depto_a, ciudad_codigo_no_valido)),
        )
        for descripcion, direccion in casos:
            with self.subTest(descripcion):
                empleado, recibo = self._listo('Ubic %s' % descripcion)
                empleado.address_id = direccion
                with self.assertRaises(UserError, msg=descripcion) as contexto:
                    recibo._ne_ubicacion_laboral_pila()
                self.assertIn(empleado.name, str(contexto.exception), descripcion)
                with self.assertRaises(UserError, msg='%s: el asistente tampoco lo deja en blanco' % descripcion) as del_asistente:
                    self._datos(recibo)
                self.assertIn(empleado.name, str(del_asistente.exception), descripcion)

    def test_la_ciudad_sin_codigo_dane_nombra_la_ciudad_y_no_cae_al_codigo_postal(self):
        ciudad_sin_codigo = self.env['res.city'].create({
            'name': 'Ciudad Postal Falsa', 'state_id': self.depto_a.id, 'country_id': self.env.ref('base.co').id,
            'zipcode': dian_utils.get_department_code(self.depto_a) + '001'})
        empleado, recibo = self._listo('Ubic Postal')
        empleado.address_id = direccion_de_trabajo(self.env, 'Con postal', self.depto_a, ciudad_sin_codigo)
        with self.assertRaises(UserError) as contexto:
            recibo._ne_ubicacion_laboral_pila()
        self.assertIn('Ciudad Postal Falsa', str(contexto.exception))
        self.assertIn('DANE', str(contexto.exception))

    # ── 5. coherencia con el XML ─────────────────────────────────────────────────────────────────────────────────────────
    def test_el_departamento_de_pila_es_el_del_xml_de_nomina(self):
        empleado, recibo = self._listo('Ubic Xml')
        empleado.l10n_co_ne_identification_type_id = self.env.ref('l10n_co.national_citizen_id')          # _ne_tipo_documento() exige un tipo con equivalente DIAN
        departamento, _municipio = recibo._ne_ubicacion_laboral_pila()
        self.assertEqual(departamento, recibo._ne_trabajador()['LugarTrabajoDepartamentoEstado'])

    # ── 6. validacion temprana ───────────────────────────────────────────────────────────────────────────────────────────
    def test_el_asistente_nombra_al_empleado_sin_ciudad_al_validar_antes_de_generar(self):
        """El ciclo de ``action_validate`` agrega el faltante a la lista de errores (patron de la CCF); como ``_build_cotizante_data`` (que NO se
        envuelve en esta pieza, decision del TL, Q2) vuelve a lanzar el mismo error del primer empleado, el usuario lo ve como un error que
        nombra al empleado al validar, no al generar el archivo; igual que hoy con la CCF."""
        empleado, recibo = self._listo('Ubic Validar')
        empleado.address_id = direccion_de_trabajo(self.env, 'Sin ciudad al validar', self.depto_a, None)
        asistente = self.env['l10n.co.hr.pila.wizard.v2'].create({
            'company_id': self.company.id, 'year': str(recibo.date_to.year), 'month': '%02d' % recibo.date_to.month, 'tipo_planilla': 'E'})
        with self.assertRaises(UserError) as contexto:
            asistente.action_validate()
        self.assertIn(empleado.name, str(contexto.exception))
        self.assertIn('municipio', str(contexto.exception))

    # ── 7. colombiano en el exterior ─────────────────────────────────────────────────────────────────────────────────────
    def test_el_colombiano_en_el_exterior_lleva_los_dos_campos_en_blanco_aunque_tenga_direccion_de_trabajo(self):
        """Regla del anexo (campos 9 y 10: «de lo contrario se deberá dejar en blanco»). FUERA DE ALCANCE, a proposito: si ese cotizante aporta
        voluntariamente a una caja de compensacion, el anexo pide reportar el departamento y municipio de LA CAJA; el modulo no modela ese aporte
        (decision del TL, 23-nov, Q1). No es una omision."""
        empleado, recibo = self._listo('Ubic Exterior')
        empleado.l10n_co_pila_colombiano_exterior = True
        datos = self._datos(recibo)
        self.assertEqual(datos['colombiano_exterior'], 'X')
        self.assertEqual((datos['codigo_departamento'], datos['codigo_municipio']), ('', ''))
        self.assertEqual(recibo._ne_ubicacion_laboral_pila(), ('', ''))
        # y sin la «X», con la misma direccion, los campos SI salen
        empleado.l10n_co_pila_colombiano_exterior = False
        departamento, municipio = recibo._ne_ubicacion_laboral_pila()
        self.assertTrue(departamento and municipio)
