# -*- coding: utf-8 -*-
{
    'name': 'Abershum Theme',
    'version': '1.0',
    'summary': 'Modern backend theme for Bahmni Odoo',
    'sequence': 5,
    'description': """
Abershum Theme
==============
Modern and minimalist backend theme for Bahmni Odoo.
Features:
- Custom sidebar navigation
- Modern top bar styling
- Clean color scheme
- Custom menu icons
    """,
    'category': 'Themes/Backend',
    'website': '',
    'images': [],
    'depends': ['base', 'web', 'mail'],
    'data': [
        'views/layout.xml',
        'views/icons.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'abershum_theme/static/src/scss/variables.scss',
            'abershum_theme/static/src/scss/navigation_bar.scss',
            'abershum_theme/static/src/scss/style.scss',
            'abershum_theme/static/src/scss/sidebar.scss',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
