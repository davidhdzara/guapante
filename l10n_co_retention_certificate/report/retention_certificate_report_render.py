# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class RetentionCertificateReport(models.AbstractModel):
    """Construye los datos para la plantilla QWeb del Certificado de
    Retenciones, a partir de lo que esté desplegado en el reporte
    'l10n_co.retention.certificate.report.handler' en el momento de
    imprimir.

    Sigue el mismo patrón que el certificado nativo
    (l10n_co_reports/report/certification_report.py: recorre
    report._get_lines() ya filtradas por lo desplegado y arma un dict por
    tercero), pero reconstruye TRES niveles en vez de dos, usando
    line['level'] (1=tercero, 2=tipo de retención, 3=concepto) en lugar
    de solo el modelo de la línea, porque el nativo no distingue más de
    un nivel de detalle bajo el tercero.
    """

    # Nombre corto a propósito: 'report.' + nombre del módulo
    # (l10n_co_retention_certificate, ya 30 caracteres) + este último
    # segmento se convierte en el nombre de tabla interno de Postgres
    # (los puntos se cambian por guion bajo). Con un segmento largo aquí
    # se supera el límite de 63 caracteres de Postgres para nombres de
    # tabla — ya ocurrió una vez con 'report_retention_certificate' y
    # tumbó la instalación del módulo. 'document' deja margen de sobra.
    _name = 'report.l10n_co_retention_certificate.document'
    _description = 'Certificado de Retenciones - Render'

    def _get_report_values(self, docids, data=None):
        options = dict(self._context.get('options') or {})
        report = self.env['account.report'].browse(options['report_id'])

        # El PDF SIEMPRE debe mostrar el detalle completo (tercero -> tipo
        # -> concepto) de los terceros seleccionados, sin depender del
        # estado de plegado/desplegado que haya quedado en la pantalla del
        # reporte. Confiar en ese estado resultó frágil: si el usuario
        # desplegaba el tercero pero no cada tipo de retención dentro de
        # él, el PDF salía con el subtotal de la sección pero SIN las
        # líneas de concepto debajo (bug real reportado por el usuario el
        # 2026-07-30 con la sección de Contribución Parafiscal). La
        # selección de QUÉ terceros entran al certificado se sigue
        # resolviendo con el filtro de tercero del reporte (filter_partner,
        # sin tocar); lo que se elimina es la posibilidad de excluir una
        # retención puntual plegándola, que nunca fue confiable.
        options['unfold_all'] = True
        lines = report._filter_out_folded_children(report._get_lines(options))

        docs = self._build_docs(report, options, lines)
        docs = [doc for doc in docs if doc['sections']]
        if not docs:
            raise UserError(_(
                'Debe desplegar al menos un tercero con retenciones en el '
                'reporte antes de generar el certificado.'
            ))

        date_from_str = options.get('date', {}).get('date_from')
        date_to_str = options.get('date', {}).get('date_to')
        date_from = (
            date_from_str
            or (data or {}).get('wizard_values', {}).get('declaration_date')
        )
        current_date = fields.Datetime.to_datetime(date_from) or datetime.now()

        return {
            'docs': docs,
            'options': (data or {}).get('wizard_values', {}),
            # Objetos date reales (no strings), para usarlos con
            # t-options widget='date' en la plantilla — t-field no
            # aplica aquí porque no son campos de un recordset.
            'date_from': fields.Date.from_string(date_from_str) if date_from_str else False,
            'date_to': fields.Date.from_string(date_to_str) if date_to_str else False,
            'company': self.env.company,
            'current_year': self.env.company.compute_fiscalyear_dates(current_date)['date_from'].year,
        }

    def _build_docs(self, report, options, lines):
        """Reconstruye la jerarquía Tercero -> Sección (tipo) -> Concepto
        a partir de la lista plana de líneas ya filtrada por lo
        desplegado, usando level para distinguir cada nivel (ver
        models/retention_certificate_report.py: 1=tercero, 2=tipo,
        3=concepto).
        """
        docs = []
        current_partner_doc = None
        current_section = None

        for line in lines:
            level = line.get('level')

            if level == 1:
                model, model_id = report._get_model_info_from_id(line['id'])
                if model != 'res.partner':
                    # La línea de Total General u otra línea de nivel 1
                    # sin modelo propio: no es un certificado de tercero.
                    continue
                current_partner_doc = {
                    'partner_id': self.env['res.partner'].browse(model_id),
                    'sections': [],
                    **self._columns_to_dict(options, line),
                }
                current_section = None
                docs.append(current_partner_doc)

            elif level == 2 and current_partner_doc is not None:
                current_section = {
                    'name': line.get('name'),
                    'type_code': self._get_retention_type_code(report, line),
                    'concepts': [],
                    **self._columns_to_dict(options, line),
                }
                current_partner_doc['sections'].append(current_section)

            elif level == 3 and current_section is not None:
                current_section['concepts'].append(
                    self._columns_to_dict(options, line)
                )

        return docs

    def _columns_to_dict(self, options, line):
        result = {}
        for i, column in enumerate(line['columns']):
            column_data = options['columns'][i % len(options['columns'])]
            result[column_data['expression_label']] = column.get('name')
        return result

    def _get_retention_type_code(self, report, line):
        """Extrae el código de tipo de retención ('retefuente', 'reteiva',
        'reteica', 'parafiscal') codificado en el markup de una línea de
        Nivel 2. Ver _get_type_line en models/retention_certificate_report.py.
        """
        markup = report._get_markup(line['id'])
        if markup and markup.startswith('type_'):
            return markup.split('type_', 1)[1]
        return False
