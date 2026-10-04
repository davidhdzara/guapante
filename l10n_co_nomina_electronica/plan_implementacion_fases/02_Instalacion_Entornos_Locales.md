# Plan de Implementación: Fase 0.4 - Entornos Locales de Desarrollo

Este plan detalla la configuración de las tres instancias de Odoo necesarias para el desarrollo y pruebas de la Nómina Electrónica.

## 🛠️ Herramientas
- **Docker & Docker Compose:** Para garantizar aislamiento y repetibilidad.
- **PostgreSQL 17:** Como motor de base de datos único para las tres instancias (usando prefijos de BD).
- **Nginx (Opcional):** Para manejo de nombres de dominio locales.

## 🏗️ Arquitectura de Puertos
| Instancia | Puerto Host | Directorio de Código |
|-----------|-------------|----------------------|
| Odoo 18 Enterprise | 8018 | `/odoo/v18_ent` |
| Odoo 19 Enterprise | 8019 | `/odoo/v19_ent` |
| Odoo Community (Latest) | 8020 | `/odoo/v19_comm` |

## 🚀 Pasos de Ejecución
1. **Identificación de Fuentes:** Localizar o clonar los repositorios `odoo` y `enterprise`.
2. **Creación de `docker-compose.yml`:** Configurar los servicios para las 3 versiones.
3. **Mapeo de Addons:** 
   - El módulo `insotech_v18_nom_electronica` se mapeará como volumen en las tres instancias para desarrollo simultáneo (con adaptaciones por versión).
4. **Validación:**
   - Crear una base de datos limpia en cada versión.
   - Instalar el módulo `hr_payroll` (en Enterprise) para iniciar el mapeo de campos.

## ⚠️ Bloqueadores Actuales
- Acceso a los repositorios de Odoo Enterprise (se requiere confirmación del usuario sobre la ubicación del código).
