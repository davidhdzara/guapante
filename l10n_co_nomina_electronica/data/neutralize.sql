-- Neutralización de bases copiadas (Odoo `--neutralize`; Odoo.sh la corre en staging/desarrollo).
-- Calcado de l10n_co_dian/data/neutralize.sql (Facturación electrónica nativa): una copia de producción
-- NUNCA debe transmitir a la DIAN real. Toda compañía pasa al ambiente de Habilitación (Pruebas).
-- NO se toca l10n_co_ne_certification_process: la habilitación se hace en staging.
UPDATE res_company
SET l10n_co_ne_environment = '2';
