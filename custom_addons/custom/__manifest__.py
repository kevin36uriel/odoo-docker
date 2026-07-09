{
    'name': "Punto Singular - Branding",
    'summary': "Identidad visual de Punto Singular: logo, favicon, colores de reportes y del backend.",
    'description': """
Aplica la identidad visual de Punto Singular a la instancia de Odoo:

- Logo de la compañía (se usa automáticamente en la pantalla de login y en el
  encabezado de los reportes PDF).
- Favicon del navegador.
- Colores de marca en los reportes PDF (base.document.layout).
- Colores de marca en el backend (barra superior, botones y enlaces).
""",
    'version': '18.0.1.0.0',
    'category': 'Theme',
    'author': "Punto Singular",
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [
        'views/webclient_templates.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            (
                'before',
                'web/static/src/scss/primary_variables.scss',
                'custom/static/src/scss/primary_variables.scss',
            ),
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
