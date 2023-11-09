import time
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta


class FlemingsPurchasePriceReport(models.TransientModel):
    _name = 'flemings.purchase.price.report.wizard'
    _description = 'Purchase Price Report'

    def _get_default_from_date(self):
        return str(datetime.now() + relativedelta(day=1))[:10]

    def _get_default_to_date(self):
        return str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10]

    from_date = fields.Date('From Date', default=_get_default_from_date)
    to_date = fields.Date('To Date', default=_get_default_to_date)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)
    product_ids = fields.Many2many('product.product', string='Product(s)')
    partner_ids = fields.Many2many('res.partner', string='Vendor(s)', domain="[('supplier_rank', '>', 0), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    file_data = fields.Binary('Download file', readonly=True)
    filename = fields.Char('Filename', size=64, readonly=True)

    @api.onchange('from_date', 'to_date')
    def onchange_to_date(self):
        if self.to_date and self.from_date and self.to_date < self.from_date:
            self.to_date = False
            return {'warning': {
                'title': _("Warning"),
                'message': _("To Date must be greater than or equal to From Date..!")}
            }

    def get_vendor_purchase_price_data(self, vendor_id, purchase_order_ids):
        where = "AND po.partner_id = %d " % vendor_id.id

        if purchase_order_ids:
            order_ids = tuple(purchase_order_ids)
            if len(order_ids) == 1:
                where += " AND po.id = %s" % order_ids
            else:
                where += " AND po.id in %s" % (order_ids,)

        if self.product_ids:
            product_ids = tuple(self.product_ids.ids)
            if len(product_ids) == 1:
                where += " AND pol.product_id = %s" % product_ids
            else:
                where += " AND pol.product_id in %s" % (product_ids,)

        self.env.cr.execute(""" SELECT to_char(po.date_approve, 'DD/MM/YY') AS po_date, 
           product.variant_name AS product_name, pol.product_qty, 
           uom.name::json->>'en_US' AS purchase_uom, currency.name AS currency_name, 
           pol.price_unit, pol.price_subtotal

           FROM purchase_order AS po
           LEFT JOIN purchase_order_line AS pol ON pol.order_id = po.id
           LEFT JOIN product_product AS product ON product.id = pol.product_id
           LEFT JOIN res_currency AS currency ON currency.id = pol.currency_id
           LEFT JOIN uom_uom AS uom ON uom.id = pol.product_uom
           
           WHERE 1=1 %s ORDER BY po.date_approve DESC """ % where)

        return [i for i in self.env.cr.dictfetchall()]

    def generate_excel_report(self):
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'flemings_base.flemings_purchase_price_report_wizard_xlsx'
        }


class FlemingsPurchasePriceReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.flemings_purchase_price_report_wizard_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Purchase Price Report'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('PURCHASE PRICE REPORT')

        align_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        align_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True})
        align_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        align_bold_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True, 'border': 1})

        for obj in objects:
            sheet.set_row(0, 20)
            sheet.set_row(1, 20)
            sheet.set_row(3, 35)

            sheet.set_column('A:A', 15)
            sheet.set_column('B:B', 35)
            sheet.set_column('C:C', 12)
            sheet.set_column('D:D', 20)
            sheet.set_column('E:E', 15)
            sheet.set_column('F:F', 18)
            sheet.set_column('G:G', 18)

            date_from = datetime.strftime(obj.from_date, '%d/%m/%Y')
            date_to = datetime.strftime(obj.to_date, '%d/%m/%Y')
            purchase_period = str(date_from) + ' - ' + str(date_to)

            sheet.merge_range(0, 3, 0, 0, 'PURCHASE PRICE REPORT', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True}))
            sheet.merge_range(1, 3, 1, 0, 'Period : ' + purchase_period, workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'num_format': 'dd/mm/yyyy'}))

            vendor_domain = [('date_approve', '>=', obj.from_date), ('date_approve', '<=', obj.to_date), ('state', 'in', ('purchase', 'done'))]
            if obj.partner_ids:
                vendor_domain.append(('partner_id', 'in', obj.partner_ids.ids or []))

            purchase_orders = self.env['purchase.order'].sudo().search(vendor_domain)
            purchase_order_ids = purchase_orders.mapped('id')
            vendors = purchase_orders.mapped('partner_id')

            row = 3
            for vendor_id in vendors:
                line_data = obj.get_vendor_purchase_price_data(vendor_id, purchase_order_ids)
                if line_data:
                    sheet.write(row, 0, 'Vendor', align_bold_left)
                    sheet.write(row, 1, vendor_id.name, align_left)
                    row += 1

                    titles = ['Date', 'Product Name', 'Qty', 'UOM', 'Currency', 'Unit Price', 'Sub-Total']
                    for index in range(0, len(titles)):
                        sheet.write(row, index, titles[index], align_bold_center)
                    row += 1

                    vendor_total = 0
                    for line in line_data:
                        sheet.write(row, 0, line['po_date'], align_center)
                        sheet.write(row, 1, line['product_name'], align_left)
                        sheet.write(row, 2, line['product_qty'], align_right)
                        sheet.write(row, 3, line['purchase_uom'], align_left)
                        sheet.write(row, 4, line['currency_name'], align_left)
                        sheet.write(row, 5, str('%.2f' % line['price_unit']), align_right)
                        sheet.write(row, 6, str('%.2f' % line['price_subtotal']), align_right)

                        vendor_total += line['price_subtotal']
                        row += 1

                    sheet.write(row, 5, 'Total', align_bold_right)
                    sheet.write(row, 6, str('%.2f' % vendor_total), align_bold_right)
                    row += 3
