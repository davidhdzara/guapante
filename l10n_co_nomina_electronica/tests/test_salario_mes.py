# -*- coding: utf-8 -*-
"""E-9 (H-QA-026): en compañías colombianas el Salario del contrato se rotula SIEMPRE «/ mes».

Trampa de captura que reprodujo QA: con «Programar pago» = Quincenal la pantalla rotulaba el Salario «/ quincena» (rótulo nativo
de ``hr_payroll``), pero ``CO_BASICO = wage / 30`` trata el campo SIEMPRE como salario MENSUAL: cargar $6.000.000 pensando que es
por quincena pagaba $3.000.000 por quincena. El rótulo nativo es un ``<div name="wage_period_label">/ month</div>`` que
``hr_payroll`` vuelve condicional (``schedule_pay != 'monthly'``) y acompaña de 8 divs hermanos («/ year», «/ quincena»…), cada uno
visible solo para su valor de ``schedule_pay``.

Un ``arch`` de vista no se ve con el navegador en una prueba de servidor: se evalúan las condiciones ``invisible`` del ``arch``
EFECTIVO (con la herencia ya aplicada) para cada valor de ``schedule_pay`` y de país, que es lo mismo que evalúa el cliente. NO
ejecutadas (no hay Odoo local) cuando se escribieron.
"""

from lxml import etree

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

NOMBRE_ROTULO_NATIVO = 'wage_period_label'
NOMBRE_ROTULO_CO = 'l10n_co_ne_wage_period_label'


@tagged('post_install', '-at_install')
class TestSalarioMes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.arch = etree.fromstring(cls.env['hr.contract'].get_view(view_type='form')['arch'].encode())
        campo = cls.env['hr.contract']._fields['schedule_pay']
        cls.valores_schedule_pay = [valor for valor, _etiqueta in campo.get_description(cls.env)['selection']]

    def _rotulos(self):
        """Los divs que rotulan el período del salario: el nativo, los 8 que agrega ``hr_payroll`` (todos con una condición
        sobre ``schedule_pay``) y el colombiano."""
        nativo = self.arch.xpath("//div[@name='%s']" % NOMBRE_ROTULO_NATIVO)
        self.assertEqual(len(nativo), 1, 'El rótulo nativo del salario ya no está en la vista del contrato.')
        padre = nativo[0].getparent()
        return [div for div in padre.xpath('./div')
                if div.get('name') in (NOMBRE_ROTULO_NATIVO, NOMBRE_ROTULO_CO)
                or 'schedule_pay' in (div.get('invisible') or '')]

    def _visibles(self, schedule_pay, country_code):
        """Textos de los rótulos que el cliente mostraría para este contrato."""
        contexto = {'schedule_pay': schedule_pay, 'country_code': country_code}
        return [
            ''.join(div.itertext()).strip() for div in self._rotulos()
            if not (div.get('invisible') and safe_eval(div.get('invisible'), contexto))]

    def test_la_vista_del_contrato_carga_con_el_rotulo_colombiano(self):
        rotulo = self.arch.xpath("//div[@name='%s']" % NOMBRE_ROTULO_CO)
        self.assertEqual(len(rotulo), 1)
        self.assertEqual(''.join(rotulo[0].itertext()).strip(), '/ mes')

    def test_hay_un_rotulo_nativo_por_cada_valor_de_programar_pago(self):
        """Control de la premisa: la vista nativa tiene un rótulo para cada valor de ``schedule_pay`` (si Odoo agrega un valor
        sin rótulo, o lo quita, esta prueba lo dice antes que el usuario)."""
        for valor in self.valores_schedule_pay:
            with self.subTest(schedule_pay=valor):
                self.assertEqual(len(self._visibles(valor, 'MX')), 1)

    def test_colombia_muestra_siempre_solo_mes_con_cualquier_programar_pago(self):
        self.assertIn('semi-monthly', self.valores_schedule_pay)
        for valor in self.valores_schedule_pay:
            with self.subTest(schedule_pay=valor):
                self.assertEqual(self._visibles(valor, 'CO'), ['/ mes'])

    def test_colombia_con_quincenal_no_muestra_quincena(self):
        visibles = self._visibles('semi-monthly', 'CO')
        self.assertEqual(visibles, ['/ mes'])
        self.assertFalse([texto for texto in visibles if 'quincena' in texto.lower()])

    def test_otra_compania_conserva_el_comportamiento_nativo(self):
        """Fuera de Colombia queda exactamente lo nativo: un solo rótulo, el de su ``schedule_pay``, y nunca «/ mes»."""
        for pais in ('MX', 'EC', False, ''):
            for valor in self.valores_schedule_pay:
                with self.subTest(pais=pais, schedule_pay=valor):
                    visibles = self._visibles(valor, pais)
                    self.assertEqual(len(visibles), 1)
                    self.assertNotEqual(visibles[0], '/ mes')

    def test_el_rotulo_nativo_mensual_sigue_para_otra_compania(self):
        self.assertEqual(self._visibles('monthly', 'MX'), ['/ month'])

    def test_no_se_toca_programar_pago(self):
        """``schedule_pay`` (aviso de duración, factor de costos y la periodicidad de la retención lo leen) no se oculta ni se
        vuelve de solo lectura por país POR ESTE MÓDULO: ni nuestras vistas lo mencionan como destino de un xpath o de un campo, ni
        la vista efectiva lo condiciona a Colombia. Se verifica lo NUESTRO y no el atributo completo: la vista nativa ya trae su
        propia condición (``country_code == 'MX'`` en ``invisible``, regresión bu del 16-nov-2026), que no es de este módulo."""
        for xmlid in ('view_contract_form_ne', 'view_contract_form_ne_salario_mes'):
            with self.subTest(vista=xmlid):
                propia = etree.fromstring(self.env.ref('l10n_co_nomina_electronica.%s' % xmlid).arch_db.encode())
                self.assertFalse(propia.xpath("//field[@name='schedule_pay']"), 'La vista propia declara schedule_pay.')
                for xpath in propia.xpath('//xpath'):
                    self.assertNotRegex(
                        xpath.get('expr'), r"""field\[@name\s*=\s*['"]schedule_pay['"]\]""",
                        'Un xpath propio apunta al campo schedule_pay.')
        campos = self.arch.xpath("//field[@name='schedule_pay']")
        self.assertTrue(campos, 'Programar pago ya no está en la vista del contrato.')
        # Con la localización de México instalada su vista (l10n_mx_hr_payroll_localisation/views/hr_contract_views.xml, herencia de
        # hr_payroll.hr_contract_form_inherit) pone EXACTAMENTE ``invisible="country_code == 'MX'"`` al campo: es el único
        # atributo que debe traer. Sin ella no trae ninguno. Readonly y required nunca los toca nadie.
        mexico = self.env['ir.module.module'].search_count([
            ('name', '=', 'l10n_mx_hr_payroll_localisation'), ('state', '=', 'installed')])
        for campo in campos:
            if mexico:
                self.assertEqual(campo.get('invisible'), "country_code == 'MX'")
            else:
                self.assertFalse(campo.get('invisible'))
            for atributo in ('readonly', 'required'):
                self.assertFalse(campo.get(atributo), 'schedule_pay trae %s: %s.' % (atributo, campo.get(atributo)))

    def test_el_salario_conserva_su_campo_y_su_contenedor(self):
        """El campo ``wage`` sigue donde estaba, dentro del contenedor del rótulo (solo cambian los rótulos de al lado)."""
        campo = self.arch.xpath("//div[@name='wage']/field[@name='wage']")
        self.assertEqual(len(campo), 1)
        self.assertNotIn('country_code', campo[0].get('invisible') or '')
