from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class WorkOrderSummaryReport(models.TransientModel):
    _name = 'work.order.summary.report.wizard'
    _description = 'Work Order Generation'

    work_order_no = fields.Char('Work Order No.', required=True)
    report_type = fields.Selection([
        ('work_order', 'Work Order Summary Report'), ('raw_material', 'Raw Material Summary Report'), ('design', 'Design Specification')
    ], default='work_order', string='Report Type')

    @api.constrains('work_order_no')
    def check_work_order_no_exists(self):
        for record in self:
            if record.work_order_no:
                if not self.env['mrp.production.work.order.no'].sudo().search([('work_order_no', '=', record.work_order_no)]):
                    raise UserError(_('Work Order No. not exists !'))

                if not self.env['mrp.production'].sudo().search([('work_order_no', '=', record.work_order_no)]):
                    raise UserError(_('Manufacturing Orders not exists for this Work Order No. !'))

                if not self.env['mo.image.for.work.order'].sudo().search([('work_order_no', '=', record.work_order_no)], limit=1):
                    raise UserError(_('Image for Work Order not set for this Work Order No. !'))

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
                                if sum(final_mo_products.mapped('product_qty')):
                                    size_attribute_list.append({
                                        'size_name': size_value_id.name,
                                        'grouped_qty': sum(final_mo_products.mapped('product_qty')) or 0,
                                    })
                                    remarks += ' ' + str(' '.join([i for i in final_mo_products.filtered(lambda x: x.remarks).mapped('remarks')]))

                        type_attribute_list.append({
                            'type_name': type_value_id.name,
                            'size_attribute_list': size_attribute_list,
                            'remarks': remarks,
                        })

                line_list.append({
                    'fabric_name': fabric_value_id.name,
                    'type_attribute_list': type_attribute_list,
                })

        return line_list

    def print_report(self):
        return self.env.ref('flemings_base.print_report_fg_work_order_summary').report_action(self)
