import time
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta


class OpenInvoiceReport(models.TransientModel):
    _name = 'open.invoice.report.wizard'
    _description = 'Open Invoice Report'

    from_date = fields.Date('From Date', default=lambda *a: str(datetime.now() + relativedelta(day=1))[:10])
    to_date = fields.Date('To Date', default=lambda *a: str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10])
    partner_ids = fields.Many2many('res.partner', string='Customer(s)')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Currency')

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
            'report_name': 'flemings_base.open_invoice_report_wizard_xlsx'
        }


class FlemingsOpenInvoiceReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.open_invoice_report_wizard_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Open Invoice Report'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('OPEN INVOICE REPORT')

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
            sheet.set_column('B:B', 22)
            sheet.set_column('C:C', 35)
            sheet.set_column('D:D', 20)
            sheet.set_column('E:E', 20)
            sheet.set_column('F:F', 20)
            sheet.set_column('G:G', 20)
            sheet.set_column('H:H', 20)
            sheet.set_column('I:I', 35)

            date_from = datetime.strftime(obj.from_date, '%d-%m-%Y')
            date_to = datetime.strftime(obj.to_date, '%d-%m-%Y')

            row = 1
            sheet.merge_range(row, 0, row, 4, 'OPEN INVOICE REPORT', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 18}))

            row += 2
            sheet.write(row, 0, 'From', align_bold_left)
            sheet.write(row, 1, str(date_from), align_left)

            row += 1
            sheet.write(row, 0, 'To', align_bold_left)
            sheet.write(row, 1, str(date_to), align_left)

            row += 2
            titles = ['S.No', 'Date', 'Customer', 'Invoice No.', 'Subtotal', 'Total (Including GST)', 'Amount Paid', 'Balance Amount', 'Status (Partially Paid / Unpaid)']
            for index in range(0, len(titles)):
                sheet.write(row, index, titles[index], align_bold_center)

            domain = [
                ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('amount_residual', '>', 0),
                ('company_id', '=', obj.company_id.id), ('invoice_date', '>=', obj.from_date), ('invoice_date', '<=', obj.to_date)
            ]
            if obj.partner_ids:
                domain += [('partner_id', 'in', obj.partner_ids.ids or [])]

            row += 1
            sno = 1
            sub_total = taxed_total = paid_amount = balance_amount = 0

            line_data = self.env['account.move'].sudo().search(domain, order='invoice_date')
            for move_id in line_data:
                sheet.write(row, 0, str(sno), align_center)
                sheet.write(row, 1, str(datetime.strftime(move_id.invoice_date, '%d-%m-%Y') or ''), align_left)
                sheet.write(row, 2, str(move_id.partner_id.display_name or ''), align_left)
                sheet.write(row, 3, str(move_id.name or ''), align_left)
                sheet.write(row, 4, str(move_id.currency_id.symbol or '') + ' ' + str('%.2f' % move_id.amount_untaxed or 0), align_right)
                sheet.write(row, 5, str(move_id.currency_id.symbol or '') + ' ' + str('%.2f' % move_id.amount_total or 0), align_right)
                sheet.write(row, 6, str(move_id.currency_id.symbol or '') + ' ' + str('%.2f' % (move_id.amount_total - move_id.amount_residual) or 0), align_right)
                sheet.write(row, 7, str(move_id.currency_id.symbol or '') + ' ' + str('%.2f' % move_id.amount_residual or 0), align_right)
                sheet.write(row, 8, 'Unpaid' if (move_id.amount_total == move_id.amount_residual) else 'Partially Paid', align_center)

                sub_total += move_id.amount_untaxed
                taxed_total += move_id.amount_total
                paid_amount += move_id.amount_total - move_id.amount_residual
                balance_amount += move_id.amount_residual

                row += 1
                sno += 1

            if line_data:
                row += 1
                sheet.write(row, 3, 'Total', align_bold_right)
                sheet.write(row, 4, str(obj.currency_id.symbol or '') + ' ' + str('%.2f' % sub_total or 0), align_bold_right)
                sheet.write(row, 5, str(obj.currency_id.symbol or '') + ' ' + str('%.2f' % taxed_total or 0), align_bold_right)
                sheet.write(row, 6, str(obj.currency_id.symbol or '') + ' ' + str('%.2f' % paid_amount or 0), align_bold_right)
                sheet.write(row, 7, str(obj.currency_id.symbol or '') + ' ' + str('%.2f' % balance_amount or 0), align_bold_right)

            else:
                sheet.merge_range(row + 1, 0, row + 1, 6, 'No Record(s) found', workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True}))
