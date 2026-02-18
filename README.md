# Guapante — Odoo 18 SH

Tema y módulo de eCommerce para [Comercializadora Guapante](https://guapante.com).

## Estructura del repositorio

```
theme_guapante/       ← Addon Odoo 18 (se despliega en SH)
  ├── __manifest__.py
  ├── controllers/    (auth_signup, shop, customer_portal)
  ├── models/         (product_template, res_users, sale_order, etc.)
  ├── views/          (layout, shop, portal, auth, snippets)
  ├── static/         (SCSS, JS, imágenes)
  ├── security/       (ACLs)
  ├── i18n/           (traducciones es.po)
  └── tests/          (suite de tests Python)

Mockup website/       ← Referencia de diseño React/Vite (NO se despliega)
```

## Instalación en Odoo SH

1. Conectar este repositorio como fuente en Odoo SH
2. `theme_guapante` será detectado automáticamente como addon
3. Instalar desde **Apps** → buscar "Guapante"

## Dependencias

`website`, `website_sale`, `auth_signup`, `l10n_co`, `stock`, `fleet`

## Tests

Los tests se ejecutan automáticamente en Odoo SH al hacer push. Para correrlos localmente:

```bash
odoo-bin -d <db> -i theme_guapante --test-enable --stop-after-init
```

## Versión actual

**2.0.2** — Incluye seguridad, i18n, y suite de tests.