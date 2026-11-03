/** @odoo-module **/

// Buscadores de Nivel 1 y Nivel 2 (E6, David/Tech Lead, 2026-11-02) —
// funciones puras compartidas, sin estado, para poder probarlas sin
// montar ningún componente (aunque hoy no hay tests de cliente acá por
// pedido explícito de Tech Lead: la lógica queda aislada por si se
// agregan después).

// Normaliza para comparar sin distinguir mayúsculas ni acentos:
// "Pérez" y "PEREZ" deben encontrarse entre sí. NFD separa cada letra
// acentuada en (letra base + marca diacrítica combinante); \p{M}
// (categoría Unicode "Mark", flag u) bota solo esas marcas, dejando
// la letra base intacta.
//   normalizeSearchText("Pérez")   -> "perez"
//   normalizeSearchText("  Óscar") -> "oscar"
//   normalizeSearchText("ABC")     -> "abc"
export function normalizeSearchText(text) {
    return (text || "")
        .normalize("NFD")
        .replace(/\p{M}/gu, "")
        .trim()
        .toLowerCase();
}

// Regla de Nivel 2 (Caja # vs. cliente), David vía Tech Lead:
//   - Empieza con "#" seguido de dígitos -> coincidencia EXACTA de
//     caja (nunca substring): "#8" trae la Caja #8, nunca la #18.
//   - Solo dígitos, sin "#" -> caja EXACTA (daily_sequence == número)
//     O cliente que CONTENGA ese texto (un cliente puede llamarse o
//     tener un NIT con números).
//   - Cualquier otro texto -> solo cliente (normalizado, substring).
//   matchesLineSearch(8,  "Pérez", "#8")  -> true  (caja exacta 8)
//   matchesLineSearch(18, "Pérez", "#8")  -> false (18 != 8, "#" exige exacto)
//   matchesLineSearch(8,  "Pérez", "8")   -> true  (caja exacta, sin "#")
//   matchesLineSearch(18, "Pérez", "8")   -> false (18 != 8, y "8" no está en "Pérez")
//   matchesLineSearch(3,  "Cliente 8 SAS", "8") -> true (substring en el cliente)
//   matchesLineSearch(1,  "Pérez", "perez") -> true (cliente, normalizado)
//   matchesLineSearch(8,  "Pérez", "#")   -> true  (sin dígitos aún —
//                                            no filtra mientras se teclea)
export function matchesLineSearch(dailySequence, customerName, rawSearchText) {
    const search = rawSearchText.trim();
    if (!search) {
        return true;
    }
    if (search.startsWith("#")) {
        const digits = search.slice(1).trim();
        // Tech Lead, 2026-11-02: "#" solo (sin dígitos todavía, el
        // usuario sigue tecleando) no debe vaciar la lista — no
        // filtra hasta que haya al menos un dígito.
        return digits === "" || String(dailySequence) === digits;
    }
    const normalizedSearch = normalizeSearchText(search);
    if (/^\d+$/.test(search) && String(dailySequence) === search) {
        return true;
    }
    return normalizeSearchText(customerName).includes(normalizedSearch);
}
