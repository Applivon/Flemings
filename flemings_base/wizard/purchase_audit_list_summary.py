from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta


class FlemingsPurchaseAudiListSummary(models.TransientModel):
    _name = 'purchase.audit.list.summary.wizard'
    _description = 'Purchase Audit List Summary'

    from_date = fields.Date('From Date', default=lambda *a: str(datetime.now() + relativedelta(day=1))[:10])
    to_date = fields.Date('To Date', default=lambda *a: str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10])
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)
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

    def generate_excel_report(self):
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'flemings_base.purchase_audit_list_summary_wizard_xlsx'
        }


class FlemingsPurchaseAudiListSummaryXlsx(models.AbstractModel):
    _name = 'report.flemings_base.purchase_audit_list_summary_wizard_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Purchase Audit List Summary Report'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('PURCHASE AUDIT LIST SUMMARY')

        align_left = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        align_right = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'align': 'right', 'valign': 'vcenter', 'text_wrap': True})
        align_center = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        align_bold_left = workbook.add_format({'font_name': 'Arial', 'font_size': 14, 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True, 'underline': True})
        align_bold_right = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'align': 'right', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_center = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True})

        for obj in objects:
            sheet.set_row(0, 20)
            sheet.set_row(1, 20)
            sheet.set_row(3, 30)

            sheet.set_column('A:A', 20)
            sheet.set_column('B:B', 20)
            sheet.set_column('C:C', 35)
            sheet.set_column('D:D', 16)
            sheet.set_column('E:E', 20)
            sheet.set_column('F:F', 18)
            sheet.set_column('G:G', 12)
            sheet.set_column('H:K', 18)

            date_from = datetime.strftime(obj.from_date, '%d/%m/%Y')
            date_to = datetime.strftime(obj.to_date, '%d/%m/%Y')
            purchase_period = str(date_from) + ' - ' + str(date_to)

            sheet.merge_range(0, 3, 0, 0, 'PURCHASE AUDIT LIST SUMMARY', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True}))
            sheet.merge_range(1, 3, 1, 0, 'Period : ' + purchase_period, workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'num_format': 'dd/mm/yyyy'}))

            purchase_domain = [('date_approve', '>=', obj.from_date), ('date_approve', '<=', obj.to_date), ('state', 'in', ('purchase', 'done'))]
            if obj.partner_ids:
                purchase_domain.append(('partner_id', 'in', obj.partner_ids.ids or []))

            purchase_orders = self.env['purchase.order'].sudo().search(purchase_domain, order='date_approve')
            currencies = purchase_orders.mapped('currency_id')

            row = 3
            titles = [
                'Date', 'PO Number', 'Vendor', 'Delivery Date', 'Term', 'Total Qty',
                'Currency', 'Gross Total', 'Tax Base', 'Tax', 'Net Total'
            ]

            for index in range(0, len(titles)):
                sheet.write(row, index, titles[index], align_bold_center)
            for currency_id in currencies:
                qty_total = gross_total = 0
                untaxed_total = tax_total = net_total = 0
                sheet.write(row + 2, 0, 'Currency : ' + str(currency_id.name), align_bold_left)
                row += 4

                currency_orders = purchase_orders.filtered(lambda x: x.currency_id.id == currency_id.id)
                for order in currency_orders:
                    last_receipt = self.env['stock.picking'].sudo().search([
                        ('state', '=', 'done'), ('id', 'in', order.picking_ids.ids or [])
                    ], order='date_done desc', limit=1) or False

                    sheet.write(row, 0, order.date_approve.strftime("%d %b %Y") or '', align_center)
                    sheet.write(row, 1, order.name or '', align_center)
                    sheet.write(row, 2, order.partner_id.display_name or '', align_left)
                    sheet.write(row, 3, last_receipt.date_done.strftime("%d %b %Y") if (last_receipt and last_receipt.date_done) else '', align_center)
                    sheet.write(row, 4, order.payment_term_id.name or '', align_left)
                    sheet.write(row, 5, str('%.2f' % sum(order.order_line.mapped('qty_received'))), align_right)
                    sheet.write(row, 6, str(currency_id.name) or '', align_center)
                    sheet.write(row, 7, str('%.2f' % sum(order.order_line.mapped('price_subtotal'))), align_right)
                    sheet.write(row, 8, str('%.2f' % order.amount_untaxed), align_right)
                    sheet.write(row, 9, str('%.2f' % order.amount_tax), align_right)
                    sheet.write(row, 10, str('%.2f' % order.amount_total), align_right)
                    row += 1

                    qty_total += sum(order.order_line.mapped('qty_received'))
                    gross_total += sum(order.order_line.mapped('price_subtotal'))

                    untaxed_total += order.amount_untaxed
                    tax_total += order.amount_tax
                    net_total += order.amount_total

                row += 1
                sheet.write(row, 0, 'Sub Total (' + str(currency_id.name) + ')', align_bold_right)
                sheet.write(row, 5, str('%.2f' % qty_total), align_bold_right)
                sheet.write(row, 7, str('%.2f' % gross_total), align_bold_right)
                sheet.write(row, 8, str('%.2f' % untaxed_total), align_bold_right)
                sheet.write(row, 9, str('%.2f' % tax_total), align_bold_right)
                sheet.write(row, 10, str('%.2f' % net_total), align_bold_right)
                row += 1
