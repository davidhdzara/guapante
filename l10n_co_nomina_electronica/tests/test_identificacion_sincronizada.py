# -*- coding: utf-8 -*-
"""UX-02 (2026-10-11, decisión de David), parte (a) -- número: "que el contacto
y el empleado queden sincronizados en el número". identification_id
(hr.employee, nativo, ~12 usos reales: NumeroDocumento del XML, UGPP, PILA, la
clave de idempotencia del wizard de certificación, pruebas) y
work_contact_id.vat (res.partner, nativo de Contactos) deben reflejarse el uno
al otro en ambas direcciones, sin propagar nunca un valor vacío/False (eso
borraría el dato real del otro lado) y sin entrar en un ciclo de escrituras.

Hallazgo que motiva el diseño (verificado contra hr/models/hr_employee.py::
create()): para un empleado SIN usuario vinculado (el caso típico),
work_contact_id NO existe todavía cuando super().create() procesa
identification_id -- hr nativo lo crea DESPUÉS, en _create_work_contacts().
Por eso la propagación en create() se hace sobre el resultado ya completo de
super().create(), nunca antes.
"""

from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestIdentificacionSincronizada(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía dedicada y descartable (ver AUD-DIAN-34 en test_dian_matching.py).
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Identificación Sincronizada',
        })

    def _make_employee(self, name, identification_id=None, vals=None):
        create_vals = {
            'name': name,
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        }
        if identification_id is not None:
            create_vals['identification_id'] = identification_id
        if vals:
            create_vals.update(vals)
        return self.env['hr.employee'].create(create_vals)

    def test_crear_empleado_sin_usuario_propaga_numero_al_contacto(self):
        """Caso típico: empleado sin user_id. work_contact_id no existe todavía
        cuando super().create() procesa identification_id (hr nativo lo crea
        DESPUÉS) -- el create() de este módulo debe propagar sobre el resultado
        ya completo."""
        employee = self._make_employee('CreaSinUsuario', identification_id='111222333')
        self.assertFalse(employee.user_id)
        self.assertTrue(employee.work_contact_id)
        self.assertEqual(employee.work_contact_id.vat, '111222333')

    def test_editar_numero_en_empleado_propaga_al_contacto(self):
        employee = self._make_employee('EditaEnEmpleado', identification_id='100')
        self.assertEqual(employee.work_contact_id.vat, '100')
        employee.identification_id = '200'
        self.assertEqual(employee.work_contact_id.vat, '200')

    def test_editar_vat_en_contactos_propaga_al_empleado(self):
        employee = self._make_employee('EditaEnContactos', identification_id='300')
        self.assertEqual(employee.identification_id, '300')
        employee.work_contact_id.vat = '400'
        self.assertEqual(employee.identification_id, '400')

    def test_no_propaga_numero_vacio_del_empleado_al_contacto(self):
        """Si identification_id se borra (False), el vat del contacto NO debe
        borrarse con él -- guard explícito pedido por Tech Lead."""
        employee = self._make_employee('NoPropagaVacioEmpleado', identification_id='500')
        self.assertEqual(employee.work_contact_id.vat, '500')
        employee.identification_id = False
        self.assertEqual(employee.work_contact_id.vat, '500')

    def test_no_propaga_vat_vacio_del_contacto_al_empleado(self):
        """Simétrico: si alguien borra el vat del contacto, identification_id
        del empleado (del que depende NumeroDocumento del XML) no desaparece."""
        employee = self._make_employee('NoPropagaVacioContacto', identification_id='600')
        self.assertEqual(employee.identification_id, '600')
        employee.work_contact_id.vat = False
        self.assertEqual(employee.identification_id, '600')

    def test_sin_bucle_infinito_entre_employee_y_partner(self):
        """El guard de igualdad (en hr_employee.py y en res_partner.py) debe
        bastar para que una sola edición del número dispare EXACTAMENTE una
        escritura del lado contrario, nunca un ciclo. Se cuenta cuántas veces
        se llama a write() de res.partner durante una sola edición del empleado."""
        employee = self._make_employee('SinBucle', identification_id='700')
        partner_model = type(employee.work_contact_id)
        original_write = partner_model.write
        llamadas = {'n': 0}

        def write_contador(self, vals):
            llamadas['n'] += 1
            return original_write(self, vals)

        with patch.object(partner_model, 'write', write_contador):
            employee.identification_id = '800'

        self.assertEqual(employee.work_contact_id.vat, '800')
        self.assertEqual(
            llamadas['n'], 1,
            'Debe escribirse el partner UNA sola vez (la propagación); más de '
            'una indica un ciclo entre employee.write() y partner.write().',
        )

    def _desincronizar_por_sql(self, employee, vat_contacto):
        """.93 (hallazgo de Tech Lead en staging): esta prueba simulaba el
        estado de 2 empleados reales (Andres Felipe Zapata, Diana Cristina Gil
        Posada) usando sus números REALES como valores de prueba -- al correr
        contra una copia de la base real de Guapante (ver AUD-DIAN-34 en
        test_dian_matching.py), esos valores colisionaban con datos de verdad
        en la base y la prueba dependía de ellos en vez de ser autosuficiente.
        Ahora usa valores puramente sintéticos (prefijo 'SINT', imposible de
        confundir con una cédula o NIT real) -- el estado que importa (número
        del empleado distinto del vat del contacto, de antes de que este
        sincronismo existiera) se reproduce igual por UPDATE SQL directo, sin
        depender de qué empleados reales existan en la base. La migración
        (migrations/18.0.3.0.89/post-sync_identification_number.py) tampoco
        toca este estado a propósito -- solo completa vat=False, nunca
        sobrescribe un valor ya distinto -- y el UPDATE SQL directo es la
        única forma de dejar esa discrepancia en la prueba sin pasar por
        partner.write() (que la resincronizaría de inmediato)."""
        self.env.cr.execute(
            'UPDATE res_partner SET vat = %s WHERE id = %s',
            (vat_contacto, employee.work_contact_id.id),
        )
        employee.work_contact_id.invalidate_recordset(['vat'])

    def test_conflicto_preexistente_la_edicion_desde_el_empleado_gana(self):
        """Pregunta de Tech Lead sobre los 2 empleados con discrepancia real en
        staging: ¿qué pasa cuando alguien edita un lado? El diseño no "corrige"
        solo el conflicto previo ni levanta ningún error por él -- simplemente,
        la PRÓXIMA edición (de cualquier lado) es la que gana y el otro lado la
        sigue, igual que en cualquier otra edición. Aquí la edición llega desde
        el empleado. Valores sintéticos, no dependen de ningún empleado real
        (ver _desincronizar_por_sql)."""
        employee = self._make_employee('ConflictoDesdeEmpleado', identification_id='SINT-EMP-001')
        self._desincronizar_por_sql(employee, 'SINT-CONTACTO-002')
        self.assertEqual(employee.identification_id, 'SINT-EMP-001')
        self.assertEqual(employee.work_contact_id.vat, 'SINT-CONTACTO-002')

        employee.identification_id = 'SINT-EMP-001-EDITADO'
        self.assertEqual(employee.work_contact_id.vat, 'SINT-EMP-001-EDITADO')

    def test_conflicto_preexistente_la_edicion_desde_contactos_gana(self):
        """Mismo caso, lado contrario: si la edición que resuelve el conflicto
        llega desde Contactos (vat), es identification_id del empleado el que
        se actualiza para seguirla. Valores sintéticos, no dependen de ningún
        empleado real (ver _desincronizar_por_sql)."""
        employee = self._make_employee('ConflictoDesdeContactos', identification_id='SINT-EMP-003')
        self._desincronizar_por_sql(employee, 'SINT-CONTACTO-004')
        self.assertEqual(employee.identification_id, 'SINT-EMP-003')
        self.assertEqual(employee.work_contact_id.vat, 'SINT-CONTACTO-004')

        employee.work_contact_id.vat = 'SINT-CONTACTO-004-EDITADO'
        self.assertEqual(employee.identification_id, 'SINT-CONTACTO-004-EDITADO')

    def test_tipo_nit_con_numero_invalido_falla_validacion_nativa(self):
        """Tipo RUT (NIT): l10n_co.check_vat() SÍ valida el dígito de
        verificación (vía base_vat/stdnum) cuando el tipo de identificación es
        RUT -- a diferencia de Cédula, que no se valida.

        .93 (hallazgo de Tech Lead en staging: "ValidationError not raised").
        Verificado contra el código fuente real de base_vat (18.0,
        ResPartner._run_vat_test()): la validación de Colombia (stdnum
        co.nit) solo se alcanza por la rama "default_country"
        (partner.commercial_partner_id.country_id) -- exige country_id='CO'
        en el contacto, que esta prueba nunca ponía. Sin country_id,
        _run_vat_test() intenta primero leer los 2 primeros caracteres del
        valor como prefijo de país (_split_vat); el valor anterior,
        'NIT-CLARAMENTE-INVALIDO', empieza por 'NI' -- código real de
        Nicaragua, un país sin validador de VAT registrado -- y ese camino,
        al no tener cómo refutarlo, lo da por válido por defecto
        (simple_vat_check: "No VAT validation available, default to check
        that the country code exists"). La prueba nunca llegaba a stdnum.

        Con country_id='CO' puesto (como lo tendría cualquier contacto real
        de un empleado colombiano) y un valor puramente numérico (sin un
        prefijo de 1-2 letras que pueda confundirse con un código de país
        real), la validación SÍ llega a stdnum.co.nit.is_valid() -- confirmado
        localmente con python-stdnum: is_valid('123456789') devuelve False --
        y esta vez sí levanta ValidationError."""
        employee = self._make_employee('TipoNitInvalido')
        employee.work_contact_id.country_id = self.env.ref('base.co').id
        employee.l10n_co_ne_identification_type_id = self.env.ref('l10n_co.rut').id
        with self.assertRaises(ValidationError):
            employee.identification_id = '123456789'

    def test_tipo_sin_codigo_dian_levanta_usererror_en_xml(self):
        """foreign_id_card ("Cédula Extranjera", tipo genérico de l10n_latam_base
        sin código DIAN) -- el número sincronizado correctamente no evita el
        UserError de _ne_tipo_documento(), que depende del TIPO, no del número."""
        employee = self._make_employee('TipoSinCodigoDian', identification_id='900')
        employee.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_latam_base.it_fid').id
        structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Sin Codigo Dian',
            'country_id': self.env.ref('base.co').id,
        })
        structure = self.env['hr.payroll.structure'].create({
            'name': 'Nómina Prueba Sin Codigo Dian',
            'type_id': structure_type.id,
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato TipoSinCodigoDian',
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': structure_type.id,
            'wage': 1800000.0,
            'date_start': date(2024, 1, 1),
            'state': 'open',
        })
        payslip = self.env['hr.payslip'].create({
            'name': 'Nómina TipoSinCodigoDian',
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': structure.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        with self.assertRaises(UserError) as exc:
            payslip._ne_tipo_documento()
        self.assertIn('TipoSinCodigoDian', str(exc.exception))
