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

import os
from odoo.addons.web.controllers.main import clean
from odoo.tools.float_utils import float_repr

IRAS_DIGITS = 2


class FlemingsProductAttribute(models.Model):
    _inherit = 'product.attribute'

    attribute_type = fields.Selection([('fabric', 'Fabric'), ('type', 'Type'), ('size', 'Size')], string='Attribute Type')

    @api.constrains('attribute_type')
    def check_attribute_type_exists(self):
        for record in self.filtered(lambda x: x.attribute_type):
            if self.sudo().search([('attribute_type', '=', record.attribute_type), ('id', '!=', record.id)]):
                raise UserError(_("This Attribute Type already assigned for another Attribute !"))


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

    def unlink(self):
        if self.env.user.has_group('flemings_base.fg_sales_group'):
            for record in self:
                if record.type and record.type != 'delivery':
                    raise UserError(_('You cannot delete this record !'))
        return super(FlemingsResPartner, self).unlink()

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super(FlemingsResPartner, self).get_view(view_id, view_type, **options)

        if self.env.user.fg_procurement_group:
            if view_type in ('tree', 'form', 'kanban'):
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//" + view_type + ""):
                    node.set('create', 'false')
                    node.set('delete', 'false')
                res['arch'] = etree.tostring(doc)

        # if self.env.user.fg_sales_group:
        #     if view_type in ('tree', 'form', 'kanban'):
        #         doc = etree.XML(res['arch'])
        #         for node in doc.xpath("//" + view_type + ""):
        #             node.set('create', 'false')
        #         res['arch'] = etree.tostring(doc)

        if (self._context.get('default_supplier_rank') and self._context.get('default_supplier_rank') == 1
                and (self.env.user.fg_sales_group or self.env.user.fg_mr_group)):
            if view_type in ('tree', 'form', 'kanban'):
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//" + view_type + ""):
                    node.set('create', 'false')
                res['arch'] = etree.tostring(doc)

        # if (self._context.get('default_supplier_rank') and self._context.get('default_supplier_rank') == 1
        #         and not (self.env.user.fg_su_group)):
        #     if view_type in ('tree', 'form', 'kanban'):
        #         doc = etree.XML(res['arch'])
        #         for node in doc.xpath("//" + view_type + ""):
        #             node.set('create', 'false')
        #             node.set('delete', 'false')
        #             if view_type == 'form' and not self.env.user.fg_procurement_group:
        #                 node.set('edit', 'false')
        #         res['arch'] = etree.tostring(doc)

        return res

    def _compute_can_edit_partner_address(self):
        for record in self:
            if self.env.user.fg_sales_group or self.env.user.fg_procurement_group:
                can_edit_partner_address = False
            elif self.type == 'contact' and record.parent_id:
                can_edit_partner_address = False
            else:
                can_edit_partner_address = True
            record.can_edit_partner_address = can_edit_partner_address

    def _compute_is_fg_user_group(self):
        for record in self:
            record.is_sales_user_group = True if self.env.user.fg_sales_group else False
            record.is_purchaser_user_group = True if self.env.user.fg_procurement_group else False

    can_edit_partner_address = fields.Boolean('Can Edit Person Address ?', compute='_compute_can_edit_partner_address')
    is_sales_user_group = fields.Boolean('Is Sales User ?', compute='_compute_is_fg_user_group')
    is_purchaser_user_group = fields.Boolean('Is Purchaser User ?', compute='_compute_is_fg_user_group')
    last_sale_date = fields.Date('Last Sale Date', copy=False)
    last_purchase_date = fields.Date('Last Purchase Date', copy=False)
    last_invoice_date = fields.Date('Last Invoice Date', copy=False)
    customer_price_book_line = fields.One2many('customer.price.book.details', 'partner_id', string='Customer Price Book')
    vendor_price_book_line = fields.One2many('vendor.price.book.details', 'partner_id', string='Vendor Price Book')
    fax = fields.Char('Fax')


class FlemingsResCompany(models.Model):
    _inherit = 'res.company'

    fax = fields.Char(related='partner_id.fax', string='Fax', readonly=False)
    sgs_img = fields.Binary('SGS Image')
    paynow_img = fields.Binary('Paynow Image')
    banner_report = fields.Binary('Logo', attachment=True)


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
        if self.order_id and self.order_id.generate_fg_sno:
            self.fg_sno = len(self.order_id.order_line.filtered(lambda x: not x.display_type))
            if self.display_type:
                self.fg_sno = 0

    fg_sno = fields.Integer('S.No', default=1)
    remarks = fields.Text('Remarks')

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

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super(FlemingsSalesOrder, self).get_view(view_id, view_type, **options)

        if (not self._context.get('search_default_my_quotation') and not self._context.get('search_default_my_quotation', False)
                and (self.env.user.fg_operations_group or self.env.user.fg_mr_group or self.env.user.fg_product_marketing_group)):
            if view_type in ('tree', 'form', 'kanban'):
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//" + view_type + ""):
                    node.set('create', 'false')
                    node.set('delete', 'false')
                    node.set('edit', 'false')
                res['arch'] = etree.tostring(doc)

        if (self._context.get('create', True)
                and self.env.user.fg_finance_with_report_group):
            if view_type in ('tree', 'form', 'kanban'):
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//" + view_type + ""):
                    node.set('delete', 'false')
                res['arch'] = etree.tostring(doc)

        return res

    @api.depends('picking_ids', 'invoice_ids')
    def _compute_so_delivery_invoice_names(self):
        for record in self:
            record.write({
                'computed_delivery_order_names': ' '.join([i.name for i in record.picking_ids]),
                'computed_customer_invoice_names': ' '.join([i.name for i in record.invoice_ids]),
            })

    computed_delivery_order_names = fields.Text(string='Delivery Order', store=False, readonly=True, compute_sudo='_compute_so_delivery_invoice_names')
    computed_customer_invoice_names = fields.Text(string='Customer Invoice', store=False, readonly=True, compute_sudo='_compute_so_delivery_invoice_names')

    delivery_order_names = fields.Text(related='computed_delivery_order_names', string='Delivery Order', store=True, readonly=True)
    customer_invoice_names = fields.Text(related='computed_customer_invoice_names', string='Customer Invoice', store=True, readonly=True)

    origin_so_no = fields.Char('Origin SO No.')
    generate_fg_sno = fields.Boolean('Generate S.No.', default=True, copy=False)
    manufacturing_order_ids = fields.Many2many('mrp.production', string='Manufacturing Order(s)')
    summary_remarks = fields.Text('Summary Remarks')

    @api.onchange('manufacturing_order_ids')
    def onchange_manufacturing_order_ids(self):
        self.order_line = False
        order_line = []
        for manufacturing_order_id in self.manufacturing_order_ids:
            fg_sno = 1
            order_line += [(0, 0, {
                'fg_sno': fg_sno,
                'product_id': manufacturing_order_id.product_id.id,
                'product_uom_qty': manufacturing_order_id.product_qty,
            })]
            fg_sno += 1

            # for move_line in manufacturing_order_id.move_raw_ids:
            #     order_line += [(0, 0, {
            #         'fg_sno': fg_sno,
            #         'product_id': move_line.product_id.id,
            #         'product_uom_qty': move_line.quantity_done,
            #     })]
            #     fg_sno += 1
        self.order_line = order_line

    @api.model
    def create(self, vals):
        res = super(FlemingsSalesOrder, self).create(vals)
        for record in res.filtered(lambda x: x.generate_fg_sno):
            asc_order_lines = record.order_line.filtered(lambda x: not x.display_type).sorted(key=lambda r: r.sequence)
            fg_sno = 1
            for asc_line in asc_order_lines:
                asc_line.fg_sno = fg_sno
                fg_sno += 1

        return res

    def write(self, vals):
        res = super(FlemingsSalesOrder, self).write(vals)
        for record in self.filtered(lambda x: x.generate_fg_sno):
            if ('generate_fg_sno' in vals and record.generate_fg_sno) or 'order_line' in vals:
                asc_order_lines = record.order_line.filtered(lambda x: not x.display_type).sorted(key=lambda r: r.sequence)
                fg_sno = 1
                for asc_line in asc_order_lines:
                    asc_line.fg_sno = fg_sno
                    fg_sno += 1

        return res

    @api.onchange('customer_po')
    def onchange_customer_po(self):
        if self.customer_po:
            exist_customer_po = self.env['account.move'].sudo().search([('customer_po', '=', self.customer_po)])
            if exist_customer_po:
                self.customer_po = False
                return {'warning': {
                    'title': _("Warning"),
                    'message': _("The Customer PO No. already exists in another invoice !")}}

    customer_po = fields.Char('Customer PO No.', copy=False)
    customer_service_id = fields.Many2one('res.users', string='Customer Service')
    delivery_mode_id = fields.Many2one('fg.delivery.carrier', string='Delivery Mode')
    fg_remarks = fields.Text('Remarks')

    def _prepare_invoice(self):
        res = super(FlemingsSalesOrder, self)._prepare_invoice()
        res.update({
            'sale_id': self.id,
            'delivery_mode_id': self.delivery_mode_id.id or False,
            'customer_po': self.customer_po,
            'fg_remarks': self.fg_remarks
        })
        return res

    def action_confirm(self):
        res = super(FlemingsSalesOrder, self).action_confirm()
        for order in self:
            order.update_customer_price_book()
            # Pickings Update
            for picking in order.picking_ids:
                picking.write({
                    'customer_po': order.customer_po,
                    'process_by_id': self.env.user.id,
                    'fg_remarks': order.fg_remarks,
                    'summary_remarks': order.summary_remarks,
                })

            # Update Order Line Remarks into DO Operations & Detailed Operations
            for picking in order.picking_ids.filtered(lambda x: x.state != 'cancel'):
                for move_id in picking.move_ids_without_package.filtered(lambda x: x.sale_line_id):
                    move_id.write({'remarks': move_id.sale_line_id.remarks})
                for move_line_id in picking.move_line_ids_without_package.filtered(lambda x: x.move_id.sale_line_id):
                    move_line_id.write({'remarks': move_line_id.move_id.sale_line_id.remarks})

        return res

    @api.depends('invoice_status', 'order_line', 'order_line.invoice_status', 'picking_ids', 'picking_ids.state', 'invoice_ids')
    def _compute_fg_invoice_status(self):
        for record in self:
            fg_invoice_status = 'no'
            if record.picking_ids.filtered(lambda x: x.state == 'done') and not record.invoice_ids:
                fg_invoice_status = 'to_invoice'
            elif record.invoice_ids and record.invoice_status != 'invoiced':
                fg_invoice_status = 'partial_invoice'

            record.write({
                'computed_fg_invoice_status': fg_invoice_status
            })

    computed_fg_invoice_status = fields.Selection([
        ('no', 'Nothing to Invoice'), ('to_invoice', 'To Invoice'), ('partial_invoice', 'Partially Invoiced')
    ], string='Invoice Status', compute_sudo='_compute_fg_invoice_status', store=False, readonly=True)
    fg_invoice_status = fields.Selection(
        related='computed_fg_invoice_status', string='Invoice Status', store=True, readonly=True)

    def update_customer_price_book(self):
        for record in self.filtered(lambda x: x.partner_id):
            for line in record.order_line:
                exist_price_book = self.env['customer.price.book.details'].search(
                    [('partner_id', '=', record.partner_id.parent_id.id or record.partner_id.id), ('product_id', '=', line.product_id.id)],
                    order='order_date desc', limit=1)
                if not exist_price_book:
                    self.env['customer.price.book.details'].create({
                        'partner_id': record.partner_id.parent_id.id or record.partner_id.id,
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
                            'sale_order_number': record.name,
                            'invoice_id': 0,
                            'invoice_number': False,
                            'product_sku': line.product_id.default_code,
                            'order_date': record.date_order,
                            'price_unit': line.price_unit
                        })

    can_user_edit_qty = fields.Boolean('Can User Edit SO Qty ?', compute_sudo='_compute_can_user_edit_qty')

    @api.depends('picking_ids', 'partner_id')
    def _compute_can_user_edit_qty(self):
        for record in self:
            if not record.picking_ids:
                record.can_user_edit_qty = True
            elif record.picking_ids and (
                    self.env.user.has_group('flemings_base.fg_su_group')
            ):
                record.can_user_edit_qty = True
            else:
                record.can_user_edit_qty = False


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
                    [('partner_id', '=', record.partner_id.parent_id.id or record.partner_id.id), ('product_id', '=', line.product_id.id)],
                    order='order_date desc', limit=1)
                if not exist_price_book:
                    self.env['vendor.price.book.details'].create({
                        'partner_id': record.partner_id.parent_id.id or record.partner_id.id,
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
                            'purchase_order_number': record.name,
                            'bill_id': 0,
                            'bill_number': False,
                            'product_sku': line.product_id.default_code,
                            'order_date': record.date_order,
                            'price_unit': line.price_unit
                        })


class FlemingsSalesAccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if self._context.get('default_move_type', False) and self._context.get('default_move_type') == 'entry':
            if not (self.env.user.has_group('flemings_base.fg_su_group')):
                args += [('journal_id', 'in', self.env.user.journal_ids.ids or [])]

        return super(FlemingsSalesAccountMove, self)._search(args, offset, limit, order, count=count, access_rights_uid=access_rights_uid)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if self._context.get('default_move_type', False) and self._context.get('default_move_type') == 'entry':
            if not (self.env.user.has_group('flemings_base.fg_su_group')):
                domain += [('journal_id', 'in', self.env.user.journal_ids.ids or [])]

        return super(FlemingsSalesAccountMove, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)

    @api.depends('amount_untaxed', 'amount_tax', 'amount_total', 'currency_id', 'invoice_line_ids.price_total')
    def _compute_sgd_equivalent_amount(self):
        for record in self:
            record.write({
                'computed_sgd_amount_untaxed': record.currency_id._convert(record.amount_untaxed, record.sgd_currency_id, record.company_id, record.invoice_date or record.create_date) if (record.invoice_date or record.create_date) else 0,
                'computed_sgd_amount_tax': record.currency_id._convert(record.amount_tax, record.sgd_currency_id, record.company_id, record.invoice_date or record.create_date) if (record.invoice_date or record.create_date) else 0,
                'computed_sgd_amount_total': record.currency_id._convert(record.amount_total, record.sgd_currency_id, record.company_id, record.invoice_date or record.create_date) if (record.invoice_date or record.create_date) else 0,
                'computed_sgd_exchange_rate': record.currency_id.with_context(date=record.invoice_date or record.create_date).inverse_rate or 1.0
            })

    @api.depends('invoice_line_ids', 'invoice_line_ids.picking_id')
    def _compute_invoice_delivery_invoice_names(self):
        for record in self:
            record.write({
                'computed_delivery_order_names': ', '.join([i.name for i in record.invoice_line_ids.mapped('picking_id')]),
            })

    computed_delivery_order_names = fields.Text(string='Delivery Order', store=False, readonly=True, compute='_compute_invoice_delivery_invoice_names')
    delivery_order_names = fields.Text(related='computed_delivery_order_names', string='Delivery Order', store=True, readonly=True)

    sgd_currency_id = fields.Many2one('res.currency', string='SGD Currency', default=lambda self: self.env['res.currency'].search([('name', '=', 'SGD')], limit=1))
    computed_sgd_amount_untaxed = fields.Float(string='SGD Untaxed Amount', store=False, readonly=True, compute='_compute_sgd_equivalent_amount')
    computed_sgd_amount_tax = fields.Float(string='SGD GST', store=False, readonly=True, compute='_compute_sgd_equivalent_amount')
    computed_sgd_amount_total = fields.Float(string='SGD Total', store=False, readonly=True, compute='_compute_sgd_equivalent_amount')
    computed_sgd_exchange_rate = fields.Float(string='SGD Exchange Rate', store=False, readonly=True, compute='_compute_sgd_equivalent_amount', digits=0)

    sgd_amount_untaxed = fields.Float(related='computed_sgd_amount_untaxed', string='SGD Untaxed Amount', store=True, readonly=True)
    sgd_amount_tax = fields.Float(related='computed_sgd_amount_tax', string='SGD GST', store=True, readonly=True)
    sgd_amount_total = fields.Float(related='computed_sgd_amount_total', string='SGD Total', store=True, readonly=True)
    sgd_exchange_rate = fields.Float(related='computed_sgd_exchange_rate', string='SGD Exchange Rate', store=True, readonly=True)

    sale_id = fields.Many2one('sale.order', string='Sales Order No.')
    delivery_mode_id = fields.Many2one('fg.delivery.carrier', string='Delivery Mode')
    customer_po = fields.Char('Customer PO No.', copy=False)
    fg_remarks = fields.Text('Remarks')

    @api.onchange('customer_po')
    def onchange_customer_po(self):
        if self.customer_po:
            exist_customer_po = self.sudo().search([('customer_po', '=', self.customer_po)])
            if exist_customer_po:
                self.customer_po = False
                return {'warning': {
                    'title': _("Warning"),
                    'message': _("The Customer PO No. already exists in another invoice !")}}

    def get_line_delivery_orders(self):
        return list(set(self.invoice_line_ids.mapped('picking_id')))

    @api.model
    def get_views(self, views, options=None):
        res = super(FlemingsSalesAccountMove, self).get_views(views, options)
        for view_type in ('list', 'form'):
            if res['views'].get(view_type, {}).get('toolbar'):
                credit_note_report_ids = self.env.ref('flemings_base.print_report_fg_credit_note').ids
                credit_note_report_ids += self.env.ref('flemings_base.account_move_print_credit_note_xlsx').ids

                if self._context and self._context.get('default_move_type') and self._context.get('default_move_type') == 'out_refund':
                    print = [rec for rec in res['views'][view_type]['toolbar']['print'] if rec.get('id', False) in credit_note_report_ids]
                else:
                    print = [rec for rec in res['views'][view_type]['toolbar']['print'] if rec.get('id', False) not in credit_note_report_ids]

                res['views'][view_type]['toolbar'] = {'print': print}
        return res

    location_return_id = fields.Many2one(
        'stock.location', string='Stock Return Location', domain=[('usage', '=', 'internal')], copy=False)
    location_source_id = fields.Many2one(
        'stock.location', string='Stock Source Location', domain=[('usage', '=', 'internal')], copy=False)
    picking_return_id = fields.Many2one('stock.picking', string='Picking Reference', copy=False)
    not_create_picking = fields.Boolean("Don\'t Create Picking", copy=False)

    @api.onchange('not_create_picking')
    def onchange_not_create_picking(self):
        self.location_return_id = self.location_source_id = False

    def action_post(self):
        res = super(FlemingsSalesAccountMove, self).action_post()
        # Update Invoice Price-book for Customer
        for invoice in self.filtered(lambda x: x.move_type == 'out_invoice'):
            # Update Unit Cost Price for Profit Report
            for invoice_line in invoice.invoice_line_ids:
                invoice_line.unit_cost_price = invoice_line.product_id.standard_price

            invoice.update_customer_price_book()

            # Update 'Last Sale & Invoice Date' for Customer
            last_date_vals = {
                'last_sale_date': datetime.now().date(),
                'last_invoice_date': datetime.now().date()
            }
            invoice.partner_id.sudo().write(last_date_vals)
            invoice.partner_id.parent_id.sudo().write(last_date_vals)

        # Update Vendor Bill Price-book for Vendor
        for invoice in self.filtered(lambda x: x.move_type == 'in_invoice'):
            invoice.update_vendor_price_book()

            # Update 'Last Purchase Date' for Vendor
            last_date_vals = {
                'last_purchase_date': datetime.now().date()
            }
            invoice.partner_id.sudo().write(last_date_vals)
            invoice.partner_id.parent_id.sudo().write(last_date_vals)

        # Create Internal Picking for Credit Note & Refunds
        for record in self.filtered(lambda x: (x.move_type == 'out_refund' and x.location_return_id) or
                                              (x.move_type == 'in_refund' and x.location_source_id)):
            is_credit = is_debit = False

            if record.move_type == 'out_refund':
                picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'incoming'), ('return_picking_type_id', '!=', False)], limit=1)
                location_id = record.partner_id.property_stock_supplier
                location_dest_id = record.location_return_id
                is_credit = True
            else:
                picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'outgoing'), ('return_picking_type_id', '!=', False)], limit=1)
                location_id = record.location_source_id
                location_dest_id = record.partner_id.property_stock_customer
                is_debit = True

            record.picking_return_id = record.flemings_create_picking(picking_type_id, location_id, location_dest_id, debit=is_debit, credit=is_credit)
            record.picking_return_id.button_validate()
        return res
    
    def flemings_create_picking(self, picking_type_id, location_id, location_dest_id, debit, credit):
        move_line_ids_without_package = []
        for move_line in self.invoice_line_ids:
            move_line_ids_without_package.append((0, 0, {
                'product_id': move_line.product_id.id,
                'product_uom_id': move_line.product_uom_id.id,
                'location_id': location_id.id,
                'location_dest_id': location_dest_id.id,
                'qty_done': move_line.quantity,
            }))

        picking_data = {
            'partner_id': self.partner_id.id if self.partner_id else False,
            'picking_type_id': picking_type_id.id,
            'location_id': location_id.id if location_id else False,
            'location_dest_id': location_dest_id.id if location_dest_id else False,
            'origin': self.name,
            'move_line_ids_without_package': move_line_ids_without_package,
        }
        if debit:
            picking_data.update({'from_debit_note': True})
        elif credit:
            picking_data.update({'from_credit_note': True})

        picking_context = self._context.copy()
        if picking_context and picking_context.get("default_move_type"):
            picking_context.pop("default_move_type")

        picking_id = self.env['stock.picking'].with_context(picking_context).create(picking_data)
        return picking_id

    def update_customer_price_book(self):
        for record in self.filtered(lambda x: x.partner_id):
            for line in record.invoice_line_ids:
                exist_price_book = self.env['customer.price.book.details'].search(
                    [('partner_id', '=', record.partner_id.parent_id.id or record.partner_id.id), ('product_id', '=', line.product_id.id)],
                    order='order_date desc', limit=1)

                sale_order = self.env['sale.order'].search([]).filtered(lambda x: x.invoice_ids in record)
                sale_order_id = sale_order[0].id if sale_order else False

                if not exist_price_book:
                    self.env['customer.price.book.details'].create({
                        'partner_id': record.partner_id.parent_id.id or record.partner_id.id,
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
                    [('partner_id', '=', record.partner_id.parent_id.id or record.partner_id.id), ('product_id', '=', line.product_id.id)],
                    order='order_date desc', limit=1)

                purchase_order = self.env['purchase.order'].search([]).filtered(lambda x: x.invoice_ids in record)
                purchase_order_id = purchase_order[0].id if purchase_order else False

                if not exist_price_book:
                    self.env['vendor.price.book.details'].create({
                        'partner_id': record.partner_id.parent_id.id or record.partner_id.id,
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


class FlemingsSalesAccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if self._context.get('journal_type', False) and self._context.get('journal_type') == 'general':
            if not (self.env.user.has_group('flemings_base.fg_su_group')):
                args += [('journal_id', 'in', self.env.user.journal_ids.ids or [])]

        return super(FlemingsSalesAccountMoveLines, self)._search(args, offset, limit, order, count=count, access_rights_uid=access_rights_uid)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if self._context.get('journal_type', False) and self._context.get('journal_type') == 'general':
            if not (self.env.user.has_group('flemings_base.fg_su_group')):
                domain += [('journal_id', 'in', self.env.user.journal_ids.ids or [])]

        return super(FlemingsSalesAccountMoveLines, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)

    picking_id = fields.Many2one('stock.picking', string='Delivery Order', copy=False)
    sale_id = fields.Many2one('sale.order', string='Sale Order', copy=False)
    unit_cost_price = fields.Float('Unit Cost Price', required=True, default=0.0)


class FlemingsProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super(FlemingsProductTemplate, self).get_view(view_id, view_type, **options)

        account_product_action_ids = self.env.ref('account.product_product_action_sellable').ids
        account_product_action_ids += self.env.ref('account.product_product_action_purchasable').ids
        
        if (((self._context.get('search_default_filter_to_sell') and self._context.get('search_default_filter_to_sell') == 1) or
                (self._context.get('search_default_filter_to_purchase') and self._context.get('search_default_filter_to_purchase') == 1)
                and self._context.get('action_id', False) not in account_product_action_ids)
                and (self.env.user.fg_sales_group or self.env.user.fg_mr_group)):
            if view_type in ('tree', 'form', 'kanban'):
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//" + view_type + ""):
                    node.set('create', 'false')
                    node.set('delete', 'false')
                    node.set('edit', 'false')
                res['arch'] = etree.tostring(doc)

        return res

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

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super(FlemingsProductProduct, self).get_view(view_id, view_type, **options)

        if (((self._context.get('search_default_filter_to_sell') and self._context.get('search_default_filter_to_sell') == 1) or
                (self._context.get('search_default_filter_to_purchase') and self._context.get('search_default_filter_to_purchase') == 1))
                and (self.env.user.fg_sales_group or self.env.user.fg_mr_group)):
            if view_type in ('tree', 'form', 'kanban'):
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//" + view_type + ""):
                    node.set('create', 'false')
                    node.set('delete', 'false')
                    node.set('edit', 'false')
                res['arch'] = etree.tostring(doc)

        return res

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

    customer_po = fields.Char('Customer PO No.', copy=False)
    process_by_id = fields.Many2one('res.users', string='Process By')
    fg_remarks = fields.Text('Remarks')
    summary_remarks = fields.Text('Summary Remarks')
    is_fully_invoiced = fields.Boolean('Fully Invoiced ?', default=False, copy=False)
    from_credit_note = fields.Boolean('From Credit Note?', default=False, copy=False)
    from_debit_note = fields.Boolean('From Debit Note?', default=False, copy=False)

    def button_validate(self):
        res = super(FlemingsStockPicking, self).button_validate()
        # Check if Delivery Order Product Quantities are Available
        for record in self.filtered(lambda x: x.picking_type_id.code == 'outgoing'):
            qty_unavailable_error_msg = 'Following SKUs do not have enough stock to deliver: \n'
            is_qty_unavailable = False

            unavailable_sno = 1
            for line_product_id in record.move_line_ids_without_package.mapped('product_id'):
                picking_qty = sum(record.move_line_ids_without_package.filtered(lambda x: x.product_id.id == line_product_id.id).mapped('qty_done'))

                if line_product_id.qty_available < 0:
                    qty_unavailable_error_msg += '\n' + str(unavailable_sno) + '. ' + str(line_product_id.display_name) + ' - ' + str(line_product_id.qty_available + picking_qty)

                    is_qty_unavailable = True
                    unavailable_sno += 1

            if is_qty_unavailable:
                raise UserError(_("%s") % qty_unavailable_error_msg)

        return res

    def action_picking_create_invoice(self):
        non_delivery_orders = list(set(self.filtered(lambda x: x.picking_type_id.code != 'outgoing')))
        if non_delivery_orders:
            raise UserError(_("Create Invoice is only allowed for 'Delivery Orders' !"))

        not_done_orders = list(set(self.filtered(lambda x: x.state != 'done')))
        if not_done_orders:
            raise UserError(_("Create Invoice is only allowed for 'Delivery Orders' which are 'Done' !"))

        partner_ids = list(set(self.mapped('partner_id')))
        if len(partner_ids) > 1:
            raise UserError(_('You cannot create invoice for Multiple Contacts, choose same Contact Delivery Orders !'))

        sale_ids = list(set(self.mapped('sale_id')))
        if len(sale_ids) > 1:
            raise UserError(_('You cannot create invoice for Multiple Sales Orders, choose same SO Delivery Orders !'))
        partner_id = partner_ids[0]

        invoice_vals, invoice_line_vals = {}, []
        for record in self.filtered(lambda x: x.sale_id and not x.is_fully_invoiced):
            for move_line in record.move_ids_without_package:
                invoice_line_vals.append((0, 0, {
                    'picking_id': record.id,
                    'sale_id': record.sale_id.id,
                    'sale_line_ids': [(6, 0, move_line.sale_line_id.ids or [])],
                    'product_id': move_line.product_id.id,
                    'name': move_line.product_id.get_product_multiline_description_sale(),
                    'quantity': move_line.quantity_done,
                    'product_uom_id': move_line.product_uom.id,
                }))
            record.is_fully_invoiced = True

        if invoice_line_vals:
            invoice_vals.update({
                'move_type': 'out_invoice',
                'partner_id': partner_id.id,
                'invoice_line_ids': invoice_line_vals,
            })
            new_invoice_id = self.env['account.move'].create(invoice_vals)
        return


class FlemingsStockRoute(models.Model):
    _inherit = 'stock.route'

    is_buy_external = fields.Boolean('Buy - External', default=False, copy=False)
    is_buy_internal = fields.Boolean('Buy - Internal', default=False, copy=False)
    is_access_restrict = fields.Boolean('Access Restrict ?', default=False, copy=False)

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if not self._context.get('user_routes_selection', False):
            is_buy_external = self.env.user.route_ids.filtered(lambda x: x.is_buy_external)
            is_buy_internal = self.env.user.route_ids.filtered(lambda x: x.is_buy_internal)
            if not is_buy_external:
                args += [('is_buy_external', '=', False)]
            if not is_buy_internal:
                args += [('is_buy_internal', '=', False)]

        return super(FlemingsStockRoute, self)._search(args, offset, limit, order, count=count, access_rights_uid=access_rights_uid)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if not self._context.get('user_routes_selection', False):
            is_buy_external = self.env.user.route_ids.filtered(lambda x: x.is_buy_external)
            is_buy_internal = self.env.user.route_ids.filtered(lambda x: x.is_buy_internal)
            if not is_buy_external:
                domain += [('is_buy_external', '=', False)]
            if not is_buy_internal:
                domain += [('is_buy_internal', '=', False)]

        return super(FlemingsStockRoute, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)


class FlemingMrpProduction(models.Model):
    _inherit = 'mrp.production'

    remarks = fields.Text('Remarks')
    summary_remarks = fields.Text('Summary Remarks')
    origin_so_no = fields.Char('Origin SO No.')
    work_order_no = fields.Char('Work Order No.')
    scheduled_production_date = fields.Date('Scheduled Production Date')

    def action_generate_mrp_work_order_numbers(self):
        non_confirmed_progress_orders = list(set(self.filtered(lambda x: x.state not in ('confirmed', 'progress'))))
        if non_confirmed_progress_orders:
            raise UserError(_("Only 'Confirmed & In Progress' Orders are applicable for Generating Work Order No. !"))

        already_processed_orders = list(set(self.filtered(lambda x: x.work_order_no)))
        if already_processed_orders:
            raise UserError(_("Work Order No. already generated for one or more selected records !"))

        next_sequence = self.env['ir.sequence'].next_by_code('mrp.production.work.order.no')
        self.env['mrp.production.work.order.no'].create({'work_order_no': next_sequence})
        for record in self:
            record.work_order_no = next_sequence
        return

    def action_release_mrp_work_order_numbers(self):
        non_processed_orders = list(set(self.filtered(lambda x: not x.work_order_no)))
        if non_processed_orders:
            raise UserError(_("Work Order No. is not generated to Release for one or more selected records !"))

        for record in self:
            record.work_order_no = False
        return

    def action_reassign_mrp_work_order_numbers(self):
        already_processed_orders = list(set(self.filtered(lambda x: x.work_order_no)))
        if already_processed_orders:
            raise UserError(_("Work Order No. already generated for one or more selected records !"))

        action = self.env['ir.actions.act_window']._for_xml_id('flemings_base.action_reassign_work_order_wizard')
        action['context'] = {'default_production_ids': [(6, 0, self.ids)]}
        return action

    @api.model
    def create(self, vals):
        res = super(FlemingMrpProduction, self).create(vals)
        for record in res:
            if not record.origin_so_no and self._context and self._context.get('origin_so_no', False):
                record.origin_so_no = self._context.get('origin_so_no')
            if self._context and self._context.get('so_origin_no', False):
                if not record.origin:
                    record.origin = self._context.get('so_origin_no')
                sale_id = self.env['sale.order'].sudo().search([('name', '=', self._context.get('so_origin_no'))], limit=1)
                if sale_id:
                    update_vals = {'summary_remarks': sale_id.summary_remarks}
                    sale_order_line_remarks = sale_id.order_line.filtered(lambda x: x.product_id.id == record.product_id.id and x.route_id.name == 'Manufacture').mapped('remarks')
                    if sale_order_line_remarks:
                        update_vals.update({'remarks': sale_order_line_remarks[0]})
                    record.write(update_vals)

        return res


class FlemingMrpProductionWorkOrder(models.Model):
    _name = 'mrp.production.work.order.no'
    _description = 'MO - Work Order No.'
    _rec_name = 'work_order_no'
    _order = 'create_date desc'

    work_order_no = fields.Char(string='Work Order No.', required=True)


class FlemingMOReassignWO(models.TransientModel):
    _name = 'mrp.production.reassign.work.order.no'
    _description = 'MO - Work Order No. - Reassign'
    _rec_name = 'work_order_id'

    work_order_id = fields.Many2one('mrp.production.work.order.no', string='Work Order No.')
    production_ids = fields.Many2many('mrp.production', string='Manufacturing Order(s)')

    def reassign_mo_work_order(self):
        for record in self:
            record.production_ids.write({'work_order_no': record.work_order_id.work_order_no})


class FlemingMrpWorkOrder(models.Model):
    _inherit = 'mrp.workorder'

    work_order_no = fields.Char(related='production_id.work_order_no', string='Work Order No.')


class FlemingMrpImageWorkOrder(models.Model):
    _name = 'mo.image.for.work.order'
    _description = 'MO - Image for Work Order'
    _rec_name = 'work_order_no'
    _order = 'create_date desc'

    work_order_no = fields.Char('Work Order No.', required=True, copy=False)
    customer_name = fields.Char('Customer Name', required=True)
    customer_ref = fields.Char('Customer Ref.')
    sale_order_no = fields.Char('Sale Order No.')
    summary_remarks = fields.Text('Summary Remarks')
    attachment_ids = fields.Many2many('ir.attachment', 'image_wo_attachment_rel', 'image_wo_id', 'attachment_id', string='Attachment')

    @api.constrains('work_order_no')
    def check_work_order_no_exists(self):
        for record in self:
            if record.work_order_no:
                if not self.env['mrp.production.work.order.no'].sudo().search([('work_order_no', '=', record.work_order_no)]):
                    raise UserError(_('Work Order No. not exists !'))

                if self.sudo().search([('work_order_no', '=', record.work_order_no), ('id', '!=', record.id)]):
                    raise UserError(_('Image for Work Order already exists for this Work Order No. !'))

    @api.constrains('attachment_ids')
    def check_valid_attachment(self):
        for record in self.filtered(lambda x: x.attachment_ids):
            offending_files = []
            for attachment in record.attachment_ids:
                if not self.check_is_allowed_extension(attachment.name):
                    msg = _(' - File extension not allowed \n\n Only "jpeg, jpg & png" files are allowed as Attachments !')
                    offending_files.append({
                        'filename': clean(attachment.name),
                        'error': msg
                    })

            if offending_files:
                raise UserError(_(" {0}{1}".format(offending_files[0]['filename'], offending_files[0]['error'])))

    def check_is_allowed_extension(self, filename):
        is_allowed = True
        ext = os.path.splitext(filename)[1][1:].lower().strip()

        whitelist = 'jpeg,jpg,png'
        if whitelist and ext not in [x.lower().strip() for x in whitelist.split(',')]:
            is_allowed = False

        return is_allowed


class FlemingAccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.depends('payment_type', 'partner_id')
    def _compute_payment_sale_ids(self):
        for record in self:
            sale_ids = []
            if record.partner_id and record.payment_type == 'inbound':
                # sale_ids = self.env['account.move'].sudo().search(
                #     [('partner_id', '=', record.partner_id.id), ('move_type', '=', 'out_invoice'), ('amount_residual', '>', 0)]
                # ).mapped('line_ids').mapped('sale_line_ids').mapped('order_id').ids
                sale_ids = self.env['sale.order'].sudo().search(
                    [('partner_id', '=', record.partner_id.id), ('state', 'in', ['sale', 'done']),
                     '|', ('invoice_ids', '=', False), ('invoice_ids.amount_residual', '>', 0)]
                ).ids or []
            record.sale_ids = [(6, 0, sale_ids or [])]

    sale_ids = fields.Many2many('sale.order', string='Sales Order(s)', compute='_compute_payment_sale_ids')
    sale_id = fields.Many2one('sale.order', string='Sales Order')


class FlemingStockMoveRemarks(models.Model):
    _inherit = 'stock.move'

    remarks = fields.Text('Remarks')


class FlemingStockMoveLineRemarks(models.Model):
    _inherit = 'stock.move.line'

    remarks = fields.Text('Remarks')

    def write(self, vals):
        res = super(FlemingStockMoveLineRemarks, self).write(vals)
        for record in self.filtered(lambda x: x.move_id and x.move_id.remarks and not x.remarks):
            record.write({'remarks': record.move_id.sale_line_id.remarks})
        return res


class FlemingsProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super(FlemingsProductPricelist, self).get_view(view_id, view_type, **options)

        if (self._context.get('default_base') and self._context.get('default_base') == 'list_price'
                and self.env.user.fg_sales_group):
            if view_type in ('tree', 'form', 'kanban'):
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//" + view_type + ""):
                    node.set('delete', 'false')
                res['arch'] = etree.tostring(doc)

        return res


class FGWebsiteVisitor(models.Model):
    _inherit = 'website.visitor'

    lead_ids = fields.Many2many('crm.lead', string='Leads')
    lead_count = fields.Integer('# Leads', compute="_compute_lead_count")


class FGAccountTransferModelLines(models.Model):
    _inherit = 'account.transfer.model.line'

    transfer_model_id = fields.Many2one('account.transfer.model', string="Transfer Model", required=True, ondelete='cascade')


class FGIrasAuditFile(models.Model):
    _inherit = 'account.report'

    def _l10n_sg_get_gldata(self, date_from, date_to):
        """
        Generate gldata for IRAS Audit File
        """
        gldata_lines = []
        total_debit = 0.0
        total_credit = 0.0
        transaction_count_total = 0
        glt_currency = 'SGD'

        company = self.env.company
        move_line_ids = self.env['account.move.line'].search([
            ('company_id', '=', company.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to)
            ])

        options = self._get_options(previous_options={
            'multi_company': {'id': company.id, 'name': company.name},
            'unfold_all': True,
            'unfolded_lines': [],
            'date': {
                'mode': 'range',
                'date_from': fields.Date.from_string(date_from),
                'date_to': fields.Date.from_string(date_from)
            }
        })
        general_ledger_report = self.env.ref('account_reports.general_ledger_report')
        handler = self.env['account.general.ledger.report.handler']
        accounts_results = handler._query_values(general_ledger_report, options)
        # accounts_results = self._general_ledger_query_values(options)
        all_accounts = self.env['account.account'].search([('company_id', '=', company.id)])

        for account in all_accounts:
            initial_bal = dict(accounts_results).get(account.id, {'initial_balance': {'balance': 0, 'amount_currency': 0, 'debit': 0, 'credit': 0}})['initial_balance']
            gldata_lines.append({
                'TransactionDate': date_from,
                'AccountID': account.code,
                'AccountName': account.name,
                'TransactionDescription': 'OPENING BALANCE',
                'Name': False,
                'TransactionID': False,
                'SourceDocumentID': False,
                'SourceType': False,
                'Debit': float_repr(initial_bal['debit'], IRAS_DIGITS),
                'Credit': float_repr(initial_bal['credit'], IRAS_DIGITS),
                'Balance': float_repr(initial_bal['balance'], IRAS_DIGITS)
            })
            balance = initial_bal['balance']
            for move_line_id in move_line_ids:
                if move_line_id.account_id.code == account.code:
                    balance = company.currency_id.round(balance + move_line_id.debit - move_line_id.credit)
                    total_credit += move_line_id.credit
                    total_debit += move_line_id.debit
                    transaction_count_total += 1
                    account_type_dict = dict(self.env['account.account']._fields['account_type']._description_selection(self.env))
                    gldata_lines.append({
                        'TransactionDate': fields.Date.to_string(move_line_id.date),
                        'AccountID': move_line_id.account_id.code,
                        'AccountName': move_line_id.account_id.name,
                        'TransactionDescription': move_line_id.name,
                        'Name': move_line_id.partner_id.name if move_line_id.partner_id else False,
                        'TransactionID': move_line_id.move_id.name,
                        'SourceDocumentID': move_line_id.move_id.invoice_origin if move_line_id.move_id else False,
                        'SourceType': account_type_dict[move_line_id.account_id.account_type][:20],
                        'Debit': float_repr(move_line_id.debit, IRAS_DIGITS),
                        'Credit': float_repr(move_line_id.credit, IRAS_DIGITS),
                        'Balance': float_repr(balance, IRAS_DIGITS)
                    })
        return {
            'lines': gldata_lines,
            'TotalDebit': float_repr(total_debit, IRAS_DIGITS),
            'TotalCredit': float_repr(total_credit, IRAS_DIGITS),
            'TransactionCountTotal': str(transaction_count_total),
            'GLTCurrency': glt_currency
        }
