{
    'name': 'Bahmni POS',
    'version': '1.0',
    'summary': 'Decoupled POS functionality for Bahmni',
    'category': 'Point of Sale',
    'depends': ['bahmni_sale', 'point_of_sale'],
    'data': [
        'views/pos_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
