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

## Fase 2 — colillas y certificados

Antes de publicar colillas, RR. HH. configura en la compañía la política
**Publicación de colillas en Portal**. El valor predeterminado y seguro es
**Solo aceptadas por DIAN**; la alternativa **Finalizadas** solo publica estados
`done` o `paid`.

Para emitir certificados, RR. HH. configura, en la misma compañía del empleado,
el nombre, cargo y firma del firmante. Esos tres datos no son obligatorios para
instalar el módulo, pero su ausencia bloquea la emisión y no deja una emisión ni
adjunto parcial. No se reutilizan certificados ni firma DIAN.

Las descargas se sirven únicamente desde las rutas propias del Portal, después
de validar usuario, empleado y compañía. Esta fase está operativamente limitada
a una compañía hasta que QA valide el escenario multicompañía; no se debe
habilitar ni anunciar operación multicompañía antes de ese gate.
