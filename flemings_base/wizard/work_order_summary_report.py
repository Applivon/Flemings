from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

from datetime import timedelta, datetime
import base64
import io


class WorkOrderSummaryReport(models.TransientModel):
    _name = 'work.order.summary.report.wizard'
    _description = 'Work Order Generation'

    work_order_no = fields.Char('Work Order No.', required=True)
    report_type = fields.Selection([
        ('work_order', 'Work Order Summary Report'), ('raw_material', 'Raw Material Summary Report'), ('design', 'Design Specification')
    ], default='work_order', string='Report Type')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)

    @api.constrains('work_order_no')
    def check_work_order_no_exists(self):
        for record in self:
            if record.work_order_no:
                if not self.env['mrp.production.work.order.no'].sudo().search([('work_order_no', '=', record.work_order_no)]):
                    raise UserError(_('Work Order No. not exists !'))

                if not self.env['mrp.production'].sudo().search([('work_order_no', '=', record.work_order_no)]):
                    raise UserError(_('Manufacturing Orders not exists for this Work Order No. !'))

                # if not self.env['mo.image.for.work.order'].sudo().search([('work_order_no', '=', record.work_order_no)], limit=1):
                #     raise UserError(_('Image for Work Order not set for this Work Order No. !'))

    def get_wo_image_work_order(self):
        return self.env['mo.image.for.work.order'].sudo().search([('work_order_no', '=', self.work_order_no)], limit=1)

    def get_wo_image_line_list(self):
        mo_orders = self.env['mrp.production'].sudo().search([('work_order_no', '=', self.work_order_no)])
        product_ids = mo_orders.mapped('product_id')
        product_attribute_ids = product_ids.mapped('attribute_line_ids')

        line_list = []
        fabric_attribute_ids = product_attribute_ids.mapped('attribute_id').filtered(lambda x: x.attribute_type == 'fabric')

        for fabric_attribute_id in fabric_attribute_ids:
            fabric_value_ids = product_attribute_ids.filtered(lambda x: x.attribute_id.id == fabric_attribute_id.id).mapped('value_ids')

            for fabric_value_id in fabric_value_ids:
                fabric_grouped_product_ids = product_ids.mapped('product_template_attribute_value_ids').filtered(
                    lambda x: x.attribute_id.id == fabric_attribute_id.id and x.product_attribute_value_id.id == fabric_value_id.id).mapped('ptav_product_variant_ids').filtered(
                    lambda x: x.id in product_ids.ids)
                type_attribute_list = []

                type_attribute_ids = product_attribute_ids.filtered(lambda x: x.attribute_id.id == fabric_attribute_id.id) and product_attribute_ids.mapped('attribute_id').filtered(lambda x: x.attribute_type == 'type')
                for type_attribute_id in type_attribute_ids:

                    type_value_ids = product_attribute_ids.filtered(lambda x: x.attribute_id.id == type_attribute_id.id).mapped('value_ids')
                    for type_value_id in type_value_ids:
                        type_grouped_product_ids = fabric_grouped_product_ids.mapped('product_template_attribute_value_ids').filtered(
                            lambda x: x.attribute_id.id == type_attribute_id.id and x.product_attribute_value_id.id == type_value_id.id).mapped('ptav_product_variant_ids').filtered(
                            lambda x: x.id in fabric_grouped_product_ids.ids)
                        remarks = ''

                        size_attribute_list = []
                        size_attribute_ids = product_attribute_ids.filtered(lambda x: x.attribute_id.id == type_attribute_id.id) and product_attribute_ids.mapped('attribute_id').filtered(lambda x: x.attribute_type == 'size')
                        for size_attribute_id in size_attribute_ids:

                            size_value_ids = product_attribute_ids.filtered(lambda x: x.attribute_id.id == size_attribute_id.id).mapped('value_ids')
                            for size_value_id in size_value_ids:
                                size_grouped_product_ids = fabric_grouped_product_ids.mapped('product_template_attribute_value_ids').filtered(
                                    lambda x: x.attribute_id.id == size_attribute_id.id and x.product_attribute_value_id.id == size_value_id.id).mapped('ptav_product_variant_ids').filtered(
                                    lambda x: x.id in type_grouped_product_ids.ids)

                                final_mo_products = mo_orders.filtered(lambda x: x.product_id.id in size_grouped_product_ids.ids)
                                product_code = size_grouped_product_ids and size_grouped_product_ids[0] and size_grouped_product_ids[0].default_code or ''
                                if sum(final_mo_products.mapped('product_qty')):
                                    size_attribute_list.append({
                                        'product_code': product_code or '',
                                        'size_name': size_value_id.name,
                                        'grouped_qty': sum(final_mo_products.mapped('product_qty')) or 0,
                                    })
                                    remarks += ' ' + str(' '.join([i for i in final_mo_products.filtered(lambda x: x.remarks).mapped('remarks')]))

                        if size_attribute_list:
                            type_attribute_list.append({
                                'type_name': type_value_id.name,
                                'size_attribute_list': size_attribute_list,
                                'remarks': remarks,
                            })

                if type_attribute_list:
                    line_list.append({
                        'fabric_name': fabric_value_id.name,
                        'type_attribute_list': type_attribute_list,
                    })

        return line_list

    def get_raw_material_line_list(self):
        mo_orders = self.env['mrp.production'].sudo().search([('work_order_no', '=', self.work_order_no)])
        raw_product_unordered_ids = mo_orders.mapped('move_raw_ids').mapped('product_id')
        raw_product_ids = self.env['product.product'].sudo().search([('id', 'in', raw_product_unordered_ids.ids or [])], order='variant_name')

        line_list = []
        for raw_product_id in raw_product_ids:
            type_attribute_list = []
            raw_product_mos = mo_orders.mapped('move_raw_ids').filtered(lambda x: x.product_id.id == raw_product_id.id).mapped('raw_material_production_id')

            type_value_unordered_ids = raw_product_mos.mapped('product_id').mapped('product_template_attribute_value_ids').filtered(lambda x: x.attribute_id.attribute_type == 'type').mapped('product_attribute_value_id')
            type_value_ids = self.env['product.attribute.value'].sudo().search([('id', 'in', type_value_unordered_ids.ids or [])], order='name')
            for type_value_id in type_value_ids:
                type_product_ids = []

                for type_product_id in raw_product_mos:
                    if type_product_id.product_id.product_template_attribute_value_ids.filtered(lambda x: x.attribute_id.attribute_type == 'type' and x.product_attribute_value_id.id == type_value_id.id):
                        type_product_ids += [type_product_id.product_id.id]

                type_total_qty = sum(raw_product_mos.filtered(lambda x: x.product_id.id in type_product_ids).mapped('move_raw_ids').filtered(lambda x: x.product_id.id == raw_product_id.id).mapped('product_uom_qty')) or 0
                type_attribute_list.append({
                    'type_name': type_value_id.name,
                    'grouped_qty': type_total_qty or 0,
                })

            line_list.append({
                'product_image': raw_product_id.image_1920 or '',
                'product_code': raw_product_id.default_code or '',
                'item_information': raw_product_id.variant_name or '',
                'uom_name': raw_product_id.uom_id.name or '',
                'type_attribute_list': type_attribute_list,
            })
        return line_list

    def print_report(self):
        return self.env.ref('flemings_base.print_report_fg_work_order_summary').report_action(self)

    def generate_excel_report(self):
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'flemings_base.work_order_summary_report_wizard_xlsx'
        }


class FlemingsWorkOrderSummaryReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.work_order_summary_report_wizard_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Work Order Generation'

    def generate_xlsx_report(self, workbook, data, objects):
        align_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'border': 1})
        align_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'border': 1})

        align_left_bold = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True, 'border': 1})
        align_center_bold = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True, 'border': 1})

        row = 0
        for obj in objects:
            if obj.report_type == 'work_order':
                sheet = workbook.add_worksheet('Work Order Summary Report')
                report_title = 'Work Order Summary Report'
            elif obj.report_type == 'raw_material':
                sheet = workbook.add_worksheet('Raw Material Summary Report')
                report_title = 'Raw Material Summary Report'
            else:
                sheet = workbook.add_worksheet('Design, Specification')
                report_title = 'Design Board'

            for i in range(row, row + 5):
                sheet.set_row(i, 14)

            sheet.set_column('A:A', 12)
            sheet.set_column('B:C', 10)
            sheet.set_column('D:D', 12)
            sheet.set_column('E:O', 10)

            image_width = 300.0
            image_height = 180.0
            cell_width = 280.0
            cell_height = 98.0

            x_scale = cell_width / image_width
            y_scale = cell_height / image_height

            sheet.merge_range(row, 0, row + 5, 2, '', align_center_bold)
            if obj.company_id.logo:
                sheet.insert_image(
                    'A' + str(row + 1), '',
                    {'x_scale': x_scale, 'y_scale': y_scale, 'align': 'center', 'valign': 'vcenter',
                     'image_data': io.BytesIO(base64.b64decode(obj.company_id.logo))
                     }
                )

            sheet.merge_range(row, 3, row + 2, 9, str(obj.company_id.name), workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True, 'font_size': 16, 'border': 1}))
            sheet.merge_range(row + 3, 3, row + 5, 9, str(report_title), workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True, 'font_size': 22, 'border': 1}))

            sheet.merge_range(row, 10, row, 11, 'Work Order Number', align_center_bold)
            sheet.merge_range(row + 1, 10, row + 2, 11, str(obj.work_order_no), align_center)

            sheet.merge_range(row + 3, 10, row + 3, 11, 'Document Date', align_center_bold)
            sheet.merge_range(row + 4, 10, row + 5, 11, str(datetime.strftime(datetime.now(), '%d %b %Y')), align_center)

            mo_orders = self.env['mrp.production'].sudo().search([('work_order_no', '=', obj.work_order_no)])
            external_reference_list, internal_reference_list, summary_remarks_list, sales_persons = [], [], [], []

            for i in mo_orders.filtered(lambda x: x.origin_so_no).mapped('origin_so_no'):
                if i not in external_reference_list:
                    external_reference_list.append(str(i))
            external_reference = str(', '.join(external_reference_list))

            for i in mo_orders.filtered(lambda x: x.origin).mapped('origin'):
                if i not in internal_reference_list:
                    internal_reference_list.append(str(i))
            internal_reference = str(', '.join(internal_reference_list))

            for i in mo_orders.filtered(lambda x: x.summary_remarks).mapped('summary_remarks'):
                if i not in summary_remarks_list:
                    summary_remarks_list.append(str(i))
            summary_remarks = str(', '.join(summary_remarks_list))

            for mo_order in mo_orders.filtered(lambda x: x.origin_so_no):
                sale_id = self.env['sale.order'].sudo().search([('name', '=', mo_order.origin_so_no)], limit=1)
                if sale_id and sale_id.user_id and sale_id.user_id.name not in sales_persons:
                    sales_persons.append(str(sale_id.user_id.name))
            sales_person_data = str(', '.join(sales_persons))

            row += 6
            for i in range(row, row + 2):
                sheet.set_row(i, 24)
            sheet.merge_range(row, 0, row, 1, ' Contract Manufacturer: ', align_left_bold)
            sheet.merge_range(row, 2, row, 3, '', align_left)
            sheet.merge_range(row, 4, row, 5, ' Salesperson: ', align_left_bold)
            sheet.merge_range(row, 6, row, 7, ' ' + str(sales_person_data or ''), align_left)
            sheet.merge_range(row, 8, row, 9, ' Created By: ', align_left_bold)
            sheet.merge_range(row, 10, row, 11, ' ' + str(self.env.user.name or ''), align_left)

            row += 1
            sheet.merge_range(row, 0, row, 1, ' Customer: ', align_left_bold)
            sheet.merge_range(row, 2, row, 3, '', align_left)
            sheet.merge_range(row, 4, row, 5, ' External Reference: ', align_left_bold)
            sheet.merge_range(row, 6, row, 7, ' ' + str(external_reference or ''), align_left)
            sheet.merge_range(row, 8, row, 9, ' Internal Reference: ', align_left_bold)
            sheet.merge_range(row, 10, row, 11, ' ' + str(internal_reference or ''), align_left)

            if obj.report_type == 'work_order':
                sno = 1
                line_list = obj.get_wo_image_line_list()
                for fabric_line in line_list:
                    for type_line in fabric_line['type_attribute_list']:
                        row += 2
                        fabric_row = row + 9 + len(type_line['size_attribute_list'])

                        sheet.set_row(row, 22)
                        sheet.write(row, 0, 'S/N', align_center_bold)
                        sheet.merge_range(row, 1, row, 2, 'Fabric', align_center_bold)
                        sheet.write(row, 3, 'Type/Style', align_center_bold)
                        sheet.merge_range(row, 4, row, 5, 'Product Code', align_center_bold)
                        sheet.write(row, 6, 'Size', align_center_bold)
                        sheet.write(row, 7, 'Qty', align_center_bold)
                        sheet.merge_range(row, 8, row, 11, 'Remarks', align_center_bold)

                        row += 1
                        sheet.merge_range(row, 0, fabric_row, 0, sno, align_center)
                        sheet.merge_range(row, 1, fabric_row, 2, fabric_line['fabric_name'], align_center)
                        sheet.merge_range(row, 3, fabric_row, 3, type_line['type_name'], align_center)
                        sheet.merge_range(row, 8, fabric_row, 11, '', align_left)

                        size_qty_total = 0
                        for size_line in type_line['size_attribute_list']:
                            sheet.merge_range(row, 4, row, 5, size_line['product_code'], align_center)
                            sheet.write(row, 6, size_line['size_name'], align_center)
                            sheet.write(row, 7, size_line['grouped_qty'], align_center)

                            size_qty_total += size_line['grouped_qty']
                            row += 1

                        sheet.merge_range(fabric_row, 4, fabric_row, 6, 'Sub Total :', align_center_bold)
                        sheet.write(fabric_row, 7, size_qty_total, align_center_bold)

                        row = fabric_row
                        sno += 1

                row += 2
                sheet.merge_range(row, 0, row + 8, 11, "\u0332".join('Summary Remarks') + '\n\n' + str(summary_remarks or ''), workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'top', 'text_wrap': True, 'border': 1}))

            elif obj.report_type == 'raw_material':
                row += 2
                sheet.set_row(row, 22)
                sheet.set_column('I:I', 16)

                sheet.merge_range(row, 0, row, 1, 'Product Image', align_center_bold)
                sheet.merge_range(row, 2, row, 3, 'Product Code', align_center_bold)
                sheet.merge_range(row, 4, row, 6, 'Item Information', align_center_bold)
                sheet.write(row, 7, 'UOM', align_center_bold)
                sheet.write(row, 8, 'Type', align_center_bold)
                sheet.write(row, 9, 'Qty', align_center_bold)
                sheet.merge_range(row, 10, row, 11, 'Remarks', align_center_bold)

                raw_image_width = 600.0
                raw_image_height = 330.0
                raw_cell_width = 280.0
                raw_cell_height = 98.0

                raw_x_scale = raw_cell_width / raw_image_width
                raw_y_scale = raw_cell_height / raw_image_height

                line_list = obj.get_raw_material_line_list()
                for raw_line in line_list:
                    type_row = row + 3 + len(raw_line['type_attribute_list'])
                    row += 1

                    sheet.merge_range(row, 0, type_row, 1, '', align_center)
                    if raw_line['product_image']:
                        sheet.insert_image(
                            'A' + str(row + 2), '',
                            {'x_scale': raw_x_scale, 'y_scale': raw_y_scale, 'align': 'center', 'valign': 'vcenter',
                             'image_data': io.BytesIO(base64.b64decode(raw_line['product_image']))
                             }
                        )

                    sheet.merge_range(row, 2, type_row, 3, raw_line['product_code'], align_center)
                    sheet.merge_range(row, 4, type_row, 6, raw_line['item_information'], align_center)
                    sheet.merge_range(row, 7, type_row, 7, raw_line['uom_name'], align_center)
                    sheet.merge_range(row, 10, type_row, 11, '', align_left)

                    type_qty_total = 0
                    for type_line in raw_line['type_attribute_list']:
                        sheet.write(row, 8, type_line['type_name'], align_center)
                        sheet.write(row, 9, type_line['grouped_qty'], align_center)

                        type_qty_total += type_line['grouped_qty']
                        row += 1

                    sheet.write(type_row, 8, 'Sub Total :', align_center_bold)
                    sheet.write(type_row, 9, type_qty_total, align_center_bold)

                    row = type_row
                    row += 1

            else:
                row += 2
                sheet.merge_range(row, 0, row + 19, 3, '', align_left)
                sheet.merge_range(row, 4, row + 19, 7, '', align_left)
                sheet.merge_range(row, 8, row + 19, 11, '', align_left)

                row += 20
                sheet.merge_range(row, 0, row + 19, 3, '', align_left)
                sheet.merge_range(row, 4, row + 19, 7, '', align_left)
                sheet.merge_range(row, 8, row + 19, 11, '', align_left)

                row += 20
                sheet.merge_range(row, 0, row + 19, 3, '', align_left)
                sheet.merge_range(row, 4, row + 19, 7, '', align_left)
                sheet.merge_range(row, 8, row + 19, 11, '', align_left)
