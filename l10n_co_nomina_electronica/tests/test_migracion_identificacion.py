# -*- coding: utf-8 -*-
"""UX-02 (.94, 2026-10-11, pedido de Tech Lead): prueba del script de
migración migrations/18.0.3.0.89/post-sync_identification_number.py --
específicamente el backfill del TIPO de identificación agregado en la .94
(hallazgo de Tech Lead en producción, solo lectura: 16 de 18 contactos de
Guapante tienen tipo VAT genérico, sin código DIAN).

La carpeta migrations/18.0.3.0.89/ no es un paquete Python importable de
forma normal (el nombre de la carpeta no es un identificador válido), así
que el script se carga con importlib.util desde su ruta real -- es la
función migrate() real del repo, no una copia reescrita para la prueba.
"""

import importlib.util
import os

from odoo.tests.common import TransactionCase


def _cargar_migracion():
    ruta = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'migrations', '18.0.3.0.89', 'post-sync_identification_number.py',
    )
    spec = importlib.util.spec_from_file_location(
        'l10n_co_nomina_electronica_migracion_89', ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class TestMigracionIdentificacion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migracion = _cargar_migracion()
        # Compañía dedicada y descartable (ver AUD-DIAN-34 en
        # test_dian_matching.py), colombiana -- el backfill del tipo solo
        # aplica a compañías colombianas.
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Migración Identificación',
        })
        cls.co_country = cls.env.ref('base.co')
        cls.company.partner_id.country_id = cls.co_country.id

    def _make_employee(self, name, identification_id, tipo_xmlid):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': identification_id,
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        })
        # Fuerza el tipo explícitamente DESPUÉS del create() -- simula tanto
        # un contacto viejo (de antes de .94, que habría quedado en VAT
        # genérico) como uno que RRHH ya corrigió a mano (ej. a NIT), sin
        # depender de cuál sea el default actual de _create_work_contacts().
        employee.l10n_co_ne_identification_type_id = self.env.ref(tipo_xmlid).id
        return employee

    def test_migracion_tipo_vat_generico_pasa_a_cedula(self):
        """Caso real citado por Tech Lead: 16 de 18 contactos de Guapante en
        VAT genérico -- la migración debe backfillear a Cédula de
        ciudadanía."""
        employee = self._make_employee(
            'MigracionVat', '111222333', 'l10n_latam_base.it_vat')
        self.migracion.migrate(self.env.cr, '18.0.3.0.89')
        employee.invalidate_recordset(['l10n_co_ne_identification_type_id'])
        self.assertEqual(
            employee.l10n_co_ne_identification_type_id,
            self.env.ref('l10n_co.national_citizen_id'),
        )

    def test_migracion_tipo_nit_no_se_toca(self):
        """Caso real citado por Tech Lead (Diana Cristina Gil Posada): tipo
        NIT ya corregido a mano por RRHH -- la migración nunca debe
        tocarlo, solo el caso VAT genérico."""
        employee = self._make_employee(
            'MigracionNit', '900123456-8', 'l10n_co.rut')
        self.migracion.migrate(self.env.cr, '18.0.3.0.89')
        employee.invalidate_recordset(['l10n_co_ne_identification_type_id'])
        self.assertEqual(
            employee.l10n_co_ne_identification_type_id,
            self.env.ref('l10n_co.rut'),
        )

    def test_migracion_tipo_cedula_existente_no_se_toca(self):
        """El 18vo contacto real (ya en Cédula) tampoco debe tocarse --
        confirma que el filtro es "vacío o VAT genérico", no "cualquier
        contacto colombiano"."""
        employee = self._make_employee(
            'MigracionCedula', '444555666', 'l10n_co.national_citizen_id')
        self.migracion.migrate(self.env.cr, '18.0.3.0.89')
        employee.invalidate_recordset(['l10n_co_ne_identification_type_id'])
        self.assertEqual(
            employee.l10n_co_ne_identification_type_id,
            self.env.ref('l10n_co.national_citizen_id'),
        )

    def test_migracion_rellena_numero_y_tipo_juntos(self):
        """El backfill del número (.89) y el del tipo (.94) conviven en el
        mismo script -- un contacto sin vat y con tipo VAT genérico debe
        salir con AMBOS corregidos en una sola corrida."""
        employee = self.env['hr.employee'].create({
            'name': 'MigracionNumeroYTipo',
            'identification_id': '777888999',
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        })
        employee.l10n_co_ne_identification_type_id = self.env.ref(
            'l10n_latam_base.it_vat').id
        # Vacía el vat por SQL directo para simular un contacto de ANTES de
        # que la sincronización del número existiera (ver _desincronizar_
        # por_sql en test_identificacion_sincronizada.py, mismo recurso).
        self.env.cr.execute(
            'UPDATE res_partner SET vat = NULL WHERE id = %s',
            (employee.work_contact_id.id,),
        )
        employee.work_contact_id.invalidate_recordset(['vat'])
        self.assertFalse(employee.work_contact_id.vat)

        self.migracion.migrate(self.env.cr, '18.0.3.0.89')
        employee.invalidate_recordset(['l10n_co_ne_identification_type_id'])
        employee.work_contact_id.invalidate_recordset(['vat'])
        self.assertEqual(employee.work_contact_id.vat, '777888999')
        self.assertEqual(
            employee.l10n_co_ne_identification_type_id,
            self.env.ref('l10n_co.national_citizen_id'),
        )
