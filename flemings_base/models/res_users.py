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


class FlemingsResUsers(models.Model):
    _inherit = 'res.users'

    @api.onchange('fg_sales_group')
    def onchange_fg_sales_group(self):
        if self.fg_sales_group:
            self.fg_procurement_group = self.fg_inventory_group = self.fg_finance_with_report_group = self.fg_finance_wo_report_group = self.fg_operations_group = self.fg_mr_group = self.fg_product_marketing_group = self.fg_su_wo_account_group = self.fg_su_with_hr_group = self.fg_su_group = False

    @api.onchange('fg_procurement_group')
    def onchange_fg_procurement_group(self):
        if self.fg_procurement_group:
            self.fg_sales_group = self.fg_inventory_group = self.fg_finance_with_report_group = self.fg_finance_wo_report_group = self.fg_operations_group = self.fg_mr_group = self.fg_product_marketing_group = self.fg_su_wo_account_group = self.fg_su_with_hr_group = self.fg_su_group = False

    @api.onchange('fg_inventory_group')
    def onchange_fg_inventory_group(self):
        if self.fg_inventory_group:
            self.fg_sales_group = self.fg_procurement_group = self.fg_finance_with_report_group = self.fg_finance_wo_report_group = self.fg_operations_group = self.fg_mr_group = self.fg_product_marketing_group = self.fg_su_wo_account_group = self.fg_su_with_hr_group = self.fg_su_group = False

    @api.onchange('fg_finance_with_report_group')
    def onchange_fg_finance_with_report_group(self):
        if self.fg_finance_with_report_group:
            self.fg_sales_group = self.fg_procurement_group = self.fg_inventory_group = self.fg_finance_wo_report_group = self.fg_operations_group = self.fg_mr_group = self.fg_product_marketing_group = self.fg_su_wo_account_group = self.fg_su_with_hr_group = self.fg_su_group = False

    @api.onchange('fg_finance_wo_report_group')
    def onchange_fg_finance_wo_report_group(self):
        if self.fg_finance_wo_report_group:
            self.fg_sales_group = self.fg_procurement_group = self.fg_inventory_group = self.fg_finance_with_report_group = self.fg_operations_group = self.fg_mr_group = self.fg_product_marketing_group = self.fg_su_wo_account_group = self.fg_su_with_hr_group = self.fg_su_group = False

    @api.onchange('fg_operations_group')
    def onchange_fg_operations_group(self):
        if self.fg_operations_group:
            self.fg_sales_group = self.fg_procurement_group = self.fg_inventory_group = self.fg_finance_with_report_group = self.fg_finance_wo_report_group = self.fg_mr_group = self.fg_product_marketing_group = self.fg_su_wo_account_group = self.fg_su_with_hr_group = self.fg_su_group = False

    @api.onchange('fg_mr_group')
    def onchange_fg_mr_group(self):
        if self.fg_mr_group:
            self.fg_sales_group = self.fg_procurement_group = self.fg_inventory_group = self.fg_finance_with_report_group = self.fg_finance_wo_report_group = self.fg_operations_group = self.fg_product_marketing_group = self.fg_su_wo_account_group = self.fg_su_with_hr_group = self.fg_su_group = False

    @api.onchange('fg_product_marketing_group')
    def onchange_fg_product_marketing_group(self):
        if self.fg_product_marketing_group:
            self.fg_sales_group = self.fg_procurement_group = self.fg_inventory_group = self.fg_finance_with_report_group = self.fg_finance_wo_report_group = self.fg_operations_group = self.fg_mr_group = self.fg_su_wo_account_group = self.fg_su_with_hr_group = self.fg_su_group = False

    @api.onchange('fg_su_wo_account_group')
    def onchange_fg_su_wo_account_group(self):
        if self.fg_su_wo_account_group:
            self.fg_sales_group = self.fg_procurement_group = self.fg_inventory_group = self.fg_finance_with_report_group = self.fg_finance_wo_report_group = self.fg_operations_group = self.fg_mr_group = self.fg_product_marketing_group = self.fg_su_with_hr_group = self.fg_su_group = False

    @api.onchange('fg_su_with_hr_group')
    def onchange_fg_su_with_hr_group(self):
        if self.fg_su_with_hr_group:
            self.fg_sales_group = self.fg_procurement_group = self.fg_inventory_group = self.fg_finance_with_report_group = self.fg_finance_wo_report_group = self.fg_operations_group = self.fg_mr_group = self.fg_product_marketing_group = self.fg_su_wo_account_group = self.fg_su_group = False

    @api.onchange('fg_su_group')
    def onchange_fg_su_group(self):
        if self.fg_su_group:
            self.fg_sales_group = self.fg_procurement_group = self.fg_inventory_group = self.fg_finance_with_report_group = self.fg_finance_wo_report_group = self.fg_operations_group = self.fg_mr_group = self.fg_product_marketing_group = self.fg_su_wo_account_group = self.fg_su_with_hr_group = False

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if self.env.user and self.sudo().env.ref('base.user_root'):
            if not self.env.user.has_group('flemings_base.fg_su_group') and self.env.user.id != self.sudo().env.ref('base.user_root').id:
                args += [('fg_su_group', '=', False)]
        return super(FlemingsResUsers, self)._search(args, offset, limit, order, count=count, access_rights_uid=access_rights_uid)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if self.env.user and self.sudo().env.ref('base.user_root'):
            if not self.env.user.has_group('flemings_base.fg_su_group') and self.env.user.id != self.sudo().env.ref('base.user_root').id:
                domain += [('fg_su_group', '=', False)]
        return super(FlemingsResUsers, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)

    def _get_groups(self, existing_user_base_groups, groups):
        group_ids = existing_user_base_groups
        for g in groups:
            group = self.env.ref(g, raise_if_not_found=False)
            if group:
                group_ids.append(group.id)
        return [[6, False, group_ids]]

    def update_flemings_external_system_user_groups(self):
        for record in self:
            groups = []

            # Flemings User System Group
            if record.fg_sales_group:
                groups.append('flemings_base.fg_sales_group')
            if record.fg_procurement_group:
                groups.append('flemings_base.fg_procurement_group')
            if record.fg_inventory_group:
                groups.append('flemings_base.fg_inventory_group')
            if record.fg_finance_with_report_group:
                groups.append('flemings_base.fg_finance_with_report_group')
            if record.fg_finance_wo_report_group:
                groups.append('flemings_base.fg_finance_wo_report_group')
            if record.fg_operations_group:
                groups.append('flemings_base.fg_operations_group')
            if record.fg_mr_group:
                groups.append('flemings_base.fg_mr_group')
            if record.fg_product_marketing_group:
                groups.append('flemings_base.fg_product_marketing_group')
            if record.fg_su_wo_account_group:
                groups.append('flemings_base.fg_su_wo_account_group')
            if record.fg_su_with_hr_group:
                groups.append('flemings_base.fg_su_with_hr_group')
            if record.fg_su_group:
                groups.append('flemings_base.fg_su_group')

            existing_base_groups = []
            category_id = self.env.ref('flemings_base.flemings_user_system_group_category').id
            grace_groups = self.env['res.groups'].sudo().search(
                ['|', ('category_id', '=', category_id), ('category_id.parent_id', '=', category_id)]).ids

            existing_user_groups = record.groups_id
            for eug in existing_user_groups:
                if eug.id not in grace_groups and eug.id not in existing_base_groups:
                    existing_base_groups.append(eug.id)

            record.sudo().write({'groups_id': self._get_groups(existing_base_groups, groups)})

    fg_sales_group = fields.Boolean(string='Sales')
    fg_procurement_group = fields.Boolean(string='Procurement')
    fg_inventory_group = fields.Boolean(string='Inventory')
    fg_finance_with_report_group = fields.Boolean(string='Finance with Report')
    fg_finance_wo_report_group = fields.Boolean(string='Finance without Report')
    fg_operations_group = fields.Boolean(string='Operations')
    fg_mr_group = fields.Boolean(string='MR')
    fg_product_marketing_group = fields.Boolean(string='Product & Marketing')
    fg_su_wo_account_group = fields.Boolean(string='Super User (w/o Accounting & HR)')
    fg_su_with_hr_group = fields.Boolean(string='Super User (with HR)')
    fg_su_group = fields.Boolean(string='Super User')

    route_ids = fields.Many2many('stock.route', string='Routes')
    journal_ids = fields.Many2many('account.journal', string='Allowed Journals')

    @api.model
    def create(self, vals):
        res = super(FlemingsResUsers, self).create(vals)
        for record in res:
            # Flemings System - User Group Update
            if 'fg_sales_group' in vals or 'fg_procurement_group' in vals or 'fg_inventory_group' in vals \
                    or 'fg_finance_with_report_group' in vals or 'fg_finance_wo_report_group' in vals \
                    or 'fg_operations_group' in vals or 'fg_mr_group' in vals \
                    or 'fg_product_marketing_group' in vals or 'fg_su_wo_account_group' in vals \
                    or 'fg_su_with_hr_group' in vals or 'fg_su_group' in vals:
                record.update_flemings_external_system_user_groups()

        return res

    def write(self, vals):
        res = super(FlemingsResUsers, self).write(vals)
        for record in self:
            # Flemings System - User Group Update
            if 'fg_sales_group' in vals or 'fg_procurement_group' in vals or 'fg_inventory_group' in vals \
                    or 'fg_finance_with_report_group' in vals or 'fg_finance_wo_report_group' in vals \
                    or 'fg_operations_group' in vals or 'fg_mr_group' in vals \
                    or 'fg_product_marketing_group' in vals or 'fg_su_wo_account_group' in vals \
                    or 'fg_su_with_hr_group' in vals or 'fg_su_group' in vals:
                record.update_flemings_external_system_user_groups()

        return res

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super(FlemingsResUsers, self).get_view(view_id, view_type, **options)

        if view_type == 'form':
            doc = etree.XML(res['arch'])

            fg_user_groups = [
                'flemings_base.fg_sales_group', 'flemings_base.fg_procurement_group', 'flemings_base.fg_inventory_group',
                'flemings_base.fg_finance_with_report_group', 'flemings_base.fg_finance_wo_report_group',
                'flemings_base.fg_operations_group', 'flemings_base.fg_mr_group',
                'flemings_base.fg_product_marketing_group', 'flemings_base.fg_su_wo_account_group',
                'flemings_base.fg_su_with_hr_group', 'flemings_base.fg_su_group'
            ]
            for group_xml_id in fg_user_groups:
                gid = self.env.ref(group_xml_id).id
                field_id = 'in_group_' + str(gid)
                if doc.xpath("//field[@name='%s']" % field_id):
                    node = doc.xpath("//field[@name='%s']" % field_id)[0]
                    node.set('modifiers', json.dumps({'invisible': True}))

            separator_labels = ['Flemings User System Group']
            for separator_label in separator_labels:
                if doc.xpath("//separator[@string='%s']" % separator_label):
                    node = doc.xpath("//separator[@string='%s']" % separator_label)[0]
                    node.set('modifiers', json.dumps({'invisible': True}))

            for node in doc.xpath("//group[@string='Flemings User System Group']"):
                node.set('modifiers', json.dumps({'invisible': True}))
            res['arch'] = etree.tostring(doc)
        return res
