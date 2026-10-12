# -*- coding: utf-8 -*-
"""Localización nómina (.99, pedido de David): bloque "Localización nómina"
en Ajustes > Nómina, calcado del bloque "Fiscal Localization" de
Accounting (chart_template/reload_template). Cubre:

- La Selección de paquete incluye Colombia.
- El compute "hay nóminas confirmadas" (gating de readonly/Recargar).
- El método de recarga ("Opción A", aprobada por David/Tech Lead):
  odoo.tools.convert.convert_file sobre SOLO estructuras/reglas/tipos de
  novedad -- recrea lo que falte, nunca toca hr.rule.parameter.
- El override del dominio de hr_payroll.open_payroll_modules (Colombia
  aparece en "Choose a Payroll Localization").
- El arch guardado de la vista: el bloque nuevo existe y el setting
  nativo "Payroll Rules" queda oculto cuando hay paquete elegido.
"""

from datetime import date

from lxml import etree

from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval


class TestSeleccionPaquete(TransactionCase):
    def test_seleccion_incluye_colombia(self):
        opciones = dict(self.env['res.company']._selection_l10n_co_ne_payroll_package())
        self.assertIn('l10n_co_nomina_electronica', opciones)


class TestHasPayrollEntries(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía dedicada y descartable (ver AUD-DIAN-34 en test_dian_matching.py).
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Has Payroll Entries',
        })
        cls.company.partner_id.country_id = cls.env.ref('base.co').id
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Has Payroll Entries',
            'country_id': cls.env.ref('base.co').id,
        })
        cls.struct = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def test_sin_nominas_confirmadas_no_tiene_entradas(self):
        settings = self.env['res.config.settings'].create({'company_id': self.company.id})
        self.assertFalse(settings.l10n_co_ne_has_payroll_entries)

    def test_con_nomina_confirmada_si_tiene_entradas(self):
        employee = self.env['hr.employee'].create({
            'name': 'EmpleadoPaquete',
            'identification_id': '888999000',
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato EmpleadoPaquete',
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 1800000.0,
            'date_start': date(2024, 1, 1),
            'state': 'open',
        })
        self.env['hr.payslip'].create({
            'name': 'Nómina EmpleadoPaquete',
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.struct.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
            'state': 'done',
        })
        settings = self.env['res.config.settings'].create({'company_id': self.company.id})
        self.assertTrue(settings.l10n_co_ne_has_payroll_entries)


class TestReloadPayrollPackage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Recargar Paquete',
        })
        cls.company.partner_id.country_id = cls.env.ref('base.co').id

    def test_recargar_recrea_tipo_de_novedad_eliminado(self):
        """Si un tipo de novedad protegido (noupdate="1", ej. embargo
        civil) se borra -- por ejemplo por error de un usuario --
        Recargar debe recrearlo, usando el mismo mecanismo real de un
        -u (odoo.tools.convert.convert_file), no una copia reescrita."""
        xmlid = 'l10n_co_nomina_electronica.input_l10n_co_embargo_civil'
        tipo = self.env.ref(xmlid)
        tipo.unlink()
        self.assertFalse(self.env.ref(xmlid, raise_if_not_found=False))

        self.company._l10n_co_ne_reload_payroll_package()
        self.env.invalidate_all()

        recreado = self.env.ref(xmlid, raise_if_not_found=False)
        self.assertTrue(recreado, 'Recargar debió recrear el tipo de novedad eliminado.')
        self.assertEqual(recreado.code, 'L10N_CO_EMBARGO_CIVIL')

    def test_recargar_no_toca_hr_rule_parameter(self):
        """El alcance de Recargar EXCLUYE deliberadamente
        data/l10n_co_rule_parameters_data.xml -- un valor de parámetro
        (ej. el SMMLV 2026) no debe cambiar aunque alguien lo edite y
        luego presione Recargar. La exclusión es por ALCANCE (el archivo
        nunca se procesa), no por comparar valores."""
        parametro = self.env.ref('l10n_co_nomina_electronica.rule_parameter_smmlv_2026')
        parametro.sudo().parameter_value = 999999999.0

        self.company._l10n_co_ne_reload_payroll_package()
        self.env.invalidate_all()

        self.assertEqual(
            parametro.parameter_value, 999999999.0,
            'Recargar no debe tocar hr.rule.parameter.value.',
        )

    def test_action_reload_delega_en_la_compania(self):
        settings = self.env['res.config.settings'].create({'company_id': self.company.id})
        xmlid = 'l10n_co_nomina_electronica.input_l10n_co_embargo_cooperativa'
        self.env.ref(xmlid).unlink()
        result = settings.action_reload_payroll_package()
        self.env.invalidate_all()
        self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False))
        self.assertEqual(result.get('tag'), 'reload')


class TestOpenPayrollModulesDomain(TransactionCase):
    def test_colombia_incluida_en_choose_payroll_localization(self):
        action = self.env.ref('hr_payroll.open_payroll_modules')
        domain = safe_eval(action.domain or '[]')
        modulos = self.env['ir.module.module'].search(domain)
        self.assertIn('l10n_co_nomina_electronica', modulos.mapped('name'))


class TestArchVistaLocalizacion(TransactionCase):
    def _arch(self, xmlid):
        return etree.fromstring(self.env.ref(xmlid).arch_db.encode('utf-8'))

    def test_bloque_localizacion_nomina_existe(self):
        arch = self._arch('l10n_co_nomina_electronica.res_config_settings_view_form')
        bloque = arch.find(".//block[@id='l10n_co_ne_settings_localizacion']")
        self.assertIsNotNone(bloque, 'Falta el bloque "Localización nómina".')
        campo = bloque.find(".//field[@name='l10n_co_ne_payroll_package']")
        self.assertIsNotNone(campo)
        boton = bloque.find(".//button[@name='action_reload_payroll_package']")
        self.assertIsNotNone(boton)
        self.assertNotIn('fa fa-', etree.tostring(bloque, encoding='unicode'))

    def test_setting_nativo_payroll_rules_queda_oculto_con_paquete(self):
        arch = self._arch('l10n_co_nomina_electronica.res_config_settings_view_form')
        xpaths = arch.xpath(
            "//xpath[@expr=\"//block[@id='hr_payroll_settings']/setting[@string='Payroll Rules']\"]")
        self.assertEqual(len(xpaths), 1)
        atributo = xpaths[0].find(".//attribute[@name='invisible']")
        self.assertIsNotNone(atributo)
        self.assertIn('l10n_co_ne_payroll_package', atributo.text)
        self.assertIn('module_l10n_fr_hr_payroll', atributo.text)
