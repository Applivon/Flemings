import time
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta


class COGSDetailedReport(models.TransientModel):
    _name = 'cogs.detailed.report.wizard'
    _description = 'COGS Report'

    from_date = fields.Date('From Date', default=lambda *a: str(datetime.now() + relativedelta(day=1))[:10])
    to_date = fields.Date('To Date', default=lambda *a: str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10])
    product_ids = fields.Many2many('product.product', string='Product(s)')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Currency')

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

    def generate_excel_report(self):
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'flemings_base.cogs_detailed_report_wizard_xlsx'
        }

    def get_utc_datetime(self, date_time):
        local = pytz.timezone(self.env.user.tz)
        naive = datetime.strptime(str(date_time), "%Y-%m-%d %H:%M:%S")
        local_dt = local.localize(naive, is_dst=None)
        return local_dt.astimezone(pytz.utc)


class FlemingsCOGSDetailedReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.cogs_detailed_report_wizard_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'COGS Report'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('COGS REPORT')

        align_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        align_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True})
        align_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        align_bold_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True, 'border': 1})

        for obj in objects:
            sheet.set_row(1, 28)
            sheet.set_row(3, 18)
            sheet.set_row(4, 18)

            sheet.set_column('A:A', 10)
            sheet.set_column('B:B', 24)
            sheet.set_column('C:C', 35)
            sheet.set_column('D:D', 30)
            sheet.set_column('E:E', 10)
            sheet.set_column('F:F', 22)
            sheet.set_column('G:G', 22)

            date_from = datetime.strftime(obj.from_date, '%d-%m-%Y')
            date_to = datetime.strftime(obj.to_date, '%d-%m-%Y')

            row = 1
            sheet.merge_range(row, 0, row, 4, 'COGS DETAILED REPORT', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 18}))

            row += 2
            sheet.write(row, 0, 'From', align_bold_left)
            sheet.write(row, 1, str(date_from), align_left)

            row += 1
            sheet.write(row, 0, 'To', align_bold_left)
            sheet.write(row, 1, str(date_to), align_left)

            row += 2
            titles = ['S.No', 'SKU', 'Product Name', 'DO No.', 'Qty', 'Unit Cost Price', 'COGS Value']
            for index in range(0, len(titles)):
                sheet.write(row, index, titles[index], align_bold_center)

            from_date_time = datetime.combine(obj.from_date, time.min).replace(microsecond=0)
            to_date_time = datetime.combine(obj.to_date, time.max).replace(microsecond=0)

            from_date = obj.get_utc_datetime(from_date_time)
            to_date = obj.get_utc_datetime(to_date_time)

            domain = [
                ('create_date', '>=', from_date), ('create_date', '<=', to_date), ('stock_move_id.picking_id', '!=', False),
                ('company_id', '=', obj.company_id.id), ('reference', '!=', False), '|', ('value', '<', 0), ('quantity', '<', 0)
            ]
            if obj.product_ids:
                domain += [('product_id', 'in', obj.product_ids.ids or [])]

            stock_valuation_env = self.env['stock.valuation.layer'].sudo()
            total_sales_ids = stock_valuation_env.search(domain, order='create_date')
            # sold_products = list(set(total_sales_ids.mapped('product_id')))

            row += 1
            sno = 1
            # for product_id in sold_products:
            #     product_sales = stock_valuation_env.search(
            #         [('product_id', '=', product_id.id), ('id', 'in', total_sales_ids.ids or [])])
            #
            #     do_nos = ', '.join([i for i in product_sales.mapped('reference')])
            #     cogs_value = sum(product_sales.mapped('value')) or 0
            #
            #     sheet.write(row, 0, str(sno), align_center)
            #     sheet.write(row, 1, str(product_id.default_code or ''), align_left)
            #     sheet.write(row, 2, str(product_id.name or ''), align_left)
            #     sheet.write(row, 3, str(do_nos or ''), align_left)
            #     sheet.write(row, 4, str(obj.currency_id.symbol or '') + ' ' + str('%.2f' % abs(cogs_value) or 0), align_right)
            #
            #     row += 1
            #     sno += 1
            for line in total_sales_ids:
                sheet.write(row, 0, str(sno), align_center)
                sheet.write(row, 1, str(line.product_id.default_code or ''), align_left)
                sheet.write(row, 2, str(line.product_id.name or ''), align_left)
                sheet.write(row, 3, str(line.reference or ''), align_left)
                sheet.write(row, 4, str('%.2f' % abs(line.quantity) or 0), align_right)
                sheet.write(row, 5, str(line.currency_id.symbol or '') + ' ' + str('%.2f' % line.unit_cost or 0), align_right)
                sheet.write(row, 6, str(line.currency_id.symbol or '') + ' ' + str('%.2f' % abs(line.value) or 0), align_right)

                row += 1
                sno += 1

            if not total_sales_ids:
                sheet.merge_range(row + 1, 0, row + 1, 4, 'No Record(s) found', workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True}))
