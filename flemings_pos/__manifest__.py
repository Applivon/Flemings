# -*- coding: utf-8 -*-
###################################################################################
#
###################################################################################
{
    'name': 'Flemings - POS',
    'version': '16.0.1.0.0',
    'summary': 'Base Module',
    'category': 'Dashboard',
    'author': 'Applivon',
    'maintainer': 'Applivon',
    'company': 'Applivon',
    'website': 'https://www.applivon.com',
    'depends': ['flemings_base'],
    'data': [
        'report/EOD.xml',
    ],
    'qweb': [],
    'images': ['static/description/applivon-logo.jpg'],
    'installable': True,
    'application': True,
    'auto_install': False,

   "assets": {
        "point_of_sale.assets": [
            "flemings_pos/static/xml/pos_button.xml",
            "flemings_pos/static/xml/customer_screen.xml",
            ],
        },

}

