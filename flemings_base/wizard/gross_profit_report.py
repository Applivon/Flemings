# -*- coding: utf-8 -*-

from odoo import models, fields, api , _
import time
from dateutil import relativedelta
from datetime import datetime, timedelta


class FGGrossProfitReport(models.TransientModel):
    _name = 'fg.gross.profit.report'
    _description = 'Gross Profit Report'

    date_from = fields.Date('From Date', default=lambda *a: time.strftime('%Y-%m-01'))
    date_to = fields.Date('To Date', default=lambda *a: str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10])
    partner_ids = fields.Many2many('res.partner', string='Customer')
    user_ids = fields.Many2many('res.users', string='Salesperson')
    product_ids = fields.Many2many('product.product', string='Product')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)

    def generate_xlsx_report(self):
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'flemings_base.fg_gross_profit_report_xlsx'
        }

    def get_gross_profit_report_data(self):
        where = "invoice.move_type = 'out_invoice' AND invoice.state = 'posted' " \
                "AND inv_line.product_id IS NOT NULL AND invoice.invoice_date BETWEEN '%s' AND '%s'" \
                "" % (self.date_from, self.date_to)

        if self.company_id:
            where += "AND invoice.company_id = %s" % self.company_id.id

        if self.partner_ids:
            partners = tuple(self.partner_ids.ids)
            if len(partners) == 1:
                where += "AND customer.id = %s" % partners
            else:
                where += "AND customer.id in %s" % (partners,)

        if self.user_ids:
            users = tuple(self.user_ids.ids)
            if len(users) == 1:
                where += "AND salesperson.id = %s" % users
            else:
                where += "AND salesperson.id in %s" % (users,)

        if self.product_ids:
            products = tuple(self.product_ids.ids)
            if len(products) == 1:
                where += "AND prod.id = %s" % products
            else:
                where += "AND prod.id in %s" % (products,)

        self.env.cr.execute("""
            SELECT row_number() over (ORDER BY invoice.invoice_date) AS sno, customer.name AS customer, 
              TO_CHAR(invoice.invoice_date, 'DD-MM-YYYY') AS date, invoice.name AS invoice_no,
              prod.default_code AS sku, prod.variant_name AS prod_name, inv_line.quantity AS quantity,
              inv_line.price_subtotal AS total_excl_gst, inv_line.price_unit AS unit_price, 
              inv_line.unit_cost_price AS unit_cost_price, sales_partner.name AS salesperson, 
              (inv_line.price_subtotal - (inv_line.quantity * inv_line.unit_cost_price)) AS gross_profit_amt,
              CASE WHEN (inv_line.price_subtotal > 0) 
                THEN (((inv_line.price_subtotal - (inv_line.quantity * inv_line.unit_cost_price)) / inv_line.price_subtotal) * 100) 
                ELSE 0 END AS gross_profit_percent
              
              FROM account_move AS invoice
              LEFT JOIN res_users AS salesperson ON salesperson.id = invoice.invoice_user_id
              LEFT JOIN res_partner AS sales_partner ON sales_partner.id = salesperson.partner_id
              LEFT JOIN account_move_line AS inv_line ON inv_line.move_id = invoice.id
              LEFT JOIN product_product AS prod ON prod.id = inv_line.product_id
              LEFT JOIN res_partner AS customer ON customer.id = invoice.partner_id
              
              WHERE %s ORDER BY invoice.invoice_date """ % where)

        line_list = [i for i in self.env.cr.dictfetchall()]
        return line_list


class FGGrossProfitReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.fg_gross_profit_report_xlsx'
    _description = 'Gross Profit Report XLSX'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('GROSS PROFIT REPORT')

        align_left = workbook.add_format({'font_name': 'Arial', 'valign': 'vcenter', 'text_wrap': True})
        align_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True})
        align_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        align_bold_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'bold': True, 'border': 1})

        row = 0
        for obj in objects:
            sheet.set_column('A:A', 10)
            sheet.set_column('B:B', 30)
            sheet.set_column('C:C', 15)
            sheet.set_column('D:D', 20)
            sheet.set_column('E:E', 25)
            sheet.set_column('F:F', 30)
            sheet.set_column('G:G', 35)
            sheet.set_column('H:H', 15)
            sheet.set_column('I:I', 15)
            sheet.set_column('J:J', 18)
            sheet.set_column('K:K', 20)
            sheet.set_column('L:L', 18)
            sheet.set_column('M:M', 18)

            sheet.set_row(row, 35)
            sheet.set_row(row + 2, 25)
            sheet.set_row(row + 2, 18)
            sheet.set_row(row + 3, 18)

            sheet.merge_range(row, 0, row, 6, 'GROSS PROFIT REPORT', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True}))

            row += 2
            sheet.write(row, 0, 'From', align_bold_left)
            sheet.write(row, 1, str(obj.date_from.strftime('%d/%m/%Y')), align_left)

            row += 1
            sheet.write(row, 0, 'To', align_bold_left)
            sheet.write(row, 1, str(obj.date_to.strftime('%d/%m/%Y')), align_left)

            row += 2
            sheet.write(row, 0, 'S.No.', align_bold_center)
            sheet.write(row, 1, 'Customer', align_bold_center)
            sheet.write(row, 2, 'Invoice Date', align_bold_center)
            sheet.write(row, 3, 'Invoice No.', align_bold_center)
            sheet.write(row, 4, 'Salesperson', align_bold_center)
            sheet.write(row, 5, 'SKU', align_bold_center)
            sheet.write(row, 6, 'Product Name', align_bold_center)
            sheet.write(row, 7, 'Quantity', align_bold_center)
            sheet.write(row, 8, 'Unit Price (S$)', align_bold_center)
            sheet.write(row, 9, 'Sub-Total (S$)', align_bold_center)
            sheet.write(row, 10, 'Unit Cost Price (S$)', align_bold_center)
            sheet.write(row, 11, 'Gross Profit ($)', align_bold_center)
            sheet.write(row, 12, 'Gross Profit (%)', align_bold_center)

            line_list = obj.get_gross_profit_report_data()

            if line_list:
                for line in line_list:
                    row += 1
                    sheet.set_row(row, 22)

                    sheet.write(row, 0, line['sno'], align_center)
                    sheet.write(row, 1, line['customer'], align_left)
                    sheet.write(row, 2, line['date'], align_center)
                    sheet.write(row, 3, line['invoice_no'], align_center)
                    sheet.write(row, 4, line['salesperson'], align_left)
                    sheet.write(row, 5, line['sku'], align_left)
                    sheet.write(row, 6, line['prod_name'], align_left)
                    sheet.write(row, 7, line['quantity'], align_center)
                    sheet.write(row, 8, str('%.2f' % line['unit_price']), align_right)
                    sheet.write(row, 9, str('%.2f' % line['total_excl_gst']), align_right)
                    sheet.write(row, 10, str('%.2f' % line['unit_cost_price']), align_right)
                    sheet.write(row, 11, str('%.2f' % line['gross_profit_amt']), align_right)
                    sheet.write(row, 12, str('%.2f' % line['gross_profit_percent']), align_right)
            else:
                sheet.merge_range(row + 2, 0, row + 2, 6, 'No Record(s) found', workbook.add_format(
                    {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True}))
