# -*- coding: utf-8 -*-
{
    'name': 'Radiology Application (Orthanc Integration)',
    'version': '16.0.1.0.0',
    'category': 'Sales/Radiology',
    'summary': 'Integration with Orthanc for Radiology Orders',
    'description': """
        Radiology Application for Odoo 16 with Orthanc Integration.
        - Radiology Product Configuration
        - Orthanc Order Generation from Sales
        - Radiology Reporting with Audit Trail
        - Access Control for Radiologists and Assistants
    """,
    'author': 'Abershum Labs',
    'website': 'https://abreshum.com',
    'depends': [
        'base', 
        'sale_management', 
        'product', 
        'mail',
        'bahmni_sale'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/cancel_reason_wizard_view.xml',
        'views/orthanc_order_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_sequence_data.xml',
        'views/product_views.xml',
        'views/res_partner_views.xml',
        'views/provider_views.xml',
        'reports/radiology_report.xml',
        'reports/report_actions.xml',
        'data/mail_template_data.xml',  # Must load after report_actions.xml
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
