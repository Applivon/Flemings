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

    def get_stock_low_products(self):
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
           WHERE quant.quantity < prod.min_stock_quantity AND prod.active = True %s """ % where)

        quant_ids = [i for j in self.env.cr.fetchall() for i in j]

        action = self.env['ir.actions.actions']._for_xml_id('flemings_base.fg_stock_low_action')
        action['domain'] = [('id', 'in', quant_ids)]
        return action


class FlemingsStockQuants(models.Model):
    _inherit = 'stock.quant'
    _description = 'Stock'

    min_stock_quantity = fields.Float(related='product_id.min_stock_quantity', string='Minimum Stock Level')


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
