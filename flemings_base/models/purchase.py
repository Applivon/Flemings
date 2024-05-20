# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError, ValidationError


class FGResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if self.env.context.get('pre_rfq_company_id', False):
            user = self.env.user
            company_partners = self.env['res.company'].sudo().search([]).mapped('partner_id')
            is_buy_internal = user.route_ids.filtered(lambda x: x.is_buy_internal)
            is_buy_external = user.route_ids.filtered(lambda x: x.is_buy_external)

            if is_buy_internal and not is_buy_external:
                args += [('id', 'in', list(set(company_partners.ids)) or []), ('id', '!=', self.env.context.get('pre_rfq_company_id'))]
            elif is_buy_external and not is_buy_internal:
                args += [('id', 'not in', list(set(company_partners.ids)) or [])]
            elif is_buy_external and is_buy_internal:
                args += []
            else:
                args += [('id', '=', 0)]

        return super(FGResPartner, self)._search(args, offset, limit, order, count=count, access_rights_uid=access_rights_uid)


class FlemingsPreRFQSalesOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super(FlemingsPreRFQSalesOrder, self).action_confirm()
        for order in self:
            # Pre-RFQ Creation
            pre_rfq_lines = order.order_line.filtered(lambda x: x.route_id.is_buy_external or x.route_id.is_buy_internal)
            order_line = []
            for line_id in pre_rfq_lines:
                order_line += [(0, 0, {
                    'route_id': line_id.route_id.id,
                    'product_id': line_id.product_id.id,
                    'name': line_id.name,
                    'product_qty': line_id.product_uom_qty,
                    'product_uom': line_id.product_uom.id,
                    'price_unit': 0,
                    'taxes_id': [(6, 0, line_id.tax_id.ids or [])],
                })]
            if order_line:
                self.env['pre.purchase.order'].create({
                    'sale_id': order.id,
                    'company_id': order.company_id.id,
                    'order_line': order_line,
                })

            # Manufacturing Order Creation
            manufacturing_lines = order.order_line.filtered(lambda x: x.route_id.name == 'Manufacture')
            for line_id in manufacturing_lines:
                self.env['mrp.production'].create({
                    'product_id': line_id.product_id.id,
                    'product_qty': line_id.product_uom_qty,
                    'product_uom_id': line_id.product_uom.id,
                    'company_id': order.company_id.id,
                })
        return res


class FlemingsPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    pre_rfq_id = fields.Many2one('pre.purchase.order', string='Pre-RFQ')

    def _prepare_sale_order_data(self, name, partner, company, direct_delivery_address):
        """ Update sale order value."""
        sale_order_data = super(FlemingsPurchaseOrder, self)._prepare_sale_order_data(name, partner, company, direct_delivery_address)
        if sale_order_data and self and self.pre_rfq_id and self.pre_rfq_id.sale_id:
            sale_order_data.update({
                'origin_so_no': self.pre_rfq_id.sale_id.name,
            })
        return sale_order_data

    @api.model
    def _prepare_sale_order_line_data(self, line, company):
        """ Update sale order line value."""
        sale_order_line_data = super(FlemingsPurchaseOrder, self)._prepare_sale_order_line_data(line, company)
        if sale_order_line_data and self and self.pre_rfq_id and self.pre_rfq_id.sale_id:
            sale_order_line_data.update({
                'route_id': self.env['stock.route'].sudo().search([('name', '=', 'Manufacture')], limit=1).id or False,
            })
        return sale_order_line_data


class FlemingPrePurchaseOrder(models.Model):
    _name = 'pre.purchase.order'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Pre-RFQ'
    _order = 'create_date desc'
    _rec_name = 'sale_id'

    @api.model
    def create(self, vals):
        res = super(FlemingPrePurchaseOrder, self).create(vals)
        for record in res:
            record.partner_ids = [(6, 0, record.order_line.mapped('partner_id').ids or [])]

        return res

    def write(self, vals):
        res = super(FlemingPrePurchaseOrder, self).write(vals)
        for record in self:
            if 'order_line' in vals:
                record.partner_ids = [(6, 0, record.order_line.mapped('partner_id').ids or [])]

        return res

    partner_ids = fields.Many2many('res.partner', string='Vendors')

    create_date = fields.Datetime('Date & Time')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company.id)
    sale_id = fields.Many2one('sale.order', string='Sale Order')
    order_line = fields.One2many('pre.purchase.order.line', 'order_id', string='Order Lines')
    notes = fields.Html('Terms and Conditions')

    purchase_ids = fields.One2many('purchase.order', 'pre_rfq_id', string='Purchase(s)')
    purchase_count = fields.Integer('Purchase Count', compute='_compute_purchase_count')

    state = fields.Selection([('draft', 'RFQ'), ('po_created', 'PO Created'), ('cancel', 'Cancelled')], string='Status', readonly=True, index=True, copy=False, default='draft', tracking=True)

    @api.depends('purchase_ids')
    def _compute_purchase_count(self):
        for record in self:
            record.purchase_count = len(record.purchase_ids) or 0

    def action_view_pre_rfq_purchases(self):
        result = self.env['ir.actions.act_window']._for_xml_id('purchase.purchase_form_action')
        # choose the view_mode accordingly
        purchases = self.purchase_ids
        if len(purchases) > 1:
            result['domain'] = [('id', 'in', purchases.ids)]
        elif len(purchases) == 1:
            res = self.env.ref('purchase.purchase_order_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + [(state, view) for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = purchases.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def button_create_po(self):
        for record in self:
            if not record.order_line:
                raise UserError(_('Please update Product Details !'))

            if record.order_line.filtered(lambda x: not x.partner_id):
                raise UserError(_('Please update Vendor in Product Details !'))

            vendors_list = list(set(record.order_line.filtered(lambda x: x.partner_id).mapped('partner_id')))
            for partner_id in vendors_list:
                to_create_po_lines = record.order_line.filtered(lambda x: x.partner_id and x.partner_id == partner_id)
                order_line = []
                currency_id = False
                for line_id in to_create_po_lines:
                    order_line += [(0, 0, {
                        'product_id': line_id.product_id.id,
                        'name': line_id.name,
                        'product_qty': line_id.product_qty,
                        'product_uom': line_id.product_uom.id,
                        'price_unit': line_id.price_unit,
                        'taxes_id': [(6, 0, line_id.taxes_id.ids or [])],
                    })]
                    currency_id = line_id.currency_id
                if order_line:
                    self.env['purchase.order'].create({
                        'pre_rfq_id': record.id,
                        'partner_id': partner_id.id,
                        'company_id': record.company_id.id,
                        'currency_id': currency_id.id,
                        'order_line': order_line,
                    })
            record.state = 'po_created'

    def button_cancel(self):
        for record in self:
            record.purchase_ids.button_cancel()
            record.state = 'cancel'


class FlemingPrePurchaseOrderLines(models.Model):
    _name = 'pre.purchase.order.line'
    _description = 'Pre-RFQ Lines'

    order_id = fields.Many2one('pre.purchase.order', string='Pre-RFQ', index=True, required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='order_id.company_id', string='Company', store=True, readonly=True)

    partner_id = fields.Many2one('res.partner', string='Vendor')
    product_id = fields.Many2one('product.product', string='Product')
    route_id = fields.Many2one('stock.route', string='Route')
    name = fields.Text(string='Description', required=True)

    product_qty = fields.Float(string='Quantity')
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', domain="[('category_id', '=', product_uom_category_id)]")
    price_unit = fields.Float(string='Unit Price', required=True, digits='Product Price')
    taxes_id = fields.Many2many('account.tax', string='Taxes', domain=['|', ('active', '=', False), ('active', '=', True)])

    currency_id = fields.Many2one('res.currency', store=True, string='Currency', required=True, default=lambda self: self.env.company.currency_id.id)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        self.currency_id = self.partner_id.property_product_pricelist.currency_id.id or False

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']

            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })

    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.partner_id,
            currency=self.currency_id,
            product=self.product_id,
            taxes=self.taxes_id,
            price_unit=self.price_unit,
            quantity=self.product_qty,
            price_subtotal=self.price_subtotal,
        )
