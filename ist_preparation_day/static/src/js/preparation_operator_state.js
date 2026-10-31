import { reactive } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

// Estado compartido de identificación por PIN (Fase 1, Preparación del Día). Reactivo para que
// tanto el widget de identificación como el gate del widget de báscula (preparation_list.js) se
// actualicen solos cuando cambia el operario identificado — ambos viven en la misma sesión de
// navegador/pestaña, por eso basta un singleton de módulo en vez de un servicio registrado.
export const operatorState = reactive({
    employeeId: false,
    employeeName: false,
    loaded: false,
});

// Cada fila de la lista de pesaje monta su propio ScaleWeightField, y todas llaman
// ensureOperatorLoaded() en onWillStart — sin este caché de la promesa en vuelo, tantas filas
// pendientes como líneas dispararían el mismo RPC en paralelo antes de que la primera resuelva
// loaded=true (hallazgo de guapante_qa en la revisión de diseño de Fase 1).
let _loadingPromise = null;

export async function ensureOperatorLoaded() {
    if (!operatorState.loaded) {
        if (!_loadingPromise) {
            _loadingPromise = rpc(
                "/web/guapante/preparation_day/current_operator", {},
            ).then((result) => {
                operatorState.employeeId = result.employee_id;
                operatorState.employeeName = result.employee_name;
                operatorState.loaded = true;
            }).finally(() => {
                _loadingPromise = null;
            });
        }
        await _loadingPromise;
    }
    return operatorState;
}

export async function identifyOperator(pin) {
    const result = await rpc("/web/guapante/preparation_day/identify", { pin });
    if (result.success) {
        operatorState.employeeId = result.employee_id;
        operatorState.employeeName = result.employee_name;
        operatorState.loaded = true;
    }
    return result;
}

// Gap #2 de la Fase 1 (cerrado en este módulo): salida explícita de la identificación en esta
// estación, en vez de depender de que el siguiente operario simplemente re-identifique encima.
export async function clearOperator() {
    await rpc("/web/guapante/preparation_day/clear_operator", {});
    operatorState.employeeId = false;
    operatorState.employeeName = false;
}
