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
