# -*- coding: utf-8 -*-

# Clave de sesión de navegador para la identificación por PIN del operario en el paso de
# pesaje (Preparation Day) — constante única, importada por el controlador de
# identificación y por el modelo que la lee en action_save_line_weight(), para no duplicar
# el string literal entre los dos (gap de la Fase 1 original, cerrado en este módulo).
PREP_OPERATOR_SESSION_KEY = 'guapante_prep_employee_id'
