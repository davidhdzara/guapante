# -*- coding: utf-8 -*-
"""Utilidad de pruebas (.296): el «Diario de salarios» de las estructuras para las pruebas con ``odoo.tests.Form``.

El recibo y la estructura de nómina (``hr_payroll_account``) llevan ``journal_id`` con ``required`` en la vista (``hr_payslip_views.xml:36`` y
``hr_payroll_structure_views.xml:9``) y ``Form`` exige un campo requerido al guardar (``odoo/tests/form.py:506``). En el recibo, ``journal_id`` es un
``related`` de ``struct_id.journal_id`` (``hr_payslip.py:16``) y en la estructura es ``company_dependent`` (``hr_payroll_structure.py:15-17``): se lee
con la compañía del ENTORNO. Hasta la .295 las pruebas lo tomaban de la base donde corrían (la copia de staging_dev solo lo trae en la estructura
general): en una base sin ese diario toda prueba con ``Form`` fallaba con «journal_id is a required field» (así falló una estructura sin diario, la de
bonificación, en la N1 de la .290). Ahora cada clase lo fija en su ``setUpClass`` (o en su prueba): un diario nuevo, de tipo general, de la compañía
del entorno, dentro de la transacción de la prueba (se revierte). Sin cambio de código del módulo."""


def fijar_diario_de_salarios(env, *estructuras):
    """Crea un diario general en la compañía del entorno y lo fija como «Diario de salarios» de las ``estructuras`` para esa compañía (la que lee
    ``Form``). Devuelve el diario."""
    diario = env['account.journal'].create({
        'name': 'Diario de salarios de prueba', 'code': 'TNE01', 'type': 'general', 'company_id': env.company.id})
    for estructura in estructuras:
        estructura.with_company(env.company).journal_id = diario
    return diario
