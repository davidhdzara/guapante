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

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
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
        # Los 3 banners de estado NE (sent/uncertain/rejected) se identifican por su modificador `l10n_co_ne_state`; los avisos (que no bloquean) por el campo de su `invisible`: periodicidad (E-2, recibo de
        # 7 dias en un contrato no semanal), afiliacion incompleta (H-F1-06), IBC del mes anterior (H-F1-11/H-F1-08) tipo de trabajador del aprendiz (H-F1-09) y dia de descanso (H-F1-07).
        de_estado = [b for b in banners if 'l10n_co_ne_state' in (b.get('invisible') or '')]
        avisos = {campo: [b for b in banners if campo in (b.get('invisible') or '')]
                  for campo in ('l10n_co_ne_aviso_periodicidad', 'l10n_co_ne_aviso_afiliacion', 'l10n_co_ne_aviso_ibc_anterior', 'l10n_co_ne_aviso_tipo_trabajador', 'l10n_co_ne_aviso_descanso')}
        self.assertEqual(len(de_estado), 3, 'Se esperaban los 3 banners de estado NE (sent/uncertain/rejected).')
        for campo, encontrados in avisos.items():
            self.assertEqual(len(encontrados), 1, 'Se esperaba un solo aviso con el campo %s.' % campo)
        self.assertEqual(len(banners), len(de_estado) + sum(len(b) for b in avisos.values()), 'Hay un banner sin clasificar.')
        for encontrados in avisos.values():
            for banner in encontrados:      # los avisos nuevos tambien son 100 % nativos: sin estilos ni colores propios
                self.assertIsNone(banner.get('style'))
                self.assertFalse(banner.xpath(".//*[@style]"))
                self.assertNotIn('text-muted', etree.tostring(banner, encoding='unicode'))
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

    # ── Frente 4 (doc 57 §14): reporte UGPP y oficio, solo estilo nativo ─────────────────────────────────
    def _sin_estilo_propio(self, xmlid):
        arch = self._arch(xmlid)
        for nodo in arch.iter():
            if not isinstance(nodo.tag, str):
                continue
            self.assertIsNone(nodo.get('style'), '%s: style inline en <%s>' % (xmlid, nodo.tag))
            clases = nodo.get('class') or ''
            self.assertNotRegex(clases, r'\bfa(\s|-)', '%s: ícono fa en <%s>' % (xmlid, nodo.tag))
            for atributo in nodo.attrib:
                self.assertFalse(atributo.startswith('decoration-') or atributo in ('color', 'bgcolor'),
                                 '%s: color propio (%s) en <%s>' % (xmlid, atributo, nodo.tag))
        return arch

    def test_reporte_ugpp_sin_estilos_propios_ni_pestanas_nuevas(self):
        arch = self._sin_estilo_propio('l10n_co_nomina_electronica.view_l10n_co_nomina_ugpp_form')
        self.assertFalse(arch.xpath('//notebook | //page'), 'El reporte UGPP no lleva pestañas nuevas.')

    def test_oficio_ugpp_sin_estilos_propios(self):
        self._sin_estilo_propio('l10n_co_nomina_electronica.report_ugpp_oficio')

    def test_ajustes_y_asistente_de_envio_sin_estilos_propios(self):
        self._sin_estilo_propio('l10n_co_nomina_electronica.res_config_settings_view_form')
        self._sin_estilo_propio('l10n_co_nomina_electronica.hr_payslip_send_view_form')

    def test_la_colilla_y_sus_bloques_comunes_sin_estilos_propios(self):
        for xmlid in ('report_payslip_ne', 'ne_comprobante_encabezado', 'ne_colilla_tabla'):
            self._sin_estilo_propio('l10n_co_nomina_electronica.' + xmlid)

    def test_el_comprobante_agrupado_sin_estilos_propios(self):
        self._sin_estilo_propio('l10n_co_nomina_electronica.report_comprobante_pago')

    def test_la_representacion_grafica_sin_estilos_propios(self):
        for xmlid in ('report_representacion_grafica', 'layout_representacion_grafica'):
            self._sin_estilo_propio('l10n_co_nomina_electronica.' + xmlid)

