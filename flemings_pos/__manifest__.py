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
    'depends': ['flemings_base','point_of_sale'],
    'data': [
        'report/EOD.xml',
        'report/customer_invoice.xml',
        'views/pos_payment_method.xml',
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
            "flemings_pos/static/xml/pos_receipt.xml",
            "flemings_pos/static/css/style.css",
            # "flemings_pos/static/js/customer_receipt.js",
            "flemings_pos/static/js/CustomPrintReceipt.js",
            "flemings_pos/static/js/PaymentScreenCustom.js",
            "flemings_pos/static/js/CustomReprint.js",
            "flemings_pos/static/js/pos_custom_validate.js"

            ],
        },

}

