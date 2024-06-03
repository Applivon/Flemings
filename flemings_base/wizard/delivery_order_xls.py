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


class FlemingsDeliveryOrderReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.flemings_delivery_order_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Delivery Order Report'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('DELIVERY ORDER REPORT')

        align_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        align_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True})
        align_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        align_bold_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True})

        row = 0
        for obj in objects:
            sheet.merge_range(row, 0, row + 7, 0, '', align_bold_center)
            sheet.merge_range(row, 3, row + 7, 3, '', align_bold_center)

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
                sheet.insert_image(
                    'D' + str(row + 2), '',
                    {'x_scale': x_scale, 'y_scale': y_scale, 'align': 'center',
                     'image_data': io.BytesIO(base64.b64decode(obj.company_id.logo))
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

            for i in range(row, row+11):
                sheet.set_row(i, 22)

            sheet.set_column('A:A', 25)
            sheet.set_column('B:B', 60)
            sheet.set_column('C:C', 25)
            sheet.set_column('D:D', 25)

            sheet.merge_range(row, 0, row, 1, 'Deliver To:', align_left)
            sheet.merge_range(row, 2, row, 3, 'DELIVERY ORDER', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 18}))

            row += 1
            sheet.merge_range(row, 0, row, 1, str(obj.partner_id.name), align_left)
            sheet.write(row, 2, 'Delivery Order No.', align_left)
            sheet.write(row, 3, str(obj.name or ''), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, str(obj.partner_id.street), align_left)
            sheet.write(row, 2, 'Sales Order No.', align_left)
            sheet.write(row, 3, str(obj.sale_id.name or ''), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, str(obj.partner_id.street2), align_left)
            sheet.write(row, 2, 'Delivery Date', align_left)
            sheet.write(row, 3, str(datetime.strftime(obj.scheduled_date, '%d %B %Y')), align_left)

            row += 1
            if obj.partner_id.country_id and obj.partner_id.country_id.code != 'SG':
                sheet.merge_range(row, 0, row, 1, str(obj.partner_id.city or '') + ' ' + str(obj.partner_id.state_id.name or ''), align_left)
                sheet.merge_range(row + 1, 0, row + 1, 1, str(obj.partner_id.country_id.name or '') + ' ' + str(obj.partner_id.zip or ''), align_left)
            else:
                sheet.merge_range(row, 0, row, 1, str(obj.partner_id.country_id.name or '') + ' ' + str(obj.partner_id.zip or ''), align_left)

            sheet.write(row, 2, 'Payment Term', align_left)
            sheet.write(row, 3, str(obj.sale_id.payment_term_id.name or ''), align_left)

            row += 1
            sheet.write(row, 2, 'Salesperson', align_left)
            sheet.write(row, 3, str(obj.user_id.name or ''), align_left)

            row += 1
            sheet.write(row, 2, 'Process By', align_left)
            sheet.write(row, 3, str(obj.process_by_id.name or ''), align_left)

            row += 1
            sheet.write(row, 2, 'Purchase Order No.', align_left)
            sheet.write(row, 3, str(obj.customer_po or ''), align_left)

            if obj.partner_id.child_ids.filtered(lambda x: x.type in ('contact', 'invoice')):
                contact_customer = obj.partner_id.child_ids.filtered(lambda x: x.type in ('contact', 'invoice'))[0]
            else:
                contact_customer = obj.partner_id

            row += 1
            sheet.merge_range(row, 0, row, 1, 'ATTN: ' + str(contact_customer.title.name or '') + ' ' + str(contact_customer.name or ''), align_left)
            sheet.write(row, 2, 'Country', align_left)
            sheet.write(row, 3, str(obj.partner_id.country_id.name or ''), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, 'Tel: ' + str(obj.company_id.phone or '') + '  Fax: ' + str(obj.company_id.fax or '') + '  Mob: ' + str(obj.company_id.mobile or ''), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, 'Email: ' + str(obj.company_id.email or ''), align_left)

            row += 2
            sheet.set_row(row, 22)
            titles = ['S/N', 'Product Code / Description', 'Qty', 'UOM']
            for index in range(0, len(titles)):
                sheet.write(row, index, titles[index], align_bold_center)

            fg_sno = 1
            row += 1
            for line in obj.move_line_ids_without_package:
                sheet.write(row, 0, fg_sno, align_center)
                sheet.write(row, 1, str(line.product_id.default_code or '') + '\n' + str(line.product_id.description_sale or ''), align_left)
                sheet.write(row, 2, str('%.0f' % line.qty_done or 0), align_center)
                sheet.write(row, 3, str(line.product_uom_id.name or ''), align_left)

                fg_sno += 1
                row += 1

            row += 1
            sheet.write(row, 0, 'Remarks', align_left)
            sheet.write(row, 1, 'Total Quantity: ', align_right)
            sheet.write(row, 2, str('%.0f' % sum(obj.move_line_ids_without_package.mapped('qty_done')) or 0), align_center)

            row += 1
            sheet.merge_range(row, 0, row + 1, 1, str(obj.fg_remarks or ''), align_left)

            row += 4
            sheet.merge_range(row, 0, row+1, 1, 'Received in good order & condition by', align_bold_center)
            sheet.merge_range(row, 2, row+1, 3, 'Authorisation', align_bold_center)

            row += 2
            sheet.merge_range(row, 0, row + 6, 1, '', align_bold_center)
            sheet.merge_range(row, 2, row + 6, 3, '', align_bold_center)

            image_width = 600.0
            image_height = 800.0
            cell_width = 256.0
            cell_height = 524.0

            x_scale = cell_width / image_width
            y_scale = cell_height / image_height

            if obj.signature:
                sheet.insert_image(
                    'A' + str(row + 1), '',
                    {'x_scale': x_scale, 'y_scale': y_scale, 'align': 'center',
                     'image_data': io.BytesIO(base64.b64decode(obj.signature))
                     }
                )

            row += 7
            sheet.merge_range(row, 0, row+1, 1, 'Signature & Company Stamp', align_bold_center)
            sheet.merge_range(row, 2, row+1, 3, 'For ' + str(obj.company_id.name), align_bold_center)

            row += 3
            sheet.set_row(row, 22)
            sheet.merge_range(row, 0, row, 3, 'Print By:  ' + str(self.env.user.name) + ' / ' + str(
                fields.Datetime.context_timestamp(obj, datetime.now()).strftime('%d-%b-%y %I:%M:%S %p')
            ), align_bold_left)
            row += 6
