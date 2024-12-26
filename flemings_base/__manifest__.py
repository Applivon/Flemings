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
    'depends': [
        'base', 'base_setup', 'web', 'crm', 'sale', 'purchase', 'account', 'stock',
        'l10n_sg', 'point_of_sale', 'delivery', 'report_xlsx', 'mrp', 'sale_stock',
        'uom', 'sale_management', 'spreadsheet_dashboard', 'hr', 'hr_contract',
        'hr_holidays', 'hr_expense', 'hr_attendance', 'hr_timesheet', 'hr_timesheet_attendance',
        'sg_hr_report', 'sg_hr_employee'
    ],
    'data': [
        # Data
        'data/data.xml',

        # Security
        'security/security.xml',
        'security/ir.model.access.csv',

        # Views
        'views/res_users_view.xml',
        'views/views.xml',
        'views/purchase_view.xml',
        'views/stock_low_view.xml',
        'views/hide_menus_view.xml',

        # Wizard
        'wizard/flemings_purchase_price_report_view.xml',
        'wizard/purchase_cogs_summary_report_view.xml',
        'wizard/cogs_detailed_report_view.xml',
        'wizard/open_invoice_report_view.xml',
        'wizard/do_not_invoiced_report_view.xml',
        'wizard/gross_profit_report_view.xml',
        'wizard/soa_view.xml',
        'wizard/delivery_order_xls_view.xml',
        'wizard/credit_note_xls_view.xml',
        'wizard/tax_invoice_xls_view.xml',
        'wizard/work_order_summary_report_view.xml',
        'wizard/purchase_audit_list_summary_view.xml',
        'wizard/inventory_detailed_report_view.xml',
        'wizard/salary_summary_report_view.xml',

        # Report
        'report/base_report.xml',
        'report/sales_order_report.xml',
        'report/purchase_order_report.xml',
        'report/tax_invoice_report.xml',
        'report/credit_note_report.xml',
        'report/delivery_order_report.xml',
        'report/soa_reports.xml',
        'report/work_order_summary_report.xml',

    ],
    'qweb': [],
    'images': ['static/description/applivon-logo.jpg'],
    'installable': True,
    'application': True,
    'auto_install': False,

    'assets': {}

}

