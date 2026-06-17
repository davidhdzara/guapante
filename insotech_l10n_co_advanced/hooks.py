import json
import os
import logging

_logger = logging.getLogger(__name__)

def post_init_hook(env):
    """
    Carga los códigos postales 'Urbanos' desde el JSON generado
    hacia el campo zipcode de res.city, usando el código DANE.
    """
    _logger.info("Iniciando la actualización de códigos postales (Urbano)...")
    
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'postal_codes.json')
    if not os.path.exists(file_path):
        _logger.warning("Archivo postal_codes.json no encontrado.")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    if not mapping:
        return

    # Extraemos todos los códigos l10n_co_edi_code de la base de datos
    cities = env['res.city'].search([('l10n_co_edi_code', '!=', False)])
    
    updated_count = 0
    for city in cities:
        dane_code = city.l10n_co_edi_code
        if not dane_code: continue
        dane_lookup = dane_code.zfill(5)
        if dane_lookup in mapping:
            if not city.zipcode:
                city.write({'zipcode': mapping[dane_lookup]})
                updated_count += 1
                
    _logger.info(f"Se actualizaron exitosamente {updated_count} códigos postales.")
