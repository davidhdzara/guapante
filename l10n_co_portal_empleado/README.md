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
