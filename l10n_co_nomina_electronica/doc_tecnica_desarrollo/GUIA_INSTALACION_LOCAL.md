# Guía de Instalación Manual: Odoo v18 & v19 (Multi-Instancia)

Esta guía detalla cómo instalar y configurar tres instancias de Odoo en el mismo servidor local de forma segura.

## 1. Usuario de Sistema y Base de Datos
Se recomienda crear un usuario de PostgreSQL dedicado (opcional si usas tu usuario personal):
```bash
sudo -u postgres createuser -s $USER
```

## 2. Preparación de Entornos (Virtualenv)
Es vital aislar las dependencias.

### Odoo v18
```bash
python3 -m venv ~/venv_odoo18
source ~/venv_odoo18/bin/activate
pip install --upgrade pip
# Clonar y entrar a la carpeta de odoo 18
pip install -r requirements.txt
deactivate
```

### Odoo v19
```bash
python3 -m venv ~/venv_odoo19
source ~/venv_odoo19/bin/activate
pip install --upgrade pip
# Clonar y entrar a la carpeta de odoo 19 (master)
pip install -r requirements.txt
deactivate
```

## 3. Archivos de Configuración (.conf)
Crea una carpeta `configs` y genera los archivos con puertos distintos para evitar el error "Address already in use".

### `odoo_v18.conf`
```ini
[options]
admin_passwd = admin
db_host = False
db_port = False
db_user = your_user
db_password = False
addons_path = /ruta/odoo18/addons,/ruta/enterprise18,/home/david/insotech/odoo-projects/insotech/insotech_Odoo_v18/insotech_v18_nom_electronica
http_port = 8018
longpolling_port = 8118
```

### `odoo_v19.conf`
```ini
[options]
...
http_port = 8019
longpolling_port = 8119
```

## 4. Ejecución
Para arrancar cada versión:
```bash
# V18
~/venv_odoo18/bin/python3 /ruta/odoo18/odoo-bin -c configs/odoo_v18.conf

# V19
~/venv_odoo19/bin/python3 /ruta/odoo19/odoo-bin -c configs/odoo_v19.conf
```

## 5. Tips Pro (InSoTech)
- **WKHTMLTOPDF:** Instala la versión 0.12.6-1 para Ubuntu 24.04 para que los reportes PDF de nómina salgan perfectos.
- **Log level:** Durante el desarrollo de nómina, usa `log_level = debug_rpc` para ver exactamente qué JSON se envía a la DIAN.
