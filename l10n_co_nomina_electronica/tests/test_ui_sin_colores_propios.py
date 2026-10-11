# -*- coding: utf-8 -*-
"""UX-03 (2026-10-11, hallazgo visual de David): el mensaje final de
Habilitación DIAN salía en verde/rojo (decoration-danger/success) y su
resumen en gris (class="text-muted"); los 3 banners de estado de
hr.payslip tenían íconos <i class="fa ..."/>. CLAUDE.md ya establece
"Visual solo nativo: sin íconos, colores ni CSS propios" (Principios de
diseño y UX/UI, regla 5).

La barra de progreso (widget="progressbar") y los widget="badge" con
decoration-* sobre campos de estado (l10n_co_ne_state, state de UGPP) SÍ
son el patrón nativo de Odoo para mostrar un estado -- no se tocan, y esta
prueba no los exige vacíos.

Se parsea el arch_db real guardado de las 2 vistas corregidas (no una
copia rehecha para la prueba) y se verifica, elemento por elemento, que
los campos/divs señalados por Tech Lead ya no tienen esos atributos."""

from lxml import etree

from odoo.tests.common import TransactionCase


class TestUiSinColoresPropios(TransactionCase):

    def _arch(self, xmlid):
        return etree.fromstring(self.env.ref(xmlid).arch_db.encode('utf-8'))

    def test_habilitacion_resumen_sin_text_muted(self):
        arch = self._arch(
            'l10n_co_nomina_electronica.res_config_settings_view_form')
        campo = arch.find(".//field[@name='l10n_co_ne_hab_summary']")
        self.assertIsNotNone(campo, 'No se encontró el campo l10n_co_ne_hab_summary.')
        self.assertNotIn('text-muted', campo.get('class') or '')

    def test_habilitacion_mensaje_sin_decoration(self):
        arch = self._arch(
            'l10n_co_nomina_electronica.res_config_settings_view_form')
        campo = arch.find(".//field[@name='l10n_co_ne_hab_message']")
        self.assertIsNotNone(campo, 'No se encontró el campo l10n_co_ne_hab_message.')
        self.assertIsNone(campo.get('decoration-danger'))
        self.assertIsNone(campo.get('decoration-success'))

    def test_banners_payslip_sin_iconos_fa(self):
        arch = self._arch('l10n_co_nomina_electronica.view_payslip_form_ne')
        banners = arch.xpath("//div[contains(@class, 'alert')]")
        self.assertEqual(
            len(banners), 3,
            'Se esperaban los 3 banners de estado NE (sent/uncertain/rejected).',
        )
        for banner in banners:
            iconos_fa = [
                i for i in banner.findall('.//i')
                if (i.get('class') or '').startswith('fa ')
            ]
            self.assertFalse(
                iconos_fa,
                'Banner todavía tiene un ícono fa fa-: %s'
                % etree.tostring(banner, encoding='unicode'),
            )

    def test_estados_badge_nativo_no_se_toca(self):
        """Confirma que el widget="badge" con decoration-* sobre el campo de
        estado SIGUE existiendo -- es el patrón nativo de Odoo, no un color
        propio, y esta corrección no debía tocarlo."""
        arch = self._arch('l10n_co_nomina_electronica.view_payslip_form_ne')
        campo = arch.find(".//field[@name='l10n_co_ne_state'][@widget='badge']")
        self.assertIsNotNone(campo)
        self.assertEqual(campo.get('decoration-success'), "l10n_co_ne_state == 'accepted'")
        self.assertEqual(campo.get('decoration-danger'), "l10n_co_ne_state == 'rejected'")
