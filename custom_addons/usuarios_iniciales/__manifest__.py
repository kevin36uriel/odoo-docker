{
    'name': 'Usuarios Iniciales Automáticos',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Módulo para precargar 4 usuarios al levantar el contenedor',
    'author': 'Kevin',
    'depends': ['base'],
    'data': [
        'data/usuarios.xml',
    ],
    'installable': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}