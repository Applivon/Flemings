import time
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta


class InventoryDetailedReport(models.TransientModel):
    _name = 'inventory.detailed.report.wizard'
    _description = 'Inventory Detailed Report'

    from_date = fields.Date('FROM Date', default=lambda *a: str(datetime.now() + relativedelta(day=1))[:10])
    to_date = fields.Date('To Date', default=lambda *a: str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10])
    company_ids = fields.Many2many('res.company', string='Companies', default=lambda self: self.env.company.ids)
    location_ids = fields.Many2many('stock.location', string='Location(s)', domain="[('usage', '=', 'internal')]")
    product_ids = fields.Many2many('product.product', string='Product(s)')
    sgd_currency_id = fields.Many2one('res.currency', string='SGD Currency', default=lambda self: self.env['res.currency'].search([('name', '=', 'SGD')], limit=1))

    file_data = fields.Binary('Download file', readonly=True)
    filename = fields.Char('Filename', size=64, readonly=True)

    @api.onchange('from_date', 'to_date')
    def onchange_to_date(self):
        if self.to_date and self.from_date and self.to_date < self.from_date:
            self.to_date = False
            return {'warning': {
                'title': _("Warning"),
                'message': _("To Date must be greater than or equal to FROM Date..!")}
            }

    def generate_excel_report(self):
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'flemings_base.inventory_detailed_report_wizard_xlsx'
        }

    def get_utc_datetime(self, date_time):
        local = pytz.timezone(self.env.user.tz)
        naive = datetime.strptime(str(date_time), "%Y-%m-%d %H:%M:%S")
        local_dt = local.localize(naive, is_dst=None)
        return local_dt.astimezone(pytz.utc)
    
    def get_inventory_data(self, from_date, to_date, where, location_where, location_dest_where):
        self.env.cr.execute(""" 
          SELECT a.company_id, a.product_id, uom.name::json->>'en_US' AS stocking_unit,
            product.default_code AS product_code, product.variant_name AS product_description,
            COALESCE(MAX(b.beginning_balance_qty), 0) AS beginning_balance_qty, 
            COALESCE(MAX(c.purchase_receive_qty), 0) AS purchase_receive_qty, 
            COALESCE(ABS(MAX(d.purchase_return_qty)), 0) AS purchase_return_qty, 
            COALESCE(ABS(MAX(e.sales_issued_qty)), 0) AS sales_issued_qty, 
            COALESCE(MAX(f.sales_return_qty), 0) AS sales_return_qty, 
            COALESCE(ABS(MAX(g.transfer_out_qty)), 0) AS transfer_out_qty, 
            COALESCE(MAX(h.transfer_in_qty), 0) AS transfer_in_qty,
            COALESCE(MAX(i.stock_adjust_qty), 0) AS stock_adjust_qty, 
            COALESCE(ABS(MAX(j.stock_disposal_qty)), 0) AS stock_disposal_qty, 
            COALESCE(MAX(k.ending_balance_qty), 0) AS ending_balance_qty, 
            COALESCE(MAX(l.avg_cost), 0) AS avg_cost,
            (COALESCE(MAX(k.ending_balance_qty), 0) * COALESCE(MAX(l.avg_cost), 0)) AS final_stock_value
          
          FROM (
            SELECT layer.company_id, layer.product_id FROM stock_valuation_layer AS layer WHERE %s
          ) a
          
          LEFT JOIN (
            SELECT SUM(layer.quantity) AS beginning_balance_qty, layer.company_id, layer.product_id 
            FROM stock_valuation_layer AS layer WHERE layer.create_date < '%s'
            GROUP BY layer.company_id, layer.product_id
          ) b
          ON a.company_id = b.company_id AND a.product_id = b.product_id 
          
          LEFT JOIN (
            SELECT SUM(layer.quantity) AS purchase_receive_qty, layer.company_id, layer.product_id
            FROM stock_valuation_layer AS layer
            LEFT JOIN stock_move AS mov ON mov.id = layer.stock_move_id
            LEFT JOIN stock_picking AS picking ON picking.id = mov.picking_id
            LEFT JOIN stock_picking_type AS picking_type ON picking_type.id = picking.picking_type_id
            WHERE picking_type.code = 'incoming' AND layer.create_date >= '%s' and layer.create_date <= '%s'
              AND picking.id not in (
                SELECT sub_picking.id FROM stock_picking AS sub_picking 
                LEFT JOIN stock_move AS sub_move ON sub_move.picking_id = sub_picking.id 
                WHERE mov.origin_returned_move_id IS NOT NULL AND sub_picking.id = picking.id
              )
            GROUP BY layer.company_id, layer.product_id
          ) c
          ON a.company_id = c.company_id and a.product_id = c.product_id 
          
          LEFT JOIN (
            SELECT SUM(layer.quantity) AS purchase_return_qty, layer.company_id, layer.product_id
            FROM stock_valuation_layer AS layer
            LEFT JOIN stock_move AS mov ON mov.id = layer.stock_move_id
            LEFT JOIN stock_picking AS picking ON picking.id = mov.picking_id
            LEFT JOIN stock_picking_type AS picking_type ON picking_type.id = picking.picking_type_id
            WHERE picking_type.code = 'outgoing' AND layer.create_date >= '%s' AND layer.create_date <= '%s'
              AND picking.id not in (
                SELECT sub_picking.id FROM stock_picking AS sub_picking 
                LEFT JOIN stock_move AS sub_move ON sub_move.picking_id = sub_picking.id 
                WHERE mov.origin_returned_move_id IS NULL AND sub_picking.id = picking.id
              )
            GROUP BY layer.company_id, layer.product_id
          ) d
          ON a.company_id = d.company_id AND a.product_id = d.product_id
          
          LEFT JOIN (
            SELECT SUM(layer.quantity) AS sales_issued_qty, layer.company_id, layer.product_id
            FROM stock_valuation_layer AS layer
            LEFT JOIN stock_move AS mov ON mov.id = layer.stock_move_id
            LEFT JOIN stock_picking AS picking ON picking.id = mov.picking_id
            LEFT JOIN stock_picking_type AS picking_type ON picking_type.id = picking.picking_type_id
            WHERE picking_type.code = 'outgoing' AND layer.create_date >= '%s' AND layer.create_date <= '%s'
              AND picking.id not in (
                SELECT sub_picking.id FROM stock_picking AS sub_picking 
                LEFT JOIN stock_move AS sub_move ON sub_move.picking_id = sub_picking.id 
                WHERE mov.origin_returned_move_id IS NOT NULL AND sub_picking.id = picking.id
              )
            GROUP BY layer.company_id, layer.product_id
          ) e
          ON a.company_id = e.company_id and a.product_id = e.product_id
          
          LEFT JOIN (
            SELECT SUM(layer.quantity) AS sales_return_qty, layer.company_id, layer.product_id
            FROM stock_valuation_layer AS layer
            LEFT JOIN stock_move AS mov ON mov.id = layer.stock_move_id
            LEFT JOIN stock_picking AS picking ON picking.id = mov.picking_id
            LEFT JOIN stock_picking_type AS picking_type ON picking_type.id = picking.picking_type_id
            WHERE picking_type.code = 'incoming' AND layer.create_date >= '%s' AND layer.create_date <= '%s'
              AND picking.id not in (
                SELECT sub_picking.id FROM stock_picking AS sub_picking 
                LEFT JOIN stock_move AS sub_move ON sub_move.picking_id = sub_picking.id 
                WHERE mov.origin_returned_move_id IS NULL AND sub_picking.id = picking.id
              )
            GROUP BY layer.company_id, layer.product_id
          ) f
          ON a.company_id = f.company_id and a.product_id = f.product_id
          
          LEFT JOIN (
            SELECT SUM(layer.quantity) AS transfer_out_qty, layer.company_id, layer.product_id
            FROM stock_valuation_layer AS layer
            LEFT JOIN stock_move AS mov ON mov.id = layer.stock_move_id
            LEFT JOIN stock_picking AS picking ON picking.id = mov.picking_id
            LEFT JOIN stock_picking_type AS picking_type ON picking_type.id = picking.picking_type_id
            WHERE %s AND picking_type.code = 'internal'
              AND layer.create_date >= '%s' and layer.create_date <= '%s'
            GROUP BY layer.company_id, layer.product_id
          ) g
          ON a.company_id = g.company_id and a.product_id = g.product_id
          
          LEFT JOIN (
            SELECT SUM(layer.quantity) AS transfer_in_qty, layer.company_id, layer.product_id
            FROM stock_valuation_layer AS layer
            LEFT JOIN stock_move AS mov ON mov.id = layer.stock_move_id
            LEFT JOIN stock_picking AS picking ON picking.id = mov.picking_id
            LEFT JOIN stock_picking_type AS picking_type ON picking_type.id = picking.picking_type_id
            WHERE %s AND picking_type.code = 'internal'
              AND layer.create_date >= '%s' AND layer.create_date <= '%s'
            GROUP BY layer.company_id, layer.product_id
          ) h
          ON a.company_id = h.company_id and a.product_id = h.product_id
          
          LEFT JOIN (
            SELECT SUM(layer.quantity) AS stock_adjust_qty, layer.company_id, layer.product_id
            FROM stock_valuation_layer AS layer
            LEFT JOIN stock_move AS mov ON mov.id = layer.stock_move_id
            WHERE mov.is_inventory = true AND layer.create_date >= '%s' AND layer.create_date <= '%s'
            GROUP BY layer.company_id, layer.product_id
          ) i
          ON a.company_id = i.company_id AND a.product_id = i.product_id 
          
          LEFT JOIN (
            SELECT SUM(layer.quantity) AS stock_disposal_qty, layer.company_id, layer.product_id
            FROM stock_valuation_layer AS layer
            LEFT JOIN stock_move AS mov ON mov.id = layer.stock_move_id
            WHERE mov.scrapped = true AND layer.create_date >= '%s' AND layer.create_date <= '%s'
            GROUP BY layer.company_id, layer.product_id
          ) j
          ON a.company_id = j.company_id AND a.product_id = j.product_id
          
          LEFT JOIN (
            SELECT layer.company_id, layer.product_id, SUM(layer.quantity) AS ending_balance_qty
            FROM stock_valuation_layer AS layer WHERE layer.create_date <= '%s'
            GROUP BY layer.product_id, layer.company_id
          ) k
          ON a.company_id = k.company_id and a.product_id = k.product_id
          
          LEFT JOIN (
            SELECT layer.company_id, layer.product_id, layer.unit_cost AS avg_cost
            FROM stock_valuation_layer AS layer WHERE layer.create_date <= '%s'
            ORDER BY layer.create_date desc LIMIT 1
          ) l
          ON a.company_id = l.company_id and a.product_id = l.product_id
        
        LEFT JOIN product_product AS product ON product.id = a.product_id
        LEFT JOIN product_template AS product_tmpl ON product_tmpl.id = product.product_tmpl_id
        LEFT JOIN uom_uom AS uom ON uom.id = product_tmpl.uom_id
        GROUP BY a.company_id, a.product_id, product.variant_name, product.default_code, uom.name 
        """ % (
            where, from_date, from_date, to_date, from_date, to_date, from_date, to_date,
            from_date, to_date, location_where, from_date, to_date, location_dest_where,
            from_date, to_date, from_date, to_date, from_date, to_date, to_date, to_date
        ))
        return [i for i in self.env.cr.dictfetchall()]


class FlemingsInventoryDetailedReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.inventory_detailed_report_wizard_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Inventory Detailed Report'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('INVENTORY REPORT')

        align_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        align_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True})
        align_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        align_bold_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True, 'border': 1})

        for obj in objects:
            sheet.set_row(0, 24)
            sheet.set_row(1, 22)
            sheet.set_row(3, 18)
            sheet.set_row(4, 18)
            sheet.set_row(6, 18)
            sheet.set_row(7, 18)

            sheet.set_column('A:A', 22)
            sheet.set_column('B:B', 40)
            sheet.set_column('C:C', 16)
            sheet.set_column('D:D', 18)
            if obj.location_ids:
                sheet.set_column('E:J', 14)
                sheet.set_column('K:O', 18)
            else:
                sheet.set_column('E:H', 14)
                sheet.set_column('I:M', 18)

            company_id = obj.company_ids and obj.company_ids[0]
            currency_id = company_id.currency_id or obj.sgd_currency_id

            row = 0
            sheet.merge_range(row, 0, row, 4, 'INVENTORY DETAILED REPORT', workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 16}))

            row += 1
            sheet.merge_range(row, 0, row, 4, str(company_id.name).upper(), workbook.add_format(
                {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 14}))

            row += 2
            sheet.write(row, 0, 'From', align_bold_left)
            sheet.write(row, 1, str(datetime.strftime(obj.from_date, '%d-%m-%Y')), align_left)

            row += 1
            sheet.write(row, 0, 'To', align_bold_left)
            sheet.write(row, 1, str(datetime.strftime(obj.to_date, '%d-%m-%Y')), align_left)

            row += 2
            row_column = 0
            sheet.merge_range(row, row_column, row + 1, row_column, 'Product Code', align_bold_center)
            sheet.merge_range(row, row_column + 1, row + 1, row_column + 1, 'Product Description', align_bold_center)
            sheet.merge_range(row, row_column + 2, row + 1, row_column + 2, 'Stocking Unit', align_bold_center)
            sheet.merge_range(row, row_column + 3, row + 1, row_column + 3, 'Beginning Balance', align_bold_center)

            sheet.merge_range(row, row_column + 4, row, row_column + 5, 'Purchase', align_bold_center)
            sheet.write(row + 1, row_column + 4, 'Receive', align_bold_center)
            sheet.write(row + 1, row_column + 5, 'Return', align_bold_center)

            row_column += 5
            if obj.location_ids:
                sheet.merge_range(row, row_column + 1, row, row_column + 2, 'Transfer', align_bold_center)
                sheet.write(row + 1, row_column + 1, 'Out', align_bold_center)
                sheet.write(row + 1, row_column + 2, 'In', align_bold_center)
                row_column += 2

            sheet.merge_range(row, row_column + 1, row, row_column + 2, 'Sales', align_bold_center)
            sheet.write(row + 1, row_column + 1, 'Issued', align_bold_center)
            sheet.write(row + 1, row_column + 2, 'Return', align_bold_center)

            row_column += 2
            sheet.merge_range(row, row_column + 1, row + 1, row_column + 1, 'Stock Adjust', align_bold_center)
            sheet.merge_range(row, row_column + 2, row + 1, row_column + 2, 'Stock Disposal', align_bold_center)
            sheet.merge_range(row, row_column + 3, row + 1, row_column + 3, 'Ending Balance', align_bold_center)
            sheet.merge_range(row, row_column + 4, row + 1, row_column + 4, 'Avg Cost', align_bold_center)
            sheet.merge_range(row, row_column + 5, row + 1, row_column + 5, 'Stock Value', align_bold_center)

            from_date_time = datetime.combine(obj.from_date, time.min).replace(microsecond=0)
            from_date = obj.get_utc_datetime(from_date_time)
            to_date_time = datetime.combine(obj.to_date, time.max).replace(microsecond=0)
            to_date = obj.get_utc_datetime(to_date_time)

            stock_valuation_env = self.env['stock.valuation.layer'].sudo()
            product_domain = [('create_date', '<=', to_date), ('company_id', '=', company_id.id)]
            if obj.product_ids:
                product_domain += [('product_id', 'in', obj.product_ids.ids or [])]

            row += 2
            product_ids = stock_valuation_env.search(product_domain).mapped('product_id')

            where = "layer.company_id = %s" % company_id.id
            if product_ids:
                products = tuple(product_ids.ids)
                if len(products) == 1:
                    where += "AND layer.product_id = %s" % products
                else:
                    where += "AND layer.product_id in %s" % (products,)

            if obj.location_ids:
                locations = tuple(obj.location_ids.ids)
                if len(locations) == 1:
                    location_where = "mov.location_id = %s" % locations
                    location_dest_where = "mov.location_dest_id = %s" % locations
                else:
                    location_where = "mov.location_id in %s" % (locations,)
                    location_dest_where = "mov.location_dest_id in %s" % (locations,)
            else:
                location_where = "mov.location_id = 0"
                location_dest_where = "mov.location_dest_id = 0"

            line_list = obj.get_inventory_data(from_date, to_date, where, location_where, location_dest_where)
            if product_ids and line_list:
                for line in line_list:
                    row_column = 0
                    sheet.write(row, row_column, str(line['product_code'] or ''), align_left)
                    sheet.write(row, row_column + 1, str(line['product_description'] or ''), align_left)
                    sheet.write(row, row_column + 2, str(line['stocking_unit'] or ''), align_left)
                    sheet.write(row, row_column + 3, str('%.2f' % line['beginning_balance_qty'] or 0), align_right)
                    sheet.write(row, row_column + 4, str('%.2f' % line['purchase_receive_qty'] or 0), align_right)
                    sheet.write(row, row_column + 5, str('%.2f' % line['purchase_return_qty'] or 0), align_right)

                    row_column += 5
                    if obj.location_ids:
                        sheet.write(row, row_column + 1, str('%.2f' % line['transfer_out_qty'] or 0), align_right)
                        sheet.write(row, row_column + 2, str('%.2f' % line['transfer_in_qty'] or 0), align_right)
                        row_column += 2

                    sheet.write(row, row_column + 1, str('%.2f' % line['sales_issued_qty'] or 0), align_right)
                    sheet.write(row, row_column + 2, str('%.2f' % line['sales_return_qty'] or 0), align_right)

                    row_column += 2
                    sheet.write(row, row_column + 1, str('%.2f' % line['stock_adjust_qty'] or 0), align_right)
                    sheet.write(row, row_column + 2, str('%.2f' % line['stock_disposal_qty'] or 0), align_right)
                    sheet.write(row, row_column + 3, str('%.2f' % line['ending_balance_qty'] or 0), align_right)
                    sheet.write(row, row_column + 4, str(currency_id.symbol or '') + ' ' + str('%.2f' % line['avg_cost'] or 0), align_right)
                    sheet.write(row, row_column + 5, str(currency_id.symbol or '') + ' ' + str('%.2f' % line['final_stock_value'] or 0), align_right)

                    row += 1

            # if product_ids:
            #     for product_id in product_ids:
            #         beginning_balance_qty = sum(stock_valuation_env.search([
            #             ('create_date', '<=', from_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id)
            #         ]).mapped('quantity')) or 0
            #
            #         stock_adjust_qty = sum(stock_valuation_env.search([
            #             ('create_date', '>=', from_date), ('create_date', '<=', to_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id), ('stock_move_id.is_inventory', '=', True)
            #         ]).mapped('quantity')) or 0
            #
            #         stock_disposal_qty = sum(stock_valuation_env.search([
            #             ('create_date', '>=', from_date), ('create_date', '<=', to_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id), ('stock_move_id.scrapped', '=', True)
            #         ]).mapped('quantity')) or 0
            #
            #         purchase_receive_qty = sum(stock_valuation_env.search([
            #             ('create_date', '>=', from_date), ('create_date', '<=', to_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id), ('stock_move_id.purchase_line_id', '!=', False), ('stock_move_id.picking_id.picking_type_id.code', '=', 'incoming')
            #         ]).mapped('quantity')) or 0
            #
            #         purchase_return_qty = sum(stock_valuation_env.search([
            #             ('create_date', '>=', from_date), ('create_date', '<=', to_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id), ('stock_move_id.purchase_line_id', '!=', False), ('stock_move_id.picking_id.picking_type_id.code', '=', 'outgoing')
            #         ]).mapped('quantity')) or 0
            #
            #         if obj.location_ids:
            #             transfer_out_qty = sum(stock_valuation_env.search([
            #                 ('create_date', '>=', from_date), ('create_date', '<=', to_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id), ('stock_move_id.location_id', 'in', obj.location_ids.ids), ('stock_move_id.picking_id.picking_type_id.code', '=', 'internal')
            #             ]).mapped('quantity')) or 0
            #
            #             transfer_in_qty = sum(stock_valuation_env.search([
            #                 ('create_date', '>=', from_date), ('create_date', '<=', to_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id), ('stock_move_id.location_dest_id', 'in', obj.location_ids.ids), ('stock_move_id.picking_id.picking_type_id.code', '=', 'internal')
            #             ]).mapped('quantity')) or 0
            #
            #         else:
            #             transfer_out_qty = transfer_in_qty = 0
            #
            #         sales_issued_qty = sum(stock_valuation_env.search([
            #             ('create_date', '>=', from_date), ('create_date', '<=', to_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id), ('stock_move_id.sale_line_id', '!=', False), ('stock_move_id.picking_id.picking_type_id.code', '=', 'outgoing')
            #         ]).mapped('quantity')) or 0
            #
            #         sales_return_qty = sum(stock_valuation_env.search([
            #             ('create_date', '>=', from_date), ('create_date', '<=', to_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id), ('stock_move_id.sale_line_id', '!=', False), ('stock_move_id.picking_id.picking_type_id.code', '=', 'incoming')
            #         ]).mapped('quantity')) or 0
            #
            #         ending_balance_ids = stock_valuation_env.search([
            #             ('create_date', '<=', to_date), ('product_id', '=', product_id.id), ('company_id', '=', company_id.id)
            #         ])
            #         ending_balance_qty = sum(ending_balance_ids.mapped('quantity')) or 0
            #         average_cost = (sum(ending_balance_ids.mapped('value')) / ending_balance_qty) if ending_balance_qty else 0
            #         final_stock_value = ending_balance_qty * average_cost

            else:
                sheet.merge_range(row + 1, 0, row + 1, 4, 'No Record(s) found', workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True}))
