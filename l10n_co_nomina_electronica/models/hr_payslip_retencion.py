# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""R-2 (doc 108, opción C; David, 25-nov): retención en la fuente sobre los pagos del MES.

Procedimiento 1: la retención se calcula con ``compute_retefuente`` (sin cambios) sobre los pagos gravables del mes (mes por «Hasta») y se descuenta completa en el recibo que lo cierra; los anteriores no
retienen y no hay reintegros. La liquidación siempre cierra; una bonificación retiene el saldo solo si el cierre ya está confirmado. Qué entra en la base lo dice el parámetro versionado
``l10n_co_retefuente_base_mes``. Procedimiento 2: cada recibo retiene su porcentaje sobre sus propios pagos.

Si lo que toca descontar no cabe en el recibo (devengado menos aportes obligatorios del trabajador), se retiene lo disponible y confirmar exige la autorización del administrador de nómina.
Ningún recibo colombiano se confirma con neto negativo."""

from calendar import monthrange
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import formatLang

PARAMETRO_BASE = 'l10n_co_retefuente_base_mes'
_CLAVES_BASE = ('categorias', 'reglas_excluidas', 'reglas_adicionales_liquidacion')
# Regla de retención de cada estructura que suma al mes -> orden entre recibos con el mismo «Hasta». La prima tiene su retención aparte.
_ORDEN = {'CO_BON_RETE': 0, 'CO_RETEFUENTE': 1, 'CO_LIQ_RETE': 2}
_DIAS_ENTRE_PAGOS = {'bi-weekly': 14, 'weekly': 7, 'daily': 1}
_CONFIRMADOS = ('done', 'paid')
_ABIERTOS = ('draft', 'verify')
_AUTORIZACION = 'l10n_co_ne_rete_autorizada'
_DEL_SISTEMA = (
    'l10n_co_ne_rete_a_descontar', 'l10n_co_ne_rete_disponible', 'l10n_co_ne_rete_faltante', 'l10n_co_ne_rete_autorizada_por', 'l10n_co_ne_rete_autorizada_fecha',
    'l10n_co_ne_rete_autorizada_a_descontar', 'l10n_co_ne_rete_autorizada_disponible')
_SIN_AUTORIZACION = {
    _AUTORIZACION: False, 'l10n_co_ne_rete_autorizada_por': False, 'l10n_co_ne_rete_autorizada_fecha': False,
    'l10n_co_ne_rete_autorizada_a_descontar': 0.0, 'l10n_co_ne_rete_autorizada_disponible': 0.0}


def _en_categorias(categoria, codigos):
    while categoria:
        if categoria.code in codigos:
            return True
        categoria = categoria.parent_id
    return False


class HrPayslipRetencion(models.Model):
    _inherit = 'hr.payslip'

    l10n_co_ne_rete_a_descontar = fields.Monetary(string='Retención por descontar', readonly=True, copy=False)
    l10n_co_ne_rete_disponible = fields.Monetary(string='Disponible para la retención', readonly=True, copy=False)
    l10n_co_ne_rete_faltante = fields.Monetary(string='Retención sin practicar', readonly=True, copy=False)
    l10n_co_ne_rete_autorizada = fields.Boolean(
        string='Autorizo confirmar con retención incompleta', copy=False, tracking=True,
        help='Solo el administrador de nómina. Vale para las cifras que se ven al marcarla: si un nuevo cálculo las cambia, la marca se borra.')
    l10n_co_ne_rete_autorizada_por = fields.Many2one('res.users', string='Autorizada por', readonly=True, copy=False)
    l10n_co_ne_rete_autorizada_fecha = fields.Datetime(string='Fecha de la autorización', readonly=True, copy=False)
    l10n_co_ne_rete_autorizada_a_descontar = fields.Monetary(string='Retención por descontar autorizada', readonly=True, copy=False)
    l10n_co_ne_rete_autorizada_disponible = fields.Monetary(string='Disponible autorizado', readonly=True, copy=False)

    # ── qué recibo retiene ───────────────────────────────────────────
    def _ne_rete_codigo(self):
        """Código de la regla de retención de la estructura del recibo si suma al mes (nómina, bonificación o liquidación); ``False`` en las demás."""
        codigos = set(self.struct_id.rule_ids.mapped('code'))
        return next((codigo for codigo in _ORDEN if codigo in codigos), False)

    def _ne_rete_es_cierre(self):
        """¿El recibo cierra el mes de su «Hasta»? La liquidación siempre; la nómina si el contrato termina dentro de su periodo o si es el último pago del mes según la periodicidad (quincenal: «Hasta»
        el día 16 o después; cada 14 días, semanal y diario: el siguiente pago ya cae en otro mes; mensual y mayores: siempre). Una bonificación nunca cierra."""
        self.ensure_one()
        codigo = self._ne_rete_codigo()
        if codigo != 'CO_RETEFUENTE':
            return codigo == 'CO_LIQ_RETE'
        contrato = self.contract_id
        if contrato.date_end and self.date_from <= contrato.date_end <= self.date_to:
            return True
        periodicidad = contrato.schedule_pay or contrato.structure_type_id.default_schedule_pay
        if periodicidad == 'semi-monthly':
            return self.date_to.day >= 16
        dias = _DIAS_ENTRE_PAGOS.get(periodicidad)
        return not dias or (self.date_to + timedelta(days=dias)).month != self.date_to.month

    def _ne_rete_otros_del_mes(self):
        """Los demás recibos que suman al mes: mismo empleado y compañía, «Hasta» en el mes del «Hasta» de este, sin los cancelados."""
        self.ensure_one()
        inicio = self.date_to.replace(day=1)
        fin = inicio.replace(day=monthrange(inicio.year, inicio.month)[1])
        otros = self.sudo().search([
            ('id', '!=', self.id), ('employee_id', '=', self.employee_id.id), ('company_id', '=', self.company_id.id),
            ('date_to', '>=', inicio), ('date_to', '<=', fin), ('state', '!=', 'cancel')])
        return otros.filtered(lambda r: r._ne_rete_codigo())

    def _ne_rete_es_procedimiento_1(self):
        return (self.contract_id.l10n_co_ne_retention_procedure or self._ne_retefuente_config().procedure) == '1'

    def _ne_rete_retiene_mes(self):
        """¿Este recibo retiene sobre el mes (Procedimiento 1)? La nómina que cierra y la liquidación; la bonificación solo si ya hay un cierre confirmado en el mes."""
        self.ensure_one()
        codigo = self._ne_rete_codigo()
        if not codigo or not self._ne_rete_es_procedimiento_1():
            return False
        if codigo != 'CO_BON_RETE':
            return self._ne_rete_es_cierre()
        cierres = self._ne_rete_otros_del_mes().filtered(lambda r: r.state in _CONFIRMADOS and r._ne_rete_es_cierre())
        return sum(-1 if cierre.credit_note else 1 for cierre in cierres) > 0

    def _ne_rete_validar_pendientes(self):
        """Antes de calcular un recibo que retiene por el mes: ningún recibo del mes que deba sumar puede estar sin confirmar. Para la nómina y la liquidación, toda bonificación y los recibos anteriores;
        para una bonificación, solo las bonificaciones anteriores (así dos recibos nunca se esperan el uno al otro)."""
        for recibo in self.filtered(lambda r: r.state in _ABIERTOS and not r.credit_note and r._ne_rete_codigo()):
            if not recibo._ne_rete_retiene_mes():
                continue
            codigo = recibo._ne_rete_codigo()
            clave = (recibo.date_to, _ORDEN[codigo], recibo.id)

            def bloquea(otro, codigo=codigo, clave=clave):
                otro_codigo = otro._ne_rete_codigo()
                anterior = (otro.date_to, _ORDEN[otro_codigo], otro.id) < clave
                if codigo == 'CO_BON_RETE':
                    return otro_codigo == codigo and anterior
                return otro_codigo == 'CO_BON_RETE' or anterior

            pendientes = recibo._ne_rete_otros_del_mes().filtered(lambda o: o.state in _ABIERTOS and bloquea(o))          # un reembolso sin confirmar también
            if pendientes:
                nombres = ', '.join('«%s»' % (p.number or p.name) for p in pendientes)
                raise UserError(_(
                    'No se puede calcular «%(recibo)s» de %(empleado)s: retiene la retención en la fuente de todo el mes y hay recibos de ese mes sin confirmar: %(pendientes)s. Confírmelos o '
                    'cancélelos primero y vuelva a pulsar «Calcular hoja».', recibo=recibo.number or recibo.name, empleado=recibo.employee_id.name, pendientes=nombres))

    # ── la base ──────────────────────────────────────────────────────
    def _ne_rete_parametro(self):
        """El valor vigente de ``l10n_co_retefuente_base_mes``: un diccionario con exactamente las tres listas de códigos. Sin valor por defecto."""
        self.ensure_one()
        valor = self._rule_parameter(PARAMETRO_BASE, self._ne_fecha_parametros())
        valido = isinstance(valor, dict) and set(valor) == set(_CLAVES_BASE) and all(
            isinstance(valor[clave], list) and all(isinstance(codigo, str) and codigo for codigo in valor[clave]) for clave in _CLAVES_BASE)
        if not valido or not valor['categorias']:
            raise UserError(_(
                'El parámetro de regla salarial «%(parametro)s» vigente el %(fecha)s no tiene la forma esperada: un diccionario con las claves «categorias» (al menos un código), «reglas_excluidas» y '
                '«reglas_adicionales_liquidacion», cada una con una lista de códigos. Corríjalo en Nómina > Configuración > Parámetros de reglas salariales.',
                parametro=PARAMETRO_BASE, fecha=self._ne_fecha_parametros()))
        return valor

    def _ne_rete_codigos_base(self, reglas, liquidacion=None):
        """Códigos de ``reglas`` cuyos valores forman la base de la retención, según el parámetro vigente en ESTE recibo. ``liquidacion``: si son de una liquidación (por defecto, lo es este recibo)."""
        parametro = self._ne_rete_parametro()
        if liquidacion is None:
            liquidacion = self._ne_rete_codigo() == 'CO_LIQ_RETE'
        adicionales = set(parametro['reglas_adicionales_liquidacion']) if liquidacion else set()
        return {
            regla.code for regla in reglas
            if regla.code in adicionales or (regla.code not in parametro['reglas_excluidas'] and _en_categorias(regla.category_id, parametro['categorias']))}

    def _ne_rete_ibc(self, salarial):
        """Base salarial de este recibo a partir de sus devengados salariales: 0 en una bonificación no salarial; con salario integral, por su factor."""
        self.ensure_one()
        if self._ne_rete_codigo() == 'CO_BON_RETE' and not self.l10n_co_ne_is_salarial:
            return 0.0
        if self.contract_id.l10n_co_ne_integral_salary:
            return salarial * self._rule_parameter('l10n_co_factor_integral_salary', self._ne_fecha_parametros())
        return salarial

    def _ne_rete_cifras_de(self, recibo):
        """``(base, base salarial, salud, pensión, retenido, exento voluntario)`` de un recibo confirmado del mes, leídos de sus líneas (un reembolso las trae negadas)."""
        lineas = recibo.line_ids
        codigos = self._ne_rete_codigos_base(lineas.salary_rule_id, liquidacion=recibo._ne_rete_codigo() == 'CO_LIQ_RETE')
        salarial = sum(l.total for l in lineas if _en_categorias(l.salary_rule_id.category_id, ('DEV_SAL',)))
        return (
            sum(l.total for l in lineas if l.code in codigos), recibo._ne_rete_ibc(salarial), *self._ne_rete_aportes_de(lineas),
            -sum(l.total for l in lineas if l.code in _ORDEN), sum(l.total for l in lineas if l.code == 'CO_EXENTO_PENSION_AFC'))

    def _ne_rete_codigos_aporte(self, reglas):
        """``(códigos de salud, códigos de pensión)`` que descuenta el trabajador: reglas de ``SS_EMP`` por su concepto DIAN. El fondo de solidaridad no entra en esta resta."""
        return tuple(
            {regla.code for regla in reglas if regla.l10n_co_ne_dian_concept == concepto and _en_categorias(regla.category_id, ('SS_EMP',))}
            for concepto in ('Salud', 'FondoPension'))

    def _ne_rete_aportes_de(self, lineas):
        """``(salud, pensión)`` del trabajador efectivamente descontadas en ``lineas`` (positivas; en un reembolso, negativas)."""
        return tuple(
            -sum(lineas.filtered(lambda l, codigos=codigos: l.code in codigos).mapped('total'))
            for codigos in self._ne_rete_codigos_aporte(lineas.salary_rule_id))

    def _ne_rete_validar_secuencias(self):
        """Un devengado o un aporte que se calcule DESPUÉS de la retención quedaría fuera de su base sin avisar (p. ej. un concepto creado por la empresa): se detiene el cálculo y se nombra."""
        for recibo in self.filtered(lambda r: r._ne_rete_codigo()):
            reglas = recibo.struct_id.rule_ids
            retencion = reglas.filtered(lambda r: r.code == recibo._ne_rete_codigo())
            limite = min(retencion.mapped('sequence'))
            codigos = recibo._ne_rete_codigos_base(reglas)
            tarde = reglas.filtered(lambda r: r.sequence >= limite and (
                r.code in codigos or _en_categorias(r.category_id.parent_id, ('DEV',)) or _en_categorias(r.category_id, ('SS_EMP',))))
            if tarde:
                raise UserError(_(
                    'No se puede calcular «%(recibo)s»: estas reglas se calculan después de «%(retencion)s» (secuencia %(limite)s) y quedarían fuera de la retención en la fuente: %(reglas)s. '
                    'Póngales una secuencia menor en la regla salarial.', recibo=recibo.number or recibo.name, retencion=retencion[:1].name, limite=limite,
                    reglas=', '.join('«%s» (%s, secuencia %s)' % (r.name, r.code, r.sequence) for r in tarde)))

    # ── el cálculo (lo llaman las reglas) ────────────────────────────
    def _ne_resultado_retefuente(self, result_rules):
        """UN solo lugar (H-F1-02) para las reglas de retención de la nómina, la liquidación y la bonificación y sus acumuladores.

        :param result_rules: las líneas ya calculadas del recibo (``localdict['result_rules']``).
        La depuración resta la salud y la pensión del trabajador efectivamente descontadas en los recibos que suman (vacaciones, incapacidad y exceso del 40 % incluidos).

        :returns: ``base`` y ``ibc`` propios del recibo; ``retiene`` (si lleva línea de retención); ``a_descontar`` (pesos, nunca negativo); ``exento`` (pensión voluntaria y AFC que este recibo suma al
            acumulado anual) y ``exceso`` (lo que el límite global no dejó deducir)."""
        self.ensure_one()
        reglas = self.struct_id.rule_ids
        base = sum(result_rules[codigo]['total'] for codigo in self._ne_rete_codigos_base(reglas))
        salariales = {regla.code for regla in reglas if _en_categorias(regla.category_id, ('DEV_SAL',))}
        ibc = self._ne_rete_ibc(sum(result_rules[codigo]['total'] for codigo in salariales))
        resultado = {'base': base, 'ibc': ibc, 'retiene': False, 'a_descontar': 0.0, 'exento': 0.0, 'exceso': 0.0}
        config = self._ne_retefuente_config()
        mensual = self._ne_rete_es_procedimiento_1()
        salud, pension = (-sum(result_rules[codigo]['total'] for codigo in codigos) for codigos in self._ne_rete_codigos_aporte(reglas))
        previos = [0.0] * 6
        if mensual:
            if not self._ne_rete_retiene_mes():
                return resultado
            for recibo in self._ne_rete_otros_del_mes().filtered(lambda r: r.state in _CONFIRMADOS):
                previos = [suma + valor for suma, valor in zip(previos, self._ne_rete_cifras_de(recibo))]
        base_previa, ibc_previo, salud_previa, pension_previa, retenido, exento_previo = previos
        calculo = config.compute_retefuente(
            self.employee_id, base + base_previa, ibc + ibc_previo, ibc + ibc_previo, self.employee_id.company_id,
            contract=self.contract_id, payslip=self, fecha_mes=self.date_to if mensual else None,
            aporte_salud=salud + salud_previa, aporte_pension=pension + pension_previa)
        resultado.update(
            retiene=True, a_descontar=max(calculo['retencion_pesos'] - retenido, 0.0),
            exento=calculo['exento_vol_pension_afc'] - exento_previo, exceso=calculo.get('exceso_limite_global', 0.0))
        return resultado

    def _ne_rete_linea(self, result_rules, resultado):
        """Pesos (positivos) que descuenta este recibo: lo que toca, con tope en lo disponible = devengado del recibo menos los aportes obligatorios del trabajador (salud, pensión y fondo de
        solidaridad), con las líneas redondeadas como en el neto. Anota las tres cifras para guardarlas cuando termine el cálculo."""
        self.ensure_one()
        a_descontar = resultado['a_descontar']
        disponible = self._ne_redondear_moneda(max(
            self._ne_suma_lineas_redondeadas(result_rules, 'DEV') + self._ne_suma_lineas_redondeadas(result_rules, 'SS_EMP'), 0.0))
        linea = min(a_descontar, disponible)
        cifras = self.env.context.get('ne_retencion')
        if cifras is not None:
            cifras[self.id] = (a_descontar, disponible, a_descontar - linea)
        return linea

    def _ne_rete_pesos(self, valor):
        return formatLang(self.env, valor, currency_obj=self.currency_id)

    def _ne_rete_guardar_cifras(self, cifras):
        """Al terminar el cálculo: guarda las tres cifras, borra la autorización si ya no corresponden y deja nota en el historial. Escribe por debajo de este ``write`` (``super``)."""
        for recibo in self:
            a_descontar, disponible, faltante = cifras.get(recibo.id, (0.0, 0.0, 0.0))
            comparar = recibo.currency_id.compare_amounts
            cambian = (comparar(a_descontar, recibo.l10n_co_ne_rete_a_descontar) or comparar(disponible, recibo.l10n_co_ne_rete_disponible)
                       or comparar(faltante, recibo.l10n_co_ne_rete_faltante))
            vals = {'l10n_co_ne_rete_a_descontar': a_descontar, 'l10n_co_ne_rete_disponible': disponible, 'l10n_co_ne_rete_faltante': faltante}
            borrar = recibo.l10n_co_ne_rete_autorizada and (
                comparar(faltante, 0.0) <= 0 or comparar(a_descontar, recibo.l10n_co_ne_rete_autorizada_a_descontar)
                or comparar(disponible, recibo.l10n_co_ne_rete_autorizada_disponible))
            if borrar:
                vals.update(_SIN_AUTORIZACION)
            super(HrPayslipRetencion, recibo).write(vals)
            if borrar:
                recibo.message_post(body=_('Las cifras de la retención cambiaron: se borró la autorización para confirmar con retención incompleta.'))
            if cambian and comparar(faltante, 0.0) > 0:
                recibo.message_post(body=_(
                    'La retención en la fuente no cabe en este recibo. Por descontar: %(toca)s; disponible: %(disponible)s; sin practicar: %(faltante)s.',
                    toca=recibo._ne_rete_pesos(a_descontar), disponible=recibo._ne_rete_pesos(disponible), faltante=recibo._ne_rete_pesos(faltante)))

    # ── huella del cálculo (C-24) ────────────────────────────────────
    def _ne_rete_huella(self):
        """Lo que la retención del mes lee fuera del recibo: si cierra y, cuando depende del mes, las cifras de cada recibo confirmado del mes."""
        self.ensure_one()
        codigo = self._ne_rete_codigo()
        if not codigo:
            return None
        cierra = self._ne_rete_es_cierre()
        if not cierra and codigo != 'CO_BON_RETE':
            return [False, []]
        confirmados = self._ne_rete_otros_del_mes().filtered(lambda r: r.state in _CONFIRMADOS)
        return [cierra, sorted([r.id] + [round(valor, 2) for valor in self._ne_rete_cifras_de(r)] for r in confirmados)]

    # ── autorización y protección de los campos ──────────────────────
    def _ne_rete_rechazar_externa(self):
        raise UserError(_('Las cifras de la retención y los datos de su autorización los pone el sistema: no se pueden crear ni modificar a mano.'))

    @api.model_create_multi
    def create(self, vals_list):
        protegidos = _DEL_SISTEMA + (_AUTORIZACION,)
        if any(vals.get(campo) for vals in vals_list for campo in protegidos):
            self._ne_rete_rechazar_externa()
        recibos = super().create(vals_list)
        if any(recibo[campo] for recibo in recibos for campo in protegidos):          # por un valor por defecto (contexto ``default_...`` o definido por el usuario)
            self._ne_rete_rechazar_externa()
        return recibos

    def write(self, vals):
        if any(campo in vals for campo in _DEL_SISTEMA):
            self._ne_rete_rechazar_externa()
        if _AUTORIZACION not in vals:
            return super().write(vals)
        resto = dict(vals)
        marcar = bool(resto.pop(_AUTORIZACION))
        res = super().write(resto) if resto else True
        self.filtered(lambda r: r.l10n_co_ne_rete_autorizada != marcar)._ne_rete_autorizar(marcar)
        return res

    def _ne_rete_autorizar(self, marcar):
        if not self:
            return
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_manager'):
            raise UserError(_('Solo el administrador de nómina puede marcar o desmarcar «Autorizo confirmar con retención incompleta».'))
        for recibo in self:
            if recibo.state not in _ABIERTOS or (marcar and recibo.currency_id.compare_amounts(recibo.l10n_co_ne_rete_faltante, 0.0) <= 0):
                raise UserError(_(
                    '«Autorizo confirmar con retención incompleta» solo se marca en un recibo en borrador o en espera al que le quede retención sin practicar: revise «%(recibo)s».',
                    recibo=recibo.number or recibo.name))
            vals = dict(_SIN_AUTORIZACION)
            if marcar:
                vals = {
                    _AUTORIZACION: True, 'l10n_co_ne_rete_autorizada_por': self.env.user.id, 'l10n_co_ne_rete_autorizada_fecha': fields.Datetime.now(),
                    'l10n_co_ne_rete_autorizada_a_descontar': recibo.l10n_co_ne_rete_a_descontar, 'l10n_co_ne_rete_autorizada_disponible': recibo.l10n_co_ne_rete_disponible}
            super(HrPayslipRetencion, recibo).write(vals)

    # ── comprobaciones al confirmar ──────────────────────────────────
    def _ne_rete_por_revisar(self):
        return self.filtered(lambda r: r.state in _ABIERTOS and not r.credit_note)

    def _ne_validar_retencion_conjunto(self):
        """Dos recibos del mismo empleado y mes confirmados a la vez no se ven entre sí: si alguno retiene por el mes, se confirman uno por uno."""
        grupos = {}
        for recibo in self._ne_rete_por_revisar().filtered(lambda r: r._ne_rete_codigo()):
            clave = (recibo.employee_id, recibo.company_id, recibo.date_to.year, recibo.date_to.month)
            grupos[clave] = grupos.get(clave, self.browse()) | recibo
        for grupo in grupos.values():
            if len(grupo) > 1 and any(recibo._ne_rete_retiene_mes() for recibo in grupo):
                raise UserError(_(
                    'No se pueden confirmar a la vez %(recibos)s de %(empleado)s: la retención en la fuente del mes los suma. Confírmelos uno por uno y pulse «Calcular hoja» en el siguiente antes de '
                    'confirmarlo.', recibos=', '.join('«%s»' % (r.number or r.name) for r in grupo), empleado=grupo[0].employee_id.name))

    def _ne_validar_retencion_incompleta(self):
        lineas = []
        for recibo in self._ne_rete_por_revisar():
            comparar = recibo.currency_id.compare_amounts
            if comparar(recibo.l10n_co_ne_rete_faltante, 0.0) <= 0:
                continue
            if (recibo.l10n_co_ne_rete_autorizada and not comparar(recibo.l10n_co_ne_rete_a_descontar, recibo.l10n_co_ne_rete_autorizada_a_descontar)
                    and not comparar(recibo.l10n_co_ne_rete_disponible, recibo.l10n_co_ne_rete_autorizada_disponible)):
                continue
            lineas.append(_(
                '- «%(recibo)s» de %(empleado)s: por descontar %(toca)s, disponible %(disponible)s, sin practicar %(faltante)s',
                recibo=recibo.number or recibo.name, empleado=recibo.employee_id.name, toca=recibo._ne_rete_pesos(recibo.l10n_co_ne_rete_a_descontar),
                disponible=recibo._ne_rete_pesos(recibo.l10n_co_ne_rete_disponible), faltante=recibo._ne_rete_pesos(recibo.l10n_co_ne_rete_faltante)))
        if lineas:
            raise UserError(_(
                'No se puede confirmar: la retención en la fuente no cabe en el recibo.\n%(recibos)s\nPara confirmar, el administrador de nómina debe marcar en el recibo «Autorizo confirmar con '
                'retención incompleta». Lo que no se practica no se recauda solo.', recibos='\n'.join(lineas)))

    def _ne_validar_neto_no_negativo(self):
        netos = set(self.env['hr.salary.rule']._NE_NETO_POR_ESTRUCTURA.values())
        errores = []
        for recibo in self._ne_solo_colombia()._ne_rete_por_revisar():
            de_neto = recibo.line_ids.filtered(lambda l: l.code in netos)
            neto = sum(de_neto.mapped('total')) if de_neto else recibo.net_wage
            if recibo.currency_id.compare_amounts(neto, 0.0) >= 0:
                continue
            deducciones = recibo.line_ids.filtered(lambda l: l.total < 0 and _en_categorias(l.salary_rule_id.category_id, ('DEDU', 'DED')))
            detalle = '\n'.join('    %s: %s' % (l.name, recibo._ne_rete_pesos(-l.total)) for l in deducciones)
            errores.append(_(
                '- «%(recibo)s» de %(empleado)s tiene neto negativo (%(neto)s). Deducciones:\n%(detalle)s',
                recibo=recibo.number or recibo.name, empleado=recibo.employee_id.name, neto=recibo._ne_rete_pesos(neto), detalle=detalle))
        if errores:
            raise UserError(_(
                'No se puede confirmar un recibo con neto negativo.\n%(recibos)s\nAjuste las deducciones o quite la novedad que las origina, pulse «Calcular hoja» y vuelva a confirmar.',
                recibos='\n'.join(errores)))
