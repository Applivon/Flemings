# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero

import json
from lxml import etree

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta

from odoo.exceptions import Warning
from odoo.exceptions import UserError, ValidationError


class StockSchedulerCompute(models.TransientModel):
    _name = 'fg.stock.low.scheduler'
    _description = 'Run Stock Low Schedule'

    type = fields.Selection(string='Type', default='by_location', selection=[
        ('by_location', 'By Location'), ('by_consolidation', 'By Consolidation')], required=True)

    def get_stock_low_products(self):
        if self.type == 'by_location':
            product_domain_loc = self.env['product.product']._get_domain_locations()[0]
            domain_location_ids = self.env['stock.quant'].sudo().search(product_domain_loc).mapped('location_id').ids or []

            where = ''
            location_ids = tuple(domain_location_ids)
            if len(location_ids) == 1:
                where += " AND quant.location_id = %s" % location_ids
            else:
                where += " AND quant.location_id in %s" % (location_ids,)

            self.env.cr.execute(""" SELECT quant.id FROM stock_quant AS quant
               LEFT JOIN product_product AS prod ON prod.id = quant.product_id
               WHERE quant.quantity < (
                 SELECT product_min_qty FROM stock_warehouse_orderpoint 
                 WHERE location_id = quant.location_id AND product_id = quant.product_id
               ) AND prod.active = True %s """ % where)

            quant_ids = [i for j in self.env.cr.fetchall() for i in j]

            action = self.env['ir.actions.actions']._for_xml_id('flemings_base.fg_stock_low_action')
            action['domain'] = [('id', 'in', quant_ids)]
            return action

        else:
            self.env.cr.execute(""" SELECT quant.id FROM stock_quant_by_consolidation AS quant
                LEFT JOIN product_product AS prod ON prod.id = quant.product_id
                WHERE quant.quantity < prod.min_stock_quantity AND prod.active = True """)
            quant_ids = [i for j in self.env.cr.fetchall() for i in j]

            action = self.env['ir.actions.actions']._for_xml_id('flemings_base.fg_stock_low_by_consolidation_action')
            action['domain'] = [('id', 'in', quant_ids)]
            return action


class FlemingsStockQuantsByConsolidation(models.Model):
    _name = 'stock.quant.by.consolidation'
    _description = 'Stock Quants By Consolidation'

    product_id = fields.Many2one('product.product', string='Product')
    min_stock_quantity = fields.Float(related='product_id.min_stock_quantity', string='Minimum Stock Level')

    quantity = fields.Float(
        'On Hand Quantity',
        help='Quantity of products in this quant, in the default unit of measure of the product',
        readonly=True, digits='Product Unit of Measure')
    reserved_quantity = fields.Float(
        'Reserved Quantity', default=0.0, readonly=True, required=True, digits='Product Unit of Measure',
        help='Quantity of reserved products in this quant, in the default unit of measure of the product')
    available_quantity = fields.Float(
        'Available Quantity', default=0.0, readonly=True, digits='Product Unit of Measure',
        help="On hand quantity which hasn't been reserved on a transfer, in the default unit of measure of the product")


class FlemingsStockQuants(models.Model):
    _inherit = 'stock.quant'
    _description = 'Stock Quants'

    min_stock_quantity = fields.Float(compute='_get_quant_reordering_product_min_qty', string='Minimum Stock Level')

    @api.depends('location_id', 'product_id')
    def _get_quant_reordering_product_min_qty(self):
        for record in self.filtered(lambda x: x.location_id and x.product_id):
            record.min_stock_quantity = sum(self.env['stock.warehouse.orderpoint'].sudo().search(
                [('location_id', '=', record.location_id.id), ('product_id', '=', record.product_id.id)]
            ).mapped('product_min_qty')) or 0

    def write(self, vals):
        res = super(FlemingsStockQuants, self).write(vals)
        if 'product_id' in vals or 'location_id' in vals or 'quantity' in vals or 'reserved_quantity' in vals:
            product_domain_loc = self.env['product.product']._get_domain_locations()[0]
            domain_location_ids = self.env['stock.quant'].sudo().search(product_domain_loc).mapped('location_id')

            for record in self.filtered(lambda x: x.location_id and x.product_id and x.location_id in domain_location_ids):
                quants = self.sudo().search([
                    ('location_id', 'in', domain_location_ids.ids),
                    ('product_id', '=', record.product_id.id)
                ])
                consolidated_qty = sum(quants.mapped('quantity')) or 0
                consolidated_reserved_qty = sum(quants.mapped('reserved_quantity'))

                exist_quant_consolidation = self.env['stock.quant.by.consolidation'].sudo().search(
                    [('product_id', '=', record.product_id.id)])
                if exist_quant_consolidation:
                    exist_quant_consolidation.sudo().write({
                        'quantity': consolidated_qty,
                        'reserved_quantity': consolidated_reserved_qty,
                        'available_quantity': consolidated_qty - consolidated_reserved_qty,
                    })
                else:
                    self.env['stock.quant.by.consolidation'].sudo().create({
                        'product_id': record.product_id.id,
                        'quantity': consolidated_qty,
                        'reserved_quantity': consolidated_reserved_qty,
                        'available_quantity': consolidated_qty - consolidated_reserved_qty
                    })

        return res

    @api.model
    def _unlink_zero_quants(self):
        """ _update_available_quantity may leave quants with no
        quantity and no reserved_quantity. It used to directly unlink
        these zero quants but this proved to hurt the performance as
        this method is often called in batch and each unlink invalidate
        the cache. We defer the calls to unlink in this method.
        """
        # precision_digits = max(6, self.sudo().env.ref('product.decimal_product_uom').digits * 2)
        # # Use a select instead of ORM search for UoM robustness.
        # query = """SELECT id FROM stock_quant WHERE (round(quantity::numeric, %s) = 0 OR quantity IS NULL)
        #                                              AND round(reserved_quantity::numeric, %s) = 0
        #                                              AND (round(inventory_quantity::numeric, %s) = 0 OR inventory_quantity IS NULL)
        #                                              AND user_id IS NULL;"""
        # params = (precision_digits, precision_digits, precision_digits)
        # self.env.cr.execute(query, params)
        # quant_ids = self.env['stock.quant'].browse([quant['id'] for quant in self.env.cr.dictfetchall()])
        # quant_ids.sudo().unlink()
        return

    def _apply_inventory(self):
        self = self.sudo()
        move_vals = []
        # if not self.user_has_groups('stock.group_stock_manager'):
        #     raise UserError(_('Only a stock manager can validate an inventory adjustment.'))
        for quant in self:
            # Create and validate a move so that the quant matches its `inventory_quantity`.
            if float_compare(quant.inventory_diff_quantity, 0, precision_rounding=quant.product_uom_id.rounding) > 0:
                move_vals.append(
                    quant._get_inventory_move_values(quant.inventory_diff_quantity,
                                                     quant.product_id.with_company(quant.company_id).property_stock_inventory,
                                                     quant.location_id))
            else:
                move_vals.append(
                    quant._get_inventory_move_values(-quant.inventory_diff_quantity,
                                                     quant.location_id,
                                                     quant.product_id.with_company(quant.company_id).property_stock_inventory,
                                                     out=True))
        moves = self.env['stock.move'].with_context(inventory_mode=False).create(move_vals)
        moves._action_done()
        self.location_id.write({'last_inventory_date': fields.Date.today()})
        date_by_location = {loc: loc._get_next_inventory_date() for loc in self.mapped('location_id')}
        for quant in self:
            quant.inventory_date = date_by_location[quant.location_id]
        self.write({'inventory_quantity': 0, 'user_id': False})
        self.write({'inventory_diff_quantity': 0})


class FlemingsStockReorderingRules(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    def create_flemings_product_quant(self):
        for record in self:
            exist_product_quant = self.env['stock.quant'].sudo().search([
                ('location_id', '=', record.location_id.id), ('product_id', '=', record.product_id.id)
            ])
            if not exist_product_quant:
                new_product_quant = self.env['stock.quant'].sudo().create({
                    'location_id': record.location_id.id,
                    'product_id': record.product_id.id,
                    'quantity': 0,
                    'inventory_quantity': 0,
                })
                new_product_quant.action_apply_inventory()

    @api.model
    def create(self, vals):
        res = super(FlemingsStockReorderingRules, self).create(vals)
        # Create Stock Quant for Product if not exists
        if 'location_id' in vals and 'product_id' in vals:
            res.create_flemings_product_quant()
        return res

    def write(self, vals):
        res = super(FlemingsStockReorderingRules, self).write(vals)
        # Create Stock Quant for Product if not exists
        if 'location_id' in vals and 'product_id' in vals:
            self.create_flemings_product_quant()

        return res


class FlemingsStockProductTemplate(models.Model):
    _inherit = 'product.template'

    min_stock_quantity = fields.Float('Minimum Stock Level', default=0)

    @api.model
    def create(self, vals):
        res = super(FlemingsStockProductTemplate, self).create(vals)
        for record in res:
            # Update Variant Minimum Stock Level
            # if 'min_stock_quantity' in vals:
            #     for variant in record.product_variant_ids:
            #         variant.min_stock_quantity = record.min_stock_quantity
            if 'min_stock_quantity' in vals and vals.get('min_stock_quantity') > 0 and record.product_variant_count > 1:
                record.min_stock_quantity = 0

        return res

    def write(self, vals):
        res = super(FlemingsStockProductTemplate, self).write(vals)
        for record in self:
            # Update Variant Minimum Stock Level
            # if 'min_stock_quantity' in vals:
            #     for variant in record.product_variant_ids:
            #         variant.min_stock_quantity = record.min_stock_quantity
            if 'min_stock_quantity' in vals and vals.get('min_stock_quantity') > 0 and record.product_variant_count > 1:
                record.min_stock_quantity = 0

        return res


class FlemingsStockProductProduct(models.Model):
    _inherit = 'product.product'

    min_stock_quantity = fields.Float('Minimum Stock Level', default=0)

    def create_flemings_product_quant(self):
        for record in self:
            exist_product_quant = self.env['stock.quant'].sudo().search([('product_id', '=', record.id)])
            location_id = self.env['stock.location'].sudo().search([('company_id', '=', self.env.company.id), ('usage', 'in', ['internal', 'transit'])], order='id asc', limit=1)
            if location_id and not exist_product_quant:
                new_product_quant = self.env['stock.quant'].sudo().create({
                    'location_id': location_id.id,
                    'product_id': record.id,
                    'quantity': 0,
                    'inventory_quantity': 0,
                })
                new_product_quant.action_apply_inventory()

    @api.model
    def create(self, vals):
        res = super(FlemingsStockProductProduct, self).create(vals)
        # Create Stock Quant for Product if not exists
        if 'min_stock_quantity' in vals:
            res.create_flemings_product_quant()
        return res

    def write(self, vals):
        res = super(FlemingsStockProductProduct, self).write(vals)
        # Create Stock Quant for Product if not exists
        if 'min_stock_quantity' in vals:
            self.create_flemings_product_quant()
        return res

    def unlink(self):
        for record in self.filtered(lambda x: x.qty_available == 0):
            record.stock_move_ids.with_context(inventory_unlink=True).filtered(lambda x: x.is_inventory).unlink()
        return super(FlemingsStockProductProduct, self).unlink()


class FGStockMoves(models.Model):
    _inherit = 'stock.move'

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft_or_cancel(self):
        if any(move.state not in ('draft', 'cancel') for move in self) and not self._context.get('inventory_unlink', False):
            raise UserError(_('You can only delete draft or cancelled moves.'))


class FGStockMoveLines(models.Model):
    _inherit = 'stock.move.line'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_done_or_cancel(self):
        for ml in self:
            if ml.state in ('done', 'cancel') and not self._context.get('inventory_unlink', False):
                raise UserError(_('You can not delete product moves if the picking is done. You can only correct the done quantities.'))
