# Portal de Empleados — operación Fase 1

## Invitación segura desde RR. HH.

1. Un responsable de RR. HH. crea o invita al contacto mediante el mecanismo
   nativo de Odoo Portal.
2. Confirma que el usuario pertenece a **Portal** y que no tiene el grupo
   **Usuarios internos** (`base.group_user`). Este módulo no crea usuarios ni
   altera grupos.
3. En la ficha interna del empleado, sección **Invitación Portal**, vincula de
   forma explícita el usuario en `user_id`.
4. Comprueba que **Estado Portal** indique “Usuario portal”. Cada usuario debe
   estar asociado a exactamente un empleado activo de una compañía autorizada.

Las solicitudes de actualización referencian al empleado con `ondelete=restrict`.
Para conservar el historial, RR. HH. debe archivar empleados con solicitudes en
lugar de eliminarlos.

## Fase 2 — certificados laborales

Antes de emitir certificados, RR. HH. configura en la compañía un empleado
activo de esa misma compañía como responsable firmante y carga su firma gráfica.
El nombre y cargo se obtienen del empleado: no se registran manualmente. La
configuración incompleta bloquea la emisión y no deja una emisión ni adjunto
parcial. La firma gráfica no sustituye una firma electrónica certificada ni se
reutiliza el certificado DIAN.

La exposición de colillas permanece deshabilitada hasta que Nómina aporte un
evento nativo comprobable de aceptación, pago/dispersión y publicación explícita.

Las descargas se sirven únicamente desde las rutas propias del Portal, después
de validar usuario, empleado y compañía. Esta fase está operativamente limitada
a una compañía hasta que QA valide el escenario multicompañía; no se debe
habilitar ni anunciar operación multicompañía antes de ese gate.

## Handoff QA — Fase 2

**Base de integración:** `b8c5d3e` + `4b6b262`. No hacer *push*, despliegue ni
actualización en staging/producción desde este procedimiento. La actualización
indicada abajo se ejecuta únicamente en una base de QA Odoo 18 aislada y
recuperable.

### Preflight y actualización de QA

1. Confirmar que la rama/checkout contiene `4b6b262` y que `git status` está
   limpio; no incluir `__pycache__`.
2. Guardar respaldo recuperable de la base de QA y confirmar que el *addons
   path* contiene `l10n_co_portal_empleado` y sus dependencias nativas.
3. Ejecutar la actualización y pruebas en Odoo 18:

   ```bash
   odoo -d <db_pruebas> -u l10n_co_portal_empleado \
     --test-enable --test-tags /l10n_co_portal_empleado --stop-after-init
   ```

4. Conservar log completo, resultado de actualización y salida de pruebas. Un
   `ParseError`, traceback, fallo de test o advertencia de acceso es FAIL hasta
   tener evidencia reproducible y corrección revisada.

### Reconfiguración obligatoria por compañía

No existe una migración automática segura para la configuración previa de
firmante: se retiraron nombre/cargo manuales y la firma almacenada como
`ir.attachment`. Después de actualizar, un usuario nativo de RR. HH. debe
configurar **en cada compañía**:

1. Un empleado activo de esa misma compañía como responsable firmante.
2. Una imagen PNG, JPEG, GIF o WEBP de firma gráfica, válida y de máximo 2 MB.

La emisión debe bloquearse de forma controlada si falta cualquiera de esos dos
datos. La firma gráfica no es una firma electrónica certificada. No se deben
copiar configuraciones entre compañías ni restaurar adjuntos antiguos por SQL.

### Matriz QA monocompañía

- Portal con un único empleado activo vinculado: `/my/employee/certificates`
  responde 200; puede emitir y descargar sus certificados con y sin salario.
- Variante sin salario: confirmar que no contiene ni consulta salario/contrato;
  variante con salario: exige un contrato abierto único de la compañía e incluye
  salario y periodicidad del contrato en el PDF.
- Cambiar después el nombre, cargo o firma del responsable: el PDF emitido y
  descargado previamente no cambia; validar consecutivo y huella SHA-256.
- Probar configuración incompleta, firma inválida, firma mayor a 2 MB y
  responsable inactivo: emisión/configuración bloqueada con mensaje controlado.
- Como usuario Portal, comprobar 403/404 para: ID de emisión ajeno,
  `/report/pdf/l10n_co_portal_empleado.report_employee_certificate/<id>`,
  `/web/content/<attachment_id>` y
  `/web/image/res.company/<id>/l10n_co_portal_certificate_signatory_signature`.
- Comprobar que `/my/employee/payslips` responde 404: las colillas no están
  expuestas en esta entrega.

### Matriz QA multiempresa A/B

Mientras esta matriz no sea PASS, el producto sigue limitado a monocompañía.

1. Crear compañías A/B, cada una con responsable, firma, empleado y usuario
   Portal propios; asignar `company_ids` de forma explícita.
2. Con la compañía activa A, validar que solo se resuelve el empleado A y que
   sus certificados usan logo, `external_layout` y firmante A. Repetir con B.
3. Intentar rutas de descarga y emisión con IDs de la otra compañía; deben dar
   404 seguro, sin filtrar identidad, estado ni adjunto.
4. Validar que cambiar firma/configuración en A no afecta PDFs históricos ni
   documentos de B.

### Revisión visual obligatoria

Abrir PDFs con y sin salario y verificar logo, encabezado/pie nativos Odoo,
nombre, identificación cuando exista, cargo, fecha de ingreso, salario y
periodicidad solo en la variante correspondiente, firma, legibilidad y saltos
de página. Registrar evidencia visual y navegador/versión usados.

### Bloqueo explícito de colillas

No habilitar ni probar publicación/descarga de colillas como funcionalidad
Fase 2. Nómina todavía no aporta un evento nativo verificable de
aceptación + pago/dispersión + publicación explícita. No se debe inferir pago
desde `done`, `paid` u otro estado ambiguo, ni introducir un estado paralelo.
