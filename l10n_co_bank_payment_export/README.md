# Colombia - Archivos Planos Bancarios

Modulo Odoo 18/19 Enterprise para la generacion de archivos de dispersion
de pagos compatibles con los portales de pago masivo de los principales
bancos colombianos. Permite exportar pagos a proveedores y nomina sin
salir de Odoo.

**Modulo tecnico:** `l10n_co_bank_payment_export`
**Version actual:** 18.0.1.1.0
**Licencia:** LGPL-3
**Repositorio:** https://github.com/davidhdzara/l10n_co_bank_payment_export

---

## Tabla de Contenidos

1. [Bancos Soportados](#bancos-soportados)
2. [Requisitos](#requisitos)
3. [Instalacion](#instalacion)
4. [Configuracion Inicial](#configuracion-inicial)
5. [Uso del Modulo](#uso-del-modulo)
6. [Arquitectura Tecnica](#arquitectura-tecnica)
7. [Especificacion de Formatos](#especificacion-de-formatos)
8. [Validaciones Implementadas](#validaciones-implementadas)
9. [Seguridad y Permisos](#seguridad-y-permisos)
10. [Tests](#tests)
11. [Extender para Nuevos Bancos](#extender-para-nuevos-bancos)
12. [Solucion de Problemas](#solucion-de-problemas)
13. [Limitaciones Conocidas](#limitaciones-conocidas)
14. [Roadmap](#roadmap)

---

## Bancos Soportados

| Banco              | Formato         | Extension | Longitud   | Estado     |
|--------------------|-----------------|-----------|------------|------------|
| Banco Davivienda   | Excel Estandar  | `.xlsx`   | 11 columnas| Disponible |
| Banco de Bogota    | ASCII ancho fijo| `.txt`    | 250 chars  | Disponible |
| Bancolombia (PAB)  | ASCII ancho fijo| `.txt`    | 264 chars  | Disponible |
| Bancolombia (SAP)  | ASCII ancho fijo| `.txt`    | 95 chars   | Disponible |

Cada banco usa un formato propio; el modulo elige el generador correcto
segun la opcion seleccionada en el wizard.

---

## Requisitos

### Software
- **Odoo:** 18 o 19 Enterprise
- **Python:** >= 3.10
- **Sistema operativo:** cualquiera soportado por Odoo

### Dependencias Python
- `openpyxl` (declarado en `external_dependencies` del manifest)
  Odoo verifica e indica si falta al instalar.

### Modulos Odoo requeridos
- `account` - modulo base de contabilidad
- `account_accountant` - contabilidad avanzada (parte de Enterprise)
- `hr_payroll` - nomina (Enterprise)
- `l10n_co` - localizacion Colombia
- `mail` - mensajeria y actividades (para auditoria)

---

## Instalacion

### 1. Obtener el codigo

```bash
git clone https://github.com/davidhdzara/l10n_co_bank_payment_export.git
cd l10n_co_bank_payment_export
git checkout 18.0   # o 19.0 segun version de Odoo
```

### 2. Copiar al directorio de addons

```bash
cp -r l10n_co_bank_payment_export /path/to/odoo/addons/
```

### 3. Instalar dependencia Python

```bash
pip install openpyxl
```

### 4. Reiniciar Odoo con actualizacion de lista

```bash
./odoo-bin -c odoo.conf -u all --stop-after-init
./odoo-bin -c odoo.conf
```

### 5. Activar desde la interfaz

`Ajustes > Aplicaciones > Buscar "Archivos Planos Bancarios" > Instalar`

---

## Configuracion Inicial

### Paso 1: Verificar codigos ACH en bancos

`Contabilidad > Configuracion > Bancos`

El modulo precarga 17 bancos colombianos con sus codigos ACH. Verifique
que los bancos que va a usar tengan el codigo correcto en el campo
**Codigo ACH Colombia**.

Tabla de codigos ACH precargados:

| Codigo | Banco              | Codigo | Banco                 |
|--------|--------------------|--------|-----------------------|
| 001    | Banco de Bogota    | 040    | Banco Agrario         |
| 002    | Banco Popular      | 051    | Davivienda / DaviPlata|
| 007    | Bancolombia        | 052    | Banco AV Villas       |
| 009    | Citibank           | 060    | Banco Helm Bank       |
| 013    | BBVA Colombia      | 062    | Banco Falabella       |
| 014    | Itau               | 063    | Banco Pichincha       |
| 019    | Scotiabank Colpatria| 507   | Nequi                 |
| 023    | Banco de Occidente | 032    | Banco Caja Social     |

### Paso 2: Configurar tipo de cuenta en proveedores

Para cada proveedor que recibira pagos:

`Contabilidad > Proveedores > [Proveedor] > Pestana "Informacion de la Empresa"`

En la seccion **Cuentas Bancarias**, en cada cuenta seleccione el campo
**Tipo de Cuenta (Colombia)**:

- `CA` - Cuenta de Ahorros (predeterminado)
- `CC` - Cuenta Corriente
- `DP` - DaviPlata
- `TP` - Tarjeta Prepago Maestro
- `DE` - Depositos Electronicos

### Paso 3: Configurar tipo de cuenta en empleados (para nomina)

`Nomina > Empleados > [Empleado] > Pestana "Informacion Privada"`

Mismo procedimiento que con proveedores.

### Paso 4: Verificar NIT/Cedula en proveedores y empleados

El campo **NIT** (VAT) debe estar configurado:

- **Empresas:** NIT con digito de verificacion sin guion (ej: `9001234561`)
- **Personas:** numero de cedula (ej: `1234567890`)

Para empleados, el VAT debe estar en la **direccion privada**
(`employee.address_home_id.vat`).

---

## Uso del Modulo

### Exportar pagos a proveedores

```
1. Ir a: Contabilidad > Proveedores > Pagos
2. Filtrar pagos en estado "Publicado"
3. Seleccionar los pagos a exportar
4. Accion > Exportar Archivo Plano Bancario
5. En el wizard:
   - Seleccionar el Banco destino
   - Revisar el "Reporte de Validacion"
     * Verde: todos listos -> generar
     * Rojo: hay errores -> cerrar, corregir, reintentar
   - Click en "Generar Archivo"
6. Descargar el archivo
7. Subir al portal del banco
```

### Exportar nomina

```
1. Ir a: Nomina > Recibos de Nomina
2. Filtrar recibos en estado "Hecho" o "Pagado"
3. Seleccionar los recibos a exportar
4. Accion > Exportar Archivo Plano Bancario
5. Continuar con mismo flujo que proveedores
```

### Consultar historial

`Contabilidad > Archivos Planos Bancarios > Historial de Exportaciones`

Desde el registro de auditoria:
- Descargar nuevamente el archivo generado
- Ver que pagos/recibos incluyo
- **Restablecer a Borrador** si el banco rechazo el archivo
- **Regenerar Archivo** despues de restablecer

---

## Arquitectura Tecnica

### Estructura de archivos

```
l10n_co_bank_payment_export/
├── __manifest__.py                  Declaracion del modulo
├── __init__.py
├── README.md                         Esta documentacion
│
├── models/
│   ├── __init__.py
│   ├── res_bank.py                   Extiende res.bank con codigo ACH
│   ├── res_partner_bank.py           Extiende res.partner.bank con tipo cuenta CO
│   ├── bank_payment_export.py        Modelo principal + Davivienda + Bogota
│   └── bancolombia_generator.py      Generadores PAB y SAP (clase aparte)
│
├── wizard/
│   ├── __init__.py
│   ├── bank_payment_export_wizard.py        Logica del wizard
│   └── bank_payment_export_wizard_views.xml Vistas del wizard
│
├── views/
│   ├── res_bank_views.xml            Campos en ficha de banco/cuenta
│   └── bank_payment_export_views.xml Form, lista, busqueda, menus
│
├── data/
│   ├── ir_sequence_data.xml          Secuencia BANCO/YYYY/MM/XXXX
│   └── res_bank_data.xml             17 bancos colombianos
│
├── security/
│   └── ir.model.access.csv           Permisos por grupo
│
├── migrations/
│   └── 18.0.1.0.0/
│       └── pre-migration.py
│
├── tests/
│   ├── __init__.py
│   ├── test_davivienda_helpers.py        Tests unitarios de helpers
│   ├── test_bank_payment_export.py       Tests integracion Davivienda
│   ├── test_bogota_generator.py          Tests integracion Bogota
│   └── test_bancolombia_generator.py     Tests integracion Bancolombia
│
├── i18n/
│   └── l10n_co_bank_payment_export.pot   Plantilla de traduccion
│
└── static/description/
    ├── icon.png                      128x128
    └── banner.png                    1200x300
```

### Modelos

#### `bank.payment.export` (modelo principal)
Registro de auditoria persistente. Se crea exclusivamente desde el wizard.
Es inmutable despues de generado (solo cancelable o reseteable a borrador).

Hereda `mail.thread` y `mail.activity.mixin` para trazabilidad completa.

#### `bank.payment.export.wizard` (TransientModel)
Punto de entrada del usuario. Ejecuta validacion previa en tiempo real,
muestra reporte HTML al usuario y crea el registro de auditoria al generar.

#### `res.bank` (extension)
Agrega el campo `l10n_co_ach_code` para el codigo ACH Colombia.

#### `res.partner.bank` (extension)
Agrega el campo `l10n_co_account_type` con valores CA/CC/DP/TP/DE.

### Patron de generacion por banco

Cada banco implementa estos metodos en `bank_payment_export.py`:

```
_generate_<banco>()        Punto de entrada: orquesta validacion + escritura
_collect_rows_<banco>()    Recolecta filas validas y errores
_row_<banco>_vendor()      Valida y construye fila para pago a proveedor
_row_<banco>_payroll()     Valida y construye fila para nomina
```

Bancolombia tiene su logica encapsulada en `bancolombia_generator.py`
(dos clases: `BancolombiaGeneratorPAB` y `BancolombiaGeneratorSAP`).

### Despachador central

```python
def _generate_file(self):
    if self.bank == 'davivienda':
        self._generate_davivienda()
    elif self.bank == 'bogota':
        self._generate_bogota()
    elif self.bank in ('bancolombia_pab', 'bancolombia_sap'):
        self._generate_bancolombia()
    self.write({'state': 'generated'})
```

---

## Especificacion de Formatos

### Davivienda - Excel (.xlsx)

Archivo Excel con una sola hoja llamada **"Hoja1"** y 11 columnas:

| Col | Campo                              | Tipo        | Obligatorio |
|-----|------------------------------------|-------------|-------------|
| A   | Tipo de Identificacion             | Numerico    | Si          |
| B   | Numero de Identificacion           | Numerico    | Si          |
| C   | Nombre                             | Alfabetico  | Si          |
| D   | Apellido                           | Alfabetico  | Si          |
| E   | Codigo del Banco                   | Numerico    | Si          |
| F   | Tipo de Producto o Servicio        | Alfanumerico| Si          |
| G   | Numero del Producto o Servicio     | Numerico    | Si          |
| H   | Valor del pago o de la recarga     | Numerico    | Si          |
| I   | Referencia                         | Numerico    | No          |
| J   | Correo Electronico                 | Alfanumerico| No          |
| K   | Descripcion o Detalle              | Alfanumerico| No          |

**Codigos de identificacion:**
`01` CC, `02` CE, `03` NIT, `04` TI, `05` Pasaporte, `13` Reg.Civil

**Tipos de producto:**
`CA` Ahorros, `CC` Corriente, `DP` DaviPlata, `TP` Prepago, `DE` Electronico

**Reglas criticas:**
- La columna G se escribe como texto para preservar ceros iniciales
- Sin caracteres especiales (n con tilde, tildes, simbolos)
- Sin filas ni columnas vacias

### Banco de Bogota - ASCII (.txt) - 250 chars/linea

Archivo plano con tres tipos de registro:

#### Registro Tipo 1 (Header) - 250 chars

| Pos     | Campo                       | Tipo | Long |
|---------|-----------------------------|------|------|
| 1       | Tipo Registro = "1"         | Num  | 1    |
| 2-9     | Fecha Dispersion (AAAAMMDD) | Num  | 8    |
| 10-33   | Ceros                       | Num  | 24   |
| 34      | Tipo Cuenta Dispersora (1/2/5)| Num | 1   |
| 35-40   | Ceros                       | Num  | 6    |
| 41-51   | Numero Cuenta Dispersora    | Num  | 11   |
| 52-91   | Nombre Empresa              | Alfa | 40   |
| 92-102  | NIT Empresa                 | Num  | 11   |
| 103-105 | Tipo Movimiento (001/002/003)| Num | 3   |
| 106-109 | Codigo Ciudad               | Num  | 4    |
| 110-117 | Fecha Elaboracion           | Num  | 8    |
| 118-120 | Codigo Oficina              | Num  | 3    |
| 121     | Tipo ID Empresa (N/L/I)     | Alfa | 1    |
| 122-250 | Espacios                    | Alfa | 129  |

#### Registro Tipo 2 (Detalle) - 250 chars

| Pos     | Campo                       | Tipo | Long |
|---------|-----------------------------|------|------|
| 1       | Tipo Registro = "2"         | Num  | 1    |
| 2       | Tipo ID (C/N/T/E/L/P)       | Alfa | 1    |
| 3-13    | Numero ID                   | Num  | 11   |
| 14-53   | Nombre Beneficiario         | Alfa | 40   |
| 54      | Cero                        | Num  | 1    |
| 55      | Tipo Cuenta (1/2/5/9)       | Num  | 1    |
| 56-72   | Numero Cuenta               | Alfa | 17   |
| 73-90   | Valor (sin punto, centavos) | Num  | 18   |
| 91      | Forma Pago = "A"            | Alfa | 1    |
| 92-94   | Ceros                       | Num  | 3    |
| 95-97   | Codigo Banco Destino        | Num  | 3    |
| 98-101  | Codigo Ciudad               | Num  | 4    |
| 102-181 | Adenda (descripcion)        | Alfa | 80   |
| 182     | Cero                        | Num  | 1    |
| 183-192 | Numero Factura              | Num  | 10   |
| 193     | Notificacion (C/E/N)        | Alfa | 1    |
| 194-241 | Espacios                    | Alfa | 48   |
| 242     | Indicador Envio Mensaje = "N"| Alfa | 1   |
| 243-250 | Espacios                    | Alfa | 8    |

#### Registro Tipo 3 (Notificaciones) - 250 chars

Opcional. Solo se incluye si pos 193 del Tipo 2 es `C` o `E`.
**No implementado en v1.1.0** (planificado v1.2).

### Bancolombia PAB - ASCII (.txt) - 264 chars/linea

Estructura completa: Tipo 1 (Control) + N Tipo 6 (Detalle).
Opcionales: Tipo 3 (Adenda Estructurada), Tipo 4 (Adenda Libre),
Tipo 5 (Pensiones), Tipo 7 (Seguridad Social).

#### Registro Tipo 1 (Control de Lote) - 264 chars

| Pos     | Campo                          | Tipo | Long |
|---------|--------------------------------|------|------|
| 1       | Tipo Registro = "1"            | Num  | 1    |
| 2-16    | NIT Entidad Originadora        | Num  | 15   |
| 17      | Aplicacion (I/M/N o blanco)    | Alfa | 1    |
| 18-32   | Filler                         | Alfa | 15   |
| 33-35   | Clase Transaccion              | Num  | 3    |
| 36-45   | Descripcion Proposito          | Alfa | 10   |
| 46-53   | Fecha Transmision (AAAAMMDD)   | Num  | 8    |
| 54-55   | Secuencia Lote (A1/A2/B1)      | Alfa | 2    |
| 56-63   | Fecha Aplicacion (AAAAMMDD)    | Num  | 8    |
| 64-69   | Numero de Registros            | Num  | 6    |
| 70-86   | Sumatoria Debitos (siempre 0)  | Num  | 17   |
| 87-103  | Sumatoria Creditos (15,2)      | Num  | 17   |
| 104-114 | Cuenta Cliente a Debitar       | Num  | 11   |
| 115     | Tipo Cuenta (S/D/C)            | Alfa | 1    |
| 116-264 | Filler                         | Alfa | 149  |

#### Registro Tipo 6 (Detalle) - 264 chars

| Pos     | Campo                          | Tipo | Long |
|---------|--------------------------------|------|------|
| 1       | Tipo Registro = "6"            | Num  | 1    |
| 2-16    | NIT Beneficiario               | Alfa | 15   |
| 17-46   | Nombre Beneficiario            | Alfa | 30   |
| 47-55   | Banco Destino (codigo ACH)     | Num  | 9    |
| 56-72   | Numero Cuenta                  | Alfa | 17   |
| 73      | Indicador Lugar Pago (espacio) | Alfa | 1    |
| 74-75   | Tipo Transaccion               | Num  | 2    |
| 76-92   | Valor (15,2)                   | Num  | 17   |
| 93-100  | Fecha Aplicacion               | Num  | 8    |
| 101-121 | Referencia                     | Alfa | 21   |
| 122     | Tipo Documento ID              | Num  | 1    |
| 123-127 | Oficina Entrega                | Alfa | 5    |
| 128-142 | Celular                        | Alfa | 15   |
| 143-222 | Email                          | Alfa | 80   |
| 223-237 | ID Autorizado                  | Alfa | 15   |
| 238-264 | Filler                         | Alfa | 27   |

**Clases de transaccion:**
- `220` Pago a Proveedores
- `225` Pago de Nomina
- `229` Pago de Pensiones
- `238` Pago a Terceros

**Tipos de transaccion (destino):**
- `27` Abono Cuenta Corriente
- `37` Abono Cuenta de Ahorros
- `52` Abono Deposito Electronico

### Bancolombia SAP - ASCII (.txt) - 95 chars/linea

Formato legacy. Estructura mas simple que PAB.

#### Registro Tipo 1 (Control) - 95 chars

Diferencias clave con PAB:
- Longitud reducida: 95 vs 264
- Fecha en formato AAMMDD (6 chars) en vez de AAAAMMDD
- NIT empresa: 10 chars (vs 15 en PAB)
- Secuencia lote: 1 char (vs 2 en PAB)

#### Registro Tipo 6 (Detalle) - 95 chars

- Numero cuenta beneficiario: numerico con ceros izq (vs alfanumerico en PAB)
- Valor: 10 chars (vs 17 en PAB)
- Sin campos email/celular/oficina/autorizado

---

## Validaciones Implementadas

### Validaciones por banco (en orden de ejecucion)

Para cada pago o recibo:

1. **Partner existe** (no nulo)
2. **Cuenta bancaria asignada** al pago
3. **Moneda COP** (todos los bancos rechazan otras monedas)
4. **NIT/Cedula configurado** en el partner
5. **Codigo ACH presente** en el banco asociado a la cuenta
6. **Numero de cuenta** no vacio
7. **Monto positivo** (> 0)

Para nomina, adicionalmente:
- **Direccion privada** del empleado configurada
- **Cuenta bancaria** asignada al empleado (no al partner)
- **VAT** en la direccion privada

### Reporte de validacion previo

El wizard ejecuta todas las validaciones **antes** de permitir generar.
Muestra un reporte HTML con:

- Numero de registros **listos para exportar**
- Numero de registros **con errores**
- Tabla detallada con cada error: que registro y que falta

El boton "Generar Archivo" se deshabilita si `ready_count == 0`.

---

## Seguridad y Permisos

### Grupos de acceso

| Grupo Odoo                       | Modelo principal    | Wizard              |
|----------------------------------|---------------------|---------------------|
| `account.group_account_manager`  | Lectura, escritura, crear, borrar | Completo |
| `account.group_account_user`     | Lectura, crear (solo wizard) | Completo |
| `hr_payroll.group_hr_payroll_user` | Lectura, crear (solo wizard) | Completo |

### Reglas adicionales

- Los registros son **multi-compania**: cada usuario ve solo los de su compania.
- El campo `company_id` es `index=True` para filtros rapidos.
- El estado **inmutable** despues de generado (solo restablecer o cancelar).
- `_sql_constraints` garantiza unicidad de `name + company_id`.

---

## Tests

### Ejecutar todos los tests

```bash
./odoo-bin -c odoo.conf --test-enable --stop-after-init -d <db> \
    -u l10n_co_bank_payment_export
```

### Ejecutar solo tests de integracion

```bash
./odoo-bin -c odoo.conf --test-tags=post_install --stop-after-init -d <db>
```

### Cobertura

| Suite                              | Tests | Verifica                              |
|------------------------------------|-------|---------------------------------------|
| `test_davivienda_helpers`          | 8     | Funciones puras (sanitize, only_digits) |
| `test_bank_payment_export`         | 11    | Flujo Davivienda + secuencia + estados |
| `test_bogota_generator`            | 6     | Longitud 250 chars + posiciones criticas |
| `test_bancolombia_generator`       | 7     | PAB 264 + SAP 95 + validaciones       |

Todos los tests usan `@tagged('post_install', '-at_install')` para
ejecutarse en una base de datos con datos demo completos.

---

## Extender para Nuevos Bancos

Agregar un nuevo banco requiere tres modificaciones:

### Paso 1: Agregar la opcion al Selection

En `models/bank_payment_export.py`:

```python
BANK_SELECTION = [
    ('davivienda',      'Banco Davivienda'),
    ('bogota',          'Banco de Bogota'),
    ('bancolombia_pab', 'Bancolombia - PAB'),
    ('bancolombia_sap', 'Bancolombia - SAP'),
    ('nuevo_banco',     'Mi Banco Nuevo'),    # <-- nuevo
]
```

En `wizard/bank_payment_export_wizard.py`, agregar la misma opcion al
campo `bank` del wizard.

### Paso 2: Implementar el generador

Agregar metodos al modelo `BankPaymentExport`:

```python
def _generate_nuevo_banco(self):
    """Genera el archivo segun el formato del nuevo banco."""
    rows, errors = self._collect_rows_nuevo_banco()
    if errors:
        raise UserError(...)
    if not rows:
        raise UserError(...)

    # Construir el archivo segun especificacion
    content = self._build_nuevo_banco_file(rows)

    self.write({
        'excel_file':     base64.b64encode(content),
        'excel_filename': 'NuevoBanco_%s.txt' % self.name.replace('/', '_'),
        'line_count':     len(rows),
    })

def _collect_rows_nuevo_banco(self):
    rows, errors = [], []
    if self.payment_source in ('vendor', 'both'):
        for pay in self.payment_ids:
            try:
                rows.append(self._row_nuevo_banco_vendor(pay))
            except ValidationError as exc:
                errors.append(exc.args[0])
    # ... mismo patron para payroll
    return rows, errors

def _row_nuevo_banco_vendor(self, payment):
    # Validar y retornar la fila
    ...

def _row_nuevo_banco_payroll(self, payslip):
    ...
```

### Paso 3: Agregar al despachador

```python
def _generate_file(self):
    self.ensure_one()
    if self.bank == 'davivienda':
        self._generate_davivienda()
    elif self.bank == 'bogota':
        self._generate_bogota()
    elif self.bank in ('bancolombia_pab', 'bancolombia_sap'):
        self._generate_bancolombia()
    elif self.bank == 'nuevo_banco':      # <-- nuevo
        self._generate_nuevo_banco()
    self.write({'state': 'generated'})
```

Y agregar al validador previo en `get_validation_report`:

```python
elif self.bank == 'nuevo_banco':
    validate_vendor  = self._row_nuevo_banco_vendor
    validate_payroll = self._row_nuevo_banco_payroll
```

### Paso 4: Agregar tests

Crear `tests/test_nuevo_banco_generator.py` con la misma estructura que
los existentes.

---

## Solucion de Problemas

### "openpyxl no esta instalado"

```bash
pip install openpyxl
```

Reiniciar Odoo.

### "El banco del proveedor no tiene Codigo ACH"

`Contabilidad > Configuracion > Bancos > [Banco]`. Llenar el campo
**Codigo ACH Colombia** segun la tabla de codigos en la seccion 4.

### "La cuenta bancaria no tiene numero de cuenta"

Editar el proveedor o empleado, en la pestana de cuentas bancarias,
verificar que el campo **Numero de Cuenta** tenga valor.

### "El pago tiene un valor de cero o negativo"

Verificar el monto del pago. Para nomina, verificar `net_wage`
del recibo.

### "Davivienda solo acepta pagos en COP"

El pago debe estar en COP (peso colombiano). Si necesita pagar en otra
moneda, ese pago debe procesarse aparte (no es soportado en esta version).

### El archivo es rechazado por el banco

1. Restablecer el registro a borrador: `Historial > [Registro] > Restablecer a Borrador`
2. Revisar los datos en Odoo
3. Click en `Regenerar Archivo`
4. Volver a subir al portal

Si persiste, revisar las longitudes con un editor que muestre el ancho
de linea (las longitudes deben ser exactas: 250 Bogota, 264 PAB, 95 SAP).

### "Ya existe una exportacion con esta referencia"

La secuencia genero un duplicado (raro). Eliminar el registro fallido
desde el historial (solo gestor de contabilidad) o ejecutar:

```sql
DELETE FROM bank_payment_export WHERE state = 'draft' AND excel_file IS NULL;
```

---

## Limitaciones Conocidas

### v1.1.0

1. **Solo moneda COP.** Pagos en USD/EUR no son soportados.
2. **Sin notificaciones email/SMS.** El Registro Tipo 3 de Banco de
   Bogota y campos de notificacion de Bancolombia no se generan
   (siempre se envia `N` = sin notificacion).
3. **Sin separacion automatica de lotes.** Si hay pagos a multiples
   bancos destino, se generan en un solo archivo.
4. **Pensiones Bancolombia (Tipo 5) no soportado.** Solo clases 220 y 225.
5. **Adendas Bancolombia (Tipo 3, 4) no generadas.**
6. **Archivos rechazados se manejan manualmente.** No hay integracion
   API con los portales de los bancos.

### Validacion en vivo

Los archivos generados se han verificado **campo por campo contra los
PDFs oficiales de los bancos**, pero **no se han probado contra los
portales reales en produccion**. Antes de uso en produccion masiva:

1. Generar un archivo de prueba con 1-2 pagos pequenos
2. Subirlo al portal del banco
3. Verificar que se procese correctamente
4. Si hay rechazos, comparar el archivo contra el ejemplo del banco

---

## Roadmap

### v1.2 (Proximo)

- [ ] Registro Tipo 3 de Banco de Bogota (notificaciones email/SMS)
- [ ] Campos email/celular para Bancolombia PAB
- [ ] Soporte de adendas opcionales Bancolombia (Tipo 3, 4)

### v1.3

- [ ] Soporte multimoneda con conversion automatica a COP
- [ ] Separacion automatica de archivos por banco destino
- [ ] Codigos BPIN para cuentas maestras SGP

### v2.0

- [ ] Integracion API directa con portales bancarios
- [ ] Webhooks para confirmacion de pagos
- [ ] Dashboard de seguimiento de pagos

---

## Autor y Soporte

**Autor:** davidhdzara
**Repositorio:** https://github.com/davidhdzara/l10n_co_bank_payment_export
**Issues:** Usar GitHub Issues para reportar problemas

Al reportar un problema, incluir:
- Version del modulo
- Version de Odoo (18 o 19)
- Banco y formato (Davivienda / Bogota / Bancolombia PAB / SAP)
- Traceback completo si hay error
- Ejemplo de archivo generado (sin datos sensibles)

---

## Licencia

LGPL-3. Ver archivo `LICENSE` en el repositorio para terminos completos.
