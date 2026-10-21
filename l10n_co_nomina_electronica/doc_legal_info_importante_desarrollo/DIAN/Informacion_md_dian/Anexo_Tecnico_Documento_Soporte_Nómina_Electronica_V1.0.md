## Página 1

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 1 de 269 
 
Dirección de Impuestos y Aduanas Nacionales 
 
 
 
 
 
 
 
 
 
Anexo Técnico Documento Soporte de Pago de Nómina 
Electrónica 
 
 
 
 
 
 
 
 
Versión 1.0 

---

## Página 2

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 2 de 269 
 
Contenido 
1. Introducción. ............................................................................................................................................. 6 
1.1. Calidad de la información: las Validaciones. ....................................................................................... 7 
1.1.1. Redondeos. ................................................................................................................................... 7 
1.1.2. Identificador de los documentos electrónicos. ............................................................................ 8 
1.1.3. Valores Negativos. ........................................................................................................................ 9 
2. Convenciones utilizadas en las tablas. ...................................................................................................... 9 
2.1. Columnas de las tablas de definición. ................................................................................................. 9 
2.2. Tipos de campos de los archivos XML. ..............................................................................................10 
2.3. Tamaños de los elementos. ...............................................................................................................11 
2.4. Convenciones utilizadas en las Tablas de Reglas de Validación. .......................................................13 
3. Formato para la generación de los Documentos Electrónicos. ............................................................... 14 
3.1. Documento Soporte de Pago de Nómina Electrónica: NominaIndividual. .......................................14 
3.2. Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica: 
NominaIndividualDeAjuste. ......................................................................................................................50 
3.3. Estándar del nombre del documento electrónico Documento Soporte de Pago de Nómina 
Electrónica XML. .......................................................................................................................................96 
3.4. Estándar del nombre del documento electrónico Nota de Ajuste de Documento Soporte de Pago 
de Nómina Electrónica XML. ....................................................................................................................96 
3.5. Guía del nombre del archivo que contiene uno o más documentos electrónicos y que será 
entregado a la DIAN mediante un web service de recepción. .................................................................97 
3.6. firma digital del documento: ds:Signature. .......................................................................................99 
3.7. Respuesta DIAN con validaciones de documentos Nomina: ApplicationResponse. .......................107 
3.7.1. Garantía de que el evento será registrado en el documento correcto. ...................................107 
3.7.2. Relacionamientos mutuos entre los eventos. ..........................................................................108 
3.7.3. Detalles de cada evento. ..........................................................................................................109 
4. Inconvenientes tecnológicos. ................................................................................................................ 119 
4.1. Por parte del Sujeto Obligado. ........................................................................................................119 
4.2. Por parte de la DIAN. .......................................................................................................................119 
5. Tablas de Contenidos de Elementos y de Atributos. ............................................................................. 119 
5.1. Códigos Relacionados con Documentos. ........................................................................................120 
5.1.1. Ambiente de Destino del Documento: Ambiente. ...................................................................120 
5.1.2. Algoritmo: EncripCUNE. ............................................................................................................120 
5.2. Códigos para identificación fiscal. ...................................................................................................120 

---

## Página 3

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 3 de 269 
 
5.2.1. Documento de identificación (Tipo de Identificador Fiscal): TipoDocumento. ........................120 
5.3. Códigos Diversos. ............................................................................................................................121 
5.3.1. Lenguaje (ISO 639): Idioma. .....................................................................................................121 
5.3.2. Moneda (ISO 4217): TipoMoneda. ...........................................................................................124 
5.3.3. Pagos. .......................................................................................................................................130 
5.4. Códigos Geográficos. .......................................................................................................................131 
5.4.1. Países (ISO 3166-1): Pais. .........................................................................................................131 
5.4.2. Departamentos (ISO 3166-2:CO): Departamento. ...................................................................143 
5.4.3. Municipios: Municipio. .............................................................................................................144 
5.5. Campos Nómina. .............................................................................................................................178 
5.5.1. Periodo de Nómina: PeriodoNomina. ......................................................................................178 
5.5.2. Tipo de Contrato: TipoContrato. ..............................................................................................179 
5.5.3. Tipo de Trabajador: TipoTrabajador.........................................................................................179 
5.5.4. Subtipo de Trabajador: SubTipoTrabajador. ............................................................................179 
5.5.5. Tipo de Hora Extra o Recargo: Porcentaje. ..............................................................................180 
5.5.6. Tipo de Incapacidad: Tipo.........................................................................................................180 
5.5.7. Tipo de XML: TipoXML. .............................................................................................................180 
5.5.8. Tipo de Nota de Ajuste: TipoNota. ...........................................................................................180 
6. Reglas y Mensajes de Validación. .......................................................................................................... 182 
6.1. Documentos Electrónicos. ...............................................................................................................182 
6.1.1. Documento Soporte de Pago de Nómina Electrónica: NominaIndividual. ..............................182 
6.1.2. Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica: 
NominaIndividualDeAjuste. ..............................................................................................198 
6.1.3. Firma Digital del Documento: ds:Signature. ............................................................................221 
6.2. Reglas Relativas al Establecimiento de la Conexión. .......................................................................231 
6.2.1. Mensaje del Web Service. ........................................................................................................231 
6.2.2. Schema XML. ............................................................................................................................231 
6.2.3. Certificado Digital de Transmisión (conexión). ........................................................................231 
6.2.4. Certificado Digital de Firma (Firma XML). ................................................................................232 
6.2.5. Firma. ........................................................................................................................................232 
Abreviaturas Utilizadas. ............................................................................................................................. 232 
7. Política de firma. .................................................................................................................................... 234 
7.1. Observaciones. ................................................................................................................................234 
7.2. Consideraciones Generales. ............................................................................................................234 

---

## Página 4

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 4 de 269 
 
7.3. Especificaciones técnicas sobre la firma digital Avanzada. .............................................................234 
7.4. Alcance de la Política de Firma. .......................................................................................................235 
7.5. Política de Firma. .............................................................................................................................235 
7.5.1. Actores de la Firma. ..................................................................................................................235 
7.5.2. Formato de Firma. ....................................................................................................................235 
7.6. Algoritmo de Firma. .........................................................................................................................236 
7.7. Algoritmo de Organización de Datos según el Canon. ....................................................................236 
7.8. Ubicación de la Firma. .....................................................................................................................236 
7.9. Condiciones de la Firma. .................................................................................................................236 
7.10. Identificador de la Política. ............................................................................................................238 
7.11. Hora de Firma. ...............................................................................................................................239 
7.12. Firmante. .......................................................................................................................................239 
7.13. Mecanismo de firma digital. ..........................................................................................................239 
7.14. Certificado digital desde la vigencia de la circular 03-2016 de la ONAC. ......................................239 
8. Mecanismos de Control del Documento Soporte de Pago de Nómina Electrónica y Nota de Ajuste del 
Documento Soporte de Pago de Nómina Electrónica. .............................................................................. 245 
8.1. Especificación Técnica de Generación Del CUNE. ...........................................................................245 
8.1.1. Consideraciones Generales del CUNE. .....................................................................................245 
8.2. Especificacón Técnica Del Código De Seguridad Del Software. ......................................................248 
8.3. Métodos de Calculo. ........................................................................................................................249 
8.3.1. Cálculo de Tiempo Laborado ....................................................................................................249 
9. Descripciónes Tecnológicas del Web Services de Método Síncrono. ................................................... 249 
9.1. Modelo conceptual de comunicación. ............................................................................................250 
9.2. Servicio síncrono. ............................................................................................................................250 
9.2.1. Secuencia del servicio síncrono. ...............................................................................................250 
9.3. Aspectos tecnológicos de las operaciones del web service. ...........................................................251 
9.4. Estándar de comunicación. .............................................................................................................251 
9.5. Estándar de mensajes de los servicios de La DIAN..........................................................................252 
9.6. Descripción de los servicios web de La DIAN. .................................................................................252 
9.7. WS recepción documento electrónico – SendNominaSync. ...........................................................252 
9.7.1. Descripción de procesamiento. ................................................................................................252 
9.7.2. Mensaje de petición. ................................................................................................................253 
9.8. WS Consulta del estado de DE – GetStatus. ....................................................................................254 
9.8.1. Descrición de procesamiento. ..................................................................................................254 

---

## Página 5

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 5 de 269 
 
9.8.2. Mensaje de petición. ................................................................................................................255 
10. Campos definidos en las extensiones. ................................................................................................. 257 
10.1. Estructura para reporte de información adicional específica de cada sector. .............................257 
11. Elemento Novedad. ............................................................................................................................. 257 
12. Preguntas Frecuentes. ......................................................................................................................... 258 
13. Servicio de Consulta. ........................................................................................................................... 258 
13.1. Servicio de consulta a través de Código Bidimensional QR. .........................................................258 
14. Anexo: Herramienta para el consumo de Web Services. .................................................................... 261 
14.1. Introducción ..................................................................................................................................261 
14.2. Descargar SOAP UI. .......................................................................................................................261 
14.3. Ejecutar SOAP UI. ..........................................................................................................................261 
14.4. Crear un nuevo proyecto tipo SOAP..............................................................................................261 
14.5. Configuración inicial. .....................................................................................................................262 
14.6. Configurar Keystore. ......................................................................................................................262 
14.7. Configurar WS-Security Signature. ................................................................................................263 
14.8. Configurar TimeStamp. .................................................................................................................264 
14.9. Configurar GetStatus Request, Authentication y WS-A addressing. .............................................264 
14.10. Configurar y ejecutar GetStatus Request. ...................................................................................266 
14.11. Configurar y ejecutar SendBillAsync Request. ............................................................................267 
14.12. SendBillAsync Response. .............................................................................................................268 
14.13. Recomendaciones. ......................................................................................................................269 
15. Control de cambios. ............................................................................................................................ 269 
 

---

## Página 6

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 6 de 269 
 
1. Introducción. 
El presente anexo técnico describe el Documento Soporte de Pago de Nómina Electrónica y la Nota de 
Ajuste del Documento Soporte de Pago de Nómina Electrónica, para que sean documentos soporte de 
costos y deducciones en el impuesto sobre la renta y complementarios, de conformidad con lo 
dispuesto en el parágrafo 6 del artículo 616-1. 
El formato No pertenece al Estandar Universal Business Language – UBL. 
La generación de l Documento Soporte de Pago de  la Nómina Elect rónica y la Nota de Ajuste del 
Documento Soporte de Pago de Nómina Electrónica poseen las siguientes características: 
 
 Documento Soporte de Pago de Nómina Electrónica (NominaIndividual): Debe existir al menos 1 
documento de este tipo por cada empleado que tenga la empresa  por mes, el cual corresponde 
al Comprobante de Nómina de dicho trabajador. 
 
 Nota de Ajuste del Documento Soporte de Pago de Nómina Electrónica 
(NominaIndividualDeAjuste): Debe existir 1 documento de este tipo por cada Documento Soporte 
de Pago de Nómina Electrónica de cada empleado que tenga la empresa el cual se deba ajustar o 
reemplazar por errores aritméticos contables o de contenido y que el sujeto obligado deberá 
ajustar o corregir. Este documento electrónico podrá hacerse tantas veces como correcciones se 
requieran realizar sobre un mismo Documento Soporte de Pago de Nómina Electrónica, siendo la 
úlima nota de ajuste del documento soporte de pago de nómina electrónica validada, la que sirva 
como soporte. 
Este documento también permite eliminar un Documento Soporte de Pago de Nómina Electrónica 
o una Nota de Ajuste del Documento Soporte de Pago de Nómina Electrónica que el sujeto 
obligado deba eliminar por errores contables o de procedimiento. 
 
El objetivo de la presente descripción es buscar, una estandarización del Documento Soporte de Pago 
de Nómina Electrónica y Nota de Ajuste del Documento Soporte de Pago de Nómina Electrónica , 
permitiendo que la información pueda ser utilizada de la manera más eficaz, eficiente y efectiva 
posible. 
 
De igual forma se deberá tener en cuenta lo referente al tratamiento de datos personales relacionado 
con la seguridad de la información que contienen los documentos que por medio de este anexo se 
implementan, de conformidad con lo previsto en los artículos 17 y 18 de la Ley 1581 de 2012 y la 
Circular 000001 del 25 de enero de 2019 de la Unidad Administrativa Especial Dirección de Impuestos 
y Aduanas Nacionales -DIAN, las cuales señalan los aspectos relacionados con el tratamiento de datos 
personales y la seguridad de la información , los cuales se desarrollan en el TÍTULO IX de la presente 
resolución.  
 

---

## Página 7

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 7 de 269 
 
Se imponen por lo tanto dos (2) requisitos: confiabilidad y calidad en las informaciones tal como se 
describe a continuación. 
 
1.1. Calidad de la información: las Validaciones. 
En el presente anexo técnico se aclara las limitaciones que se pueden presentar al brindar información 
en un determinado elemento, tanto de manera lógica, como de manera aritmética. 
 
La aplicación de las reglas de validación puede terminar en uno (1) de los siguientes tres (3) resultados: 
 Rechazo, si la aplicación de la regla apunta a una discrepancia grave, que indica que las 
informaciones del archivo no pueden ser utilizadas de manera confiable o de manera legal; 
 Notificación, si la aplicación de la regla apunta a una discrepancia menos important e, pero que 
asimismo merece que se advierta al emisor de un posible problema con las informaciones del 
archivo; 
 Aprobación, si la aplicación de la regla no apunta a ningún tipo de problema. 
 
Las reglas de validación serán aplicadas en los siguientes momentos: 
 Por la DIAN al recibir, del Sujeto Obligado directamente a través de Modalidad Software Propio o 
a través de un tercero. 
 
1.1.1. Redondeos. 
Las reglas de validación que contengan operaciones aritméticas relacionadas con valores monetarios 
deberán cumplir con los siguientes parámetros para su aproximación, dependiendo de la cantidad de 
decimales definidos para el campo respectivo en las reglas de validación que apliquen: 
 
Dígito siguiente al dígito menos significativo es Redondeo 
Entre 0 y 4. Mantener el dígito menos significativo. 
Entre 6 y 9. Incrementar el dígito menos significativo. 
5, y el segundo dígito siguiente al dígito menos significativo es cero o par. Mantener el dígito menos significativo. 
5, y el segundo dígito siguiente al dígito menos significativo es impar. Incrementar el dígito menos significativo. 
 
Esta definición se hace para que se reduzca el riesgo de problemas de suma de los valores 
redondeados, para valores originales con décimas conteniendo el número “5”. 
En caso que con la ad opción de este procedimiento haya diferencia entre los totales calculados y la 
suma de los parciales para el valor total de un documento, se debe rá utilizar el elemento 

---

## Página 8

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 8 de 269 
 
/NominaIndividual/Redondeo y /NominaInd ividualDeAjuste/Reempolazar/Redondeo para informar la 
diferencia. 
 
1.1.1.1. Redondeos valores monetarios. 
Redondeos para los elementos, que contienen valores monetarios. 
Nota: Los valores monetarios permitirán una tolerancia de error + - 2.00. 
Nota: La fórmula de redondeo utilizada en estos momentos es la round-half-to-even cuya definición 
se puede encontrar en la siguiente dirección https://www.w3.org/TR/xpath -functions-31/#func-
round-half-to-even, y, corresponde a la norma técnica colombiana NTC 3711 (Norma técnica 
internacional JIS Z 8401). 
 
1.1.2.  Identificador de los documentos electrónicos. 
El Código Único de Documento Soporte de Pago de Nómina Electrónica – CUNE utilizado para l os 
Documentos Soporte de Pago de Nómina Electrónica, es el identificador de los diferentes documentos 
electrónicos. Para su cálculo debe remitirse al numeral 8.1 del presente documento. 
Para posibilitar la referencia cruzada entre los diferentes documentos electrónico s, se incluye la 
etiqueta /Generales/@CUNE, la cual contendrá un identif icador universal denominado “ CUNE” y su 
Tipo de encriptado denominado “EncripCUNE” . Est e identificador y el Tipo de Encriptado están 
localizados en la siguiente ruta de ambos documentos: 
Documento Soporte de Pago de Nómina Electrónica: 
 /NominaIndividual/InformacionGeneral/@CUNE 
 /NominaIndividual/InformacionGeneral/@EncripCUNE 
Nota de Ajuste del Documento Soporte de Pago de Nómina Electrónica: 
 /NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@CUNE 
 /NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@CUNE 
 /NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@EncripCUNE 
 /NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@EncripCUNE 
 
La etiqueta CUNE contendrá: 
 Como se mencionó anteriormente, el lector debe remitirse al numeral 8.1, con el objeto de revisar 
cómo se calcula o genera el CUNE para los diferentes documentos electrónicos. 
Los elementos utilizados en los cálculos se encuentran especificados en el presente documento. 
 

---

## Página 9

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 9 de 269 
 
1.1.3. Valores Negativos. 
1.1.3.1. Monetarios. 
Todos los valores monetarios deberán ser expresados en valores positivos. La naturaleza del signo 
negativo o positivo la otorga el concepto de campo, mas no está incluido en el valor. 
Se informa la generación de la regla VLR01. 
1.1.3.2. Tarifas. 
Las tarifas tributarias deben corresponde r a valores iguales o superiores a 0.00, en este caso no 
se permiten valores negativos. 
 
2. Convenciones utilizadas en las tablas. 
Este capítulo presenta la definición de las estructuras de las tablas de definición del formato XML tanto 
de los Documentos Electrónicos, como de las reglas de validación. 
 
2.1. Columnas de las tablas de definición. 
Las columnas de las Tablas de Definición siguen las descripciones que se encuentran en la Tabla 1. 
 
Tabla 1 – Convenciones Utilizadas en la Tablas de Definición de los Formatos XML. 
Columna Descripción 
ID Identificador único del elemento atributo y que servirá de base para la codificación de notificaciones o errores de cada 
uno de ellos. 
NS 
Identifica el NameSpace al cual pertenece el campo: 
 xmlns="dian:gov:co:facturaelectronica:NominaIndividual" 
 xmlns="dian:gov:co:facturaelectronica:NominaIndividualDeAjuste" 
 xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" 
 ds - http://www.w3.org/2000/09/xmldsig# 
 ext - urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2 
 xades -http://uri.etsi.org/01903/v1.3.2# 
 xmlns - xades141="http://uri.etsi.org/01903/v1.4.1#" 
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
 SchemaLocation="" 
 xsi:schemaLocation="dian:gov:co:facturaelectronica:NominaIndividual NominaIndividualElectronicaXSD.xsd" 
 xsi:schemaLocation="dian:gov:co:facturaelectronica:NominaIndividualDeAjuste 
NominaIndividualDeAjusteElectronicaXSD.xsd" 
Campo Nombre del elemento o grupo de elementos: 
 Los atributos de elementos inician con el símbolo “@”. 
Descripción Descripción del elemento o grupo y su significado. 
T Tipo de elemento (ver Tabla 2). 
F Tipo de dato (ver Tabla 3). 
Tam Tamaño del elemento (ver Tabla 4). 

---

## Página 10

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 10 de 269 
 
Columna Descripción 
Padre Nombre del grupo que contiene este elemento o grupo. 
Ocu 
Identifica la cantidad de posibles ocurrencias del elemento o grupo. Ejemplo: 
1-1 – Identifica que el elemento o grupo es obligatorio, con máximo de una ocurrencia. 
0-1 – Identifica que el elemento o grupo es facultativo (posible de no ser informado), con máximo de una ocurrencia. 
1-N – Identifica que el elemento o grupo es obligatorio, con máximo de N ocurrencias. 
0-N – Identifica que el elemento o grupo es facultativo (posible de no ser informado), con máximo de N ocurrencias. 
Observaciones Observaciones importantes sobre el campo, incluyendo listas de valores posibles, validaciones relevantes entre otras. 
V Versión que el campo fue introducido en el formato, o versión en que ha sido modificado por la última vez. 
  
Nota: La definición de los namespace utilizados en los Documentos Electrónicos  deben ser 
mencionados a nivel de la cabecera de los documentos NominaIndividual o NominaIndividualDeAjuste. 
2.2. Tipos de campos de los archivos XML. 
Los tipos de campos de los archivos XML tienen su contenido descrito en la Tabla 2 y en la Tabla 3. 
 
Tabla 2 – Tipos de Campo en los Archivos XML. 
Tipo Descripción 
G Grupo de elementos. 
E Elemento. 
A Atributo de un elemento. 
 
Tabla 3 – Tipos de Datos de los Elementos en los Archivos XML. 
Tipo Descripción 
A Alfanumérico: son aceptados los caracteres UNICODE permitidos en el XML. 
B Booleano: acepta solamente los literales “true” y “false” (se debe usar minúsculas). 
N Numérico: solamente son aceptados los números “0” a “9”, el punto de separación decimal, y las señales “+” y “-“. 
F 
Fecha: elementos que deben ser informados en el formato AAAA-MM-DD, de acuerdo con la norma ISO 8601-2, en el 
cual: 
 AAAA: año. 
 MM: mes. 
 DD: día. 

---

## Página 11

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 11 de 269 
 
Tipo Descripción 
H 
Hora: elementos que deben ser informados en el formato de tiempo universal coordinado HH:MM:SSdhh:mm, de 
acuerdo con la norma ISO 8601-2, en el cual: 
 HH: hora UTC (número de horas contadas desde la media noche, o sea, de 00 hasta 23). 
 MM: minutos. 
 SS: segundos. 
 hh:mm – diferencia en horas y minutos con relación a la hora GMT. 
 d: señal (“+” o “-“) para la diferencia con relación a la hora GMT1. 
Ejemplo: dos y treinta de la tarde en Bogotá debe ser informado como 14:30:00-05:00. 
I 
Intervalo de tiempo: elementos que deben ser informados en el formato <Fecha Inicial>/<Fecha Final>, siendo que 
obedece el formato “F” para ambas las fechas. 
Ejemplo: el período entre 01 de septiembre y 30 de septiembre de 2020 debe ser informado como 2020-09-01/2020-
09-30. 
X Documento XML. 
 
2.3. Tamaños de los elementos. 
Existen elementos con tamaño fijo, y elementos con tamaño variable. Los elementos de tamaño fijo 
no admiten información con otro número de posición diferente a la que se establece, es decir, la 
información en este tipo de configuración siempre tiene exactamente el mismo tamaño. 
Los elementos de tamaño variable admiten un rango de número de posiciones que varía de un mínimo 
hasta un máximo. En caso que la información no utilice el número máximo de posiciones, no se deben 
incluir caracteres para rellenar el espacio, tales como ceros o blancos. 
Los elementos de tamaño variable que tienen el valor cero (0) como tamaño mínimo admiten que sean 
informados sin contenido, en este caso, el emisor declara que no existe o no se encuentra disponible 
la información correspondiente. 
 
Tabla 4 – Tamaños de Elementos. 
                                                 
1 Atención: no es la hora “Zulu”, o sea, referenciada al meridiano zero. Debe ser informada una hora en una zona 
horaria específica, de libre elección del emisor: en el ejemplo fue escogido -5, que es la zona horaria oficial de 
Colombia.  
 La zona horaria ele gida por el emisor del documento electrónico es indiferente para la aplicación de las 
reglas de validación: todas las operaciones de evaluación de horas se realizan tomando en cuenta la zona 
horaria informada en el campo específico. 
 No existe necesidad de utilizar la misma zona horaria en todos los campos del tipo “hora” a lo largo de un 
mismo archivo. 
Formato Descripción 
X Tamaño exacto del elemento. 

---

## Página 12

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 12 de 269 
 
 
Ejemplos de cómo se deben informar los valores en los elementos numéricos de acuerdo con el 
formato especificado pueden ser encontrados en la Tabla 5. 
 
Tabla 5 – Ejemplos de Información de Valores Utilizando los Formatos Numéricos. 
Formato Para Informar: Llenar elemento con: 
0-11 p (0-6) 
1,105.13  1105.13 
1,105.137  1105.137 
1,105  1105 
0  0 
para no informar cantidad dejar el elemento vacío 
1-11 
1,105  1105 
0  0 
para no informar cantidad no es posible 
 
 ej.: 5. 
 Informar menos o más de cinco posiciones tendrá como resultado el rechazo del archivo. 
x-y 
Tamaño mínimo de “x”, máximo de “y”. 
 ej.: 0-10. 
 Es posible expresar ningún valor, porque se permite el tamaño “0”. 
 Informar más de diez posiciones tendrá como resultado el rechazo del archivo. 
x p n 
Tamaño exacto del elemento de “x”, con exactamente “n” casillas decimales. 
 ej.: 11 p 4. 
 El número debe tener once posiciones, siendo exactamente seis posiciones antes del punto 
decimal, y exactamente cuatro (4) posiciones después del punto decimal; cualquier otro número 
de posiciones tendrá como resultado el rechazo del archivo. 
x p (n-m) 
Tamaño exacto del elemento de “x”, con entre “n” y “m” casillas decimales. 
 ej.: 11 p (0-6). 
 El número debe tener exactamente once posiciones, aceptándose cualquier combinación desde 
once posiciones sin punto decimal hasta exactamente cuatro (4) posiciones an tes del punto 
decimal, y exactamente seis (6) posiciones después del punto decimal. 
(x-y) p (n-m) 
Tamaño mínimo de “x”, máximo de “y”, con entre “n” y “m” casillas decimales. 
 ej.: 1-11 p (0-6). 
 Es obligatorio expresar algún valor, porque no se permite el tamaño “0”. 
 El número debe entre una (1) y once posiciones, aceptándose cualquier combinación desde once 
posiciones sin punto decimal hasta exactamente cuatro (4) posiciones antes del punto decimal, y 
exactamente seis (6) posiciones después del punto decimal, pero la parte fraccionaria es opcional. 
Valores separados 
por comas 
El elemento deberá ser informado con tamaño de exactamente una de las opciones listadas. 
 ej.: 1, 3, 5, 8 significa que se debe informar el elemento con uno de estos cuatro tamaños fijos. 

---

## Página 13

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
             
          Página 13 de 269 
 
2.4. Convenciones utilizadas en las Tablas de Reglas de Validación. 
Las columnas de las Tablas de Reglas de Validación siguen las descripciones que se encuentran en la 
Tabla 6. 
Tabla 6 – Nombres de las Columnas de las Tablas de Reglas de Validación. 
Columna Descripción 
Tipo Categoría de la regla de validación. 
# Identificador de la regla de validación. 
Campo Nombre del campo en las tablas de formato. 
Regla  Descripción de la regla de validación. 
Cod Código de mensaje correspondiente a la regla de validación. 
Y 
Efecto de la regla de validación: 
 R: Rechazo, el procesamiento correspondiente ha encontrado problemas que impiden el procesamiento de la 
solicitud. 
 N: Notificación, el procesa miento correspondiente ha encontrado indicios de potenciales problemas, los 
cuales no impiden el procesamiento de la solicitud. 
Mensaje Mensaje regresado como resultado de un rechazo el de una notificación. 
V Versión de las reglas de validación. 

---

## Página 14

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 14 de 269 
 
3. Formato para la generación de los Documentos Electrónicos. 
El sistema de Documento Soporte de Pago de Nómina Electrónica de Colombia utiliza dos ( 2) documentos XML: NominaIndividual y 
NominaIndividualDeAjuste. 
 
3.1. Documento Soporte de Pago de Nómina Electrónica: NominaIndividual. 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  NominaIndividual Documento Soporte de Pago de Nómina 
Electrónica - NominaIndividual (raíz)     1-1  1.0 /NominaIndividual 
NIE001 Ext UBLExtensions Grupo correspondiente a la Firma Digital 
del Documento (Signature) G A  NominaIndividual 1-1 
Solamente puede haber una ocurrencia de 
un grupo UBLExtensions conteniendo el 
grupo ds:Signature. Ver definición en 
numeral 3.6 
1.0 /NominaIndividual/ext:UB
LExtensions 
NIE199  Novedad 
Indica si existe alguna Novedad 
Contractual en el Documento Soporte de 
Pago de Nómina Electrónica o Nota de 
Ajuste de Documento Soporte de Pago de 
Nómina Electrónica del Trabajador en 
dicho Mes. 
E B  NominaIndividual 0-1 Se debe colocar "true" o "false". 1.0 /NominaIndividual/Noved
ad 
NIE204  CUNENov 
Debe corresponder al CUNE del 
Documento Soporte de Pago de Nómina 
Electrónica o Nota de Ajuste de 
Documento Soporte de Pago de Nómina 
Electrónica a realizar la Novedad 
A A 96 Novedad 1-1 Debe ir el CUNE del documento al cual se le 
realizará la novedad contractual 1.0 /NominaIndividual/Noved
ad/@CUNENov 
  Periodo Utilizado para Atributos del Periodo 
Generación del Documento E A  NominaIndividual 1-1 Elemento Vacio 1.0 /NominaIndividual/Period
o 

---

## Página 15

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 15 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE002  FechaIngreso 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz presenta ingreso o 
vinculación a la nómina del reportante. 
(en caso de tener mas de un ingreso en el 
mes, se debe reportar la primera fecha en 
la que se presenta esta novedad en el 
mes que se esta reportando). 
A F 10 Periodo 1-1 
Se debe indicar la Fecha de Ingreso del 
trabajador a la empresa, en formato AAAA-
MM-DD 
1.0 /NominaIndividual/Period
o/@FechaIngreso 
NIE003  FechaRetiro 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz presenta retiro de 
la nómina del reportante.(en caso de 
tener mas de un retiro en el mes, se debe 
reportar la ultima fecha en la que se 
presenta esta novedad en el mes que se 
esta reportando). 
A F 10 Periodo 0-1 
Se debe indicar la Fecha de Retiro del 
trabajador a la empresa, en formato AAAA-
MM-DD 
1.0 /NominaIndividual/Period
o/@FechaRetiro 
NIE004  FechaLiquidacionIni
cio Fecha de inicio de Liquidación de Nómina A F 10 Periodo 1-1 
Se debe indicar la Fecha de Inicio del 
Periodo de liquidación del documento, en 
formato AAAA-MM-DD 
1.0 
/NominaIndividual/Period
o/@FechaLiquidacionInici
o 
NIE005  FechaLiquidacionFin Fecha fin de Liquidación de Nómina A F 10 Periodo 1-1 
Se debe indicar la Fecha de Fin del Periodo 
de liquidación del documento, en formato 
AAAA-MM-DD 
1.0 /NominaIndividual/Period
o/@FechaLiquidacionFin 
NIE006  TiempoLaborado Cantidad de Tiempo que lleva laborando 
el Trabajador en la empresa A A  Periodo 1-1 Definido en el numeral 8.4.1, debe ser 
mayor o gual a 1. 1.0 /NominaIndividual/Period
o/@TiempoLaborado 
NIE008  FechaGen Fecha de emisión: Fecha de emisión del 
documento A F 10 Periodo 1-1 
Debe ir la fecha de emision del documento. 
Considerando zona horaria de Colombia (-
5), en formato AAAA-MM-DD 
1.0 /NominaIndividual/Period
o/@FechaGen 

---

## Página 16

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 16 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  NumeroSecuenciaX
ML 
Utilizado para Atributos de Numero de 
Secuencia del Documento XML E A  NominaIndividual 1-1 Elemento Vacio 1.0 /NominaIndividual/Numer
oSecuenciaXML 
NIE009  CodigoTrabajador Codigo del Trabajador A A  NumeroSecuencia
XML 0-1 Campo Opcional queda a manejo Interno 
del Empleador. 1.0 
/NominaIndividual/Numer
oSecuenciaXML/@Codigo
Trabajador 
NIE010  Prefijo Prefijo del documento, depende de las 
sucursales que posea el Empleador A A  NumeroSecuencia
XML 0-1 Debe corresponder a un Prefijo elegido por 
el Emisor del documento 1.0 /NominaIndividual/Numer
oSecuenciaXML/@Prefijo 
NIE011  Consecutivo Debe corresponder a un consecutivo 
manejado por el Empleador A N  NumeroSecuencia
XML 1-1 Debe corresponder a un Consecutivo 
elegido por el Emisor del documento 1.0 
/NominaIndividual/Numer
oSecuenciaXML/@Consec
utivo 
NIE012  Numero Debe corresponder al Prefijo y 
consecutivo manejado por el Empleador A A  NumeroSecuencia
XML 1-1 
No se permiten caracteres adicionales como 
espacios o guiones. Prefijo + Número 
consecutivo del documento 
1.0 
/NominaIndividual/Numer
oSecuenciaXML/@Numer
o 
  LugarGeneracionXM
L 
Utilizado para Atributos del Lugar de 
Generacion del Documento XML E A  NominaIndividual 1-1 Elemento Vacio 1.0 /NominaIndividual/LugarG
eneracionXML 
NIE013  Pais Codigo del país donde se genera el 
documento A A 2 LugarGeneracionX
ML 1-1 Se debe colocar el Codigo alfa-2 de la tabla 
5.4.1 1.0 /NominaIndividual/LugarG
eneracionXML/@Pais 
NIE014  DepartamentoEstad
o 
Código del departamento donde se 
genera el documento A N 2 LugarGeneracionX
ML 1-1 Se debe colocar el Codigo de la tabla 5.4.2 1.0 
/NominaIndividual/LugarG
eneracionXML/@Departa
mentoEstado 
NIE015  MunicipioCiudad Código del municipio o ciudad donde se 
genera el documento A N 5 LugarGeneracionX
ML 1-1 Se debe colocar el Codigo de la tabla 5.4.3 1.0 
/NominaIndividual/LugarG
eneracionXML/@Municipi
oCiudad 

---

## Página 17

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 17 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE016  Idioma Codigo del país donde se genera el 
documento A A 2 LugarGeneracionX
ML 1-1 
Se debe colocar el Codigo ISO 639-1 de la 
tabla 5.3.1. Para Colombia se debe colocar 
"es" (Español, Castellano) 
1.0 /NominaIndividual/LugarG
eneracionXML/@Idioma 
  ProveedorXML Utilizado para Atributos del Proveedor del 
Documento XML E A  NominaIndividual 1-1 Elemento Vacio 1.0 /NominaIndividual/Provee
dorXML 
NIE205  RazonSocial 
Debe corresponder al Nombre de la 
Razón Social del Proveedor de Soluciones 
Tecnológicas 
A A  ProveedorXML 0-1 Debe ir el Nombre o Razón Social del 
Proveedor de Soluciones Tecnológicas 1.0 /NominaIndividual/Provee
dorXML/@RazonSocial 
NIE206  PrimerApellido Primer Apellido del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Debe ir el Primer Apellido del Proveedor de 
Soluciones Tecnológicas 1.0 /NominaIndividual/Provee
dorXML/@PrimerApellido 
NIE207  SegundoApellido Segundo Apellido del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Debe ir el Segundo Apellido del Proveedor 
de Soluciones Tecnológicas 1.0 
/NominaIndividual/Provee
dorXML/@SegundoApellid
o 
NIE208  PrimerNombre Primer Nombre del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Debe ir el Primer Nombre del Proveedor de 
Soluciones Tecnológicas 1.0 /NominaIndividual/Provee
dorXML/@PrimerNombre 
NIE209  OtrosNombres Otros Nombres del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Deben ir los Otros Nombres del Proveedor 
de Soluciones Tecnológicas 1.0 /NominaIndividual/Provee
dorXML/@OtrosNombres 
NIE017  NIT Debe corresponder al NIT que realiza el 
DE A N  ProveedorXML 1-1 
Se debe colocar el NIT sin guiones ni DV de 
la empresa dueña del Software que genera 
el Documento, debe estar registrado en la 
DIAN 
1.0 /NominaIndividual/Provee
dorXML/@NIT 
NIE018  DV Debe corresponder al DV del NIT del o 
que realiza el DE A N 2 ProveedorXML 1-1 
Se debe colocar el DV de la empresa dueña 
del Software que genera el Documento, 
debe estar registrado en la DIAN 
1.0 /NominaIndividual/Provee
dorXML/@DV 

---

## Página 18

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 18 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE019  SoftwareID 
Identificador Software: Identificador del 
software habilitado para la emisión de 
nóminas 
A A  ProveedorXML 1-1 
Identificador del software asignado cuando 
el software se activa en el Sistema del 
Documento Soporte de Pago de Nómina 
Electrónica, debe corresponder a un 
software autorizado para este Emisor 
1.0 /NominaIndividual/Provee
dorXML/@SoftwareID 
NIE020  SoftwareSC 
Huella del software que autorizó la DIAN 
al Obligado a Generar Nómina Electrónica 
o al Proveedor de soluciones Tecnológicas 
A A  ProveedorXML 1-1 Definido en el numeral 8.3 1.0 /NominaIndividual/Provee
dorXML/@SoftwareSC 
NIE021  CodigoQR Debe poseer información detallada del 
Documento Electronico E A  NominaIndividual 1-1 
Debe corresponder a la siguiente URL 
“https://catalogo-
vpfe.dian.gov.co/document/searchqr?docu
mentkey=CUNE”  donde la palabra CUNE 
debe ser reemplazada por el CUNE del 
documento electrónico 
1.0 /NominaIndividual/Codigo
QR 
  InformacionGeneral Utilizado para Atributos de Información 
General Documento E A  NominaIndividual 1-1 Elemento Vacio 1.0 /NominaIndividual/Inform
acionGeneral 
NIE022  Version Versión base de Schema XML usada para 
crear este perfil (NominaIndividual) A A  InformacionGener
al 1-1 Debe ir el literal: "V1.0: Documento Soporte 
de Pago de Nómina Electrónica" 1.0 /NominaIndividual/Inform
acionGeneral/@Version 
NIE023  Ambiente Tipo de Ambiente de Emision del 
Documento: Habilitacion o Produccion A N 1 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.1.1 1.0 /NominaIndividual/Inform
acionGeneral/@Ambiente 
NIE202  TipoXML Tipo de XML del Documento A N 2 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.5.7 1.0 /NominaIndividual/Inform
acionGeneral/@TipoXML 

---

## Página 19

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 19 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE024  CUNE 
CUNE:  Código Único de Documento 
Soporte de Pago de Nómina Electrónica. 
Elemento que verifica la integridad de la 
información recibida 
A A  InformacionGener
al 1-1 Definido en el numeral 8.1 1.0 /NominaIndividual/Inform
acionGeneral/@CUNE 
NIE025  EncripCUNE 
Identificador del esquema de 
identificación. Algoritmo utilizado para el 
cáculo del CUNE, SHA-384 
A A 11 InformacionGener
al 1-1 Debe ir la palabra "CUNE-SHA384" 1.0 
/NominaIndividual/Inform
acionGeneral/@EncripCU
NE 
NIE026  FechaGen Fecha de emisión: Fecha de emisión del 
documento A F 10 InformacionGener
al 1-1 
Debe ir la fecha de emision del documento. 
Considerando zona horaria de Colombia (-
5), en formato AAAA-MM-DD 
1.0 /NominaIndividual/Inform
acionGeneral/@FechaGen 
NIE027  HoraGen Hora de emisión: hora de emisión del 
documento A H 14 InformacionGener
al 1-1 
Debe ir la hora de emision del documento. 
Considerando zona horaria de Colombia (-
5), en formato HH:MM:SSdhh:mm 
1.0 /NominaIndividual/Inform
acionGeneral/@HoraGen 
NIE029  PeriodoNomina Corresponde al Codigo de Periodo de 
Nómina A N 1 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.5.1 1.0 
/NominaIndividual/Inform
acionGeneral/@PeriodoN
omina 
NIE030  TipoMoneda Tipo de Moneda utilizada en el 
documento A A 3 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.3.2. 
Para Colombia se debe colocar "COP" 1.0 
/NominaIndividual/Inform
acionGeneral/@TipoMon
eda 
NIE200  TRM 
Tasa Representativa del mercado. 
Corresponde a la tasa de cambio de la 
moneda utilizada en el documento en el 
Campo “TipoMoneda” a Pesos 
Colombianos. 
A N  InformacionGener
al 0-1 
Se debe colocar la tasa de cambio de la 
moneda utilizada en el documento en el 
Campo “TipoMoneda” a Pesos 
Colombianos. 
1.0 /NominaIndividual/Inform
acionGeneral/@TRM 
NIE031  Notas Campo de libre uso para Observaciones 
en el documento E A  NominaIndividual 0-N 
Información adicional: Texto libre, relativo 
al documento, Ejemplo: Información de 
Novedades de los trabajadores. 
1.0 /NominaIndividual/Notas 

---

## Página 20

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 20 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  Empleador Utilizado para Atributos del Empleador o 
Emisor del Documento E A  NominaIndividual 1-1 Elemento Vacio 1.0 /NominaIndividual/Emple
ador 
NIE032  RazonSocial Debe corresponder al Nombre de la 
Razón Social del Empleador A A  Empleador 0-1 Debe ir el Nombre o Razón Social del 
Empleador 1.0 /NominaIndividual/Emple
ador/@RazonSocial 
NIE210  PrimerApellido Primer Apellido del Empleador A A 60 Empleador 0-1 Debe ir el Primer Apellido del Empleador 1.0 /NominaIndividual/Emple
ador/@PrimerApellido 
NIE211  SegundoApellido Segundo Apellido del Empleador A A 60 Empleador 0-1 Debe ir el Segundo Apellido del Empleador 1.0 /NominaIndividual/Emple
ador/@SegundoApellido 
NIE212  PrimerNombre Primer Nombre del Empleador A A 60 Empleador 0-1 Debe ir el Primer Nombre del Empleador 1.0 /NominaIndividual/Emple
ador/@PrimerNombre 
NIE213  OtrosNombres Otros Nombres del Empleador A A 60 Empleador 0-1 Deben ir los Otros Nombres del Empleador 1.0 /NominaIndividual/Emple
ador/@OtrosNombres 
NIE033  NIT Debe corresponder al NIT del Empleador 
que realiza el DE A N  Empleador 1-1 Debe ir el NIT del Empleador sin guiones ni 
DV 1.0 /NominaIndividual/Emple
ador/@NIT 
NIE034  DV Debe corresponder al DV del NIT del 
Empleador que realiza el DE A N 2 Empleador 1-1 Debe ir el DV del Empleador 1.0 /NominaIndividual/Emple
ador/@DV 
NIE035  Pais 
Codigo del país donde se encuentra 
ubicada la empresa del empleador en el 
mes que se esta reportando 
A A 2 Empleador 1-1 Se debe colocar el Codigo alfa-2 de la tabla 
5.4.1 1.0 /NominaIndividual/Emple
ador/@Pais 
NIE036  DepartamentoEstad
o 
Código del departamento donde se 
encuentra ubicada la empresa del 
empleador en el mes que se esta 
reportando 
A N 2 Empleador 1-1 Se debe colocar el Codigo de la tabla 5.4.2 1.0 
/NominaIndividual/Emple
ador/@DepartamentoEsta
do 

---

## Página 21

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 21 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE037  MunicipioCiudad 
Código del municipio o ciudad donde se 
encuentra ubicada la empresa del 
empleador en el mes que se esta 
reportando 
A N 5 Empleador 1-1 Se debe colocar el Codigo de la tabla 5.4.3 1.0 /NominaIndividual/Emple
ador/@MunicipioCiudad 
NIE038  Direccion Debe corresponder a la dirección del 
lugar físico de expedición del documento.  A A  Empleador 1-1 Debe ir la Dirección Fisica del Empleador 1.0 /NominaIndividual/Emple
ador/@Direccion 
  Trabajador Utilizado para Atributos del Trabajador o 
Receptor del Documento E A  NominaIndividual 1-1 Elemento Vacio 1.0 /NominaIndividual/Trabaj
ador 
NIE041  TipoTrabajador 
Código del tipo de trabajador del 
Ministerio de salud. Aportes a Seguridad 
Social de Activos. 
A N 2 Trabajador 1-1 
Corresponde a la clasificación de PILA para 
conocer en que calidad se realizan las 
cotizaciones a la seguridad social. Se debe 
colocar el Codigo de la tabla 5.5.3 
1.0 /NominaIndividual/Trabaj
ador/@TipoTrabajador 
NIE042  SubTipoTrabajador 
Código del Sub tipo de trabajador del 
Ministerio de salud. Aportes a Seguridad 
Social de Activos 
A N 2 Trabajador 1-1 
Corresponde a una sub clasificación de PILA 
para conocer en que calidad se realizan las 
cotizaciones a la seguridad social. Se debe 
colocar el Codigo de la tabla 5.5.4 
1.0 
/NominaIndividual/Trabaj
ador/@SubTipoTrabajado
r 
NIE043  AltoRiesgoPension 
Si el trabajador desarrollo durante el 
presente periodo alguna de las 
actividades descritas en el Decreto 2090 
de 2003, o la norma que lo modifique, 
adicione o sustituya. 
A B 4-5 Trabajador 1-1 Se debe colocar "true" o "false" 1.0 /NominaIndividual/Trabaj
ador/@AltoRiesgoPension 
NIE044  TipoDocumento 
Tipo de documento de identificación que 
actualmente tiene el trabajador,  
aprendiz, o pasante 
A N 2 Trabajador 1-1 Se debe colocar el Codigo de la tabla 5.2.1 1.0 /NominaIndividual/Trabaj
ador/@TipoDocumento 

---

## Página 22

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 22 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE045  NumeroDocumento Numero de identificación que 
actualmente el trabajador o aprendiz A N  Trabajador 1-1 Debe ir el Numero de documento del 
trabajador, sin puntos ni comas ni espacios 1.0 
/NominaIndividual/Trabaj
ador/@NumeroDocument
o 
NIE046  PrimerApellido Primer Apellido del trabajador o aprendiz A A 60 Trabajador 1-1 Debe ir el Primer Apellido del trabajador 1.0 /NominaIndividual/Trabaj
ador/@PrimerApellido 
NIE047  SegundoApellido Segundo Apellido del trabajador o 
aprendiz A A 60 Trabajador 1-1 Debe ir el Segundo Apellido del trabajador 1.0 /NominaIndividual/Trabaj
ador/@SegundoApellido 
NIE048  PrimerNombre Primer Nombre del trabajador o aprendiz A A 60 Trabajador 1-1 Debe ir el Primer Nombre del trabajador 1.0 /NominaIndividual/Trabaj
ador/@PrimerNombre 
NIE049  OtrosNombres Otros Nombres del trabajador o aprendiz A A 60 Trabajador 0-1 Deben ir los Otros Nombres del trabajador 1.0 /NominaIndividual/Trabaj
ador/@OtrosNombres 
NIE050  LugarTrabajoPais 
Código del país actual donde se 
encontraba ubicado el trabajador o 
aprendiz en el mes reportado. 
A N 3 Trabajador 1-1 Se debe colocar el Codigo alfa-2 de la tabla 
5.4.1 1.0 /NominaIndividual/Trabaj
ador/@LugarTrabajoPais 
NIE051  LugarTrabajoDepart
amentoEstado 
Código del departamento actual donde se 
encontraba ubicado el trabajador o 
aprendiz en el mes reportado. 
A N 2 Trabajador 1-1 Se debe colocar el Codigo de la tabla 5.4.2 1.0 
/NominaIndividual/Trabaj
ador/@LugarTrabajoDepa
rtamentoEstado 
NIE052  LugarTrabajoMunici
pioCiudad 
Código del municipio o ciudad actual 
donde se encontraba ubicado el 
trabajador o aprendiz en el mes 
reportado. 
A N 5 Trabajador 1-1 Se debe colocar el Codigo de la tabla 5.4.3 1.0 
/NominaIndividual/Trabaj
ador/@LugarTrabajoMuni
cipioCiudad 
NIE053  LugarTrabajoDirecci
on 
Debe corresponder a la dirección del 
lugar físico donde vive el empleado. A A  Trabajador 1-1 Debe ir la Dirección Fisica del Trabajador 1.0 
/NominaIndividual/Trabaj
ador/@LugarTrabajoDirec
cion 

---

## Página 23

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 23 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE056  SalarioIntegral 
Si el trabajador tiene un salario integral, el 
cual es el tipo de remuneración que 
incluye todos los conceptos que puedan 
constituir salario en un solo monto o pago 
(prestaciones sociales y recargos 
nocturno, dominical y festivo, y el trabajo 
extra) y que sea superior a 10 SMLMV 
mas un 30% correspondiente a factor 
prestacional. 
A B 4-5 Trabajador 1-1 Se debe colocar "true" o "false" 1.0 /NominaIndividual/Trabaj
ador/@SalarioIntegral 
NIE061  TipoContrato Tipo de Contrato que posee el empleado 
con el Empleador A N 1 Trabajador 1-1 Se debe colocar el Codigo de la tabla 5.5.2 1.0 /NominaIndividual/Trabaj
ador/@TipoContrato 
NIE062  Sueldo 
Corresponde al valor que el empleador 
paga de forma periódica al trabajador 
como contraprestación por el trabajo 
realizado, este puede ser fijo o variable de 
acuerdo a la unidad de tiempo en que las 
partes hayan acordado el pago, teniendo 
como base el día o la hora trabajada. 
A N  Trabajador 1-1 Se debe colocar el Sueldo Base que el 
Trabajador tiene en la empresa 1.0 /NominaIndividual/Trabaj
ador/@Sueldo 
NIE063  CodigoTrabajador Codigo del Trabajador A A  Trabajador 0-1 Campo Opcional queda a manejo Interno 
del Empleador. 1.0 /NominaIndividual/Trabaj
ador/@CodigoTrabajador 
  Pago Utilizado para Atributos del Pago del 
Documento E A  NominaIndividual 1-1 Elemento Vacio 1.0 /NominaIndividual/Pago 
NIE064  Forma Formas de Pago del Documento A N 1 Pago 1-1 Se debe colocar el Codigo de la tabla 5.3.3.1 1.0 /NominaIndividual/Pago/
@Forma 

---

## Página 24

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 24 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE065  Metodo Metodos de Pago del Documento A N 2 Pago 1-1 Se debe colocar el Codigo de la tabla 5.3.3.2 1.0 /NominaIndividual/Pago/
@Metodo 
NIE066  Banco 
Nombre de Entidad Bancaria del 
Empleado donde se realiza la 
consignación 
A A  Pago 0-1 
Si el método de pago se realiza de forma 
bancaria. Se debe colocar el nombre de la 
entidad bancaria donde el trabajador tiene 
su cuenta para pago de nómina. 
1.0 /NominaIndividual/Pago/
@Banco 
NIE067  TipoCuenta Tipo de Cuenta Bancaria del Empleado 
donde se realiza la consignación A A  Pago 0-1 
Si el método de pago se realiza de forma 
bancaria. Se debe colocar el tipo de cuenta 
que el trabajador tiene para pago de 
nómina. 
1.0 /NominaIndividual/Pago/
@TipoCuenta 
NIE068  NumeroCuenta 
Numero de Cuenta Bancaria del 
Empleado donde se realiza la 
consignación 
A A  Pago 0-1 
Si el método de pago se realiza de forma 
bancaria. Se debe colocar el número de la 
cuenta que el trabajador tiene para pago de 
nómina.. 
1.0 /NominaIndividual/Pago/
@NumeroCuenta 
  FechasPagos Utilizado para Todos los Elementos de 
Fechas de Pagos del Documento G A  NominaIndividual 1-1  1.0 /NominaIndividual/Fechas
Pagos 
NIE203  FechaPago Fecha de Pago de la Nómina E F 10 FechasPagos 1-N 
Debe ir la fecha de pago del documento. 
Considerando zona horaria de Colombia (-
5), en formato AAAA-MM-DD 
1.0 /NominaIndividual/Fechas
Pagos/FechaPago 
  Devengados Utilizado para Todos los Devengos del 
Documento G A  NominaIndividual 1-1 
Hace referencia al concepto de valor 
devengado de nómina señalado en el 
numeral 18, articulo 1 de la presente 
resolución.  
1.0 /NominaIndividual/Deven
gados 
  Basico Utilizado para Atributos Basicos de 
Devengos del Documento E A  Devengados 1-1 Elemento Vacio 1.0 /NominaIndividual/Deven
gados/Basico 

---

## Página 25

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 25 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE069  DiasTrabajados 
Número de días que el trabajador o 
aprendiz efectivamente estuvo 
ejecutando sus labores en la empresa. 
A N 1-2 Basico 1-1 Cantidad de dias laborados durante el 
Periodo de Pago 1.0 
/NominaIndividual/Deven
gados/Basico/@DiasTraba
jados 
NIE070  SueldoTrabajado 
Corresponde al valor que el empleador 
paga de forma periódica al trabajador 
como contraprestación por el trabajo 
realizado, este puede ser fijo o variable de 
acuerdo a la unidad de tiempo en que las 
partes hayan acordado el pago, teniendo 
como base el día o la hora trabajada. 
A N  Basico 1-1 
Valor Base o Sueldo del trabajador según lo 
estipulado en su contrato. Corresponde al 
Sueldo Trabajado por los días laborados. 
1.0 
/NominaIndividual/Deven
gados/Basico/@SueldoTra
bajado 
  Transporte Utilizado para Atributos de Transporte de 
Devengos del Documento E A  Devengados 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/Transporte 
NIE071  AuxilioTransporte 
Parte de los viáticos pagado al trabajador 
correspondientes a medios de transporte 
y/o los gastos de representación. 
A N  Transporte 0-1 Valor de Auxilio de Transporte que recibe el 
trabajador por ley, según aplique 1.0 
/NominaIndividual/Deven
gados/Transporte/@Auxili
oTransporte 
NIE072  ViaticoManuAlojS 
Parte de los viáticos pagado al trabajador 
correspondientes a manutención y/o 
alojamiento. 
A N  Transporte 0-1 Valor de Viaticos, Manutención y 
Alojamiento de carácter Salarial 1.0 
/NominaIndividual/Deven
gados/Transporte/@Viatic
oManuAlojS 
NIE073  ViaticoManuAlojNS 
Parte de los viáticos pagado al trabajador 
correspondientes a manutención y/o 
alojamiento No Salariales. 
A N  Transporte 0-1 Valor de Viaticos, Manutención y 
Alojamiento de carácter No Salarial 1.0 
/NominaIndividual/Deven
gados/Transporte/@Viatic
oManuAlojNS 
  HEDs 
Utilizado para Todos los Elementos de 
Horas Extras Diarias de Devengos del 
Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/HEDs 
  HED Utilizado para Atributos de Horas Extras 
Diarias de Devengos del Documento E A  HEDs 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/HEDs/HED 

---

## Página 26

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 26 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE074  HoraInicio Hora de inicio de Hora Extra Diurna A H 19 HED 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HEDs/HED/@HoraI
nicio 
NIE075  HoraFin Hora de fin de Hora Extra Diurna A H 19 HED 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HEDs/HED/@HoraF
in 
NIE076  Cantidad Cantidad de Horas Extra Diurna A N  HED 1-1 Cantidad de Horas 1.0 
/NominaIndividual/Deven
gados/HEDs/HED/@Canti
dad 
NIE077  Porcentaje Porcentaje al cual corresponde el calculo 
de 1 hora Extra Diurna A N 4-6 HED 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividual/Deven
gados/HEDs/HED/@Porce
ntaje 
NIE078  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HED 1-1 Valor Pagado por las Horas 1.0 /NominaIndividual/Deven
gados/HEDs/HED/@Pago 
  HENs 
Utilizado para Todos los Elementos de 
Horas Extras Nocturnas de Devengos del 
Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/HENs 
  HEN Utilizado para Atributos de Horas Extras 
Nocturnas de Devengos del Documento E A  HENs 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/HENs/HEN 
NIE079  HoraInicio Hora de inicio de Hora Extra Nocturna A H 19 HEN 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HENs/HEN/@HoraI
nicio 
NIE080  HoraFin Hora de fin de Hora Extra Nocturna A H 19 HEN 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HENs/HEN/@HoraF
in 

---

## Página 27

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 27 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE081  Cantidad Cantidad de Horas Extras Nocturnas A N  HEN 1-1 Cantidad de Horas 1.0 
/NominaIndividual/Deven
gados/HENs/HEN/@Canti
dad 
NIE082  Porcentaje Porcentaje al cual corresponde el calculo 
de 1 hora Extra Nocturna A N 4-6 HEN 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividual/Deven
gados/HENs/HEN/@Porce
ntaje 
NIE083  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HEN 1-1 Valor Pagado por las Horas 1.0 /NominaIndividual/Deven
gados/HENs/HEN/@Pago 
  HRNs 
Utilizado para Todos los Elementos de 
Horas Recargo Nocturno de Devengos del 
Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/HRNs 
  HRN Utilizado para Atributos de Horas Recargo 
Nocturno de Devengos del Documento E A  HRNs 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/HRNs/HRN 
NIE084  HoraInicio Hora de inicio de Hora Recargo Nocturno A H 19 HRN 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRNs/HRN/@HoraI
nicio 
NIE085  HoraFin Hora de fin de Hora Recargo Nocturno A H 19 HRN 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRNs/HRN/@Hora
Fin 
NIE086  Cantidad Cantidad de Horas Recargo Nocturno A N  HRN 1-1 Cantidad de Horas 1.0 
/NominaIndividual/Deven
gados/HRNs/HRN/@Canti
dad 
NIE087  Porcentaje Porcentaje al cual corresponde el calculo 
de 1 hora Recargo Nocturno A N 4-6 HRN 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividual/Deven
gados/HRNs/HRN/@Porce
ntaje 

---

## Página 28

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 28 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE088  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HRN 1-1 Valor Pagado por las Horas 1.0 /NominaIndividual/Deven
gados/HRNs/HRN/@Pago 
  HEDDFs 
Utilizado para Todos los Elementos de 
Horas Extras Diarias Dominicales y 
Festivas de Devengos del Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/HEDDFs 
  HEDDF 
Utilizado para Atributos de Horas Extras 
Diarias Dominicales y Festivas de 
Devengos del Documento 
E A  HEDDFs 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/HEDDFs/HEDDF 
NIE089  HoraInicio Hora de inicio de Horas Extras Diurnas 
Dominical y Festivos A H 19 HEDDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
HoraInicio 
NIE090  HoraFin Hora de fin de Horas Extras Diurnas 
Dominical y Festivos A H 19 HEDDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
HoraFin 
NIE091  Cantidad Cantidad de Horas Extras Diurnas 
Dominical y Festivos A N  HEDDF 1-1 Cantidad de Horas 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
Cantidad 
NIE092  Porcentaje 
Porcentaje al cual corresponde el calculo 
de 1 Hora Extra Diurna Dominical y 
Festivo 
A N 4-6 HEDDF 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
Porcentaje 
NIE093  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HEDDF 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
Pago 
  HRDDFs 
Utilizado para Todos los Elementos de 
Horas Recargo Diarias Dominicales y 
Festivas de Devengos del Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/HRDDFs 

---

## Página 29

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 29 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  HRDDF 
Utilizado para Atributos de Horas Recargo 
Diarias Dominicales y Festivas del 
Documento 
E A  HRDDFs 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/HRDDFs/HRDDF 
NIE094  HoraInicio Hora de inicio de Horas Recargo Diurno 
Dominical y Festivos A H 19 HRDDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
HoraInicio 
NIE095  HoraFin Hora de fin de Horas Recargo Diurno 
Dominical y Festivos A H 19 HRDDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
HoraFin 
NIE096  Cantidad Cantidad de Horas Recargo Diurno 
Dominical y Festivos A N  HRDDF 1-1 Cantidad de Horas 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
Cantidad 
NIE097  Porcentaje 
Porcentaje al cual corresponde el calculo 
de 1 Hora Recargo Diurno Dominical y 
Festivos 
A N 4-6 HRDDF 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
Porcentaje 
NIE098  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HRDDF 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
Pago 
  HENDFs 
Utilizado para Todos los Elementos de 
Horas Extras Nocturnas Dominicales y 
Festivas de Devengos del Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/HENDFs 
  HENDF 
Utilizado para Atributos de Horas Extras 
Nocturnas Dominicales y Festivas del 
Documento 
E A  HENDFs 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/HENDFs/HENDF 
NIE099  HoraInicio Hora de inicio de Horas Extras Nocturna 
Dominical y Festivos A H 19 HENDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
HoraInicio 

---

## Página 30

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 30 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE100  HoraFin Hora de fin de Horas Extras Nocturna 
Dominical y Festivos A H 19 HENDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
HoraFin 
NIE101  Cantidad Cantidad de Horas Extras Nocturna 
Dominical y Festivos A N  HENDF 1-1 Cantidad de Horas 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
Cantidad 
NIE102  Porcentaje 
Porcentaje al cual corresponde el calculo 
de 1 Hora Extra Nocturna Dominical y 
Festivos 
A N 4-6 HENDF 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
Porcentaje 
NIE103  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HENDF 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
Pago 
  HRNDFs 
Utilizado para Todos los Elementos de 
Horas Recargo Nocturno Dominicales y 
Festivas de Devengos del Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/HRNDFs 
  HRNDF 
Utilizado para Atributos de Horas Recargo 
Nocturno Dominicales y Festivas del 
Documento 
E A  HRNDFs 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/HRNDFs/HRNDF 
NIE104  HoraInicio Hora de inicio de Horas Recargo Nocturno 
Dominical y Festivos A H 19 HRNDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
HoraInicio 
NIE105  HoraFin Hora de fin de Horas Recargo Nocturno 
Dominical y Festivos A H 19 HRNDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
HoraFin 
NIE106  Cantidad Cantidad de Horas Recargo Nocturno 
Dominical y Festivos A N  HRNDF 1-1 Cantidad de Horas 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
Cantidad 

---

## Página 31

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 31 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE107  Porcentaje 
Porcentaje al cual corresponde el calculo 
de 1 Hora Recargo Nocturno Dominical y 
Festivos 
A N 4-6 HRNDF 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
Porcentaje 
NIE108  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HRNDF 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
Pago 
  Vacaciones Utilizado para Todos los Elementos de 
Vacaciones de Devengos del Documento G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/Vacaciones 
  VacacionesComunes Utilizado para Atributos de Vacaciones 
Comunes del Documento E A  Vacaciones 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesComunes 
NIE109  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador presenta el inicio del disfrute 
de sus vacaciones en tiempo. 
A F 10 VacacionesComun
es 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesComunes/@FechaInici
o 
NIE110  FechaFin 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador regresa o termina el disfrute 
de sus vacaciones. 
A F 10 VacacionesComun
es 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesComunes/@FechaFin 
NIE111  Cantidad Número de días que el trabajador estuvo 
inactivo durante el mes por vacaciones. A N  VacacionesComun
es 1-1 Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesComunes/@Cantidad 

---

## Página 32

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 32 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE112  Pago 
Corresponde al valor pagado al 
trabajador, por el descanso remunerado 
que tiene derecho por haber trabajado un 
determinado tiempo. (Vacaciones SI 
disfrutadas) 
A N  VacacionesComun
es 1-1 Valor Pagado por Vacaciones Si Disfrutadas 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesComunes/@Pago 
  VacacionesCompens
adas 
Utilizado para Atributos de Vacaciones 
Compensadas del Documento E A  Vacaciones 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesCompensadas 
NIE115  Cantidad 
Número de días que el trabajador estuvo 
activo durante el mes sin disfrutar sus 
vacaciones. (Vacaciones NO disfrutadas) 
A N  VacacionesCompe
nsadas 1-1 Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesCompensadas/@Canti
dad 
NIE116  Pago 
Corresponde al valor pagado al 
trabajador, por el descanso remunerado 
que no disfrutó y que tiene derecho por 
haber trabajado un determinado tiempo. 
(Vacaciones NO disfrutadas) 
A N  VacacionesCompe
nsadas 1-1 Valor Pagado por Vacaciones No Disfrutadas 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesCompensadas/@Pago 
  Primas Utilizado para Atributos de Primas de 
Devengos del Documento E A  Devengados 0-1 Elemento Vacio 1.0 /NominaIndividual/Deven
gados/Primas 
NIE117  Cantidad Cantidad de dias trabajados para calculo 
de Pago de Corte de Prima A N  Primas 1-1 Cantidad de Dias a los cuales corresponde el 
pago de la Prima legal 1.0 /NominaIndividual/Deven
gados/Primas/@Cantidad 
NIE118  Pago 
Pagos por el reconocimiento del logro o 
cumplimiento por parte del trabajador en 
el desarrollo de sus labores, de 
condiciones definidas expresamente 
entre las partes. 
A N  Primas 1-1 Valor Pagado por Prima Legal con respecto 
a Cantidad de Dias 1.0 /NominaIndividual/Deven
gados/Primas/@Pago 

---

## Página 33

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 33 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE119  PagoNS 
Son valores pagados al trabajador de 
forma ocasional y por mera liberalidad o 
los pactados entre las partes de forma 
expresa como pago no salarial. 
A N  Primas 0-1 Valor Pagado por Prima No Salarial 1.0 /NominaIndividual/Deven
gados/Primas/@PagoNS 
  Cesantias Utilizado para Atributos de Cesantias de 
Devengos del Documento E A  Devengados 0-1 Elemento Vacio 1.0 /NominaIndividual/Deven
gados/Cesantias 
NIE120  Pago Pago de la Cesantia otorgada por Ley. A N  Cesantias 1-1 Valor Pagado por Cesantias 1.0 /NominaIndividual/Deven
gados/Cesantias/@Pago 
NIE121  Porcentaje Porcentaje que corresponde al Interes de 
Cesantia de Ley A N  Cesantias 1-1 Porcentaje de Interes de Cesantias 1.0 
/NominaIndividual/Deven
gados/Cesantias/@Porcen
taje 
NIE122  PagoIntereses Pago de los Intereses de Cesantia 
otorgada por Ley. A N  Cesantias 1-1 Valor Pagado por Intereses de Cesantias 1.0 
/NominaIndividual/Deven
gados/Cesantias/@PagoIn
tereses 
  Incapacidades 
Utilizado para Todos los Elementos de 
Incapacidades de Devengos del 
Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/Incapacidades 
  Incapacidad Utilizado para Atributos de Incapacidad 
del Documento E A  Incapacidades 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad 
NIE123  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador presenta o da por iniciada su 
Incapacidad. 
A F 10 Incapacidad 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@FechaInicio 

---

## Página 34

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 34 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE124  FechaFin 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador presenta o da por terminada 
su Incapacidad. 
A F 10 Incapacidad 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@FechaFin 
NIE125  Cantidad 
Número de días que el trabajador o 
aprendiz estuvo inactivo por incapacidad 
(sin importar su origen). 
A N  Incapacidad 1-1 Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@Cantidad 
NIE126  Tipo 
Se debe indicar el codigo al cual 
corresponda el tipo de incapacidad del 
Empleado 
A N 1 Incapacidad 1-1 Se debe colocar el Codigo que corresponda 
de la tabla 5.5.6 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@Tipo 
NIE127  Pago 
Valor de la prestación económica pagada 
al trabajador por consecuencia de la falta 
de capacidad laboral sin importar su 
origen. 
A N  Incapacidad 1-1 Valor Pagado por Incapacidad con respecto 
a Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@Pago 
  Licencias Utilizado para Todos los Elementos de 
Licencias de Devengos del Documento G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/Licencias 
  LicenciaMP Utilizado para Atributos de Licencia de 
Materinidad o Paternidad del Documento E A  Licencias 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/Licencias/Licencia
MP 
NIE128  FechaInicio Fecha donde da inicio la Licencia de 
Maternidad o Paternidad A F 10 LicenciaMP 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/Licencia
MP/@FechaInicio 
NIE129  FechaFin Fecha donde termina la Licencia de 
Maternidad o Paternidad A F 10 LicenciaMP 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/Licencia
MP/@FechaFin 

---

## Página 35

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 35 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE130  Cantidad 
Número de días que el trabajador o 
aprendiz efectivamente estuvo inactivo 
por licencia de maternidad o paternidad. 
A N  LicenciaMP 1-1 Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/Licencias/Licencia
MP/@Cantidad 
NIE131  Pago 
Valor pagado al trabajador del descanso 
remunerado que la ley confiere por el 
nacimiento de un hijo, y que es 
reconocido y pagado por la EPS a la que 
está afiliado el padre o la madre, o en su 
defecto por el empleador. 
A N  LicenciaMP 1-1 Valor Pagado por Licencia de Maternidad o 
Paternidad con respecto a Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/Licencias/Licencia
MP/@Pago 
  LicenciaR Utilizado para Atributos de Licencia 
Remunerada del Documento E A  Licencias 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/Licencias/LicenciaR 
NIE132  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz inicia algún permiso 
o licencia remunerada. 
A F 10 LicenciaR 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaR
/@FechaInicio 
NIE133  FechaFin 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz termina el permiso 
o licencia remunerada. 
A F 10 LicenciaR 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaR
/@FechaFin 
NIE134  Cantidad 
Número de días que el trabajador o 
aprendiz efectivamente estuvo inactivo 
por permiso o licencia pero que le fueron 
reconocidos en su pago. 
A N  LicenciaR 1-1 Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaR
/@Cantidad 
NIE135  Pago 
Valor pagado al trabajador corresponde a 
tiempo no laborado, que por ley o por 
acuerdo con el empleador se le concede 
A N  LicenciaR 1-1 Valor Pagado por Licencia Remunerada con 
respecto a Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaR
/@Pago 

---

## Página 36

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 36 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  LicenciaNR Utilizado para Atributos de Licencia No 
Remunerada del Documento E A  Licencias 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaN
R 
NIE136  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz inicia alguna 
suspensión, permiso o licencia NO 
remunerada. 
A F 10 LicenciaNR 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaN
R/@FechaInicio 
NIE137  FechaFin 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz termina la 
suspensión, permiso o licencia NO 
remunerada. 
A F 10 LicenciaNR 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaN
R/@FechaFin 
NIE138  Cantidad 
Número de días que el trabajador o 
aprendiz efectivamente estuvo inactivo 
por suspensión, permiso o licencia y que 
NO le fueron reconocidos en su pago. 
A N  LicenciaNR 1-1 Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaN
R/@Cantidad 
  Bonificaciones 
Utilizado para Todos los Elementos de 
Bonificaciones de Devengos del 
Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/Bonificaciones 
  Bonificacion Utilizado para Atributos de Bonificacion 
del Documento E A  Bonificaciones 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/Bonificaciones/Boni
ficacion 
NIE139  BonificacionS 
Son valores pagados al trabajador en 
forma de incentivo o recompensa por la 
contraprestación directa del servicio. 
A N  Bonificacion 0-1 Valor Pagado por Bonificación Salarial 1.0 
/NominaIndividual/Deven
gados/Bonificaciones/Boni
ficacion/@BonificacionS 

---

## Página 37

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 37 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE140  BonificacionNS 
Son valores de incentivos pagados al 
trabajador de forma ocasional y por mera 
liberalidad o los pactados entre las partes 
de forma expresa como pago no salarial. 
A N  Bonificacion 0-1 Valor Pagado por Bonificación No Salarial 1.0 
/NominaIndividual/Deven
gados/Bonificaciones/Boni
ficacion/@BonificacionNS 
  Auxilios Utilizado para Todos los Elementos de 
Auxilios de Devengos del Documento G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/Auxilios 
  Auxilio Utilizado para Atributos de Auxilio del 
Documento E A  Auxilios 0-N Elemento Vacio 1.0 /NominaIndividual/Deven
gados/Auxilios/Auxilio 
NIE141  AuxilioS 
Son beneficios, ayudas o apoyos 
económicos, pagados al trabajador de 
forma habitual o pactados entre las 
partes como factor salarial. 
A N  Auxilio 0-1 Valor Pagado por Auxilios Salariales 1.0 
/NominaIndividual/Deven
gados/Auxilios/Auxilio/@A
uxilioS 
NIE142  AuxilioNS 
Son beneficios, ayudas o apoyos 
económicos, pagados al trabajador de 
forma ocasional y por mera liberalidad o 
los pactados entre las partes de forma 
expresa como pago no salarial. 
A N  Auxilio 0-1 Valor Pagado por Auxilios No Salariales 1.0 
/NominaIndividual/Deven
gados/Auxilios/Auxilio/@A
uxilioNS 
  HuelgasLegales 
Utilizado para Todos los Elementos de 
Huelgas Legales de Devengos del 
Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/HuelgasLegales 
  HuelgaLegal Utilizado para Atributos de Huelga Legal 
del Documento E A  HuelgasLegales 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/HuelgasLegales/Hu
elgaLegal 

---

## Página 38

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 38 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE143  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador inicia la huelga legalmente 
declarada. 
A F 10 HuelgaLegal 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/HuelgasLegales/Hu
elgaLegal/@FechaInicio 
NIE144  FechaFIn 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador termina la huelga legalmente 
declarada. 
A F 10 HuelgaLegal 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/HuelgasLegales/Hu
elgaLegal/@FechaFIn 
NIE145  Cantidad 
número de días en los que el trabajador 
estuvo inactivo por huelga legalmente 
declarada. 
A N  HuelgaLegal 1-1 Cantidad de Dias 1.0 
/NominaIndividual/Deven
gados/HuelgasLegales/Hu
elgaLegal/@Cantidad 
  OtrosConceptos 
Utilizado para Todos los Elementos de 
Otros Conceptos de Devengos del 
Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/OtrosConceptos 
  OtroConcepto Utilizado para Atributos de Otro Concepto 
del Documento E A  OtrosConceptos 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/OtrosConceptos/Ot
roConcepto 
NIE146  DescripcionConcept
o 
Nombre del Concepto que corresponde a 
los demás pagos fijos o variables 
realizados al trabajador que remuneren 
en dinero o en especie como 
contraprestación directa del servicio, sea 
cualquiera la forma o denominación que 
se adopte. 
A A  OtroConcepto 1-1 Debe ir la Descripcion del Concepto 1.0 
/NominaIndividual/Deven
gados/OtroConceptos/Otr
oConcepto/@Descripcion
Concepto 

---

## Página 39

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 39 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE147  ConceptoS 
Valor de los demás pagos fijos o variables 
realizados al trabajador que remuneren 
en dinero o en especie como 
contraprestación directa del servicio, sea 
cualquiera la forma o denominación que 
se adopte (Salarial). 
A N  OtroConcepto 0-1 Valor Pagado por Conceptos Salariales 1.0 
/NominaIndividual/Deven
gados/OtroConceptos/Otr
oConcepto/@ConceptoS 
NIE148  ConceptoNS 
Valor de los demás pagos que 
ocasionalmente y por mera liberalidad 
recibe el trabajador del empleador, en 
dinero o en especie no para su beneficio, 
ni para enriquecer su patrimonio, sino 
para desempeñar a cabalidad sus 
funciones (No Salarial). 
A N  OtroConcepto 0-1 Valor Pagado por Conceptos No Salariales 1.0 
/NominaIndividual/Deven
gados/OtroConceptos/Otr
oConcepto/@ConceptoNS 
  Compensaciones 
Utilizado para Todos los Elementos de 
Compensaciones de Devengos del 
Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/Compensaciones 
  Compensacion Utilizado para Atributos de Compensacion 
del Documento E A  Compensaciones 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/Compensaciones/C
ompensacion 

---

## Página 40

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 40 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE149  CompensacionO 
Suma de dinero definido en el régimen de 
compensaciones como retribución 
mensual recibido por el asociado por la 
ejecución de su actividad material o 
inmaterial, la cual se fija teniendo en 
cuenta el tipo de labor desempeñada, el 
rendimiento o la productividad y la 
cantidad de trabajo aportado. El monto 
de la compensación ordinaria podrá ser 
una suma básica igual para todos los 
asociados (Ordinaria). 
A N  Compensacion 1-1 Valor Pagado por Compensaciones 
Ordinarias 1.0 
/NominaIndividual/Deven
gados/Compensaciones/C
ompensacion/@Compens
acionO 
NIE150  CompensacionE 
Los demás pagos adicionales a la 
Compensación Ordinaria que recibe el 
asociado como retribución por su trabajo, 
definidos en el régimen de 
compensaciones (Extraordinaria). 
A N  Compensacion 1-1 Valor Pagado por Compensaciones 
Extraordinarias 1.0 
/NominaIndividual/Deven
gados/Compensaciones/C
ompensacion/@Compens
acionE 
  BonoEPCTVs 
Utilizado para Todos los Elementos de 
Bonos Electronicos o de Papel de Servicio, 
Cheques, Tarjetas, Vales, etc de Devengos 
del Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/BonoEPCTVs 
  BonoEPCTV 
Utilizado para Atributos de Bono 
Electronico o de Papel de Servicio, 
Cheque, Tarjeta, Vale, etc del Documento 
E A  BonoEPCTVs 0-N Elemento Vacio 1.0 
/NominaIndividual/Deven
gados/BonoEPCTVs/Bono
EPCTV 

---

## Página 41

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 41 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE151  PagoS 
Valor que el trabajador recibe como 
contraprestación por el trabajo realizado, 
por medio de bonos electrónicos, 
recargas, cheques, vales. es decir, todo 
pago realizado en un medio diferente a 
dinero en efectivo o consignación de 
cuenta bancaria (Salarial). 
A N  BonoEPCTV 0-1 Concepto Salarial 1.0 
/NominaIndividual/Deven
gados/BonoEPCTVs/Bono
EPCTV/@PagoS 
NIE152  PagoNS 
Valor que el trabajador recibe como 
concepto no salarial, por medio de bonos 
electrónicos, recargas, cheques, vales. es 
decir, todo pago realizado en un medio 
diferente a dinero en efectivo o 
consignación de cuenta bancaria (No 
Salarial). 
A N  BonoEPCTV 0-1 Concepto No Salarial 1.0 
/NominaIndividual/Deven
gados/BonoEPCTVs/Bono
EPCTV/@PagoNS 
NIE153  PagoAlimentacionS 
Valor que el trabajador recibe como 
concepto no salarial, por medio de bonos 
electrónicos, recargas, cheques, vales. es 
decir, todo pago realizado en un medio 
diferente a dinero en efectivo o 
consignación de cuenta bancaria (Para 
Alimentación Salarial). 
A N  BonoEPCTV 0-1 Concepto Salarial 1.0 
/NominaIndividual/Deven
gados/BonoEPCTVs/Bono
EPCTV/@PagoAlimentacio
nS 

---

## Página 42

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 42 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE154  PagoAlimentacionN
S 
Valor que el trabajador recibe como 
concepto no salarial, por medio de bonos 
electrónicos, recargas, cheques, vales. es 
decir, todo pago realizado en un medio 
diferente a dinero en efectivo o 
consignación de cuenta bancaria (Para 
Alimentación No Salarial). 
A N  BonoEPCTV 0-1 Concepto No Salarial 1.0 
/NominaIndividual/Deven
gados/BonoEPCTVs/Bono
EPCTV/@PagoAlimentacio
nNS 
  Comisiones Utilizado para Todos los Elementos de 
Comisiones de Devengos del Documento G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/Comisiones 
NIE155  Comision 
Valor pagado al trabajador usualmente 
del área comercial, y de forma regular se 
liquida con un porcentaje sobre el 
importe de una operación, también se 
presenta como incentivo por el logro de 
objetivos. 
E N  Comisiones 0-N Valor Pagado por Comision 1.0 
/NominaIndividual/Deven
gados/Comisiones/Comisi
on 
  PagosTerceros 
Utilizado para Todos los Elementos de 
Pagos a Tercero de Devengos del 
Documento 
G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/PagosTerceros 
NIE193  PagoTercero Beneficios en cabeza del Trabjador que se 
pagan a un proveedor o tercero. E N  PagosTerceros 0-N Valor Pagado por Pago Tercero 1.0 
/NominaIndividual/Deven
gados/PagosTerceros/Pag
oTercero 
  Anticipos Utilizado para Todos los Elementos de 
Anticipos de Devengos del Documento G A  Devengados 0-1  1.0 /NominaIndividual/Deven
gados/Anticipos 
NIE194  Anticipo Anticipos de Nómina. E N  Anticipos 0-N Valor Pagado por Anticipo 1.0 /NominaIndividual/Deven
gados/Anticipos/Anticipo 

---

## Página 43

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 43 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE156  Dotacion 
De conformidad con lo previsto en el 
artículo 230 del Código Sustantivo del 
Trabajo, o la norma que lo modifique, 
adicione o sustituya, corresponde al valor 
que el empleador dispone para 
suministrar la dotación de sus 
trabajadores. 
E N  Devengados 0-1 Valor Pagado por Dotación 1.0 /NominaIndividual/Deven
gados/Dotacion 
NIE157  ApoyoSost 
Corresponde al valor no salarial que el 
patrocinador paga de forma mensual 
como ayuda o apoyo economía al 
aprendiz o practicante universitario 
durante su etapa lectiva y fase practica. 
E N  Devengados 0-1 Valor Pagado por Apoyo a Sostenimiento 1.0 /NominaIndividual/Deven
gados/ApoyoSost 
NIE158  Teletrabajo 
Valor que debe ser pagado al trabajador 
cuyo contrato indica expresamente que 
puede laborar mediante teletrabajo 
E N  Devengados 0-1 Valor Pagado por trabajo en Teletrabajo 1.0 /NominaIndividual/Deven
gados/Teletrabajo 
NIE159  BonifRetiro Valor establecido por mutuo acuerdo por 
retiro del Trabajador E N  Devengados 0-1 Valor Pagado por Retiro de la empresa 1.0 /NominaIndividual/Deven
gados/BonifRetiro 
NIE160  Indemnizacion Valor de Indemnizacion establecido por 
ley E N  Devengados 0-1 Valor Pagado por Indemnización 1.0 /NominaIndividual/Deven
gados/Indemnizacion 
NIE201  Reintegro 
Valor que le regresa la empresa al 
trabajador por una deducción mal 
realizada en otro pago de nomina 
E N  Devengados 0-1 Valor Pagado correspondiente a Reintegro 
por parte del empleador 1.0 /NominaIndividual/Deven
gados/Reintegro 
  Deducciones Utilizado para Todas las Deducciones del 
Documento G A  NominaIndividual 1-1 
Hace referencia al concepto de valor 
deducido de nómina señalado en el 
numeral 18, articulo 1 de la presente 
resolución. 
1.0 /NominaIndividual/Deduc
ciones 

---

## Página 44

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 44 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  Salud Utilizado para Atributos de Salud del 
Documento E A  Deducciones 1-1 Elemento Vacio 1.0 /NominaIndividual/Deduc
ciones/Salud 
NIE161  Porcentaje 
Debe corresponder al porcentaje de 
deducción de salud que paga el 
trabajador 
A N  Salud 1-1 Se debe colocar el Porcentaje que 
corresponda 1.0 
/NominaIndividual/Deduc
ciones/Salud/@Porcentaj
e 
NIE163  Deduccion 
El trabajador debe estar afiliado al 
sistema de salud. La cotización por salud 
que corresponde al 12.5% de la base del 
aporte, se hace en conjunto con la 
empresa. Ésta última aporta el 8.5%, y el 
empleado debe aportar el 4% restante. 
Ese 4% es el valor que se debe descontar 
(deducir) del total devengado a cargo del 
empleado.  
A N  Salud 1-1 Valor Pagado correspondiente a Salud por 
parte del trabajador 1.0 /NominaIndividual/Deduc
ciones/Salud/@Deduccion 
  FondoPension Utilizado para Atributos de Fondos de 
Pension del Documento E A  Deducciones 1-1 Elemento Vacio 1.0 /NominaIndividual/Deduc
ciones/FondoPension 
NIE164  Porcentaje 
Debe corresponder al porcentaje de 
deducción de fondo de pensión que paga 
el trabajador 
A N 4-6 FondoPension 1-1 Se debe colocar el Porcentaje que 
corresponda 1.0 
/NominaIndividual/Deduc
ciones/FondoPension/@P
orcentaje 

---

## Página 45

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 45 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE166  Deduccion 
El trabajador también debe estar afiliado 
al sistema de pensiones. La cotización por 
pensión está a cargo tanto de la empresa 
como del empleado. Del total del aporte 
(16%), la empresa aporta el 75% (12%) y 
el trabajador aporta el restante 25% (4%). 
Como el trabajador debe aportar un 4% 
por concepto de pensión, este valor se le 
descuenta (deduce) del valor devengado 
en el respectivo periodo (mes o 
quincena). 
A N  FondoPension 1-1 Valor Pagado correspondiente a Pension 
por parte del trabajador 1.0 
/NominaIndividual/Deduc
ciones/FondoPension/@D
educcion 
  FondoSP Utilizado para Atributos de Fondo de 
Seguridad Pensional del Documento E A  Deducciones 0-1 Elemento Vacio 1.0 /NominaIndividual/Deduc
ciones/FondoSP 
NIE167  Porcentaje 
Debe corresponder al porcentaje de 
deducción de fondo de seguridad 
pensional que paga el trabajador 
A N 4-6 FondoSP 0-1 Se debe colocar el Porcentaje que 
corresponda 1.0 
/NominaIndividual/Deduc
ciones/FondoSP/@Porcen
taje 
NIE168  DeduccionSP 
Todo trabajador que devengue un sueldo 
que sea igual o superior a 4 salarios 
mininos, debe aportar un 1% al Fondo de 
solidaridad pensional. 
A N  FondoSP 0-1 
Valor Pagado correspondiente a Fondo de 
Solidaridad Pensional por parte del 
trabajador 
1.0 
/NominaIndividual/Deduc
ciones/FondoSP/@Deducc
ionSP 
NIE169  PorcentajeSub 
Se debe colocar el Porcentaje que 
correspondiente al Fondo de Subsistencia 
correspondiente 
A N 4-6 FondoSP 0-1 
Se debe colocar el Porcentaje que 
correspondiente al Fondo de Subsistencia 
correspondiente 
1.0 
/NominaIndividual/Deduc
ciones/FondoSP/@Porcen
tajeSub 
NIE170  DeduccionSub Valor Pagado correspondiente a Fondo de 
Subsistencia por parte del trabajador A N  FondoSP 0-1 Valor Pagado correspondiente a Fondo de 
Subsistencia por parte del trabajador 1.0 
/NominaIndividual/Deduc
ciones/FondoSP/@Deducc
ionSub 

---

## Página 46

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 46 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  Sindicatos 
Utilizado para Todos los Elementos de 
Sindicatos de Deducciones del 
Documento 
G A  Deducciones 0-1  1.0 /NominaIndividual/Deduc
ciones/Sindicatos 
  Sindicato Utilizado para Atributos de Sindicato del 
Documento E A  Sindicatos 0-N Elemento Vacio 1.0 
/NominaIndividual/Deduc
ciones/Sindicatos/Sindicat
o 
NIE171  Porcentaje Porcentaje establecido en la ley o por 
estatutos del sindicato. A N  Sindicato 1-1 
Se debe colocar el Porcentaje que 
correspondiente a Aportes del Sindicato 
correspondiente 
1.0 
/NominaIndividual/Deduc
ciones/Sindicatos/Sindicat
o/@Porcentaje 
NIE172  Deduccion 
Las cuotas que los trabajadores 
sindicalizados deben aportar al sindicato 
al que estén afiliados, y siempre que 
medie autorización del empleado. 
A N  Sindicato 1-1 Valor Pagado correspondiente a Aportes del 
Sindicato por parte del trabajador 1.0 
/NominaIndividual/Deduc
ciones/Sindicatos/Sindicat
o/@Deduccion 
  Sanciones 
Utilizado para Todos los Elementos de 
Sanciones de Deducciones del 
Documento 
G A  Deducciones 0-1  1.0 /NominaIndividual/Deduc
ciones/Sanciones 
  Sancion Utilizado para Atributos de Sancion del 
Documento E A  Sanciones 0-N Elemento Vacio 1.0 /NominaIndividual/Deduc
ciones/Sanciones/Sancion 
NIE173  SancionPublic 
Valor por el del incumplimiento de una 
regla o norma de conducta obligatoria 
(Publica) 
A N  Sancion 1-1 Valor Pagado correspondiente a Sanción 
Pública por parte del trabajador 1.0 
/NominaIndividual/Deduc
ciones/Sanciones/Sancion
/@SancionPublic 
NIE174  SancionPriv 
Valor por el del incumplimiento de una 
regla o norma de conducta obligatoria 
(Privada o Ordinaria) 
A N  Sancion 1-1 Valor Pagado correspondiente a Sanción 
Privada por parte del trabajador 1.0 
/NominaIndividual/Deduc
ciones/Sanciones/Sancion
/@SancionPriv 
  Libranzas Utilizado para Todos los Elementos de 
Libranzas de Deducciones del Documento G A  Deducciones 0-1  1.0 /NominaIndividual/Deduc
ciones/Libranzas 

---

## Página 47

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 47 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  Libranza Utilizado para Atributos de Libranza del 
Documento E A  Libranzas 0-N Elemento Vacio 1.0 /NominaIndividual/Deduc
ciones/Libranzas/Libranza 
NIE175  Descripcion 
Nombre de la Libranza que corresponda a 
las cuotas que el empleado deba pagar a 
una entidad financiera, para la 
amortización de un crédito que le haya 
sido otorgado por libranza 
A A  Libranza 1-1 Debe ir la Descripcion de la Libranza 1.0 
/NominaIndividual/Deduc
ciones/Libranzas/Libranza
/@Descripcion 
NIE176  Deduccion 
Las cuotas que el empleado deba pagar a 
una entidad financiera, para la 
amortización de un crédito que le haya 
sido otorgado por libranza 
A N  Libranza 1-1 
Valor Pagado correspondiente a Aportes a 
Entidades Financieras por parte del 
trabajador 
1.0 
/NominaIndividual/Deduc
ciones/Libranzas/Libranza
/@Deduccion 
  PagosTerceros 
Utilizado para Todos los Elementos de 
Pagos a Tercero de Deducciones del 
Documento 
G A  Deducciones 0-1  1.0 
/NominaIndividual/Deduc
ciones/PagosTerceros 
NIE195  PagoTercero Deducciones en cabeza del Trabjador que 
se pagan a un proveedor o tercero. E N  PagosTerceros 0-N Valor Pagado por Pago Tercero 1.0 
/NominaIndividual/Deduc
ciones/PagosTerceros/Pag
oTercero 
  Anticipos Utilizado para Todos los Elementos de 
Anticipos de Deducciones del Documento G A  Deducciones 0-1  1.0 
/NominaIndividual/Deduc
ciones/Anticipos 
NIE196  Anticipo Deduccion por Anticipos de Nómina. E N  Anticipos 0-N Valor Pagado por Anticipo 1.0 
/NominaIndividual/Deduc
ciones/Anticipos/Anticipo 
  OtrasDeducciones Utilizado para Todos los Elementos de 
Otras Deducciones del Documento G A  Deducciones 0-1  1.0 
/NominaIndividual/Deduc
ciones/OtrasDeducciones 

---

## Página 48

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 48 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE197  OtraDeduccion Otro tipo de deducción dentro de la 
Nomina. E N  OtrasDeducciones 0-N Valor Pagado por Otra Deducción 1.0 
/NominaIndividual/Deduc
ciones/OtrasDeducciones/
OtraDeduccion 
NIE198  PensionVoluntaria 
Valor correspondiente al ahorro que hace 
el trabajador para complementar su 
pension obligatoria o cumplir metas 
especificas. 
E N  Deducciones 0-1 
Valor Pagado correspondiente al ahorro que 
hace el trabajador para complementar su 
pension obligatoria o cumplir metas 
especificas. 
1.0 /NominaIndividual/Deduc
ciones/PensionVoluntaria 
NIE177  RetencionFuente 
Si hubiere lugar, la empresa deberá 
calcular y retener al empleado el valor 
correspondiente a retención en la fuente 
por ingresos laborales. Este valor será 
declarado y consignado en la respectiva 
declaración mensual de retención en la 
fuente. 
E N  Deducciones 0-1 Valor Pagado correspondiente a Retención 
en la Fuente por parte del trabajador 1.0 /NominaIndividual/Deduc
ciones/RetencionFuente 
NIE179  AFC Corresponde a (Ahorro Fomento a la 
contruccion)  E N  Deducciones 0-1 Valor Pagado correspondiente a AFC por 
parte del trabajador 1.0 /NominaIndividual/Deduc
ciones/AFC 
NIE180  Cooperativa 
Las cuotas o aportes que los empleados 
hagan a las cooperativas legalmente 
constituidas 
E N  Deducciones 0-1 Valor Pagado correspondiente a 
Cooperativas por parte del trabajador 1.0 /NominaIndividual/Deduc
ciones/Cooperativa 
NIE181  EmbargoFiscal 
Los embargos ordenados por autoridad 
judicial competente contra los empleados 
deben ser descontados de la nómina por 
la empresa y consignarlos en la cuenta 
que el juez haya ordenado. 
E N  Deducciones 0-1 Valor Pagado correspondiente aEmbargos 
Fiscales por parte del trabajador 1.0 /NominaIndividual/Deduc
ciones/EmbargoFiscal 

---

## Página 49

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 49 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIE182  PlanComplementari
os 
 Valor de planes complementarios de 
salud al que el trabajador se encuentran 
afiliado, siempre que medie autorización 
del empleado. 
E N  Deducciones 0-1 Valor Pagado correspondiente a Planes 
Complementarios por parte del trabajador 1.0 
/NominaIndividual/Deduc
ciones/PlanComplementar
ios 
NIE183  Educacion  Valor de servicios educativos  que el 
trabajador autorice descuento. E N  Deducciones 0-1 Valor Pagado correspondiente a Conceptos 
Educativos por parte del trabajador 1.0 /NominaIndividual/Deduc
ciones/Educacion 
NIE184  Reintegro 
Valor que le regresa el trabajador a la 
empresa por un devengo mal realizado en 
otro pago de nómina 
E N  Deducciones 0-1 Valor Pagado correspondiente a Reintegro 
por parte del trabajador 1.0 /NominaIndividual/Deduc
ciones/Reintegro 
NIE185  Deuda 
Valor que se deba pagar por las 
obligaciones que el empleado tenga con 
su empresa, como puede ser un crédito 
que ésta le haya otorgado, o como 
compensación por algún perjuicio o 
detrimento económico que el empleado 
le haya causado a la empresa. 
E N  Deducciones 0-1 Valor Pagado correspondiente a Deuda con 
la Empresa por parte del trabajador 1.0 /NominaIndividual/Deduc
ciones/Deuda 
NIE186  Redondeo Se utiliza para cuando se utilice el 
Redondeo en el Documento E N  NominaIndividual 0-1 Definido en el numeral 1.1.1 1.0 /NominaIndividual/Redon
deo 
NIE187  DevengadosTotal Valor total de la Suma de todos los 
Devengados del Documento E N  NominaIndividual 1-1 Debe ir el valor Total de Todos los 
Devengados del Trabajador 1.0 /NominaIndividual/Deven
gadosTotal 
NIE188  DeduccionesTotal Valor total de la Suma de todas las 
Deducciones del Documento E N  NominaIndividual 1-1 Debe ir el valor Total de Todos las 
Deducciones del Trabajador 1.0 /NominaIndividual/Deduc
cionesTotal 
NIE189  ComprobanteTotal Debe ir el total de: Devengados - 
Deducciones E N  NominaIndividual 1-1 Debe ser la Diferencia entre 
DevengadosTotal - DeduccionesTotal 1.0 /NominaIndividual/Compr
obanteTotal 

---

## Página 50

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 50 de 269 
 
3.2. Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica: NominaIndividualDeAjuste. 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  NominaIndividualDe
Ajuste 
Nota de Ajuste de Documento Soporte de 
Pago de Nómina Electrónica - 
NominaIndividualDeAjuste (raíz) 
    1-1  1.0 /NominaIndividualDeAjust
e 
NIAE001 ext UBLExtensions Grupo correspondiente a la Firma Digital 
del Documento (Signature) G A  NominaIndividual
DeAjuste 1-1 
Solamente puede haber una ocurrencia de 
un grupo UBLExtensions conteniendo el 
grupo ds:Signature. Ver definición en 
numeral 3.6 
1.0 /NominaIndividualDeAjust
e/ext:UBLExtensions 
NIAE214  TipoNota 
Corresponde al tipo de Nota de Ajuste de 
Documento Soporte de Pago de Nómina 
Electrónica que se desee implementar 
E N 1 NominaIndividual
DeAjuste 1-1 Se debe colocar el Codigo de la tabla 5.5.8 1.0 /NominaIndividualDeAjust
e/TipoNota 
  Reemplazar 
Utilizado para todo el contenido 
correspondiente al evento de Reemplazar 
Documento 
G A  NominaIndividual
DeAjuste 0-1  1.0 /NominaIndividualDeAjust
e/Reemplazar 
  ReemplazandoPrede
cesor 
Utilizado para Atributos de Documento 
Predecesor a Reemplazar E A  Reemplazar 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Reemplaza
ndoPredecesor 
NIAE190  NumeroPred 
Debe corresponder al Numero de 
Documento Soporte de Pago de Nómina 
Electrónica a Reemplazar 
A A  ReemplazandoPre
decesor 1-1 Debe ir el Numero de documento a 
Reemplazar 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Reemplaza
ndoPredecesor/@Numero
Pred 
NIAE191  CUNEPred 
Debe corresponder al CUNE del 
Documento Soporte de Pago de Nómina 
Electrónica a Reemplazar 
A A  ReemplazandoPre
decesor 1-1 Debe ir el CUNE del documento a 
Reemplazar 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Reemplaza
ndoPredecesor/@CUNEPr
ed 

---

## Página 51

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 51 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE192  FechaGenPred 
Debe corresponder a la Fecha de Emision 
del Documento Soporte de Pago de 
Nómina Electrónica a Reemplazar 
A F 10 ReemplazandoPre
decesor 1-1 Debe ir la fecha del documento a 
Reemplazar, en formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Reemplaza
ndoPredecesor/@FechaG
enPred 
  Periodo Utilizado para Atributos del Periodo 
Generación del Documento E A  Reemplazar 1-1 Elemento Vacio 1.0 /NominaIndividualDeAjust
e/Reemplazar/Periodo 
NIAE002  FechaIngreso 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz presenta ingreso o 
vinculación a la nómina del reportante. 
(en caso de tener mas de un ingreso en el 
mes, se debe reportar la primera fecha en 
la que se presenta esta novedad en el 
mes que se esta reportando). 
A F 10 Periodo 1-1 
Se debe indicar la Fecha de Ingreso del 
trabajador a la empresa, en formato AAAA-
MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaIngreso 
NIAE003  FechaRetiro 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz presenta retiro de 
la nómina del reportante.(en caso de 
tener mas de un retiro en el mes, se debe 
reportar la ultima fecha en la que se 
presenta esta novedad en el mes que se 
esta reportando). 
A F 10 Periodo 0-1 
Se debe indicar la Fecha de Retiro del 
trabajador a la empresa, en formato AAAA-
MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaRetiro 
NIAE004  FechaLiquidacionIni
cio Fecha de inicio de Liquidación de Nómina A F 10 Periodo 1-1 
Se debe indicar la Fecha de Inicio del 
Periodo de Liquidación del documento, en 
formato AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaLiquidacionInicio 

---

## Página 52

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 52 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE005  FechaLiquidacionFin Fecha fin de Liquidación de Nómina A F 10 Periodo 1-1 
Se debe indicar la Fecha de Fin del Periodo 
de Liquidación del documento, en formato 
AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaLiquidacionFin 
NIAE006  TiempoLaborado Cantidad de Tiempo que lleva laborando 
el Trabajador en la empresa A A  Periodo 1-1 Definido en el numeral 8.4.1, debe ser 
mayor o gual a 1. 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
TiempoLaborado 
NIAE008  FechaGen Fecha de emisión: Fecha de emisión del 
documento A F 10 Periodo 1-1 
Debe ir la fecha de emision del documento. 
Considerando zona horaria de Colombia (-
5), en formato AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaGen 
  NumeroSecuenciaX
ML 
Utilizado para Atributos de Numero de 
Secuencia del Documento XML E A  Reemplazar 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/NumeroSec
uenciaXML 
NIAE009  CodigoTrabajador Codigo del Trabajador A A  NumeroSecuencia
XML 0-1 Campo Opcional queda a manejo Interno 
del Empleador. 1.0 
/NominaIndividualDeAjust
e/Reemplazar/NumeroSec
uenciaXML/@CodigoTrab
ajador 
NIAE010  Prefijo Prefijo del documento, depende de las 
sucursales que posea el Empleador A A  NumeroSecuencia
XML 0-1 Debe corresponder a un Prefijo elegido por 
el Emisor del documento 1.0 
/NominaIndividualDeAjust
e/Reemplazar/NumeroSec
uenciaXML/@Prefijo 
NIAE011  Consecutivo Debe corresponder a un consecutivo 
manejado por el Empleador A N  NumeroSecuencia
XML 1-1 Debe corresponder a un Consecutivo 
elegido por el Emisor del documento 1.0 
/NominaIndividualDeAjust
e/Reemplazar/NumeroSec
uenciaXML/@Consecutivo 
NIAE012  Numero Debe corresponder al Prefijo y 
consecutivo manejado por el Empleador A A  NumeroSecuencia
XML 1-1 
No se permiten caracteres adicionales como 
espacios o guiones. Prefijo + Número 
consecutivo del documento 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/NumeroSec
uenciaXML/@Numero 

---

## Página 53

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 53 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  LugarGeneracionXM
L 
Utilizado para Atributos del Lugar de 
Generacion del Documento XML E A  Reemplazar 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/LugarGener
acionXML 
NIAE013  Pais Codigo del país donde se genera el 
documento A A 2 LugarGeneracionX
ML 1-1 Se debe colocar el Codigo alfa-2 de la tabla 
5.4.1 1.0 
/NominaIndividualDeAjust
e/Reemplazar/LugarGener
acionXML/@Pais 
NIAE014  DepartamentoEstad
o 
Código del departamento donde se 
genera el documento A N 2 LugarGeneracionX
ML 1-1 Se debe colocar el Codigo de la tabla 5.4.2 1.0 
/NominaIndividualDeAjust
e/Reemplazar/LugarGener
acionXML/@Departament
oEstado 
NIAE015  MunicipioCiudad Código del municipio o ciudad donde se 
genera el documento A N 5 LugarGeneracionX
ML 1-1 Se debe colocar el Codigo de la tabla 5.4.3 1.0 
/NominaIndividualDeAjust
e/Reemplazar/LugarGener
acionXML/@MunicipioCiu
dad 
NIAE016  Idioma Codigo del país donde se genera el 
documento A A 2 LugarGeneracionX
ML 1-1 
Se debe colocar el Codigo ISO 639-1 de la 
tabla 5.3.1. Para Colombia se debe colocar 
"es" (Español, Castellano) 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/LugarGener
acionXML/@Idioma 
  ProveedorXML Utilizado para Atributos del Proveedor del 
Documento XML E A  Reemplazar 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML 
NIAE205  RazonSocial 
Debe corresponder al Nombre de la 
Razón Social del Proveedor de Soluciones 
Tecnológicas 
A A  ProveedorXML 0-1 Debe ir el Nombre o Razón Social del 
Proveedor de Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@RazonSocial 
NIAE206  PrimerApellido Primer Apellido del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Debe ir el Primer Apellido del Proveedor de 
Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@PrimerApellido 

---

## Página 54

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 54 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE207  SegundoApellido Segundo Apellido del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Debe ir el Segundo Apellido del Proveedor 
de Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@SegundoApellido 
NIAE208  PrimerNombre Primer Nombre del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Debe ir el Primer Nombre del Proveedor de 
Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@PrimerNombre 
NIAE209  OtrosNombres Otros Nombres del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Deben ir los Otros Nombres del Proveedor 
de Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@OtrosNombres 
NIAE017  NIT 
Debe corresponder al NIT del Proveedor 
de Soluciones Tecnologicas que realiza el 
DE 
A N  ProveedorXML 1-1 
Se debe colocar el NIT sin guiones ni DV de 
la empresa dueña del Software que genera 
el Documento, debe estar registrado en la 
DIAN 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@NIT 
NIAE018  DV 
Debe corresponder al DV del NIT del 
Proveedor de Soluciones Tecnologicas 
que realiza el DE 
A N 2 ProveedorXML 1-1 
Se debe colocar el DV de la empresa dueña 
del Software que genera el Documento, 
debe estar registrado en la DIAN 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@DV 
NIAE019  SoftwareID 
Identificador Software: Identificador del 
software habilitado para la emisión de 
nóminas 
A A  ProveedorXML 1-1 
Identificador del software asignado cuando 
el software se activa en el Sistema del 
Documento Soporte de Pago de Nómina 
Electrónica, debe corresponder a un 
software autorizado para este Emisor 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@SoftwareID 
NIAE020  SoftwareSC 
Huella del software que autorizó la DIAN 
al Obligado a Generar Nómina Electrónica 
o al Proveedor de Soluciones Tecnológicas 
A A  ProveedorXML 1-1 Definido en el numeral 8.3 1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@SoftwareSC 

---

## Página 55

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 55 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE021  CodigoQR Debe poseer información detallada del 
Documento Electronico E A  NominaIndividual
DeAjuste 1-1 
Debe  corresponder a la siguiente URL 
“https://catalogo-
vpfe.dian.gov.co/document/searchqr?docu
mentkey=CUNE”  donde la palabra CUNE 
debe ser reemplazada por el CUNE del 
documento electrónico 
1.0 /NominaIndividualDeAjust
e/Reemplazar/CodigoQR 
  InformacionGeneral Utilizado para Atributos de Información 
General Documento E A  Reemplazar 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral 
NIAE022  Version 
Versión base de Schema XML usada para 
crear este perfil 
(NominaIndividualDeAjuste) 
A A  InformacionGener
al 1-1 
Debe ir el literal: "V1.0: Nota de Ajuste de 
Documento Soporte de Pago de Nómina 
Electrónica" 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@Version 
NIAE023  Ambiente Tipo de Ambiente de Emision del 
Documento: Habilitacion o Produccion A N 1 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.1.1 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@Ambiente 
NIAE202  TipoXML Tipo de XML del Documento A N 2 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.5.7 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@TipoXML 
NIAE024  CUNE 
CUNE:  Código Único de Documento 
Soporte de Pago de Nómina Electrónica. 
Elemento que verifica la integridad de la 
información recibida 
A A  InformacionGener
al 1-1 Definido en el numeral 8.1 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@CUNE 
NIAE025  EncripCUNE 
Identificador del esquema de 
identificación. Algoritmo utilizado para el 
cáculo del CUNE, SHA-384 
A A 7 InformacionGener
al 1-1 Debe ir la palabra "CUNE-SHA384" 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@EncripCUNE 

---

## Página 56

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 56 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE026  FechaGen Fecha de emisión: Fecha de emisión del 
documento A F 10 InformacionGener
al 1-1 
Debe ir la fecha de emision del documento. 
Considerando zona horaria de Colombia (-
5), en formato AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@FechaGen 
NIAE027  HoraGen Hora de emisión: hora de emisión del 
documento A H 14 InformacionGener
al 1-1 
Debe ir la hora de emision del documento. 
Considerando zona horaria de Colombia (-
5), en formato HH:MM:SSdhh:mm 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@HoraGen 
NIAE029  PeriodoNomina Corresponde al Codigo de Periodo de 
Nómina A N 1 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.5.1 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@PeriodoNomi
na 
NIAE030  TipoMoneda Tipo de Moneda utilizada en el 
documento A A 3 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.3.2. 
Para Colombia se debe colocar "COP" 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@TipoMoneda 
NIAE200  TRM 
Tasa Representativa del mercado. 
Corresponde a la tasa de cambio de la 
moneda utilizada en el documento en el 
Campo “TipoMoneda” a Pesos 
Colombianos. 
A N  InformacionGener
al 0-1 
Se debe colocar la tasa de cambio de la 
moneda utilizada en el documento en el 
Campo “TipoMoneda” a Pesos 
Colombianos. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@TRM 
NIAE031  Notas Campo de libre uso para Observaciones 
en el documento E A  NominaIndividual
DeAjuste 0-N Información adicional: Texto libre, relativo 
al documento 1.0 /NominaIndividualDeAjust
e/Reemplazar/Notas 
  Empleador Utilizado para Atributos del Empleador o 
Emisor del Documento E A  Reemplazar 1-1 Elemento Vacio 1.0 /NominaIndividualDeAjust
e/Reemplazar/Empleador 
NIAE032  RazonSocial Debe corresponder al Nombre de la 
Razón Social del Empleador A A  Empleador 0-1 Debe ir el Nombre o Razón Social del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@RazonSocial 

---

## Página 57

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 57 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE210  PrimerApellido Primer Apellido del Empleador A A 60 Empleador 0-1 Debe ir el Primer Apellido del Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@PrimerApellido 
NIAE211  SegundoApellido Segundo Apellido del Empleador A A 60 Empleador 0-1 Debe ir el Segundo Apellido del Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@SegundoApellido 
NIAE212  PrimerNombre Primer Nombre del Empleador A A 60 Empleador 0-1 Debe ir el Primer Nombre del Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@PrimerNombre 
NIAE213  OtrosNombres Otros Nombres del Empleador A A 60 Empleador 0-1 Deben ir los Otros Nombres del Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@OtrosNombres 
NIAE033  NIT Debe corresponder al NIT del Empleador 
que realiza el DE A N  Empleador 1-1 Debe ir el NIT del Empleador sin guiones ni 
DV 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@NIT 
NIAE034  DV Debe corresponder al DV del NIT del 
Empleador que realiza el DE A N 2 Empleador 1-1 Debe ir el DV del Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@DV 
NIAE035  Pais 
Codigo del país donde donde se 
encuentra ubicado el empleador el mes 
que se esta reportando 
A A 2 Empleador 1-1 Se debe colocar el Codigo alfa-2 de la tabla 
5.4.1 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@Pais 
NIAE036  DepartamentoEstad
o 
Código del departamento donde se 
encuentra ubicado el empleador el mes 
que se esta reportando 
A N 2 Empleador 1-1 Se debe colocar el Codigo de la tabla 5.4.2 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@DepartamentoEstado 
NIAE037  MunicipioCiudad 
Código del municipio o ciudad donde se 
encuentra ubicado el empleador el mes 
que se esta reportando 
A N 5 Empleador 1-1 Se debe colocar el Codigo de la tabla 5.4.3 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@MunicipioCiudad 

---

## Página 58

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 58 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE038  Direccion Debe corresponder a la dirección del 
lugar físico de expedición del documento.  A A  Empleador 1-1 Debe ir la Dirección Fisica del Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@Direccion 
  Trabajador Utilizado para Atributos del Trabajador o 
Receptor del Documento E A  Reemplazar 1-1 Elemento Vacio 1.0 /NominaIndividualDeAjust
e/Reemplazar/Trabajador 
NIAE041  TipoTrabajador 
Código del tipo de trabajador del 
Ministerio de salud. Aportes a Seguridad 
Social de Activos. 
A N 2 Trabajador 1-1 
Corresponde a la clasificación de PILA para 
conocer en que calidad se realizan las 
cotizaciones a la seguridad social. Se debe 
colocar el Codigo de la tabla 5.5.3 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@TipoTrabajador 
NIAE042  SubTipoTrabajador 
Código del Sub tipo de trabajador del 
Ministerio de salud. Aportes a Seguridad 
Social de Activos 
A N 2 Trabajador 1-1 
Corresponde a una sub clasificación de PILA 
para conocer en que calidad se realizan las 
cotizaciones a la seguridad social. Se debe 
colocar el Codigo de la tabla 5.5.4 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@SubTipoTrabajador 
NIAE043  AltoRiesgoPension 
Si el trabajador desarrollo durante el 
presente periodo alguna de las 
actividades descritas en el Decreto 2090 
de 2003, o la norma que lo modifique, 
adicione o sustituya. 
A B 4-5 Trabajador 1-1 Se debe colocar "true" o "false" 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@AltoRiesgoPension 
NIAE044  TipoDocumento 
Tipo de documento de identificación que 
actualmente tiene el trabajador, aprendiz 
o pasante. 
A N 2 Trabajador 1-1 Se debe colocar el Codigo de la tabla 5.2.1 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@TipoDocumento 
NIAE045  NumeroDocumento Numero de identificación que 
actualmente el trabajador o aprendiz A N  Trabajador 1-1 Debe ir el Numero de documento del 
trabajador, sin puntos ni comas ni espacios 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@NumeroDocumento 

---

## Página 59

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 59 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE046  PrimerApellido Primer Apellido del trabajador o aprendiz A A 60 Trabajador 1-1 Debe ir el Primer Apellido del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@PrimerApellido 
NIAE047  SegundoApellido Segundo Apellido del trabajador o 
aprendiz A A 60 Trabajador 1-1 Debe ir el Segundo Apellido del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@SegundoApellido 
NIAE048  PrimerNombre Primer Nombre del trabajador o aprendiz A A 60 Trabajador 1-1 Debe ir el Primer Nombre del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@PrimerNombre 
NIAE049  OtrosNombres Otros Nombres del trabajador o aprendiz A A 60 Trabajador 0-1 Deben ir los Otros Nombres del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@OtrosNombres 
NIAE050  LugarTrabajoPais 
Código del país actual donde se 
encontraba ubicado el trabajador o 
aprendiz en el mes reportado. 
A N 3 Trabajador 1-1 Se debe colocar el Codigo alfa-2 de la tabla 
5.4.1 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@LugarTrabajoPais 
NIAE051  LugarTrabajoDepart
amentoEstado 
Código del departamento actual donde se 
encontraba ubicado el trabajador o 
aprendiz en el mes reportado. 
A N 2 Trabajador 1-1 Se debe colocar el Codigo de la tabla 5.4.2 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@LugarTrabajoDepartam
entoEstado 
NIAE052  LugarTrabajoMunici
pioCiudad 
Código del municipio o ciudad actual 
donde se encontraba ubicado el 
trabajador o aprendiz en el mes 
reportado. 
A N 5 Trabajador 1-1 Se debe colocar el Codigo de la tabla 5.4.3 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@LugarTrabajoMunicipio
Ciudad 
NIAE053  LugarTrabajoDirecci
on 
Debe corresponder a la dirección del 
lugar físico donde vive el empleado. A A  Trabajador 1-1 Debe ir la Dirección Fisica del Trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@LugarTrabajoDireccion 

---

## Página 60

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 60 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE056  SalarioIntegral 
Si el trabajador tiene un salario integral, el 
cual es el tipo de remuneración que 
incluye todos los conceptos que puedan 
constituir salario en un solo monto o pago 
(prestaciones sociales y recargos 
nocturno, dominical y festivo, y el trabajo 
extra) y que sea superior a 10 SMLMV 
mas un 30% correspondiente a factor 
prestacional. 
A B 4-5 Trabajador 1-1 Se debe colocar "true" o "false" 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@SalarioIntegral 
NIAE061  TipoContrato Tipo de Contrato que posee el empleado 
con el Empleador A N 1 Trabajador 1-1 Se debe colocar el Codigo de la tabla 5.5.2 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@TipoContrato 
NIAE062  Sueldo 
Corresponde al valor que el empleador 
paga de forma periódica al trabajador 
como contraprestación por el trabajo 
realizado, este puede ser fijo o variable de 
acuerdo a la unidad de tiempo en que las 
partes hayan acordado el pago, teniendo 
como base el día o la hora trabajada. 
A N  Trabajador 1-1 Se debe colocar el Sueldo Base que el 
Trabajdor tiene en la empresa 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@Sueldo 
NIAE063  CodigoTrabajador Codigo del Trabajador A A  Trabajador 0-1 Campo Opcional queda a manejo Interno 
del Empleador. 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador
/@CodigoTrabajador 
  Pago Utilizado para Atributos del Pago del 
Documento E A  Reemplazar 1-1 Elemento Vacio 1.0 /NominaIndividualDeAjust
e/Reemplazar/Pago 
NIAE064  Forma Formas de Pago del Documento A N 1 Pago 1-1 Se debe colocar el Codigo de la tabla 5.3.3.1 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@For
ma 

---

## Página 61

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 61 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE065  Metodo Metodos de Pago del Documento A N 2 Pago 1-1 Se debe colocar el Codigo de la tabla 5.3.3.2 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@Me
todo 
NIAE066  Banco 
Nombre de Entidad Bancaria del 
Empleado donde se realiza la 
consignación 
A A  Pago 0-1 
Se debe colocar el nombre de la entidad 
bancaria donde el trabajador tiene su 
cuenta para pago de nómina. Si el Metodo 
de Pago se realiza de forma Bancaria, este 
campo es obligatorio. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@Ba
nco 
NIAE067  TipoCuenta Tipo de Cuenta Bancaria del Empleado 
donde se realiza la consignación A A  Pago 0-1 
Se debe colocar el tipo de cuenta que el 
trabajador tiene para pago de nómina. Si el 
Metodo de Pago se realiza de forma 
Bancaria, este campo es obligatorio. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@Tip
oCuenta 
NIAE068  NumeroCuenta 
Numero de Cuenta Bancaria del 
Empleado donde se realiza la 
consignación 
A A  Pago 0-1 
Se debe colocar el número de la cuenta que 
el trabajador tiene para pago de nomina. Si 
el Metodo de Pago se realiza de forma 
Bancaria, este campo es obligatorio. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@Nu
meroCuenta 
  FechasPagos Utilizado para Todos los Elementos de 
Fechas de Pagos del Documento G A  Reemplazar 1-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/FechasPago
s 
NIAE203  FechaPago Fecha de Pago de la Nómina E F 10 FechasPagos 1-N 
Debe ir la fecha de pago del documento. 
Considerando zona horaria de Colombia (-
5), en formato AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/FechasPago
s/FechaPago 
  Devengados Utilizado para Todos los Devengos del 
Documento G A  Reemplazar 1-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s 

---

## Página 62

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 62 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  Basico Utilizado para Atributos Basicos de 
Devengos del Documento E A  Devengados 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Basico 
NIAE069  DiasTrabajados 
Número de días que el trabajador o 
aprendiz efectivamente estuvo 
ejecutando sus labores en la empresa. 
A N 1-2 Basico 1-1 Cantidad de dias laborados durante el 
Periodo de Pago 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Basico/@DiasTrabajados 
NIAE070  SueldoTrabajado 
Corresponde al valor que el empleador 
paga de forma periódica al trabajador 
como contraprestación por el trabajo 
realizado, este puede ser fijo o variable de 
acuerdo a la unidad de tiempo en que las 
partes hayan acordado el pago, teniendo 
como base el día o la hora trabajada. 
A N  Basico 1-1 
Valor Base o Sueldo del trabajador según lo 
estipulado en su contrato. Corresponde al 
Sueldo Trabajado por los días laborados. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Basico/@SueldoTrabaja
do 
  Transporte Utilizado para Atributos de Transporte de 
Devengos del Documento E A  Devengados 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Transporte 
NIAE071  AuxilioTransporte 
Parte de los viáticos pagado al trabajador 
correspondientes a medios de transporte 
y/o los gastos de representación. 
A N  Transporte 0-1 Valor de Auxilio de Transporte que recibe el 
trabajador por ley, según aplique 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Transporte/@AuxilioTra
nsporte 
NIAE072  ViaticoManuAlojS 
Parte de los viáticos pagado al trabajador 
correspondientes a manutención y/o 
alojamiento. 
A N  Transporte 0-1 Valor de Viaticos, Manutención y 
Alojamiento de carácter Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Transporte/@ViaticoMa
nuAlojS 

---

## Página 63

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 63 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE073  ViaticoManuAlojNS 
Parte de los viáticos pagado al trabajador 
correspondientes a manutención y/o 
alojamiento No Salariales. 
A N  Transporte 0-1 Valor de Viaticos, Manutención y 
Alojamiento de carácter No Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Transporte/@ViaticoMa
nuAlojNS 
  HEDs 
Utilizado para Todos los Elementos de 
Horas Extras Diarias de Devengos del 
Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs 
  HED Utilizado para Atributos de Horas Extras 
Diarias de Devengos del Documento E A  HEDs 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED 
NIAE074  HoraInicio Hora de inicio de Hora Extra Diurna A H 19 HED 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@HoraInicio 
NIAE075  HoraFin Hora de fin de Hora Extra Diurna A H 19 HED 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@HoraFin 
NIAE076  Cantidad Cantidad de Horas Extra Diurna A N  HED 1-1 Cantidad de Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@Cantidad 
NIAE077  Porcentaje Porcentaje al cual corresponde el calculo 
de 1 hora Extra Diurna A N 4-6 HED 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@Porcentaje 
NIAE078  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HED 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@Pago 

---

## Página 64

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 64 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  HENs 
Utilizado para Todos los Elementos de 
Horas Extras Nocturnas de Devengos del 
Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs 
  HEN Utilizado para Atributos de Horas Extras 
Nocturnas de Devengos del Documento E A  HENs 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN 
NIAE079  HoraInicio Hora de inicio de Hora Extra Nocturna A H 19 HEN 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@HoraInicio 
NIAE080  HoraFin Hora de fin de Hora Extra Nocturna A H 19 HEN 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@HoraFin 
NIAE081  Cantidad Cantidad de Horas Extras Nocturnas A N  HEN 1-1 Cantidad de Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@Cantidad 
NIAE082  Porcentaje Porcentaje al cual corresponde el calculo 
de 1 hora Extra Nocturna A N 4-6 HEN 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@Porcentaje 
NIAE083  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HEN 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@Pago 
  HRNs 
Utilizado para Todos los Elementos de 
Horas Recargo Nocturno de Devengos del 
Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs 
  HRN Utilizado para Atributos de Horas Recargo 
Nocturno de Devengos del Documento E A  HRNs 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN 

---

## Página 65

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 65 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE084  HoraInicio Hora de inicio de Hora Recargo Nocturno A H 19 HRN 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@HoraInicio 
NIAE085  HoraFin Hora de fin de Hora Recargo Nocturno A H 19 HRN 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@HoraFin 
NIAE086  Cantidad Cantidad de Horas Recargo Nocturno A N  HRN 1-1 Cantidad de Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@Cantidad 
NIAE087  Porcentaje Porcentaje al cual corresponde el calculo 
de 1 hora Recargo Nocturno A N 4-6 HRN 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@Porcentaje 
NIAE088  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HRN 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@Pago 
  HEDDFs 
Utilizado para Todos los Elementos de 
Horas Extras Diarias Dominicales y 
Festivas de Devengos del Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs 
  HEDDF 
Utilizado para Atributos de Horas Extras 
Diarias Dominicales y Festivas de 
Devengos del Documento 
E A  HEDDFs 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF 
NIAE089  HoraInicio Hora de inicio de Horas Extras Diurnas 
Dominical y Festivos A H 19 HEDDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@HoraI
nicio 

---

## Página 66

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 66 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE090  HoraFin Hora de fin de Horas Extras Diurnas 
Dominical y Festivos A H 19 HEDDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@Hora
Fin 
NIAE091  Cantidad Cantidad de Horas Extras Diurnas 
Dominical y Festivos A N  HEDDF 1-1 Cantidad de Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@Canti
dad 
NIAE092  Porcentaje 
Porcentaje al cual corresponde el calculo 
de 1 Hora Extra Diurna Dominical y 
Festivo 
A N 4-6 HEDDF 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@Porce
ntaje 
NIAE093  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HEDDF 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@Pago 
  HRDDFs 
Utilizado para Todos los Elementos de 
Horas Recargo Diarias Dominicales y 
Festivas de Devengos del Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs 
  HRDDF 
Utilizado para Atributos de Horas Recargo 
Diarias Dominicales y Festivas del 
Documento 
E A  HRDDFs 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF 
NIAE094  HoraInicio Hora de inicio de Horas Recargo Diurno 
Dominical y Festivos A H 19 HRDDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@HoraI
nicio 

---

## Página 67

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 67 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE095  HoraFin Hora de fin de Horas Recargo Diurno 
Dominical y Festivos A H 19 HRDDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@Hora
Fin 
NIAE096  Cantidad Cantidad de Horas Recargo Diurno 
Dominical y Festivos A N  HRDDF 1-1 Cantidad de Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@Canti
dad 
NIAE097  Porcentaje 
Porcentaje al cual corresponde el calculo 
de 1 Hora Recargo Diurno Dominical y 
Festivos 
A N 4-6 HRDDF 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@Porc
entaje 
NIAE098  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HRDDF 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@Pago 
  HENDFs 
Utilizado para Todos los Elementos de 
Horas Extras Nocturnas Dominicales y 
Festivas de Devengos del Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs 
  HENDF 
Utilizado para Atributos de Horas Extras 
Nocturnas Dominicales y Festivas del 
Documento 
E A  HENDFs 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF 
NIAE099  HoraInicio Hora de inicio de Horas Extras Nocturna 
Dominical y Festivos A H 19 HENDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@HoraI
nicio 

---

## Página 68

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 68 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE100  HoraFin Hora de fin de Horas Extras Nocturna 
Dominical y Festivos A H 19 HENDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@Hora
Fin 
NIAE101  Cantidad Cantidad de Horas Extras Nocturna 
Dominical y Festivos A N  HENDF 1-1 Cantidad de Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@Canti
dad 
NIAE102  Porcentaje 
Porcentaje al cual corresponde el calculo 
de 1 Hora Extra Nocturna Dominical y 
Festivos 
A N 4-6 HENDF 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@Porce
ntaje 
NIAE103  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HENDF 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@Pago 
  HRNDFs 
Utilizado para Todos los Elementos de 
Horas Recargo Nocturno Dominicales y 
Festivas de Devengos del Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs 
  HRNDF 
Utilizado para Atributos de Horas Recargo 
Nocturno Dominicales y Festivas del 
Documento 
E A  HRNDFs 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF 
NIAE104  HoraInicio Hora de inicio de Horas Recargo Nocturno 
Dominical y Festivos A H 19 HRNDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@HoraI
nicio 

---

## Página 69

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 69 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE105  HoraFin Hora de fin de Horas Recargo Nocturno 
Dominical y Festivos A H 19 HRNDF 0-1 En formato YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@Hora
Fin 
NIAE106  Cantidad Cantidad de Horas Recargo Nocturno 
Dominical y Festivos A N  HRNDF 1-1 Cantidad de Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@Canti
dad 
NIAE107  Porcentaje 
Porcentaje al cual corresponde el calculo 
de 1 Hora Recargo Nocturno Dominical y 
Festivos 
A N 4-6 HRNDF 1-1 Se debe colocar el Porcentaje que 
corresponda de la tabla 5.5.5 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@Porc
entaje 
NIAE108  Pago 
Es el valor pagado por el tiempo que se 
trabaja adicional a la jornada legal o 
pactada contractualmente. 
A N  HRNDF 1-1 Valor Pagado por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@Pago 
  Vacaciones Utilizado para Todos los Elementos de 
Vacaciones de Devengos del Documento G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones 
  VacacionesComunes Utilizado para Atributos de Vacaciones 
Comunes del Documento E A  Vacaciones 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
omunes 
NIAE109  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador presenta el inicio del disfrute 
de sus vacaciones en tiempo. 
A F 10 VacacionesComun
es 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
omunes/@FechaInicio 

---

## Página 70

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 70 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE110  FechaFin 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador regresa o termina el disfrute 
de sus vacaciones. 
A F 10 VacacionesComun
es 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
omunes/@FechaFin 
NIAE111  Cantidad Número de días que el trabajador estuvo 
inactivo durante el mes por vacaciones. A N  VacacionesComun
es 1-1 Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
omunes/@Cantidad 
NIAE112  Pago 
Corresponde al valor pagado al 
trabajador, por el descanso remunerado 
que tiene derecho por haber trabajado un 
determinado tiempo. (Vacaciones SI 
disfrutadas) 
A N  VacacionesComun
es 1-1 Valor Pagado por Vacaciones Si Disfrutadas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
omunes/@Pago 
  VacacionesCompens
adas 
Utilizado para Atributos de Vacaciones 
Compensadas del Documento E A  Vacaciones 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
ompensadas 
NIAE115  Cantidad 
Número de días que el trabajador estuvo 
activo durante el mes sin disfrutar sus 
vacaciones. (Vacaciones NO disfrutadas) 
A N  VacacionesCompe
nsadas 1-1 Cantidad de Dias. 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
ompensadas/@Cantidad 
NIAE116  Pago 
Corresponde al valor pagado al 
trabajador, por el descanso remunerado 
que no disfrutó y que tiene derecho por 
haber trabajado un determinado tiempo. 
(Vacaciones NO disfrutadas) 
A N  VacacionesCompe
nsadas 1-1 Valor Pagado por Vacaciones No Disfrutadas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
ompensadas/@Pago 

---

## Página 71

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 71 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  Primas Utilizado para Atributos de Primas de 
Devengos del Documento E A  Devengados 0-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Primas 
NIAE117  Cantidad Cantidad de dias trabajados para calculo 
de Pago de Corte de Prima A N  Primas 1-1 Cantidad de Dias a los cuales corresponde el 
pago de la Prima legal 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Primas/@Cantidad 
NIAE118  Pago 
Pagos por el reconocimiento del logro o 
cumplimiento por parte del trabajador en 
el desarrollo de sus labores, de 
condiciones definidas expresamente 
entre las partes. 
A N  Primas 1-1 Valor Pagado por Prima Legal con respecto 
a Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Primas/@Pago 
NIAE119  PagoNS 
Son valores pagados al trabajador de 
forma ocasional y por mera liberalidad o 
los pactados entre las partes de forma 
expresa como pago no salarial. 
A N  Primas 0-1 Valor Pagado por Prima No Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Primas/@PagoNS 
  Cesantias Utilizado para Atributos de Cesantias de 
Devengos del Documento E A  Devengados 0-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Cesantias 
NIAE120  Pago Pago de la Cesantia otorgada por Ley. A N  Cesantias 1-1 Valor Pagado por Cesantias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Cesantias/@Pago 
NIAE121  Porcentaje Porcentaje que corresponde al Interes de 
Cesantia de Ley A N  Cesantias 1-1 Porcentaje de Interes de Cesantias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Cesantias/@Porcentaje 

---

## Página 72

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 72 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE122  PagoIntereses Pago de los Intereses de Cesantia 
otorgada por Ley. A N  Cesantias 1-1 Valor Pagado por Intereses de Cesantias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Cesantias/@PagoInteres
es 
  Incapacidades 
Utilizado para Todos los Elementos de 
Incapacidades de Devengos del 
Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades 
  Incapacidad Utilizado para Atributos de Incapacidad 
del Documento E A  Incapacidades 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad 
NIAE123  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador presenta o da por iniciada su 
Incapacidad. 
A F 10 Incapacidad 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@FechaInicio 
NIAE124  FechaFin 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador presenta o da por terminada 
su Incapacidad. 
A F 10 Incapacidad 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@FechaFin 
NIAE125  Cantidad 
Número de días que el trabajador o 
aprendiz estuvo inactivo por incapacidad 
(sin importar su origen). 
A N  Incapacidad 1-1 Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@Cantidad 
NIAE126  Tipo 
Se debe indicar el codigo al cual 
corresponda el tipo de incapacidad del 
Empleado 
A N 1 Incapacidad 1-1 Se debe colocar el Codigo que corresponda 
de la tabla 5.5.6 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@Tipo 

---

## Página 73

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 73 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE127  Pago 
Valor de la prestación económica pagada 
al trabajador por consecuencia de la falta 
de capacidad laboral sin importar su 
origen. 
A N  Incapacidad 1-1 Valor Pagado por Incapacidad con respecto 
a Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@Pago 
  Licencias Utilizado para Todos los Elementos de 
Licencias de Devengos del Documento G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias 
  LicenciaMP Utilizado para Atributos de Licencia de 
Materinidad o Paternidad del Documento E A  Licencias 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaMP 
NIAE128  FechaInicio Fecha donde da inicio la Licencia de 
Maternidad o Paternidad A F 10 LicenciaMP 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaMP/@
FechaInicio 
NIAE129  FechaFin Fecha donde termina la Licencia de 
Maternidad o Paternidad A F 10 LicenciaMP 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaMP/@
FechaFin 
NIAE130  Cantidad 
Número de días que el trabajador o 
aprendiz efectivamente estuvo inactivo 
por licencia de maternidad o paternidad. 
A N  LicenciaMP 1-1 Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaMP/@
Cantidad 

---

## Página 74

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 74 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE131  Pago 
Valor pagado al trabajador del descanso 
remunerado que la ley confiere por el 
nacimiento de un hijo, y que es 
reconocido y pagado por la EPS a la que 
está afiliado el padre o la madre, o en su 
defecto por el empleador. 
A N  LicenciaMP 1-1 Valor Pagado por Licencia de Maternidad o 
Paternidad con respecto a Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaMP/@
Pago 
  LicenciaR Utilizado para Atributos de Licencia 
Remunerada del Documento E A  Licencias 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaR 
NIAE132  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz inicia algún permiso 
o licencia remunerada. 
A F 10 LicenciaR 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaR/@Fe
chaInicio 
NIAE133  FechaFin 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz termina el permiso 
o licencia remunerada. 
A F 10 LicenciaR 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaR/@Fe
chaFin 
NIAE134  Cantidad 
Número de días que el trabajador o 
aprendiz efectivamente estuvo inactivo 
por permiso o licencia pero que le fueron 
reconocidos en su pago. 
A N  LicenciaR 1-1 Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaR/@Ca
ntidad 
NIAE135  Pago 
Valor pagado al trabajador corresponde a 
tiempo no laborado, que por ley o por 
acuerdo con el empleador se le concede 
A N  LicenciaR 1-1 Valor Pagado por Licencia Remunerada con 
respecto a Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaR/@Pa
go 

---

## Página 75

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 75 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  LicenciaNR Utilizado para Atributos de Licencia No 
Remunerada del Documento E A  Licencias 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaNR 
NIAE136  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz inicia alguna 
suspensión, permiso o licencia NO 
remunerada. 
A F 10 LicenciaNR 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaNR/@
FechaInicio 
NIAE137  FechaFin 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador o aprendiz termina la 
suspensión, permiso o licencia NO 
remunerada. 
A F 10 LicenciaNR 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaNR/@
FechaFin 
NIAE138  Cantidad 
Número de días que el trabajador o 
aprendiz efectivamente estuvo inactivo 
por suspensión, permiso o licencia y que 
NO le fueron reconocidos en su pago. 
A N  LicenciaNR 1-1 Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaNR/@
Cantidad 
  Bonificaciones 
Utilizado para Todos los Elementos de 
Bonificaciones de Devengos del 
Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Bonificaciones 
  Bonificacion Utilizado para Atributos de Bonificacion 
del Documento E A  Bonificaciones 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Bonificaciones/Bonificac
ion 

---

## Página 76

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 76 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE139  BonificacionS 
Son valores pagados al trabajador en 
forma de incentivo o recompensa por la 
contraprestación directa del servicio. 
A N  Bonificacion 0-1 Valor Pagado por Bonificación Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Bonificaciones/Bonificac
ion/@BonificacionS 
NIAE140  BonificacionNS 
Son valores de incentivos pagados al 
trabajador de forma ocasional y por mera 
liberalidad o los pactados entre las partes 
de forma expresa como pago no salarial. 
A N  Bonificacion 0-1 Valor Pagado por Bonificación No Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Bonificaciones/Bonificac
ion/@BonificacionNS 
  Auxilios Utilizado para Todos los Elementos de 
Auxilios de Devengos del Documento G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Auxilios 
  Auxilio Utilizado para Atributos de Auxilio del 
Documento E A  Auxilios 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Auxilios/Auxilio 
NIAE141  AuxilioS 
Son beneficios, ayudas o apoyos 
económicos, pagados al trabajador de 
forma habitual o pactados entre las 
partes como factor salarial. 
A N  Auxilio 0-1 Valor Pagado por Auxilios Salariales 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Auxilios/Auxilio/@Auxili
oS 
NIAE142  AuxilioNS 
Son beneficios, ayudas o apoyos 
económicos, pagados al trabajador de 
forma ocasional y por mera liberalidad o 
los pactados entre las partes de forma 
expresa como pago no salarial. 
A N  Auxilio 0-1 Valor Pagado por Auxilios No Salariales 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Auxilios/Auxilio/@Auxili
oNS 
  HuelgasLegales 
Utilizado para Todos los Elementos de 
Huelgas Legales de Devengos del 
Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HuelgasLegales 

---

## Página 77

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 77 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  HuelgaLegal Utilizado para Atributos de Huelga Legal 
del Documento E A  HuelgasLegales 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HuelgasLegales/HuelgaL
egal 
NIAE143  FechaInicio 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador inicia la huelga legalmente 
declarada. 
A F 10 HuelgaLegal 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HuelgasLegales/HuelgaL
egal/@FechaInicio 
NIAE144  FechaFIn 
Este dato se debe diligenciar solamente 
en el registro del mes en que el 
trabajador termina la huelga legalmente 
declarada. 
A F 10 HuelgaLegal 0-1 En formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HuelgasLegales/HuelgaL
egal/@FechaFIn 
NIAE145  Cantidad 
número de días en los que el trabajador 
estuvo inactivo por huelga legalmente 
declarada. 
A N  HuelgaLegal 1-1 Cantidad de Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HuelgasLegales/HuelgaL
egal/@Cantidad 
  OtrosConceptos 
Utilizado para Todos los Elementos de 
Otros Conceptos de Devengos del 
Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/OtrosConceptos 
  OtroConcepto Utilizado para Atributos de Otro Concepto 
del Documento E A  OtrosConceptos 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/OtrosConceptos/OtroCo
ncepto 

---

## Página 78

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 78 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE146  DescripcionConcept
o 
Nombre del Concepto que corresponde a 
los demás pagos fijos o variables 
realizados al trabajador que remuneren 
en dinero o en especie como 
contraprestación directa del servicio, sea 
cualquiera la forma o denominación que 
se adopte. 
A A  OtroConcepto 1-1 Debe ir la Descripcion del Concepto 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/OtroConceptos/OtroCon
cepto/@DescripcionConc
epto 
NIAE147  ConceptoS 
Valor de los demás pagos fijos o variables 
realizados al trabajador que remuneren 
en dinero o en especie como 
contraprestación directa del servicio, sea 
cualquiera la forma o denominación que 
se adopte (Salarial). 
A N  OtroConcepto 0-1 Valor Pagado por Conceptos Salariales 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/OtroConceptos/OtroCon
cepto/@ConceptoS 
NIAE148  ConceptoNS 
Valor de los demás pagos que 
ocasionalmente y por mera liberalidad 
recibe el trabajador del empleador, en 
dinero o en especie no para su beneficio, 
ni para enriquecer su patrimonio, sino 
para desempeñar a cabalidad sus 
funciones (No Salarial). 
A N  OtroConcepto 0-1 Valor Pagado por Conceptos No Salariales 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/OtroConceptos/OtroCon
cepto/@ConceptoNS 
  Compensaciones 
Utilizado para Todos los Elementos de 
Compensaciones de Devengos del 
Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Compensaciones 
  Compensacion Utilizado para Atributos de Compensacion 
del Documento E A  Compensaciones 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Compensaciones/Comp
ensacion 

---

## Página 79

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 79 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE149  CompensacionO 
Suma de dinero definido en el régimen de 
compensaciones como retribución 
mensual recibido por el asociado por la 
ejecución de su actividad material o 
inmaterial, la cual se fija teniendo en 
cuenta el tipo de labor desempeñada, el 
rendimiento o la productividad y la 
cantidad de trabajo aportado. El monto 
de la compensación ordinaria podrá ser 
una suma básica igual para todos los 
asociados (Ordinaria). 
A N  Compensacion 1-1 Valor Pagado por Compensaciones 
Ordinarias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Compensaciones/Comp
ensacion/@Compensacio
nO 
NIAE150  CompensacionE 
Los demás pagos adicionales a la 
Compensación Ordinaria que recibe el 
asociado como retribución por su trabajo, 
definidos en el régimen de 
compensaciones (Extraordinaria). 
A N  Compensacion 1-1 Valor Pagado por Compensaciones 
Extraordinarias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Compensaciones/Comp
ensacion/@Compensacio
nE 
  BonoEPCTVs 
Utilizado para Todos los Elementos de 
Bonos Electronicos o de Papel de Servicio, 
Cheques, Tarjetas, Vales, etc de Devengos 
del Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs 
  BonoEPCTV 
Utilizado para Atributos de Bono 
Electronico o de Papel de Servicio, 
Cheque, Tarjeta, Vale, etc del Documento 
E A  BonoEPCTVs 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs/BonoEPCT
V 

---

## Página 80

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 80 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE151  PagoS 
Valor que el trabajador recibe como 
contraprestación por el trabajo realizado, 
por medio de bonos electrónicos, 
recargas, cheques, vales. es decir, todo 
pago realizado en un medio diferente a 
dinero en efectivo o consignación de 
cuenta bancaria (Salarial). 
A N  BonoEPCTV 0-1 Concepto Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs/BonoEPCT
V/@PagoS 
NIAE152  PagoNS 
Valor que el trabajador recibe como 
concepto no salarial, por medio de bonos 
electrónicos, recargas, cheques, vales. es 
decir, todo pago realizado en un medio 
diferente a dinero en efectivo o 
consignación de cuenta bancaria (No 
Salarial). 
A N  BonoEPCTV 0-1 Concepto No Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs/BonoEPCT
V/@PagoNS 
NIAE153  PagoAlimentacionS 
Valor que el trabajador recibe como 
concepto no salarial, por medio de bonos 
electrónicos, recargas, cheques, vales. es 
decir, todo pago realizado en un medio 
diferente a dinero en efectivo o 
consignación de cuenta bancaria (Para 
Alimentación Salarial). 
A N  BonoEPCTV 0-1 Concepto Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs/BonoEPCT
V/@PagoAlimentacionS 

---

## Página 81

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 81 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE154  PagoAlimentacionN
S 
Valor que el trabajador recibe como 
concepto no salarial, por medio de bonos 
electrónicos, recargas, cheques, vales. es 
decir, todo pago realizado en un medio 
diferente a dinero en efectivo o 
consignación de cuenta bancaria (Para 
Alimentación No Salarial). 
A N  BonoEPCTV 0-1 Concepto No Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs/BonoEPCT
V/@PagoAlimentacionNS 
  Comisiones Utilizado para Todos los Elementos de 
Comisiones de Devengos del Documento G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Comisiones 
NIAE155  Comision 
Valor pagado al trabajador usualmente 
del área comercial, y de forma regular se 
liquida con un porcentaje sobre el 
importe de una operación, también se 
presenta como incentivo por el logro de 
objetivos. 
E N  Comisiones 0-N Valor Pagado por Comision 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Comisiones/Comision 
  PagosTerceros 
Utilizado para Todos los Elementos de 
Pagos a Tercero de Devengos del 
Documento 
G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/PagosTerceros 
NIAE193  PagoTercero Beneficios en cabeza del Trabjador que se 
pagan a un proveedor o tercero. E N  PagosTerceros 0-N Valor Pagado por Pago Tercero 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/PagosTerceros/PagoTerc
ero 
  Anticipos Utilizado para Todos los Elementos de 
Anticipos de Devengos del Documento G A  Devengados 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Anticipos 

---

## Página 82

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 82 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE194  Anticipo Anticipos de Nomina. E N  Anticipos 0-N Valor Pagado por Anticipo 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Anticipos/Anticipo 
NIAE156  Dotacion 
De conformidad con lo previsto en el 
artículo 230 del Código Sustantivo del 
Trabajo, o la norma que lo modifique, 
adicione o sustituya, corresponde al valor 
que el empleador dispone para 
suministrar la dotación de sus 
trabajadores. 
E N  Devengados 0-1 Valor Pagado por Dotación 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Dotacion 
NIAE157  ApoyoSost 
Corresponde al valor no salarial que el 
patrocinador paga de forma mensual 
como ayuda o apoyo economía al 
aprendiz o practicante universitario 
durante su etapa lectiva y fase practica. 
E N  Devengados 0-1 Valor Pagado por Apoyo a Sostenimiento 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/ApoyoSost 
NIAE158  Teletrabajo 
Valor que debe ser pagado al trabajador 
cuyo contrato indica expresamente que 
puede laborar mediante teletrabajo 
E N  Devengados 0-1 Valor Pagado por trabajo en Teletrabajo 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Teletrabajo 
NIAE159  BonifRetiro Valor establecido por mutuo acuerdo por 
retiro del Trabajador E N  Devengados 0-1 Valor Pagado por Retiro de la empresa 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonifRetiro 
NIAE160  Indemnizacion Valor de Indemnizacion establecido por 
ley E N  Devengados 0-1 Valor Pagado por Indemnización 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Indemnizacion 
NIAE201  Reintegro 
Valor que le regresa la empresa al 
trabajador por una deducción mal 
realizada en otro pago de nomina 
E N  Devengados 0-1 Valor Pagado correspondiente a Reintegro 
por parte del empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Reintegro 

---

## Página 83

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 83 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  Deducciones Utilizado para Todas las Deducciones del 
Documento G A  Reemplazar 1-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es 
  Salud Utilizado para Atributos de Salud del 
Documento E A  Deducciones 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Salud 
NIAE161  Porcentaje 
Debe corresponder al porcentaje de 
deducción de salud que paga el 
trabajador 
A N 4-6 Salud 1-1 Se debe colocar el Porcentaje que 
corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Salud/@Porcentaje 
NIAE163  Deduccion 
El trabajador debe estar afiliado al 
sistema de salud. La cotización por salud 
que corresponde al 12.5% de la base del 
aporte, se hace en conjunto con la 
empresa. Ésta última aporta el 8.5%, y el 
empleado debe aportar el 4% restante. 
Ese 4% es el valor que se debe descontar 
(deducir) del total devengado a cargo del 
empleado.  
A N  Salud 1-1 Valor Pagado correspondiente a Salud por 
parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Salud/@Deduccion 
  FondoPension Utilizado para Atributos de Fondos de 
Pension del Documento E A  Deducciones 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/FondoPension 
NIAE164  Porcentaje 
Debe corresponder al porcentaje de 
deducción de fondo de pension que paga 
el trabajador 
A N 4-6 FondoPension 1-1 Se debe colocar el Porcentaje que 
corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/FondoPension/@Porce
ntaje 

---

## Página 84

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 84 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE166  Deduccion 
El trabajador también debe estar afiliado 
al sistema de pensiones. La cotización por 
pensión está a cargo tanto de la empresa 
como del empleado. Del total del aporte 
(16%), la empresa aporta el 75% (12%) y 
el trabajador aporta el restante 25% (4%). 
Como el trabajador debe aportar un 4% 
por concepto de pensión, este valor se le 
descuenta (deduce) del valor devengado 
en el respectivo periodo (mes o 
quincena). 
A N  FondoPension 1-1 Valor Pagado correspondiente a Pension 
por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/FondoPension/@Dedu
ccion 
  FondoSP Utilizado para Atributos de Fondo de 
Seguridad Pensional del Documento E A  Deducciones 0-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/FondoSP 
NIAE167  Porcentaje 
Debe corresponder al porcentaje de 
deducción de fondo de seguridad 
pensional que paga el trabajador 
A N 4-6 FondoSP 0-1 Se debe colocar el Porcentaje que 
corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/FondoSP/@Porcentaje 
NIAE168  DeduccionSP 
Todo trabajador que devengue un sueldo 
que sea igual o superior a 4 salarios 
mininos, debe aportar un 1% al Fondo de 
solidaridad pensional. 
A N  FondoSP 0-1 
Valor Pagado correspondiente a Fondo de 
Solidaridad Pensional por parte del 
trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/FondoSP/@Deduccion
SP 
NIAE169  PorcentajeSub 
Se debe colocar el Porcentaje que 
correspondiente al Fondo de Subsistencia 
correspondiente 
A N 4-6 FondoSP 0-1 
Se debe colocar el Porcentaje que 
correspondiente al Fondo de Subsistencia 
correspondiente 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/FondoSP/@Porcentaje
Sub 

---

## Página 85

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 85 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE170  DeduccionSub Valor Pagado correspondiente a Fondo de 
Subsistencia por parte del trabajador A N  FondoSP 0-1 Valor Pagado correspondiente a Fondo de 
Subsistencia por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/FondoSP/@Deduccion
Sub 
  Sindicatos 
Utilizado para Todos los Elementos de 
Sindicatos de Deducciones del 
Documento 
G A  Deducciones 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Sindicatos 
  Sindicato Utilizado para Atributos de Sindicato del 
Documento E A  Sindicatos 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Sindicatos/Sindicato 
NIAE171  Porcentaje Porcentaje establecido en la ley o por 
estatutos del sindicato. A N  Sindicato 1-1 
Se debe colocar el Porcentaje que 
correspondiente a Aportes del Sindicato 
correspondiente 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Sindicatos/Sindicato/@
Porcentaje 
NIAE172  Deduccion 
Las cuotas que los trabajadores 
sindicalizados deben aportar al sindicato 
al que estén afiliados, y siempre que 
medie autorización del empleado. 
A N  Sindicato 1-1 Valor Pagado correspondiente a Aportes del 
Sindicato por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Sindicatos/Sindicato/@
Deduccion 
  Sanciones 
Utilizado para Todos los Elementos de 
Sanciones de Deducciones del 
Documento 
G A  Deducciones 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Sanciones 
  Sancion Utilizado para Atributos de Sancion del 
Documento E A  Sanciones 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Sanciones/Sancion 

---

## Página 86

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 86 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE173  SancionPublic 
Valor por el del incumplimiento de una 
regla o norma de conducta obligatoria 
(Publica) 
A N  Sancion 1-1 Valor Pagado correspondiente a Sanción 
Pública por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Sanciones/Sancion/@S
ancionPublic 
NIAE174  SancionPriv 
Valor por el del incumplimiento de una 
regla o norma de conducta obligatoria 
(Privada o Ordinaria) 
A N  Sancion 1-1 Valor Pagado correspondiente a Sanción 
Privada por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Sanciones/Sancion/@S
ancionPriv 
  Libranzas Utilizado para Todos los Elementos de 
Libranzas de Deducciones del Documento G A  Deducciones 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Libranzas 
  Libranza Utilizado para Atributos de Libranza del 
Documento E A  Libranzas 0-N Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Libranzas/Libranza 
NIAE175  Descripcion 
Nombre de la Libranza que corresponda a 
las cuotas que el empleado deba pagar a 
una entidad financiera, para la 
amortización de un crédito que le haya 
sido otorgado por libranza 
A A  Libranza 1-1 Debe ir la Descripcion de la Libranza 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Libranzas/Libranza/@D
escripcion 
NIAE176  Deduccion 
Las cuotas que el empleado deba pagar a 
una entidad financiera, para la 
amortización de un crédito que le haya 
sido otorgado por libranza 
A N  Libranza 1-1 
Valor Pagado correspondiente a Aportes a 
Entidades Financieras por parte del 
trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Libranzas/Libranza/@D
educcion 
  PagosTerceros 
Utilizado para Todos los Elementos de 
Pagos a Tercero de Deducciones del 
Documento 
G A  Deducciones 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/PagosTerceros 

---

## Página 87

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 87 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE195  PagoTercero Deducciones en cabeza del Trabjador que 
se pagan a un proveedor o tercero. E N  PagosTerceros 0-N Valor Pagado por Pago Tercero 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/PagosTerceros/PagoTe
rcero 
  Anticipos Utilizado para Todos los Elementos de 
Anticipos de Deducciones del Documento G A  Deducciones 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Anticipos 
NIAE196  Anticipo Deduccion por Anticipos de Nómina. E N  Anticipos 0-N Valor Pagado por Anticipo 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Anticipos/Anticipo 
  OtrasDeducciones Utilizado para Todos los Elementos de 
Otras Deducciones del Documento G A  Deducciones 0-1  1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/OtrasDeducciones 
NIAE197  OtraDeduccion Otro tipo de deducción dentro de la 
Nómina. E N  OtrasDeducciones 0-N Valor Pagado por Otra Deducción 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/OtrasDeducciones/Otr
aDeduccion 
NIAE198  PensionVoluntaria 
Valor correspondiente al ahorro que hace 
el trabajador para complementar su 
pension obligatoria o cumplir metas 
especificas. 
E N  Deducciones 0-1 
Valor Pagado correspondiente al ahorro que 
hace el trabajador para complementar su 
pension obligatoria o cumplir metas 
especificas. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/PensionVoluntaria 

---

## Página 88

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 88 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE177  RetencionFuente 
Si hubiere lugar, la empresa deberá 
calcular y retener al empleado el valor 
correspondiente a retención en la fuente 
por ingresos laborales. Este valor será 
declarado y consignado en la respectiva 
declaración mensual de retención en la 
fuente. 
E N  Deducciones 0-1 Valor Pagado correspondiente a Retención 
en la Fuente por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/RetencionFuente 
NIAE179  AFC Corresponde a (Ahorro Fomento a la 
contruccion)  E N  Deducciones 0-1 Valor Pagado correspondiente a AFC por 
parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/AFC 
NIAE180  Cooperativa 
Las cuotas o aportes que los empleados 
hagan a las cooperativas legalmente 
constituidas 
E N  Deducciones 0-1 Valor Pagado correspondiente a 
Cooperativas por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Cooperativa 
NIAE181  EmbargoFiscal 
Los embargos ordenados por autoridad 
judicial competente contra los empleados 
deben ser descontados de la nómina por 
la empresa y consignarlos en la cuenta 
que el juez haya ordenado. 
E N  Deducciones 0-1 Valor Pagado correspondiente a Embargos 
Fiscales por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/EmbargoFiscal 
NIAE182  PlanComplementari
os 
 Valor de planes complementarios de 
salud al que el trabajador se encuentran 
afiliado, siempre que medie autorización 
del empleado. 
E N  Deducciones 0-1 Valor Pagado correspondiente a Planes 
Complementarios por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/PlanComplementarios 
NIAE183  Educacion  Valor de servicios educativos  que el 
trabajador autorice descuento. E N  Deducciones 0-1 Valor Pagado correspondiente a Conceptos 
Educativos por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Educacion 

---

## Página 89

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 89 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE184  Reintegro 
Valor que le regresa el trabajador a la 
empresa por un devengo mal realizado en 
otro pago de nómina 
E N  Deducciones 0-1 Valor Pagado correspondiente a Reintegro 
por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Reintegro 
NIAE185  Deuda 
Valor que se deba pagar por las 
obligaciones que el empleado tenga con 
su empresa, como puede ser un crédito 
que ésta le haya otorgado, o como 
compensación por algún perjuicio o 
detrimento económico que el empleado 
le haya causado a la empresa. 
E N  Deducciones 0-1 Valor Pagado correspondiente a Deuda con 
la Empresa por parte del trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
es/Deuda 
NIAE186  Redondeo Se utiliza para cuando se utilice el 
Redondeo en el Documento E N  Reemplazar 0-1 Definido en el numeral 1.1.1 1.0 /NominaIndividualDeAjust
e/Reemplazar/Redondeo 
NIAE187  DevengadosTotal Valor total de la Suma de todos los 
Devengados del Documento E N  Reemplazar 1-1 Debe ir el valor Total de Todos los 
Devengados del Trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
sTotal 
NIAE188  DeduccionesTotal Valor total de la Suma de todas las 
Deducciones del Documento E N  Reemplazar 1-1 Debe ir el valor Total de Todos las 
Deducciones del Trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccion
esTotal 
NIAE189  ComprobanteTotal Debe ir el total de: Devengados - 
Deducciones E N  Reemplazar 1-1 Debe ser la Diferencia entre 
DevengadosTotal - DeduccionesTotal 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Comproba
nteTotal 
  Eliminar 
Utilizado para todo el contenido 
correspondiente al evento de Eliminar 
Documento 
G A  NominaIndividual
DeAjuste 0-1  1.0 /NominaIndividualDeAjust
e/Eliminar 

---

## Página 90

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 90 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
  EliminandoPredeces
or 
Utilizado para Atributos de Documento 
Predecesor a Eliminar E A  Eliminar 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Eliminar/EliminandoPre
decesor 
NIAE215  NumeroPred 
Debe corresponder al Numero de 
Documento Soporte de Pago de Nómina 
Electrónica o Nota de Ajuste de 
Documento Soporte de Pago de Nómina 
Electrónica a Reemplazar 
A A  EliminandoPredec
esor 1-1 Debe ir el Numero de documento a 
Reemplazar 1.0 
/NominaIndividualDeAjust
e/Eliminar/EliminandoPre
decesor/@NumeroPred 
NIAE216  CUNEPred 
Debe corresponder al CUNE del 
Documento Soporte de Pago de Nómina 
Electrónica o Nota de Ajuste de 
Documento Soporte de Pago de Nómina 
Electrónica a Reemplazar 
A A  EliminandoPredec
esor 1-1 Debe ir el CUNE del documento a 
Reemplazar 1.0 
/NominaIndividualDeAjust
e/Eliminar/EliminandoPre
decesor/@CUNEPred 
NIAE217  FechaGenPred 
Debe corresponder a la Fecha de Emision 
del Documento Soporte de Pago de 
Nómina Electrónica o Nota de Ajuste de 
Documento Soporte de Pago de Nómina 
Electrónica a Reemplazar 
A F 10 EliminandoPredec
esor 1-1 Debe ir la fecha del documento a 
Reemplazar, en formato AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Eliminar/EliminandoPre
decesor/@FechaGenPred 
  NumeroSecuenciaX
ML 
Utilizado para Atributos de Numero de 
Secuencia del Documento XML E A  Eliminar 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Eliminar/NumeroSecue
nciaXML 
NIAE218  Prefijo Prefijo del documento, depende de las 
sucursales que posea el Empleador A A  NumeroSecuencia
XML 0-1 Debe corresponder a un Prefijo elegido por 
el Emisor del documento 1.0 
/NominaIndividualDeAjust
e/Eliminar/NumeroSecue
nciaXML/@Prefijo 
NIAE219  Consecutivo Debe corresponder a un consecutivo 
manejado por el Empleador A N  NumeroSecuencia
XML 1-1 Debe corresponder a un Consecutivo 
elegido por el Emisor del documento 1.0 
/NominaIndividualDeAjust
e/Eliminar/NumeroSecue
nciaXML/@Consecutivo 

---

## Página 91

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 91 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE220  Numero Debe corresponder al Prefijo y 
consecutivo manejado por el Empleador A A  NumeroSecuencia
XML 1-1 
No se permiten caracteres adicionales como 
espacios o guiones. Prefijo + Número 
consecutivo del documento 
1.0 
/NominaIndividualDeAjust
e/Eliminar/NumeroSecue
nciaXML/@Numero 
  LugarGeneracionXM
L 
Utilizado para Atributos del Lugar de 
Generacion del Documento XML E A  Eliminar 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Eliminar/LugarGeneraci
onXML 
NIAE221  Pais Codigo del país donde se genera el 
documento A A 2 LugarGeneracionX
ML 1-1 Se debe colocar el Codigo alfa-2 de la tabla 
5.4.1 1.0 
/NominaIndividualDeAjust
e/Eliminar/LugarGeneraci
onXML/@Pais 
NIAE222  DepartamentoEstad
o 
Código del departamento donde se 
genera el documento A N 2 LugarGeneracionX
ML 1-1 Se debe colocar el Codigo de la tabla 5.4.2 1.0 
/NominaIndividualDeAjust
e/Eliminar/LugarGeneraci
onXML/@DepartamentoE
stado 
NIAE223  MunicipioCiudad Código del municipio o ciudad donde se 
genera el documento A N 5 LugarGeneracionX
ML 1-1 Se debe colocar el Codigo de la tabla 5.4.3 1.0 
/NominaIndividualDeAjust
e/Eliminar/LugarGeneraci
onXML/@MunicipioCiuda
d 
NIAE224  Idioma Codigo del país donde se genera el 
documento A A 2 LugarGeneracionX
ML 1-1 
Se debe colocar el Codigo ISO 639-1 de la 
tabla 5.3.1. Para Colombia se debe colocar 
"es" (Español, Castellano) 
1.0 
/NominaIndividualDeAjust
e/Eliminar/LugarGeneraci
onXML/@Idioma 
  ProveedorXML Utilizado para Atributos del Proveedor del 
Documento XML E A  Eliminar 1-1 Elemento Vacio 1.0 /NominaIndividualDeAjust
e/Eliminar/ProveedorXML 
NIAE225  RazonSocial 
Debe corresponder al Nombre de la 
Razón Social del Proveedor de Soluciones 
Tecnológicas 
A A  ProveedorXML 0-1 Debe ir el Nombre o Razón Social del 
Proveedor de Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@RazonSocial 

---

## Página 92

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 92 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE226  PrimerApellido Primer Apellido del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Debe ir el Primer Apellido del Proveedor de 
Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@PrimerApellido 
NIAE227  SegundoApellido Segundo Apellido del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Debe ir el Segundo Apellido del Proveedor 
de Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@SegundoApellido 
NIAE228  PrimerNombre Primer Nombre del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Debe ir el Primer Nombre del Proveedor de 
Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@PrimerNombre 
NIAE229  OtrosNombres Otros Nombres del Proveedor de 
Soluciones Tecnológicas A A 60 ProveedorXML 0-1 Deben ir los Otros Nombres del Proveedor 
de Soluciones Tecnológicas 1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@OtrosNombres 
NIAE230  NIT 
Debe corresponder al NIT del Proveedor 
de Soluciones Tecnologicas que realiza el 
DE 
A N  ProveedorXML 1-1 
Se debe colocar el NIT sin guiones ni DV de 
la empresa dueña del Software que genera 
el Documento, debe estar registrado en la 
DIAN 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@NIT 
NIAE231  DV 
Debe corresponder al DV del NIT del 
Proveedor de Soluciones Tecnologicas 
que realiza el DE 
A N 2 ProveedorXML 1-1 
Se debe colocar el DV de la empresa dueña 
del Software que genera el Documento, 
debe estar registrado en la DIAN 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@DV 
NIAE232  SoftwareID 
Identificador Software: Identificador del 
software habilitado para la emisión de 
nóminas 
A A  ProveedorXML 1-1 
Identificador del software asignado cuando 
el software se activa en el Sistema del 
Documento Soporte de Pago de Nómina 
Electrónica, debe corresponder a un 
software autorizado para este Emisor 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@SoftwareID 
NIAE233  SoftwareSC 
Huella del software que autorizó la DIAN 
al Obligado a Generar Nómina Electrónica 
o al Proveedor de Soluciones Tecnológicas 
A A  ProveedorXML 1-1 Definido en el numeral 8.3 1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@SoftwareSC 

---

## Página 93

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 93 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE234  CodigoQR Debe poseer información detallada del 
Documento Electronico E A  Eliminar 1-1 
Debe  corresponder a la siguiente URL 
“https://catalogo-
vpfe.dian.gov.co/document/searchqr?docu
mentkey=CUNE”  donde la palabra CUNE 
debe ser reemplazada por el CUNE del 
documento electrónico 
1.0 /NominaIndividualDeAjust
e/Eliminar/CodigoQR 
  InformacionGeneral Utilizado para Atributos de Información 
General Documento E A  Eliminar 1-1 Elemento Vacio 1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral 
NIAE235  Version 
Versión base de Schema XML usada para 
crear este perfil 
(NominaIndividualDeAjuste) 
A A  InformacionGener
al 1-1 
Debe ir el literal: "V1.0: Nota de Ajuste de 
Documento Soporte de Pago de Nómina 
Electrónica" 
1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@Version 
NIAE236  Ambiente Tipo de Ambiente de Emision del 
Documento: Habilitacion o Produccion A N 1 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.1.1 1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@Ambiente 
NIAE237  TipoXML Tipo de XML del Documento A N 2 InformacionGener
al 1-1 Se debe colocar el Codigo de la tabla 5.5.7 1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@TipoXML 
NIAE238  CUNE 
CUNE:  Código Único de Documento 
Soporte de Pago de Nómina Electrónica. 
Elemento que verifica la integridad de la 
información recibida 
A A  InformacionGener
al 1-1 Definido en el numeral 8.1 1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@CUNE 
NIAE239  EncripCUNE 
Identificador del esquema de 
identificación. Algoritmo utilizado para el 
cáculo del CUNE, SHA-384 
A A 7 InformacionGener
al 1-1 Debe ir la palabra "CUNE-SHA384" 1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@EncripCUNE 

---

## Página 94

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 94 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE240  FechaGen Fecha de emisión: Fecha de emisión del 
documento A F 10 InformacionGener
al 1-1 
Debe ir la fecha de emision del documento. 
Considerando zona horaria de Colombia (-
5), en formato AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@FechaGen 
NIAE241  HoraGen Hora de emisión: hora de emisión del 
documento A H 14 InformacionGener
al 1-1 
Debe ir la hora de emision del documento. 
Considerando zona horaria de Colombia (-
5), en formato HH:MM:SSdhh:mm 
1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@HoraGen 
NIAE242  Notas Campo de libre uso para Observaciones 
en el documento E A  Eliminar 0-N Información adicional: Texto libre, relativo 
al documento 1.0 /NominaIndividualDeAjust
e/Eliminar/Notas 
  Empleador Utilizado para Atributos del Empleador o 
Emisor del Documento E A  Eliminar 1-1 Elemento Vacio 1.0 /NominaIndividualDeAjust
e/Eliminar/Empleador 
NIAE243  RazonSocial Debe corresponder al Nombre de la 
Razón Social del Empleador A A  Empleador 1-1 Debe ir el Nombre o Razón Social del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@R
azonSocial 
NIAE244  PrimerApellido Primer Apellido del Empleador A A 60 Empleador 0-1 Debe ir el Primer Apellido del Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@P
rimerApellido 
NIAE245  SegundoApellido Segundo Apellido del Empleador A A 60 Empleador 0-1 Debe ir el Segundo Apellido del Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@S
egundoApellido 
NIAE246  PrimerNombre Primer Nombre del Empleador A A 60 Empleador 0-1 Debe ir el Primer Nombre del Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@P
rimerNombre 
NIAE247  OtrosNombres Otros Nombres del Empleador A A 60 Empleador 0-1 Deben ir los Otros Nombres del Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
OtrosNombres 

---

## Página 95

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 95 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
NIAE248  NIT Debe corresponder al NIT del Empleador 
que realiza el DE A N  Empleador 1-1 Debe ir el NIT del Empleador sin guiones ni 
DV 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
NIT 
NIAE249  DV Debe corresponder al DV del NIT del 
Empleador que realiza el DE A N 2 Empleador 1-1 Debe ir el DV del Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
DV 
NIAE250  Pais 
Codigo del país donde donde se 
encuentra ubicado el empleador el mes 
que se esta reportando 
A A 2 Empleador 1-1 Se debe colocar el Codigo alfa-2 de la tabla 
5.4.1 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@P
ais 
NIAE251  DepartamentoEstad
o 
Código del departamento donde se 
encuentra ubicado el empleador el mes 
que se esta reportando 
A N 2 Empleador 1-1 Se debe colocar el Codigo de la tabla 5.4.2 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
DepartamentoEstado 
NIAE252  MunicipioCiudad 
Código del municipio o ciudad donde se 
encuentra ubicado el empleador el mes 
que se esta reportando 
A N 5 Empleador 1-1 Se debe colocar el Codigo de la tabla 5.4.3 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
MunicipioCiudad 
NIAE253  Direccion Debe corresponder a la dirección del 
lugar físico de expedición del documento.  A A  Empleador 1-1 Debe ir la Dirección Fisica del Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
Direccion 

---

## Página 96

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 96 de 269 
 
3.3. Estándar del nombre del documento electrónico Documento Soporte de Pago de Nómina Electrónica 
XML. 
Notas: 
 Los tamaños de cada variable son constantes, es necesario generar el ajuste con ceros a la izquierda en cada 
uno de ellos. 
 El año “aa” corresponde al año en vigencia. 
 Cada Año, el 1ro de enero se debe reiniciar en consecutivo de archivos enviados “dddddddd” a 00000001. 
 
3.4. Estándar del nombre del documento electrónico Nota de Ajuste de Documento Soporte de Pago de 
Nómina Electrónica XML. 
Guía del nombre del archivo XML del documento electrónico Documento Soporte de Pago de Nómina Electrónica requerido 
por la DIAN 
Ejemplo de Nomenclatura Observaciones 
niennnnnnnnnnaadddddddd.xml nie: Documento Soporte de Pago de Nómina Electrónica. 
nnnnnnnnnn: NIT del Sujeto Obligado sin DV, de diez (10) dígitos alineados a la 
derecha y relleno con ceros a la izquierda. 
aa: Dos (2) últimos dígitos año calendario. 
dddddddd: consecutivo de archivos enviados, de ocho (8) dígitos hexadecimales 
alineados a la derecha y ajustado a la izquierda con ceros, en el rango: 
00000001 <= FFFFFFFF 
Ejemplo del décimo segundo Documento Soporte de Pago de Nómina Electrónica 
del Sujeto Obligado con NIT 800197268 con software propio para el año 2020. 
nie0800197268200000000C.xml 
Guía del nombre del archivo XML del documento electrónico Nota de Ajuste de Documento Soporte de Pago de Nómina 
Electrónica requerido por la DIAN 
Ejemplo de Nomenclatura Observaciones 

---

## Página 97

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 97 de 269 
 
Notas: 
 Los tamaños de cada variable son constantes, es necesario generar el ajuste con ceros a la izquierda en cada 
uno de ellos. 
 El año “aa” corresponde al año en vigencia. 
 Cada Año, el 1ro de enero se debe reiniciar en consecutivo de archivos enviados “dddddddd” a 00000001. 
 
3.5. Guía del nombre del archivo que contiene uno o más documentos electrónicos y que será entregado a 
la DIAN mediante un web service de recepción. 
 
niaennnnnnnnnnaadddddddd.xml niae: Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica. 
nnnnnnnnnn: NIT del Sujeto Obligado sin DV, de diez (10) dígitos alineados a la 
derecha y relleno con ceros a la izquierda. 
aa: Dos (2) últimos dígitos año calendario. 
dddddddd: consecutivo de archivos enviados, de ocho (8) dígitos hexadecimales 
alineados a la derecha y ajustado a la izquierda con ceros, en el rango: 
00000001 <= FFFFFFFF 
Ejemplo del décimo segundo Documento Soporte de Pago de Nómina Electrónica 
del Sujeto Obligado con NIT 800197268 con software propio para el año 2020. 
niae0800197268200000000C.xml 
Guía del nombre del archivo ZIP que Contiene uno o más documentos electrónicos y que será Entregado a la DIAN mediante un 
web service de recepción. 
Ejemplo de Nomenclatura Observaciones 
znnnnnnnnnnaadddddddd.zip 
 archivo comprimido que contiene uno o varios 
archivos *.XML. 
 Si el archivo se transmitirá a la DIAN a través del 
servicio asincrónico , entonces la cantidad de 
documentos electrónicos será inferior a 51. 
 Este formato será el único para la entrega de 
archivos comprimidos. 
z: comprimido 
nnnnnnnnnn: NIT del Sujeto Obligado  sin DV, de diez (10) dígitos 
alineados a la derecha y relleno con ceros a la izquierda. 
aa: Dos (2) últimos dígitos año calendario. 
dddddddd: consecutivo del paquete de archivos comprimidos 
enviados; de ocho (8) dígitos hexadecimales alineados a la derecha y 
ajustado a la izquierda con ceros; en el rango: 
00000001 <= FFFFFFFF 
Ejemplo de la décima segunda  Nómina del Sujeto Obligado  con NIT 
800197268 con software propio para el año 2020. 
z0800197268200000000C.zip 
Regla: el consecutivo se iniciará en “00000001” cada primero de 
enero. 

---

## Página 98

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 98 de 269 
 
Nota:  
 El consecutivo “dddddddd” corresponde al envió del archivo .Zip enviado a la entidad. 

---

## Página 99

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 99 de 269 
 
3.6. firma digital del documento: ds:Signature.  
Datos de la firma de acuerdo con xmldsig-core-schema.xsd 
Ver documentación en 
 http://docs.oasis-open.org/ubl/os-UBL-2.1/UBL-2.1.html#S-PROFILES-FOR-UBL-DIGITAL-SIGNATURES  
 https://www.w3.org/TR/XadES/ 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
 ext UBLExtensions     
NominaIndividual||
NominaIndividualDe
Ajuste 
   .../ext:UBLExtensions 
 ext UBLExtension     UBLExtensions    .../ext:UBLExtensions/ext:UBLEx
tension 
 ext ExtensionContent     UBLExtension    .../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent 
DC01 ds Signature Grupo de la firma XadES-EPES G   ExtensionContent 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature 
DC02 ds SignedInfo 
Grupo de información donde contiene la 
firma aplicada a todos los elementos del 
Documento Soporte de Pago de Nómina 
Electrónica, los elementos contenidos 
dentro  del  elemento  SignedProperties  
más  la  clave  pública  contenida  en  el  
elemento KeyInfo. 
G   Signature 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo 

---

## Página 100

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 100 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
DC03 ds CanonicalizationM
ethod 
Algoritmo para organizar los datos según el 
canon usado sobre el elemento 
«SignedInfo» para  la  firma  digital.  
   Signature 1..1 
Para esto se debe usar el valor 
http://www.w3.org/TR/2001/REC-
xml-c14n-20010315. 
1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Ca
nonicalizationMethod 
DC04 ds SignatureMethod El algoritmo de firma usado sobre el 
elemento «SignedInfo»    Signature 1..1 
Puede  ser  cualquiera  de  los  
definidos  en  la especificación   
XML-Signature   Syntax   and   
Processing   
(http://www.w3.org/TR/xmldsig-
core2/#sec-Algorithms) que 
actualmente son: 
RSAwithSHA256=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha256 
RSAwithSHA384=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha384 
RSAwithSHA512=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha512 
1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Sig
natureMethod 
DC05 ds Reference 
Grupo de la primera referencia que 
contiene la firma aplicada de todo el 
documento 
G   Signature 1..1 URI="" 1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference 

---

## Página 101

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 101 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
DC06 ds Transforms Grupo de trasformación del documento G   Reference 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference/ds:Transforms 
DC07 ds TransForm 
Transformación del documento. Se debe 
especificar que la firma se aplica a todo el 
documento y esta se encuentre embebida 
en este. 
   Transforms 1..1 
Algorithm="http://www.w3.org/2
000/09/xmldsig#enveloped-
signature" 
1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference/ds:Transforms/ds:Trans
Form 
DC08 ds DigestMethod El algoritmo de firma usado sobre el 
elemento    Reference 1..1 
Puede  ser  cualquiera  de  los  
definidos  en  la especificación   
XML-Signature   Syntax   and   
Processing   
(http://www.w3.org/TR/xmldsig-
core2/#sec-Algorithms) que 
actualmente son: 
RSAwithSHA256=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha256 
RSAwithSHA384=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha384 
RSAwithSHA512=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha512 
1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference/ds:DigestMethod 

---

## Página 102

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 102 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
DC09 ds DigestValue 
Resultado de aplicar el algoritmo de 
generación hash especificado en el 
“DigestMethod” en codificación base64 
   Reference 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference/ds:DigestValue 
DC10 ds Reference 
Grupo de la segunda referencia donde se 
especifica clave  pública  contenida  en  el  
elemento KeyInfo. 
G   Signature 1..1 URI="#{UUID}-KeyInfo" 1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference 
DC11 ds DigestMethod El algoritmo de firma usado sobre el 
elemento    Reference 1..1 
Puede  ser  cualquiera  de  los  
definidos  en  la especificación   
XML-Signature   Syntax   and   
Processing   
(http://www.w3.org/TR/xmldsig-
core2/#sec-Algorithms) que 
actualmente son: 
RSAwithSHA256=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha256 
RSAwithSHA384=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha384 
RSAwithSHA512=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha512 
1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference/ds:DigestMethod 

---

## Página 103

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 103 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
DC12 ds DigestValue 
Resultado de aplicar el algoritmo de 
generación hash especificado en el 
“DigestMethod” en codificación base64 
   Reference 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference/ds:DigestValue 
DC13 ds Reference 
Grupo de la tercera referencia de los 
elementos contenidos dentro 
“SignedProperties”   
G   Signature 1..1 URI="#xmldsig-{UUID}-
signedprops" 1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference 
DC14 ds DigestMethod El  algoritmo  de  firma  usado  sobre  el  
elemento    Reference 1..1 
Puede  ser  cualquiera  de  los  
definidos  en  la especificación   
XML-Signature   Syntax   and   
Processing   
(http://www.w3.org/TR/xmldsig-
core2/#sec-Algorithms) que 
actualmente son: 
RSAwithSHA256=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha256 
RSAwithSHA384=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha384 
RSAwithSHA512=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha512 
1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference/ds:DigestMethod 

---

## Página 104

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 104 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
DC15 ds DigestValue 
Resultado de aplicar el algoritmo de 
generación hash especificado en el 
“DigestMethod” en codificación base64 
   Reference 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignedInfo/ds:Re
ference/ds:DigestValue 
DC16 ds SignatureValue 
Resultado de aplicar el algoritmo de 
generación hash especificado en el 
“SignatureMethod” en codificación base64 
   Signature 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:SignatureValue 
DC17 ds KeyInfo 
Grupo de información para embeber el 
certificado público requerido para validar la 
firma. 
G   Signature 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:KeyInfo 
DC18 ds X509Data Grupo que contiene el certificado publico 
del que firma el documento G   KeyInfo 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:KeyInfo/ds:X509
Data 
DC19 ds X509Certificate Certificado publico requerido para validar la 
firma del documento electronico    X509Data 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:KeyInfo/ds:X509
Data/ds:X509Certificate 
DC20 ds Object Grupo de objetos para definir las 
propiedades de la firma G   Signature 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:Object 
DC21 xade
s 
QualifyingProperti
es 
Grupo de elementos calificables de 
comprobación del firma G   Object 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:Object/xades:Qu
alifyingProperties 

---

## Página 105

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 105 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
DC22 xade
s SignedProperties Grupo de elementos para definir las 
propiedades G   QualifyingProperties 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:Object/xades:Qu
alifyingProperties/xades:Signed
Properties 
DC23 xade
s 
SignedSignaturePr
operties 
Grupo de elementos para definir las 
propiedades de la firma G   SignedProperties 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:Object/xades:Qu
alifyingProperties/xades:Signed
Properties/xades:SignedSignatur
eProperties 
DC24 xade
s SigningTime Fecha y Hora de generación    SignedSignaturePro
perties 1..1 
Es deber de los emisores de 
nómina electrónicos que los 
sistemas computacionales que 
utilicen para el firmado de los 
documentos deberán estar 
sincronizados con el reloj de la 
súper intendencia de industria y 
comercio el cual determina la 
hora legal 
colombiana.http://www.sic.gov.co
/hora-legal-colombiana 
1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:Object/xades:Qu
alifyingProperties/xades:Signed
Properties/xades:SignedSignatur
eProperties/xades:SigningTime 

---

## Página 106

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 106 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
DC25 xade
s SigningCertificate 
Grupo de elemento que contiene la cadena 
de confianza del certificado con el que se 
firmó el documento. 
G   SignedSignaturePro
perties 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:Object/xades:Qu
alifyingProperties/xades:Signed
Properties/xades:SignedSignatur
eProperties/xades:SigningCertifi
cate 
DC26 xade
s Cert Grupo para definir un certificado G   SignedSignaturePro
perties 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:Object/xades:Qu
alifyingProperties/xades:Signed
Properties/xades:SignedSignatur
eProperties/xades:SigningCertifi
cate/xades:Cert 
DC27 xade
s CertDigest Grupo de cifrado del certificado G   SignedSignaturePro
perties 1..1  1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:Object/xades:Qu
alifyingProperties/xades:Signed
Properties/xades:SignedSignatur
eProperties/xades:SigningCertifi
cate/xades:Cert/xades:CertDige
st 

---

## Página 107

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 107 de 269 
 
ID ns Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
DC28 ds DigestMethod El algoritmo de firma usado sobre el 
elemento    SignedSignaturePro
perties 1..1 
Puede ser cualquiera de los 
definidos en la especificación 
XML-Signature Syntax and 
Processing 
(http://www.w3.org/TR/xmldsig-
core2/#sec-Algorithms) que 
actualmente son: 
RSAwithSHA256=http://www.w3.
org/2001/04/xmldsig-more#rsa-
sha256 
1 
.../ext:UBLExtensions/ext:UBLEx
tension/ext:ExtensionContent/d
s:Signature/ds:Object/xades:Qu
alifyingProperties/xades:Signed
Properties/xades:SignedSignatur
eProperties/xades:SigningCertifi
cate/xades:Cert/xades:CertDige
st/ds:DigestMethod 
 
3.7. Respuesta DIAN con validaciones de documentos Nomina: ApplicationResponse. 
Tal como sucede con el modelo de Factura Electrónica en Validación Previa, los Documentos Soporte de Pago de Nómina Electrónica la 
DIAN devolverá la validación en un ApplicationRepsonse firmado por la entdad. 
Son adoptadas las siguientes definiciones: 
 Documento Electrónico: un Documento Soporte de Pago de Nómin a Electrónica o una Nota de Ajuste del Documento Soporte de 
Pago de Nómina Electrónica; y 
 Evento: una ocurrencia relacionada con un Documento Electrónico, declarada por una entidad relacionada con estos documentos. 
3.7.1. Garantía de que el evento será registrado en el documento correcto. 
Algunos eventos necesitan que la persona o entidad que lo registra tenga absoluta seguridad del contenido del documento a que 
se refieren, y que este documento existe en la base de datos de la DIAN.  

---

## Página 108

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 108 de 269 
 
Estos eventos requieren, para su registro, que se informe, en el cuerpo del documento las claves principales del documento a la 
que se esta aplicando el evento. 
3.7.2. Relacionamientos mutuos entre los eventos. 
 
Tabla 7 – Relacionamientos Mutuos Entre los Eventos 
 
 
 
 
 
La  
Tabla 7 muestra los efectos del registro de un evento sobre la posibilidad que otro evento sea registrado en el mismo documento 
electrónico. Los códigos y nombres de los eventos, que se utilizan en la  
Tabla 7 y en los elementos /ApplicationResponse/cac:DocumentResponse/cac:Response/cbc:ResponseCode y 
/ApplicationResponse/cac:DocumentResponse/cac:Response/cbc:Description, 
Es posible la existencia de casos en los cuales exista conflicto entre declaraciones; eso ocurre cuando no existe manera automática 
de decidir cuál de las dos informaciones debe prevalecer sobre la otra. En tales situaciones, será necesario intervención de la DIAN 
para resolver el conflicto, probablemente por medio de contacto con uno o ambos los declarantes. 
 
Las definiciones de los eventos se detallan en cada uno de los ítems que siguen el cuerpo común, detallado a continuación. 
  Impedido por 
Eventos   02 04 
¡Error! No se encuentra el origen de la referencia.  02  X 
¡Error! No se encuentra el origen de la referencia.  04 X  

---

## Página 109

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 109 de 269 
 
3.7.3. Detalles de cada evento. 
3.7.3.1. Documento validado por la DIAN. 
Este documento es la respuesta del servicio de validación de la DIAN, cuando el documento electrónico enviado al 
servicio de validación previa es validado exitosamente por la DIAN. 
Teniendo en cuenta las definiciones del presente anexo, la DIAN puede emitir un ApplicationResponse Documento 
validado por la DIAN con notificaciones. 
Este evento debe ser enviado por la DIAN al emisor del DE validado. 
Responsable por la generación del DE: DIAN 
Efecto: El DE referenciado tiene validez de acuerdo con lo que dispone la normatividad vigente. 
Cardinalidad: Solo se puede generar si y solamente el resultado de la validación es exitosa para un determina do 
documento electrónico. 
Detalles particulares del DE ApplicationResponse Documento validado por la DIAN 
ID NS Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
AAH01 cac DocumentRespon
se 
Grupo de información del 
evento a ser registrado G   ApplicationRespons
e 1..1  1.0 /ApplicationResponse/cac:Docum
entResponse 
AAH02 cac Response Descripción del evento 
registrado G   DocumentResponse 1..1  1.0 /ApplicationResponse/cac:Docum
entResponse/cac:Response 
AAH03 cbc ResponseCode Código del evento registrado E N 3 Response 1..1 Debe contener “02” 
 1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:Response/cbc: 
ResponseCode 
AAH04 cbc Description Descripción del evento 
registrado E A 15-
100 Response 1..1 Debe contener el literal “Documento 
validado por la DIAN” 1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:Response/cbc:D
escription 

---

## Página 110

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 110 de 269 
 
ID NS Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
AAH05 cac DocumentReferen
ce 
Documento al cual está 
referenciado el evento siendo 
registrado 
G   DocumentResponse 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:DocumentRefere
nce 
AAH06 cbc ID Prefijo y Número del 
documento referenciado E A 12 DocumentReferenc
e 0..1 ../cbc:ID 1.0 ../cac:DocumentReference/cbc:ID 
AAH07 cbc UUID CUNE del documento 
referenciado E A 96 DocumentReferenc
e 0..1 Notificación: si este CUNE no existe en la 
base de datos de la DIAN 1.0 ../cac:DocumentReference/cbc:U
UID 
AAH08 cbc @schemeName Identificador del esquema de 
identificación A A 11 UUID 1..1 
Algoritmo utilizado para el cálculo del 
CUFE 
Ver lista de valores posibles en 0 
Rechazo: si el contenido de este atributo 
no corresponde a algún de los valores de 
la columna “Código” 
1.0 ../cac:DocumentReference/cbc:U
UID/@schemeName 
AAH09 cbc DocumentTypeCo
de 
Identificador del tipo de 
documento de referencia  A N 2 DocumentReferenc
e 1..1 
Rechazo: Si este elemento no 
corresponde a un valor de la columna 
"Código" de uso “Tipo de Documento” 
1.0 ../cac:DocumentReference/cbc:Do
cumentTypeCode 
AAI01 cac LineResponse Grupo de información para 
registro de la anotación G   DocumentResponse 1..1  1.0 /ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
AAI02 cac LineReference 
Grupo de información 
correspondiente a la 
anotación 
G   LineResponse 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:LineReference 
AAI03 cbc LineID  E N  LineReference 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse/ca
c:LineReference/cbc:LineID 
AAI04 cac Response Grupo de información del NSU 
del documento validado G   LineResponse 1..N  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response 

---

## Página 111

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 111 de 269 
 
ID NS Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
AAI05 cbc ResponseCode Código de la notificación E A 4-10 Response 1..1 
Si  TODAS las reglas de validación previas 
estan ok, entonces se generara una 
Aprobación  del documento el cual será 
informado con  el literal “0000”. 
 
Si algunas reglas de validación previas 
apunta a una discrepancia menos 
importante (reglas no mandatorias), 
pero que asimismo merece que se 
advierta al emisor de un posible 
problema con las información del 
archivo, entonces se generara una 
Aprobación con Notificaciones del 
documento el cual será informado con  el 
literal “0001” 
1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response/cbc:ResponseCode 
AAI06 cbc Description NSU del documento validado E A 4-150 Response 1..1 NSU generado por la DIAN para el 
documento validado 1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response/cbc:Description 
AAI04 cac Response 
Grupo de información 
correspondiente a las 
notificaciones 
G   LineResponse 1..N Grupo generado si existe por lo menos 
una notificación  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response 
AAI05 cbc ResponseCode Código de la notificación E A 4-10 Response 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response/cbc:ResponseCode 
AAI06 cbc Description Descripción de la notificación E A 4-150 Response 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response/cbc:Description 
 

---

## Página 112

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 112 de 269 
 
3.7.3.2. Documento Rechazado por la DIAN. 
Este documento es la respuesta del servicio de validación de la DIAN, cuando el documento electrónico enviado al 
servicio de validación previa no es validado exitosamente por la DIAN. Este evento debe ser enviado por la DIAN al 
emisor del DE validado, en el mismo contenedor del DE. 
Responsable por la generación del DE: DIAN 
Efecto: El DE NO tiene validez de acuerdo con lo que dispone la normatividad vigente. 
Cardinalidad: Debe ser generado como resultado de una validación no exitosa ante la DIAN  para un determinado 
documento electrónico. 
 
ID NS Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
AAH01 cac DocumentRespon
se 
Grupo de información del evento 
a ser registrado G   ApplicationRespons
e 1..1  1.0 /ApplicationResponse/cac:Docum
entResponse 
AAH02 cac Response Descripción del evento registrado G   DocumentResponse 1..1  1.0 /ApplicationResponse/cac:Docum
entResponse/cac:Response 
AAH03 cbc ResponseCode Código del evento registrado E N 3 Response 1..1 Debe contener “04” 
 1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:Response/cbc: 
ResponseCode 
AAH04 cbc Description Descripción del evento registrado E A 15-
100 Response 1..1 Debe contener el literal “Documento 
Rechazado por la DIAN” 1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:Response/cbc:D
escription 
AAH05 cac DocumentReferen
ce 
Documento al cual está 
referenciado el evento siendo 
registrado 
G   DocumentResponse 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:DocumentRefere
nce 
AAH06 cbc ID Prefijo y Número del documento 
referenciado E A 12 AddtionalDocument
Reference 0..1 ../cbc:ID 1.0 ../cac:DocumentReference/cbc:ID 
AAH07 cbc UUID CUNE del documento 
referenciado E A 96 AddtionalDocument
Reference 0..1 Notificación si esta UUID no existe en la 
base de datos de la DIAN 1.0 ../cac:DocumentReference/cbc:U
UID 

---

## Página 113

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 113 de 269 
 
ID NS Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
AAH08 cbc @schemeName Identificador del esquema de 
identificación A A 11 UUID 1..1 
Algoritmo utilizado para el cáculo del 
CUFE 
Ver lista de valores posibles en 0 
Rechazo si el contenido de este atributo 
no corresponde a algún de los valores 
de la columna “Código” 
1.0 ../cac:DocumentReference/cbc:U
UID/@schemeName 
AAH09 cbc DocumentTypeCo
de 
Identificador del tipo de 
documento de referencia  A N 2 DocumentReferenc
e 1..1 
Ver lista de valores posibles en 5.1.3 
Rechazo:  
Si este elemento no corresponde a un 
valor de la columna "Código" de uso 
“Tipo de Documento” 
1.0 ../cac:DocumentReference/cbc:Do
cumentTypeCode 
AAI01 cac LineResponse Grupo de información para 
registro de la anotación G   DocumentResponse 1..1  1.0 /ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
AAI02 cac LineReference Grupo de información 
correspondiente a la anotación G   LineResponse 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:LineReference 
AAI03 cbc LineID  E N  LineReference 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse/ca
c:LineReference/cbc:LineID 
AAI04 cac Response Grupo de información del NSU del 
documento validado G   LineResponse 1..N  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response 
AAI05 cbc ResponseCode Código de la notificación E A 4-10 Response 1..1 
Si algunas reglas de validación previas  
apunta a una a mas discrepancia grave, 
que indica que las información del 
archivo no pueden ser utilizadas de 
manera confiable o de manera legal;, 
entonces se generara un rechazo, el 
cual contendrán las  Notificaciones del 
documento el cual será informado con  
el literal “0003” 
1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response/cbc:ResponseCode 

---

## Página 114

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 114 de 269 
 
ID NS Campo Descripción T F Tam Padre Oc Observaciones V Xpath 
AAI06 cbc Description NSU del documento NO validado E A 4-150 Response 1..1 NSU generado por la DIAN para el 
documento NO validado 1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response/cbc:Description 
AAI04 cac Response 
Grupo de información 
correspondiente a las 
notificaciones 
G   LineResponse 1..N Grupo generado si existe por lo menos 
una notificación  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response 
AAI05 cbc ResponseCode Código de la notificación E A 4-10 Response 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response/cbc:ResponseCode 
AAI06 cbc Description Descripción de la notificación E A 4-150 Response 1..1  1.0 
/ApplicationResponse/cac:Docum
entResponse/cac:LineResponse 
/cac:Response/cbc:Description 
 
A continuación, se puede visualizar la estructura simplificada, asumiendo un documento rechazado con dos notificaciones 
 
<?xml version="1.0" encoding="utf-8" standalone="no"?> 
<ApplicationResponse xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents -2" 
xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents -2" 
xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1" 
xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse -2"> 
 <ext:UBLExtensions> 
  <ext:UBLExtension> 
   <ext:ExtensionContent> 
    <sts:DianExtensions> 
     <sts:InvoiceSource> 
      <cbc:IdentificationCode listAgencyID="6" listAgencyName="United Nations Economic Commission for 
Europe" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1">CO</cbc:IdentificationCode> 

---

## Página 115

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 115 de 269 
 
     </sts:InvoiceSource> 
     <sts:SoftwareProvider> 
      <sts:ProviderID schemeID="4" schemeName="31" schemeAgencyID="195" schemeAgencyName="CO, 
DIAN (Dirección de Impuestos y Aduanas Nacionales)">800197268</sts:ProviderID> 
      <sts:SoftwareID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y 
Aduanas Nacionales)">...</sts:SoftwareID> 
     </sts:SoftwareProvider> 
     <sts:SoftwareSecurityCode schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos 
y Aduanas Nacionales)">...</sts:SoftwareSecurityCode> 
     <sts:AuthorizationProvider> 
      <sts:AuthorizationProviderID schemeID="4" schemeName="31" schemeAgencyID="195" 
schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">800197268</sts:AuthorizationProviderID>  
     </sts:AuthorizationProvider> 
    </sts:DianExtensions> 
   </ext:ExtensionContent> 
  </ext:UBLExtension> 
  <ext:UBLExtension> 
   <ext:ExtensionContent> 
    <ds:Signature> Información de la firma </ds:Signature>        
   </ext:ExtensionContent> 
  </ext:UBLExtension> 
 </ext:UBLExtensions> 
 <cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID> 
 <cbc:CustomizationID>1</cbc:CustomizationID> 
 <cbc:ProfileID>DIAN 2.1</cbc:ProfileID> 
 <cbc:ProfileExecutionID>2</cbc:ProfileExecutionID> 

---

## Página 116

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 116 de 269 
 
 <cbc:ID>63200030</cbc:ID> 
 <cbc:UUID schemeName="CUDE-
SHA384">43a0738ec86966f9a7eb3314387508ca6adbf852a855fb4fc9b0c9396b87f64c9a711bd0046b3ef4c83b1c2c3eec9d32</cbc:UUID>  
 <cbc:IssueDate>2021-01-25</cbc:IssueDate> 
 <cbc:IssueTime>19:30:03-05:00</cbc:IssueTime> 
 <cac:SenderParty> 
  <cac:PartyTaxScheme> 
   <cbc:RegistrationName>Unidad Especial Dirección de Impuestos y Aduanas Nacionales</cbc:RegistrationName>  
   <cbc:CompanyID schemeID="4" schemeName="">800197268</cbc:CompanyID>  
   <cac:TaxScheme> 
    <cbc:ID>01</cbc:ID> 
    <cbc:Name>IVA</cbc:Name> 
   </cac:TaxScheme> 
  </cac:PartyTaxScheme> 
 </cac:SenderParty> 
 <cac:ReceiverParty> 
  <cac:PartyTaxScheme> 
   <cbc:RegistrationName>Empresa Emisora</cbc:RegistrationName> 
   <cbc:CompanyID schemeID="" schemeName="">456789123</cbc:CompanyID>  
   <cac:TaxScheme> 
    <cbc:ID>01</cbc:ID> 
    <cbc:Name>IVA</cbc:Name> 
   </cac:TaxScheme> 
  </cac:PartyTaxScheme> 
 </cac:ReceiverParty> 
 <cac:DocumentResponse> 

---

## Página 117

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 117 de 269 
 
  <cac:Response> 
   <cbc:ResponseCode>04</cbc:ResponseCode> 
   <cbc:Description>Documento rechazado por la DIAN</cbc:Description>  
  </cac:Response> 
  <cac:DocumentReference> 
   <cbc:ID>CD001</cbc:ID> 
   <cbc:UUID schemeName="CUNE-
SHA384">210b27d90355411c95bae7532c91eb8e2fb57507c0a1cd55599c5063d65b4ac890016f8d5a6e48dbb3e949fc4994606f</cbc:UUID>  
  </cac:DocumentReference> 
  <cac:LineResponse> 
   <cac:LineReference> 
    <cbc:LineID>1</cbc:LineID> 
   </cac:LineReference> 
   <cac:Response> 
    <cbc:ResponseCode>0000</cbc:ResponseCode> 
    <cbc:Description>0</cbc:Description> 
   </cac:Response> 
  </cac:LineResponse> 
  <cac:LineResponse> 
   <cac:LineReference> 
    <cbc:LineID>2</cbc:LineID> 
   </cac:LineReference> 
   <cac:Response> 
    <cbc:ResponseCode>NIE901</cbc:ResponseCode> 
    <cbc:Description>Error al validar regla Nómina Individual Electrónica - NominaIndividual (raíz): Namespace prefix 
'xmlns' has not been declared</cbc:Description> 

---

## Página 118

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
                 
      Página 118 de 269 
 
   </cac:Response> 
  </cac:LineResponse> 
  <cac:LineResponse> 
   <cac:LineReference> 
    <cbc:LineID>3</cbc:LineID> 
   </cac:LineReference> 
   <cac:Response> 
    <cbc:ResponseCode>NIE153</cbc:ResponseCode> 
    <cbc:Description>Se debe colocar el Concepto Salarial</cbc:Description>  
   </cac:Response> 
  </cac:LineResponse> 
 </cac:DocumentResponse> 
</ApplicationResponse>

---

## Página 119

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 119 de 269 
 
4. Inconvenientes tecnológicos. 
4.1. Por parte del Sujeto Obligado. 
Cuando se presenten inconvenientes tecnológicos por parte del sujeto obligado que impidan la transmisión 
de la información para la validación, el  Documento Soporte de Pago de Nómina Electrónica  se deberá  
trasmitir en un plazo máximo de cuarenta y ocho (48) horas contadas a partir del día siguiente al que se 
haya superado el inconveniente tecnológico. 
 
4.2. Por parte de la DIAN. 
Los sujetos obligados que utilicen los servicios del Documento Soporte de Pago de Nómina Electrónica que 
la DIAN disponga, podrán establecer automáticamente el procedimiento para establecer si la DIAN presenta 
inconvenientes tecnológicos,  señalado en la presente resolución, si se cumplen las siguientes condiciones: 
 Detección del error “500 – Internal Server Error” o “503 – Service Unavailable” o error “507 – Insufficient 
Storage” o error “508 - Loop Detected” o error “403 Site Disabled”. Únicamente estos errores. 
 Transmitir nuevamente a la DIAN el  Documento Soporte de Pago de Nómina Electrónica transcurridos 
20 segundos después de la detección del error “500 – Internal Server Error” o “503 – Service 
Unavailable” o error “507 – Insufficient Storage” o error “508 - Loop Detected”. Si persiste el error, se 
deben realizar dos (2) intentos más, cada uno en intervalo de 20 segundos. Al finalizar el último intento, 
es decir un minuto después de la transmisión inicial y si persiste la condición de error, el Sujeto Obligado 
deberá esperar a que se restablezca el servicio de recepción del Documento Soporte de Pago de Nómina 
Electrónica para continuar con la transmisión de las mismas. 
 Mantener o archivar las evidencias del error “500 – Internal Server Error” o “503 – Service Unavailable” 
o error “507 – Insufficient Storage” o error “508 - Loop Detected” en sus registros digitales. 
 Monitorear la conexión y los servicios web de la DIAN de l Documento Soporte de Pago de Nómina 
Electrónica a los 30 minutos después de haber recibido el primer mensaje (500 o 503), con el fin de 
identificar el restablecimiento del servicio por parte de la DIAN. Mientras que el servicio no este 
restablecido, continuar el monitoreo de la conexión y lo s servicios web de la DIAN de l Documento 
Soporte de Pago de Nómina Electrónica. 
 Si el servicio está restablecido, tra nsmitir normalmente el Documento Soporte de Pago de Nómina 
Electrónica. 
 El Sujeto Obligado tendrá 48 horas para transmitir a la DIAN el Documento Soporte de Pago de Nómina 
Electrónica, una vez el emisor de nómina detecte que el servicio de la DIAN está activo. 
 
5. Tablas de Contenidos de Elementos y de Atributos. 

---

## Página 120

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 120 de 269 
 
5.1. Códigos Relacionados con Documentos. 
5.1.1. Ambiente de Destino del Documento: Ambiente. 
Documentos enviados para el ambiente de pruebas no producen ningún tipo de efecto; documentos 
enviados para el ambiente de producción producen efectos para todas las finalidades legales: 
tributarios, financieros, económicos, comerciales y de del derecho del consumidor. 
 
Código Ambiente de Destino 
1 Producción 
2 Pruebas 
 
5.1.2. Algoritmo: EncripCUNE. 
 
5.1.2.1. Algoritmo de CUNE: EncripCUNE. 
Algoritmo utilizado para cálculo del Código Único de Documento Soporte de Pago 
de Nómina Electrónica. 
 
 
 
 
5.2. Códigos para identificación fiscal. 
5.2.1. Documento de identificación (Tipo de Identificador Fiscal): TipoDocumento. 
 
Código Significado 
11  Registro civil  
12  Tarjeta de identidad  
13  Cédula de ciudadanía  
21  Tarjeta de extranjería  
22  Cédula de extranjería  
31  NIT 
41  Pasaporte  
42  Documento de identificación extranjero  
47 PEP 
50 NIT de otro país 
91  NUIP *  
 
* Deberá utilizarse solamente para el empleado, debido a que este tipo de documento no pertenece 
a los tipos de documento en la base de datos del RUT 
 
Código 
CUNE-SHA384 

---

## Página 121

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 121 de 269 
 
5.3. Códigos Diversos. 
5.3.1. Lenguaje (ISO 639): Idioma. 
La ISO 639: Norma internacional para los códigos de idioma, tiene el propósito de establecer códigos 
reconocidos internacionalmente (ya sea 2, 3, o 4 letras de largo) para la representación de las lenguas 
o familias lingüísticas. 
La ISO 639 se compone de seis partes diferentes: 
 Parte 1 (ISO 639-1:2002) proporciona un código de 2 letras que ha sido diseñado para representar 
a la mayoría de los idiomas más importantes del mundo. 
 Parte 2 (ISO 639 -2:1998) proporciona un código de 3 letras, lo que da más combinaciones 
posibles, por lo que la norma ISO 639-2:1998 puede cubrir más idiomas. 
 Parte 3 (ISO 639 -3:2007) proporciona un código de 3 letras y tiene como objetivo dar como 
completa una lista de idiomas como sea posible, incluyendo la vida, extinto y lenguas antiguas. 
 Parte 4 (ISO 639 -4:2010) da los principios generales de la codificación de la lengua y establece 
directrices para el uso de ISO 639. 
 Parte 5 (ISO 639 -5:2008) proporciona un código de 3 letras para las familias y grupos (vivos y 
extintos) del lenguaje. 
 Parte 6 (ISO 639 -6:2009) proporciona un código de 4 letras, útil cuando hay una necesidad 
potencial para cubrir toda la gama de lenguas, familias y grupos lingüísticos y variantes lingüísticas 
en un sistema. 
En los atributos languageID deberán ser utilizados los códigos de 2 letras de la ISO 639-1. 
 
Nombre de idioma ISO 639-1 ISO 639-2 Nombre de idioma ISO 639-1 ISO 639-2 
Abkhaz ab abk Lingala Ln lin 
Afar aa aar Lao Lo lao 
Africanos af afr Lituano Lt lit 
Akan ak aka Luba-Katanga Lu lub 
Albania sq sqi Letonia Lv lav 
Amárico am amh Manx Gv glv 
Árabe ar ara Macedonia Mk mkd 
Aragonés an arg Madagascar Mg mlg 
Armenio hy hye Malayo Ms msa 
Assamese los asm Malayalam Ml mal 
Avaric av ava Maltés Mt mlt 
Avestan ae ave Māori Mi mri 
Aymara ay aym Maratí (Marathi) Mr mar 
Azerbaiyán az aze De las Islas Marshall Mh mah 
Bambara bm bam Mongolia Mn mon 
Bashkir ba bak Nauru Na nau 
Vasco eu eus Navajo, Navaho Nv nav 

---

## Página 122

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 122 de 269 
 
Nombre de idioma ISO 639-1 ISO 639-2 Nombre de idioma ISO 639-1 ISO 639-2 
Belarús be bel Noruego Bokmål Nb nob 
Bengalí bn ben Ndebele del Norte Nd nde 
Bihari bh bih Nepali Ne nep 
Bislama bi bis Ndonga Ng ndo 
Bosnia bs bos Noruego Nynorsk Nn nno 
Breton br bre Noruego No nor 
Búlgaro bg bul Nuosu Ii iii 
Burmese my mya Ndebele del sur nr nbl 
Catalán ca cat Occitano oc oci 
Chamorro ch cha Ojibwe, Ojibwa oj oji 
Chechenio ce che 
Antiguo eslavo eclesiástico, Iglesia 
eslava, eslavo eclesiástico, antiguo 
Búlgaro, Esclavo viejo 
cu chu 
Chichewa, Chewa, 
Nyanja ny nya Oromo om orm 
Chino zh zho Oriya or ori 
Chuvashia cv chv Osetia del Sur, osetio os oss 
Cornualles kw cor Panjabi, Punjabi pa pan 
Corso co cos Pāli pi pli 
Cree cr cre Persa fa fas 
Croacia hr hrv Polaco pl pol 
Checo cs ces Pashto, Pushto ps pus 
Danés da dan Portugués pt por 
Divehi, Dhivehi, 
Maldivas dv div Quechua qu que 
Holandés nl nld Romanche rm roh 
Dzongkha dz dzo Kirundi rn run 
Inglés en eng Rumania, Moldavia, Moldavan ro ron 
Esperanto eo epo Ruso ru rus 
Estonia et est Sánscrito (samskrta) sa san 
Ewe ee ewe Sardo sc srd 
Faroese fo fao Sindhi sd snd 
Fiji fj fij Sami del norte se sme 
Finlandés fi fin Samoa sm smo 
Francés fr fra Sango sg sag 
Fula, Fulah, Pulaar, 
Pular ff ful Serbio sr srp 
Galicia gl glg Gaélico escocés, gaélico gd gla 

---

## Página 123

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 123 de 269 
 
Nombre de idioma ISO 639-1 ISO 639-2 Nombre de idioma ISO 639-1 ISO 639-2 
Georgiano ka kat Shona sn sna 
Alemán de deu Cingalés, singalés si sin 
Griego Moderno el ell Eslovaca sk slk 
Guaraní gn grn Esloveno sl slv 
Gujarati gu guj Somalí so som 
Haitiano, creole 
haitiano ht hat Southern Sotho st sot 
Hausa ha hau Español, castellano es spa 
Hebreo (moderno) he heb Sundanese su sun 
Herero hz her Swahili sw swa 
Hindi hi hin Swati ss ssw 
Hiri Motu ho hmo Sueco sv swe 
Húngaro hu hun Tamil ta tam 
Interlingua ia ina Telugu te tel 
Indonesio id ind Tayikistán tg tgk 
Interlingue ie ile Tailandia th tha 
Irlanda ga gle Tigrinya ti tir 
Igbo ig ibo Tibetano estándar, Tibetano, 
Central bo bod 
Inupiaq ik ipk Turkmenistán tk tuk 
Ido io ido Tagalo tl tgl 
Islandés is isl Tswana tn tsn 
Italiano it ita Tonga (Islas Tonga) to ton 
Inuktitut iu iku Turco tr tur 
Japonés ja jpn Tsonga ts tso 
Javanés jv jav Tártara tt tat 
Kalaallisut, 
Groenlandia kl kal Twi tw twi 
Canarés kn kan Tahitian ty tah 
Kanuri kr kau Uighur, Uyghur ug uig 
Cachemira ks kas Ucrania uk ukr 
Kazajstán kk kaz Urdu ur urd 
Khmer km khm Uzbeko uz uzb 
Kikuyu, Gikuyu ki kik Venda ve ven 
Kinyarwanda rw kin Vietnamita vi vie 
Kirguises, Kirguistán ky kir Volapük vo vol 
Komi kv kom Valonia wa wln 
Kongo kg kon Galés cy cym 

---

## Página 124

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 124 de 269 
 
Nombre de idioma ISO 639-1 ISO 639-2 Nombre de idioma ISO 639-1 ISO 639-2 
Corea ko kor Wolof wo wol 
Kurdo ku kur Oeste de Frisia fy fry 
Kwanyama, 
Kuanyama kj kua Xhosa xh xho 
Latin la lat Yiddish yi yid 
Luxemburgués, 
Luxemburgués lb ltz Yoruba yo yor 
Luganda lg lug Zhuang, Chuang za zha 
Limburgués, 
Limburgan, 
Limburger 
li lim Zulu zu zul 
 
5.3.2. Moneda (ISO 4217): TipoMoneda. 
El estándar internacional ISO 4217 fue creado por la ISO con el objetivo de definir códigos de tres letras 
para todas las divisas del mundo. Las dos primeras letras del código son las dos letras del código del 
país de la divisa según el estándar ISO 3166-1 y la tercera es normalmente la inicial de la divisa en sí. 
 
Código Divisa Países que Adoptan 
AED Dírham de los Emiratos 
Árabes Unidos Emiratos Árabes Unidos 
AFN Afgani Afganistán 
ALL Lek Albania 
AMD Dram armenio Armenia 
ANG Florín antillano neerlandés Curazao, Saint Maarten 
AOA Kwanza Angola 
ARS Peso argentino Argentina 
AUD Dólar australiano Australia, Isla de Navidad, Islas Cocos, Islas Heard y McDonald, Kiribati, 
Nauru, Norfolk, Tuvalu 
AWG Florín arubeño Aruba 
AZN Manat azerbaiyano Azerbaiyán 
BAM Marco convertible Bosnia y Herzegovina 
BBD Dólar de Barbados Barbados 
BDT Taka Bangladés 
BGN Lev búlgaro Bulgaria 
BHD Dinar bareiní Baréin 
BIF Franco de Burundi Burundi 
BMD Dólar bermudeño Bermudas 
BND Dólar de Brunéi Brunéi 

---

## Página 125

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 125 de 269 
 
Código Divisa Países que Adoptan 
BOB Boliviano Bolivia 
BOV MVDOL Bolivia 
BRL Real brasileño Brasil 
BSD Dólar bahameño Bahamas 
BTN Ngultrum Bután 
BWP Pula Botsuana 
BYR Rublo bielorruso Bielorrusia 
BZD Dólar beliceño Belice 
CAD Dólar canadiense Canadá 
CDF Franco congoleño República Democrática del Congo 
CHE Euro WIR Suiza 
CHF Franco suizo Liechtenstein, Suiza 
CHW Franco WIR Suiza 
CLF Unidad de fomento Chile 
CLP Peso chileno Chile 
CNY Yuan chino China 
COP Peso colombiano Colombia 
COU Unidad de valor real Colombia 
CRC Colón costarricense Costa Rica 
CUC Peso convertible Cuba 
CUP Peso cubano Cuba 
CVE Escudo caboverdiano Cabo Verde 
CZK Corona checa República Checa 
DJF Franco yibutiano Yibuti 
DKK Corona danesa Dinamarca, Groenlandia, Islas Feroe 
DOP Peso dominicano República Dominicana 
DZD Dinar argelino Argelia 
EGP Libra egipcia Egipto 
ERN Nakfa Eritrea 
ETB Birr etíope Etiopía 
EUR Euro 
Alemania, Andorra, Austria, Bélgica, Chipre, Ciudad del Vaticano, 
Eslovaquia, Eslovenia, España, Estonia, Finlandia, Francia, Grecia, 
Guadalupe, Guayana Francesa, Irlanda, Italia, Letonia, Lituania, 
Luxemburgo, Malta, Martinica, Mayotte, Mónaco, Montenegro, Países 
Bajos, Portugal, Reunión, San Bartolomé, San Marino, San Martín, San 
Pedro y Miquelón, Tierras Australes y Antárticas Francesas, Unión 
Europea 
FJD Dólar fiyiano Fiyi 

---

## Página 126

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 126 de 269 
 
Código Divisa Países que Adoptan 
FKP Libra malvinense Islas Malvinas 
GBP Libra esterlina Guernsey, Isla de Man, Jersey, Reino Unido 
GEL Lari Georgia 
GHS Cedi ghanés Ghana 
GIP Libra de Gibraltar Gibraltar 
GMD Dalasi Gambia 
GNF Franco guineano Guinea 
GTQ Quetzal Guatemala 
GYD Dólar guyanés Guyana 
HKD Dólar de Hong Kong Hong Kong 
HNL Lempira Honduras 
HRK Kuna Croacia 
HTG Gourde Haití 
HUF Forinto Hungría 
IDR Rupia indonesia Indonesia 
ILS Nuevo shéquel israelí Israel 
INR Rupia india Bután, India 
IQD Dinar iraquí Irak 
IRR Rial iraní Irán 
ISK Corona islandesa Islandia 
JMD Dólar jamaiquino Jamaica 
JOD Dinar jordano Jordania 
JPY Yen Japón 
KES Chelín keniano Kenia 
KGS Som Kirguistán 
KHR Riel Camboya 
KMF Franco comorense Comoras 
KPW Won norcoreano Corea del Norte 
KRW Won Corea del Sur 
KWD Dinar kuwaití Kuwait 
KYD Dólar de las Islas Caimán Islas Caimán 
KZT Tenge Kazajistán 
LAK Kip Laos 
LBP Libra libanesa Líbano 
LKR Rupia de Sri Lanka Sri Lanka 
LRD Dólar liberiano Liberia 
LSL Loti Lesoto 

---

## Página 127

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 127 de 269 
 
Código Divisa Países que Adoptan 
LYD Dinar libio Libia 
MAD Dírham marroquí Marruecos, República Árabe Saharaui Democrática 
MDL Leu moldavo Moldavia 
MGA Ariary malgache Madagascar 
MKD Denar Macedonia 
MMK Kyat Myanmar 
MNT Tugrik Mongolia 
MOP Pataca Macao 
MRO Uguiya Mauritania 
MUR Rupia de Mauricio Mauricio 
MVR Rufiyaa Maldivas 
MWK Kwacha Malaui 
MXN Peso mexicano México 
MXV Unidad de Inversión (UDI) 
mexicana México 
MYR Ringgit malayo Malasia 
MZN Metical mozambiqueño Mozambique 
NAD Dólar namibio Namibia 
NGN Naira Nigeria 
NIO Córdoba Nicaragua 
NOK Corona noruega Isla Bouvet, Noruega, Svalbard y Jan Mayen 
NPR Rupia nepalí Nepal 
NZD Dólar neozelandés Islas Cook, Islas Pitcairn, Niue, Nueva Zelanda, Tokelau 
OMR Rial omaní Omán 
PAB Balboa Panamá 
PEN Sol Perú 
PGK Kina Papúa Nueva Guinea 
PHP Peso filipino Filipinas 
PKR Rupia pakistaní Pakistán 
PLN Złoty Polonia 
PYG Guaraní Paraguay 
QAR Riyal qatarí Catar 
RON Leu rumano Rumania 
RSD Dinar serbio Serbia 
RUB Rublo ruso Rusia 
RWF Franco ruandés Ruanda 
SAR Riyal saudí Arabia Saudita 
SBD Dólar de las Islas Salomón Islas Salomón 

---

## Página 128

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 128 de 269 
 
Código Divisa Países que Adoptan 
SCR Rupia seychelense Seychelles 
SDG Dinar sudanés Sudán 
SEK Corona sueca Suecia 
SGD Dólar de Singapur Singapur 
SHP Libra de Santa Elena Santa Elena, Ascensión y Tristán de Acuña 
SLL Leone Sierra Leona 
SOS Chelín somalí Somalia 
SRD Dólar surinamés Surinam 
SSP Libra sursudanesa Sudán del Sur 
STD Dobra Santo Tomé y Príncipe 
SVC Colon Salvadoreño El Salvador 
SYP Libra siria Siria 
SZL Lilangeni Suazilandia 
THB Baht Tailandia 
TJS Somoni tayiko Tayikistán 
TMT Manat turcomano Turkmenistán 
TND Dinar tunecino Túnez 
TOP Paʻanga Tonga 
TRY Lira turca Turquía 
TTD Dólar de Trinidad y Tobago Trinidad y Tobago 
TWD Nuevo dólar taiwanés República de China 
TZS Chelín tanzano Tanzania 
UAH Grivna Ucrania 
UGX Chelín ugandés Uganda 
USD Dólar estadounidense 
Caribe Neerlandés, Ecuador, El Salvador, Estados Unidos, Guam, Haití, 
Islas Marianas del Norte, Islas Marshall, Islas Turcas y Caicos, Islas 
ultramarinas de Estados Unidos, Islas Vírgenes Británicas, Islas Vírgenes 
de los Estados Unidos, Micronesia, Palaos, Panamá, Puerto Rico, Samoa 
Americana, Territorio Británico del Océano Índico, Timor Oriental 
USN Dólar estadounidense 
(Siguiente día) Estados Unidos 
UYI Peso en Unidades 
Indexadas (Uruguay) Uruguay 
UYU Peso uruguayo Uruguay 
UZS Som uzbeko Uzbekistán 
VEF Bolívar Venezuela 
VES Bolívar soberano Venezuela 
VND Dong vietnamita Vietnam 

---

## Página 129

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 129 de 269 
 
Código Divisa Países que Adoptan 
VUV Vatu Vanuatu 
WST Tala Samoa 
XAF Franco CFA de África 
Central 
Camerún, Chad, Gabón, Guinea Ecuatorial, República Centroafricana, 
República del Congo 
XAG Plata (una onza troy)  
XAU Oro (una onza troy)  
XBA 
Unidad compuesta 
europea (EURCO) (Unidad 
del mercado de bonos) 
 
XBB 
Unidad Monetaria europea 
(E.M.U.-6) (Unidad del 
mercado de bonos) 
 
XBC 
Unidad europea de cuenta 
9 (E.U.A.-9) (Unidad del 
mercado de bonos) 
 
XBD 
Unidad europea de cuenta 
17 (E.U.A.-17) (Unidad del 
mercado de bonos) 
 
XCD Dólar del Caribe Oriental Anguila, Antigua y Barbuda, Dominica, Granada, Montserrat, San 
Cristóbal y Nieves, San Vicente y las Granadinas, Santa Lucía 
XDR Derechos especiales de 
giro Fondo Monetario Internacional 
XOF Franco CFA de África 
Occidental 
Benín, Burkina Faso, Costa de Marfil, Guinea-Bisáu, Malí, Níger, Senegal, 
Togo 
XPD Paladio (una onza troy)  
XPF Franco CFP Nueva Caledonia, Polinesia Francesa, Wallis y Futuna 
XPT Platino (una onza troy)  
XSU SUCRE Sistema Unitario de Compensación Regional 
XTS Reservado para pruebas  
XUA Unidad de cuenta BAD Banco Africano de Desarrollo 
XXX Sin divisa  
YER Rial yemení Yemen 
ZAR Rand Lesoto, Namibia, Sudáfrica 
ZMW Kwacha zambiano Zambia 
ZWL Dólar zimbabuense Zimbabue 

---

## Página 130

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 130 de 269 
 
5.3.3. Pagos. 
5.3.3.1. Formas de Pago: Forma. 
Código Significado 
1 Contado 
 
5.3.3.2. Medios de Pago: Metodo. 
Definición de los atributos del elemento: 
Código Medio Código Medio 
1 Instrumento no definido 40 Débito Negocio Intercambio Corporativo (CTX) 
2 Crédito ACH 41 Concentración efectivo/Desembolso Crédito 
plus (CCD+)  
3 Débito ACH 42 Consignación bancaria 
4 Reversión débito de demanda ACH 43 Concentración efectivo / Desembolso Débito 
plus (CCD+) 
5 Reversión crédito de demanda ACH  44 Nota cambiaria 
6 Crédito de demanda ACH 45 Transferencia Crédito Bancario 
7 Débito de demanda ACH 46 Transferencia Débito Interbancario 
8 Mantener 47 Transferencia Débito Bancaria 
9 Clearing Nacional o Regional 48 Tarjeta Crédito 
10 Efectivo 49 Tarjeta Débito 
11 Reversión Crédito Ahorro 50 Postgiro 
12 Reversión Débito Ahorro 51 Telex estándar bancario francés 
13 Crédito Ahorro 52 Pago comercial urgente 
14 Débito Ahorro 53 Pago Tesorería Urgente 
15 Bookentry Crédito 60 Nota promisoria 
16 Bookentry Débito 61 Nota promisoria firmada por el acreedor 
17 Concentración de la demanda en efectivo 
/Desembolso Crédito (CCD) 62 Nota promisoria firmada por el acreedor, 
avalada por el banco 
18 Concentración de la demanda en efectivo / 
Desembolso (CCD) débito 63 Nota promisoria firmada por el acreedor, 
avalada por un tercero 
19 Crédito Pago negocio corporativo (CTP) 64 Nota promisoria firmada por el banco 
20 Cheque 65 Nota promisoria firmada por un banco avalada 
por otro banco 
21 Proyecto bancario 66 Nota promisoria firmada  
22 Proyecto bancario certificado 67 Nota promisoria firmada por un tercero avalada 
por un banco 
23 Cheque bancario 70 Retiro de nota por el por el acreedor 
24 Nota cambiaria esperando aceptación 71 Bonos 
25 Cheque certificado 72 Vales 

---

## Página 131

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 131 de 269 
 
Código Medio Código Medio 
26 Cheque Local 74 Retiro de nota por el por el acreedor sobre un 
banco 
27 Débito Pago Negocio Corporativo (CTP) 75 Retiro de nota por el acreedor, avalada por otro 
banco 
28 Crédito Negocio Intercambio Corporativo 
(CTX) 76 Retiro de nota por el acreedor, sobre un banco 
avalada por un tercero 
29 Débito Negocio Intercambio Corporativo 
(CTX) 77 Retiro de una nota por el acreedor sobre un 
tercero 
30 Transferencia Crédito 78 Retiro de una nota por el acreedor sobre un 
tercero avalada por un banco 
31 Transferencia Débito 91 Nota bancaria transferible 
32 Concentración Efectivo / Desembolso 
Crédito plus (CCD+) 92 Cheque local trasferible 
33 Concentración Efectivo / Desembolso 
Débito plus (CCD+) 93 Giro referenciado 
34 Pago y depósito pre acordado (PPD) 94 Giro urgente 
35 Concentración efectivo ahorros / 
Desembolso Crédito (CCD) 95 Giro formato abierto 
36 Concentración efectivo ahorros / 
Desembolso Crédito (CCD) 96 Método de pago solicitado no usado 
37 Pago Negocio Corporativo Ahorros Crédito 
(CTP) 97 Clearing entre partners 
38 Pago Negocio Corporativo Ahorros Débito 
(CTP) 98 Cuentas de Ahorro de Tramite Simplificado 
(CATS)(Nequi, Daviplata, etc) 
39 Crédito Negocio Intercambio Corporativo 
(CTX) ZZZ Acuerdo mutuo 
 
5.4. Códigos Geográficos. 
5.4.1. Países (ISO 3166-1): Pais. 
ISO 3166-1 es la primera parte del estándar internacional de normalización ISO 3166, publicado por la 
Organización Internacional de Normalización (ISO), que proporciona códigos para los nombres de países 
y otras dependencias administrativas. La norma ISO 3166 se publicó por primera vez en 1974 por la 
Organización Internacional para la Normalización (ISO), y se amplió a tres partes en 1997, de las cuales 
esta primera parte se corresponde con la parte única anterior. 
La versión más reciente de la norma es ISO 3166 -1:2013, Códigos para la representación de nombres de 
países y sus subdivisiones – Parte 1: Códigos de los países. Esta norma define tres tipos de códigos de país: 
 ISO 3166-1 alfa-2: Códigos de país de das letras. Si recomienda como el código de propósito general. 
Estos códigos se utilizan por ejemplo en internet como dominios geográficos de nivel superior. 

---

## Página 132

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 132 de 269 
 
 ISO 3166-1 alfa-3: Códigos de país de tres letras. Está más estrechamente relacionado con el nombre 
del país, lo que permite una mejor identificación. 
 ISO 3166-1 numérico: Códigos de país de tres dígitos. Desarrollados y asignados por la División de  
Estadística de las Naciones Unidas. Pueden ser útiles cuando los códigos deban ser entendidos en los 
países que no utilizan el alfabeto latino. 
A un país o territorio generalmente se le asigna un nuevo código alfabético si su nombre cambia, mientras 
que se asocia un nuevo código numérico a un cambio de fronteras. Se reservan algunos códigos en cada 
área, por diversas razones. 
Actualmente 249 países, territorios o áreas de interés geográfico tienen asignados códigos oficiales en la 
norma ISO 3166 -1. La lis ta es mantenida por la Agencia de Mantenimiento ISO 3166 (ISO 3166/MA), a 
partir de las siguientes fuentes: 
 El boletín de terminologías de Nombres de País de las Naciones Unidas 
 Códigos de País y de Región para uso estadístico de la División de Estadística de las Naciones Unidas. 
De las fuentes anteriores se extrae el nombre oficial del país (como figura inscrito en la ONU) o la región, 
utilizado para formar los códigos ISO, y el código numérico de 3 cifras asignado por la División de 
Estadística de las Naciones Unidas. 
Siempre que un país o territorio aparezca en una de estas listas, se le asigna un código ISO por defecto, 
pero no todos los países están reconocidos por la ONU y por tanto no todos los países tienen un código 
ISO. Este es el caso de Kosovo, que no está reconocido por la ONU debido al veto de Rusia y no está 
presente en la norma. 
También puede ocurrir que una región, que no es un país independiente, figure en la lista con sus propios 
códigos, debido a que la División de Estadística de las Naci ones Unidas la procesa de manera 
independiente. Este es el caso de las Islas Ultramarinas Menores de Estados Unidos o las islas Åland de 
Finlandia. 
Adicionalmente, la ISO 3166/MA puede reservar códigos para otras entidades que no puedan clasificarse 
en bas e al criterio anterior. Por ejemplo, debido a que la Unión Europea no es un país, no está 
formalmente incluida en la norma ISO 3166 -1, pero por razones prácticas, la ISO 3166/MA ha reservado 
la combinación de dos letras EU (European Union) con el fin de identificar a la Unión Europea en el marco 
de la norma ISO 3166-1. 
La siguiente tabla, es una lista completa de los actuales códigos ISO 3166 -1 oficialmente asignados, con 
las siguientes columnas: 
 Nombre común: Nombre del país o territorio comúnmente usado. 
 Nombre ISO del país o territorio: Denominación del país o territorio según la norma ISO 3166-1. 
 Las denominaciones oficiales en la norma se han obtenido mediante la combinación de las 
denominaciones en inglés y francés, idiomas oficiales de la norma ISO. Algunos nombres solo figuran 
en su idioma local, porque esos países o territorios prefieren que su use el nombre únicamente en su 
idioma sin traducirlo. La grafía de los nombres en español se ha cogido de la lista de Estados 
Miembros de las Naciones Unidas, manteniendo el nombre utilizado en la norma ISO. 
 Código alfa-2: Código ISO de 2 letras de este país o territorio. 
 Código alfa-3: Código ISO de 3 letras de este país o territorio. 

---

## Página 133

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 133 de 269 
 
 Código numérico: Código ISO numérico de este país o territorio. 
 Observaciones: Información adicional relativa a los códigos de este país o territorio. 
Debe ser utilizado el Código alfa-2: Código ISO de 2 letras asignado a este país o territorio en los elementos 
Pais. 
Si @Idioma es “es”, debe ser utilizado el Nombre Común en los el ementos Name; si @Idioma es otro 
idioma, n estos elementos. 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Afganistán Afganistán AF AFG 004  
Åland Åland, Islas AX ALA 248 Es una provincia autónoma de 
Finlandia. 
Albania Albania AL ALB 008  
Alemania Alemania DE DEU 276 
Códigos obtenidos del idioma 
nativo (alemán): Deutschland 
 Códigos alfa usados por 
Alemania Occidental antes de la 
reunificación alemana en 1990. 
Andorra Andorra AD AND 020  
Angola Angola AO AGO 024  
Anguila Anguila AI AIA 660  
Antártida Antártida AQ ATA 010 
Cubre el territorio al sur del 
paralelo 60º sur.  
 Códigos obtenidos del 
nombre en francés: Antarctique 
Antigua y Barbuda Antigua y Barbuda AG ATG 028  
Arabia Saudita Arabia Saudita SA SAU 682  
Argelia Argelia DZ DZA 012 Códigos obtenidos del idioma 
nativo (cabilio): Dzayer 
Argentina Argentina AR ARG 032  
Armenia Armenia AM ARM 051  
Aruba Aruba AW ABW 533 Forma parte del Reino de los Países 
Bajos. 
Australia Australia AU AUS 036 Incluye las Islas Ashmore y Cartier y 
las Islas del Mar del Coral. 
Austria Austria AT AUT 040  
Azerbaiyán Azerbaiyán AZ AZE 031  
Bahamas Bahamas (las) BS BHS 044  
Bangladés Bangladesh BD BGD 050  

---

## Página 134

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 134 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Barbados Barbados BB BRB 052  
Baréin Bahrein BH BHR 048  
Bélgica Bélgica BE BEL 056  
Belice Belice BZ BLZ 084  
Benín Benin BJ BEN 204  
Bermudas Bermudas BM BMU 060  
Bielorrusia Belarús BY BLR 112 
El nombre oficial del país es 
Belarús, aunque tradicionalmente 
se le sigue denominando 
Bielorrusia. 
Bolivia Bolivia (Estado 
Plurinacional de) BO BOL 068  
Bonaire, San 
Eustaquio y 
Saba 
Bonaire, San 
Eustaquio y Saba BQ BES 535 Son tres municipios especiales que 
forman parte de los Países Bajos. 
Bosnia y Herzegovina Bosnia y 
Herzegovina BA BIH 070  
Botsuana Botswana BW BWA 072  
Brasil Brasil BR BRA 076  
Brunéi Brunei Darussalam BN BRN 096  
Bulgaria Bulgaria BG BGR 100  
Burkina Faso Burkina Faso BF BFA 854  
Burundi Burundi BI BDI 108  
Bután Bhután BT BTN 064  
Cabo Verde Cabo Verde CV CPV 132  
Camboya Camboya KH KHM 116 
Códigos obtenidos del anterior 
nombre: Khmer Republic 
(República Jemer) 
Camerún Camerún CM CMR 120  
Canadá Canadá CA CAN 124  
Catar Qatar QA QAT 634  
Chad Chad TD TCD 148 Códigos obtenidos del nombre en 
francés: Tchad 
Chile Chile CL CHL 152  
China China CN CHN 156  
Chipre Chipre CY CYP 196  
Colombia Colombia CO COL 170  

---

## Página 135

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 135 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Comoras Comoras (las) KM CON 174 Códigos obtenidos del idioma 
nativo (comorense): Komori 
Corea del Norte 
Corea (la República 
Popular 
Democrática de) 
KP PRK 408  
Corea del Sur Corea (la República 
de) KR KOR 410  
Costa de Marfil Côte d’Ivoire CI CIV 384 Nombre oficial en la ISO en francés. 
Costa Rica Costa Rica CR CRI 188 Nombre oficial en la ISO en español. 
Croacia Croacia HR HRV 191 Códigos obtenidos del idioma 
nativo (croata): Hrvatska 
Cuba Cuba CU CUB 192  
Curazao Curaçao CW CUW 531 Forma parte del Reino de los Países 
Bajos. 
Dinamarca Dinamarca DK DNK 208  
Dominica Dominica DM DMA 212  
Ecuador Ecuador EC ECU 218  
Egipto Egipto EG EGY 818  
El Salvador El Salvador SV SLV 222 Nombre oficial en la ISO en español. 
Emiratos Árabes 
Unidos 
Emiratos Árabes 
Unidos (los) AE ARE 784  
Eritrea Eritrea ER ERI 232  
Eslovaquia Eslovaquia SK SVK 703  
Eslovenia Eslovenia SI SVN 705  
España España ES ESP 724 Códigos obtenidos del idioma 
nativo (español): España 
Estados Unidos Estados Unidos de 
América (los) US USA 840  
Estonia Estonia EE EST 233 Códigos obtenidos del idioma 
nativo (estonio): Eesti 
Etiopía Etiopía ET ETH 231  
Filipinas Filipinas (las) PH PHL 608  
Finlandia Finlandia FI FIN 246  
Fiyi Fiji FJ FJI 242  
Francia Francia FR FRA 250 Incluye la Isla Clipperton. 
Gabón Gabón GA GAB 266  
Gambia Gambia (la) GM GMB 270  

---

## Página 136

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 136 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Georgia Georgia GE GEO 268  
Ghana Ghana GH GHA 288  
Gibraltar Gibraltar GI GIB 292 Pertenece al Reino Unido. 
Granada Granada GD GRD 308  
Grecia Grecia GR GRC 300  
Groenlandia Groenlandia GL GRL 304 Pertenece al Reino de Dinamarca. 
Guadalupe Guadeloupe GP GLP 312 Departamento de ultramar francés. 
Nombre oficial en la ISO en francés. 
Guam Guam GU GUM 316 Territorio no incorporado de los 
Estados Unidos. 
Guatemala Guatemala GT GTM 320  
Guayana Francesa Guayana Francesa GF GUF 254 
Departamento de ultramar francés. 
 Códigos obtenidos del 
nombre en francés: Guyane 
française 
Guernsey Guernsey GG GGY 831 Una dependencia de la Corona 
británica. 
Guinea Guinea GN GIN 324  
Guinea-Bisáu Guinea Bissau GW GNB 624  
Guinea Ecuatorial Guinea Ecuatorial GQ GNQ 226 Códigos obtenidos del nombre en 
francés: Guinée équatoriale 
Guyana Guyana GY GUY 328  
Haití Haití HT HTI 332  
Honduras Honduras HN HND 340  
Hong Kong Hong Kong HK HKG 344 Región administrativa especial de 
China. 
Hungría Hungría HU HUN 348  
India India IN IND 356  
Indonesia Indonesia ID IDN 360  
Irak Iraq IQ IRQ 368  
Irán Irán (República 
Islámica de) IR IRN 364  
Irlanda Irlanda IE IRL 372  
Isla Bouvet Bouvet, Isla BV BVT 074 Pertenece a Noruega. 
Isla de Man Isla de Man IM IMN 833 Una dependencia de la Corona 
británica. 
Isla de Navidad Navidad, Isla de CX CXR 162 Pertenece a Australia. 

---

## Página 137

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 137 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Islandia Islandia IS ISL 352 Códigos obtenidos del idioma 
nativo (islandés): Ísland 
Islas Caimán Caimán, (las) Islas KY CYM 136  
Islas Cocos Cocos / Keeling, 
(las) Islas CC CCK 166 Pertenecen a Australia. 
Islas Cook Cook, (las) Islas CK COK 184  
Islas Feroe Feroe, (las) Islas FO FRO 234 Pertenecen al Reino de Dinamarca. 
Islas Georgias del Sur 
y Sandwich del 
Sur 
Georgia del Sur (la) 
y las Islas Sandwich 
del Sur 
GS SGS 239  
Islas Heard y 
McDonald 
Heard (Isla) e Islas 
McDonald HM HMD 334 Pertenecen a Australia. 
Islas Malvinas 
Malvinas 
[Falkland], (las) 
Islas 
FK FLK 238 Códigos obtenidos del nombre en 
(inglés): Falkland 
Islas Marianas del 
Norte 
Marianas del 
Norte, (las) Islas MP MNP 580 Territorio no incorporado de los 
Estados Unidos. 
Islas Marshall Marshall, (las) Islas MH MHL 584  
Islas Pitcairn Pitcairn PN PCN 612  
Islas Salomón Salomón, Islas SB SLB 090 Códigos obtenidos de su anterior 
nombre: British Solomon Islands 
Islas Turcas y Caicos Turcas y Caicos, 
(las) Islas TC TCA 796  
Islas ultramarinas de 
Estados Unidos 
Islas Ultramarinas 
Menores de los 
Estados Unidos 
(las) 
UM UMI 581 
Comprende nueve áreas insulares 
menores de los Estados Unidos: 
Arrecife Kingman, Atolón Johnston, 
Atolón Palmyra, Isla Baker, Isla 
Howland, Isla Jarvis, Islas Midway, 
Isla de Navaza e Isla Wake. 
Islas Vírgenes 
Británicas 
Vírgenes británicas, 
Islas VG VGB 092  
Islas Vírgenes de los 
Estados Unidos 
Vírgenes de los 
Estados Unidos, 
Islas 
VI VIR 850 Territorio no incorporado de los 
Estados Unidos. 
Israel Israel IL ISR 376  
Italia Italia IT ITA 380  
Jamaica Jamaica JM JAM 388  

---

## Página 138

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 138 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Japón Japón JP JPN 392  
Jersey Jersey JE JEY 832 Una dependencia de la Corona 
británica. 
Jordania Jordania JO JOR 400  
Kazajistán Kazajstán KZ KAZ 398  
Kenia Kenya KE KEN 404  
Kirguistán Kirguistán KG KGZ 417  
Kiribati Kiribati KI KIR 296  
Kuwait Kuwait KW KWT 414  
Laos 
Lao, (la) República 
Democrática 
Popular 
LA LAO 418  
Lesoto Lesotho LS LSO 426  
Letonia Letonia LV LVA 428  
Líbano Líbano LB LBN 422  
Liberia Liberia LR LBR 430  
Libia Libia LY LBY 434  
Liechtenstein Liechtenstein LI LIE 438  
Lituania Lituania LT LTU 440  
Luxemburgo Luxemburgo LU LUX 442  
Macao Macao MO MAC 446 Región administrativa especial de 
China. 
Macedonia 
Macedonia (la ex 
República 
Yugoslava de) 
MK MKD 807 Códigos obtenidos del idioma 
nativo (macedonio): Makedonija 
Madagascar Madagascar MG MDG 450  
Malasia Malasia MY MYS 458  
Malaui Malawi MW MWI 454  
Maldivas Maldivas MV MDV 462  
Malí Malí ML MLI 466  
Malta Malta MT MLT 470  
Marruecos Marruecos MA MAR 504 Códigos obtenidos del nombre en 
francés: Maroc 
Martinica Martinique MQ MTQ 474 Departamento de ultramar francés. 
Nombre oficial en la ISO en francés. 
Mauricio Mauricio MU MUS 480  
Mauritania Mauritania MR MRT 478  

---

## Página 139

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 139 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Mayotte Mayotte YT MYT 175 Departamento de ultramar francés. 
México México MX MEX 484  
Micronesia 
Micronesia 
(Estados Federados 
de) 
FM FSM 583  
Moldavia Moldova (la 
República de) MD MDA 498  
Mónaco Mónaco MC MCO 492  
Mongolia Mongolia MN MNG 496  
Montenegro Montenegro ME MNE 499  
Montserrat Montserrat MS MSR 500  
Mozambique Mozambique MZ MOZ 508  
Myanmar Myanmar MM MMR 104 Anteriormente conocida como 
Birmania. 
Namibia Namibia NA NAM 516  
Nauru Nauru NR NRU 520  
Nepal Nepal NP NPL 524  
Nicaragua Nicaragua NI NIC 558  
Níger Níger (el) NE NER 562  
Nigeria Nigeria NG NGA 566  
Niue Niue UN NIU 570 Asociado a Nueva Zelanda. 
Norfolk Norfolk, Isla NF NFK 574 Pertenece a Australia. 
Noruega Noruega NO NOR 578  
Nueva Caledonia Nueva Caledonia NC NCL 540  
Nueva Zelanda Nueva Zelandia NZ NZL 554  
Omán Omán OM OMN 512  
Países Bajos Países Bajos (los) NL NLD 528 Forma parte del Reino de los Países 
Bajos. 
Pakistán Pakistán PK PAK 586  
Palaos Palau PW PLW 585  
Palestina Palestina, Estado 
de PS PSE 275 Comprende los territorios de 
Cisjordania y Franja de Gaza. 
Panamá Panamá PA PAN 591  
Papúa Nueva Guinea Papua Nueva 
Guinea PG PNG 598  
Paraguay Paraguay PY PRY 600  
Perú Perú PE PER 604  

---

## Página 140

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 140 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Polinesia Francesa Polinesia Francesa PF PYF 258 Códigos obtenidos del nombre en 
francés: Polynésie française 
Polonia Polonia PL POL 616  
Portugal Portugal PT PRT 620  
Puerto Rico Puerto Rico PR PRI 630 
Territorio no incorporado de los 
Estados Unidos. Nombre oficial en 
la ISO en español. 
Reino Unido 
Reino Unido de 
Gran Bretaña e 
Irlanda del Norte 
(el) 
GB GBR 826 
Debido a que para obtener los 
códigos ISO no se utilizan las 
palabras comunes de Reino y 
Unido, los códigos se han obtenido 
a partir del resto del nombre 
oficial. 
República Árabe 
Saharaui 
Democrática 
Sahara Occidental EH ESH 732 
Nombre provisional. Anterior 
nombre en la ISO: Sahara español 
 Códigos obtenidos del 
anterior nombre en español 
República 
Centroafricana 
República 
Centroafricana (la) CF CAF 140  
República Checa Chequia CZ CZE 203  
República del Congo Congo (el) CG COG 178  
República 
Democrática 
del Congo 
Congo (la República 
Democrática del) CD COD 180  
República 
Dominicana 
Dominicana, (la) 
República DO DOM 214  
Reunión Reunión RE REU 638 Departamento de ultramar francés. 
Ruanda Rwanda RW RWA 646  
Rumania Rumania RO ROU 642  
Rusia Rusia, (la) 
Federación de RU RUS 643  
Samoa Samoa WS WSM 882 
Códigos obtenidos del anterior 
nombre: Western Samoa (Samoa 
Occidental) 
Samoa Americana Samoa Americana AS ASM 016 Territorio no incorporado de los 
Estados Unidos. 

---

## Página 141

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 141 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
San Bartolomé Saint Barthélemy BL BLM 652 Colectividad de ultramar francesa. 
Nombre oficial en la ISO en francés. 
San Cristóbal y 
Nieves Saint Kitts y Nevis KN KNA 659  
San Marino San Marino SM SMR 674  
San Martín Saint Martin (parte 
francesa) MF MAF 663 Colectividad de ultramar francesa. 
Nombre oficial en la ISO en francés. 
San Pedro y 
Miquelón 
San Pedro y 
Miquelón PM SPM 666 Colectividad de ultramar francesa. 
San Vicente y las 
Granadinas 
San Vicente y las 
Granadinas VC VCT 670  
Santa Elena, 
Ascensión y Tristán 
de Acuña 
Santa Helena, 
Ascensión y Tristán 
de Acuña 
SH SHN 654  
Santa Lucía Santa Lucía LC LCA 662  
Santo Tomé y 
Príncipe 
Santo Tomé y 
Príncipe ST STP 678  
Senegal Senegal SN SEN 686  
Serbia Serbia RS SRB 688 
Códigos obtenidos de su nombre 
oficial: República de Serbia, en 
inglés. 
Seychelles Seychelles SC SYC 690  
Sierra Leona Sierra leona SL SLE 694  
Singapur Singapur SG SGP 702  
Sint Maarten Sint Maarten (parte 
neerlandesa) SX SXM 534 
Forma parte del Reino de los Países 
Bajos. 
 Nombre oficial en 
neerlandés. 
Siria República Árabe 
Siria SY SYR 760  
Somalia Somalia SO SOM 706  
Sri Lanka Sri Lanka LK LKA 144  
Suazilandia Swazilandia SZ SWZ 748  
Sudáfrica Sudáfrica ZA ZAF 710 Códigos obtenidos del nombre en 
neerlandés: Zuid-Afrika 
Sudán Sudán (el) SD SDN 729  
Sudán del Sur Sudán del Sur SS SSD 728  

---

## Página 142

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 142 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Suecia Suecia SE SWE 752  
Suiza Suiza CH CHE 756 Códigos obtenidos del nombre en 
latín: Confoederatio Helvetica 
Surinam Suriname SR SUR 740  
Svalbard y Jan 
Mayen 
Svalbard y Jan 
Mayen SJ SJM 744 Comprende dos territorios árticos 
de Noruega: Svalbard y Jan Mayen. 
Tailandia Tailandia TH THA 764  
Taiwán (República de 
China) 
Taiwán (Provincia 
de China) TW TWN 158 
Cubre la jurisdicción actual de la 
República de China (Taiwán), 
excepto Kinmen e Islas Matsu. 
 La ONU considera a Taiwán 
como una provincia de China, 
debido a su estatus político 
Tanzania Tanzania, República 
Unida de TZ TZA 834  
Tayikistán Tayikistán TJ TJK 762  
Territorio Británico 
del Océano Índico 
Territorio Británico 
del Océano Índico 
(el) 
IO IOT 086  
Tierras Australes y 
Antárticas Francesas 
Tierras Australes 
Francesas (las) TF ATF 260 
Comprende las tierras australes y 
antárticas francesas excepto la 
parte incluida en la Antártida 
conocida como Tierra Adelia. 
 Códigos obtenidos del 
nombre en francés: Terres 
australes françaises. 
Timor Oriental Timor-Leste TL TLS 626 Nombre oficial en la ISO en 
portugués. 
Togo Togo TG TGO 768  
Tokelau Tokelau TK TKL 772  
Tonga Tonga TO TON 776  
Trinidad y Tobago Trinidad y Tobago TT TTO 780  
Túnez Túnez TN TUN 788  
Turkmenistán Turkmenistán TM TKM 795  
Turquía Turquía TR TUR 792  
Tuvalu Tuvalu TV TUV 798  
Ucrania Ucrania UA UKR 804  

---

## Página 143

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 143 de 269 
 
Nombre común Nombre ISO oficial 
del país o territorio 
Código 
alfa-2 
Código 
alfa-3 
Código 
numérico Observaciones 
Uganda Uganda UG UGA 800  
Uruguay Uruguay UY URY 858  
Uzbekistán Uzbekistán UZ UZB 860  
Vanuatu Vanuatu VU VUT 548  
Vaticano, Ciudad del Santa Sede (la) VA VAT 336 
La Santa Sede es la representante 
diplomática del Estado de la Ciudad 
del Vaticanoante la ONU y otros 
países y organismos 
internacionales, aunque 
jurídicamente se trata de entes 
distintos. Los códigos ISO se 
asignan a la Santa Sede como 
representante de este Estado, pero 
se refieren al territorio del Estado 
de la Ciudad del Vaticano. 
Venezuela 
Venezuela 
(República 
Bolivariana de) 
VE VEN 862  
Vietnam Viet Nam VN VNM 704  
Wallis y Futuna Wallis y Futuna WF WLF 876 Colectividad de ultramar francesa. 
Yemen Yemen YE YEM 887  
Yibuti Djibouti DJ DJI 262  
Zambia Zambia ZM ZMB 894  
Zimbabue Zimbabwe ZW ZWE 716  
 
 
5.4.2. Departamentos (ISO 3166-2:CO): Departamento. 
ISO 3166-2:CO es la serie de códigos ISO 3166-2 correspondientes a Colombia.  En ella se incluyen las 33 
subdivisiones administrativas del país. Fue publicada en 1998 y actualizada por última vez en el sexto 
boletín de la primera edición en 2004. 
 
Código Nombre Código ISO Código Nombre Código ISO 
91 Amazonas AMA 41 Huila HUI 
05 Antioquia ANT 44 La Guajira LAG 
81 Arauca ARA 47 Magdalena MAG 
08 Atlántico ATL 50 Meta MET 
11 Bogotá DC 52 Nariño NAR 

---

## Página 144

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 144 de 269 
 
13 Bolívar BOL 54 Norte de Santander NSA 
15 Boyacá BOY 86 Putumayo PUT 
17 Caldas CAL 63 Quindío QUI 
18 Caquetá CAQ 66 Risaralda RIS 
85 Casanare CAS 88 San Andrés y Providencia SAP 
19 Cauca CAU 68 Santander SAN 
20 Cesar CES 70 Sucre SUC 
27 Chocó CHO 73 Tolima TOL 
23 Córdoba COR 76 Valle del Cauca VAC 
25 Cundinamarca CUN 97 Vaupés VAU 
94 Guainía GUA 99 Vichada VID 
95 Guaviare GUV    
 
5.4.3. Municipios: Municipio. 
Fuente: Departamento Administrativo Nacional de Estadística (DANE), entidad responsable de la 
planeación, levantamiento, procesamiento, análisis y difusión de las estadísticas oficiales de Colombia. 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
91 91001 Amazonas LETICIA 
91 91263 Amazonas EL ENCANTO 
91 91405 Amazonas LA CHORRERA 
91 91407 Amazonas LA PEDRERA 
91 91430 Amazonas LA VICTORIA 
91 91460 Amazonas MIRITÍ – PARANÁ 
91 91530 Amazonas PUERTO ALEGRÍA 
91 91536 Amazonas PUERTO ARICA 
91 91540 Amazonas PUERTO NARIÑO 
91 91669 Amazonas PUERTO SANTANDER 
91 91798 Amazonas TARAPACÁ 
05 05001 Antioquia MEDELLÍN 
05 05002 Antioquia ABEJORRAL 
05 05004 Antioquia ABRIAQUÍ 
05 05021 Antioquia ALEJANDRÍA 
05 05030 Antioquia AMAGÁ 
05 05031 Antioquia AMALFI 
05 05034 Antioquia ANDES 

---

## Página 145

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 145 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
05 05036 Antioquia ANGELÓPOLIS 
05 05038 Antioquia ANGOSTURA 
05 05040 Antioquia ANORÍ 
05 05042 Antioquia SANTA FÉ DE ANTIOQUIA 
05 05044 Antioquia ANZÁ 
05 05045 Antioquia APARTADÓ 
05 05051 Antioquia ARBOLETES 
05 05055 Antioquia ARGELIA 
05 05059 Antioquia ARMENIA 
05 05079 Antioquia BARBOSA 
05 05086 Antioquia BELMIRA 
05 05088 Antioquia BELLO 
05 05091 Antioquia BETANIA 
05 05093 Antioquia BETULIA 
05 05101 Antioquia CIUDAD BOLÍVAR 
05 05107 Antioquia BRICEÑO 
05 05113 Antioquia BURITICÁ 
05 05120 Antioquia CÁCERES 
05 05125 Antioquia CAICEDO 
05 05129 Antioquia CALDAS 
05 05134 Antioquia CAMPAMENTO 
05 05138 Antioquia CAÑASGORDAS 
05 05142 Antioquia CARACOLÍ 
05 05145 Antioquia CARAMANTA 
05 05147 Antioquia CAREPA 
05 05148 Antioquia EL CARMEN DE VIBORAL 
05 05150 Antioquia CAROLINA 
05 05154 Antioquia CAUCASIA 
05 05172 Antioquia CHIGORODÓ 
05 05190 Antioquia CISNEROS 
05 05197 Antioquia COCORNÁ 
05 05206 Antioquia CONCEPCIÓN 
05 05209 Antioquia CONCORDIA 

---

## Página 146

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 146 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
05 05212 Antioquia COPACABANA 
05 05234 Antioquia DABEIBA 
05 05237 Antioquia DONMATÍAS 
05 05240 Antioquia EBÉJICO 
05 05250 Antioquia EL BAGRE 
05 05264 Antioquia ENTRERRÍOS 
05 05266 Antioquia ENVIGADO 
05 05282 Antioquia FREDONIA 
05 05284 Antioquia FRONTINO 
05 05306 Antioquia GIRALDO 
05 05308 Antioquia GIRARDOTA 
05 05310 Antioquia GÓMEZ PLATA 
05 05313 Antioquia GRANADA 
05 05315 Antioquia GUADALUPE 
05 05318 Antioquia GUARNE 
05 05321 Antioquia GUATAPÉ 
05 05347 Antioquia HELICONIA 
05 05353 Antioquia HISPANIA 
05 05360 Antioquia ITAGÜÍ 
05 05361 Antioquia ITUANGO 
05 05364 Antioquia JARDÍN 
05 05368 Antioquia JERICÓ 
05 05376 Antioquia LA CEJA 
05 05380 Antioquia LA ESTRELLA 
05 05390 Antioquia LA PINTADA 
05 05400 Antioquia LA UNIÓN 
05 05411 Antioquia LIBORINA 
05 05425 Antioquia MACEO 
05 05440 Antioquia MARINILLA 
05 05467 Antioquia MONTEBELLO 
05 05475 Antioquia MURINDÓ 
05 05480 Antioquia MUTATÁ 
05 05483 Antioquia NARIÑO 

---

## Página 147

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 147 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
05 05490 Antioquia NECOCLÍ 
05 05495 Antioquia NECHÍ 
05 05501 Antioquia OLAYA 
05 05541 Antioquia PEÑOL 
05 05543 Antioquia PEQUE 
05 05576 Antioquia PUEBLORRICO 
05 05579 Antioquia PUERTO BERRÍO 
05 05585 Antioquia PUERTO NARE 
05 05591 Antioquia PUERTO TRIUNFO 
05 05604 Antioquia REMEDIOS 
05 05607 Antioquia RETIRO 
05 05615 Antioquia RIONEGRO 
05 05628 Antioquia SABANALARGA 
05 05631 Antioquia SABANETA 
05 05642 Antioquia SALGAR 
05 05647 Antioquia SAN ANDRÉS DE CUERQUÍA 
05 05649 Antioquia SAN CARLOS 
05 05652 Antioquia SAN FRANCISCO 
05 05656 Antioquia SAN JERÓNIMO 
05 05658 Antioquia SAN JOSÉ DE LA MONTAÑA 
05 05659 Antioquia SAN JUAN DE URABÁ 
05 05660 Antioquia SAN LUIS 
05 05664 Antioquia SAN PEDRO DE LOS MILAGROS 
05 05665 Antioquia SAN PEDRO DE URABÁ 
05 05667 Antioquia SAN RAFAEL 
05 05670 Antioquia SAN ROQUE 
05 05674 Antioquia SAN VICENTE FERRER 
05 05679 Antioquia SANTA BÁRBARA 
05 05686 Antioquia SANTA ROSA DE OSOS 
05 05690 Antioquia SANTO DOMINGO 
05 05697 Antioquia EL SANTUARIO 
05 05736 Antioquia SEGOVIA 
05 05756 Antioquia SONSÓN 

---

## Página 148

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 148 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
05 05761 Antioquia SOPETRÁN 
05 05789 Antioquia TÁMESIS 
05 05790 Antioquia TARAZÁ 
05 05792 Antioquia TARSO 
05 05809 Antioquia TITIRIBÍ 
05 05819 Antioquia TOLEDO 
05 05837 Antioquia TURBO 
05 05842 Antioquia URAMITA 
05 05847 Antioquia URRAO 
05 05854 Antioquia VALDIVIA 
05 05856 Antioquia VALPARAÍSO 
05 05858 Antioquia VEGACHÍ 
05 05861 Antioquia VENECIA 
05 05873 Antioquia VIGÍA DEL FUERTE 
05 05885 Antioquia YALÍ 
05 05887 Antioquia YARUMAL 
05 05890 Antioquia YOLOMBÓ 
05 05893 Antioquia YONDÓ 
05 05895 Antioquia ZARAGOZA 
05 05861 Antioquía VENECIA 
81 81001 Arauca ARAUCA 
81 81065 Arauca ARAUQUITA 
81 81220 Arauca CRAVO NORTE 
81 81300 Arauca FORTUL 
81 81591 Arauca PUERTO RONDÓN 
81 81736 Arauca SARAVENA 
81 81794 Arauca TAME 
88 88001 
Archipiélago de San 
Andrés, Providencia y Santa 
Catalina 
SAN ANDRÉS 
88 88564 
Archipiélago de San 
Andrés, Providencia y Santa 
Catalina 
PROVIDENCIA 

---

## Página 149

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 149 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
08 08001 Atlántico BARRANQUILLA 
08 08078 Atlántico BARANOA 
08 08137 Atlántico CAMPO DE LA CRUZ 
08 08141 Atlántico CANDELARIA 
08 08296 Atlántico GALAPA 
08 08372 Atlántico JUAN DE ACOSTA 
08 08421 Atlántico LURUACO 
08 08433 Atlántico MALAMBO 
08 08436 Atlántico MANATÍ 
08 08520 Atlántico PALMAR DE VARELA 
08 08549 Atlántico PIOJÓ 
08 08558 Atlántico POLONUEVO 
08 08560 Atlántico PONEDERA 
08 08573 Atlántico PUERTO COLOMBIA 
08 08606 Atlántico REPELÓN 
08 08634 Atlántico SABANAGRANDE 
08 08638 Atlántico SABANALARGA 
08 08675 Atlántico SANTA LUCÍA 
08 08685 Atlántico SANTO TOMÁS 
08 08758 Atlántico SOLEDAD 
08 08770 Atlántico SUAN 
08 08832 Atlántico TUBARÁ 
08 08849 Atlántico USIACURÍ 
11 11001 Bogotá, D.C. BOGOTÁ, D.C. 
13 13001 Bolívar CARTAGENA DE INDIAS 
13 13006 Bolívar ACHÍ 
13 13030 Bolívar ALTOS DEL ROSARIO 
13 13042 Bolívar ARENAL 
13 13052 Bolívar ARJONA 
13 13062 Bolívar ARROYOHONDO 
13 13074 Bolívar BARRANCO DE LOBA 
13 13140 Bolívar CALAMAR 
13 13160 Bolívar CANTAGALLO 

---

## Página 150

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 150 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
13 13188 Bolívar CICUCO 
13 13212 Bolívar CÓRDOBA 
13 13222 Bolívar CLEMENCIA 
13 13244 Bolívar EL CARMEN DE BOLÍVAR 
13 13248 Bolívar EL GUAMO 
13 13268 Bolívar EL PEÑÓN 
13 13300 Bolívar HATILLO DE LOBA 
13 13430 Bolívar MAGANGUÉ 
13 13433 Bolívar MAHATES 
13 13440 Bolívar MARGARITA 
13 13442 Bolívar MARÍA LA BAJA 
13 13458 Bolívar MONTECRISTO 
13 13468 Bolívar MOMPÓS 
13 13473 Bolívar MORALES 
13 13490 Bolívar NOROSÍ 
13 13549 Bolívar PINILLOS 
13 13580 Bolívar REGIDOR 
13 13600 Bolívar RÍO VIEJO 
13 13620 Bolívar SAN CRISTÓBAL 
13 13647 Bolívar SAN ESTANISLAO 
13 13650 Bolívar SAN FERNANDO 
13 13654 Bolívar SAN JACINTO 
13 13655 Bolívar SAN JACINTO DEL CAUCA 
13 13657 Bolívar SAN JUAN NEPOMUCENO 
13 13667 Bolívar SAN MARTÍN DE LOBA 
13 13670 Bolívar SAN PABLO SUR 
13 13673 Bolívar SANTA CATALINA 
13 13683 Bolívar SANTA ROSA DE LIMA 
13 13688 Bolívar SANTA ROSA DEL SUR 
13 13744 Bolívar SIMITÍ 
13 13760 Bolívar SOPLAVIENTO 
13 13780 Bolívar TALAIGUA NUEVO 
13 13810 Bolívar TIQUISIO 

---

## Página 151

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 151 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
13 13836 Bolívar TURBACO 
13 13838 Bolívar TURBANÁ 
13 13873 Bolívar VILLANUEVA 
13 13894 Bolívar ZAMBRANO 
15 15001 Boyacá TUNJA 
15 15022 Boyacá ALMEIDA 
15 15047 Boyacá AQUITANIA 
15 15051 Boyacá ARCABUCO 
15 15087 Boyacá BELÉN 
15 15090 Boyacá BERBEO 
15 15092 Boyacá BETÉITIVA 
15 15097 Boyacá BOAVITA 
15 15104 Boyacá BOYACÁ 
15 15106 Boyacá BRICEÑO 
15 15109 Boyacá BUENAVISTA 
15 15114 Boyacá BUSBANZÁ 
15 15131 Boyacá CALDAS 
15 15135 Boyacá CAMPOHERMOSO 
15 15162 Boyacá CERINZA 
15 15172 Boyacá CHINAVITA 
15 15176 Boyacá CHIQUINQUIRÁ 
15 15180 Boyacá CHISCAS 
15 15183 Boyacá CHITA 
15 15185 Boyacá CHITARAQUE 
15 15187 Boyacá CHIVATÁ 
15 15189 Boyacá CIÉNEGA 
15 15204 Boyacá CÓMBITA 
15 15212 Boyacá COPER 
15 15215 Boyacá CORRALES 
15 15218 Boyacá COVARACHÍA 
15 15223 Boyacá CUBARÁ 
15 15224 Boyacá CUCAITA 
15 15226 Boyacá CUÍTIVA 

---

## Página 152

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 152 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
15 15232 Boyacá CHÍQUIZA 
15 15236 Boyacá CHIVOR 
15 15238 Boyacá DUITAMA 
15 15244 Boyacá EL COCUY 
15 15248 Boyacá EL ESPINO 
15 15272 Boyacá FIRAVITOBA 
15 15276 Boyacá FLORESTA 
15 15293 Boyacá GACHANTIVÁ 
15 15296 Boyacá GÁMEZA 
15 15299 Boyacá GARAGOA 
15 15317 Boyacá GUACAMAYAS 
15 15322 Boyacá GUATEQUE 
15 15325 Boyacá GUAYATÁ 
15 15332 Boyacá GÜICÁN DE LA SIERRA 
15 15362 Boyacá IZA 
15 15367 Boyacá JENESANO 
15 15368 Boyacá JERICÓ 
15 15377 Boyacá LABRANZAGRANDE 
15 15380 Boyacá LA CAPILLA 
15 15401 Boyacá LA VICTORIA 
15 15403 Boyacá LA UVITA 
15 15407 Boyacá VILLA DE LEYVA 
15 15425 Boyacá MACANAL 
15 15442 Boyacá MARIPÍ 
15 15455 Boyacá MIRAFLORES 
15 15464 Boyacá MONGUA 
15 15466 Boyacá MONGUÍ 
15 15469 Boyacá MONIQUIRÁ 
15 15476 Boyacá MOTAVITA 
15 15480 Boyacá MUZO 
15 15491 Boyacá NOBSA 
15 15494 Boyacá NUEVO COLÓN 
15 15500 Boyacá OICATÁ 

---

## Página 153

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 153 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
15 15507 Boyacá OTANCHE 
15 15511 Boyacá PACHAVITA 
15 15514 Boyacá PÁEZ 
15 15516 Boyacá PAIPA 
15 15518 Boyacá PAJARITO 
15 15522 Boyacá PANQUEBA 
15 15531 Boyacá PAUNA 
15 15533 Boyacá PAYA 
15 15537 Boyacá PAZ DE RÍO 
15 15542 Boyacá PESCA 
15 15550 Boyacá PISBA 
15 15572 Boyacá PUERTO BOYACÁ 
15 15580 Boyacá QUÍPAMA 
15 15599 Boyacá RAMIRIQUÍ 
15 15600 Boyacá RÁQUIRA 
15 15621 Boyacá RONDÓN 
15 15632 Boyacá SABOYÁ 
15 15638 Boyacá SÁCHICA 
15 15646 Boyacá SAMACÁ 
15 15660 Boyacá SAN EDUARDO 
15 15664 Boyacá SAN JOSÉ DE PARE 
15 15667 Boyacá SAN LUIS DE GACENO 
15 15673 Boyacá SAN MATEO 
15 15676 Boyacá SAN MIGUEL DE SEMA 
15 15681 Boyacá SAN PABLO DE BORBUR 
15 15686 Boyacá SANTANA 
15 15690 Boyacá SANTA MARÍA 
15 15693 Boyacá SANTA ROSA DE VITERBO 
15 15696 Boyacá SANTA SOFÍA 
15 15720 Boyacá SATIVANORTE 
15 15723 Boyacá SATIVASUR 
15 15740 Boyacá SIACHOQUE 
15 15753 Boyacá SOATÁ 

---

## Página 154

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 154 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
15 15755 Boyacá SOCOTÁ 
15 15757 Boyacá SOCHA 
15 15759 Boyacá SOGAMOSO 
15 15761 Boyacá SOMONDOCO 
15 15762 Boyacá SORA 
15 15763 Boyacá SOTAQUIRÁ 
15 15764 Boyacá SORACÁ 
15 15774 Boyacá SUSACÓN 
15 15776 Boyacá SUTAMARCHÁN 
15 15778 Boyacá SUTATENZA 
15 15790 Boyacá TASCO 
15 15798 Boyacá TENZA 
15 15804 Boyacá TIBANÁ 
15 15806 Boyacá TIBASOSA 
15 15808 Boyacá TINJACÁ 
15 15810 Boyacá TIPACOQUE 
15 15814 Boyacá TOCA 
15 15816 Boyacá TOGÜÍ 
15 15820 Boyacá TÓPAGA 
15 15822 Boyacá TOTA 
15 15832 Boyacá TUNUNGUÁ 
15 15835 Boyacá TURMEQUÉ 
15 15837 Boyacá TUTA 
15 15839 Boyacá TUTAZÁ 
15 15842 Boyacá ÚMBITA 
15 15861 Boyacá VENTAQUEMADA 
15 15879 Boyacá VIRACACHÁ 
15 15897 Boyacá ZETAQUIRA 
17 17001 Caldas MANIZALES 
17 17013 Caldas AGUADAS 
17 17042 Caldas ANSERMA 
17 17050 Caldas ARANZAZU 
17 17088 Caldas BELALCÁZAR 

---

## Página 155

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 155 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
17 17174 Caldas CHINCHINÁ 
17 17272 Caldas FILADELFIA 
17 17380 Caldas LA DORADA 
17 17388 Caldas LA MERCED 
17 17433 Caldas MANZANARES 
17 17442 Caldas MARMATO 
17 17444 Caldas MARQUETALIA 
17 17446 Caldas MARULANDA 
17 17486 Caldas NEIRA 
17 17495 Caldas NORCASIA 
17 17513 Caldas PÁCORA 
17 17524 Caldas PALESTINA 
17 17541 Caldas PENSILVANIA 
17 17614 Caldas RIOSUCIO 
17 17616 Caldas RISARALDA 
17 17653 Caldas SALAMINA 
17 17662 Caldas SAMANÁ 
17 17665 Caldas SAN JOSÉ 
17 17777 Caldas SUPÍA 
17 17867 Caldas VICTORIA 
17 17873 Caldas VILLAMARÍA 
17 17877 Caldas VITERBO 
18 18001 Caquetá FLORENCIA 
18 18029 Caquetá ALBANIA 
18 18094 Caquetá BELÉN DE LOS ANDAQUÍES 
18 18150 Caquetá CARTAGENA DEL CHAIRÁ 
18 18205 Caquetá CURILLO 
18 18247 Caquetá EL DONCELLO 
18 18256 Caquetá EL PAUJÍL 
18 18410 Caquetá LA MONTAÑITA 
18 18460 Caquetá MILÁN 
18 18479 Caquetá MORELIA 
18 18592 Caquetá PUERTO RICO 

---

## Página 156

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 156 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
18 18610 Caquetá SAN JOSÉ DEL FRAGUA 
18 18753 Caquetá SAN VICENTE DEL CAGUÁN 
18 18756 Caquetá SOLANO 
18 18785 Caquetá SOLITA 
18 18860 Caquetá VALPARAÍSO 
85 85001 Casanare YOPAL 
85 85010 Casanare AGUAZUL 
85 85015 Casanare CHÁMEZA 
85 85125 Casanare HATO COROZAL 
85 85136 Casanare LA SALINA 
85 85139 Casanare MANÍ 
85 85162 Casanare MONTERREY 
85 85225 Casanare NUNCHÍA 
85 85230 Casanare OROCUÉ 
85 85250 Casanare PAZ DE ARIPORO 
85 85263 Casanare PORE 
85 85279 Casanare RECETOR 
85 85300 Casanare SABANALARGA 
85 85315 Casanare SÁCAMA 
85 85325 Casanare SAN LUIS DE PALENQUE 
85 85400 Casanare TÁMARA 
85 85410 Casanare TAURAMENA 
85 85430 Casanare TRINIDAD 
85 85440 Casanare VILLANUEVA 
19 19001 Cauca POPAYÁN 
19 19022 Cauca ALMAGUER 
19 19050 Cauca ARGELIA 
19 19075 Cauca BALBOA 
19 19100 Cauca BOLÍVAR 
19 19110 Cauca BUENOS AIRES 
19 19130 Cauca CAJIBÍO 
19 19137 Cauca CALDONO 
19 19142 Cauca CALOTO 

---

## Página 157

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 157 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
19 19212 Cauca CORINTO 
19 19256 Cauca EL TAMBO 
19 19290 Cauca FLORENCIA 
19 19300 Cauca GUACHENÉ 
19 19318 Cauca GUAPÍ 
19 19355 Cauca INZÁ 
19 19364 Cauca JAMBALÓ 
19 19392 Cauca LA SIERRA 
19 19397 Cauca LA VEGA 
19 19418 Cauca LÓPEZ DE MICAY 
19 19450 Cauca MERCADERES 
19 19455 Cauca MIRANDA 
19 19473 Cauca MORALES 
19 19513 Cauca PADILLA 
19 19517 Cauca PÁEZ - BELALCAZAR 
19 19532 Cauca PATÍA – EL BORDO 
19 19533 Cauca PIAMONTE 
19 19548 Cauca PIENDAMÓ – TUNÍA 
19 19573 Cauca PUERTO TEJADA 
19 19585 Cauca PURACÉ - COCONUCO 
19 19622 Cauca ROSAS 
19 19693 Cauca SAN SEBASTIÁN 
19 19698 Cauca SANTANDER DE QUILICHAO 
19 19701 Cauca SANTA ROSA 
19 19743 Cauca SILVIA 
19 19760 Cauca SOTARA 
19 19780 Cauca SUÁREZ 
19 19785 Cauca SUCRE 
19 19807 Cauca TIMBÍO 
19 19809 Cauca TIMBIQUÍ 
19 19821 Cauca TORIBÍO 
19 19824 Cauca TOTORÓ 
19 19845 Cauca VILLA RICA 

---

## Página 158

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 158 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
20 20001 Cesar VALLEDUPAR 
20 20011 Cesar AGUACHICA 
20 20013 Cesar AGUSTÍN CODAZZI 
20 20032 Cesar ASTREA 
20 20045 Cesar BECERRIL 
20 20060 Cesar BOSCONIA 
20 20175 Cesar CHIMICHAGUA 
20 20178 Cesar CHIRIGUANÁ 
20 20228 Cesar CURUMANÍ 
20 20238 Cesar EL COPEY 
20 20250 Cesar EL PASO 
20 20295 Cesar GAMARRA 
20 20310 Cesar GONZÁLEZ 
20 20383 Cesar LA GLORIA 
20 20400 Cesar LA JAGUA DE IBIRICO 
20 20443 Cesar MANAURE BALCÓN DEL CESAR 
20 20517 Cesar PAILITAS 
20 20550 Cesar PELAYA 
20 20570 Cesar PUEBLO BELLO 
20 20614 Cesar RÍO DE ORO 
20 20621 Cesar LA PAZ 
20 20710 Cesar SAN ALBERTO 
20 20750 Cesar SAN DIEGO 
20 20770 Cesar SAN MARTÍN 
20 20787 Cesar TAMALAMEQUE 
27 27001 Chocó QUIBDÓ 
27 27006 Chocó ACANDÍ 
27 27025 Chocó ALTO BAUDÓ (PIE DE PATÓ) 
27 27050 Chocó ATRATO (YUTO) 
27 27073 Chocó BAGADÓ 
27 27075 Chocó BAHÍA SOLANO (MUTIS) 
27 27077 Chocó BAJO BAUDÓ (PIZARRO) 
27 27099 Chocó BOJAYÁ (BELLA VISTA) 

---

## Página 159

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 159 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
27 27135 Chocó EL CANTÓN DEL SAN PABLO 
27 27150 Chocó CARMEN DEL DARIÉN 
27 27160 Chocó CÉRTEGUI 
27 27205 Chocó CONDOTO 
27 27245 Chocó EL CARMEN DE ATRATO 
27 27250 Chocó EL LITORAL DEL SAN JUAN 
27 27361 Chocó ISTMINA 
27 27372 Chocó JURADÓ 
27 27413 Chocó LLORÓ 
27 27425 Chocó MEDIO ATRATO (BETÉ) 
27 27430 Chocó MEDIO BAUDÓ 
27 27450 Chocó MEDIO SAN JUAN (ANDAGOYA) 
27 27491 Chocó NÓVITA 
27 27495 Chocó NUQUÍ 
27 27580 Chocó RÍO IRÓ (SANTA RITA) 
27 27600 Chocó RÍO QUITO (PAIMADÓ) 
27 27615 Chocó RIOSUCIO 
27 27660 Chocó SAN JOSÉ DEL PALMAR 
27 27745 Chocó SIPÍ 
27 27787 Chocó TADÓ 
27 27800 Chocó UNGUÍA 
27 27810 Chocó UNIÓN PANAMERICANA (LAS 
ÁNIMAS) 
23 23001 Córdoba MONTERÍA 
23 23068 Córdoba AYAPEL 
23 23079 Córdoba BUENAVISTA 
23 23090 Córdoba CANALETE 
23 23162 Córdoba CERETÉ 
23 23168 Córdoba CHIMÁ 
23 23182 Córdoba CHINÚ 
23 23189 Córdoba CIÉNAGA DE ORO 
23 23300 Córdoba COTORRA 

---

## Página 160

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 160 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
23 23350 Córdoba LA APARTADA 
23 23417 Córdoba LORICA 
23 23419 Córdoba LOS CÓRDOBAS 
23 23464 Córdoba MOMIL 
23 23466 Córdoba MONTELÍBANO 
23 23500 Córdoba MOÑITOS 
23 23555 Córdoba PLANETA RICA 
23 23570 Córdoba PUEBLO NUEVO 
23 23574 Córdoba PUERTO ESCONDIDO 
23 23580 Córdoba PUERTO LIBERTADOR 
23 23586 Córdoba PURÍSIMA DE LA CONCEPCIÓN 
23 23660 Córdoba SAHAGÚN 
23 23670 Córdoba SAN ANDRÉS DE SOTAVENTO 
23 23672 Córdoba SAN ANTERO 
23 23675 Córdoba SAN BERNARDO DEL VIENTO 
23 23678 Córdoba SAN CARLOS 
23 23682 Córdoba SAN JOSÉ DE URÉ 
23 23686 Córdoba SAN PELAYO 
23 23807 Córdoba TIERRALTA 
23 23815 Córdoba TUCHÍN 
23 23855 Córdoba VALENCIA 
25 25001 Cundinamarca AGUA DE DIOS 
25 25019 Cundinamarca ALBÁN 
25 25035 Cundinamarca ANAPOIMA 
25 25040 Cundinamarca ANOLAIMA 
25 25053 Cundinamarca ARBELÁEZ 
25 25086 Cundinamarca BELTRÁN 
25 25095 Cundinamarca BITUIMA 
25 25099 Cundinamarca BOJACÁ 
25 25120 Cundinamarca CABRERA 
25 25123 Cundinamarca CACHIPAY 
25 25126 Cundinamarca CAJICÁ 
25 25148 Cundinamarca CAPARRAPÍ 

---

## Página 161

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 161 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
25 25151 Cundinamarca CÁQUEZA 
25 25154 Cundinamarca CARMEN DE CARUPA 
25 25168 Cundinamarca CHAGUANÍ 
25 25175 Cundinamarca CHÍA 
25 25178 Cundinamarca CHIPAQUE 
25 25181 Cundinamarca CHOACHÍ 
25 25183 Cundinamarca CHOCONTÁ 
25 25200 Cundinamarca COGUA 
25 25214 Cundinamarca COTA 
25 25224 Cundinamarca CUCUNUBÁ 
25 25245 Cundinamarca EL COLEGIO 
25 25258 Cundinamarca EL PEÑÓN 
25 25260 Cundinamarca EL ROSAL 
25 25269 Cundinamarca FACATATIVÁ 
25 25279 Cundinamarca FÓMEQUE 
25 25281 Cundinamarca FOSCA 
25 25286 Cundinamarca FUNZA 
25 25288 Cundinamarca FÚQUENE 
25 25290 Cundinamarca FUSAGASUGÁ 
25 25293 Cundinamarca GACHALÁ 
25 25295 Cundinamarca GACHANCIPÁ 
25 25297 Cundinamarca GACHETÁ 
25 25299 Cundinamarca GAMA 
25 25307 Cundinamarca GIRARDOT 
25 25312 Cundinamarca GRANADA 
25 25317 Cundinamarca GUACHETÁ 
25 25320 Cundinamarca GUADUAS 
25 25322 Cundinamarca GUASCA 
25 25324 Cundinamarca GUATAQUÍ 
25 25326 Cundinamarca GUATAVITA 
25 25328 Cundinamarca GUAYABAL DE SÍQUIMA 
25 25335 Cundinamarca GUAYABETAL 
25 25339 Cundinamarca GUTIÉRREZ 

---

## Página 162

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 162 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
25 25368 Cundinamarca JERUSALÉN 
25 25372 Cundinamarca JUNÍN 
25 25377 Cundinamarca LA CALERA 
25 25386 Cundinamarca LA MESA 
25 25394 Cundinamarca LA PALMA 
25 25398 Cundinamarca LA PEÑA 
25 25402 Cundinamarca LA VEGA 
25 25407 Cundinamarca LENGUAZAQUE 
25 25426 Cundinamarca MACHETÁ 
25 25430 Cundinamarca MADRID 
25 25436 Cundinamarca MANTA 
25 25438 Cundinamarca MEDINA 
25 25473 Cundinamarca MOSQUERA 
25 25483 Cundinamarca NARIÑO 
25 25486 Cundinamarca NEMOCÓN 
25 25488 Cundinamarca NILO 
25 25489 Cundinamarca NIMAIMA 
25 25491 Cundinamarca NOCAIMA 
25 25506 Cundinamarca VENECIA 
25 25513 Cundinamarca PACHO 
25 25518 Cundinamarca PAIME 
25 25524 Cundinamarca PANDI 
25 25530 Cundinamarca PARATEBUENO 
25 25535 Cundinamarca PASCA 
25 25572 Cundinamarca PUERTO SALGAR 
25 25580 Cundinamarca PULÍ 
25 25592 Cundinamarca QUEBRADANEGRA 
25 25594 Cundinamarca QUETAME 
25 25596 Cundinamarca QUIPILE 
25 25599 Cundinamarca APULO 
25 25612 Cundinamarca RICAURTE 
25 25645 Cundinamarca SAN ANTONIO DEL 
TEQUENDAMA 

---

## Página 163

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 163 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
25 25649 Cundinamarca SAN BERNARDO 
25 25653 Cundinamarca SAN CAYETANO 
25 25658 Cundinamarca SAN FRANCISCO 
25 25662 Cundinamarca SAN JUAN DE RIOSECO 
25 25718 Cundinamarca SASAIMA 
25 25736 Cundinamarca SESQUILÉ 
25 25740 Cundinamarca SIBATÉ 
25 25743 Cundinamarca SILVANIA 
25 25745 Cundinamarca SIMIJACA 
25 25754 Cundinamarca SOACHA 
25 25758 Cundinamarca SOPÓ 
25 25769 Cundinamarca SUBACHOQUE 
25 25772 Cundinamarca SUESCA 
25 25777 Cundinamarca SUPATÁ 
25 25779 Cundinamarca SUSA 
25 25781 Cundinamarca SUTATAUSA 
25 25785 Cundinamarca TABIO 
25 25793 Cundinamarca TAUSA 
25 25797 Cundinamarca TENA 
25 25799 Cundinamarca TENJO 
25 25805 Cundinamarca TIBACUY 
25 25807 Cundinamarca TIBIRITA 
25 25815 Cundinamarca TOCAIMA 
25 25817 Cundinamarca TOCANCIPÁ 
25 25823 Cundinamarca TOPAIPÍ 
25 25839 Cundinamarca UBALÁ 
25 25841 Cundinamarca UBAQUE 
25 25843 Cundinamarca VILLA DE SAN DIEGO DE UBATÉ 
25 25845 Cundinamarca UNE 
25 25851 Cundinamarca ÚTICA 
25 25862 Cundinamarca VERGARA 
25 25867 Cundinamarca VIANÍ 
25 25871 Cundinamarca VILLAGÓMEZ 

---

## Página 164

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 164 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
25 25873 Cundinamarca VILLAPINZÓN 
25 25875 Cundinamarca VILLETA 
25 25878 Cundinamarca VIOTÁ 
25 25885 Cundinamarca YACOPÍ 
25 25898 Cundinamarca ZIPACÓN 
25 25899 Cundinamarca ZIPAQUIRÁ 
94 94001 Guainía INÍRIDA 
94 94343 Guainía BARRANCOMINAS 
94 94663 Guainía MAPIRIPANA 
94 94883 Guainía SAN FELIPE 
94 94884 Guainía PUERTO COLOMBIA 
94 94885 Guainía LA GUADALUPE 
94 94886 Guainía CACAHUAL 
94 94887 Guainía PANA PANA 
94 94888 Guainía MORICHAL NUEVO 
95 95001 Guaviare SAN JOSÉ DEL GUAVIARE 
95 95015 Guaviare CALAMAR 
95 95025 Guaviare EL RETORNO 
95 95200 Guaviare MIRAFLORES 
41 41001 Huila NEIVA 
41 41006 Huila ACEVEDO 
41 41013 Huila AGRADO 
41 41016 Huila AIPE 
41 41020 Huila ALGECIRAS 
41 41026 Huila ALTAMIRA 
41 41078 Huila BARAYA 
41 41132 Huila CAMPOALEGRE 
41 41206 Huila COLOMBIA 
41 41244 Huila ELÍAS 
41 41298 Huila GARZÓN 
41 41306 Huila GIGANTE 
41 41319 Huila GUADALUPE 
41 41349 Huila HOBO 

---

## Página 165

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 165 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
41 41357 Huila ÍQUIRA 
41 41359 Huila ISNOS 
41 41378 Huila LA ARGENTINA (LA PLATA 
VIEJA) 
41 41396 Huila LA PLATA 
41 41483 Huila NÁTAGA 
41 41503 Huila OPORAPA 
41 41518 Huila PAICOL 
41 41524 Huila PALERMO 
41 41530 Huila PALESTINA 
41 41548 Huila PITAL 
41 41551 Huila PITALITO 
41 41615 Huila RIVERA 
41 41660 Huila SALADOBLANCO 
41 41668 Huila SAN AGUSTÍN 
41 41676 Huila SANTA MARÍA 
41 41770 Huila SUAZA 
41 41791 Huila TARQUI 
41 41797 Huila TESALIA (CARNICERÍAS) 
41 41799 Huila TELLO 
41 41801 Huila TERUEL 
41 41807 Huila TIMANÁ 
41 41872 Huila VILLAVIEJA 
41 41885 Huila YAGUARÁ 
44 44001 La Guajira RIOHACHA 
44 44035 La Guajira ALBANIA 
44 44078 La Guajira BARRANCAS 
44 44090 La Guajira DIBULLA 
44 44098 La Guajira DISTRACCIÓN 
44 44110 La Guajira EL MOLINO 
44 44279 La Guajira FONSECA 
44 44378 La Guajira HATONUEVO 
44 44420 La Guajira LA JAGUA DEL PILAR 

---

## Página 166

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 166 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
44 44430 La Guajira MAICAO 
44 44560 La Guajira MANAURE 
44 44650 La Guajira SAN JUAN DEL CESAR 
44 44847 La Guajira URIBIA 
44 44855 La Guajira URUMITA 
44 44874 La Guajira VILLANUEVA 
47 47001 Magdalena SANTA MARTA 
47 47030 Magdalena ALGARROBO 
47 47053 Magdalena ARACATACA 
47 47058 Magdalena ARIGUANÍ 
47 47161 Magdalena CERRO DE SAN ANTONIO 
47 47170 Magdalena CHIBOLO 
47 47189 Magdalena CIÉNAGA 
47 47205 Magdalena CONCORDIA 
47 47245 Magdalena EL BANCO 
47 47258 Magdalena EL PIÑÓN 
47 47268 Magdalena EL RETÉN 
47 47288 Magdalena FUNDACIÓN 
47 47318 Magdalena GUAMAL 
47 47460 Magdalena NUEVA GRANADA 
47 47541 Magdalena PEDRAZA 
47 47545 Magdalena PIJIÑO DEL CARMEN 
47 47551 Magdalena PIVIJAY 
47 47555 Magdalena PLATO 
47 47570 Magdalena PUEBLOVIEJO 
47 47605 Magdalena REMOLINO 
47 47660 Magdalena SABANAS DE SAN ÁNGEL 
47 47675 Magdalena SALAMINA 
47 47692 Magdalena SAN SEBASTIÁN DE 
BUENAVISTA 
47 47703 Magdalena SAN ZENÓN 
47 47707 Magdalena SANTA ANA 
47 47720 Magdalena SANTA BÁRBARA DE PINTO 

---

## Página 167

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 167 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
47 47745 Magdalena SITIONUEVO 
47 47798 Magdalena TENERIFE 
47 47960 Magdalena ZAPAYÁN 
47 47980 Magdalena ZONA BANANERA 
50 50001 Meta VILLAVICENCIO 
50 50006 Meta ACACÍAS 
50 50110 Meta BARRANCA DE UPÍA 
50 50124 Meta CABUYARO 
50 50150 Meta CASTILLA LA NUEVA 
50 50223 Meta CUBARRAL 
50 50226 Meta CUMARAL 
50 50245 Meta EL CALVARIO 
50 50251 Meta EL CASTILLO 
50 50270 Meta EL DORADO 
50 50287 Meta FUENTEDEORO 
50 50313 Meta GRANADA 
50 50318 Meta GUAMAL 
50 50325 Meta MAPIRIPÁN 
50 50330 Meta MESETAS 
50 50350 Meta LA MACARENA 
50 50370 Meta URIBE 
50 50400 Meta LEJANÍAS 
50 50450 Meta PUERTO CONCORDIA 
50 50568 Meta PUERTO GAITÁN 
50 50573 Meta PUERTO LÓPEZ 
50 50577 Meta PUERTO LLERAS 
50 50590 Meta PUERTO RICO 
50 50606 Meta RESTREPO 
50 50680 Meta SAN CARLOS DE GUAROA 
50 50683 Meta SAN JUAN DE ARAMA 
50 50686 Meta SAN JUANITO 
50 50689 Meta SAN MARTÍN DE LOS LLANOS 
50 50711 Meta VISTAHERMOSA 

---

## Página 168

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 168 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
52 52001 Nariño PASTO 
52 52019 Nariño ALBÁN (SAN JOSÉ) 
52 52022 Nariño ALDANA 
52 52036 Nariño ANCUYÁ 
52 52051 Nariño ARBOLEDA 
52 52079 Nariño BARBACOAS 
52 52083 Nariño BELÉN 
52 52110 Nariño BUESACO 
52 52203 Nariño COLÓN (GÉNOVA) 
52 52207 Nariño CONSACÁ 
52 52210 Nariño CONTADERO 
52 52215 Nariño CÓRDOBA 
52 52224 Nariño CUASPÚD 
52 52227 Nariño CUMBAL 
52 52233 Nariño CUMBITARA 
52 52240 Nariño CHACHAGÜÍ 
52 52250 Nariño EL CHARCO 
52 52254 Nariño EL PEÑOL 
52 52256 Nariño EL ROSARIO 
52 52258 Nariño EL TABLÓN DE GÓMEZ 
52 52260 Nariño EL TAMBO 
52 52287 Nariño FUNES 
52 52317 Nariño GUACHUCAL 
52 52320 Nariño GUAITARILLA 
52 52323 Nariño GUALMATÁN 
52 52352 Nariño ILES 
52 52354 Nariño IMUÉS 
52 52356 Nariño IPIALES 
52 52378 Nariño LA CRUZ 
52 52381 Nariño LA FLORIDA 
52 52385 Nariño LA LLANADA 
52 52390 Nariño LA TOLA 
52 52399 Nariño LA UNIÓN 

---

## Página 169

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 169 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
52 52405 Nariño LEIVA 
52 52411 Nariño LINARES 
52 52418 Nariño LOS ANDES (SOTOMAYOR) 
52 52427 Nariño MAGÜÍ (PAYÁN) 
52 52435 Nariño MALLAMA (PIEDRANCHA) 
52 52473 Nariño MOSQUERA 
52 52480 Nariño NARIÑO 
52 52490 Nariño OLAYA HERRERA 
52 52506 Nariño OSPINA 
52 52520 Nariño FRANCISCO PIZARRO 
52 52540 Nariño POLICARPA 
52 52560 Nariño POTOSÍ 
52 52565 Nariño PROVIDENCIA 
52 52573 Nariño PUERRES 
52 52585 Nariño PUPIALES 
52 52612 Nariño RICAURTE 
52 52621 Nariño ROBERTO PAYÁN (SAN JOSÉ) 
52 52678 Nariño SAMANIEGO 
52 52683 Nariño SANDONÁ 
52 52685 Nariño SAN BERNARDO 
52 52687 Nariño SAN LORENZO 
52 52693 Nariño SAN PABLO 
52 52694 Nariño SAN PEDRO DE CARTAGO 
52 52696 Nariño SANTA BÁRBARA 
52 52699 Nariño SANTACRUZ 
52 52720 Nariño SAPUYES 
52 52786 Nariño TAMINANGO 
52 52788 Nariño TANGUA 
52 52835 Nariño SAN ANDRÉS DE TUMACO 
52 52838 Nariño TÚQUERRES 
52 52885 Nariño YACUANQUER 
54 54001 Norte de Santander CÚCUTA 
54 54003 Norte de Santander ÁBREGO 

---

## Página 170

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 170 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
54 54051 Norte de Santander ARBOLEDAS 
54 54099 Norte de Santander BOCHALEMA 
54 54109 Norte de Santander BUCARASICA 
54 54125 Norte de Santander CÁCOTA DE VELASCO 
54 54128 Norte de Santander CÁCHIRA 
54 54172 Norte de Santander CHINÁCOTA 
54 54174 Norte de Santander CHITAGÁ 
54 54206 Norte de Santander CONVENCIÓN 
54 54223 Norte de Santander CUCUTILLA 
54 54239 Norte de Santander DURANIA 
54 54245 Norte de Santander EL CARMEN 
54 54250 Norte de Santander EL TARRA 
54 54261 Norte de Santander EL ZULIA 
54 54313 Norte de Santander GRAMALOTE 
54 54344 Norte de Santander HACARÍ 
54 54347 Norte de Santander HERRÁN 
54 54377 Norte de Santander LABATECA 
54 54385 Norte de Santander LA ESPERANZA 
54 54398 Norte de Santander LA PLAYA DE BELÉN 
54 54405 Norte de Santander LOS PATIOS 
54 54418 Norte de Santander LOURDES 
54 54480 Norte de Santander MUTISCUA 
54 54498 Norte de Santander OCAÑA 
54 54518 Norte de Santander PAMPLONA 
54 54520 Norte de Santander PAMPLONITA 
54 54553 Norte de Santander PUERTO SANTANDER 
54 54599 Norte de Santander RAGONVALIA 
54 54660 Norte de Santander SALAZAR DE LAS PALMAS 
54 54670 Norte de Santander SAN CALIXTO 
54 54673 Norte de Santander SAN CAYETANO 
54 54680 Norte de Santander SANTIAGO 
54 54720 Norte de Santander SARDINATA 
54 54743 Norte de Santander SANTO DOMINGO DE SILOS 

---

## Página 171

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 171 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
54 54800 Norte de Santander TEORAMA 
54 54810 Norte de Santander TIBÚ 
54 54820 Norte de Santander TOLEDO 
54 54871 Norte de Santander VILLA CARO 
54 54874 Norte de Santander VILLA DEL ROSARIO 
86 86001 Putumayo MOCOA 
86 86219 Putumayo COLÓN 
86 86320 Putumayo ORITO 
86 86568 Putumayo PUERTO ASÍS 
86 86569 Putumayo PUERTO CAICEDO 
86 86571 Putumayo PUERTO GUZMÁN 
86 86573 Putumayo PUERTO LEGUÍZAMO 
86 86749 Putumayo SIBUNDOY 
86 86755 Putumayo SAN FRANCISCO 
86 86757 Putumayo SAN MIGUEL 
86 86760 Putumayo SANTIAGO 
86 86865 Putumayo VALLE DEL GUAMUEZ 
86 86885 Putumayo VILLAGARZÓN 
63 63001 Quindío ARMENIA 
63 63111 Quindío BUENAVISTA 
63 63130 Quindío CALARCÁ 
63 63190 Quindío CIRCASIA 
63 63212 Quindío CÓRDOBA 
63 63272 Quindío FILANDIA 
63 63302 Quindío GÉNOVA 
63 63401 Quindío LA TEBAIDA 
63 63470 Quindío MONTENEGRO 
63 63548 Quindío PIJAO 
63 63594 Quindío QUIMBAYA 
63 63690 Quindío SALENTO 
66 66001 Risaralda PEREIRA 
66 66045 Risaralda APÍA 
66 66075 Risaralda BALBOA 

---

## Página 172

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 172 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
66 66088 Risaralda BELÉN DE UMBRÍA 
66 66170 Risaralda DOSQUEBRADAS 
66 66318 Risaralda GUÁTICA 
66 66383 Risaralda LA CELIA 
66 66400 Risaralda LA VIRGINIA 
66 66440 Risaralda MARSELLA 
66 66456 Risaralda MISTRATÓ 
66 66572 Risaralda PUEBLO RICO 
66 66594 Risaralda QUINCHÍA 
66 66682 Risaralda SANTA ROSA DE CABAL 
66 66687 Risaralda SANTUARIO 
68 68001 Santander BUCARAMANGA 
68 68013 Santander AGUADA 
68 68020 Santander ALBANIA 
68 68051 Santander ARATOCA 
68 68077 Santander BARBOSA 
68 68079 Santander BARICHARA 
68 68081 Santander BARRANCABERMEJA 
68 68092 Santander BETULIA 
68 68101 Santander BOLÍVAR 
68 68121 Santander CABRERA 
68 68132 Santander CALIFORNIA 
68 68147 Santander CAPITANEJO 
68 68152 Santander CARCASÍ 
68 68160 Santander CEPITÁ 
68 68162 Santander CERRITO 
68 68167 Santander CHARALÁ 
68 68169 Santander CHARTA 
68 68176 Santander CHIMA 
68 68179 Santander CHIPATÁ 
68 68190 Santander CIMITARRA 
68 68207 Santander CONCEPCIÓN 
68 68209 Santander CONFINES 

---

## Página 173

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 173 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
68 68211 Santander CONTRATACIÓN 
68 68217 Santander COROMORO 
68 68229 Santander CURITÍ 
68 68235 Santander EL CARMEN DE CHUCURÍ 
68 68245 Santander EL GUACAMAYO 
68 68250 Santander EL PEÑÓN 
68 68255 Santander EL PLAYÓN 
68 68264 Santander ENCINO 
68 68266 Santander ENCISO 
68 68271 Santander FLORIÁN 
68 68276 Santander FLORIDABLANCA 
68 68296 Santander GALÁN 
68 68298 Santander GÁMBITA 
68 68307 Santander GIRÓN 
68 68318 Santander GUACA 
68 68320 Santander GUADALUPE 
68 68322 Santander GUAPOTÁ 
68 68324 Santander GUAVATÁ 
68 68327 Santander GÜEPSA 
68 68344 Santander HATO 
68 68368 Santander JESÚS MARÍA 
68 68370 Santander JORDÁN 
68 68377 Santander LA BELLEZA 
68 68385 Santander LANDÁZURI 
68 68397 Santander LA PAZ 
68 68406 Santander LEBRIJA 
68 68418 Santander LOS SANTOS 
68 68425 Santander MACARAVITA 
68 68432 Santander MÁLAGA 
68 68444 Santander MATANZA 
68 68464 Santander MOGOTES 
68 68468 Santander MOLAGAVITA 
68 68498 Santander OCAMONTE 

---

## Página 174

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 174 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
68 68500 Santander OIBA 
68 68502 Santander ONZAGA 
68 68522 Santander PALMAR 
68 68524 Santander PALMAS DEL SOCORRO 
68 68533 Santander PÁRAMO 
68 68547 Santander PIEDECUESTA 
68 68549 Santander PINCHOTE 
68 68572 Santander PUENTE NACIONAL 
68 68573 Santander PUERTO PARRA 
68 68575 Santander PUERTO WILCHES 
68 68615 Santander RIONEGRO 
68 68655 Santander SABANA DE TORRES 
68 68669 Santander SAN ANDRÉS 
68 68673 Santander SAN BENITO 
68 68679 Santander SAN GIL 
68 68682 Santander SAN JOAQUÍN 
68 68684 Santander SAN JOSÉ DE MIRANDA 
68 68686 Santander SAN MIGUEL 
68 68689 Santander SAN VICENTE DE CHUCURÍ 
68 68705 Santander SANTA BÁRBARA 
68 68720 Santander SANTA HELENA DEL OPÓN 
68 68745 Santander SIMACOTA 
68 68755 Santander SOCORRO 
68 68770 Santander SUAITA 
68 68773 Santander SUCRE 
68 68780 Santander SURATÁ 
68 68820 Santander TONA 
68 68855 Santander VALLE DE SAN JOSÉ 
68 68861 Santander VÉLEZ 
68 68867 Santander VETAS 
68 68872 Santander VILLANUEVA 
68 68895 Santander ZAPATOCA 
70 70001 Sucre SINCELEJO 

---

## Página 175

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 175 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
70 70110 Sucre BUENAVISTA 
70 70124 Sucre CAIMITO 
70 70204 Sucre COLOSÓ 
70 70215 Sucre COROZAL 
70 70221 Sucre COVEÑAS 
70 70230 Sucre CHALÁN 
70 70233 Sucre EL ROBLE 
70 70235 Sucre GALERAS 
70 70265 Sucre GUARANDA 
70 70400 Sucre LA UNIÓN 
70 70418 Sucre LOS PALMITOS 
70 70429 Sucre MAJAGUAL 
70 70473 Sucre MORROA 
70 70508 Sucre OVEJAS 
70 70523 Sucre PALMITO 
70 70670 Sucre SAMPUÉS 
70 70678 Sucre SAN BENITO ABAD 
70 70702 Sucre SAN JUAN DE BETULIA 
70 70708 Sucre SAN MARCOS 
70 70713 Sucre SAN ONOFRE 
70 70717 Sucre SAN PEDRO 
70 70742 Sucre SAN LUIS DE SINCÉ 
70 70771 Sucre SUCRE 
70 70820 Sucre SANTIAGO DE TOLÚ 
70 70823 Sucre TOLÚ VIEJO 
73 73001 Tolima IBAGUÉ 
73 73024 Tolima ALPUJARRA 
73 73026 Tolima ALVARADO 
73 73030 Tolima AMBALEMA 
73 73043 Tolima ANZOÁTEGUI 
73 73055 Tolima ARMERO (GUAYABAL) 
73 73067 Tolima ATACO 
73 73124 Tolima CAJAMARCA 

---

## Página 176

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 176 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
73 73148 Tolima CARMEN DE APICALÁ 
73 73152 Tolima CASABIANCA 
73 73168 Tolima CHAPARRAL 
73 73200 Tolima COELLO 
73 73217 Tolima COYAIMA 
73 73226 Tolima CUNDAY 
73 73236 Tolima DOLORES 
73 73268 Tolima ESPINAL 
73 73270 Tolima FALAN 
73 73275 Tolima FLANDES 
73 73283 Tolima FRESNO 
73 73319 Tolima GUAMO 
73 73347 Tolima HERVEO 
73 73349 Tolima HONDA 
73 73352 Tolima ICONONZO 
73 73408 Tolima LÉRIDA 
73 73411 Tolima LÍBANO 
73 73443 Tolima SAN SEBASTIÁN DE MARIQUITA 
73 73449 Tolima MELGAR 
73 73461 Tolima MURILLO 
73 73483 Tolima NATAGAIMA 
73 73504 Tolima ORTEGA 
73 73520 Tolima PALOCABILDO 
73 73547 Tolima PIEDRAS 
73 73555 Tolima PLANADAS 
73 73563 Tolima PRADO 
73 73585 Tolima PURIFICACIÓN 
73 73616 Tolima RIOBLANCO 
73 73622 Tolima RONCESVALLES 
73 73624 Tolima ROVIRA 
73 73671 Tolima SALDAÑA 
73 73675 Tolima SAN ANTONIO 

---

## Página 177

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 177 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
73 73678 Tolima SAN LUIS 
73 73686 Tolima SANTA ISABEL 
73 73770 Tolima SUÁREZ 
73 73854 Tolima VALLE DE SAN JUAN 
73 73861 Tolima VENADILLO 
73 73870 Tolima VILLAHERMOSA 
73 73873 Tolima VILLARRICA 
76 76001 Valle del Cauca CALI 
76 76020 Valle del Cauca ALCALÁ 
76 76036 Valle del Cauca ANDALUCÍA 
76 76041 Valle del Cauca ANSERMANUEVO 
76 76054 Valle del Cauca ARGELIA 
76 76100 Valle del Cauca BOLÍVAR 
76 76109 Valle del Cauca BUENAVENTURA 
76 76111 Valle del Cauca GUADALAJARA DE BUGA 
76 76113 Valle del Cauca BUGALAGRANDE 
76 76122 Valle del Cauca CAICEDONIA 
76 76126 Valle del Cauca CALIMA (DARIEN) 
76 76130 Valle del Cauca CANDELARIA 
76 76147 Valle del Cauca CARTAGO 
76 76233 Valle del Cauca DAGUA 
76 76243 Valle del Cauca EL ÁGUILA 
76 76246 Valle del Cauca EL CAIRO 
76 76248 Valle del Cauca EL CERRITO 
76 76250 Valle del Cauca EL DOVIO 
76 76275 Valle del Cauca FLORIDA 
76 76306 Valle del Cauca GINEBRA 
76 76318 Valle del Cauca GUACARÍ 
76 76364 Valle del Cauca JAMUNDÍ 
76 76377 Valle del Cauca LA CUMBRE 
76 76400 Valle del Cauca LA UNIÓN 
76 76403 Valle del Cauca LA VICTORIA 
76 76497 Valle del Cauca OBANDO 

---

## Página 178

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 178 de 269 
 
Código Departamento Código Municipio Nombre Departamento Nombre Municipio 
76 76520 Valle del Cauca PALMIRA 
76 76563 Valle del Cauca PRADERA 
76 76606 Valle del Cauca RESTREPO 
76 76616 Valle del Cauca RIOFRÍO 
76 76622 Valle del Cauca ROLDANILLO 
76 76670 Valle del Cauca SAN PEDRO 
76 76736 Valle del Cauca SEVILLA 
76 76823 Valle del Cauca TORO 
76 76828 Valle del Cauca TRUJILLO 
76 76834 Valle del Cauca TULUÁ 
76 76845 Valle del Cauca ULLOA 
76 76863 Valle del Cauca VERSALLES 
76 76869 Valle del Cauca VIJES 
76 76890 Valle del Cauca YOTOCO 
76 76892 Valle del Cauca YUMBO 
76 76895 Valle del Cauca ZARZAL 
97 97001 Vaupés MITÚ 
97 97161 Vaupés CARURÚ 
97 97511 Vaupés PACOA 
97 97666 Vaupés TARAIRA 
97 97777 Vaupés PAPUNAHUA 
97 97889 Vaupés YAVARATÉ 
99 99001 Vichada PUERTO CARREÑO 
99 99524 Vichada LA PRIMAVERA 
99 99624 Vichada SANTA ROSALÍA 
99 99773 Vichada CUMARIBO 
 
5.5. Campos Nómina. 
5.5.1. Periodo de Nómina: PeriodoNomina. 
Código Periodo de Nómina 
1 Semanal 
2 Decenal 
3 Catorcenal 
4 Quincenal 

---

## Página 179

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 179 de 269 
 
Código Periodo de Nómina 
5 Mensual 
6 Otro 
 
5.5.2. Tipo de Contrato: TipoContrato. 
Código Tipo de Contrato 
1 Termino Fijo 
2 Término Indefinido 
3 Obra o Labor 
4 Aprendizaje 
5 Prácticas o Pasantías 
 
5.5.3. Tipo de Trabajador: TipoTrabajador. 
Código Tipo de Trabajador 
01 Dependiente 
02 Servicio domestico 
04 Madre comunitaria 
12 Aprendices del Sena en etapa lectiva 
18 Funcionarios públicos sin tope máximo de ibc 
19 Aprendices del SENA en etapa productiva 
21 Estudiantes de postgrado en salud 
22 Profesor de establecimiento particular 
23 Estudiantes aportes solo riesgos laborales 
30 Dependiente entidades o universidades públicas con régimen especial en salud 
31 Cooperados o pre cooperativas de trabajo asociado 
47 Trabajador dependiente de entidad beneficiaria del sistema general de 
participaciones - aportes patronales 
51 Trabajador de tiempo parcial 
54 Pre pensionado de entidad en liquidación. 
56 Pre pensionado con aporte voluntario a salud 
58 Estudiantes de prácticas laborales en el sector público 
 
5.5.4. Subtipo de Trabajador: SubTipoTrabajador. 
Código Subtipo de Trabajador 
00 No Aplica 
01 Dependiente pensionado por vejez activo 
 

---

## Página 180

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 180 de 269 
 
5.5.5. Tipo de Hora Extra o Recargo: Porcentaje. 
Código Tipo de Hora Extra o Recargo Porcentaje 
1 Hora Extra Diurna 25.00 
2 Hora Extra Nocturna 75.00 
3 Hora Recargo Nocturno 35.00 
4 Hora Extra Diurna Dominical y Festivos 100.00 
5 Hora Recargo Diurno Dominical y Festivos 75.00 
6 Hora Extra Nocturna Dominical y Festivos 150.00 
7 Hora Recargo Nocturno Dominical y Festivos 110.00 
 
5.5.6. Tipo de Incapacidad: Tipo. 
Código Tipo de Incapacidad 
1 Común 
2 Profesional 
3 Laboral 
 
5.5.7. Tipo de XML: TipoXML. 
Código Nombre XML Tipo de XML 
102 NominaIndividual Documento Soporte de Pago de Nómina Electrónica 
103 NominaIndividualDeAjuste Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica 
 
5.5.8. Tipo de Nota de Ajuste: TipoNota. 
Código Tipo de Nota de Ajuste 
1 Reemplazar 
2 Eliminar 
 
Reemplazar: Se utilizará este código cuando se requiera realizar ajustes sobre Documentos 
Soporte de Pago de Nómina Electrónica o Notas de Ajuste del Documento Soporte de Pago 
de Nómina Electrónica, por errores aritméticos, contables o de contenido. 
Eliminar: Se utilizará este código cuando se requiera eliminar el Documento Soporte de Pago 
de Nómina Electrónica, y/o una Nota de Ajuste del Documento Soporte de Pago de Nómina 
Electrónica, para los casos en los cuales se haya transmitido un documento por error es 
contables o de procedimiento.  
 
Nota: Se indica que el tipo de Nota de Ajuste del Documento Soporte de Pago de Nómina 
Electrónica con código 2 Eliminar, solo invalida los documentos enviados por error, no 

---

## Página 181

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 181 de 269 
 
obtante los mismos seguirán existiendo en la base de datos pero quedar án marcados con 
esta observación. 

---

## Página 182

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 182 de 269 
 
6. Reglas y Mensajes de Validación. 
En el presente capítulo se presentan los mensajes correspondientes a las reglas de validación. 
La Columna “Y” contiene, la definición si una regla determina rechazo (“R”) o notificación (”N”).  
Un documento solamente puede recibir el sello de “validado” si no falla en ninguna validación identificada por 
“R”. 
Un documento puede recibir el sello de “validado” independiente de fallar en cualquier número de las reglas 
identificadas por “N”. 
La construcción de las reglas puede ser encontrada en las tabla s del capítulo 6.1.1 la columna ID: identifica la 
línea correspondiente en aquellos capítulos y en este capítulo. 
En el caso de que la evaluación de un determinado elemento pueda tener más que una regla, en el presente 
capítulo se adicionan letras (a, b, …) al correspondiente ID para diferenciar los resultados posibles. 
Algunos elementos pueden ocurrir en diferentes partes del documento XML; en estos casos, los mensajes 
deben explicitar el Xpath completo, para permitir la correcta identificación de la corre spondiente ubicación. 
Estos elementos están identificados en la columna “Mensaje” por la expresión <Xpath>. 
El resultado de una validación fallida debe siempre ser la concatenación entre el ID, el resultado (“R” o “N”), y 
el mensaje correspondiente, como se puede ver en los siguientes ejemplos: 
 
Tabla 8 – Ejemplos de Mensajes de Validación. 
Mensaje 
NIE022 – (R) Debe ir el literal: "V1.0: Documento Soporte de Pago de Nómina Electrónica" 
NIE013 – (R) Se debe colocar el Codigo alfa-2 correspondiente 
 
Se informa la incorporación de las siguientes reglas: 
ID Y Elemento Regla Mensaje V Xpath 
90 R  Solo se podrá transmitir una única vez el Número del 
documento para el trabajador. Documento procesado anteriormente 1.0  
92 R  
El Emisor del Documento debe encontrarse habilitado en 
la plataforma de emisión de Nómina Electrónica (Para 
NominaIndividual y NominaIndividualDeAjuste). 
El Emisor del Documento no se 
encuentra Habilitado en la 
Plataforma. 
1.0  
VLR01 R  Los valores monetarios/porcentajes deben corresponder 
a valores positivos 
Los valores monetarios/porcentajes 
deben corresponder a valores 
Positivos 
1.0  
 
6.1. Documentos Electrónicos. 
6.1.1. Documento Soporte de Pago de Nómina Electrónica: NominaIndividual. 
 
ID Y Campo Regla Mensaje V Xpath 
NIE901 R - 
El documento debe poseer 
Todos los Namespace 
correspondientes a su 
estructura. 
El documento debe poseer 
Todos los Namespace 
correspondientes a su 
estructura. 
1.0 /NominaIndividual/ 

---

## Página 183

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 183 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE001 R UBLExtensions 
Solamente puede haber una 
ocurrencia de un grupo 
UBLExtensions conteniendo el 
grupo ds:Signature. Ver 
definición en numeral 3.6 
Solamente puede haber una 
ocurrencia de un grupo 
UBLExtensions conteniendo el 
grupo ds:Signature. 
1.0 /NominaIndividual/ext:UB
LExtensions 
NIE199 R Novedad 
Indica si existe alguna Novedad 
Contractual en el Documento 
Soporte de Pago de Nómina 
Electrónica o Nota de Ajuste de 
Documento Soporte de Pago de 
Nómina Electrónica del 
Trabajador en dicho Mes. 
Se debe colocar "true" o "false". 1.0 /NominaIndividual/Noved
ad 
NIE199a R Novedad 
Indica si existe alguna Novedad 
Contractual en el Documento 
Soporte de Pago de Nómina 
Electrónica o Nota de Ajuste de 
Documento Soporte de Pago de 
Nómina Electrónica del 
Trabajador en dicho Mes. 
Elemento Novedad con valor 
“true” no puede ser recibido 
por primera vez, ya que no 
existe un Documento Soporte 
de Pago de Nómina Electrónica 
o Nota de Ajuste de Documento 
Soporte de Pago de Nómina 
Electrónica recibida para este 
trabajador reportada por este 
Emisor durante este mes. 
1.0 /NominaIndividual/Noved
ad 
NIE204 R CUNENov Debe ir el CUNE del documento 
a Reemplazar 
Debe ir el CUNE del documento 
al cual se le realizará la novedad 
contractual 
1.0 /NominaIndividual/Noved
ad/@CUNENov 
NIE204a R CUNENov Debe ir el CUNE del documento 
a Reemplazar 
Documento a Realizar la 
Novedad contractual no se 
encuentra recibido en la Base 
de Datos. 
1.0 /NominaIndividual/Noved
ad/@CUNENov 
NIE002 R FechaIngreso 
Se debe indicar la Fecha de 
Ingreso del trabajador a la 
empresa, en formato AAAA-
MM-DD 
Se debe indicar la Fecha de 
Ingreso del trabajador a la 
empresa, en formato AAAA-
MM-DD 
1.0 /NominaIndividual/Period
o/@FechaIngreso 
NIE003 R FechaRetiro 
Se debe indicar la Fecha de 
Retiro del trabajador a la 
empresa, en formato AAAA-
MM-DD 
Se debe indicar la Fecha de 
Retiro del trabajador a la 
empresa, en formato AAAA-
MM-DD 
1.0 /NominaIndividual/Period
o/@FechaRetiro 
NIE004 R FechaLiquidacionIni
cio 
Se debe indicar la Fecha de 
Inicio del Periodo de Liquidación 
del documento, en formato 
AAAA-MM-DD 
Se debe indicar la Fecha de 
Inicio del Periodo de Liquidación 
del documento, en formato 
AAAA-MM-DD 
1.0 
/NominaIndividual/Period
o/@FechaLiquidacionInici
o 

---

## Página 184

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 184 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE005 R FechaLiquidacionFin 
Se debe indicar la Fecha de Fin 
del Periodo de Liquidación del 
documento, en formato AAAA-
MM-DD 
Se debe indicar la Fecha de Fin 
del Periodo de Liquidación del 
documento, en formato AAAA-
MM-DD 
1.0 /NominaIndividual/Period
o/@FechaLiquidacionFin 
NIE006 R TiempoLaborado Definido en el numeral 8.4.1, 
debe ser mayor o gual a 1. 
Se debe indicar el Tiempo 
laborado del trabajador según la 
definición establecida. 
1.0 /NominaIndividual/Period
o/@TiempoLaborado 
NIE008 R FechaGen 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
1.0 /NominaIndividual/Period
o/@FechaGen 
NIE009 N CodigoTrabajador Campo Opcional queda a 
manejo Interno del Empleador. 
Se debe indicar el Codigo del 
Trabajador. 1.0 
/NominaIndividual/Numer
oSecuenciaXML/@Codigo
Trabajador 
NIE010 R Prefijo 
Debe corresponder a un Prefijo 
elegido por el Emisor del 
documento 
Debe corresponder a un Prefijo 
elegido por el Emisor del 
documento 
1.0 /NominaIndividual/Numer
oSecuenciaXML/@Prefijo 
NIE011 R Consecutivo 
Debe corresponder a un 
Consecutivo elegido por el 
Emisor del documento 
Debe corresponder a un 
Consecutivo elegido por el 
Emisor del documento 
1.0 
/NominaIndividual/Numer
oSecuenciaXML/@Consec
utivo 
NIE012 R Numero 
No se permiten caracteres 
adicionales como espacios o 
guiones. Prefijo + Número 
consecutivo del documento 
No se permiten caracteres 
adicionales como espacios o 
guiones. Debe corresponder a 
Prefijo + Número consecutivo 
del documento 
1.0 
/NominaIndividual/Numer
oSecuenciaXML/@Numer
o 
NIE013 R Pais Se debe colocar el Codigo alfa-2 
de la tabla 5.4.1 
Se debe colocar el Codigo alfa-2 
correspondiente 1.0 /NominaIndividual/LugarG
eneracionXML/@Pais 
NIE014 R DepartamentoEstad
o 
Se debe colocar el Codigo de la 
tabla 5.4.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividual/LugarG
eneracionXML/@Departa
mentoEstado 
NIE015 R MunicipioCiudad Se debe colocar el Codigo de la 
tabla 5.4.3 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividual/LugarG
eneracionXML/@Municipi
oCiudad 
NIE016 R Idioma 
Se debe colocar el Codigo ISO 
639-1 de la tabla 5.3.1. Para 
Colombia se debe colocar "es" 
(Español, Castellano) 
Se debe colocar el Codigo ISO 
639-1 correspondiente. Para 
Colombia se debe colocar "es" 
(Español, Castellano) 
1.0 /NominaIndividual/LugarG
eneracionXML/@Idioma 
NIE205 R RazonSocial 
Debe ir el Nombre o Razón 
Social del Proveedor de 
Soluciones Tecnológicas 
Debe ir el Nombre o Razón 
Social del Proveedor de 
Soluciones Tecnológicas 
1.0 /NominaIndividual/Provee
dorXML/@RazonSocial 

---

## Página 185

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 185 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE206 R PrimerApellido 
Debe ir el Primer Apellido del 
Proveedor de Soluciones 
Tecnológicas 
Debe ir el Primer Apellido del 
Proveedor de Soluciones 
Tecnológicas 
1.0 /NominaIndividual/Provee
dorXML/@PrimerApellido 
NIE207 R SegundoApellido 
Debe ir el Segundo Apellido del 
Proveedor de Soluciones 
Tecnológicas 
Debe ir el Segundo Apellido del 
Proveedor de Soluciones 
Tecnológicas 
1.0 
/NominaIndividual/Provee
dorXML/@SegundoApellid
o 
NIE208 R PrimerNombre 
Debe ir el Primer Nombre del 
Proveedor de Soluciones 
Tecnológicas 
Debe ir el Primer Nombre del 
Proveedor de Soluciones 
Tecnológicas 
1.0 /NominaIndividual/Provee
dorXML/@PrimerNombre 
NIE209 N OtrosNombres 
Deben ir los Otros Nombres del 
Proveedor de Soluciones 
Tecnológicas 
Deben ir los Otros Nombres del 
Proveedor de Soluciones 
Tecnológicas 
1.0 /NominaIndividual/Provee
dorXML/@OtrosNombres 
NIE017 R NIT 
Se debe colocar el NIT sin 
guiones ni DV de la empresa 
dueña del Software que genera 
el Documento, debe estar 
registrado en la DIAN 
Se debe colocar el NIT sin 
guiones ni DV de la empresa 
dueña del Software que genera 
el Documento, debe estar 
registrado en la DIAN 
1.0 /NominaIndividual/Provee
dorXML/@NIT 
NIE018 R DV 
Se debe colocar el DV de la 
empresa dueña del Software 
que genera el Documento, debe 
estar registrado en la DIAN 
Se debe colocar el DV de la 
empresa dueña del Software 
que genera el Documento, debe 
estar registrado en la DIAN 
1.0 /NominaIndividual/Provee
dorXML/@DV 
NIE019 R SoftwareID 
Identificador del software 
asignado cuando el software se 
activa en el Sistema de 
Documento Soporte de Pago de 
Nómina Electrónica, debe 
corresponder a un software 
autorizado para este Emisor 
Identificador del software 
asignado cuando el software se 
activa en el Sistema de 
Documento Soporte de Pago de 
Nómina Electrónica, debe 
corresponder a un software 
autorizado para este Emisor 
1.0 /NominaIndividual/Provee
dorXML/@SoftwareID 
NIE020 R SoftwareSC Definido en el numeral 8.3 
Se debe indicar el Software 
Security Code según la 
definición establecida. 
1.0 /NominaIndividual/Provee
dorXML/@SoftwareSC 
NIE021 R CodigoQR 
Debe corresponder a la 
siguiente URL “https://catalogo-
vpfe.dian.gov.co/document/sea
rchqr?documentkey=CUNE”  
donde la palabra CUNE debe ser 
reemplazada por el CUNE del 
documento electrónico 
Se debe indicar la información 
detallada del docuemnto según 
la definición establecida. 
1.0 /NominaIndividual/Codigo
QR 
NIE022 R Version 
Debe ir el literal: " V1.0: 
Documento Soporte de Pago de 
Nómina Electrónica " 
Debe ir el literal: " V1.0: 
Documento Soporte de Pago de 
Nómina Electrónica " 
1.0 /NominaIndividual/Inform
acionGeneral/@Version 

---

## Página 186

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 186 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE023 R Ambiente Se debe colocar el Codigo de la 
tabla 5.1.1 
Se debe colocar el Codigo 
correspondiente 1.0 /NominaIndividual/Inform
acionGeneral/@Ambiente 
NIE202 R TipoXML Se debe colocar el Codigo de la 
tabla 5.5.7 
Se debe colocar el Codigo 
correspondiente 1.0 /NominaIndividual/Inform
acionGeneral/@TipoXML 
NIE024 R CUNE Definido en el numeral 8.1 Se debe indicar el CUNE según 
la definición establecida. 1.0 /NominaIndividual/Inform
acionGeneral/@CUNE 
NIE025 R EncripCUNE Debe ir la palabra "CUNE-
SHA384" 
Debe ir la palabra "CUNE-
SHA384" 1.0 
/NominaIndividual/Inform
acionGeneral/@EncripCU
NE 
NIE026 R FechaGen 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
1.0 /NominaIndividual/Inform
acionGeneral/@FechaGen 
NIE027 R HoraGen 
Debe ir la hora de emision del 
documento. Considerando zona 
horaria de Colombia (-5) 
Debe ir la hora de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato HH:MM:SSdhh:mm 
1.0 /NominaIndividual/Inform
acionGeneral/@HoraGen 
NIE029 R PeriodoNomina Se debe colocar el Codigo de la 
tabla 5.5.1.1 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividual/Inform
acionGeneral/@PeriodoN
omina 
NIE030 R TipoMoneda 
Se debe colocar el Codigo de la 
tabla 5.3.2. Para Colombia se 
debe colocar "COP" 
Se debe colocar el Codigo 
correspondiente. Para Colombia 
se debe colocar "COP" 
1.0 
/NominaIndividual/Inform
acionGeneral/@TipoMone
da 
NIE200 R TRM 
Tasa Representativa del 
mercado. Corresponde a la tasa 
de cambio de la moneda 
utilizada en el documento en el 
Campo “TipoMoneda” a Pesos 
Colombianos. 
Se debe colocar la tasa de 
cambio de la moneda utilizada 
en el documento en el Campo 
“TipoMoneda” a Pesos 
Colombianos. 
1.0 /NominaIndividual/Inform
acionGeneral/@TRM 
NIE031 N Notas Información adicional: Texto 
libre, relativo al documento 
Utilizado para agregar Notas al 
documento 1.0 /NominaIndividual/Notas 
NIE032 R RazonSocial Debe ir el Nombre o Razón 
Social del Empleador 
Debe ir el Nombre o Razón 
Social del Empleador 1.0 /NominaIndividual/Emple
ador/@RazonSocial 
NIE210 R PrimerApellido Debe ir el Primer Apellido del 
Empleador 
Debe ir el Primer Apellido del 
Empleador 1.0 /NominaIndividual/Emple
ador/@PrimerApellido 
NIE211 R SegundoApellido Debe ir el Segundo Apellido del 
Empleador 
Debe ir el Segundo Apellido del 
Empleador 1.0 /NominaIndividual/Emple
ador/@SegundoApellido 

---

## Página 187

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 187 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE212 R PrimerNombre Debe ir el Primer Nombre del 
Empleador 
Debe ir el Primer Nombre del 
Empleador 1.0 /NominaIndividual/Emple
ador/@PrimerNombre 
NIE213 N OtrosNombres Deben ir los Otros Nombres del 
Empleador 
Deben ir los Otros Nombres del 
Empleador 1.0 /NominaIndividual/Emple
ador/@OtrosNombres 
NIE033 R NIT Debe ir el NIT del Empleador sin 
guiones ni DV 
Debe ir el NIT del Empleador sin 
guiones ni DV 1.0 /NominaIndividual/Emple
ador/@NIT 
NIE034 R DV Debe ir el DV del Empleador Debe ir el DV del Empleador 1.0 /NominaIndividual/Emple
ador/@DV 
NIE035 R Pais Se debe colocar el Codigo alfa-2 
de la tabla 5.4.1 
Se debe colocar el Codigo alfa-2 
correspondiente 1.0 /NominaIndividual/Emple
ador/@Pais 
NIE036 R DepartamentoEstad
o 
Se debe colocar el Codigo de la 
tabla 5.4.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividual/Emple
ador/@DepartamentoEsta
do 
NIE037 R MunicipioCiudad Se debe colocar el Codigo de la 
tabla 5.4.3 
Se debe colocar el Codigo 
correspondiente 1.0 /NominaIndividual/Emple
ador/@MunicipioCiudad 
NIE038 R Direccion Debe ir la Dirección Fisica del 
Empleador 
Debe ir la Dirección Fisica del 
Empleador 1.0 /NominaIndividual/Emple
ador/@Direccion 
NIE041 R TipoTrabajador 
Corresponde a la clasificación 
de PILA para conocer en que 
calidad se realizan las 
cotizaciones a la seguridad 
social. Se debe colocar el Codigo 
de la tabla 5.5.3 
Se debe colocar el Codigo 
correspondiente 1.0 /NominaIndividual/Trabaj
ador/@TipoTrabajador 
NIE042 R SubTipoTrabajador 
Corresponde a una sub 
clasificación de PILA para 
conocer en que calidad se 
realizan las cotizaciones a la 
seguridad social. Se debe 
colocar el Codigo de la tabla 
5.5.4 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividual/Trabaj
ador/@SubTipoTrabajado
r 
NIE043 R AltoRiesgoPension Se debe colocar "true" o "false" Se debe colocar "true" o "false" 1.0 /NominaIndividual/Trabaj
ador/@AltoRiesgoPension 
NIE044 R TipoDocumento Se debe colocar el Codigo de la 
tabla 5.2.1 
Se debe colocar el Codigo 
correspondiente 1.0 /NominaIndividual/Trabaj
ador/@TipoDocumento 
NIE045 R NumeroDocumento 
Debe ir el Numero de 
documento del trabajador, sin 
puntos ni comas ni espacios 
Debe ir el Numero de 
documento del trabajador, sin 
puntos ni comas ni espacios 
1.0 
/NominaIndividual/Trabaj
ador/@NumeroDocument
o 

---

## Página 188

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 188 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE046 R PrimerApellido Debe ir el Primer Apellido del 
trabajador 
Debe ir el Primer Apellido del 
trabajador 1.0 /NominaIndividual/Trabaj
ador/@PrimerApellido 
NIE047 R SegundoApellido Debe ir el Segundo Apellido del 
trabajador 
Debe ir el Segundo Apellido del 
trabajador 1.0 /NominaIndividual/Trabaj
ador/@SegundoApellido 
NIE048 R PrimerNombre Debe ir el Primer Nombre del 
trabajador 
Debe ir el Primer Nombre del 
trabajador 1.0 /NominaIndividual/Trabaj
ador/@PrimerNombre 
NIE049 N OtrosNombres Deben ir los Otros Nombres del 
trabajador 
Deben ir los Otros Nombres del 
trabajador 1.0 /NominaIndividual/Trabaj
ador/@OtrosNombres 
NIE050 R LugarTrabajoPais Se debe colocar el Codigo alfa-2 
de la tabla 5.4.1 
Se debe colocar el Codigo alfa-2 
correspondiente 1.0 /NominaIndividual/Trabaj
ador/@LugarTrabajoPais 
NIE051 R LugarTrabajoDepart
amentoEstado 
Se debe colocar el Codigo de la 
tabla 5.4.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividual/Trabaj
ador/@LugarTrabajoDepa
rtamentoEstado 
NIE052 R LugarTrabajoMunici
pioCiudad 
Se debe colocar el Codigo de la 
tabla 5.4.3 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividual/Trabaj
ador/@LugarTrabajoMuni
cipioCiudad 
NIE053 R LugarTrabajoDirecci
on 
Debe ir la Dirección Fisica del 
Trabajador 
Debe ir la Dirección Fisica del 
Trabajador 1.0 
/NominaIndividual/Trabaj
ador/@LugarTrabajoDirec
cion 
NIE056 R SalarioIntegral Se debe colocar "true" o "false" Se debe colocar "true" o "false" 1.0 /NominaIndividual/Trabaj
ador/@SalarioIntegral 
NIE061 R TipoContrato Se debe colocar el Codigo de la 
tabla 5.5.2 
Se debe colocar el Codigo 
correspondiente 1.0 /NominaIndividual/Trabaj
ador/@TipoContrato 
NIE062 R Sueldo 
Se debe colocar el Sueldo Base 
que el Trabajdor tiene en la 
empresa 
Se debe colocar el Sueldo Base 
que el Trabajdor tiene en la 
empresa 
1.0 /NominaIndividual/Trabaj
ador/@Sueldo 
NIE063 N CodigoTrabajador Campo Opcional queda a 
manejo Interno del Empleador. 
Se debe indicar el Codigo del 
Trabajador. 1.0 /NominaIndividual/Trabaj
ador/@CodigoTrabajador 
NIE064 R Forma Se debe colocar el Codigo de la 
tabla 5.3.3.1 
Se debe colocar el Codigo 
correspondiente 1.0 /NominaIndividual/Pago/
@Forma 
NIE065 R Metodo Se debe colocar el Codigo de la 
tabla 5.3.3.2 
Se debe colocar el Codigo 
correspondiente 1.0 /NominaIndividual/Pago/
@Metodo 
NIE066 N Banco 
Se debe colocar el nombre de la 
entidad bancaria donde el 
trabajador tiene su cuenta para 
pago de nómina 
Se debe colocar el nombre de la 
entidad bancaria donde el 
trabajador tiene su cuenta para 
pago de nómina 
1.0 /NominaIndividual/Pago/
@Banco 

---

## Página 189

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 189 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE067 N TipoCuenta 
Se debe colocar el tipo de 
cuenta que el trabajador tiene 
para pago de nómina 
Se debe colocar el tipo de 
cuenta que el trabajador tiene 
para pago de nómina 
1.0 /NominaIndividual/Pago/
@TipoCuenta 
NIE068 N NumeroCuenta 
Se debe colocar el número de la 
cuenta que el trabajador tiene 
para pago de nómina 
Se debe colocar el número de la 
cuenta que el trabajador tiene 
para pago de nómina 
1.0 /NominaIndividual/Pago/
@NumeroCuenta 
NIE203 R FechaPago 
Debe ir la fecha de Pago del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
Debe ir la fecha de Pago del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
1.0 /NominaIndividual/Fechas
Pagos/FechaPago 
NIE069 R DiasTrabajados Cantidad de dias laborados 
durante el Periodo de Pago 
Se debe colocar la Cantidad de 
dias laborados durante el 
Periodo de Pago 
1.0 
/NominaIndividual/Deven
gados/Basico/@DiasTraba
jados 
NIE070 R SueldoTrabajado 
Valor Base o Sueldo del 
trabajador por los días 
laborados. 
Se debe colocar el Sueldo 
Trabajado por los días 
laborados. 
1.0 
/NominaIndividual/Deven
gados/Basico/@SueldoTra
bajado 
NIE071 R AuxilioTransporte 
Valor de Auxilio de Transporte 
que recibe el trabajador por ley, 
según aplique 
Se debe colocar el Valor de 
Auxilio de Transporte que recibe 
el trabajador por ley, según 
aplique 
1.0 
/NominaIndividual/Deven
gados/Transporte/@Auxili
oTransporte 
NIE072 R ViaticoManuAlojS 
Valor de Viaticos, Manutención 
y Alojamiento de carácter 
Salarial 
Se debe colocar el Valor de 
Viaticos, Manutención y 
Alojamiento de carácter Salarial 
1.0 
/NominaIndividual/Deven
gados/Transporte/@Viatic
oManuAlojS 
NIE073 R ViaticoManuAlojNS 
Valor de Viaticos, Manutención 
y Alojamiento de carácter No 
Salarial 
Se debe colocar el Valor de 
Viaticos, Manutención y 
Alojamiento de carácter No 
Salarial 
1.0 
/NominaIndividual/Deven
gados/Transporte/@Viatic
oManuAlojNS 
NIE074 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HEDs/HED/@HoraI
nicio 
NIE075 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HEDs/HED/@HoraF
in 
NIE076 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividual/Deven
gados/HEDs/HED/@Canti
dad 
NIE077 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividual/Deven
gados/HEDs/HED/@Porce
ntaje 

---

## Página 190

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 190 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE078 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 /NominaIndividual/Deven
gados/HEDs/HED/@Pago 
NIE079 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HENs/HEN/@HoraI
nicio 
NIE080 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HENs/HEN/@HoraF
in 
NIE081 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividual/Deven
gados/HENs/HEN/@Canti
dad 
NIE082 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividual/Deven
gados/HENs/HEN/@Porce
ntaje 
NIE083 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 /NominaIndividual/Deven
gados/HENs/HEN/@Pago 
NIE084 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRNs/HRN/@HoraI
nicio 
NIE085 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRNs/HRN/@Hora
Fin 
NIE086 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividual/Deven
gados/HRNs/HRN/@Canti
dad 
NIE087 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividual/Deven
gados/HRNs/HRN/@Porce
ntaje 
NIE088 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 /NominaIndividual/Deven
gados/HRNs/HRN/@Pago 
NIE089 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
HoraInicio 
NIE090 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
HoraFin 
NIE091 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
Cantidad 

---

## Página 191

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 191 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE092 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
Porcentaje 
NIE093 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividual/Deven
gados/HEDDFs/HEDDF/@
Pago 
NIE094 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
HoraInicio 
NIE095 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
HoraFin 
NIE096 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
Cantidad 
NIE097 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
Porcentaje 
NIE098 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividual/Deven
gados/HRDDFs/HRDDF/@
Pago 
NIE099 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
HoraInicio 
NIE100 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
HoraFin 
NIE101 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
Cantidad 
NIE102 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
Porcentaje 
NIE103 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividual/Deven
gados/HENDFs/HENDF/@
Pago 
NIE104 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
HoraInicio 

---

## Página 192

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 192 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE105 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
HoraFin 
NIE106 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
Cantidad 
NIE107 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
Porcentaje 
NIE108 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividual/Deven
gados/HRNDFs/HRNDF/@
Pago 
NIE109 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesComunes/@FechaInici
o 
NIE110 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesComunes/@FechaFin 
NIE111 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesComunes/@Cantidad 
NIE112 R Pago Valor Pagado por Vacaciones Si 
Disfrutadas 
Se debe colocar el Valor Pagado 
por Vacaciones Si Disfrutadas 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesComunes/@Pago 
NIE115 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesCompensadas/@Canti
dad 
NIE116 R Pago Valor Pagado por Vacaciones No 
Disfrutadas 
Se debe colocar el Valor Pagado 
por Vacaciones No Disfrutadas 1.0 
/NominaIndividual/Deven
gados/Vacaciones/Vacacio
nesCompensadas/@Pago 
NIE117 R Cantidad 
Cantidad de Dias a los cuales 
corresponde el pago de la Prima 
legal 
Se debe colocar la cantidad de 
Dias a los cuales corresponde el 
pago de la Prima legal 
1.0 /NominaIndividual/Deven
gados/Primas/@Cantidad 
NIE118 R Pago Valor Pagado por Prima Legal 
con respecto a Cantidad de Dias 
Se debe colocar el Valor Pagado 
por Prima Legal con respecto a 
Cantidad de Dias 
1.0 /NominaIndividual/Deven
gados/Primas/@Pago 
NIE119 R PagoNS Valor Pagado por Prima No 
Salarial 
Se debe colocar el Valor Pagado 
por Prima No Salarial 1.0 /NominaIndividual/Deven
gados/Primas/@PagoNS 

---

## Página 193

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 193 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE120 R Pago Valor Pagado por Cesantias Se debe colocar el Valor Pagado 
por Cesantias 1.0 /NominaIndividual/Deven
gados/Cesantias/@Pago 
NIE121 R Porcentaje Porcentaje de Interes de 
Cesantias 
Se debe colocar el Porcentaje 
de Interes de Cesantias 1.0 
/NominaIndividual/Deven
gados/Cesantias/@Porcen
taje 
NIE122 R PagoIntereses Valor Pagado por Intereses de 
Cesantias 
Se debe colocar el Valor Pagado 
por Intereses de Cesantias 1.0 
/NominaIndividual/Deven
gados/Cesantias/@PagoIn
tereses 
NIE123 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@FechaInicio 
NIE124 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@FechaFin 
NIE125 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@Cantidad 
NIE126 R Tipo Se debe colocar el Codigo que 
corresponda de la tabla 5.5.6 
Se debe colocar el Codigo que 
corresponda 1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@Tipo 
NIE127 R Pago Valor Pagado por Incapacidad 
con respecto a Cantidad de Dias 
Se debe colocar el Valor Pagado 
por Incapacidad con respecto a 
Cantidad de Dias 
1.0 
/NominaIndividual/Deven
gados/Incapacidades/Inca
pacidad/@Pago 
NIE128 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/Licencia
MP/@FechaInicio 
NIE129 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/Licencia
MP/@FechaFin 
NIE130 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividual/Deven
gados/Licencias/Licencia
MP/@Cantidad 
NIE131 R Pago 
Valor Pagado por Licencia de 
Maternidad o Paternidad con 
respecto a Cantidad de Dias 
Se debe colocar el Valor Pagado 
por Licencia de Maternidad o 
Paternidad con respecto a 
Cantidad de Dias 
1.0 
/NominaIndividual/Deven
gados/Licencias/Licencia
MP/@Pago 
NIE132 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaR
/@FechaInicio 

---

## Página 194

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 194 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE133 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaR
/@FechaFin 
NIE134 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaR
/@Cantidad 
NIE135 R Pago 
Valor Pagado por Licencia 
Remunerada con respecto a 
Cantidad de Dias 
Se debe colocar el Valor Pagado 
por Licencia Remunerada con 
respecto a Cantidad de Dias 
1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaR
/@Pago 
NIE136 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaN
R/@FechaInicio 
NIE137 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaN
R/@FechaFin 
NIE138 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividual/Deven
gados/Licencias/LicenciaN
R/@Cantidad 
NIE139 R BonificacionS Valor Pagado por Bonificación 
Salarial 
Se debe colocar el Valor Pagado 
por Bonificación Salarial 1.0 
/NominaIndividual/Deven
gados/Bonificaciones/Boni
ficacion/@BonificacionS 
NIE140 R BonificacionNS Valor Pagado por Bonificación 
No Salarial 
Se debe colocar el Valor Pagado 
por Bonificación No Salarial 1.0 
/NominaIndividual/Deven
gados/Bonificaciones/Boni
ficacion/@BonificacionNS 
NIE141 R AuxilioS Valor Pagado por Auxilios 
Salariales 
Se debe colocar el Valor Pagado 
por Auxilios Salariales 1.0 
/NominaIndividual/Deven
gados/Auxilios/Auxilio/@A
uxilioS 
NIE142 R AuxilioNS Valor Pagado por Auxilios No 
Salariales 
Se debe colocar el Valor Pagado 
por Auxilios No Salariales 1.0 
/NominaIndividual/Deven
gados/Auxilios/Auxilio/@A
uxilioNS 
NIE143 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/HuelgasLegales/Hu
elgaLegal/@FechaInicio 
NIE144 R FechaFIn En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividual/Deven
gados/HuelgasLegales/Hu
elgaLegal/@FechaFIn 
NIE145 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividual/Deven
gados/HuelgasLegales/Hu
elgaLegal/@Cantidad 

---

## Página 195

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 195 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE146 R DescripcionConcept
o 
Debe ir la Descripcion del 
Concepto 
Debe ir la Descripcion del 
Concepto 1.0 
/NominaIndividual/Deven
gados/OtroConceptos/Otr
oConcepto/@Descripcion
Concepto 
NIE147 R ConceptoS Valor Pagado por Conceptos 
Salariales 
Se debe colocar el Valor Pagado 
por Conceptos Salariales 1.0 
/NominaIndividual/Deven
gados/OtroConceptos/Otr
oConcepto/@ConceptoS 
NIE148 R ConceptoNS Valor Pagado por Conceptos No 
Salariales 
Se debe colocar el Valor Pagado 
por Conceptos No Salariales 1.0 
/NominaIndividual/Deven
gados/OtroConceptos/Otr
oConcepto/@ConceptoNS 
NIE149 R CompensacionO Valor Pagado por 
Compensaciones Ordinarias 
Se debe colocar el Valor Pagado 
por Compensaciones Ordinarias 1.0 
/NominaIndividual/Deven
gados/Compensaciones/C
ompensacion/@Compens
acionO 
NIE150 R CompensacionE 
Valor Pagado por 
Compensaciones 
Extraordinarias 
Se debe colocar el Valor Pagado 
por Compensaciones 
Extraordinarias 
1.0 
/NominaIndividual/Deven
gados/Compensaciones/C
ompensacion/@Compens
acionE 
NIE151 R PagoS Concepto Salarial Se debe colocar el Concepto 
Salarial 1.0 
/NominaIndividual/Deven
gados/BonoEPCTVs/Bono
EPCTV/@PagoS 
NIE152 R PagoNS Concepto No Salarial Se debe colocar el Concepto No 
Salarial 1.0 
/NominaIndividual/Deven
gados/BonoEPCTVs/Bono
EPCTV/@PagoNS 
NIE153 R PagoAlimentacionS Concepto Salarial Se debe colocar el Concepto 
Salarial 1.0 
/NominaIndividual/Deven
gados/BonoEPCTVs/Bono
EPCTV/@PagoAlimentacio
nS 
NIE154 R PagoAlimentacionN
S Concepto No Salarial Se debe colocar el Concepto No 
Salarial 1.0 
/NominaIndividual/Deven
gados/BonoEPCTVs/Bono
EPCTV/@PagoAlimentacio
nNS 
NIE155 R Comision Valor Pagado por Comision Se debe colocar el Valor Pagado 
por Comision 1.0 
/NominaIndividual/Deven
gados/Comisiones/Comisi
on 
NIE193 R PagoTercero Valor Pagado por Pago Tercero Se debe colocar el Valor Pagado 
por Pago Tercero 1.0 
/NominaIndividual/Deven
gados/PagosTerceros/Pag
oTercero 
NIE194 R Anticipo Valor Pagado por Anticipo Se debe colocar el Valor Pagado 
por Anticipo 1.0 /NominaIndividual/Deven
gados/Anticipos/Anticipo 

---

## Página 196

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 196 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE156 R Dotacion Valor Pagado por Dotación Se debe colocar el Valor Pagado 
por Dotación 1.0 /NominaIndividual/Deven
gados/Dotacion 
NIE157 R ApoyoSost Valor Pagado por Apoyo a 
Sostenimiento 
Se debe colocar el Valor Pagado 
por Apoyo a Sostenimiento 1.0 /NominaIndividual/Deven
gados/ApoyoSost 
NIE158 R Teletrabajo Valor Pagado por trabajo en 
Teletrabajo 
Se debe colocar el Valor Pagado 
por trabajo en Teletrabajo 1.0 /NominaIndividual/Deven
gados/Teletrabajo 
NIE159 R BonifRetiro Valor Pagado por Retiro de la 
empresa 
Se debe colocar el Valor Pagado 
por Retiro de la empresa 1.0 /NominaIndividual/Deven
gados/BonifRetiro 
NIE160 R Indemnizacion Valor Pagado por Indemnización Se debe colocar el Valor Pagado 
por Indemnización 1.0 /NominaIndividual/Deven
gados/Indemnizacion 
NIE201 R Reintegro 
Valor Pagado correspondiente a 
Reintegro por parte del 
empleador 
Se debe colocar el Valor Pagado 
correspondiente a Reintegro 
por parte del empleador 
1.0 /NominaIndividual/Deven
gados/Reintegro 
NIE161 R Porcentaje Se debe colocar el Porcentaje 
que corresponda 
Se debe colocar el Porcentaje 
que corresponda 1.0 /NominaIndividual/Deduc
ciones/Salud/@Porcentaje 
NIE163 R Deduccion Valor Pagado correspondiente a 
Salud por parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Salud por 
parte del trabajador 
1.0 /NominaIndividual/Deduc
ciones/Salud/@Deduccion 
NIE164 R Porcentaje Se debe colocar el Porcentaje 
que corresponda 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividual/Deduc
ciones/FondoPension/@P
orcentaje 
NIE166 R Deduccion 
Valor Pagado correspondiente a 
Pension por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Pension por 
parte del trabajador 
1.0 
/NominaIndividual/Deduc
ciones/FondoPension/@D
educcion 
NIE167 R Porcentaje Se debe colocar el Porcentaje 
que corresponda 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividual/Deduc
ciones/FondoSP/@Porcen
taje 
NIE168 R DeduccionSP 
Valor Pagado correspondiente a 
Fondo de Solidaridad Pensional 
por parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Fondo de 
Solidaridad Pensional por parte 
del trabajador 
1.0 
/NominaIndividual/Deduc
ciones/FondoSP/@Deducc
ionSP 
NIE169 R PorcentajeSub 
Se debe colocar el Porcentaje 
que correspondiente al Fondo 
de Subsistencia correspondiente 
Se debe colocar el Porcentaje 
que correspondiente al Fondo 
de Subsistencia correspondiente 
1.0 
/NominaIndividual/Deduc
ciones/FondoSP/@Porcen
tajeSub 
NIE170 R DeduccionSub 
Valor Pagado correspondiente a 
Fondo de Subsistencia por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Fondo de 
Subsistencia por parte del 
trabajador 
1.0 
/NominaIndividual/Deduc
ciones/FondoSP/@Deducc
ionSub 

---

## Página 197

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 197 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE171 R Porcentaje 
Se debe colocar el Porcentaje 
que correspondiente a Aportes 
del Sindicato correspondiente 
Se debe colocar el Porcentaje 
que correspondiente a Aportes 
del Sindicato correspondiente 
1.0 
/NominaIndividual/Deduc
ciones/Sindicatos/Sindicat
o/@Porcentaje 
NIE172 R Deduccion 
Valor Pagado correspondiente a 
Aportes del Sindicato por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Aportes del 
Sindicato por parte del 
trabajador 
1.0 
/NominaIndividual/Deduc
ciones/Sindicatos/Sindicat
o/@Deduccion 
NIE173 R SancionPublic 
Valor Pagado correspondiente a 
Sanción Pública por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Sanción 
Pública por parte del trabajador 
1.0 
/NominaIndividual/Deduc
ciones/Sanciones/Sancion
/@SancionPublic 
NIE174 R SancionPriv 
Valor Pagado correspondiente a 
Sanción Privada por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Sanción 
Privada por parte del trabajador 
1.0 
/NominaIndividual/Deduc
ciones/Sanciones/Sancion
/@SancionPriv 
NIE175 R Descripcion Debe ir la Descripcion de la 
Libranza 
Debe ir la Descripcion de la 
Libranza 1.0 
/NominaIndividual/Deduc
ciones/Libranzas/Libranza
/@Descripcion 
NIE176 R Deduccion 
Valor Pagado correspondiente a 
Aportes a Entidades Financieras 
por parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Aportes a 
Entidades Financieras por parte 
del trabajador 
1.0 
/NominaIndividual/Deduc
ciones/Libranzas/Libranza
/@Deduccion 
NIE195 R PagoTercero Valor Pagado por Pago Tercero Se debe colocar el Valor Pagado 
por Pago Tercero 1.0 
/NominaIndividual/Deduc
ciones/PagosTerceros/Pag
oTercero 
NIE196 R Anticipo Valor Pagado por Anticipo Se debe colocar el Valor Pagado 
por Anticipo 1.0 /NominaIndividual/Deduc
ciones/Anticipos/Anticipo 
NIE197 R OtraDeduccion Valor Pagado por Otra 
Deducción 
Se debe colocar el Valor Pagado 
por Otra Deducción 1.0 
/NominaIndividual/Deduc
ciones/OtrasDeducciones/
OtraDeduccion 
NIE198 R PensionVoluntaria 
Valor Pagado correspondiente 
al ahorro que hace el trabajador 
para complementar su pension 
obligatoria o cumplir metas 
especificas. 
Se debe colocar el Valor Pagado 
correspondiente al ahorro que 
hace el trabajador para 
complementar su pension 
obligatoria o cumplir metas 
especificas. 
1.0 /NominaIndividual/Deduc
ciones/PensionVoluntaria 
NIE177 R RetencionFuente 
Valor Pagado correspondiente a 
Retención en la Fuente por 
parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Retención en 
la Fuente por parte del 
trabajador 
1.0 /NominaIndividual/Deduc
ciones/RetencionFuente 
NIE179 R AFC Valor Pagado correspondiente a 
AFC por parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a AFC por 
parte del trabajador 
1.0 /NominaIndividual/Deduc
ciones/AFC 

---

## Página 198

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 198 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIE180 R Cooperativa 
Valor Pagado correspondiente a 
Cooperativas por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Cooperativas 
por parte del trabajador 
1.0 /NominaIndividual/Deduc
ciones/Cooperativa 
NIE181 R EmbargoFiscal 
Valor Pagado correspondiente 
aEmbargos Fiscales por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente aEmbargos 
Fiscales por parte del trabajador 
1.0 /NominaIndividual/Deduc
ciones/EmbargoFiscal 
NIE182 R PlanComplementari
os 
Valor Pagado correspondiente a 
Planes Complementarios por 
parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Planes 
Complementarios por parte del 
trabajador 
1.0 
/NominaIndividual/Deduc
ciones/PlanComplementar
ios 
NIE183 R Educacion 
Valor Pagado correspondiente a 
Conceptos Educativos por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Conceptos 
Educativos por parte del 
trabajador 
1.0 /NominaIndividual/Deduc
ciones/Educacion 
NIE184 R Reintegro 
Valor Pagado correspondiente a 
Reintegro por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Reintegro 
por parte del trabajador 
1.0 /NominaIndividual/Deduc
ciones/Reintegro 
NIE185 R Deuda 
Valor Pagado correspondiente a 
Deuda con la Empresa por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Deuda con la 
Empresa por parte del 
trabajador 
1.0 /NominaIndividual/Deduc
ciones/Deuda 
NIE186 R Redondeo Definido en el numeral 1.1.1 Se debe indicar el Redondeo 
según la definición establecida. 1.0 /NominaIndividual/Redon
deo 
NIE187 R DevengadosTotal Debe ir el valor Total de Todos 
los Devengados del Trabajador 
Debe ir el valor Total de Todos 
los Devengados del Trabajador 1.0 /NominaIndividual/Deven
gadosTotal 
NIE188 R DeduccionesTotal Debe ir el valor Total de Todos 
las Deducciones del Trabajador 
Debe ir el valor Total de Todos 
las Deducciones del Trabajador 1.0 /NominaIndividual/Deduc
cionesTotal 
NIE189 R ComprobanteTotal 
Debe ser la Diferencia entre 
DevengadosTotal - 
DeduccionesTotal 
Debe ser la Diferencia entre 
DevengadosTotal - 
DeduccionesTotal 
1.0 /NominaIndividual/Compr
obanteTotal 
 
 
6.1.2. Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica: NominaIndividualDeAjuste. 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE901 R - 
El documento debe poseer 
Todos los Namespace 
correspondientes a su 
estructura. 
El documento debe poseer 
Todos los Namespace 
correspondientes a su 
estructura. 
1.0 /NominaIndividualDeAjust
e/ 

---

## Página 199

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 199 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE001 R UBLExtensions 
Solamente puede haber una 
ocurrencia de un grupo 
UBLExtensions conteniendo el 
grupo ds:Signature. Ver 
definición en numeral 3.6 
Solamente puede haber una 
ocurrencia de un grupo 
UBLExtensions conteniendo el 
grupo ds:Signature. 
1.0 /NominaIndividualDeAjust
e/ext:UBLExtensions 
NIAE214 R TipoNota Se debe colocar el Codigo de la 
tabla 5.5.8 
Se debe colocar el Codigo 
correspondiente 1.0 /NominaIndividualDeAjust
e/Reemplazar 
NIAE190 N NumeroPred Debe ir el Numero de 
documento a Reemplazar 
Debe ir el Numero de 
documento a Reemplazar 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Reemplaza
ndoPredecesor/@Numero
Pred 
NIAE191 N CUNEPred Debe ir el CUNE del documento 
a Reemplazar 
Debe ir el CUNE del documento 
a Reemplazar 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Reemplaza
ndoPredecesor/@CUNEPr
ed 
NIAE191a N CUNEPred Debe ir el CUNE del documento 
a Reemplazar 
Documento a Reemplazar no se 
encuentra recibido en la Base 
de Datos. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Reemplaza
ndoPredecesor/@CUNEPr
ed 
NIAE192 N FechaGenPred 
Debe ir la fecha del documento 
a Reemplazar, en formato 
AAAA-MM-DD 
Debe ir la fecha del documento 
a Reemplazar, en formato 
AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Reemplaza
ndoPredecesor/@FechaG
enPred 
NIAE002 R FechaIngreso 
Se debe indicar la Fecha de 
Ingreso del trabajador a la 
empresa, en formato AAAA-
MM-DD 
Se debe indicar la Fecha de 
Ingreso del trabajador a la 
empresa, en formato AAAA-
MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaIngreso 
NIAE003 R FechaRetiro 
Se debe indicar la Fecha de 
Retiro del trabajador a la 
empresa, en formato AAAA-
MM-DD 
Se debe indicar la Fecha de 
Retiro del trabajador a la 
empresa, en formato AAAA-
MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaRetiro 
NIAE004 R FechaLiquidacionIni
cio 
Se debe indicar la Fecha de 
Inicio del Periodo de Liquidación 
del documento, en formato 
AAAA-MM-DD 
Se debe indicar la Fecha de 
Inicio del Periodo de Liquidación 
del documento, en formato 
AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaLiquidacionInicio 
NIAE005 R FechaLiquidacionFin 
Se debe indicar la Fecha de Fin 
del Periodo de Liquidación del 
documento, en formato AAAA-
MM-DD 
Se debe indicar la Fecha de Fin 
del Periodo de Liquidación del 
documento, en formato AAAA-
MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaLiquidacionFin 

---

## Página 200

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 200 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE006 R TiempoLaborado Definido en el numeral 8.4.1, 
debe ser mayor o gual a 1. 
Se debe indicar el Tiempo 
laborado del trabajador según la 
definición establecida. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
TiempoLaborado 
NIAE008 R FechaGen 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Periodo/@
FechaGen 
NIAE009 N CodigoTrabajador Campo Opcional queda a 
manejo Interno del Empleador. 
Se debe indicar el Codigo del 
Trabajador. 1.0 
/NominaIndividualDeAjust
e/Reemplazar/NumeroSec
uenciaXML/@CodigoTrab
ajador 
NIAE010 R Prefijo 
Debe corresponder a un Prefijo 
elegido por el Emisor del 
documento 
Debe corresponder a un Prefijo 
elegido por el Emisor del 
documento 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/NumeroSec
uenciaXML/@Prefijo 
NIAE011 R Consecutivo 
Debe corresponder a un 
Consecutivo elegido por el 
Emisor del documento 
Debe corresponder a un 
Consecutivo elegido por el 
Emisor del documento 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/NumeroSec
uenciaXML/@Consecutivo 
NIAE012 R Numero 
No se permiten caracteres 
adicionales como espacios o 
guiones. Prefijo + Número 
consecutivo del documento 
No se permiten caracteres 
adicionales como espacios o 
guiones. Debe corresponder a 
Prefijo + Número consecutivo 
del documento 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/NumeroSec
uenciaXML/@Numero 
NIAE013 R Pais Se debe colocar el Codigo alfa-2 
de la tabla 5.4.1 
Se debe colocar el Codigo alfa-2 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/LugarGener
acionXML/@Pais 
NIAE014 R DepartamentoEstad
o 
Se debe colocar el Codigo de la 
tabla 5.4.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/LugarGener
acionXML/@Departament
oEstado 
NIAE015 R MunicipioCiudad Se debe colocar el Codigo de la 
tabla 5.4.3 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/LugarGener
acionXML/@MunicipioCiu
dad 
NIAE016 R Idioma 
Se debe colocar el Codigo ISO 
639-1 de la tabla 5.3.1. Para 
Colombia se debe colocar "es" 
(Español, Castellano) 
Se debe colocar el Codigo ISO 
639-1 correspondiente. Para 
Colombia se debe colocar "es" 
(Español, Castellano) 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/LugarGener
acionXML/@Idioma 
NIAE205 R RazonSocial 
Debe ir el Nombre o Razón 
Social del Proveedor de 
Soluciones Tecnológicas 
Debe ir el Nombre o Razón 
Social del Proveedor de 
Soluciones Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@RazonSocial 

---

## Página 201

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 201 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE206 R PrimerApellido 
Debe ir el Primer Apellido del 
Proveedor de Soluciones 
Tecnológicas 
Debe ir el Primer Apellido del 
Proveedor de Soluciones 
Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@PrimerApellido 
NIAE207 R SegundoApellido 
Debe ir el Segundo Apellido del 
Proveedor de Soluciones 
Tecnológicas 
Debe ir el Segundo Apellido del 
Proveedor de Soluciones 
Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@SegundoApellido 
NIAE208 R PrimerNombre 
Debe ir el Primer Nombre del 
Proveedor de Soluciones 
Tecnológicas 
Debe ir el Primer Nombre del 
Proveedor de Soluciones 
Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@PrimerNombre 
NIAE209 N OtrosNombres 
Deben ir los Otros Nombres del 
Proveedor de Soluciones 
Tecnológicas 
Deben ir los Otros Nombres del 
Proveedor de Soluciones 
Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@OtrosNombres 
NIAE017 R NIT 
Se debe colocar el NIT sin 
guiones ni DV de la empresa 
dueña del Software que genera 
el Documento, debe estar 
registrado en la DIAN 
Se debe colocar el NIT sin 
guiones ni DV de la empresa 
dueña del Software que genera 
el Documento, debe estar 
registrado en la DIAN 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@NIT 
NIAE018 R DV 
Se debe colocar el DV de la 
empresa dueña del Software 
que genera el Documento, debe 
estar registrado en la DIAN 
Se debe colocar el DV de la 
empresa dueña del Software 
que genera el Documento, debe 
estar registrado en la DIAN 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@DV 
NIAE019 R SoftwareID 
Identificador del software 
asignado cuando el software se 
activa en el Sistema de 
Documento Soporte de Pago de 
Nómina Electrónica, debe 
corresponder a un software 
autorizado para este Emisor 
Identificador del software 
asignado cuando el software se 
activa en el Sistema de 
Documento Soporte de Pago de 
Nómina Electrónica, debe 
corresponder a un software 
autorizado para este Emisor 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@SoftwareID 
NIAE020 R SoftwareSC Definido en el numeral 8.3 
Se debe indicar el Software 
Security Code según la 
definición establecida. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/ProveedorX
ML/@SoftwareSC 
NIAE021 R CodigoQR 
Debe corresponder a la 
siguiente URL “https://catalogo-
vpfe.dian.gov.co/document/sea
rchqr?documentkey=CUNE”  
donde la palabra CUNE debe ser 
reemplazada por el CUNE del 
documento electrónico 
Se debe indicar la información 
detallada del docuemnto según 
la definición establecida. 
1.0 /NominaIndividualDeAjust
e/Reemplazar/CodigoQR 

---

## Página 202

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 202 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE022 R Version 
Debe ir el literal: " V1.0: Nota 
de Ajuste de Documento 
Soporte de Pago de Nómina 
Electrónica " 
Debe ir el literal " V1.0: Nota de 
Ajuste de Documento Soporte 
de Pago de Nómina Electrónica 
" 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@Version 
NIAE023 R Ambiente Se debe colocar el Codigo de la 
tabla 5.1.1 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@Ambiente 
NIAE202 R TipoXML Se debe colocar el Codigo de la 
tabla 5.5.7 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@TipoXML 
NIAE024 R CUNE Definido en el numeral 8.1 Se debe indicar el CUNE según 
la definición establecida. 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@CUNE 
NIAE025 R EncripCUNE Debe ir la palabra "CUNE-
SHA384" 
Debe ir la palabra "CUNE-
SHA384" 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@EncripCUNE 
NIAE026 R FechaGen 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@FechaGen 
NIAE027 R HoraGen 
Debe ir la hora de emision del 
documento. Considerando zona 
horaria de Colombia (-5) 
Debe ir la hora de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato HH:MM:SSdhh:mm 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@HoraGen 
NIAE029 R PeriodoNomina Se debe colocar el Codigo de la 
tabla 5.5.1 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@PeriodoNomi
na 
NIAE030 R TipoMoneda 
Se debe colocar el Codigo de la 
tabla 5.3.2. Para Colombia se 
debe colocar "COP" 
Se debe colocar el Codigo 
correspondiente. Para Colombia 
se debe colocar "COP" 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@TipoMoneda 
NIAE200 R TRM 
Tasa Representativa del 
mercado. Corresponde a la tasa 
de cambio de la moneda 
utilizada en el documento en el 
Campo “TipoMoneda” a Pesos 
Colombianos. 
Se debe colocar la tasa de 
cambio de la moneda utilizada 
en el documento en el Campo 
“TipoMoneda” a Pesos 
Colombianos. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Informacio
nGeneral/@TRM 
NIAE031 N Notas Información adicional: Texto 
libre, relativo al documento 
Utilizado para agregar Notas al 
documento 1.0 /NominaIndividualDeAjust
e/Reemplazar/Notas 

---

## Página 203

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 203 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE032 R RazonSocial Debe ir el Nombre o Razón 
Social del Empleador 
Debe ir el Nombre o Razón 
Social del Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@RazonSocial 
NIAE210 R PrimerApellido Debe ir el Primer Apellido del 
Empleador 
Debe ir el Primer Apellido del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@PrimerApellido 
NIAE211 R SegundoApellido Debe ir el Segundo Apellido del 
Empleador 
Debe ir el Segundo Apellido del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@SegundoApellido 
NIAE212 R PrimerNombre Debe ir el Primer Nombre del 
Empleador 
Debe ir el Primer Nombre del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@PrimerNombre 
NIAE213 N OtrosNombres Deben ir los Otros Nombres del 
Empleador 
Deben ir los Otros Nombres del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@OtrosNombres 
NIAE033 R NIT Debe ir el NIT del Empleador sin 
guiones ni DV 
Debe ir el NIT del Empleador sin 
guiones ni DV 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@NIT 
NIAE034 R DV Debe ir el DV del Empleador Debe ir el DV del Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@DV 
NIAE035 R Pais Se debe colocar el Codigo alfa-2 
de la tabla 5.4.1 
Se debe colocar el Codigo alfa-2 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@Pais 
NIAE036 R DepartamentoEstad
o 
Se debe colocar el Codigo de la 
tabla 5.4.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@DepartamentoEstado 
NIAE037 R MunicipioCiudad Se debe colocar el Codigo de la 
tabla 5.4.3 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@MunicipioCiudad 
NIAE038 R Direccion Debe ir la Dirección Fisica del 
Empleador 
Debe ir la Dirección Fisica del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Empleador/
@Direccion 
NIAE041 R TipoTrabajador 
Corresponde a la clasificación 
de PILA para conocer en que 
calidad se realizan las 
cotizaciones a la seguridad 
social. Se debe colocar el Codigo 
de la tabla 5.5.3 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@TipoTrabajador 

---

## Página 204

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 204 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE042 R SubTipoTrabajador 
Corresponde a una sub 
clasificación de PILA para 
conocer en que calidad se 
realizan las cotizaciones a la 
seguridad social. Se debe 
colocar el Codigo de la tabla 
5.5.4 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@SubTipoTrabajador 
NIAE043 R AltoRiesgoPension Se debe colocar “true” o “false” Se debe colocar “true” o “false” 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@AltoRiesgoPension 
NIAE044 R TipoDocumento Se debe colocar el Codigo de la 
tabla 5.2.1 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@TipoDocumento 
NIAE045 R NumeroDocumento 
Debe ir el Numero de 
documento del trabajador, sin 
puntos ni comas ni espacios 
Debe ir el Numero de 
documento del trabajador, sin 
puntos ni comas ni espacios 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@NumeroDocumento 
NIAE046 R PrimerApellido Debe ir el Primer Apellido del 
trabajador 
Debe ir el Primer Apellido del 
trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@PrimerApellido 
NIAE047 R SegundoApellido Debe ir el Segundo Apellido del 
trabajador 
Debe ir el Segundo Apellido del 
trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@SegundoApellido 
NIAE048 R PrimerNombre Debe ir el Primer Nombre del 
trabajador 
Debe ir el Primer Nombre del 
trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@PrimerNombre 
NIAE049 N OtrosNombres Deben ir los Otros Nombres del 
trabajador 
Deben ir los Otros Nombres del 
trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@OtrosNombres 
NIAE050 R LugarTrabajoPais Se debe colocar el Codigo alfa-2 
de la tabla 5.4.1 
Se debe colocar el Codigo alfa-2 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@LugarTrabajoPais 
NIAE051 R LugarTrabajoDepart
amentoEstado 
Se debe colocar el Codigo de la 
tabla 5.4.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@LugarTrabajoDepartame
ntoEstado 
NIAE052 R LugarTrabajoMunici
pioCiudad 
Se debe colocar el Codigo de la 
tabla 5.4.3 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@LugarTrabajoMunicipioC
iudad 

---

## Página 205

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 205 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE053 R LugarTrabajoDirecci
on 
Debe ir la Dirección Fisica del 
Trabajador 
Debe ir la Dirección Fisica del 
Trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@LugarTrabajoDireccion 
NIAE056 R SalarioIntegral Se debe colocar “true” o “false” Se debe colocar “true” o “false” 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@SalarioIntegral 
NIAE061 R TipoContrato Se debe colocar el Codigo de la 
tabla 5.5.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@TipoContrato 
NIAE062 R Sueldo 
Se debe colocar el Sueldo Base 
que el Trabajdor tiene en la 
empresa 
Se debe colocar el Sueldo Base 
que el Trabajdor tiene en la 
empresa 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@Sueldo 
NIAE063 N CodigoTrabajador Campo Opcional queda a 
manejo Interno del Empleador. 
Se debe indicar el Codigo del 
Trabajador. 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Trabajador/
@CodigoTrabajador 
NIAE064 R Forma Se debe colocar el Codigo de la 
tabla 5.3.3.1 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@For
ma 
NIAE065 R Metodo Se debe colocar el Codigo de la 
tabla 5.3.3.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@Me
todo 
NIAE066 N Banco 
Se debe colocar el nombre de la 
entidad bancaria donde el 
trabajador tiene su cuenta para 
pago de nómina 
Se debe colocar el nombre de la 
entidad bancaria donde el 
trabajador tiene su cuenta para 
pago de nómina 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@Ban
co 
NIAE067 N TipoCuenta 
Se debe colocar el tipo de 
cuenta que el trabajador tiene 
para pago de nómina 
Se debe colocar el tipo de 
cuenta que el trabajador tiene 
para pago de nómina 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@Tip
oCuenta 
NIAE068 N NumeroCuenta 
Se debe colocar el número de la 
cuenta que el trabajador tiene 
para pago de nómina 
Se debe colocar el número de la 
cuenta que el trabajador tiene 
para pago de nómina 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Pago/@Nu
meroCuenta 
NIAE203 R FechaPago 
Debe ir la fecha de Pago del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
Debe ir la fecha de Pago del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/FechasPago
s/FechaPago 
NIAE069 R DiasTrabajados Cantidad de dias laborados 
durante el Periodo de Pago 
Se debe colocar la Cantidad de 
dias laborados durante el 
Periodo de Pago 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Basico/@DiasTrabajados 

---

## Página 206

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 206 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE070 R SueldoTrabajado 
Valor Base o Sueldo del 
trabajador por los días 
laborados. 
Se debe colocar el Sueldo 
Trabajado por los días 
laborados. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Basico/@SueldoTrabaja
do 
NIAE071 R AuxilioTransporte 
Valor de Auxilio de Transporte 
que recibe el trabajador por ley, 
según aplique 
Se debe colocar el Valor de 
Auxilio de Transporte que recibe 
el trabajador por ley, según 
aplique 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Transporte/@AuxilioTra
nsporte 
NIAE072 R ViaticoManuAlojS 
Valor de Viaticos, Manutención 
y Alojamiento de carácter 
Salarial 
Se debe colocar el Valor de 
Viaticos, Manutención y 
Alojamiento de carácter Salarial 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Transporte/@ViaticoMa
nuAlojS 
NIAE073 R ViaticoManuAlojNS 
Valor de Viaticos, Manutención 
y Alojamiento de carácter No 
Salarial 
Se debe colocar el Valor de 
Viaticos, Manutención y 
Alojamiento de carácter No 
Salarial 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Transporte/@ViaticoMa
nuAlojNS 
NIAE074 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@HoraInicio 
NIAE075 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@HoraFin 
NIAE076 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@Cantidad 
NIAE077 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@Porcentaje 
NIAE078 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDs/HED/@Pago 
NIAE079 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@HoraInicio 
NIAE080 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@HoraFin 
NIAE081 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@Cantidad 

---

## Página 207

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 207 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE082 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@Porcentaje 
NIAE083 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENs/HEN/@Pago 
NIAE084 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@HoraInicio 
NIAE085 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@HoraFin 
NIAE086 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@Cantidad 
NIAE087 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@Porcentaje 
NIAE088 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNs/HRN/@Pago 
NIAE089 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@HoraI
nicio 
NIAE090 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@Hora
Fin 
NIAE091 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@Canti
dad 
NIAE092 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@Porce
ntaje 
NIAE093 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HEDDFs/HEDDF/@Pago 

---

## Página 208

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 208 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE094 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@HoraI
nicio 
NIAE095 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@Hora
Fin 
NIAE096 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@Canti
dad 
NIAE097 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@Porce
ntaje 
NIAE098 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRDDFs/HRDDF/@Pago 
NIAE099 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@HoraI
nicio 
NIAE100 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@Hora
Fin 
NIAE101 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@Canti
dad 
NIAE102 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@Porce
ntaje 
NIAE103 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HENDFs/HENDF/@Pago 

---

## Página 209

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 209 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE104 R HoraInicio En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@HoraI
nicio 
NIAE105 R HoraFin En formato YYYY-MM-
DDTHH:MM:SS 
Se debe colocar en formato 
YYYY-MM-DDTHH:MM:SS 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@Hora
Fin 
NIAE106 R Cantidad Cantidad de Horas Se debe colocar la cantidad de 
Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@Canti
dad 
NIAE107 R Porcentaje 
Se debe colocar el Porcentaje 
que corresponda de la tabla 
5.5.5 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@Porc
entaje 
NIAE108 R Pago Valor Pagado por las Horas Se debe colocar el Valor Pagado 
por las Horas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HRNDFs/HRNDF/@Pago 
NIAE109 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
omunes/@FechaInicio 
NIAE110 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
omunes/@FechaFin 
NIAE111 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
omunes/@Cantidad 
NIAE112 R Pago Valor Pagado por Vacaciones Si 
Disfrutadas 
Se debe colocar el Valor Pagado 
por Vacaciones Si Disfrutadas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
omunes/@Pago 
NIAE115 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
ompensadas/@Cantidad 

---

## Página 210

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 210 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE116 R Pago Valor Pagado por Vacaciones No 
Disfrutadas 
Se debe colocar el Valor Pagado 
por Vacaciones No Disfrutadas 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Vacaciones/VacacionesC
ompensadas/@Pago 
NIAE117 R Cantidad 
Cantidad de Dias a los cuales 
corresponde el pago de la Prima 
legal 
Se debe colocar la cantidad de 
Dias a los cuales corresponde el 
pago de la Prima legal 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Primas/@Cantidad 
NIAE118 R Pago Valor Pagado por Prima Legal 
con respecto a Cantidad de Dias 
Se debe colocar el Valor Pagado 
por Prima Legal con respecto a 
Cantidad de Dias 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Primas/@Pago 
NIAE119 R PagoNS Valor Pagado por Prima No 
Salarial 
Se debe colocar el Valor Pagado 
por Prima No Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Primas/@PagoNS 
NIAE120 R Pago Valor Pagado por Cesantias Se debe colocar el Valor Pagado 
por Cesantias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Cesantias/@Pago 
NIAE121 R Porcentaje Porcentaje de Interes de 
Cesantias 
Se debe colocar el Porcentaje 
de Interes de Cesantias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Cesantias/@Porcentaje 
NIAE122 R PagoIntereses Valor Pagado por Intereses de 
Cesantias 
Se debe colocar el Valor Pagado 
por Intereses de Cesantias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Cesantias/@PagoInteres
es 
NIAE123 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@FechaInicio 
NIAE124 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@FechaFin 
NIAE125 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@Cantidad 
NIAE126 R Tipo Se debe colocar el Codigo que 
corresponda de la tabla 5.5.6 
Se debe colocar el Codigo que 
corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@Tipo 

---

## Página 211

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 211 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE127 R Pago Valor Pagado por Incapacidad 
con respecto a Cantidad de Dias 
Se debe colocar el Valor Pagado 
por Incapacidad con respecto a 
Cantidad de Dias 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Incapacidades/Incapacid
ad/@Pago 
NIAE128 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaMP/@
FechaInicio 
NIAE129 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaMP/@
FechaFin 
NIAE130 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaMP/@
Cantidad 
NIAE131 R Pago 
Valor Pagado por Licencia de 
Maternidad o Paternidad con 
respecto a Cantidad de Dias 
Se debe colocar el Valor Pagado 
por Licencia de Maternidad o 
Paternidad con respecto a 
Cantidad de Dias 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaMP/@
Pago 
NIAE132 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaR/@Fe
chaInicio 
NIAE133 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaR/@Fe
chaFin 
NIAE134 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaR/@Ca
ntidad 
NIAE135 R Pago 
Valor Pagado por Licencia 
Remunerada con respecto a 
Cantidad de Dias 
Se debe colocar el Valor Pagado 
por Licencia Remunerada con 
respecto a Cantidad de Dias 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaR/@Pa
go 
NIAE136 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaNR/@
FechaInicio 

---

## Página 212

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 212 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE137 R FechaFin En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaNR/@
FechaFin 
NIAE138 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Licencias/LicenciaNR/@
Cantidad 
NIAE139 R BonificacionS Valor Pagado por Bonificación 
Salarial 
Se debe colocar el Valor Pagado 
por Bonificación Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Bonificaciones/Bonificac
ion/@BonificacionS 
NIAE140 R BonificacionNS Valor Pagado por Bonificación 
No Salarial 
Se debe colocar el Valor Pagado 
por Bonificación No Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Bonificaciones/Bonificac
ion/@BonificacionNS 
NIAE141 R AuxilioS Valor Pagado por Auxilios 
Salariales 
Se debe colocar el Valor Pagado 
por Auxilios Salariales 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Auxilios/Auxilio/@Auxili
oS 
NIAE142 R AuxilioNS Valor Pagado por Auxilios No 
Salariales 
Se debe colocar el Valor Pagado 
por Auxilios No Salariales 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Auxilios/Auxilio/@Auxili
oNS 
NIAE143 R FechaInicio En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HuelgasLegales/HuelgaL
egal/@FechaInicio 
NIAE144 R FechaFIn En formato AAAA-MM-DD Se debe colocar en formato 
AAAA-MM-DD 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HuelgasLegales/HuelgaL
egal/@FechaFIn 
NIAE145 R Cantidad Cantidad de Dias Se debe colocar la cantidad de 
Dias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/HuelgasLegales/HuelgaL
egal/@Cantidad 
NIAE146 R DescripcionConcept
o 
Debe ir la Descripcion del 
Concepto 
Debe ir la Descripcion del 
Concepto 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/OtroConceptos/OtroCon
cepto/@DescripcionConc
epto 

---

## Página 213

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 213 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE147 R ConceptoS Valor Pagado por Conceptos 
Salariales 
Se debe colocar el Valor Pagado 
por Conceptos Salariales 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/OtroConceptos/OtroCon
cepto/@ConceptoS 
NIAE148 R ConceptoNS Valor Pagado por Conceptos No 
Salariales 
Se debe colocar el Valor Pagado 
por Conceptos No Salariales 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/OtroConceptos/OtroCon
cepto/@ConceptoNS 
NIAE149 R CompensacionO Valor Pagado por 
Compensaciones Ordinarias 
Se debe colocar el Valor Pagado 
por Compensaciones Ordinarias 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Compensaciones/Comp
ensacion/@Compensacio
nO 
NIAE150 R CompensacionE 
Valor Pagado por 
Compensaciones 
Extraordinarias 
Se debe colocar el Valor Pagado 
por Compensaciones 
Extraordinarias 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Compensaciones/Comp
ensacion/@Compensacio
nE 
NIAE151 R PagoS Concepto Salarial Se debe colocar el Concepto 
Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs/BonoEPCT
V/@PagoS 
NIAE152 R PagoNS Concepto No Salarial Se debe colocar el Concepto No 
Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs/BonoEPCT
V/@PagoNS 
NIAE153 R PagoAlimentacionS Concepto Salarial Se debe colocar el Concepto 
Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs/BonoEPCT
V/@PagoAlimentacionS 
NIAE154 R PagoAlimentacionN
S Concepto No Salarial Se debe colocar el Concepto No 
Salarial 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonoEPCTVs/BonoEPCT
V/@PagoAlimentacionNS 
NIAE155 R Comision Valor Pagado por Comision Se debe colocar el Valor Pagado 
por Comision 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Comisiones/Comision 
NIAE193 R PagoTercero Valor Pagado por Pago Tercero Se debe colocar el Valor Pagado 
por Pago Tercero 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/PagosTerceros/PagoTerc
ero 

---

## Página 214

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 214 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE194 R Anticipo Valor Pagado por Anticipo Se debe colocar el Valor Pagado 
por Anticipo 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Anticipos/Anticipo 
NIAE156 R Dotacion Valor Pagado por Dotación Se debe colocar el Valor Pagado 
por Dotación 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Dotacion 
NIAE157 R ApoyoSost Valor Pagado por Apoyo a 
Sostenimiento 
Se debe colocar el Valor Pagado 
por Apoyo a Sostenimiento 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/ApoyoSost 
NIAE158 R Teletrabajo Valor Pagado por trabajo en 
Teletrabajo 
Se debe colocar el Valor Pagado 
por trabajo en Teletrabajo 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Teletrabajo 
NIAE159 R BonifRetiro Valor Pagado por Retiro de la 
empresa 
Se debe colocar el Valor Pagado 
por Retiro de la empresa 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/BonifRetiro 
NIAE160 R Indemnizacion Valor Pagado por Indemnización Se debe colocar el Valor Pagado 
por Indemnización 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Indemnizacion 
NIAE201 R Reintegro 
Valor Pagado correspondiente a 
Reintegro por parte del 
empleador 
Se debe colocar el Valor Pagado 
correspondiente a Reintegro 
por parte del empleador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
s/Reintegro 
NIAE161 R Porcentaje Se debe colocar el Porcentaje 
que corresponda 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Salud/@Porcentaje 
NIAE163 R Deduccion Valor Pagado correspondiente a 
Salud por parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Salud por 
parte del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Salud/@Deduccion 
NIAE164 R Porcentaje Se debe colocar el Porcentaje 
que corresponda 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/FondoPension/@Porcen
taje 
NIAE166 R Deduccion 
Valor Pagado correspondiente a 
Pension por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Pension por 
parte del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/FondoPension/@Deducc
ion 
NIAE167 R Porcentaje Se debe colocar el Porcentaje 
que corresponda 
Se debe colocar el Porcentaje 
que corresponda 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/FondoSP/@Porcentaje 

---

## Página 215

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 215 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE168 R DeduccionSP 
Valor Pagado correspondiente a 
Fondo de Solidaridad Pensional 
por parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Fondo de 
Solidaridad Pensional por parte 
del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/FondoSP/@DeduccionS
P 
NIAE169 R PorcentajeSub 
Se debe colocar el Porcentaje 
que correspondiente al Fondo 
de Subsistencia correspondiente 
Se debe colocar el Porcentaje 
que correspondiente al Fondo 
de Subsistencia correspondiente 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/FondoSP/@PorcentajeS
ub 
NIAE170 R DeduccionSub 
Valor Pagado correspondiente a 
Fondo de Subsistencia por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Fondo de 
Subsistencia por parte del 
trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/FondoSP/@DeduccionS
ub 
NIAE171 R Porcentaje 
Se debe colocar el Porcentaje 
que correspondiente a Aportes 
del Sindicato correspondiente 
Se debe colocar el Porcentaje 
que correspondiente a Aportes 
del Sindicato correspondiente 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Sindicatos/Sindicato/@P
orcentaje 
NIAE172 R Deduccion 
Valor Pagado correspondiente a 
Aportes del Sindicato por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Aportes del 
Sindicato por parte del 
trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Sindicatos/Sindicato/@
Deduccion 
NIAE173 R SancionPublic 
Valor Pagado correspondiente a 
Sanción Pública por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Sanción 
Pública por parte del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Sanciones/Sancion/@Sa
ncionPublic 
NIAE174 R SancionPriv 
Valor Pagado correspondiente a 
Sanción Privada por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Sanción 
Privada por parte del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Sanciones/Sancion/@Sa
ncionPriv 
NIAE175 R Descripcion Debe ir la Descripcion de la 
Libranza 
Debe ir la Descripcion de la 
Libranza 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Libranzas/Libranza/@De
scripcion 
NIAE176 R Deduccion 
Valor Pagado correspondiente a 
Aportes a Entidades Financieras 
por parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Aportes a 
Entidades Financieras por parte 
del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Libranzas/Libranza/@De
duccion 
NIAE195 R PagoTercero Valor Pagado por Pago Tercero Se debe colocar el Valor Pagado 
por Pago Tercero 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/PagosTerceros/PagoTerc
ero 

---

## Página 216

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 216 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE196 R Anticipo Valor Pagado por Anticipo Se debe colocar el Valor Pagado 
por Anticipo 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Anticipos/Anticipo 
NIAE197 R OtraDeduccion Valor Pagado por Otra 
Deducción 
Se debe colocar el Valor Pagado 
por Otra Deducción 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/OtrasDeducciones/Otra
Deduccion 
NIAE198 R PensionVoluntaria 
Valor Pagado correspondiente 
al ahorro que hace el trabajador 
para complementar su pension 
obligatoria o cumplir metas 
especificas. 
Se debe colocar el Valor Pagado 
correspondiente al ahorro que 
hace el trabajador para 
complementar su pension 
obligatoria o cumplir metas 
especificas. 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/PensionVoluntaria 
NIAE177 R RetencionFuente 
Valor Pagado correspondiente a 
Retención en la Fuente por 
parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Retención en 
la Fuente por parte del 
trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/RetencionFuente 
NIAE179 R AFC Valor Pagado correspondiente a 
AFC por parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a AFC por 
parte del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/AFC 
NIAE180 R Cooperativa 
Valor Pagado correspondiente a 
Cooperativas por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Cooperativas 
por parte del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Cooperativa 
NIAE181 R EmbargoFiscal 
Valor Pagado correspondiente 
aEmbargos Fiscales por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente aEmbargos 
Fiscales por parte del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/EmbargoFiscal 
NIAE182 R PlanComplementari
os 
Valor Pagado correspondiente a 
Planes Complementarios por 
parte del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Planes 
Complementarios por parte del 
trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/PlanComplementarios 
NIAE183 R Educacion 
Valor Pagado correspondiente a 
Conceptos Educativos por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Conceptos 
Educativos por parte del 
trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Educacion 
NIAE184 R Reintegro 
Valor Pagado correspondiente a 
Reintegro por parte del 
trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Reintegro 
por parte del trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Reintegro 
NIAE185 R Deuda 
Valor Pagado correspondiente a 
Deuda con la Empresa por parte 
del trabajador 
Se debe colocar el Valor Pagado 
correspondiente a Deuda con la 
Empresa por parte del 
trabajador 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
s/Deuda 

---

## Página 217

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 217 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE186 R Redondeo Definido en el numeral 1.1.1 Se debe indicar el Redondeo 
según la definición establecida. 1.0 /NominaIndividualDeAjust
e/Reemplazar/Redondeo 
NIAE187 R DevengadosTotal Debe ir el valor Total de Todos 
los Devengados del Trabajador 
Debe ir el valor Total de Todos 
los Devengados del Trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Devengado
sTotal 
NIAE188 R DeduccionesTotal Debe ir el valor Total de Todos 
las Deducciones del Trabajador 
Debe ir el valor Total de Todos 
las Deducciones del Trabajador 1.0 
/NominaIndividualDeAjust
e/Reemplazar/Deduccione
sTotal 
NIAE189 R ComprobanteTotal 
Debe ser la Diferencia entre 
DevengadosTotal - 
DeduccionesTotal 
Debe ser la Diferencia entre 
DevengadosTotal - 
DeduccionesTotal 
1.0 
/NominaIndividualDeAjust
e/Reemplazar/Comproban
teTotal 
NIAE215 N NumeroPred Debe ir el Numero de 
documento a Reemplazar 
Debe ir el Numero de 
documento a Reemplazar 1.0 
/NominaIndividualDeAjust
e/Eliminar/EliminandoPre
decesor/@NumeroPred 
NIAE216 N CUNEPred Debe ir el CUNE del documento 
a Reemplazar 
Debe ir el CUNE del documento 
a Reemplazar 1.0 
/NominaIndividualDeAjust
e/Eliminar/EliminandoPre
decesor/@CUNEPred 
NIAE216a N CUNEPred Debe ir el CUNE del documento 
a Reemplazar 
Documento a Reemplazar no se 
encuentra recibido en la Base 
de Datos. 
1.0 
/NominaIndividualDeAjust
e/Eliminar/EliminandoPre
decesor/@CUNEPred 
NIAE217 N FechaGenPred 
Debe ir la fecha del documento 
a Reemplazar, en formato 
AAAA-MM-DD 
Debe ir la fecha del documento 
a Reemplazar, en formato 
AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Eliminar/EliminandoPre
decesor/@FechaGenPred 
NIAE218 R Prefijo 
Debe corresponder a un Prefijo 
elegido por el Emisor del 
documento 
Debe corresponder a un Prefijo 
elegido por el Emisor del 
documento 
1.0 
/NominaIndividualDeAjust
e/Eliminar/NumeroSecuen
ciaXML/@Prefijo 
NIAE219 R Consecutivo 
Debe corresponder a un 
Consecutivo elegido por el 
Emisor del documento 
Debe corresponder a un 
Consecutivo elegido por el 
Emisor del documento 
1.0 
/NominaIndividualDeAjust
e/Eliminar/NumeroSecuen
ciaXML/@Consecutivo 
NIAE220 R Numero 
No se permiten caracteres 
adicionales como espacios o 
guiones. Prefijo + Número 
consecutivo del documento 
No se permiten caracteres 
adicionales como espacios o 
guiones. Debe corresponder a 
Prefijo + Número consecutivo 
del documento 
1.0 
/NominaIndividualDeAjust
e/Eliminar/NumeroSecuen
ciaXML/@Numero 
NIAE221 R Pais Se debe colocar el Codigo alfa-2 
de la tabla 5.4.1 
Se debe colocar el Codigo alfa-2 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Eliminar/LugarGeneraci
onXML/@Pais 

---

## Página 218

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 218 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE222 R DepartamentoEstad
o 
Se debe colocar el Codigo de la 
tabla 5.4.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Eliminar/LugarGeneraci
onXML/@DepartamentoE
stado 
NIAE223 R MunicipioCiudad Se debe colocar el Codigo de la 
tabla 5.4.3 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Eliminar/LugarGeneraci
onXML/@MunicipioCiuda
d 
NIAE224 R Idioma 
Se debe colocar el Codigo ISO 
639-1 de la tabla 5.3.1. Para 
Colombia se debe colocar "es" 
(Español, Castellano) 
Se debe colocar el Codigo ISO 
639-1 correspondiente. Para 
Colombia se debe colocar "es" 
(Español, Castellano) 
1.0 
/NominaIndividualDeAjust
e/Eliminar/LugarGeneraci
onXML/@Idioma 
NIAE225 R RazonSocial 
Debe ir el Nombre o Razón 
Social del Proveedor de 
Soluciones Tecnológicas 
Debe ir el Nombre o Razón 
Social del Proveedor de 
Soluciones Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@RazonSocial 
NIAE226 R PrimerApellido 
Debe ir el Primer Apellido del 
Proveedor de Soluciones 
Tecnológicas 
Debe ir el Primer Apellido del 
Proveedor de Soluciones 
Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@PrimerApellido 
NIAE227 R SegundoApellido 
Debe ir el Segundo Apellido del 
Proveedor de Soluciones 
Tecnológicas 
Debe ir el Segundo Apellido del 
Proveedor de Soluciones 
Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@SegundoApellido 
NIAE228 R PrimerNombre 
Debe ir el Primer Nombre del 
Proveedor de Soluciones 
Tecnológicas 
Debe ir el Primer Nombre del 
Proveedor de Soluciones 
Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@PrimerNombre 
NIAE229 N OtrosNombres 
Deben ir los Otros Nombres del 
Proveedor de Soluciones 
Tecnológicas 
Deben ir los Otros Nombres del 
Proveedor de Soluciones 
Tecnológicas 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@OtrosNombres 
NIAE230 R NIT 
Se debe colocar el NIT sin 
guiones ni DV de la empresa 
dueña del Software que genera 
el Documento, debe estar 
registrado en la DIAN 
Se debe colocar el NIT sin 
guiones ni DV de la empresa 
dueña del Software que genera 
el Documento, debe estar 
registrado en la DIAN 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@NIT 
NIAE231 R DV 
Se debe colocar el DV de la 
empresa dueña del Software 
que genera el Documento, debe 
estar registrado en la DIAN 
Se debe colocar el DV de la 
empresa dueña del Software 
que genera el Documento, debe 
estar registrado en la DIAN 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@DV 

---

## Página 219

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 219 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE232 R SoftwareID 
Identificador del software 
asignado cuando el software se 
activa en el Sistema de 
Documento Soporte de Pago de 
Nómina Electrónica, debe 
corresponder a un software 
autorizado para este Emisor 
Identificador del software 
asignado cuando el software se 
activa en el Sistema de 
Documento Soporte de Pago de 
Nómina Electrónica, debe 
corresponder a un software 
autorizado para este Emisor 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@SoftwareID 
NIAE233 R SoftwareSC Definido en el numeral 8.3 
Se debe indicar el Software 
Security Code según la 
definición establecida. 
1.0 
/NominaIndividualDeAjust
e/Eliminar/ProveedorXML
/@SoftwareSC 
NIAE234 R CodigoQR 
Debe corresponder a la 
siguiente URL “https://catalogo-
vpfe.dian.gov.co/document/sea
rchqr?documentkey=CUNE”  
donde la palabra CUNE debe ser 
reemplazada por el CUNE del 
documento electrónico 
Se debe indicar la información 
detallada del docuemnto según 
la definición establecida. 
1.0 /NominaIndividualDeAjust
e/Eliminar/CodigoQR 
NIAE235 R Version 
Debe ir el literal: " V1.0: Nota 
de Ajuste de Documento 
Soporte de Pago de Nómina 
Electrónica " 
Debe ir el literal " V1.0: Nota de 
Ajuste de Documento Soporte 
de Pago de Nómina Electrónica 
" 
1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@Version 
NIAE236 R Ambiente Se debe colocar el Codigo de la 
tabla 5.1.1 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@Ambiente 
NIAE237 R TipoXML Se debe colocar el Codigo de la 
tabla 5.5.7 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@TipoXML 
NIAE238 R CUNE Definido en el numeral 8.1 Se debe indicar el CUNE según 
la definición establecida. 1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@CUNE 
NIAE239 R EncripCUNE Debe ir la palabra "CUNE-
SHA384" 
Debe ir la palabra "CUNE-
SHA384" 1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@EncripCUNE 
NIAE240 R FechaGen 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
Debe ir la fecha de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato AAAA-MM-DD 
1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@FechaGen 
NIAE241 R HoraGen 
Debe ir la hora de emision del 
documento. Considerando zona 
horaria de Colombia (-5) 
Debe ir la hora de emision del 
documento. Considerando zona 
horaria de Colombia (-5), en 
formato HH:MM:SSdhh:mm 
1.0 
/NominaIndividualDeAjust
e/Eliminar/InformacionGe
neral/@HoraGen 

---

## Página 220

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 220 de 269 
 
ID Y Campo Regla Mensaje V Xpath 
NIAE242 N Notas Información adicional: Texto 
libre, relativo al documento 
Utilizado para agregar Notas al 
documento 1.0 /NominaIndividualDeAjust
e/Eliminar/Notas 
NIAE243 R RazonSocial Debe ir el Nombre o Razón 
Social del Empleador 
Debe ir el Nombre o Razón 
Social del Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@R
azonSocial 
NIAE244 R PrimerApellido Debe ir el Primer Apellido del 
Empleador 
Debe ir el Primer Apellido del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@P
rimerApellido 
NIAE245 R SegundoApellido Debe ir el Segundo Apellido del 
Empleador 
Debe ir el Segundo Apellido del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@S
egundoApellido 
NIAE246 R PrimerNombre Debe ir el Primer Nombre del 
Empleador 
Debe ir el Primer Nombre del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@P
rimerNombre 
NIAE247 N OtrosNombres Deben ir los Otros Nombres del 
Empleador 
Deben ir los Otros Nombres del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
OtrosNombres 
NIAE248 R NIT Debe ir el NIT del Empleador sin 
guiones ni DV 
Debe ir el NIT del Empleador sin 
guiones ni DV 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
NIT 
NIAE249 R DV Debe ir el DV del Empleador Debe ir el DV del Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
DV 
NIAE250 R Pais Se debe colocar el Codigo alfa-2 
de la tabla 5.4.1 
Se debe colocar el Codigo alfa-2 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@P
ais 
NIAE251 R DepartamentoEstad
o 
Se debe colocar el Codigo de la 
tabla 5.4.2 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
DepartamentoEstado 
NIAE252 R MunicipioCiudad Se debe colocar el Codigo de la 
tabla 5.4.3 
Se debe colocar el Codigo 
correspondiente 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
MunicipioCiudad 
NIAE253 R Direccion Debe ir la Dirección Fisica del 
Empleador 
Debe ir la Dirección Fisica del 
Empleador 1.0 
/NominaIndividualDeAjust
e/Eliminar/Empleador/@
Direccion 
 
 
 

---

## Página 221

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 221 de 269 
 
6.1.3. Firma Digital del Documento: ds:Signature. 
ID Y Campo Regla Mensaje V Xpath 
DC01 R Signature 
Solamente puede haber una 
ocurrencia del Grupo 
Ext:ExtensionContent 
conteniendo información de la 
firma información.   
Más de un grupo  DIAN 
Extensión conteniendo 
información electrónica  
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature 
DC02 R SignedInfo Este grupo debe contener tres 
(3) grupos Reference 
El Grupo Reference no aparece 
tres veces. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo 
DC03 R Canonicalization 
Method 
Se verifica que el valor usado 
corresponde al establecido 
según 
http://www.w3.org/TR/2001/R
EC-xml-c14n-20010315. 
El valor usado en 
Canonicalization Method no 
corresponde al definido 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Canoni
calizationMethod 
DC04 R SignatureMethod El método debe ser SHA 256 o 
SHA 384 o SHA 512 
El método de firma utilizado no 
corresponde a la política de 
firma de la DIAN. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Signat
ureMethod 
DC05 R Reference 
Debe contener la información 
de la firma aplicada a todo el 
documento. 
La información suministrada 
no corresponde a la contendia 
en  URI=””  
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce 
DC06 R Transforms El grupo debe existir una vez El grupo NO existe una vez 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce/ds:Transforms 
DC07 R TransForm 
El contenido de la firma debe 
estar embebido en el 
documento. 
El valor del elemento debe ser 
igual a 
Algorithm=”http://www.w3.or
g/2000/09/xmldsig#enveloped
-signature” 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce/ds:Transforms/ds:Tr
ansForm 

---

## Página 222

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 222 de 269 
 
DC08 R DigestMethod 
El algoritmo reportado debe 
ser uno de los siguientes 
valores:  
 
RSAwithSHA256=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha256 
 
RSAwithSHA384=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha384 
 
RSAwithSHA512=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha512 
El valor reportado no 
corresponde a los definidos en 
la política de firma. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce/ds:DigestMethod 
DC09 R DigestValue 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod en 
base 64 debe corresponder. 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod no 
corresponde. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce/ds:DigestValue 
DC10 R Reference 
Debe contener la información 
correspondiente a la clave 
públic contenida en el 
elemento KeyInfo 
La información suministrada 
no corresponde a la contendia 
en  URI=”#{UUID}-KeyInfo”  
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce 
DC11 R DigestMethod 
El algoritmo reportado debe 
ser uno de los siguientes 
valores:  
 
RSAwithSHA256=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha256 
 
RSAwithSHA384=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha384 
 
RSAwithSHA512=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha512 
El valor reportado NO 
corresponde a los definidos en 
la política de firma 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce/ds:DigestMethod 
DC12 R DigestValue 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod en 
base 64 debe corresponder. 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod no 
corresponde. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce/ds:DigestValue 
DC13 R Reference 
Debe contener la información 
correspondiente al grupo 
SignedProperties. 
La información suministrada 
no corresponde a la contendia 
en  URI=”#xmldsig-{UUID}-
signedprops” 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature

---

## Página 223

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 223 de 269 
 
/ds:SignedInfo/ds:Refere
nce 
DC14 R DigestMethod 
El algoritmo reportado debe 
ser uno de los siguientes 
valores:  
 
RSAwithSHA256=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha256 
 
RSAwithSHA384=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha384 
 
RSAwithSHA512=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha512 
El valor reportado no 
corresponde a los definidos en 
la política de firma. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce/ds:DigestMethod 
DC15 R DigestValue 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod en 
base 64 debe corresponder. 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod no 
corresponde. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignedInfo/ds:Refere
nce/ds:DigestValue 
DC16 R SignatureValue 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en SignatureMethod 
en base 64 debe corresponder. 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en SignatureMethod 
NO corresponde. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:SignatureValue 
DC17 R KeyInfo El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:KeyInfo 
DC18 R X509Data El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:KeyInfo/ds:X509Data 
DC19 R X509Certificate Debe ser un certificado 
público. 
El certificado reportardo no es 
un certificado público válido. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:KeyInfo/ds:X509Data
/ds:X509Certificate 
DC20 R Object El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object 
DC21 R Qualifying 
Properties El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties 

---

## Página 224

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 224 de 269 
 
DC22 R SignedProperties El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties 
DC23 R SignedSignature 
Properties El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties 
DC24 R SigningTime 
El valor de la fecha debe venir 
en el formato definido en la 
política de firma y debe ser 
menor a la fecha del sistema. 
Error en el valor de la fecha y 
hora de firma. NO corresponde 
al formato y/o el valor 
reportado es superior a la 
fecha del sistema. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningTime 
DC25 R SigningCertificate 
El grupo debe existir una vez. 
Dentro de este grupo deben 
aparecer al menos tres grupos 
Cert diferentes. 
El grupo NO se reportó una vez 
ó el grupo Cert aparece menos 
de tres de veces. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate 
DC26 R Cert El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert 
DC27 R CertDigest El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:CertDiges
t 

---

## Página 225

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 225 de 269 
 
DC28 R DigestMethod 
El algoritmo reportado debe 
ser uno de los siguientes 
valores:  
 
RSAwithSHA256=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha256 
 
RSAwithSHA384=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha384 
 
RSAwithSHA512=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha512 
El valor reportado NO 
corresponde a los definidos en 
la política de firma 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:CertDiges
t/ds:DigestMethod 
DC29 R DigestValue 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod en 
base 64 debe corresponder. 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod 
NO corresponde. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:CertDiges
t/ds:DigestValue 
DC30 R IssuerSerial El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:IssuerSeri
al 
DC31 R X509IssuerName 
Debe ser igual al Subject que 
viene en el certificado público 
informado en X509Certificate 
El valor reportado NO 
corresponde con el valor 
informado en X509Certificate 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:IssuerSeri
al/ds:X509IssuerName 
DC32 R X509Serial Number 
Debe ser igual al Serial que 
viene en el certificado público 
informado en X509Certificate 
El valor reportado no 
corresponde con el valor 
informado en X509Certificate 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi

---

## Página 226

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 226 de 269 
 
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:IssuerSeri
al/ds:X509SerialNumber 
DC33 R Cert El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert 
DC34   CertDigest     1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:CertDiges
t 
DC35 R DigestMethod 
El algoritmo reportado debe 
ser uno de los siguientes 
valores:  
 
RSAwithSHA256=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha256 
 
RSAwithSHA384=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha384 
 
RSAwithSHA512=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha512 
El valor reportado NO 
corresponde a los definidos en 
la política de firma. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:CertDiges
t/ds:DigestMethod 
DC36   DigestValue 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod en 
base 64 debe corresponder. 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod 
NO corresponde. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa

---

## Página 227

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 227 de 269 
 
des:Cert/xades:CertDiges
t/ds:DigestValue 
DC37 R IssuerSerial 
El IssuerName y IssuerSerial 
deben pertenecer a una 
entidad subordinada 
certificadora abierta avalada 
por la ONAC en Colombia. 
El certificado NO pertenece a 
una de las Entidades 
certificadoras abiertas 
subordinadas avaladas por la 
ONAC en Colombia. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:IssuerSeri
al 
DC38 R X509IssuerName 
El IssuerName debe 
pertenecer a una entidad 
subordinada certificadora 
abierta avalada por la ONAC en 
Colombia.  
El valor no corresponde a una 
entidad subordinada 
certificadora abierta avalada 
por la ONAC en Colombia. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:IssuerSeri
al/ds:X509IssuerName 
DC39 R X509Serial Number 
El SerialNumber debe 
pertenecer a una entidad 
subordinada certificadora 
abierta avalada por la ONAC en 
Colombia.  
El valor no corresponde a una 
entidad subordinada 
certificadora abierta avalada 
por la ONAC en Colombia. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:IssuerSeri
al/ds:X509SerialNumber 
DC40 R Cert El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert 
DC41 R CertDigest El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa

---

## Página 228

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 228 de 269 
 
des:Cert/xades:CertDiges
t 
DC42 R DigestMethod 
El algoritmo reportado debe 
ser uno de los siguientes 
valores:  
 
RSAwithSHA256=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha256 
 
RSAwithSHA384=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha384 
 
RSAwithSHA512=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha512 
El valor reportado NO 
corresponde a los definidos en 
la política de firma. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:CertDiges
t/ds:DigestMethod 
DC43 R DigestValue 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod en 
base 64 debe corresponder. 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod 
NO corresponde. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:CertDiges
t/ds:DigestValue 
DC44 R IssuerSerial 
El IssuerName y IssuerSerial 
deben pertenecer a una 
entidad raíz certificadora 
abierta avalada por la ONAC en 
Colombia. 
El certificado NO pertenece a 
una de las Entidades 
certificadoras abiertas raíces 
avaladas por la ONAC en 
Colombia. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:IssuerSeri
al 
DC45 R X509IssuerName 
El IssuerName debe 
pertenecer a una entidad raíz 
certificadora abierta avalada 
por la ONAC en Colombia.  
El valor NO corresponde a una 
entidad raíz certificadora 
abierta avalada por la ONAC en 
Colombia. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:IssuerSeri
al/ds:X509IssuerName 

---

## Página 229

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 229 de 269 
 
DC46 R X509Serial Number 
El SerialNumber debe 
pertenecer a una entidad raíz 
certificadora abierta avalada 
por la ONAC en Colombia. 
El valor NO corresponde a una 
entidad raíz certificadora 
abierta avalada por la ONAC en 
Colombia. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SigningCertificate/xa
des:Cert/xades:IssuerSeri
al/ds:X509SerialNumber 
DC47 R SignaturePolicy 
Identifier El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignaturePolicyIdenti
fier 
DC48 R SignaturePolicyId El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignaturePolicyIdenti
fier/xades:SignaturePolic
yId 
DC49 R SigPolicyId El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignaturePolicyIdenti
fier/xades:SignaturePolic
yId/xades:SigPolicyId 
DC50 R Identifier Debe incluir el identificador 
definido por la DIAN. 
El identificador NO 
corresponde con el valor 
definido por la DIAN. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignaturePolicyIdenti
fier/xades:SignaturePolic

---

## Página 230

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 230 de 269 
 
yId/xades:SigPolicyId/xad
es:Identifier 
DC51 R SigPolicyHash El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignaturePolicyIdenti
fier/xades:SignaturePolic
yId/xades:SigPolicyHash 
DC52 R DigestMethod 
El algoritmo reportado debe 
ser uno de los siguientes 
valores:  
 
RSAwithSHA256=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha256 
 
RSAwithSHA384=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha384 
 
RSAwithSHA512=http://www.
w3.org/2001/04/xmldsig-
more#rsa-sha512 
El valor reportado NO 
corresponde a los definidos en 
la política de firma. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignaturePolicyIdenti
fier/xades:SignaturePolic
yId/xades:SigPolicyHash/
ds:DigestMethod 
DC53 R DigestValue 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod en 
base 64 debe corresponder. 
El valor de hash generado a 
partir del uso del algoritmo 
reportado en DigestMethod 
NO corresponde. 
1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignaturePolicyIdenti
fier/xades:SignaturePolic
yId/xades:SigPolicyHash/
ds:DigestValue 
DC54 R SignerRole El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignerRole 
DC55 R ClaimedRoles El grupo debe existir una vez. El grupo no se reportó una vez. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature

---

## Página 231

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 231 de 269 
 
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignerRole/xades:Cla
imedRoles 
DC56 R ClaimedRole El valor del rol debe ser 
thirdparty ó supplier. 
El valor NO contiene uno de los 
definidos. 1 
…//Ext:UBLExtensions/ex
t:UBLExtension/ext:Exten
sionContent/ds:Signature
/ds:Object/xades:Qualifyi
ngProperties/xades:Signe
dProperties/xades:Signe
dSignatureProperties/xa
des:SignerRole/xades:Cla
imedRoles/xades:Claime
dRole 
 
6.2. Reglas Relativas al Establecimiento de la Conexión. 
6.2.1. Mensaje del Web Service. 
# Regla Y Mensaje V 
ZA01 Verificar si el tamaño del archivo XML es superior a 500 KB R Tamaño del mensaje superior al límite establecido 
[Máximo: 500 KB] 1.0 
ZA02 Verificar si el servicio está parado momentáneamente N Servicio parado momentáneamente [corto plazo] 1.0 
ZA03 Verificar si el servicio está parado sin previsión N Servicio parado sin previsión 1.0 
 
6.2.2. Schema XML. 
# Regla Y Mensaje V 
ZB01 Verificar si el esquema XML está correcto R Fallo en el esquema XML del archivo 1.0 
ZB02 Verificar la existencia de caracteres de edición en el inicio o 
fin del mensaje o entre los tags R No es permitida la presencia de caracteres de edición en 
el inicio/fin o entre los tags del mensaje 1.0 
ZB03 Verificar si el XML utiliza la codificación diferente de UTF-8 R XML con codificación diferente de UTF-8 1.0 
ZB04 Verificar las personalizaciones de DIAN 
(Prefijos de NameSpace) R 
XML no cumple con las personalizaciones de XSD-
NóminaDIAN 
 
1.0 
 
6.2.3. Certificado Digital de Transmisión (conexión). 
# Regla Y Mensaje V 
ZC01 Verificar validez del Certificado Digital de transmisión R Certificado de la Transmisión vencido 1.0 
ZC02 
Error en acceso a la Lista de Certificados revocados (CRL) 
- Falta la dirección de la CRL (CRLDistributionPoint) 
- Error en el acceso a la CRL o CRL inexistente 
R Certificado Firma – Error en el acceso a la CRL 1.0 
ZC03 Verificar Lista de Certificados revocados (CRL)  R Certificado de Transmisión revocado 1.0 
 

---

## Página 232

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 232 de 269 
 
# Regla Y Mensaje V 
ZC04 
Verificar Cadena de Certificación: 
- Certificado de la AC emisora no registrado 
- Certificado de AC revocado 
- Certificado no asignado por la AC emisora del Certificado 
R Certificado de Transmisión – Error en la Cadena de 
Certificación 1.0 
ZC05 Verificar la cadena de confianza del certificado R La cadena de confianza No se pudo verificar o se 
encuentra revocada. 1.0 
ZC06 El certificado tiene que tener los atributos de conexión  R El certificado no contiene los atributos para realizar 
conexión de trasmisión. 1.0 
 
6.2.4. Certificado Digital de Firma (Firma XML). 
# Regla Y Mensaje V 
ZD01 Verificar si existe certificado de firma R Certificado de Firma inexistente en el  
archivo 1.0 
ZD02 Verificar data validez (data inicio y data fin) del Certificado 
Digital de la Firma R Certificado de la Firma con data de validez inválida 1.0 
ZD03 
Error en al acceso a la Lista de Certificados revocados (CRL) 
- Falta la dirección de la CRL (CRLDistributionPoint) 
- Error en el acceso a la CRL o CRL inexistente 
R Certificado de la Firma – Error en el acceso a la CRL 1.0 
ZD04 Verificar Lista de Certificados revocados (CRL) R Certificado de la Firma revocado 1.0 
ZD05 
Verificar Cadena de Certificación: 
- Certificado de la AC emisora no registrado 
- Certificado de AC revocado 
- Certificado no asignado pela AC emisora del Certificado 
R Certificado de la Firma – Error en la Cadena de 
Certificación 1.0 
ZD06 Verificar la cadena de confianza del certificado R La cadena de confianza no se puede verificar o se 
encuentra revocada. 1.0 
ZD07 El certificado tiene que tener los atributos de no repudio 
para firmar digitalmente R El certificado no contiene los atributos para realizar la 
firma digital con no repudio. 1.0 
 
6.2.5. Firma. 
# Regla Y Mensaje V 
ZE01 Verificar si la firma está en el estándar (XMLDSig con 
formato XAdES-EPES) R Certificado de la Firma con estándar inválido 1.0 
ZE02 Verificar si el valor de la Firma está válido (difiere del 
calculado) R Valor de la Firma inválido 1.0 
ZE03 Identificación (ID) del emisor difiere de la Identificación 
(propietario) del Certificado Digital R ID del emisor difiere del propietario del Certificado 
Digital 1.0 
 
Abreviaturas Utilizadas. 
CIAT .........................  Centro Interamericano de Administraciones Tributarias. 
CUNE .......................  Código Único de Documento Soporte de Pago de Nómina Electrónica. 
DE ............................  Documento Electrónico. 
DIAN ........................  Dirección de Impuestos y Aduanas Nacionales. 

---

## Página 233

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 233 de 269 
 
NE ............................  Nóminca Electrónica. 
NIT ...........................  Número de Identificación Tributaria. 
PA ............................  Proveedor, Proveedores Autorizado(s). 
XAdES ...................... XML Advanced Electronic Signature. 
XAdES-EPES ............. Forma básica a la que se la ha añadido información sobre la política de firma. 
XML .........................  eXtensible Markup Language. 
XPath .......................  XML Path Language. 
XSD ..........................  XML Schema Definition. 
XSL ...........................  eXtensible Stylesheet Language. 
XSLT .........................  XML Stylesheet Language for Transformations. 
 
 
 

---

## Página 234

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 234 de 269 
 
7. Política de firma. 
7.1. Observaciones. 
Todo documento electrónico enviado a la DIAN para validación deberá ser firmado con un certificado digital, 
expedido por una entidad de certificación digital Abierta autorizada por la Organización Nacional de Acreditación 
de Colombia (ONAC) para tal fin, cualquier docume nto electrónico firmado que no cumpla con esta condición, 
se entenderá invalido y no tendrá los efectos fiscales establecidos en el artículo 616 -1 del Estatuto Tributario y 
en la normativa vigente de factura electrónica..  
 
7.2. Consideraciones Generales. 
El objetivo de esta Política define las principales características técnicas para la firma digital, que garantizan la  
integridad, autenticidad y no repudio de todos los procesos que soporten la implementación del Documento 
Soporte de Pago de Nómina Electrónica en Colombia con fines de masificación y control fiscal, y adicionalmente 
los criterios comunes para el reconocimiento mutuo de firmas digitales basadas en certificados digitales, que 
garanticen la seguridad e interoperabilidad. 
 
La Política de Firma está  indicada y referenciada para todos los documentos electrónicos que componen el 
conjunto de documentos del negocio electrónico denominado Documento Soporte de Pago de Nómina 
Electrónica establecida por el Gobierno Nacional a cargo de la DIAN. Para todos los documentos que componen 
el Documento Soporte de Pago de Nómina Electrónica la firma se hará mediante la inclusión de una etiqueta i.e. 
<Signature …/> — dentro del formato estándar de intercambio XML, el cual está localizado en la siguiente ruta:  
XPath:  
 
 /NominaIndividual/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:Signature 
 /NominaIndividualDeAjuste/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:Signature 
 
La etiqueta contendrá los elementos que constituyen la implementación del estándar técnico XAdES, i.e. XML 
Advanced Electronic Signature asc; firma digital avanzada XML. 
 
La política de firma suministra la información que sobre la firma digital con destino  al control fiscal de la DIAN, 
deberá aplicar el Sujeto Obligado  como medida de ampliación del proceso de expedición de las nóminas 
electrónicas. Se advierte que los detalles de las técnicas informáticas de implementación no forman parte de 
esta política. Únicamente se incluyen las referencias a los estándares que describen las especificaciones técnicas 
sobre la implementación.  
La política de firma suministra la información que sobre la firma digital debiera verificar el Receptor de la Nómina, 
de acuerdo a la normatividad vigente. 
 
7.3. Especificaciones técnicas sobre la firma digital Avanzada. 
ETSI TS 101 903, v.1.2.2. v 1.3.2. y 1.4.1. Electronic Signatures and Infrastructures (SEI); XML Advanced Electronic 
Signatures (XAdES). 

---

## Página 235

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 235 de 269 
 
ETSI TR 102 038, v.1.1.1. Electronic Signatures and Infraestructures (SEI); XML format for signature policies. 
ETSI TS 102 176-1 V2.0.0 Electronic Signatures and Infraestructures (ESI): Algorithms and Paremeters for Secure 
Electronic Signatures; Part 1: Hash functions and asymmetric algorithms. 
ETSI TR 102 041, v.1.1.1. Electronic Signatures and Infraestructures (SEI); Signature policies report. 
ETSI TR 102 045, v.1.1.1. Electronic Signatures and Infraestructures (SEI); Signature policy for extended business 
model. 
ETSI TR 102 272, v.1.1.1. Electronic Signatures and Infraestructures (SEI); ASN.1 format for signature policies. 
IETF RFC 2560, X.509 Public Key Infrastructure Online Certificate Status-Protocol-OCSP 
IETF RFC 3125, Electronic Signature Policies 
IETF RFC 5280, RFC 4325 y RFC 4630, Internet X.509 Public Key Infrastructure; Certificate and Certificate 
Revocation List (CRL) Profile. 
ITU-T Recommendation X.680 (1997): “Information technology – Abstract Syntax Notation One (ASN.1): 
Specification on basic notation”. 
 
7.4. Alcance de la Política de Firma. 
Este documento define la Política de Firma que detalla las condiciones para la validación del Documento Soporte 
de Pago de Nómina Electrónica y que deberán ser admitidas por todas las plataformas tecnológicas implicadas 
en el ciclo del Documento Soporte de Pago de Nómina Electrónica. 
 
7.5. Política de Firma. 
7.5.1. Actores de la Firma. 
Sujeto Obligado o Empleador: 
Persona natural o jurídica que como tal debe emitir electrónicamente el Documento Soporte de Pago 
de Nómina Electrónica en las condiciones establecidas en la normatividad vigente. Para el ámbito de 
la firma digital son los firmantes vinculados a la persona  natural o jurídica que ha cumplido la 
habilitación como Sujeto Obligado. 
Proveedor de Soluciones Tecnológicas: 
En el ámbito de la emisión de l Documento Soporte de Pago de Nómina Electrónica  podrá ser el 
firmante autorizado por el Sujeto Obligado a actuar en su nombre , de acuerdo con lo señalado en el 
artículo 22 de la presente resolución. 
El término firmante se circunscribe a la definición dada en el Artículo 1.4 Decreto 2364 de 2012.  
Entidades de Certificación Digital – ECD: 
En el ámbito del Documento Soporte de Pago de Nómina Electrónica  es el tercero de confianza que 
tiene bajo su control la gestión de constatación, expedición, autenticación y registro histórico de los 
certificados digitales utilizados para las firmas digitales de las nóminas electrónicas. 
 
7.5.2. Formato de Firma. 
Se debe utilizar el estándar XMLDSig enveloped con formato XAdES -EPES según la especificación técnica 
ETSI TS 101 903, versión 1.2.2, versión 1.3.2 y versión 1.4.1 siendo obligatorio indicar la versión adoptada 
en las etiquetas XML, en las que se hace referencia al número de versión. 

---

## Página 236

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 236 de 269 
 
El formato XAdES de firma digital avanzada adoptado por la DIAN para el uso de firma digital corresponde 
a la Directiva XAdES-EPES, con el certificado digital y toda la cadena de certificac ión (desde el certificado 
raíz) incluida en los elementos «ds:X509Data» y «ds:Object», y la política de firma, es decir este 
documento, como un hiperenlace en el elemento «xades:SignaturePolicyIdentifier». 
Se admiten como válidos los algoritmos de generaci ón de hash, codificación en base64, firma, 
normalización y transformación definidos en el estándar XMLDSig. 
 
7.6. Algoritmo de Firma. 
El algoritmo de firma usado sobre el elemento «SignedInfo» (organizado previamente como establece el cánon) 
para la firma digital (que se adiciona al elemento «SignatureValue») del Documento Soporte de Pago de Nómina 
Electrónica puede ser cualquiera de los  definidos en la especificación XML -Signature Syntax and Processing 
(http:/www.w3.org/TR/xmldsig-core2/#sec-Algorithms) que actualmente son: 
Recomendado RSAwithSHA256 http:/www.w3.org/2001/04/xmldsig-more#rsa-sha256 
Recomendado RSAwithSHA384 http:/www.w3.org/2001/04/xmldsig-more#rsa-sha384 
Recomendado RSAwithSHA512 http:/www.w3.org/2001/04/xmldsig-more#rsa-sha512 
 
7.7. Algoritmo de Organización de Datos según el Canon. 
El algoritmo para organizar los datos según el canon usado sobre el elemento «SignedInfo» para la firma digital 
(que se adiciona al elemento  «SignatureValue») del Documento Soporte de Pago de Nómina Electrónica  es 
“Canonical XML (omits comments)”. Para esto se debe usar el valor “http:/www.w3.org/TR/2001/REC-xml-c14n-
20010315” dentro del elemento «CanonicalizationMethod».  
NOTA: atienda lo dicho en la sección “8 Sobre el CANON de los documentos electrónicos y la validez de la firma 
digital” 
<ds:CanonicalizationMethod Algorithm="http:/www.w3.org/TR/2001/REC-xml-c14n-20010315" /> 
 
7.8. Ubicación de la Firma. 
La firma se ubicará dentro del documento electrónico en el XPath: 
/NominaIndividual||NominaIndividualDeAjuste/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:S
ignature/ds:SignatureValue Para mayor detalle de los elementos que componen la firma ver el numeral 3.6 de 
este documento. 
 
7.9. Condiciones de la Firma. 
El emisor del Documento Soporte de Pago de Nómina Electrónica  o el proveedor de soluciones tecnológicas 
expresamente autorizado por este para hacerlo deberá aplicar la firma digital sobre el documento completo, 
con un certificado digital vigente y no revocado al momento de la firma. 
La firma se aplica a todos los elementos del Documento Soporte de Pago de Nómina Electrónica, los elementos 
contenidos dentro del elemento SignedProperties más la clave pública contenida en el elemento KeyInfo. Cada 
uno de estos se adiciona como referencia dentro del elemento SignedInfo. 
<ds:SignedInfo> 
<ds:CanonicalizationMethod Algorithm="http:/www.w3.org/TR/2001/REC-xml-c14n-20010315"/> 

---

## Página 237

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 237 de 269 
 
<ds:SignatureMethod Algorithm="http:/www.w3.org/2001/04/xmldsig-more#rsa-sha256"/> 
<ds:Reference Id="xmldsig-50280329-cdf3-4bb7-9d8f-edd480c8079c-ref0" URI=""> 
<ds:Transforms> 
<ds:Transform Algorithm="http:/www.w3.org/2000/09/xmldsig#enveloped-signature"/> 
</ds:Transforms> 
<ds:DigestMethod Algorithm="http:/www.w3.org/2001/04/xmlenc#sha256"/> 
<ds:DigestValue>vDUXUvy+JoIsT1k4dFv7ay8eJ+7jOMyRTcqiVKkdXHI=</ds:DigestValue> 
</ds:Reference> 
<ds:Reference URI="#xmldsig-50280329-cdf3-4bb7-9d8f-edd480c8079c-keyinfo"> 
<ds:DigestMethod Algorithm="http:/www.w3.org/2001/04/xmlenc#sha256"/> 
<ds:DigestValue>O5Bin7GRCjlH8qG1BFc3Cd2GlFx+IAp5DoEpn3nArgk=</ds:DigestValue> 
</ds:Reference> 
<ds:Reference Type="http:/uri.etsi.org/01903#SignedProperties" URI="#xmldsig-50280329-cdf3-4bb7-
9d8f-edd480c8079c-signedprops"> 
<ds:DigestMethod Algorithm="http:/www.w3.org/2001/04/xmlenc#sha256"/> 
<ds:DigestValue>scoM3Nb4cTlMm1GHP9ECfFetSUP+S9DqTVYVHW99KEw=</ds:DigestValue> 
</ds:Reference> 
</ds:SignedInfo> 
El certificado público requerido para validar la firma debe ser embebido dentro del XPath: 
/NominaIndividual||NominaIndividualDeAJuste/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds
:Signature/ds:KeyInfo/ds:X509Data/ds:X509Certificate 
en formato base64: 
<ds:KeyInfo Id="xmldsig-50280329-cdf3-4bb7-9d8f-edd480c8079c-keyinfo"> 
<ds:X509Data> 
<ds:X509Certificate> 
MIIHEjCCBfqgAwIBAgIQRMochPrzPAhYXX/wKSkB/DANBgkqhkiG9w0BAQsFADCBqDEcMBoGA1UECQ
wTd3d3LmNlcnRpY2FtYXJhLmNvbTEPMA0GA1UEBwwGQk9HT1RBMRkwFwYDVQQIDBBESVNUUklU
TyBDQVBJVEFMMQswCQYDVQQGEwJDTzEYMBYGA1UECwwPTklUIDgzMDA4NDQzMy03MRgwFgY
DVQQKDA9DRVJUSUNBTUFSQSBTLkExGzAZBgNVBAMMEkFDIFNVQiBDRVJUSUNBTUFSQTAgFw0xNj
EyMjMxOTUwMDhaGA8yMDE4MTIyMzE5NTAwNVowggEZMRQwEgYDVQQIDAtCT0dPVEEgRC5DLjE
NMAsGA1UECwwERElBTjEPMA0GA1UEBRMGNjQ0NjM1MRowGAYKKwYBBAGBtWMCAxMKODAw
MTk3MjY4NDE7MDkGA1UECgwyVS5BLkUuIERJUkVDQ0lPTiBERSBJTVBVRVNUT1MgWSBBRFVBTkFT
IE5BQ0lPTkFMRVMxFDASBgNVBAcMC0JPR09UQSBELkMuMSgwJgYJKoZIhvcNAQkBFhlTQU5USUFHT
1JPSkFTQERJQU4uR09WLkNPMQswCQYDVQQGEwJDTzE7MDkGA1UEAwwyVS5BLkUuIERJUkVDQ0lP
TiBERSBJTVBVRVNUT1MgWSBBRFVBTkFTIE5BQ0lPTkFMRVMwggEiMA0GCSqGSIb3DQEBAQUAA4IB
DwAwggEKAoIBAQCYyo2c1lRA4KgbH5mVB1fIhcZEKfTLP7OpOhsx9HfK8mbAM9tFv4Ep0wac8Vw2Ch
E1/McEFajbMA3pF+Ks4xVRaeTYqrlSXwPicR/R+F25zwhM4twYMg4+Bp7aXeGecY+gCfE2omfjY4AIu9
UlVWYGI+NWjJqktnCp/RomAWWgmJS8cZ6n4WIolWcUfts/OAflDJDr66WmohkEfpYSbQJ6D0z1qwUh
0i79x6I4dQCaUw4HeNFwWe1RyZSPi15YUZ2glCPH22FhyMC2/83p8dMD0+Y8XNpk3IAaMrZZD+JnOU
c3dvhO0LFHW1xniK6RrkHJNkHE3UxYaZ2SzhdbTi43AgMBAAGjggLAMIICvDA2BggrBgEFBQcBAQQq

---

## Página 238

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 238 de 269 
 
MCgwJgYIKwYBBQUHMAGGGmh0dHA6Ly9vY3NwLmNlcnRpY2FtYXJhLmNvMCQGA1UdEQQdMBuB
GVNBTlRJQUdPUk9KQVNARElBTi5HT1YuQ08wgecGA1UdIASB3zCB3DCBmQYLKwYBBAGBtWMyAQg
wgYkwKwYIKwYBBQUHAgEWH2h0dHA6Ly93d3cuY2VydGljYW1hcmEuY29tL2RwYy8wWgYIKwYBBQ
UHAgIwThpMTGltaXRhY2lvbmVzIGRlIGdhcmFudO1hcyBkZSBlc3RlIGNlcnRpZmljYWRvIHNlIHB1ZWRl
biBlbmNvbnRyYXIgZW4gbGEgRFBDLjA+BgsrBgEEAYG1YwoKATAvMC0GCCsGAQUFBwICMCEaH0Rpc
3Bvc2l0aXZvIGRlIGhhcmR3YXJlIChUb2tlbikwDAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMCA/gwJ
wYDVR0lBCAwHgYIKwYBBQUHAwEGCCsGAQUFBwMCBggrBgEFBQcDBDAdBgNVHQ4EFgQUxFbjYtGl
lLfoIB2sE5ThQbAkjyMwHwYDVR0jBBgwFoAUgHHMMpJYdfQDITqrvhzTj/IgFe0wEQYJYIZIAYb4QgEBB
AQDAgWgMIHXBgNVHR8Egc8wgcwwgcmggcaggcOGXmh0dHA6Ly93d3cuY2VydGljYW1hcmEuY29t
L3JlcG9zaXRvcmlvcmV2b2NhY2lvbmVzL2FjX3N1Ym9yZGluYWRhX2NlcnRpY2FtYXJhXzIwMTQuY3JsP2
NybD1jcmyGYWh0dHA6Ly9taXJyb3IuY2VydGljYW1hcmEuY29tL3JlcG9zaXRvcmlvcmV2b2NhY2lvbmV
zL2FjX3N1Ym9yZGluYWRhX2NlcnRpY2FtYXJhXzIwMTQuY3JsP2NybD1jcmwwDQYJKoZIhvcNAQELBQ
ADggEBAFjwIciRfKLmswvqI1gLtF0wroegzv6bHPF+pB9jJS+FLMdTXqh9OnvEh6cMrOL6Dnpcpc6m9je
Dn4dL9BdsMW3UFEur+QzbsL/H3bIVHXKFFmYPwaZZyD4xyEtyomSLtVe6LCV97Ojxg/Q48Kl3XORYC1
FJySfW89CMUPdm2QvSiYO3EC7wgeyfTiPrLhRqS3F0dmjYsDRQRqK7QfWtmGLJWlEFb6EE5mFUNUM
NDhAHF1quC12cWMpcbu3JfM9Khd74lz2GxvMvWwwdwBfX68bwwmfcRktVXDKq6X7z8MflfvdbOLz
1IchxNa2AOqtqHtE/689WaOrHfeSSkzWVUAc= 
</ds:X509Certificate> 
</ds:X509Data> 
</ds:KeyInfo> 
 
7.10. Identificador de la Política. 
Configuración del Identificador de Política para certificados digitales tipo sha-2 
 xPath: 
/NominaIndividual||NominaIndividualDeAjuste/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionCont
ent/ds:Signature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignaturePr
operties/xades:SignaturePolicyIdentifier/xades:SignaturePolicyId/xades:SigPolicyId/xades:Identifier:= 
Valor:  
https:/facturaelectronica.dian.gov.co/politicadefirma/v2/politicadefirmav2.pdf      
 
 xPath 
/NominaIndividual||NominaIndividualDeAjuste/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionCont
ent/ds:Signature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignaturePr
operties/xades:SignaturePolicyIdentifier/xades:SignaturePolicyId/xades:SigPolicyHash/ds:DigestMethod/
@Algorithm:= 
Valor: 2 Opciones 
http:/www.w3.org/2001/04/xmlenc#sha256 o http:/www.w3.org/2001/04/xmlenc#sha512  
 
 xPath: 
/NominaIndividual||NominaIndividualDeAjuste/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionCont

---

## Página 239

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 239 de 269 
 
ent/ds:Signature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignaturePr
operties/xades:SignaturePolicyIdentifier/xades:SignaturePolicyId/xades:SigPolicyId/xades:Description 
Valor: Política de firma para nóminas electrónicas de la República de Colombia. 
 
7.11. Hora de Firma. 
Se debe especificar en formato xsd:dateTime la fecha y hora en que reclama el firmante haber firmado el 
Documento Soporte de Pago de Nómina Electrónica. 
<xades:SigningTime>2009-07-14T13:28:00+02:00</xades:SigningTime> 
NOTA: El deber de los emisores del Documento Soporte de Pago de Nómina Electrónica  es que los sistemas 
computacionales que utilicen para el firmado de los documentos deberán estar sincronizados con el reloj de la 
súper intendencia de industria y comercio el cual determina la hora legal colombiana. 
http:/www.sic.gov.co/hora-legal-colombiana. 
 
7.12. Firmante. 
El elemento xades:SignerRole contiene uno y sólo uno de los siguientes atributos: 
• “supplier” cuando la firma de la nómina la realiza el Obligado a Emitir Documento Soporte de Pago de Nómina 
Electrónica. 
• “third party” cuando la firma la realiza un Proveedor de Soluciones Tecnológicas que en su caso, actué en su 
nombre. 
<xades:SignerRole>supplier</xades:SignerRole> 
 
7.13. Mecanismo de firma digital. 
El mecanismo de firma digital a que se refiere el artículo 7 de la Ley 527 de 1999 y el Decreto 2364 de 2012 
será considerada en el negocio electrónico denominado Emisión del Documento Soporte de Pago de Nómina 
Electrónica una vez sea reglamentada por la DIAN para tal efecto. 
 
7.14. Certificado digital desde la vigencia de la circular 03-2016 de la ONAC. 
Este documento incluye los argumentos que deberán usarse como valores de los parámetros de: 
 Los certificados digitales con no repudio  previstos en el estándar RFC -5280, y que cumplan con la Ley de 
Comercio Electrónico de Colombia, que utilicen los emisores electrónicos para firmar digitalmente los 
documentos desmaterializados del negocio del Documento Soporte de Pago de Nómina Electrónica. 
 Los atributos que resuelven las ambigüedades de los elementos que conforman los documentos 
desmaterializados del negocio del Documento Soporte de Pago de Nómina Electrónica , precisando las 
características criptográficas empleadas para cumplir con la Ley de Comercio Electrónico de Colombia.  
Referencia: URL https:/es.wikipedia.org/wiki/SHA-2 
 
Regla-1 

---

## Página 240

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 240 de 269 
 
Lapso de Validez del certificado digital Expedido ANTES de octubre 1 de 2016 T00:00:00, y hasta la terminación 
de la vigencia 
Signature Algorithm Valores válidos dentro del certificado digital: 
      Sha1WithRSAEncryption 
      sha224WithRSAEncryption 
      sha256WithRSAEncryption 
      sha384WithRSAEncryption 
      sha512WithRSAEncryption 
X509v3 Key Usage: critical Valores necesarios dentro del certificado digital: 
Digital Signature 
Non Repudiation 
Descripción: 
Estamos aplicando la reglamentación de la ONAC, URL 
http:/onac.org.co/anexos/documentos/TRANSICIRCULARES/2016circulares/circular03-2016.pdf 
Si el valor “Validity” del lapso de vigencia del certificado empezó antes de octubre 1 de 2016, la firma digital del 
Documento Soporte de Pago de Nómina Electrónica puede: 
 Emplear certificados digitales que hayan sido generados con resúmenes criptográficos del tipo SHA1 
 Que el fragmento SignedInfo al que se le aplicó el canon fue la entrada para calcular el resumen criptográfico 
que fue firmado digitalmente con << http:/www.w3.org/2000/09/xmldsig#rsa-sha1 >> 
 La aplicación del algoritmo de firma digital de las nóminass electrónicas depende del lapso de vigencia dentro del 
cual debió haber sido generada y firmada, y del método de generación del certificado digital utilizado. No podrá 
existir una nómina con fecha válida, i.e. 
/NominaIndividual||NominaIndividualDeAjuste/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:Si
gnature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignatureProperties/xades:Si
gningTime— diferente o por fuera del lapso de vigencia del certificado digital que se usó para calcular la firma-
digital. 
El no cumplimiento de estos valores deberá registrarse como una firma digital fallida para el documento 
electrónico, motivada en: 
 Algoritmo de Firma del certificado digital (tipo SHA1) no previsto por la DIAN 
 Uso de la clave pública del certificado digital carece de los propósitos “firma digital” o “no repudio”. 
Pueden estar presentes ambos motivos. 
Si el lapso de validez inhabilita a 
/NominaIndividual||NominaIndividualDeAjuste/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:
Signature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignatureProperties/xades:Sig
ningTime, entonces deberá registrarse como una firma digital fallida para el documento electrónico, motivada en: 
 Fecha de expedición del documento electrónico no corresponde con el lapso de vigencia del certificado digital. 
Este motivo puede ser concurrente con los descritos en la celda anterior. 
 

---

## Página 241

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 241 de 269 
 
Regla-2 
Lapso de Validez del certificado 
digital 
Después de 30 de septiembre de 2016 T23:59:59 
Signature Algorithm Valores válidos dentro del certificado digital: 
      sha256WithRSAEncryption 
      sha384WithRSAEncryption 
      sha512WithRSAEncryption 
X509v3 Key Usage: critical Valores necesarios dentro del certificado digital: 
Digital Signature 
Non Repudiation 
Descripción: 
Estamos aplicando la reglamentación de la ONAC, URL 
http:/onac.org.co/anexos/documentos/TRANSICIRCULARES/2016circulares/circular03-2016.pdf 
Si el valor “Validity” del lapso de vigencia del certificado empezó después del 30 de septiembre de 2016 T23:59:59, 
la firma digital del Documento Soporte de Pago de Nómina Electrónica tiene que: 
 Emplear certificados digitales que hayan sido generados con resúmenes criptográficos del tipo SHA256; existen 
otras opciones como aparece en la lista << Signature Algorithm >> 
 Que el resumen criptográfico que se aplicó al fragmento que fue firmado digitalmente corresponda con el << 
SignatureMethod >> empleado 
El no cumplimiento de estos valores deberá registrarse como una firma digital fallida para el documento 
electrónico, motivada en: 
 Algoritmo de Firma del certificado digital (tipo SHA2) no previsto por la DIAN 
 Uso de la clave pública del certificado digital carece de los propósitos “firma digital” o “no repudio”. Vea Anexo 2. 
Pueden estar presentes ambos motivos. 
Si el lapso de validez inhabilita a  
/NominaIndividual||NominaIndividualDeAjuste/Ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:S
ignature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignatureProperties/xades:Signi
ngTime, entonces deberá registrarse como una firma digital fallida para el documento electrónico, motivada en: 
 Fecha de expedición del documento electrónico no corresponde con el lapso de vigencia del certificado digital. 
Este motivo puede ser concurrente con los descritos en la celda anterior. 
 
Regla-3 
Algoritmo de firma digital aplicado 
al Documento Soporte de Pago de 
Nómina Electrónica 
Certificado digital expedido después de 30 de septiembre de 2016 T23:59:59 
/NominaIndividual||NominaIndivid
ualDeAjuste/Ext:UBLExtensions/ext:
UBLExtension/ext:ExtensionContent
Algoritmo=RSAwithSHA256 
Use: http:/www.w3.org/2001/04/xmldsig-more#rsa-sha256  
Algoritmo=RSAwithSHA384  
Use: http:/www.w3.org/2001/04/xmldsig-more#rsa-sha384   

---

## Página 242

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 242 de 269 
 
Algoritmo de firma digital aplicado 
al Documento Soporte de Pago de 
Nómina Electrónica 
Certificado digital expedido después de 30 de septiembre de 2016 T23:59:59 
/ds:Signature/ds:SignedInfo/ds:Sign
atureMethod/@Algorithm= 
Algoritmo=RSAwithSHA512  
Use: http:/www.w3.org/2001/04/xmldsig-more#rsa-sha512 
Descripción: 
Estamos aplicando la reglamentación de la ONAC, URL  
http:/onac.org.co/anexos/documentos/TRANSICIRCULARES/2016circulares/circular03-2016.pdf 
El algoritmo de firma digital aplicado a la facture electrónica no tiene correspondencia directa con el resumen 
criptográfico utilizado para obtener los fragmentos de la Regla-4, i.e. pueden usarse tamaños de  
Si el valor del ../ds:SignatureMethod/@Algorithm no corresponde con los valores paramétricos, entonces deberá 
registrarse como una firma digital fallida para el documento electrónico, motivada en: 
 Empleó un algoritmo de firma digital no previsto por la DIAN.  
Si el valor del ../ds:SignatureMethod/@Algorithm corresponde a http:/www.w3.org/2000/09/xmldsig#rsa-sha1, 
entonces deberá registrarse como una firma digital fallida para el documento electrónico, motivada en: 
 Empleó un algoritmo de firma digital que está caducado según el reglamento de la Ley de Comercio Electrónico 
de Colombia.  
 
Regla-4 
Algoritmos de resumen criptográfico 
aplicado a los fragmentos del Documento 
Soporte de Pago de Nómina Electrónica 
que se incluyen dentro del fragmento que 
se firma digitalmente 
Certificado digital expedido después de 30 de septiembre de 2016 
T23:59:59 
/NominaIndividual||NominaIndividualDeA
juste/Ext:UBLExtensions/ext:UBLExtension
/ext:ExtensionContent/ds:Signature/ds:Sig
nedInfo/ds:Reference/ds:DigestMethod/
@Algorithm= 
/NominaIndividual||NominaIndividualDeA
juste/Ext:UBLExtensions/ext:UBLExtension
/ext:ExtensionContent/ds:Signature/ds:Sig
nedInfo/ds:Reference/ds:DigestMethod/
@Algorithm= 
/NominaIndividual||NominaIndividualDeA
juste/Ext:UBLExtensions/ext:UBLExtension
/ext:ExtensionContent/ds:Signature/ds:Sig
nedInfo/ds:Reference[3]/ds:DigestMetho
d/@Algorithm 
SHA256. Cadena de 256 bits.  
Use: http:/www.w3.org/2001/04/xmlenc#sha256 
SHA384. Cadena de 384 bits. 
Use: 
http:/www.w3.org/2001/04/xmldsig-more#sha384 
SHA512. Cadena de 512 bits. 
Use: 
http:/www.w3.org/2001/04/xmlenc#sha512 

---

## Página 243

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 243 de 269 
 
Algoritmos de resumen criptográfico 
aplicado a los fragmentos del Documento 
Soporte de Pago de Nómina Electrónica 
que se incluyen dentro del fragmento que 
se firma digitalmente 
Certificado digital expedido después de 30 de septiembre de 2016 
T23:59:59 
/NominaIndividual||NominaIndividualDeA
juste/Ext:UBLExtensions/ext:UBLExtension
/ext:ExtensionContent/ds:Signature/ds:Ob
ject/xades:QualifyingProperties/xades:Sig
nedProperties/xades:SignedSignatureProp
erties/xades:SigningCertificate/xades:Cert
/xades:CertDigest/ds:DigestMethod/@Alg
orithm= 
/NominaIndividual||NominaIndividualDeA
juste/Ext:UBLExtensions/ext:UBLExtension
/ext:ExtensionContent/ds:Signature/ds:Ob
ject/xades:QualifyingProperties/xades:Sig
nedProperties/xades:SignedSignatureProp
erties/xades:SigningCertificate/xades:Cert
/xades:CertDigest/ds:DigestMethod/@Alg
orithm= 
/NominaIndividual||NominaIndividualDeA
juste/Ext:UBLExtensions/ext:UBLExtension
/ext:ExtensionContent/ds:Signature/ds:Ob
ject/xades:QualifyingProperties/xades:Sig
nedProperties/xades:SignedSignatureProp
erties/xades:SigningCertificate/xades:Cert
[3]/xades:CertDigest/ds:DigestMethod/@
Algorithm= 
/NominaIndividual||NominaIndividualDeA
juste/Ext:UBLExtensions/ext:UBLExtension
/ext:ExtensionContent/ds:Signature/ds:Ob
ject/xades:QualifyingProperties/xades:Sig
nedProperties/xades:SignedSignatureProp
erties/xades:SignaturePolicyIdentifier/xad
es:SignaturePolicyId/xades:SigPolicyHash/
ds:DigestMethod/@Algorithm= 
Descripción: 
Estamos aplicando la reglamentación de la ONAC, URL  
http:/onac.org.co/anexos/documentos/TRANSICIRCULARES/2016circulares/circular03-2016.pdf 

---

## Página 244

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 244 de 269 
 
Algoritmos de resumen criptográfico 
aplicado a los fragmentos del Documento 
Soporte de Pago de Nómina Electrónica 
que se incluyen dentro del fragmento que 
se firma digitalmente 
Certificado digital expedido después de 30 de septiembre de 2016 
T23:59:59 
El algoritmo de resumen criptográfico utilizado para los fragmentos que intervienen y forman parte del elemento 
que se firma digitalmente no tiene correspondencia con el algoritmo de firma digital de la Regla-3. 
Si el valor del ../ds:DigestMethod/@Algorithm no corresponde con los valores paramétricos, entonces deberá 
registrarse como una firma digital fallida para el documento electrónico, motivada en: 
 Empleó un algoritmo de resumen criptográfico no previsto por la DIAN. Vea Anexo 2. 
Si el valor del ../ds:DigestMethod/@Algorithm corresponde a http:/www.w3.org/2000/09/xmldsig#sha1, entonces 
deberá registrarse como una firma digital fallida para el documento electrónico, motivada en: 
 Empleó un algoritmo de resumen criptográfico que está caducado según el reglamento de la Ley de Comercio 
Electrónico de Colombia. Vea Anexo 2. 
 

---

## Página 245

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 245 de 269 
 
8. Mecanismos de Control del Documento Soporte de Pago de Nómina Electrónica y Nota de Ajuste del 
Documento Soporte de Pago de Nómina Electrónica. 
8.1. Especificación Técnica de Generación Del CUNE. 
8.1.1. Consideraciones Generales del CUNE. 
El siguiente numeral presenta la especificación técnica para la genera ción del Código Único de l Documento 
Soporte de Pago de Nómina Electrónica – CUNE, que es utilizado con varios propósitos, entre ellos: 
 Como identificador universal del Documento Soporte de Pago de Nómina Electrónica y la Nota de Ajuste de 
Documento Soporte de Pago de Nómina Electrónica. 
 Como un mecanismo del sistema técnico  para validar la integridad y autenticidad de informaciones claves 
del ejemplar del Documento Soporte de Pago de Nómina Electrónica  y Nota de Ajuste de Documento 
Soporte de Pago de Nómina Electrónica. 
El CUNE tal como se calcula en esta especificación técnica está indicado y referenciado para las instancias o 
ejemplares que contienen datos con la sintaxis y la semántica de emisión del Documento Soporte de Pago de 
Nómina Electrónica y Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica y que se producen 
para dejar registro electrónico de la ocurrencia de las mismas. Las instancias corresponden a los siguientes 
documentos que forman parte de los perfiles de emisiones de comprobantes de nómina para la DIANi:  
 Documento Soporte de Pago de Nómina Electrónica. 
Para todos los documentos de los perfiles de emisiones del Documento Soporte de Pago de Nómina Electrónica 
para la DIAN se incluirá el atributo <CUNE> que contendrá un identificador universal que para los documentos 
Documento Soporte de Pago de Nómina Electrónica y Nota de Ajuste de Documento Soporte de Pago de Nómina 
Electrónica, se denomina CUNE. Este atributo está localizado en la siguiente ruta:  
XPathii: 
 /NominaIndividual/InformacionGeneral/@CUNE 
 /NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@CUNE 
 /NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@CUNE 
La etiqueta contendrá el resultado del cálculo especificado en esta sección.  
Esta especificación suministra la información que sobre el CUNE, como mecanismo  de control de la DIAN, deberá 
aplicar el Emisor de la Nómina  como medida de la ampliación del proceso de emisión del Documento Soporte 
de Pago de Nómina Electrónica. Los mecanismos de esta medida facilitarán la inclusión de evidencias de validez 
de la firma digital avanzada así el EN E o quien verifique la validez de la firma intente repudiar el Documento 
Soporte de Pago de Nómina Electrónica  posteriormente, haciendo más confiable la  circulación de los 
documentos electrónicos entre los participantes en las operaciones de entrega del Documento Soporte de Pago 
de Nómina Electrónica, y serán tenidas en cuenta por la autoridad competente. Los ingenieros de software del 
OENE deberán conoce r este documento, y se advierte  que los detalles de las técnicas informáticas de 
implementación del CUNE se describen en esta sección. 
 
8.1.1.1. Generación de CUNE. 
El CUN E, permite identificar unívocamente un Documento Soporte de Pago de Nómina Electrónica  en el 

---

## Página 246

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 246 de 269 
 
territorio nacional, lo cual se logra por medio de la generación de un código único usando una función one-way 
hash. 
Para la generación del CUN E se debe utilizar el algoritmo SHA -384 que garantiza que dos (2) cadenas de texto 
no generarán el mismo hash. En  expresión matemática tenemos que el Código Único del Documento Soporte 
de Pago de Nómina Electrónica es: 
 
NumNE: Numero de Documento Soporte de Pago de Nómina Electronica. (Prefijo concatenado con el 
Consecutivo de la nómina) 
FecNE: Fecha de Generación del Documento. 
HorNE: Hora de Generación del Documento incluyendo GMT. 
ValDev: Total Devengos, con punto decimal, con decimales truncados a dos (2) dígitos, sin 
separadores de miles, ni símbolo pesos. 
ValDed: Total Deducciones, con punto decimal, con decimales truncados a dos (2) dígitos, sin 
separadores de miles, ni símbolo pesos.  
ValTolNE: Total Pagado (Devengado - Deducciones), con punto decimal, con decimales truncados a dos 
(2) dígitos, sin separadores de miles, ni símbolo pesos. 
NitNE: NIT del Emisor del Documento, sin puntos ni guiones, sin digito de verificación. 
DocEmp: Número de Identificación del Empleado, sin puntos ni guiones, sin digito de verificación. 
TipoXML: Tipo de XML utilizado. 
Software-Pin: Pin del Software utilizado. 
TipAmb: Número de identificación del ambiente utilizado por el contribuyente para emitir la nómina, 
validar el numeral 5.1.1. 
Composición del CUNE = SHA-384 (NumNE + FecNE + HorNE + ValDev + ValDed + ValTolNE + NitNE + DocEmp + 
TipoXML + Software-Pin +TipAmb) 
Donde + significa la concatenación de las cadenas de caracteres. 
 
8.1.1.2. Ejemplos. 
8.1.1.3. Ejemplo de CUN E para Documento Soporte de Pago de Nómina Electrónica  y Nota de Ajuste de 
Documento Soporte de Pago de Nómina Electrónica. 
 
Teniendo en cuenta los siguientes datos de entrada, se presenta el resultado del CUNE.  
 Ejemplo: CUNE de un Documento Soporte de Pago de Nómina Electrónica-e y Nota de Ajuste de Documento Soporte 
de Pago de Nómina Electrónica-e (Opción Reemplazar): SHA384 
NumNE: N00001 
FecNE: 2020-01-16 
HorNE: 10:53:10-05:00 
ValDev: 3500000.00 

---

## Página 247

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 247 de 269 
 
 Ejemplo: CUNE de un Documento Soporte de Pago de Nómina Electrónica-e y Nota de Ajuste de Documento Soporte 
de Pago de Nómina Electrónica-e (Opción Reemplazar): SHA384 
ValDed: 1000000.00 
ValTolNE: 2500000.00 
NitNE: 700085371 
DocEmp: 800199436 
TipoXML: 102 
Software-Pin: 693 
TipAmb: 1 
Composición 
del CUNE: 
(N000012020-01-161053:10-
05:003500000.001000000.002500000.007000853718001994361026931) 
CUNE.SHA384: 16560dc8956122e84ffb743c817fe7d494e058a44d9ca3fa4c234c268b4f766003253fbee7ea4af9682dd
57210f3bac2 Destino: /NominaIndividual/InformacionGeneral/@CUNE y 
/NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@CUNE o 
/NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@CUNE 
Ref: http:/www.sha1-online.com/  
 
8.1.1.4. Xpath. 
De forma no ambigua se especifican las expresiones XPath que deben aplicarse a un Documento Soporte de 
Pago de Nómina Electrónica  y Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica  para 
obtener la información requerida y permitir la generación del CUNE. 
 
Definición CUNE de un Documento Soporte de Pago de Nómina Electrónica. 
NumNIE: /NominaIndividual/NumeroSecuenciaXML/@Numero 
FecNIE: /NominaIndividual/InformacionGeneral/@FechaGen 
HorNIE: /NominaIndividual/InformacionGeneral/@HoraGen 
ValDev: /NominaIndividual/DevengadosTotal 
ValDed: /NominaIndividual/DeduccionesTotal 
ValTol: /NominaIndividual/ComprobanteTotal 
NitNIE: /NominaIndividual/Empleador/@NIT 
DocEmp: /NominaIndividual/Trabajador/@NumeroDocumento 
TipoXML: /NominaIndividual/InformacionGeneral/@TipoXML 
Software-Pin:  No está incluido dentro del documento XML. 
 Valor reservado, de circulación restringida, asignado por quien obtuvo el Código de Activación 
del software en la plataforma del Documento Soporte de Pago de Nómina Electrónica - DIAN 
TipAmb: /NominaIndividual/InformacionGeneral/@Ambiente 
 
Definición CUNE de una Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica (Opción 

---

## Página 248

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 248 de 269 
 
Reemplazar). 
NumNIAE: /NominaIndividualDeAjuste/Reemplazar/NumeroSecuenciaXML/@Numero 
FecNIAE: /NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@FechaGen 
HorNIAE: /NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@HoraGen 
ValDev: /NominaIndividualDeAjuste/Reemplazar/DevengadosTotal 
ValDed: /NominaIndividualDeAjuste/Reemplazar/DeduccionesTotal 
ValTol: /NominaIndividualDeAjuste/Reemplazar/ComprobanteTotal 
NitNIAE: /NominaIndividualDeAjuste/Reemplazar/Empleador/@NIT 
DocEmp: /NominaIndividualDeAjuste/Reemplazar/Trabajador/@NumeroDocumento 
TipoXML: /NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@TipoXML 
Software-Pin:  No está incluido dentro del documento XML. 
 Valor reservado, de circulación restringida, asignado por quien obtuvo el Código de Activación 
del software en la plataforma del Documento Soporte de Pago de Nómina Electrónica - DIAN 
TipAmb: /NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@Ambiente 
 
Definición CUNE de una Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica (Opción 
Eliminar). 
NumNIAE: /NominaIndividualDeAjuste/Eliminar/NumeroSecuenciaXML/@Numero 
FecNIAE: /NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@FechaGen 
HorNIAE: /NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@HoraGen 
ValDev: 0.00 
ValDed: 0.00 
ValTol: 0.00 
NitNIAE: /NominaIndividualDeAjuste/Eliminar/Empleador/@NIT 
DocEmp: 0 
TipoXML: /NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@TipoXML 
Software-Pin:  No está incluido dentro del documento XML. 
 Valor reservado, de circulación restringida, asignado por quien obtuvo el Código de Activación 
del software en la plataforma del Documento Soporte de Pago de Nómina Electrónica - DIAN 
TipAmb: /NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@Ambiente 
 
8.2. Especificacón Técnica Del Código De Seguridad Del Software. 
El elemento /@SoftwareSC ubicado en: 
/NominaIndividual/ProveedorXML/@SoftwareSC (Documento Soporte de Pago de Nómina Electrónica) 
/NominaIndividualDeAjuste/Reemplazar/ProveedorXML/@SoftwareSC (Nota de Ajuste de Documento Soporte 
de Pago de Nómina Electrónica – Opción Reemplazar) 
/NominaIndividualDeAjuste/Eliminar/ProveedorXML/@SoftwareSC (Nota de Ajuste de Documento Soporte de 
Pago de Nómina Electrónica – Opción Eliminar) 

---

## Página 249

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 249 de 269 
 
Es la huella de legitimidad del software que produjo las nóminas electrónicas, y que se basa en informaciones 
privadas que se usan para calcular un resumen criptográfico. Una parte de esa información fue asignada por  el 
Emisor del Documento Soporte de Pago de Nómina Electrónica , i.e. el PIN del software — y la otra la asignó el 
sistema de Emisión del Documento Soporte de Pago de Nómina Electrónica. El Emisor del Documento Soporte 
de Pago de Nómina Electrónica  directo y los PT deben mantener en reserva estas informaciones para evitar 
actividades maliciosas de quienes buscan explotar las vulnerabilidades de los usuarios de sistemas informáticos. 
Es el producto de un algoritmo criptográfico del tipo one-way hash function. 
Arma una cadena con dos valores: 
 
Identificador del software asignado desde el sistema de la DIAN cuando el software se activa en el Sistema de 
Emisión del Documento Soporte de Pago de Nómina Electrónica. i.e. código de activación. 
PIN del software que usted asignó en el sistema de la DIAN cuando el software se activa en el Sistema de Emisión 
del Documento Soporte de Pago de Nómina Electrónica. 
La cadena resultante es la semilla para el cálculo SHA-384. El resultado es la huella del software que autorizó la 
DIAN al Emisor de l Documento Soporte de Pago de Nómina Electrónica  o al Proveedor de Soluciones 
Tecnológicas. 
 
SoftwareSecurityCode:= SHA-384 (Id Software + Pin + NroDocumento) 
NroDocumento (Documento Soporte de Pago de Nómina Electrónica) = 
/NominaIndividual/NumeroSecuenciaXML/@Numero 
NroDocumento (Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica) = 
/NominaIndividualDeAjuste/Reemplazar/NumeroSecuenciaXML/@Numero ó 
/NominaIndividualDeAjuste/Eliminar/NumeroSecuenciaXML/@Numero 
 
8.3. Métodos de Calculo. 
8.3.1. Cálculo de Tiempo Laborado 
Para indicar el Tiempo laborado de un determinado trabajador en la empresa del emisor del Documento 
Soporte de Pago de Nómina Electrónica, debe utilizarse la siguiente Nomenclatura: 
 
Calculo Tiempo Laborado 
Significado 
1 Año = 360 Dias 
1 Mes = 30 Dias 
5 Años + 3 Meses + 18 Dias 
(5*360)+(3*30)+18 
1908.00 
 
9. Descripciónes Tecnológicas del Web Services de Método Síncrono.  
La solución de transmisión de documentos electrónicos de Documento Soporte de Pago de Nómina Electrónica 

---

## Página 250

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 250 de 269 
 
y Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica involucra la utilización de UBL 2.1 como 
lenguaje para la sección de firmado de los  documentos electrónicos a diferencia de la estructura definida y el 
contenido de todas las demás secciones requeridas ya que estas no cumplen con el lenguaje estándar UBL 2.1. 
El firmado de los documentos de Nómina se realiza mediante certificados digitales. 
 
9.1. Modelo conceptual de comunicación. 
El modelo de comunicación iniciará en el sistema del contribuyente posterior al proceso de habilitación, por 
medio del consumo del servicio que expone la DIAN para validar la transmisión de los documentos 
electrónicos de Documento Soporte de Pago de Nómina Electrónica y Nota de Ajuste de Documento Soporte 
de Pago de Nómina Electrónica. 
La DIAN expone sobre el mismo servicio web actual de Factura Electrónica en Validación Previa 
(WcfDianCustomerServices) una nueva la operación llamada SendNominaSync para la transmisión síncrona 
de 1 documento electrónico de Documento Soporte de Pago de Nómina Electrónica o Nota de Ajuste de 
Documento Soporte de Pago de Nómina Electrónica XML en contenedor .zip y la modificacion de la operación 
actual llamada GetStatus para incluir la consulta de Documentos Soporte de Pago de Nómina Electrónica. 
 
9.2. Servicio síncrono. 
Este servicio tiene la funcionalidad de transmitir a la DIAN los documentos de Nó mina, de tal forma que la 
plataforma de validacion los evalúe de acuerdo a la estructura de firmado UBL 2.1 y a la estructura propia 
definida para el contenido de todas las demás secciones requeridas, y de forma síncr ona de respuesta de 
validacion. 
El servicio puede recibir un .zip con un solo d ocumento electrónico firmado digitalmente, construido según 
esquema detallado en el presente anexo técnico. 
 
9.2.1. Secuencia del servicio síncrono. 
Este servicio estará disponible en los ambientes de producción (Habilitación y Operación) como sucede con 
Factura Electrónica en Validación Previa .El software cliente realiza la conexión autenticando por medio de 
certificado digital. 
 Se adjunta archivo .zip con documento XML de NominaIndividual o NominaIndividualDeAjuste a 
validar.Se envía solicitud (Request) con los parámetros de consumo en la estructura del XML 
definida para este método. 
 Se descomprime ZIP y se evalúan los siguientes elementos. 
 Archivo zip no este vacío. 
 Archivo zip no este corrupto. 
 Exista la sección UBL 2.1 con firmado digital. 
 Corresponda a la estructura XSD de NominaINdividual o NominaIndividualDeAjuste definida 

---

## Página 251

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 251 de 269 
 
para estos documentos.  
 No existan errores en las reglas de validaciones de acuerdo al presente Anexo Técnico. 
 Posterior a las validaciones se genera respuesta (Response) síncrona con el detalle de la evaluación 
del documento, que incluye dentro de sus elementos un ApplicationResponse codificado en Base64 
con la respuesta de validacion de la DIAN. 
 
9.3. Aspectos tecnológicos de las operaciones del web service. 
Los participantes que estén registrados para operar con la plataforma de validacion previa de la DIAN, podrán 
hacer uso de las operaciones de transmisión y consulta de los documentos de Documento Soporte de Pago 
de Nómina Electrónica y Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica. 
Los Proveedores Tecnológicos realizarán la transmisión de los documentos electrónicos consumiendo el 
servicio WEB que expone la DIAN sin operar intermediarios en dicha transmisión. 
Para ello el sistema cliente de los participantes deberán tener las siguientes consideraciones: 
 
 Para la transmisión de los DE deberán desarrollar un software cliente independiente del lenguaje de 
programación. 
 El lenguaje XML de los archivos de intercambio de información será el de UBL 2.1 para el proceso de 
firmado y las demás secciones del documento serán la estructura propia detallada en el presente Anexo 
Técnico. 
 Con el fin de garantizar la seguridad en la c omunicación, el software cliente deberá autenticarse ante la 
DIAN utilizando certificado digital. 
 El medio de comunicación es internet con la utilización del protocolo TLS versión 1.2. con autenticación 
mutua a través de certificados digitales. 
 El intercambio de mensajes entre los Servicios Web de la DIAN y el particpante Habilitado será realizado 
mediante el estándar SOAP versión 1.2, con intercambio de mensajes XML en el estándar Style/Encoding: 
Document/Literal. 
 
9.4. Estándar de comunicación. 
La comunicación  está basada en servicios Web expuestos por el Sistema de Validación y Gestión de 
Documentos de DIAN. 
El medio físico de comunicación es Internet, con la utilización del protocolo TLS versión 1.2, con 
autentificación mutua a través de certificados digitales. 
El modelo de comunicación sigue el estándar de servicios web definido por el WS -Security 1.0 Oasis, con 
autenticación X.509 Certificate Token Profile 1.1. 
El intercambio de mensajes entre los Servicios Web de la DIAN y el sistema del Habilitado para el Proveedor 

---

## Página 252

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 252 de 269 
 
Tecnológico (PT) será realizado mediante el estándar SOAP versión 1.2, con intercambio de mensajes XML en 
el estándar Style/Encoding: Document/Literal. 
9.5. Estándar de mensajes de los servicios de La DIAN. 
La solicitud de consumo de los servicios dispuestos por la DIAN seguirá el siguiente estándar.  
 
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
xmlns:wcf="http://wcf.dian.colombia"> 
<soap:Header/> 
   <soap:Body> 
      <wcf:SendNominaSync> 
         <wcf:contentFile>------ Área de Dato: Archivo Nomina.zip en base 64 que contiene un documento XML 
que atiende al formato definido para la operación de nómina 
         </wcf:contentFile> 
      </wcf:SendNominaSync> 
</soap:Body> 
</soap:Envelope> 
 
El área de datos obedecerá a un formato XML definido para cada WS. 
 
9.6. Descripción de los servicios web de La DIAN. 
El sistema de validación y gestión de documentos de Documento Soporte de Pago de Nómina Electrónica y 
Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica DIAN, dispone de una capa de servicios 
que atienden las funcionalidades requeridas para operar, cada operación del servicio se encuentra 
respaldado por un Método Web específico. 
El modelo de comunicación e interoperabilidad siempre iniciará en el sistema del participante habilitado, por 
medio del consumo del servicio correspondiente de un PT, el cual posteriormente consumirá los servicios de 
la DIAN para validar la transmisión de los documentos. 
 
9.7. WS recepción documento electrónico – SendNominaSync. 
 Función: Recibir un ZIP con UBLs DE. 
 Proceso: Sincrónico  
 Método: SendBillSync 
 
9.7.1. Descripción de procesamiento. 
 El software cliente realiza la conexión autenticando por medio de certificado digital. 
 Se adj unta archivo .zip con documento XML de NominaIndividual o NominaIndividualDeAjuste a 
validar. 

---

## Página 253

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 253 de 269 
 
 Se envía solicitud (Request) con los parámetros de consumo en la estructura del XML definida para 
este método. 
 Se descomprime ZIP y se evalúan los siguientes elementos. 
 Archivo zip no este vacío. 
 Archivo zip no este corrupto. 
 Exista la sección UBL 2.1 con firmado digital. 
 Corresponda a la estructura XSD de NominaIndividual o NominaINdividualDeAjuste definida 
para estos documentos. 
 No existan errores en estructura XML propia de acuerdo al Anexo Técnico. 
 Posterior a las validaciones se genera respuesta (Response) síncrona con el detalle de la evaluación 
del documento, que incluye dentro de sus elementos un ApplicationResponse codificado en Base64 
con la respuesta de validacion de la DIAN. 
 
9.7.2. Mensaje de petición. 
Operación : SendNominaSync 
Descripción: Operación que realiza la transmisión de eventos tipo NominaIndividual y 
NominaIndividualAjuste. 
Request 
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia"> 
   <soap:Header/> 
   <soap:Body> 
      <wcf:SendNominaSync> 
         <!--Optional:--> 
         <wcf:contentFile>cid:1057568194758</wcf:contentFile> 
      </wcf:SendNominaSync> 
   </soap:Body> 
</soap:Envelope> 
Response 
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://www.w3.org/2005/08/addressing" 
xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"> 
   <s:Header> 
      <a:Action 
s:mustUnderstand="1">http://wcf.dian.colombia/IWcfDianCustomerServices/SendNominaSyncResponse</a:Action> 
      <o:Security s:mustUnderstand="1" xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-
1.0.xsd"> 
         <u:Timestamp u:Id="_0"> 

---

## Página 254

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 254 de 269 
 
            <u:Created>2021-01-02T07:27:17.048Z</u:Created> 
            <u:Expires>2021-01-02T07:32:17.048Z</u:Expires> 
         </u:Timestamp> 
      </o:Security> 
   </s:Header> 
   <s:Body> 
      <SendNominaSyncResponse xmlns="http://wcf.dian.colombia"> 
         <SendNominaSyncResult xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse" 
xmlns:i="http://www.w3.org/2001/XMLSchema-instance"> 
            <b:ErrorMessage xmlns:c="http://schemas.microsoft.com/2003/10/Serialization/Arrays"/> 
            <b:IsValid>true</b:IsValid> 
            <b:StatusCode>00</b:StatusCode> 
            <b:StatusDescription> Procesado Correctamente </b:StatusDescription> 
            <b:StatusMessage> Documento Nomina  689, ha sido autorizada.</b:StatusMessage>            
<b:XmlBase64Bytes>PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiIHN0YW5kYWxvbmU9Im5vIj8+……………. 
+DQogICAgPC9jYWM6TGluZVJlc3BvbnNlPg0KICA8L2NhYzpEb2N1bWVudFJlc3BvbnNlPg0KPC9BcHBsaWNhdGlvblJlc3BvbnNlPg==<
/b:XmlBase64Bytes> 
<b:XmlBytes i:nil="true"/> 
        
<b:XmlDocumentKey>660ebb7fdd77b6d67a00448e7afde2959992c53ad1bf14b9a394272c56ee8cc64b75dc08940625e39390a0af
3d8d7cb9</b:XmlDocumentKey> 
            <b:XmlFileName>Nomina (1)-firmado-SHA256</b:XmlFileName> 
         </SendNominaSyncResult> 
      </SendNominaSyncResponse> 
   </s:Body> 
</s:Envelope> 
 
9.8. WS Consulta del estado de DE – GetStatus. 
 Función: Recibir una consulta para obtener el estado del documento en el proceso de validación y 
devuelve respuesta del estado del documento.  
 Proceso: Sincrónico 
 Método: GetStatus 
 
9.8.1. Descrición de procesamiento. 
Este servicio atiende la funcionalidad de consultar el estado del documento registrado en la DIAN, por medio 
del CUNE retornando el estado. 

---

## Página 255

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 255 de 269 
 
Este servicio estará disponible en los ambientes de producción en habilitación y producción en operación; 
es el mismo método actual que se usa para consultar documentos electrónicos de Factura Electronica en 
Validación Previa. 
 
9.8.2. Mensaje de petición. 
Operación : GetStatus 
Descripción: Operación que realiza la consulta del estado de validación de documentos 
electrónicos incluyendo tipo NominaIndividual y NominaIndividualAjuste. 
Request 
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia"> 
   <soap:Header/> 
   <soap:Body> 
      <wcf:GetStatus> 
         <!--Optional:--> 
      
<wcf:trackId>660ebb7fdd77b6d67a00448e7afde2959992c53ad1bf14b9a394272c56ee8cc64b75dc08940625e39390a0af3d8d7cb9</wcf:trackId> 
      </wcf:GetStatus> 
   </soap:Body> 
</soap:Envelope> 
Response 
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://www.w3.org/2005/08/addressing" 
xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"> 
   <s:Header> 
      <a:Action s:mustUnderstand="1">http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatusResponse</a:Action> 
      <o:Security s:mustUnderstand="1" xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"> 
         <u:Timestamp u:Id="_0"> 
            <u:Created>2021-01-02T09:54:14.154Z</u:Created> 
            <u:Expires>2021-01-02T09:59:14.154Z</u:Expires> 
         </u:Timestamp> 
      </o:Security> 
   </s:Header> 
   <s:Body> 
      <GetStatusResponse xmlns="http://wcf.dian.colombia"> 
         <GetStatusResult xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse" xmlns:i="http://www.w3.org/2001/XMLSchema-
instance"> 
            <b:ErrorMessage xmlns:c="http://schemas.microsoft.com/2003/10/Serialization/Arrays"> 
               <c:string>Regla: NIE901, Rechazo: Error al validar regla Nómina Individual Electrónica - NominaIndividual (raíz): Namespace prefix 'xmlns' 
has not been declared</c:string> 
               <c:string>Regla: NIE140, Rechazo: Se debe colocar el Valor Pagado por Bonificación No Salarial</c:string> 
               <c:string>Regla: ZB01, Rechazo: Fallo en el schema XML del archivo (Nomina Individual) - The complexType 
'urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2:AmountType' has already been declared. -</c:string> 
               <c:string>Regla: NIE060, Notificación: Se debe colocar el Nombre del Cargo que el Trabajador ocupa en la empresa. Manejo 
Interno</c:string> 
            </b:ErrorMessage> 

---

## Página 256

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 256 de 269 
 
            <b:IsValid>false</b:IsValid> 
            <b:StatusCode>99</b:StatusCode> 
            <b:StatusDescription>Validación contiene errores en campos mandatorios.</b:StatusDescription> 
            <b:StatusMessage>Documento con errores en campos mandatorios.</b:StatusMessage> 
 <b:XmlBase64Bytes>PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiIHN0YW5kYWxvbmU9Im5vIj8+……………. 
+DQogICAgPC9jYWM6TGluZVJlc3BvbnNlPg0KICA8L2NhYzpEb2N1bWVudFJlc3BvbnNlPg0KPC9BcHBsaWNhdGlvblJlc3BvbnNlPg==</b:XmlBase64By
tes> 
<b:XmlBytes i:nil="true"/> 
            
<b:XmlDocumentKey>660ebb7fdd77b6d67a00448e7afde2959992c53ad1bf14b9a394272c56ee8cc64b75dc08940625e39390a0af3d8d7cb9</b:
XmlDocumentKey> 
            <b:XmlFileName>Nomina Individual Electronica-firmado-SHA256</b:XmlFileName> 
         </GetStatusResult> 
      </GetStatusResponse> 
   </s:Body> 
</s:Envelope> 
 

---

## Página 257

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 257 de 269 
 
10. Campos definidos en las extensiones. 
Se establece por la DIAN como uso obligatorio por lo menos una Extensión que corresponde a la de la Firma 
Digital “ds:Signature” la cual esta informada en el numeral 4.2 y cuya extensión debe ser la ultima expresada 
en el grupo ext:UBLExtensions. 
10.1. Estructura para reporte de información adicional específica de cada sector. 
Este suplemento tiene por objeto explicar el uso de grupos de información opcional a nivel de 
cabecera, que faciliten el reporte de información de una operación comercial para un sector 
particular y cuya información no pueda  ser incluida en los grupos establecidos por el estándar XML 
del “Anexo Técnico Documento Soporte de Pago de Nómina Electrónica”. 
Esta información no será sujeta a validaciones por parte de la DIAN. 
11. Elemento Novedad. 
Dentro del documento electrónico Documento Soporte de Pago de Nómina Electrónica (NominaIndividual), 
se ha introducido un elemento el  cual es llamado Novedad. Éste elemento posee las siguientes 
caracteristicas, de acuerdo con el Artículo 1, Numeral 13 de la presente resolución, a saber: 
Novedades reportadas dentro del periodo: Las novedades reportadas dentro del periodo, son un elemento 
que permite informar aquellos eventos que se suscitan dentro del periodo de pago y que afectan la 
liquidación de los valores devengados de nómina y los valores deducidos de nómina, este elemento deberá 
informarse en la forma prevista según se define en el presente anexo técnico. 

---

## Página 258

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 258 de 269 
 
12. Preguntas Frecuentes. 
1. Como puedo agregar en el Documento Soporte de Pago de Nómina Electrónica los Retroactivos? 
R/: Los Retroactivos pueden ser agregados en el Documento Soporte de Pago de Nómina Electrónica 
dentro de la Ruta “/NominaIndividual/Devengados/OtrosConceptos/OtroConcepto” en la cual deberá 
agregar los datos de Descripción y el Pago Salarial respectivo a dicho trabajador. Con respecto a las 
Deducciones a que haya lugar con ese Concepto, deberán ser tenidas en cuenta en dicho documento 
XML en las Rutas que correspondan. 
 
13. Servicio de Consulta. 
13.1. Servicio de consulta a través de Código Bidimensional QR. 
 
Para la representación gráfica de las nóminas individuales electrónicas y nóminas Individual de Ajustes 
electrónicas, es requisito la generación de un código QR con la siguiente información: 
 
Documento Soporte de Pago de Nómina Electrónica: 
Detalle: Xpath: 
NumNIE: [NUMERO_NOMINAINDIVIDUAL] /NominaIndividual/NumeroSecuenciaXML/@Numero 
FecNIE: [FECHA_NOMINAINDIVIDUAL] /NominaIndividual/InformacionGeneral/@FechaGen 
HorNIE: [HORA_NOMINAINDIVIDUAL(con 
GMT)] /NominaIndividual/InformacionGeneral/@HoraGen 
NitNIE: [NIT 
EMISOR_NOMINAINDIVIDUAL] /NominaIndividual/Empleador/@NIT 
DocEmp: [NUMERO_ID_EMPLEADO] /NominaIndividual/Trabajador/@NumeroDocumento 
ValDev: [VALOR_DEVENGADO_TOTAL] /NominaIndividual/DevengadosTotal 
ValDed: [VALOR_DEDUCCION_TOTAL] /NominaIndividual/DeduccionesTotal 
ValTol: 
[VALOR_TOTAL_NOMINAINDIVIDUAL /NominaIndividual/ComprobanteTotal 
CUNE: [CUNE] /NominaIndividual/InformacionGeneral/@CUNE 
QRCode: /NominaIndividual/CodigoQR 
 
Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica (Opción Reemplazar): 
Detalle: Xpath: 
NumNIE: 
[NUMERO_NOMINAINDIVIDUALDEAJUSTE
] 
/NominaIndividualDeAjuste/Reemplazar/NumeroSecuenciaXML/@
Numero 
FecNIE: 
[FECHA_NOMINAINDIVIDUALDEAJUSTE] 
/NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@Fec
haGen 
HorNIE: /NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@Hor

---

## Página 259

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 259 de 269 
 
[HORA_NOMINAINDIVIDUALDEAJUSTE(co
n GMT)] 
aGen 
TipoNota: [TIPO_NOTA] /NominaIndividualDeAjuste/TipoNota 
NitNIE: [NIT 
EMISOR_NOMINAINDIVIDUALDEAJUSTE] /NominaIndividualDeAjuste/Reemplazar/Empleador/@NIT 
DocEmp: [NUMERO_ID_EMPLEADO] /NominaIndividualDeAjuste/Reemplazar/Trabajador/@NumeroDoc
umento 
ValDev: [VALOR_DEVENGADO_TOTAL] /NominaIndividualDeAjuste/Reemplazar/DevengadosTotal 
ValDed: [VALOR_DEDUCCION_TOTAL] /NominaIndividualDeAjuste/Reemplazar/DeduccionesTotal 
ValTol: 
[VALOR_TOTAL_NOMINAINDIVIDUALDEAJ
USTE 
/NominaIndividualDeAjuste/Reemplazar/ComprobanteTotal 
CUNE: [CUNE] /NominaIndividualDeAjuste/Reemplazar/InformacionGeneral/@CU
NE 
QRCode: /NominaIndividualDeAjuste/Reemplazar/CodigoQR 
 
Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica (Opción Eliminar): 
Detalle: Xpath: 
NumNIE: 
[NUMERO_NOMINAINDIVIDUALDEAJUSTE] 
/NominaIndividualDeAjuste/Eliminar/NumeroSecuenciaXML/@Nu
mero 
FecNIE: 
[FECHA_NOMINAINDIVIDUALDEAJUSTE] 
/NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@Fecha
Gen 
HorNIE: 
[HORA_NOMINAINDIVIDUALDEAJUSTE(con 
GMT)] 
/NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@Hora
Gen 
TipoNota: [TIPO_NOTA] /NominaIndividualDeAjuste/TipoNota 
NitNIE: [NIT 
EMISOR_NOMINAINDIVIDUALDEAJUSTE] /NominaIndividualDeAjuste/Eliminar/Empleador/@NIT 
DocEmp: [NUMERO_ID_EMPLEADO] 0 
ValDev: [VALOR_DEVENGADO_TOTAL] 0.00 
ValDed: [VALOR_DEDUCCION_TOTAL] 0.00 
ValTol: 
[VALOR_TOTAL_NOMINAINDIVIDUALDEAJU
STE 
0.00 
CUNE: [CUNE] /NominaIndividualDeAjuste/Eliminar/InformacionGeneral/@CUNE 
QRCode: /NominaIndividualDeAjuste/Eliminar/CodigoQR 
 
 
 

---

## Página 260

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 260 de 269 
 
NumNIE: [NUMERO_NOMINAINDIVIDUAL] 
FecNIE: [FECHA_NOMINAINDIVIDUAL] 
HorNIE: [HORA_NOMINAINDIVIDUAL(con GMT)] 
NitNIE: [NIT EMISOR_NOMINAINDIVIDUAL] sin puntos ni guiones 
DocEmp: [NUMERO_ID_EMPLEADO] sin puntos ni guiones 
ValDev: [VALOR_DEVENGADO_TOTAL] con punto decimal, con decimales a dos (2) dígitos, sin separadores de 
miles, ni símbolo pesos. 
ValDed: [VALOR_DESDUCCION_TOTAL] con punto decimal, con decimales a dos (2) dígitos, sin separadores de 
miles, ni símbolo pesos. 
ValTol: [VALOR_TOTAL_NOMINAINDIVIDUAL con punto decimal, con decimales a dos (2) dígitos, sin separadores 
de miles, ni símbolo pesos. 
CUNE: [CUNE] 
QRCode: URL disponible por la DIAN  
 Ambiente Habilitación: https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey=CUNE 
 Ambiente Producción: https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey=CUNE 
 
Ejemplo: 
Teniendo en cuenta los datos de entrada, se presenta el código QR que se incluye en la representación gráfica 
del Documento Soporte de Pago de Nómina Electrónica: 
 
NumNIE: 323200000129 
FecNIE: 2019-16-01 
HorNIE: 10:53:10-05:00 
NitNIE: 700085371 
DocEmp: 800199436 
ValDev: 1500000.00 
ValDed: 285000.00 
ValTol: 1785000.00 
CUNE: e5bac48e354bc907bccff0ea7d45fbf784f0a8e7243b58337361e1fbd430489d 
https://catalogo-
vpfe.dian.gov.co/document/searchqr?documentkey=e5bac48e354bc907bccff0ea7d45fbf784f0a8e7243b5833
7361e1fbd430489d  
 
Figura 1. - Ejemplo de código bidimensional QR 
 
Tamaño: 
El tamaño mínimo que debe tener el código bidimensional QR es de 2cm para facilitar la lectura por los diferentes 
dispositivos. 
 
La Representación Gráfica: 

---

## Página 261

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 261 de 269 
 
La representación gráfica puede ser diseñada de acuerdo con las necesidades del Emisor del Documento Soporte 
de Pago de Nómina Electrónica y las Notas de Ajuste del mencionado documento ; como la generación está en 
formato XML, entonces cualquier herramienta informática de conversión de este formato a .pdf, .docx, u otros 
formatos digitales podrá ser utilizada, en todo caso deberá tener el código bidimensional QR tal como ya se 
indicó, según corresponda, ya que el mismo es el que permite la consulta de los documentos validados.  
 
Una alternativa a dicional a los formatos digitales es la  posibilidad de generar impresión en papel de la 
representación gráfica diseñada, la cual deberá de igual forma tener el código bidimensional QR. 
 
La representación gráfica debe incluir el código QR en todas las páginas de los formatos digitales y de la impresión 
en papel del Documento Soporte de Pago de Nómina Electrónica y Nota de Ajuste de Documento Soporte de 
Pago de Nómina Electrónica. 
 
La representación gráfica sie mpre será “una representación, una imagen” de la información consignada en el 
formato XML de los perfiles de la DIAN. Esto significa que el documento electrónico siempre será el que tenga 
valor legal para las autoridades nacionales. Si cualquier persona re quiere validar la autenticidad de una 
representación gráfica, entonces deberá acceder al sitio web que la DIAN disponga para ello, activar el 
hiperenlace, diligenciar los campos de información, disparar el botón de Validación, y comparar lo que le muestra 
la respuesta devuelta por el sistema de emisión del Documento Soporte de Pago de Nómina Electrónica de la 
DIAN con lo que le exhibe la representación que tiene a la mano, y proceder en consecuencia. Si la información 
difiere, podrá denunciar el hecho a la DIAN, porque puede tratarse de un documento apócrifo, sin validez legal, 
y que podría ser la evidencia de una acción que amerita ser investigada fiscalmente. 
 
14. Anexo: Herramienta para el consumo de Web Services. 
14.1. Introducción 
SoapUI es una herramienta, para la realización de pruebas a aplicaciones con arquitectura orientada 
a servicio (SOA). Soporta múltiples protocolos como SOAP, por tanto es adecuada para realizar 
pruebas del web services DIAN y sus distintos métodos. 
A continuación, se entregan lineamientos para su uso y configuración. 
 
14.2. Descargar SOAP UI. 
La descarga de la herramienta se recomienda hacerla visitando el sitio oficial de SOAP UI, en el link 
que se deja a continuación. 
https:/www.soapui.org/downloads/soapui.html 
 
14.3. Ejecutar SOAP UI. 
Una vez descargada la herramienta e instalada se procede a ejecutar la aplicación. 
 
14.4. Crear un nuevo proyecto tipo SOAP. 

---

## Página 262

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 262 de 269 
 
Para crear un nuevo proyecto de tipo SOAP de clic en el menú File/New SOAP Project como se 
muestra a continuación. 
 
 
Ilustración 1. Crear nuevo proyecto 
 
14.5. Configuración inicial. 
En la configuración inicial debe ingresar el nombre del proyecto y cargar la url WSDL como se muestra 
en la siguiente imagen. 
 
 
Ilustración 2. Configuración carga inicial 
 
Nota: la URL del Web Service “WS” estará expuesta en el catalogo de participante (habilitación ó 
producción) sobre la opción Participantes, Emisor de Nómina. 
 
14.6. Configurar Keystore. 


---

## Página 263

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 263 de 269 
 
Debe agregar un nuevo certificado y su contraseña. 
 
 
Ilustración 3. Configuración keystore 
 
14.7. Configurar WS-Security Signature. 
Inicialmente se debe agregar una nueva configuración colocándole un nombre. Se agrega una nueva 
entrada de WS-Security Signature y automáticamente se muestra un formulario en blanco donde se 
debe agregar el certificado y su contraseña configurado en el paso anterior.  
Los próximos campos a completar debe tener los mismos valores que se indican en la imagen a 
continuación. 
 


---

## Página 264

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 264 de 269 
 
 
Ilustración 4. Configuración WS-Security Signature 
 
14.8. Configurar TimeStamp. 
La configuración del tiempo de vigencia del token de seguridad (Timestamp) debe ser configurado en 
milisegundos. 
 
 
Ilustración 5. Configuración WS-Security Timestamp 
 
14.9. Configurar GetStatus Request, Authentication y WS-A addressing. 
En la configuración de GetStatus Request se debe configurar la autenticación. Debe agregar 


---

## Página 265

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 265 de 269 
 
autorización básica y seleccionar la configuración WS-Security creada y configurada previamente. 
 
 
Ilustración 6. Configuración de autenticación 
Además, para configurar WS-A addressing se deben habilitar las opciones WS-A addressing y wsa:To 
como se muestra en la imagen siguiente.  
 


---

## Página 266

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 266 de 269 
 
 
 
Ilustración 7. Configuración WS-A addressing 
 
14.10. Configurar y ejecutar GetStatus Request. 
Para ejecutar el Request se debe ingresar un TrackId. En la derecha se muestra el resultado de la 
ejecución donde el XMLBytes representa el arreglo de bytes del ApplicationResponse. 
 


---

## Página 267

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 267 de 269 
 
 
Ilustración 8. Configuración y ejecución GetStatus Request 
 
14.11. Configurar y ejecutar SendBillAsync Request. 
Para ejecutar SendBillAsync Request se debe agregar el nombre del archivo .zip, cargar los XMLs 
adjuntos, seleccionar Part. y habilitar Cached. 
 


---

## Página 268

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 268 de 269 
 
 
Ilustración 9. Configuración SendBillAsync Request 
 
14.12. SendBillAsync Response. 
El resultado del SendBillAsync Request se muestra a continuación en la siguiente imagen. 
 


---

## Página 269

 
 
                                                         Resolución No. 000013 
  
 (11 FEB 2021) 
 
Anexo Técnico Documento Soporte de Pago de Nómina Electrónica – Versión 1.0  
 
 
Dirección de Gestión de Ingresos     
Carrera 8 Nº 6C-38 piso 6º   PBX 607 9999 – 382 4500 Ext. 905101 
Código postal 111711 
www.dian.gov.co 
Formule su petición, queja, sugerencia o reclamo en el Sistema PQSR de la DIAN      
              
         Página 269 de 269 
 
 
Ilustración 10. Configuración SendBillAsync Soap response 
 
14.13. Recomendaciones. 
Se recomienda después de crear o actualizar la configuración del WS -Security eliminar  
el request anterior y crear uno nuevo. Estos no ven reflejados las actualizaciones de la  
configuración global. 
 
15. Control de cambios. 
Primera Versión del Documento. 
Versión #9.3 
 
 
                                                 


---

