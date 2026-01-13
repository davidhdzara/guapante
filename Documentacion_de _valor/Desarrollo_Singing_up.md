Informe Técnico Integral: Arquitectura y Desarrollo de Módulos Web Personalizados en Odoo 18 Enterprise sobre Infraestructura Odoo.sh1. Introducción a la Arquitectura de Desarrollo en Odoo 181.1 Evolución del Framework y Paradigmas de DiseñoEl ecosistema de Odoo ha experimentado una transformación significativa en su versión 18, consolidándose como una plataforma robusta para el desarrollo rápido de aplicaciones (RAD) empresariales. Si bien la plataforma ofrece herramientas de "bajo código" como Odoo Studio, la implementación de lógica de negocio específica —como la solicitada en este proyecto para la gestión dual de identidades (Persona Natural vs. Compañía) y la captura de documentos de identidad sin restricciones fiscales estándar— exige un enfoque de desarrollo tradicional ("code-first"). Este enfoque permite un control granular sobre el ciclo de vida de los datos, la seguridad de las transacciones y la experiencia del usuario final (UX) en el portal web.1La arquitectura subyacente de Odoo opera sobre un patrón Modelo-Vista-Controlador (MVC) modificado. En el contexto de Odoo 18 sobre Odoo.sh, esta arquitectura se distribuye de manera que el Modelo (definido en Python) gestiona la persistencia y las reglas de negocio en PostgreSQL; la Vista (definida en XML y QWeb) se encarga de la presentación y la interacción del usuario en el navegador; y el Controlador (Python) actúa como el orquestador que gestiona las solicitudes HTTP, la autenticación y el enrutamiento.3 Comprender esta tríada es fundamental para abordar el requerimiento de un formulario de registro público, ya que implica exponer de manera segura la lógica interna del ERP a usuarios no autenticados en la web abierta.1.2 El Entorno Odoo.sh: Implicaciones para el Ciclo de Vida del DesarrolloEl despliegue en Odoo.sh, la plataforma de Plataforma como Servicio (PaaS) oficial de Odoo, impone una disciplina estricta en la gestión del código fuente. A diferencia de las instalaciones locales (on-premise) donde los desarrolladores pueden tener acceso directo al sistema de archivos, Odoo.sh se basa en una integración continua con GitHub. Esto significa que cualquier modificación, desde la adición de un campo en la base de datos hasta un cambio cosmético en el formulario web, debe pasar por un ciclo de commit, push y build.El desarrollo de módulos en Odoo.sh requiere una estructura de directorios precisa. El código personalizado no debe mezclarse con el código núcleo de Odoo (enterprise o community) para garantizar la mantenibilidad y la capacidad de actualización. La convención establece que los módulos personalizados deben residir en un directorio específico, comúnmente denominado src/user, asegurando que las actualizaciones automáticas del núcleo de Odoo no sobrescriban la lógica personalizada.5 Este aislamiento es crítico para la estabilidad del proyecto a largo plazo, especialmente cuando se trata de componentes sensibles como el registro de contactos y la gestión de identidades.2. Análisis y Modelado de Datos: Extendiendo el Núcleo de Contactos (res.partner)2.1 La Dicotomía de Entidades: Personas vs. CompañíasUno de los requisitos centrales de esta investigación es la capacidad de distinguir y almacenar si el registrante es una "Persona Natural" o una "Compañía" mediante una interfaz de selección específica (radio buttons). En el núcleo de Odoo, el modelo res.partner es la entidad unificada que almacena proveedores, clientes, empleados y empresas.Históricamente, y mantenido en la versión 18, Odoo gestiona esta distinción a través de un campo técnico llamado is_company (booleano) y un campo funcional más complejo llamado company_type. El campo company_type es un campo de selección (Selection) con dos valores codificados de forma rígida: 'person' y 'company'.7Campo en res.partnerTipo de DatoValores PosiblesFunción Arquitectónicais_companyBooleanoTrue / FalseDetermina si la entidad puede tener contactos hijos y cómo se gestionan los impuestos.company_typeSelection'person', 'company'Campo de interfaz que sincroniza con is_company. Es el objetivo principal para el formulario web.La implicación técnica de este diseño es que, aunque el usuario solicite "radio buttons" en la interfaz web, en la base de datos no estamos creando una estructura nueva, sino mapeando una entrada de usuario a un campo existente del estándar. La incorrecta manipulación de este campo puede llevar a inconsistencias, como personas que aparecen como empresas en los informes contables o viceversa.92.2 Estrategia para el Documento de Identidad: vat vs. Campo PersonalizadoEl requisito de "almacenar el documento de identidad" presenta un desafío técnico significativo en Odoo estándar. Odoo utiliza el campo nativo vat para almacenar el Número de Identificación Fiscal (NIF, CIF, RUT, NIT, etc.). Sin embargo, el campo vat está sujeto a validaciones estrictas y automáticas que dependen del país seleccionado.El análisis de la documentación y los foros técnicos revela que utilizar el campo vat para un formulario de registro público de propósito general es arriesgado.10 Si un usuario introduce un número de documento personal (como una Cédula de Ciudadanía o DNI) que no cumple con el algoritmo de validación fiscal (VIES en Europa, o algoritmos locales en Latinoamérica), Odoo lanzará una excepción de tipo ValidationError. En un contexto de backend, esto es deseable; en un formulario web público, esto resulta en una experiencia de usuario frustrante y una tasa de abandono alta, ya que el usuario recibe un error técnico incomprensible.12Por consiguiente, la solución arquitectónica recomendada y detallada en este informe es la creación de un nuevo campo personalizado, denominado técnicamente x_identity_document (o identification_document en el código del módulo). Este campo actuará como un contenedor de texto libre o con validaciones ligeras, separado de las restricciones fiscales del campo vat. Esto permite capturar el dato fidedigno del usuario sin bloquear el proceso de registro por reglas contables estrictas que pueden ser procesadas posteriormente por un administrador.2.3 Implementación del Modelo en PythonLa implementación técnica requiere la creación de un archivo Python dentro de la estructura del módulo que herede de la clase base. Utilizando la API de Odoo 18, definimos la clase para extender res.partner. Es imperativo utilizar _inherit para asegurar que todas las funcionalidades existentes (CRM, Ventas, Contabilidad) sigan operando sobre este modelo extendido sin interrupciones.1El código debe incluir no solo la definición del campo, sino también índices de base de datos (index=True) para optimizar futuras búsquedas, dado que el documento de identidad es un criterio de búsqueda frecuente. Además, es una práctica recomendada a nivel de ingeniería de software añadir restricciones SQL (_sql_constraints) para garantizar la unicidad del documento de identidad a nivel de base de datos, proporcionando una capa de seguridad de datos que persiste incluso si la validación del formulario web falla o es eludida.153. Ingeniería de la Interfaz de Usuario: QWeb y Diseño de Formularios3.1 El Motor de Plantillas QWeb y la Integración BootstrapLa capa de presentación en el sitio web de Odoo 18 se construye utilizando QWeb, un motor de plantillas basado en XML que se compila a HTML5. A diferencia de las vistas de backend (Form, Tree, Kanban) que son declarativas y abstractas, las vistas de sitio web requieren una construcción explícita del DOM (Document Object Model). Odoo 18 integra Bootstrap 5 como su framework CSS predeterminado, lo que facilita la creación de diseños responsivos y estéticamente coherentes.16Para el formulario de registro, la estructura debe heredar de la plantilla maestra del sitio web (website.layout). Esto es crucial para mantener la consistencia de la marca, asegurando que el encabezado, el pie de página, los menús de navegación y los scripts de análisis (como Google Analytics o el chat en vivo de Odoo) estén presentes en la página de registro. La directiva <t t-call="website.layout"> actúa como el envoltorio que inyecta nuestro formulario personalizado dentro del "chrome" del sitio web.183.2 Implementación Técnica de Radio Buttons para company_typeLa solicitud del usuario especifica el uso de "2 radio buttons" para la selección del tipo de entidad. Esta es una decisión de diseño de interfaz que debe traducirse cuidadosamente al backend. En HTML, los botones de radio funcionan como un grupo lógico cuando comparten el mismo atributo name.Para conectar esto con Odoo, asignaremos el atributo name="company_type" a ambos inputs de radio. Los valores (value) asignados a estos inputs deben corresponder exactamente a las claves internas del campo de selección de Odoo: 'person' y 'company'. De esta manera, cuando el controlador reciba la solicitud POST, obtendrá un único valor de cadena que puede pasarse directamente al ORM sin necesidad de lógica de transformación compleja.8El código QWeb debe estructurarse para maximizar la accesibilidad y la usabilidad. Esto implica el uso de etiquetas <label> correctamente vinculadas a los inputs mediante el atributo for, permitiendo que los usuarios hagan clic en el texto "Persona Natural" para seleccionar la opción, no solo en el pequeño círculo del radio button.3.3 Gestión de Seguridad en el Frontend: Tokens CSRFUna vulnerabilidad crítica en los formularios web es la Falsificación de Solicitudes en Sitios Cruzados (CSRF). Odoo 18 implementa una defensa robusta contra esto, pero requiere que el desarrollador incluya explícitamente el token en sus formularios personalizados. Si se omite este token, el controlador de Odoo rechazará la solicitud entrante por razones de seguridad antes de que se ejecute cualquier línea de código personalizado.16El ciclo de vida de una solicitud segura es el siguiente: cuando el usuario carga el formulario (método GET), Odoo genera un token criptográfico único para esa sesión y lo inyecta en el campo oculto <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>. Cuando el usuario envía el formulario (método POST), este token viaja de regreso al servidor. El framework compara el token recibido con el esperado para la sesión; si no coinciden, la conexión se termina. Omitir este paso es el error más común en el desarrollo de módulos web para Odoo.204. Lógica de Negocio y Controladores: El Puente entre Web y Datos4.1 Enrutamiento HTTP y Manejo de SolicitudesEl Controlador (Controller) es el componente que define los puntos finales (endpoints) de la URL. En Odoo, esto se gestiona mediante la clase http.Controller y el decorador @http.route. Para este proyecto, necesitamos definir dos rutas distintas pero interconectadas:Ruta de Renderizado (GET): Una URL pública (ej. /registro-contacto) que sirva la plantilla XML con el formulario vacío.Ruta de Procesamiento (POST): Una URL (ej. /registro/submit) que reciba los datos, los procese y devuelva una respuesta (página de éxito o error).Es imperativo configurar el parámetro auth='public' en estas rutas. Odoo tiene un sistema de autenticación estricto; si el parámetro se establece en auth='user' (el valor predeterminado para muchas operaciones internas), un visitante anónimo sería redirigido inmediatamente a la página de inicio de sesión, haciendo inaccesible el formulario de registro.14.2 Elevación de Privilegios: El Uso Correcto de sudo()Aquí nos encontramos con una paradoja de seguridad: queremos que un usuario público (anónimo) cree un registro en la base de datos, pero por defecto, los usuarios anónimos no tienen (y no deberían tener) permisos de escritura en el modelo res.partner, ya que esto contiene datos sensibles de todos los clientes y proveedores.La solución arquitectónica proporcionada por Odoo es el método sudo(). Este método permite ejecutar un conjunto específico de comandos con los privilegios del "Superusuario" (administrador del sistema), ignorando las reglas de acceso estándar (ACLs) y las reglas de registro.Análisis de Riesgo y Mitigación: El uso de sudo() debe ser quirúrgico. No se debe aplicar a todo el controlador, sino estrictamente a la operación de creación del registro (create()). Al encapsular el uso de sudo() dentro de una función específica que recibe datos ya sanitizados del formulario, limitamos la superficie de ataque. El controlador actúa como un guardián: valida que los datos sean coherentes (por ejemplo, que el email tenga formato de email, que el nombre no esté vacío) y solo entonces invoca el poder del superusuario para persistir el dato.164.3 Procesamiento de Datos del FormularioEl controlador recibe los datos del formulario en un diccionario (comúnmente llamado kw o post). La extracción de datos debe ser defensiva. Por ejemplo, al extraer el valor de los radio buttons (company_type), el sistema debe estar preparado para manejar casos donde el dato no llegue (aunque el frontend lo marque como requerido, un atacante podría manipular la petición).El mapeo de datos es directo:name (Frontend) -> name (Modelo)identification_document (Frontend) -> identification_document (Modelo Personalizado)company_type (Frontend/Radio) -> company_type (Modelo/Selection)email (Frontend) -> email (Modelo)Una vez construido el diccionario de valores, se pasa al método create() del modelo. Es fundamental envolver esta operación en un bloque try...except para capturar errores de integridad de base de datos (como un documento de identidad duplicado debido a la restricción SQL que definimos anteriormente) y devolver un mensaje amigable al usuario en lugar de un trazo de error técnico (stack trace).15. Implementación en Odoo.sh: Despliegue y Ciclo de Vida5.1 Estructura del Módulo y ManifiestoEl éxito del despliegue en Odoo.sh depende de la corrección del archivo __manifest__.py. Este archivo es el DNI del módulo. Para nuestra funcionalidad, debemos declarar explícitamente las dependencias:'base': El núcleo del sistema.'website': Necesario para heredar las plantillas web y usar el enrutamiento web.'contacts': Necesario para interactuar correctamente con res.partner y sus vistas.Si olvidamos declarar website como dependencia, Odoo podría intentar cargar nuestro módulo antes que el módulo de sitio web, causando errores de referencia en las plantillas XML (ej. External ID not found). Asimismo, el manifiesto debe listar todos los archivos XML (vistas, plantillas) en la sección 'data'. Odoo solo carga en la base de datos los archivos explícitamente listados aquí.35.2 Flujo de Trabajo Git y CI/CDOdoo.sh integra un pipeline de Integración Continua (CI) y Despliegue Continuo (CD). El flujo de trabajo recomendado para incorporar este nuevo módulo es:Desarrollo Local: Escribir el código en la máquina local dentro de la carpeta src/user.Commit y Push: Enviar los cambios a una rama de desarrollo (staging) en el repositorio de GitHub vinculado al proyecto Odoo.sh.Build Automático: Odoo.sh detecta el push y dispara una nueva construcción. Esto implica reiniciar el servicio Odoo y actualizar la lista de módulos disponibles.Instalación/Actualización: Una vez el build es exitoso (indicado en verde en la interfaz de Odoo.sh), el administrador debe ingresar a la base de datos, actualizar la lista de aplicaciones y hacer clic en "Instalar" o "Actualizar" en el módulo personalizado.Es vital entender que Odoo no "lee" los archivos Python en caliente. Cualquier cambio en la lógica de Python (Controlador o Modelo) requiere un reinicio del servicio (que Odoo.sh maneja automáticamente tras un commit). Los cambios en XML (Vistas), sin embargo, requieren una actualización del módulo (-u module_name) para que se vuelvan a cargar en la base de datos de vistas de Odoo.56. Guía de Implementación Paso a PasoA continuación, se detalla el código fuente necesario para construir el módulo, integrando todos los conceptos analizados previamente.6.1 Estructura de Directoriosmy_website_register/├── init.py├── manifest.py├── controllers/│   ├── init.py│   └── main.py├── models/│   ├── init.py│   └── res_partner.py└── views/└── website_form_template.xml6.2 El Manifiesto (__manifest__.py)Python{
    'name': 'Registro Web de Contactos',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Formulario de registro con ID y tipo de compañía',
    'depends': ['base', 'website', 'contacts'],
    'data':,
    'installable': True,
    'license': 'LGPL-3',
}
6.3 El Modelo (models/res_partner.py)Pythonfrom odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Campo personalizado para evitar conflictos con validaciones de VAT
    identification_document = fields.Char(
        string='Documento de Identidad',
        index=True,
        help='Número de documento de identidad del contacto.'
    )

    _sql_constraints = [
        ('identification_document_uniq', 'unique(identification_document)', 
         '¡Este documento de identidad ya está registrado!')
    ]
6.4 El Controlador (controllers/main.py)Pythonfrom odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class WebsiteRegistration(http.Controller):

    @http.route('/registro-contacto', type='http', auth='public', website=True)
    def registration_form(self, **kw):
        return request.render("my_website_register.custom_contact_registration_form", {})

    @http.route('/registro/submit', type='http', auth='public', methods=, website=True, csrf=True)
    def registration_submit(self, **post):
        # Extracción y limpieza básica
        vals = {
            'name': post.get('name'),
            'identification_document': post.get('identification_document'),
            'company_type': post.get('company_type'), # Recibe 'person' o 'company'
            'email': post.get('email'),
        }

        # Validación mínima
        if not vals['name'] or not vals['identification_document']:
            return "Error: Campos obligatorios faltantes."

        try:
            # sudo() es crucial aquí para usuarios anónimos
            new_partner = request.env['res.partner'].sudo().create(vals)
            _logger.info(f"Contacto creado: {new_partner.name} (ID: {new_partner.id})")
            return request.render("my_website_register.registration_success", {})
        except Exception as e:
            _logger.error(f"Error en registro web: {str(e)}")
            return "Ocurrió un error al procesar su solicitud."
6.5 La Vista (views/website_form_template.xml)XML<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="custom_contact_registration_form" name="Formulario de Registro">
        <t t-call="website.layout">
            <div class="container py-5">
                <div class="row justify-content-center">
                    <div class="col-lg-8">
                        <form action="/registro/submit" method="post">
                            <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>

                            <div class="mb-3">
                                <label class="form-label">Nombre</label>
                                <input type="text" class="form-control" name="name" required="required"/>
                            </div>

                            <div class="mb-3">
                                <label class="form-label">Documento de Identidad</label>
                                <input type="text" class="form-control" name="identification_document" required="required"/>
                            </div>

                            <div class="mb-3">
                                <label class="form-label d-block">Tipo de Entidad</label>
                                <div class="form-check form-check-inline">
                                    <input class="form-check-input" type="radio" name="company_type" id="radioPerson" value="person" checked="checked"/>
                                    <label class="form-check-label" for="radioPerson">Persona Natural</label>
                                </div>
                                <div class="form-check form-check-inline">
                                    <input class="form-check-input" type="radio" name="company_type" id="radioCompany" value="company"/>
                                    <label class="form-check-label" for="radioCompany">Compañía</label>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Email</label>
                                <input type="email" class="form-control" name="email" required="required"/>
                            </div>

                            <button type="submit" class="btn btn-primary">Registrar</button>
                        </form>
                    </div>
                </div>
            </div>
        </t>
    </template>

    <template id="registration_success" name="Registro Exitoso">
        <t t-call="website.layout">
            <div class="container py-5 text-center">
                <div class="alert alert-success">Registro completado con éxito.</div>
            </div>
        </t>
    </template>
</odoo>
7. Conclusión y Recomendaciones FinalesLa implementación de formularios personalizados en Odoo 18 bajo la infraestructura de Odoo.sh es un ejercicio que valida la flexibilidad del framework, permitiendo trascender las limitaciones de las herramientas "no-code" para satisfacer requisitos de negocio específicos.El análisis realizado confirma que el uso de un campo personalizado (identification_document) es superior al uso del campo vat para propósitos de registro general, evitando conflictos de validación fiscal. Asimismo, la implementación de la lógica de radio buttons para company_type demuestra cómo una decisión de interfaz de usuario puede mapearse directamente a estructuras de datos backend existentes sin necesidad de crear modelos redundantes.Se recomienda encarecidamente a los desarrolladores seguir las prácticas de seguridad descritas, específicamente la inclusión de tokens CSRF y el uso restrictivo de sudo(), para garantizar que la apertura del ERP a la web pública no comprometa la integridad de los datos empresariales. El cumplimiento de la estructura de directorios y el flujo de Git en Odoo.sh asegurará además que esta solución sea sostenible y escalable en futuras versiones de Odoo.