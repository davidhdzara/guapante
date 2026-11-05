/** @odoo-module **/

// Formateador de duración compartido entre el cronómetro de Nivel 2
// (preparation_picking_level2_display.js) y los contadores L1 del pie
// de tarjeta de Nivel 1 (preparation_picking_level1_display.js) —
// función pura, sin estado, mismo criterio que
// preparation_picking_search_utils.js.
//
// mm:ss por debajo de 1 hora, h:mm:ss desde ahí (Tech Lead,
// 2026-11-04). Negativos y no-números se tratan como 0 — un contador
// de tiempo nunca debe mostrar texto roto ni un signo negativo, aun si
// quien llama pasó un valor inválido.
//   formatDuration(0)      -> "00:00"
//   formatDuration(59)     -> "00:59"
//   formatDuration(60)     -> "01:00"
//   formatDuration(3599)   -> "59:59"
//   formatDuration(3600)   -> "1:00:00"
//   formatDuration(3661)   -> "1:01:01"
//   formatDuration(-5)     -> "00:00"
export function formatDuration(totalSeconds) {
    const safeSeconds = Number.isFinite(totalSeconds) && totalSeconds > 0
        ? Math.floor(totalSeconds) : 0;
    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const seconds = safeSeconds % 60;
    const pad2 = (n) => String(n).padStart(2, "0");
    if (hours > 0) {
        return `${hours}:${pad2(minutes)}:${pad2(seconds)}`;
    }
    return `${pad2(minutes)}:${pad2(seconds)}`;
}
