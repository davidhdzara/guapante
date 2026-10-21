# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Cálculo automático de Retención en la Fuente — Nómina Colombiana.

Implementa el Procedimiento 1 (Art. 383 del Estatuto Tributario) y el
Procedimiento 2 para el cálculo de la retención en la fuente sobre pagos
laborales.

El modelo ``l10n.co.retefuente.uvt`` almacena el valor de la UVT por año
fiscal y expone el método :meth:`compute_retefuente` que ejecuta la
depuración de la base gravable y aplica la tabla marginal vigente.

Referencia legal:
- Estatuto Tributario, Art. 383 — Tabla de retención en la fuente.
- Estatuto Tributario, Art. 387 — Deducciones permitidas (dependientes, etc.).
- Decreto 1070 de 2013, Art. 1 — Procedimiento 2.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════
# Tabla marginal Art. 383 ET
# Cada tupla: (límite_inferior_UVT, límite_superior_UVT, tarifa, UVT_fijas)
# ════════════════════════════════════════════════════════════════════════
MARGINAL_TABLE_ART383 = [
    (0, 95, 0.00, 0),
    (95, 150, 0.19, 0),
    (150, 360, 0.28, 10),
    (360, 640, 0.33, 69),
    (640, 945, 0.35, 162),
    (945, 2300, 0.37, 268),
    (2300, float('inf'), 0.39, 770),
]


class L10nCoRetefuenteUvt(models.Model):
    """Tabla de configuración y cálculo de Retención en la Fuente — Colombia.

    Almacena el valor de la UVT vigente por año fiscal y el procedimiento
    de retención aplicable.  Expone el método ``compute_retefuente()`` que
    realiza la depuración de la base gravable y aplica la tabla marginal
    del Art. 383 del Estatuto Tributario.
    """

    _name = 'l10n.co.retefuente.uvt'
    _description = 'Tabla de Retención en la Fuente - Colombia'
    _order = 'year desc'

    # ──────────────────────────────────────────────────────────────────
    # Campos
    # ──────────────────────────────────────────────────────────────────
    year = fields.Char(
        string='Año Fiscal',
        required=True,
        help='Año gravable al que corresponde el valor de la UVT. '
             'Ejemplo: 2024.',
    )
    uvt_value = fields.Monetary(
        string='Valor UVT ($)',
        compute='_compute_uvt_value',
        readonly=True,
        currency_field='currency_id',
        help='Valor de la Unidad de Valor Tributario (UVT) fijado por la '
             'DIAN para el año fiscal correspondiente. Se toma del '
             'parámetro nativo l10n_co_uvt (hr.rule.parameter) — única '
             'fuente de verdad para el UVT (doc 13).',
    )
    procedure = fields.Selection(
        selection=[
            ('1', 'Procedimiento 1'),
            ('2', 'Procedimiento 2'),
        ],
        string='Procedimiento de Retención',
        default='1',
        required=True,
        help='Procedimiento de retención en la fuente a aplicar:\n'
             '• Procedimiento 1 (Art. 383 ET): tabla marginal mes a mes.\n'
             '• Procedimiento 2 (Art. 386 ET): porcentaje fijo semestral '
             'calculado sobre el promedio de pagos del semestre anterior.',
    )
    percentage_procedure2 = fields.Float(
        string='Porcentaje Fijo Proc. 2 (%)',
        digits=(5, 2),
        default=0.0,
        help='Porcentaje fijo de retención aplicable bajo el Procedimiento 2. '
             'Se calcula semestralmente sobre el promedio de pagos gravables '
             'del semestre inmediatamente anterior.\n'
             'Solo se usa cuando el procedimiento seleccionado es "2".',
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Permite archivar registros de UVT de años anteriores.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        help='Compañía a la que pertenece esta configuración. '
             'Si se deja vacío aplica para todas las compañías.',
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
        store=True,
        readonly=True,
    )
    notes = fields.Text(
        string='Notas',
        help='Notas internas o referencias legales adicionales.',
    )

    # ──────────────────────────────────────────────────────────────────
    # SQL Constraint — un solo registro de UVT por año + compañía
    # ──────────────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'year_company_uniq',
            'UNIQUE(year, company_id)',
            'Ya existe una configuración de UVT para este año y compañía.',
        ),
    ]

    # ──────────────────────────────────────────────────────────────────
    # Validaciones
    # ──────────────────────────────────────────────────────────────────
    @api.constrains('uvt_value')
    def _check_uvt_value(self):
        """Valida que el valor de la UVT sea positivo."""
        for rec in self:
            if rec.uvt_value <= 0:
                raise ValidationError(_(
                    'El valor de la UVT debe ser mayor a cero. '
                    'Valor ingresado: %(value)s',
                    value=rec.uvt_value,
                ))

    @api.constrains('percentage_procedure2', 'procedure')
    def _check_percentage_procedure2(self):
        """Valida que el porcentaje del Proc. 2 sea coherente."""
        for rec in self:
            if rec.procedure == '2' and rec.percentage_procedure2 < 0:
                raise ValidationError(_(
                    'El porcentaje fijo del Procedimiento 2 no puede ser '
                    'negativo. Valor ingresado: %(pct)s%%',
                    pct=rec.percentage_procedure2,
                ))

    @api.constrains('year')
    def _check_year_format(self):
        """Valida que el año sea un número de 4 dígitos."""
        for rec in self:
            if not rec.year or not rec.year.isdigit() or len(rec.year) != 4:
                raise ValidationError(_(
                    'El año fiscal debe ser un número de 4 dígitos. '
                    'Ejemplo: 2024. Valor ingresado: "%(year)s"',
                    year=rec.year,
                ))

    # ──────────────────────────────────────────────────────────────────
    # Display name
    # ──────────────────────────────────────────────────────────────────
    @api.depends('year')
    def _compute_uvt_value(self):
        """Toma el valor de UVT del parámetro nativo l10n_co_uvt.

        `hr.rule.parameter` no tiene `company_id` (solo `country_id`,
        ver doc 13) por lo que este lookup no depende de la compañía del
        registro — el UVT es un valor nacional único por año fiscal.

        Doc 06 (2026-09-12): deliberadamente NO ``store=True``. La única
        dependencia declarable con ``@api.depends`` es ``year`` -- Odoo no
        puede rastrear automáticamente cambios en
        ``hr.rule.parameter.value`` (modelo distinto, sin relación directa)
        para invalidar un valor cacheado. Verificado empíricamente: con
        ``store=True`` este campo quedaba con el valor viejo (stale) si el
        parámetro real ``l10n_co_uvt`` se corregía después de creado el
        registro de retención -- exactamente las "2 fuentes de UVT sin
        relacionar entre sí" que motivó este punto del backlog. Sin
        ``store``, el lookup se recalcula en cada lectura (barato, un solo
        ``_get_parameter_from_code``), sin riesgo de desincronización.
        """
        RuleParameter = self.env['hr.rule.parameter']
        for rec in self:
            if not rec.year or not rec.year.isdigit():
                rec.uvt_value = 0.0
                continue
            value = RuleParameter._get_parameter_from_code(
                'l10n_co_uvt', '%s-01-01' % rec.year,
                raise_if_not_found=False)
            rec.uvt_value = value or 0.0

    @api.depends('year', 'uvt_value', 'procedure')
    def _compute_display_name(self):
        """Nombre descriptivo: 'UVT 2024 — $47,065.00 (Proc. 1)'."""
        for rec in self:
            proc_label = dict(
                rec._fields['procedure'].selection
            ).get(rec.procedure, '')
            rec.display_name = (
                f"UVT {rec.year} — "
                f"${rec.uvt_value:,.2f} ({proc_label})"
            )

    # ══════════════════════════════════════════════════════════════════
    # MÉTODO PRINCIPAL: compute_retefuente
    # ══════════════════════════════════════════════════════════════════
    def compute_retefuente(self, employee, gross_salary, ibc_pension,
                           ibc_salud, company=None, contract=None,
                           payslip=None, force_procedure=None):
        """Calcula la retención en la fuente mensual para un empleado.

        Ejecuta la depuración de la base gravable según la normatividad
        colombiana y aplica la tabla marginal del Art. 383 ET
        (Procedimiento 1) o el porcentaje fijo (Procedimiento 2).

        :param employee: recordset ``hr.employee``
        :param gross_salary: float — Ingreso bruto mensual ($)
        :param ibc_pension: float — IBC para aportes a pensión ($)
        :param ibc_salud: float — IBC para aportes a salud ($)
        :param company: recordset ``res.company`` (opcional; si no se
            pasa se usa ``self.env.company``)
        :param contract: recordset ``hr.contract`` (opcional -- fuente de
            ``l10n_co_ne_pension_voluntaria``/``l10n_co_ne_afc`` para el
            tope combinado del 30%%, AUD-05/doc 32. Sin contrato, esos
            aportes se tratan como 0 -- mismo comportamiento que antes de
            AUD-05 cuando el empleado no tenia los campos configurados)
        :param payslip: recordset ``hr.payslip`` (opcional -- necesario
            para el techo anual de 3.800 UVT combinado, AUD-05/doc 32:
            consulta cuanto se trato como exento en meses anteriores del
            mismo año calendario via ``payslip._sum('CO_EXENTO_PENSION_AFC',
            ...)``. Sin payslip, se omite el techo anual -- solo aplica el
            tope mensual)
        :param force_procedure: str '1'/'2' (opcional -- doc 08). Si se
            pasa, ignora ``self.procedure`` (el de la config anual,
            compartido) y fuerza esa rama. Lo usa
            ``hr.contract.action_calculate_retention_procedure2()`` para
            aplicar SIEMPRE la tabla marginal Art. 383 (fuerza '1') sobre
            el ingreso PROMEDIO al derivar el % fijo semestral, sin
            importar qué procedimiento tenga configurado el año en curso.
        :returns: dict con el detalle de la depuración y el valor final
            de retención en pesos, con la siguiente estructura::

                {
                    'ingreso_bruto': float,
                    'aporte_salud': float,
                    'aporte_pension': float,
                    'aporte_voluntario_pension': float,
                    'afc': float,
                    'deduccion_dependientes': float,
                    'subtotal_depurado': float,
                    'renta_exenta_25': float,
                    'base_gravable': float,
                    'base_uvt': float,
                    'retencion_uvt': float,
                    'retencion_pesos': float,
                    'procedure': str,
                    'uvt_value': float,
                }
        """
        self.ensure_one()
        uvt = self.uvt_value
        _ref_date = '%s-01-01' % self.year
        RuleParameter = self.env['hr.rule.parameter']

        def _p(code):
            return RuleParameter._get_parameter_from_code(code, _ref_date)

        if uvt <= 0:
            raise UserError(_(
                'El valor de la UVT para el año %(year)s no está '
                'configurado o es inválido.',
                year=self.year,
            ))

        # ── 1. Ingreso bruto mensual ─────────────────────────────────
        ingreso_bruto = gross_salary

        # ── 2. Aportes obligatorios salud empleado ────────────────────
        aporte_salud = round(
            ibc_salud * _p('l10n_co_pct_salud_empleado') / 100, 2)

        # ── 3. Aportes obligatorios pensión empleado ──────────────────
        aporte_pension = round(
            ibc_pension * _p('l10n_co_pct_pension_empleado') / 100, 2)

        # ── 4/5. Pensión voluntaria + AFC — tope COMBINADO del 30%% ──
        #     AUD-05/doc 32: Art. 126-1 ET (mod. Ley 1819/2016) + Art.
        #     126-4 ET dan un tope UNICO combinado, no 2 topes
        #     independientes -- un aporte que sume mas del limite entre
        #     ambos conceptos se reduce PROPORCIONALMENTE (sin prelacion
        #     normativa entre los 2, decision de diseño confirmada).
        #     Fuente de los montos: contract.l10n_co_ne_pension_voluntaria/
        #     l10n_co_ne_afc -- la misma fuente que alimenta la deduccion
        #     real del payslip (reglas CO_PENSION_VOL/CO_AFC), no un campo
        #     de empleado desconectado (el que existia antes se eliminó).
        raw_vol_pension = (contract.l10n_co_ne_pension_voluntaria or 0.0) if contract else 0.0
        raw_afc = (contract.l10n_co_ne_afc or 0.0) if contract else 0.0
        total_raw_vol_afc = raw_vol_pension + raw_afc

        max_combinado_pct = _p('l10n_co_max_vol_pension_afc_combinado_pct')
        max_combinado_mes = ingreso_bruto * max_combinado_pct / 100

        if total_raw_vol_afc > max_combinado_mes and total_raw_vol_afc > 0:
            _factor = max_combinado_mes / total_raw_vol_afc
            exento_vol_pension_mes = raw_vol_pension * _factor
            exento_afc_mes = raw_afc * _factor
        else:
            exento_vol_pension_mes = raw_vol_pension
            exento_afc_mes = raw_afc

        exento_vol_afc_mes = exento_vol_pension_mes + exento_afc_mes

        # ── Techo anual adicional: 3.800 UVT combinados (mismo Art.) ──
        #     Requiere saber cuanto ya se trato como exento en meses
        #     ANTERIORES del mismo año calendario -- se consulta sobre la
        #     regla invisible CO_EXENTO_PENSION_AFC de payslips ya
        #     confirmados (state in done/paid), mismo criterio que
        #     payslip._sum() ya usa en el resto del modulo (helper nativo
        #     de hr_payroll Enterprise). Sin payslip (ej. accion de
        #     ejemplo/demo), se omite el techo anual.
        if payslip is not None:
            techo_anual = _p('l10n_co_max_vol_pension_afc_anual_uvt') * uvt
            _year_start = payslip.date_from.replace(month=1, day=1)
            _dia_anterior = payslip.date_from - timedelta(days=1)
            if _dia_anterior >= _year_start:
                acumulado_previo = payslip._sum(
                    'CO_EXENTO_PENSION_AFC', _year_start, _dia_anterior,
                )
            else:
                acumulado_previo = 0.0
            disponible_anual = max(0.0, techo_anual - acumulado_previo)
            exento_vol_afc_mes = min(exento_vol_afc_mes, disponible_anual)

        # Reparto proporcional del exento FINAL (ya con tope mensual y techo
        # anual aplicados) entre los 2 conceptos, en la misma proporcion de
        # sus montos brutos originales -- mantiene aporte_voluntario_pension/
        # afc como cifras separadas en el dict de retorno (para reportes/
        # accion de ejemplo), consistente pase lo que pase con el escalado.
        if total_raw_vol_afc > 0:
            aporte_vol_pension = exento_vol_afc_mes * (raw_vol_pension / total_raw_vol_afc)
            afc = exento_vol_afc_mes * (raw_afc / total_raw_vol_afc)
        else:
            aporte_vol_pension = 0.0
            afc = 0.0

        # ── 6. Deducción por dependientes ─────────────────────────────
        #     pct_deduccion_dependientes%, máx max_dependientes_uvt UVT/mes
        deduccion_dep = 0.0
        has_dependientes = False
        if hasattr(employee, 'l10n_co_ne_dependientes'):
            has_dependientes = employee.l10n_co_ne_dependientes
        if has_dependientes:
            dep_calc = (
                ingreso_bruto * _p('l10n_co_pct_deduccion_dependientes')
                / 100)
            dep_max = _p('l10n_co_max_dependientes_uvt') * uvt
            deduccion_dep = min(dep_calc, dep_max)

        # ── Subtotal depurado (antes de renta exenta 25%) ────────────
        subtotal = (
            ingreso_bruto
            - aporte_salud
            - aporte_pension
            - aporte_vol_pension
            - afc
            - deduccion_dep
        )
        subtotal = max(subtotal, 0.0)

        # ── 7. Renta exenta (máximo max_renta_exenta_uvt UVT/mes) ────
        renta_exenta_25 = min(
            subtotal * _p('l10n_co_pct_renta_exenta') / 100,
            _p('l10n_co_max_renta_exenta_uvt') * uvt)

        # ── 8. Base gravable ─────────────────────────────────────────
        base_gravable = max(subtotal - renta_exenta_25, 0.0)

        # ── 9. Conversión a UVT ──────────────────────────────────────
        base_uvt = base_gravable / uvt

        # ── 10. Aplicar tabla marginal o porcentaje fijo ─────────────
        # Doc 08: el procedimiento real es POR CONTRATO
        # (contract.l10n_co_ne_retention_procedure), no el ``self.procedure``
        # de esta config anual compartida (queda solo como fallback legado
        # si no se pasa contrato). ``force_procedure`` (doc 08) tiene
        # prioridad sobre ambos -- lo usa
        # ``action_calculate_retention_procedure2()`` para forzar tabla
        # marginal sobre el ingreso promedio al derivar el % fijo.
        effective_procedure = (
            force_procedure
            or (contract.l10n_co_ne_retention_procedure if contract else None)
            or self.procedure
        )
        if effective_procedure == '1':
            retencion_uvt = self._apply_marginal_table(base_uvt)
        else:
            # Procedimiento 2 (Art. 384 ET): % fijo del semestre vigente,
            # calculado por contrato (doc 08) -- ``percentage_procedure2``
            # (compartido) queda solo como fallback si no hay contrato o
            # no se ha calculado el semestre todavia.
            pct = self.percentage_procedure2
            if contract:
                _ref = payslip.date_from if payslip else fields.Date.context_today(self)
                semester_start = _ref.replace(month=1, day=1) if _ref.month <= 6 else _ref.replace(month=7, day=1)
                proc2 = self.env['l10n.co.retefuente.procedure2'].search([
                    ('contract_id', '=', contract.id),
                    ('semester_start', '=', semester_start),
                ], limit=1)
                if proc2:
                    pct = proc2.fixed_percentage
                else:
                    raise UserError(_(
                        'El contrato de %(employee)s está en Procedimiento '
                        '2 pero no tiene el porcentaje fijo calculado para '
                        'el semestre que inicia %(semester)s. Use el botón '
                        '"Calcular Procedimiento 2" en el contrato antes de '
                        'generar esta nómina.',
                        employee=employee.name,
                        semester=semester_start,
                    ))
            retencion_uvt = base_uvt * (pct / 100.0)

        # ── 11. Convertir resultado a pesos ──────────────────────────
        retencion_pesos = round(retencion_uvt * uvt, 0)

        result = {
            'ingreso_bruto': ingreso_bruto,
            'aporte_salud': aporte_salud,
            'aporte_pension': aporte_pension,
            'aporte_voluntario_pension': aporte_vol_pension,
            'afc': afc,
            'exento_vol_pension_afc': aporte_vol_pension + afc,
            'deduccion_dependientes': deduccion_dep,
            'subtotal_depurado': subtotal,
            'renta_exenta_25': renta_exenta_25,
            'base_gravable': base_gravable,
            'base_uvt': round(base_uvt, 4),
            'retencion_uvt': round(retencion_uvt, 4),
            'retencion_pesos': retencion_pesos,
            'procedure': self.procedure,
            'uvt_value': uvt,
        }

        _logger.info(
            'Retención en la fuente calculada para %s: '
            'base_gravable=$%s, base_uvt=%s UVT, '
            'retención=$%s (Proc. %s)',
            employee.name,
            f'{base_gravable:,.2f}',
            f'{base_uvt:,.4f}',
            f'{retencion_pesos:,.0f}',
            self.procedure,
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    # TABLA MARGINAL — Art. 383 ET (Procedimiento 1)
    # ══════════════════════════════════════════════════════════════════
    @api.model
    def _apply_marginal_table(self, base_uvt):
        """Aplica la tabla marginal del Art. 383 del Estatuto Tributario.

        :param base_uvt: float — Base gravable expresada en UVT.
        :returns: float — Retención calculada en UVT.

        **Tabla de rangos:**

        +-----------------------+--------+-----------------------------------------+
        | Rango (UVT)           | Tarifa | Instrucción                             |
        +=======================+========+=========================================+
        | > 0 hasta 95          |   0%   | 0                                       |
        | > 95 hasta 150        |  19%   | (Ingreso − 95) × 19%                   |
        | > 150 hasta 360       |  28%   | (Ingreso − 150) × 28% + 10 UVT         |
        | > 360 hasta 640       |  33%   | (Ingreso − 360) × 33% + 69 UVT         |
        | > 640 hasta 945       |  35%   | (Ingreso − 640) × 35% + 162 UVT        |
        | > 945 hasta 2300      |  37%   | (Ingreso − 945) × 37% + 268 UVT        |
        | > 2300                |  39%   | (Ingreso − 2300) × 39% + 770 UVT       |
        +-----------------------+--------+-----------------------------------------+
        """
        if base_uvt <= 0:
            return 0.0

        for lower, upper, rate, fixed_uvt in MARGINAL_TABLE_ART383:
            if base_uvt <= upper:
                return (base_uvt - lower) * rate + fixed_uvt

        # Fallback (no debería alcanzarse por el inf en la tabla)
        last = MARGINAL_TABLE_ART383[-1]
        return (base_uvt - last[0]) * last[2] + last[3]

    # ══════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════
    @api.model
    def get_uvt_for_year(self, year, company=None):
        """Obtiene el registro de UVT vigente para un año fiscal y compañía.

        :param year: str — Año fiscal (e.g. '2024').
        :param company: recordset ``res.company`` (opcional).
        :returns: recordset ``l10n.co.retefuente.uvt``
        :raises UserError: si no se encuentra configuración para el año.
        """
        company = company or self.env.company
        domain = [
            ('year', '=', str(year)),
            '|',
            ('company_id', '=', company.id),
            ('company_id', '=', False),
        ]
        uvt_rec = self.search(domain, limit=1, order='company_id desc')
        if not uvt_rec:
            raise UserError(_(
                'No se encontró configuración de UVT para el año %(year)s. '
                'Vaya a Nómina ▸ Configuración ▸ Retención en la Fuente '
                'y cree el registro correspondiente.',
                year=year,
            ))
        return uvt_rec

    def action_compute_example(self):
        """Acción de prueba: calcula la retención para un salario ejemplo.

        Útil para verificar que la configuración de UVT y la tabla marginal
        estén funcionando correctamente. Muestra el resultado en un
        cuadro de diálogo.
        """
        self.ensure_one()

        # Crear un mock mínimo para el empleado
        class _MockEmployee:
            name = 'Empleado Ejemplo'
            l10n_co_ne_dependientes = False

        example_salary = 5_000_000.0
        result = self.compute_retefuente(
            employee=_MockEmployee(),
            gross_salary=example_salary,
            ibc_pension=example_salary,
            ibc_salud=example_salary,
        )

        message_lines = [
            _('═══ EJEMPLO DE CÁLCULO — RETENCIÓN EN LA FUENTE ═══'),
            '',
            _('Salario bruto: $%(salary)s',
              salary=f'{example_salary:,.0f}'),
            _('UVT %(year)s: $%(uvt)s',
              year=self.year, uvt=f'{self.uvt_value:,.2f}'),
            '',
            _('── Depuración ──'),
            _('(-) Aporte salud: $%(v)s', v=f'{result["aporte_salud"]:,.0f}'),
            _('(-) Aporte pensión: $%(v)s',
              v=f'{result["aporte_pension"]:,.0f}'),
            _('(-) Dependientes: $%(v)s',
              v=f'{result["deduccion_dependientes"]:,.0f}'),
            _('= Subtotal depurado: $%(v)s',
              v=f'{result["subtotal_depurado"]:,.0f}'),
            _('(-) Renta exenta 25%%: $%(v)s',
              v=f'{result["renta_exenta_25"]:,.0f}'),
            '',
            _('Base gravable: $%(v)s', v=f'{result["base_gravable"]:,.0f}'),
            _('Base en UVT: %(v)s', v=f'{result["base_uvt"]:,.4f}'),
            _('Retención en UVT: %(v)s', v=f'{result["retencion_uvt"]:,.4f}'),
            '',
            _('RETENCION EN PESOS: $%(v)s',
              v=f'{result["retencion_pesos"]:,.0f}'),
        ]

        raise UserError('\n'.join(message_lines))
