# -*- coding: utf-8 -*-
{
    'name': 'Abershum Login Custom',
    'version': '1.0',
    'summary': 'Customize login/signup page styling for Bahmni Odoo',
    'sequence': 10,
    'description': """
Abershum Login Custom
=====================
This module provides customizable login and signup page styling for Bahmni Odoo.
Features:
- Custom background (color, image, or URL)
- Login card positioning (left, center, right)
- Admin configuration via Settings panel
    """,
    'category': 'Website',
    'website': '',
    'images': [],
    'depends': ['base', 'web'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/login_templates.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
