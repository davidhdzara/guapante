# -*- coding: utf-8 -*-
"""PDS Operación — rediseño F2 (shell oscuro, KPIs, tablero de 4 columnas).
Verificación de código (no hay navegador en la suite): CSS acotado a la clase
raíz, scroll independiente por columna, tarjeta intacta y KPIs presentes."""
import re

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.misc import file_path

BASE = 'ist_preparation_day_picking/static/src/'


def _read(rel):
    with open(file_path(BASE + rel), encoding='utf-8') as fh:
        return fh.read()


def _top_level_selectors(css):
    """Selectores de los bloques de primer nivel (ignora comentarios y el
    contenido de los bloques)."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    selectors, depth, buf = [], 0, ''
    for ch in css:
        if ch == '{':
            if depth == 0:
                selectors.append(buf.strip())
            depth += 1
            buf = ''
        elif ch == '}':
            depth -= 1
            buf = ''
        elif depth == 0:
            buf += ch
    return selectors


@tagged('post_install', '-at_install')
class TestPreparationPdsShell(TransactionCase):

    def test_scss_is_scoped_to_the_root_class(self):
        selectors = _top_level_selectors(
            _read('scss/preparation_pds_operacion.scss'))
        allowed = {'.o_guapante_pds', '@keyframes gp-pulse'}
        self.assertEqual(set(selectors), allowed,
                         'CSS fuera de .o_guapante_pds afectaría otras pantallas')

    def test_scss_has_independent_column_scroll(self):
        css = _read('scss/preparation_pds_operacion.scss')
        cards = re.search(r'\.gp-cards\s*\{([^}]*)\}', css).group(1)
        self.assertIn('overflow-y: auto', cards)
        board = re.search(r'\.gp-board\s*\{([^}]*)\}', css).group(1)
        self.assertIn('min-height: 0', board)
        self.assertIn('repeat(4', board)
        root = re.search(r'\.o_guapante_pds\s*\{(.*?)\n    /\*', css, flags=re.S).group(1)
        self.assertIn('overflow: hidden', root, 'la página no scrollea')

    def test_scss_does_not_load_external_resources(self):
        css = _read('scss/preparation_pds_operacion.scss')
        self.assertNotIn('@import', css)
        self.assertNotIn('googleapis', css)
        self.assertNotIn('url(', css)

    def test_template_has_shell_kpis_and_four_columns(self):
        xml = _read('js/preparation_pds_operacion.xml')
        for needle in (
                'o_guapante_pds', 'gp-header', 'gp-kpis', 'gp-board',
                'Progreso general', 'Cajas vs. Pickings', 'Productos distintos',
                'cotizaciones sin confirmar', 'detenidos ahora',
                'statusOrder'):
            self.assertIn(needle, xml, needle)

    def test_card_keeps_its_information(self):
        """David: «las tarjetas están perfectas»: ninguna pieza de información
        de la tarjeta desaparece."""
        xml = _read('js/preparation_pds_operacion.xml')
        card = xml[xml.index('o_mrp_display_record card'):xml.index('</ul>')]
        for needle in (
                'card.product_name', 'card.done_line_count',
                'card.total_line_count', 'card.zero_line_count',
                'elapsedLabel(card)', 'isStoppedAlert(card, status)',
                'card.no_weigh_yet', 'card.weighed_kg', 'card.expected_kg',
                'card.waiting_customers', 'card.operator_name',
                'card.stop_reason_label', 'fa-clock-o', 'fa-user'):
            self.assertIn(needle, card, needle)

    def test_js_reads_new_payload_blocks(self):
        js = _read('js/preparation_pds_operacion.js')
        for needle in ('data.kpis', 'data.ranking', 'data.rhythm',
                       'data.session_state'):
            self.assertIn(needle, js, needle)
