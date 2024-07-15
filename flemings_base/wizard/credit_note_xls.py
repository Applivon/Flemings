# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar
import logging
from datetime import timedelta, datetime
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

import base64
import io

_logger = logging.getLogger(__name__)


class FlemingsCreditNoteReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.flemings_credit_note_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Credit Note Report'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('CREDIT NOTE REPORT')

        align_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        align_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True})
        align_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        align_bold_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True})

        row = 0
        for obj in objects:
            sheet.merge_range(row, 0, row + 7, 0, '', align_bold_center)
            sheet.merge_range(row, 3, row + 7, 5, '', align_bold_center)

            image_width = 140.0
            image_height = 180.0
            cell_width = 80.0
            cell_height = 100.0

            x_scale = cell_width / image_width
            y_scale = cell_height / image_height

            if obj.company_id.logo:
                sheet.insert_image(
                    'A' + str(row + 2), '',
                    {'x_scale': x_scale, 'y_scale': y_scale, 'align': 'center',
                     'image_data': io.BytesIO(base64.b64decode(obj.company_id.logo))
                     }
                )
            if obj.company_id.sgs_img:
                image_width = 240.0
                image_height = 300.0
                cell_width = 40.0
                cell_height = 50.0

                x_scale = cell_width / image_width
                y_scale = cell_height / image_height

                sheet.insert_image(
                    'D' + str(row + 2), '',
                    {'x_scale': x_scale, 'y_scale': y_scale, 'align': 'center',
                     'image_data': io.BytesIO(base64.b64decode(obj.company_id.sgs_img))
                     }
                )

            company_address = (
                    str(obj.company_id.street or '') + ' ' + str(obj.company_id.street2 or '') + '\n' +
                    str(obj.company_id.country_id.name or '') + ' ' + str(obj.company_id.zip or '') + ' Tel: ' + str(obj.company_id.phone or '') + ' Fax: ' + str(obj.company_id.fax or '') + '\n' +
                    'Email: ' + str(obj.company_id.email or '') + ' ' + str(obj.company_id.website or '')
            )

            sheet.merge_range(row, 1, row + 2, 2, str(obj.company_id.name), workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'bottom', 'bold': True, 'text_wrap': True, 'font_size': 18}))
            sheet.merge_range(row + 3, 1, row + 7, 2, company_address, align_center)

            row += 8

            for i in range(row, row+9):
                sheet.set_row(i, 22)

            sheet.set_column('A:A', 25)
            sheet.set_column('B:B', 60)
            sheet.set_column('C:C', 12)
            sheet.set_column('D:D', 12)
            sheet.set_column('E:E', 16)
            sheet.set_column('F:F', 16)

            sheet.merge_range(row, 0, row, 1, 'Bill To:', align_left)
            sheet.merge_range(row, 2, row, 5, 'CREDIT NOTE', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 18}))

            row += 1
            sheet.merge_range(row, 0, row, 1, str(obj.partner_id.name), align_left)
            sheet.merge_range(row, 2, row, 3, 'CO Reg. No.', align_left)
            sheet.merge_range(row, 4, row, 5, str(obj.company_id.l10n_sg_unique_entity_number or ''), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, str(obj.partner_id.street), align_left)
            sheet.merge_range(row, 2, row, 3, 'GST Reg. No.', align_left)
            sheet.merge_range(row, 4, row, 5, str(obj.company_id.vat or ''), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, str(obj.partner_id.street2), align_left)
            sheet.merge_range(row, 2, row, 3, 'Transaction No.', align_left)
            sheet.merge_range(row, 4, row, 5, str(obj.name or ''), align_left)

            row += 1
            right_column_row = row
            if obj.partner_id.country_id and obj.partner_id.country_id.code != 'SG':
                sheet.merge_range(row, 0, row, 1, str(obj.partner_id.city or '') + ' ' + str(obj.partner_id.state_id.name or ''), align_left)
                sheet.merge_range(row + 1, 0, row + 1, 1, str(obj.partner_id.country_id.name or '') + ' ' + str(obj.partner_id.zip or ''), align_left)
                row += 2
            else:
                sheet.merge_range(right_column_row, 0, right_column_row, 1, str(obj.partner_id.country_id.name or '') + ' ' + str(obj.partner_id.zip or ''), align_left)
                row += 1

            sheet.merge_range(right_column_row, 2, right_column_row, 3, 'Date', align_left)
            sheet.merge_range(right_column_row, 4, right_column_row, 5, str(datetime.strftime(obj.invoice_date, '%d %B %Y')) if obj.invoice_date else '', align_left)

            if obj.partner_id.child_ids.filtered(lambda x: x.type in ('contact', 'invoice')):
                contact_customer = obj.partner_id.child_ids.filtered(lambda x: x.type in ('contact', 'invoice'))[0]
            else:
                contact_customer = obj.partner_id

            row += 1
            right_column_row += 1
            sheet.merge_range(row, 0, row, 1, 'Contact Name: ' + str(contact_customer.title.name or '') + ' ' + str(contact_customer.name or ''), align_left)
            sheet.merge_range(right_column_row, 2, right_column_row, 3, 'Currency', align_left)
            sheet.merge_range(right_column_row, 4, right_column_row, 5, str(obj.currency_id.name or ''), align_left)

            row += 1
            right_column_row += 1
            if contact_customer and contact_customer.parent_id:
                sheet.merge_range(row, 0, row, 1, 'ATTN: ' + str(contact_customer.parent_id.title.name or '') + ' ' + str(contact_customer.parent_id.name or ''), align_left)
            else:
                sheet.merge_range(row, 0, row, 1, 'Tel: ' + str(contact_customer.phone or '') + '  Fax: ' + str(contact_customer.fax or '') + '  Mob: ' + str(contact_customer.mobile or ''), align_left)

            sheet.merge_range(right_column_row, 2, right_column_row, 3, 'Salesperson', align_left)
            sheet.merge_range(right_column_row, 4, right_column_row, 5, str(obj.user_id.name or ''), align_left)

            if contact_customer and contact_customer.parent_id:
                row += 1
                sheet.merge_range(row, 0, row, 1, 'Tel: ' + str(contact_customer.phone or '') + '  Fax: ' + str(contact_customer.fax or '') + '  Mob: ' + str(contact_customer.mobile or ''), align_left)

            row += 2
            sheet.set_row(row, 22)
            titles = ['S/N', 'Product Code / Description', 'Qty', 'UOM', 'Unit Price', 'Total Amount']
            for index in range(0, len(titles)):
                sheet.write(row, index, titles[index], align_bold_center)

            fg_sno = 1
            row += 1
            for line in obj.invoice_line_ids.sorted(key=lambda x: x.sequence):
                sheet.write(row, 0, fg_sno, align_center)
                sheet.write(row, 1, str(line.product_id.default_code or '') + '\n' + str(line.name or ''), align_left)
                sheet.write(row, 2, str('%.0f' % line.quantity or 0), align_center)
                sheet.write(row, 3, str(line.product_uom_id.name or ''), align_left)
                sheet.write(row, 4, str('%.2f' % line.price_unit or 0), align_center)
                sheet.write(row, 5, str('%.2f' % line.price_subtotal or 0), align_center)

                fg_sno += 1
                row += 1

            row += 1
            sheet.write(row, 1, 'Total Quantity: ', align_bold_right)
            sheet.write(row, 2, str('%.0f' % sum(obj.invoice_line_ids.mapped('quantity')) or 0), align_bold_center)
            sheet.merge_range(row, 3, row, 4, 'Sub Total : ' + str(obj.currency_id.name or ''), align_bold_right)
            sheet.write(row, 5, str('%.2f' % obj.amount_untaxed or 0), align_bold_center)

            row += 2
            sheet.merge_range(row, 3, row, 4, 'Tax Base : ' + str(obj.currency_id.name or ''), align_bold_right)
            sheet.write(row, 5, str('%.2f' % obj.amount_untaxed or 0), align_bold_center)

            row += 1
            tax_totals = obj.tax_totals
            for subtotal in tax_totals['subtotals']:
                subtotal_to_show = subtotal['name']
                for amount_by_group in tax_totals['groups_by_subtotal'][subtotal_to_show]:
                    sheet.merge_range(row, 3, row, 4, str(amount_by_group['tax_group_name']) + ' : ' + str(obj.currency_id.name or ''), align_bold_right)
                    sheet.write(row, 5, str('%.2f' % amount_by_group['tax_group_amount'] or 0), align_bold_center)
                    row += 1

            row += 1
            sheet.merge_range(row, 3, row, 4, 'Grand Total : ' + str(obj.currency_id.name or ''), align_bold_right)
            sheet.write(row, 5, str('%.2f' % obj.amount_total or 0), align_bold_center)

            row += 2
            sheet.merge_range(row, 0, row, 1, 'For GST Auditing Only (SGD)', align_bold_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, 'Net Total: ' + str(obj.currency_id.symbol or '') + ' ' + str('%.2f' % obj.sgd_amount_untaxed or 0), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, 'GST: ' + str(obj.currency_id.symbol or '') + ' ' + str('%.2f' % obj.sgd_amount_tax or 0), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, 'Total: ' + str(obj.currency_id.symbol or '') + ' ' + str('%.2f' % obj.sgd_amount_total or 0), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, 'Exchange Rate: ' + str(obj.currency_id.symbol or '') + ' ' + str('%.6f' % obj.sgd_exchange_rate or 0), align_left)

            row += 2
            sheet.merge_range(row, 0, row, 1, 'Remarks: ', align_bold_left)

            row += 1
            sheet.merge_range(row, 0, row + 1, 1, str(obj.fg_remarks or ''), align_left)

            row += 4
            sheet.merge_range(row, 0, row + 1, 1, 'Received By', align_bold_center)
            sheet.merge_range(row, 2, row + 1, 3, 'Date', align_bold_center)
            sheet.merge_range(row, 4, row + 1, 5, 'Authorisation', align_bold_center)

            row += 2
            sheet.merge_range(row, 0, row + 6, 1, '', align_bold_center)
            sheet.merge_range(row, 2, row + 6, 3, '', align_bold_center)
            sheet.merge_range(row, 4, row + 6, 5, '', align_bold_center)

            row += 7
            sheet.merge_range(row, 4, row, 5, 'for ' + str(obj.company_id.name), align_bold_center)

            row += 2
            sheet.set_row(row, 22)
            sheet.merge_range(row, 0, row, 3, 'Print By:  ' + str(self.env.user.name) + ' / ' + str(
                fields.Datetime.context_timestamp(obj, datetime.now()).strftime('%d-%b-%y %I:%M:%S %p')
            ), align_bold_left)
            row += 6
