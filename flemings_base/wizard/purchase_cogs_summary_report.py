import time
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta


class PurchaseCOGSSummaryReport(models.TransientModel):
    _name = 'purchase.cogs.summary.report.wizard'
    _description = 'Summary Report for Purchase, Inventory, COGS'

    from_date = fields.Date('From Date', default=lambda *a: str(datetime.now() + relativedelta(day=1))[:10])
    to_date = fields.Date('To Date', default=lambda *a: str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10])
    sgd_currency_id = fields.Many2one('res.currency', string='SGD Currency', default=lambda self: self.env['res.currency'].search([('name', '=', 'SGD')], limit=1))

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
            'report_name': 'flemings_base.purchase_cogs_summary_report_wizard_xlsx'
        }

    def get_utc_datetime(self, date_time):
        local = pytz.timezone(self.env.user.tz)
        naive = datetime.strptime(str(date_time), "%Y-%m-%d %H:%M:%S")
        local_dt = local.localize(naive, is_dst=None)
        return local_dt.astimezone(pytz.utc)


class FlemingsPurchaseCOGSSummaryReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.purchase_cogs_summary_report_wizard_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Summary Report for Purchase, Inventory, COGS'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('SUMMARY REPORT')

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
            sheet.set_row(6, 18)

            sheet.set_column('A:A', 15)
            sheet.set_column('B:B', 15)
            sheet.set_column('C:C', 18)
            sheet.set_column('D:D', 18)
            sheet.set_column('E:E', 18)

            date_from = datetime.strftime(obj.from_date, '%d-%m-%Y')
            date_to = datetime.strftime(obj.to_date, '%d-%m-%Y')

            row = 1
            sheet.merge_range(row, 0, row, 4, 'SUMMARY REPORT FOR STOCK, PURCHASE, COGS', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 16}))

            stock_valuation_env = self.env['stock.valuation.layer'].sudo()
            purchase_order_env = self.env['purchase.order'].sudo()
            from_date_time = datetime.combine(obj.from_date, time.min).replace(microsecond=0)
            from_date = obj.get_utc_datetime(from_date_time)
            opening_stocks_total = sum(stock_valuation_env.search([('create_date', '<=', from_date)]).mapped('value')) or 0

            row += 2
            sheet.write(row, 0, 'From', align_bold_left)
            sheet.write(row, 1, str(date_from), align_left)

            row += 1
            sheet.write(row, 0, 'To', align_bold_left)
            sheet.write(row, 1, str(date_to), align_left)

            row += 2
            sheet.write(row, 0, 'Opening Stock', align_bold_left)
            sheet.write(row, 1, str(obj.sgd_currency_id.symbol) + ' ' + str('%.2f' % opening_stocks_total or 0), align_bold_right)

            row += 2
            titles = ['S.No', 'Date', 'Stock', 'Purchase', 'COGS']
            for index in range(0, len(titles)):
                sheet.write(row, index, titles[index], align_bold_center)

            row += 1

            start_date = obj.from_date
            end_date = obj.to_date

            sno = 1
            while start_date <= end_date:
                from_date_time = datetime.combine(start_date, time.min).replace(microsecond=0)
                to_date_time = datetime.combine(start_date, time.max).replace(microsecond=0)

                from_date = obj.get_utc_datetime(from_date_time)
                to_date = obj.get_utc_datetime(to_date_time)

                stocks_total = sum(stock_valuation_env.search(
                    [('create_date', '<=', to_date)]).mapped('value')) or 0
                # purchase_total = sum(stock_valuation_env.search(
                #     [('create_date', '>=', from_date), ('create_date', '<=', to_date), ('value', '>', 0)]).mapped('value')) or 0
                purchase_total = sum(purchase_order_env.search(
                    [('date_approve', '>=', from_date), ('date_approve', '<=', to_date)]).mapped('amount_untaxed')) or 0
                sales_total = sum(stock_valuation_env.search(
                    [('create_date', '>=', from_date), ('create_date', '<=', to_date), ('value', '<', 0), ('quantity', '<', 0),
                     ('stock_move_id.location_id.usage', 'in', ('internal', 'transit')),
                     ('stock_move_id.location_dest_id.usage', 'not in', ('internal', 'transit'))
                     ]).mapped('value')) or 0

                sheet.write(row, 0, str(sno), align_center)
                sheet.write(row, 1, str(datetime.strftime(start_date, '%d-%m-%Y') or ''), align_left)
                sheet.write(row, 2, str(obj.sgd_currency_id.symbol or '') + ' ' + str('%.2f' % stocks_total or 0), align_right)
                sheet.write(row, 3, str(obj.sgd_currency_id.symbol or '') + ' ' + str('%.2f' % purchase_total or 0), align_right)
                sheet.write(row, 4, str(obj.sgd_currency_id.symbol or '') + ' ' + str('%.2f' % abs(sales_total) or 0), align_right)

                row += 1
                sno += 1

                start_date += timedelta(days=1)
