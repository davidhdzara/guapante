"""Capa de servicios para nómina electrónica DIAN — Colombia.

Módulos puros de Python (sin dependencias de Odoo) que implementan:
- Utilidades DIAN (DV, NIT, tipos de documento)
- Cálculo de CUNE (Código Único de Nómina Electrónica)
- Firmado XAdES-BES de XML
- Cliente SOAP para web services DIAN
- Constructor de XML de Nómina Individual Electrónica
- Generador de archivo plano PILA
"""

from . import dian_utils
from . import cune
from . import xml_signer
from . import soap_client
from . import nomina_xml_builder
from . import pila_generator_v2
