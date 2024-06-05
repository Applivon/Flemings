import time
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta


class DoNotInvoicedReport(models.TransientModel):
    _name = 'do.not.invoiced.report.wizard'
    _description = 'Do Not Invoiced Report'

    from_date = fields.Date('From Date', default=lambda *a: str(datetime.now() + relativedelta(day=1))[:10])
    to_date = fields.Date('To Date', default=lambda *a: str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10])
    partner_ids = fields.Many2many('res.partner', string='Customer(s)')

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
            'report_name': 'flemings_base.do_not_invoiced_report_wizard_xlsx'
        }

    def get_utc_datetime(self, date_time):
        local = pytz.timezone(self.env.user.tz)
        naive = datetime.strptime(str(date_time), "%Y-%m-%d %H:%M:%S")
        local_dt = local.localize(naive, is_dst=None)
        return local_dt.astimezone(pytz.utc)


class FlemingsDoNotInvoicedReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.do_not_invoiced_report_wizard_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Do Not Invoiced Report'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('DO NOT INVOICED REPORT')

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
            sheet.set_column('E:E', 30)

            date_from = datetime.strftime(obj.from_date, '%d-%m-%Y')
            date_to = datetime.strftime(obj.to_date, '%d-%m-%Y')

            row = 1
            sheet.merge_range(row, 0, row, 4, 'DO NOT INVOICED REPORT', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 18}))

            row += 2
            sheet.write(row, 0, 'From', align_bold_left)
            sheet.write(row, 1, str(date_from), align_left)

            row += 1
            sheet.write(row, 0, 'To', align_bold_left)
            sheet.write(row, 1, str(date_to), align_left)

            row += 2
            titles = ['S.No', 'DO Date', 'Customer', 'SO No.', 'DO No.']
            for index in range(0, len(titles)):
                sheet.write(row, index, titles[index], align_bold_center)

            domain = [
                ('sale_id', '!=', False), ('sale_id.fg_invoice_status', 'in', ['to invoice', 'partial_invoice']),
                ('scheduled_date', '>=', obj.from_date), ('scheduled_date', '<=', obj.to_date)
            ]
            if obj.partner_ids:
                domain += ['', ('sale_id.partner_id', 'in', obj.partner_ids.ids or []), ('partner_id', 'in', obj.partner_ids.ids or [])]

            row += 1
            sno = 1

            line_data = self.env['stock.picking'].sudo().search(domain, order='scheduled_date').mapped('sale_id')
            for order_id in line_data:
                do_dates = order_id.picking_ids.mapped('scheduled_date')
                utc_do_date_times = [obj.get_utc_datetime(i) for i in do_dates]
                utc_do_dates = list(set(j.date() for j in utc_do_date_times))

                if len(utc_do_dates) == 1:
                    sheet.write(row, 0, str(sno), align_center)
                    sheet.write(row, 1, str(datetime.strftime(utc_do_dates[0], '%d-%m-%Y') or ''), align_left)
                    sheet.write(row, 2, str(order_id.partner_id.name or ''), align_left)
                    sheet.write(row, 3, str(order_id.name or ''), align_left)
                    sheet.write(row, 4, str(', '.join([i.name for i in order_id.picking_ids]) or ''), align_left)

                    row += 1
                    sno += 1
                else:
                    for utc_do_date in utc_do_dates:
                        picking_ids = []
                        for picking_id in order_id.picking_ids:
                            picking_utc_do_date = obj.get_utc_datetime(picking_id.scheduled_date) and obj.get_utc_datetime(picking_id.scheduled_date).date()
                            if utc_do_date == picking_utc_do_date:
                                picking_ids += [picking_id]

                        sheet.write(row, 0, str(sno), align_center)
                        sheet.write(row, 1, str(datetime.strftime(utc_do_date, '%d-%m-%Y') or ''), align_left)
                        sheet.write(row, 2, str(order_id.partner_id.name or ''), align_left)
                        sheet.write(row, 3, str(order_id.name or ''), align_left)
                        sheet.write(row, 4, str(', '.join([i.name for i in picking_ids]) or ''), align_left)

                        row += 1
                        sno += 1

            if not line_data:
                sheet.merge_range(row + 1, 0, row + 1, 4, 'No Record(s) found', workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True}))
