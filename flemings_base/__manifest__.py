# -*- coding: utf-8 -*-
###################################################################################
#
###################################################################################
{
    'name': 'Flemings - Base',
    'version': '11.0.1.0.0',
    'summary': 'Base Module',
    'category': 'Dashboard',
    'author': 'Applivon',
    'maintainer': 'Applivon',
    'company': 'Applivon',
    'website': 'https://www.applivon.com',
    'depends': ['base', 'base_setup', 'web', 'crm', 'sale', 'purchase', 'account', 'stock',
                'l10n_sg', 'point_of_sale', 'delivery', 'report_xlsx'],
    'data': [
        # Data
        'data/data.xml',

        # Security
        'security/security.xml',
        'security/ir.model.access.csv',

        # Views
        'views/res_users_view.xml',
        'views/views.xml',

        # Wizard
        'wizard/flemings_purchase_price_report_view.xml',

    ],
    'qweb': [],
    'images': ['static/description/applivon-logo.jpg'],
    'installable': True,
    'application': True,
    'auto_install': False,

    'assets': {}

}

