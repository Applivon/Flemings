# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

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
    _description = 'Stock'

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


class FlemingsStockProductTemplate(models.Model):
    _inherit = 'product.template'

    min_stock_quantity = fields.Float('Minimum Stock Level', default=0)

    @api.model
    def create(self, vals):
        res = super(FlemingsStockProductTemplate, self).create(vals)
        for record in res:
            # Update Variant Minimum Stock Level
            if 'min_stock_quantity' in vals:
                for variant in record.product_variant_ids:
                    variant.min_stock_quantity = record.min_stock_quantity

        return res

    def write(self, vals):
        res = super(FlemingsStockProductTemplate, self).write(vals)
        for record in self:
            # Update Variant Minimum Stock Level
            if 'min_stock_quantity' in vals:
                for variant in record.product_variant_ids:
                    variant.min_stock_quantity = record.min_stock_quantity

        return res


class FlemingsStockProductProduct(models.Model):
    _inherit = 'product.product'

    min_stock_quantity = fields.Float('Minimum Stock Level', default=0)
