# -*- coding: utf-8 -*-
{
    'name': 'Abershum Lab',
    'version': '1.0',
    'summary': 'Sync lab test orders from Odoo to OpenELIS',
    'sequence': 10,
    'description': """
Abershum ELIS Sync
==================
This module syncs lab test orders from Odoo to OpenELIS when sale orders are confirmed.
It automatically identifies lab test products and sends them to OpenELIS via REST API.
    """,
    'category': 'Sales',
    'website': '',
    'icon': 'abershum_elis_sync/static/src/img/abershum-logo.png',
    'images': [],
    'depends': ['base', 'sale', 'bahmni_sale'],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        # Security must be loaded first
        'security/security_groups.xml',  # Create groups first
        'security/ir.model.access.csv',  # Basic access rules
        'security/ir_model_access_failed_event.xml',  # Failed event access (uses XML to reference group)
        'security/ir_rule_failed_event.xml',  # Then record rules
        # Seed Data
        'data/openelis_department_data.xml',
        'data/openelis_sample_type_data.xml',
        # Data files
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        # Views
        'views/openelis_failed_event_views.xml',
        'views/res_config_settings_view.xml',
        'views/res_partner_view.xml',
        'views/product_template_view.xml',
        'views/sale_order_view.xml',
        'views/openelis_master_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'abershum_elis_sync/static/src/js/navbar.js',
            'abershum_elis_sync/static/src/xml/navbar.xml',
        ],
    },
    'demo': [],
    'qweb': [],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
