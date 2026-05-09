# Resolución de Inconsistencias por Timeout DIAN (Factura Electrónica)

## Contexto
Facturas (ej. FE-365) que en Odoo quedan en estado pendiente o "colgadas", sin CUFE ni estado de "Aceptada", pero que en la plataforma de la DIAN sí figuran como recibidas y aceptadas. Esto ocurre cuando Odoo envía la factura, la DIAN la procesa, pero hay una interrupción o timeout al recibir el acuse de recibo (response de la API).

## Restricciones
- **NO REENVIAR:** La DIAN rechazaría un reintento por documento duplicado (regla de oro del consecutivo único).

## Solución Aplicada (Odoo 18 / insotech_l10n_co_advanced)
Es posible normalizar la base de datos inyectando manualmente los metadatos suministrados por la representación gráfica que tiene el cliente sin disparar los métodos de re-envío:

1. Modificar a través de ORM mediante shell interactiva (`odoo-bin shell`) los campos críticos de `account.move`:
   - `insotech_dian_status`: Pasar a `'accepted'`
   - `l10n_co_dian_state`: Pasar a `'invoice_accepted'`
   - `l10n_co_edi_cufe_cude_ref`: Asignar el CUFE de 96 caracteres

2. **Habilitar pestaña DIAN visualmente:** Para que la pestaña "DIAN" aparezca en la factura, Odoo exige que exista al menos un registro en `l10n_co_dian.document`. En casos de rollback por timeout, este registro no existe, por lo que debe inyectarse manualmente:
   ```python
   env['l10n_co_dian.document'].create({
       'move_id': invoice.id,
       'state': 'invoice_accepted',
       'identifier': 'CUFE_AQUI',
       'message_json': {'status': 'Aceptado (Sincronización Manual por Timeout)'},
       'datetime': invoice.l10n_co_dian_post_time or fields.Datetime.now()
   })
   ```

## Reglas de Oro Comprobadas
- **Escritura sobre registros Posted:** Aunque el registro contable (`account.move`) esté en estado `posted`, los campos personalizados y de la integración electrónica (`l10n_co_...`) generalmente no tienen restricciones restrictivas de solo-lectura que impidan su inyección por el ORM.
- **Pestaña DIAN invisible:** Si cambias los estados y la pestaña no aparece, verifica que exista un `l10n_co_dian_document_ids` asociado. Sin este "acuse de recibo" histórico, la pestaña permanece oculta (`invisible="not l10n_co_dian_document_ids"`).
