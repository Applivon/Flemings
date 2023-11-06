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
        'views/stock_low_view.xml',

        # Wizard
        'wizard/flemings_purchase_price_report_view.xml',

        # Report
        'report/base_report.xml',
        'report/sales_order_report.xml',
        'report/delivery_order_report.xml',

    ],
    'qweb': [],
    'images': ['static/description/applivon-logo.jpg'],
    'installable': True,
    'application': True,
    'auto_install': False,

    'assets': {}

}

