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


class FlemingsItemCategory(models.Model):
    _name = 'fg.item.category'
    _description = 'Item Category'

    name = fields.Char('Item Category')
    user_ids = fields.Many2many('res.users', 'res_users_item_category_rel', 'item_category_id', 'user_id', string='Users')


class FlemingsDeliveryMode(models.Model):
    _name = 'fg.delivery.carrier'
    _description = 'Delivery Mode'

    name = fields.Char('Delivery Mode')


class FlemingsResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super(FlemingsResPartner, self).get_view(view_id, view_type, **options)

        if (self._context.get('default_supplier_rank') and self._context.get('default_supplier_rank') == 1
                and not (self.env.user.fg_finance_group or self.env.user.fg_admin_group)):
            if view_type == 'tree':
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//tree"):
                    node.set('create', 'false')
                    node.set('delete', 'false')
                res['arch'] = etree.tostring(doc)

            if view_type == 'form':
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//form"):
                    node.set('create', 'false')
                    node.set('edit', 'false')
                    node.set('delete', 'false')
                res['arch'] = etree.tostring(doc)

            if view_type == 'kanban':
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//kanban"):
                    node.set('create', 'false')
                    node.set('delete', 'false')
                res['arch'] = etree.tostring(doc)
        return res

    def _compute_is_sales_user_group(self):
        for record in self:
            record.is_sales_user_group = True if self.env.user.fg_sales_group else False

    is_sales_user_group = fields.Boolean('Is Sales User ?', compute='_compute_is_sales_user_group')
    last_sale_date = fields.Date('Last Sale Date', copy=False)
    last_purchase_date = fields.Date('Last Purchase Date', copy=False)
    last_invoice_date = fields.Date('Last Invoice Date', copy=False)
    customer_price_book_line = fields.One2many('customer.price.book.details', 'partner_id', string='Customer Price Book')
    vendor_price_book_line = fields.One2many('vendor.price.book.details', 'partner_id', string='Vendor Price Book')
    fax = fields.Char('Fax')


class FlemingsResCompany(models.Model):
    _inherit = 'res.company'

    fax = fields.Char(related='partner_id.fax', string='Fax', readonly=False)


class FlemingsCustomerPriceBook(models.Model):
    _name = 'customer.price.book.details'
    _description = 'Customer Price Book'
    _order = 'order_date desc'

    partner_id = fields.Many2one('res.partner', string='Partner')
    product_sku = fields.Char('SKU')
    product_id = fields.Many2one('product.product', string='Product')
    order_date = fields.Date('Order Date')
    price_unit = fields.Float('Unit Price')

    sale_order_id = fields.Integer('Sales Order ID')
    sale_order_number = fields.Char('Sales Order')
    invoice_id = fields.Integer('Invoice ID')
    invoice_number = fields.Char('Invoice')


class FlemingsVendorPriceBook(models.Model):
    _name = 'vendor.price.book.details'
    _description = 'Vendor Price Book'
    _order = 'order_date desc'

    partner_id = fields.Many2one('res.partner', string='Partner')
    product_sku = fields.Char('SKU')
    product_id = fields.Many2one('product.product', string='Product')
    order_date = fields.Date('Order Date')
    price_unit = fields.Float('Unit Price')

    purchase_order_id = fields.Integer('Purchase Order ID')
    purchase_order_number = fields.Char('Purchase Order')
    bill_id = fields.Char('Bill ID')
    bill_number = fields.Char('Bill No.')


class FlemingsSalesOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('order_id', 'sequence')
    def onchange_order_id_fg_sno(self):
        self.fg_sno = len(self.order_id.order_line)

    fg_sno = fields.Integer('S.No', default=1)

    def _get_display_price(self):
        """Compute the displayed unit price for a given line.

        Overridden in custom flows:
        * where the price is not specified by the pricelist
        * where the discount is not specified by the pricelist

        Note: self.ensure_one()
        """
        self.ensure_one()

        # Customer Product Price-Book
        pricebook_price_line = self.env['customer.price.book.details'].search([
            ('partner_id', '=', self.order_id.partner_id.id), ('product_id', '=', self.product_id.id)
        ], order='order_date desc', limit=1)
        if pricebook_price_line:
            return pricebook_price_line.price_unit or 0

        pricelist_price = self._get_pricelist_price()

        if self.order_id.pricelist_id.discount_policy == 'with_discount':
            return pricelist_price

        if not self.pricelist_item_id:
            # No pricelist rule found => no discount from pricelist
            return pricelist_price

        base_price = self._get_pricelist_price_before_discount()

        # negative discounts (= surcharge) are included in the display price
        return max(base_price, pricelist_price)


class FlemingsSalesOrder(models.Model):
    _inherit = 'sale.order'

    fg_purchase_order_no = fields.Char('Purchase Order No.')
    customer_service_id = fields.Many2one('res.users', string='Customer Service')
    delivery_mode_id = fields.Many2one('fg.delivery.carrier', string='Delivery Mode')
    fg_remarks = fields.Text('Remarks')

    def action_confirm(self):
        res = super(FlemingsSalesOrder, self).action_confirm()
        for order in self:
            order.update_customer_price_book()
            # Pickings Update
            for picking in order.picking_ids:
                picking.write({
                    'fg_purchase_order_no': order.fg_purchase_order_no,
                    'fg_remarks': order.fg_remarks,
                })
        return res

    def update_customer_price_book(self):
        for record in self.filtered(lambda x: x.partner_id):
            for line in record.order_line:
                exist_price_book = self.env['customer.price.book.details'].search(
                    [('partner_id', '=', record.partner_id.id), ('product_id', '=', line.product_id.id)],
                    order='order_date desc', limit=1)
                if not exist_price_book:
                    self.env['customer.price.book.details'].create({
                        'partner_id': record.partner_id.id,
                        'product_id': line.product_id.id,
                        'product_sku': line.product_id.default_code,
                        'sale_order_id': record.id,
                        'sale_order_number': record.name,
                        'invoice_id': 0,
                        'invoice_number': False,
                        'order_date': record.date_order,
                        'price_unit': line.price_unit
                    })
                else:
                    if exist_price_book.price_unit != line.price_unit:
                        exist_price_book.write({
                            'sale_order_id': record.id,
                            'sale_order_number': record.nme,
                            'invoice_id': 0,
                            'invoice_number': False,
                            'product_sku': line.product_id.default_code,
                            'order_date': record.date_order,
                            'price_unit': line.price_unit
                        })


class FlemingsPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        res = super(FlemingsPurchaseOrder, self).button_confirm()
        for order in self:
            order.update_vendor_price_book()
        return res

    def update_vendor_price_book(self):
        for record in self.filtered(lambda x: x.partner_id):
            for line in record.order_line:
                exist_price_book = self.env['vendor.price.book.details'].search(
                    [('partner_id', '=', record.partner_id.id), ('product_id', '=', line.product_id.id)],
                    order='order_date desc', limit=1)
                if not exist_price_book:
                    self.env['vendor.price.book.details'].create({
                        'partner_id': record.partner_id.id,
                        'product_id': line.product_id.id,
                        'product_sku': line.product_id.default_code,
                        'purchase_order_id': record.id,
                        'purchase_order_number': record.name,
                        'bill_id': 0,
                        'bill_number': False,
                        'order_date': record.date_order,
                        'price_unit': line.price_unit
                    })
                else:
                    if exist_price_book.price_unit != line.price_unit:
                        exist_price_book.write({
                            'purchase_order_id': record.id,
                            'purchase_order_number': record.nme,
                            'bill_id': 0,
                            'bill_number': False,
                            'product_sku': line.product_id.default_code,
                            'order_date': record.date_order,
                            'price_unit': line.price_unit
                        })


class FlemingsSalesAccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super(FlemingsSalesAccountMove, self).action_post()
        # Update Invoice Price-book for Customer
        for invoice in self.filtered(lambda x: x.move_type == 'out_invoice'):
            invoice.update_customer_price_book()

            # Update 'Last Sale & Invoice Date' for Customer
            invoice.partner_id.sudo().write({
                'last_sale_date': datetime.now().date(),
                'last_invoice_date': datetime.now().date()
            })

        # Update Vendor Bill Price-book for Vendor
        for invoice in self.filtered(lambda x: x.move_type == 'in_invoice'):
            invoice.update_vendor_price_book()

            # Update 'Last Purchase Date' for Vendor
            invoice.partner_id.sudo().write({
                'last_purchase_date': datetime.now().date()
            })
        return res

    def update_customer_price_book(self):
        for record in self.filtered(lambda x: x.partner_id):
            for line in record.invoice_line_ids:
                exist_price_book = self.env['customer.price.book.details'].search(
                    [('partner_id', '=', record.partner_id.id), ('product_id', '=', line.product_id.id)],
                    order='order_date desc', limit=1)

                sale_order = self.env['sale.order'].search([]).filtered(lambda x: x.invoice_ids in record)
                sale_order_id = sale_order[0].id if sale_order else False

                if not exist_price_book:
                    self.env['customer.price.book.details'].create({
                        'partner_id': record.partner_id.id,
                        'product_id': line.product_id.id,
                        'product_sku': line.product_id.default_code,
                        'sale_order_id': sale_order[0].id if sale_order else False,
                        'sale_order_number': sale_order[0].name if sale_order else False,
                        'invoice_id': record.id,
                        'invoice_number': record.name,
                        'order_date': record.invoice_date,
                        'price_unit': line.price_unit
                    })
                else:
                    if (exist_price_book.price_unit != line.price_unit) or (sale_order_id and exist_price_book.sale_order_id == sale_order_id):
                        exist_price_book.write({
                            'sale_order_id': sale_order[0].id if sale_order else False,
                            'sale_order_number': sale_order[0].name if sale_order else False,
                            'invoice_id': record.id,
                            'invoice_number': record.name,
                            'product_sku': line.product_id.default_code,
                            'order_date': record.invoice_date,
                            'price_unit': line.price_unit
                        })

    def update_vendor_price_book(self):
        for record in self.filtered(lambda x: x.partner_id):
            for line in record.invoice_line_ids:
                exist_price_book = self.env['vendor.price.book.details'].search(
                    [('partner_id', '=', record.partner_id.id), ('product_id', '=', line.product_id.id)],
                    order='order_date desc', limit=1)

                purchase_order = self.env['purchase.order'].search([]).filtered(lambda x: x.invoice_ids in record)
                purchase_order_id = purchase_order[0].id if purchase_order else False

                if not exist_price_book:
                    self.env['vendor.price.book.details'].create({
                        'partner_id': record.partner_id.id,
                        'product_id': line.product_id.id,
                        'product_sku': line.product_id.default_code,
                        'purchase_order_id': purchase_order[0].id if purchase_order else False,
                        'purchase_order_number': purchase_order[0].name if purchase_order else False,
                        'bill_id': record.id,
                        'bill_number': record.name,
                        'order_date': record.invoice_date,
                        'price_unit': line.price_unit
                    })
                else:
                    if (exist_price_book.price_unit != line.price_unit) or (purchase_order_id and exist_price_book.purchase_order_id == purchase_order_id):
                        exist_price_book.write({
                            'purchase_order_id': purchase_order[0].id if purchase_order else False,
                            'purchase_order_number': purchase_order[0].name if purchase_order else False,
                            'bill_id': record.id,
                            'bill_number': record.name,
                            'product_sku': line.product_id.default_code,
                            'order_date': record.invoice_date,
                            'price_unit': line.price_unit
                        })


class FlemingsProductTemplate(models.Model):
    _inherit = 'product.template'

    item_category_id = fields.Many2one('fg.item.category', string='Item Category')

    def _compute_template_fg_available_stock(self):
        for record in self:
            product_domain_loc = self.env['product.product']._get_domain_locations()[0]
            product_stock_quants = self.env['stock.quant'].sudo().search(product_domain_loc + [('product_id', 'in', record.product_variant_ids.ids)])

            fg_available_stock = ''
            seq = 1
            for quant_location in list(set(product_stock_quants.mapped('location_id'))):
                if seq != 1:
                    fg_available_stock += '\n'
                seq += 1
                quant_quantity = sum(self.env['stock.quant'].sudo().search([('id', 'in', product_stock_quants.ids), ('location_id', '=', quant_location.id)]).mapped('available_quantity')) or 0
                fg_available_stock += str(quant_location.display_name) + ' : ' + str('{:.2f}'.format(quant_quantity))

            record.fg_available_stock = fg_available_stock

    fg_available_stock = fields.Text('Available Stock', compute='_compute_template_fg_available_stock')


class FlemingsProductProduct(models.Model):
    _inherit = 'product.product'

    def get_product_multiline_description_sale(self):
        """ Compute a multiline description of this product, in the context of sales
                (do not use for purchases or other display reasons that don't intend to use "description_sale").
            It will often be used as the default description of a sale order line referencing this product.
        """
        # name = self.display_name
        variant = self.product_template_attribute_value_ids._get_combination_name()
        name = variant and "%s (%s)" % (self.name, variant) or self.name

        if self.description_sale:
            name += '\n' + self.description_sale

        return name

    def _compute_variant_fg_available_stock(self):
        for record in self:
            product_domain_loc = self.env['product.product']._get_domain_locations()[0]
            product_stock_quants = self.env['stock.quant'].sudo().search(product_domain_loc + [('product_id', '=', record.id)])

            fg_available_stock = ''
            seq = 1
            for quant in product_stock_quants:
                if seq != 1:
                    fg_available_stock += '\n'
                seq += 1
                fg_available_stock += str(quant.location_id.display_name) + ' : ' + str('{:.2f}'.format(quant.available_quantity))

            record.fg_available_stock = fg_available_stock

    @api.depends('name', 'product_template_attribute_value_ids')
    def _compute_product_variant_name(self):
        for record in self:
            variant = record.product_template_attribute_value_ids._get_combination_name()
            variant_name = variant and "%s (%s)" % (record.name, variant) or record.name
            record.write({'computed_variant_name': variant_name})

    computed_variant_name = fields.Char(
        'Product Variant Name', store=False, readonly=True, compute='_compute_product_variant_name')
    variant_name = fields.Char(
        related='computed_variant_name', string='Variant Name', store=True, readonly=True)
    fg_available_stock = fields.Text('Available Stock', compute='_compute_variant_fg_available_stock')


class FlemingsStockPicking(models.Model):
    _inherit = 'stock.picking'

    fg_purchase_order_no = fields.Char('Purchase Order No.')
    fg_remarks = fields.Text('Remarks')

    def button_validate(self):
        res = super(FlemingsStockPicking, self).button_validate()
        # Check if Delivery Order Product Quantities are Available
        for record in self.filtered(lambda x: x.picking_type_id.code == 'outgoing'):
            qty_unavailable_error_msg = 'Following SKUs do not have enough stock to deliver: \n'
            is_qty_unavailable = False

            unavailable_sno = 1
            for line_product_id in record.move_line_ids_without_package.mapped('product_id'):
                picking_qty = sum(record.move_line_ids_without_package.filtered(lambda x: x.product_id.id == line_product_id.id).mapped('qty_done'))

                if picking_qty > line_product_id.qty_available:
                    qty_unavailable_error_msg += '\n' + str(unavailable_sno) + '. ' + str(line_product_id.display_name) + ' - ' + str(line_product_id.qty_available)

                    is_qty_unavailable = True
                    unavailable_sno += 1

            if is_qty_unavailable:
                raise UserError(_("%s") % qty_unavailable_error_msg)

        return res
