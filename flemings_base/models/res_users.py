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
            if record.fg_purchaser_group:
                groups.append('flemings_base.fg_purchaser_group')
            if record.fg_business_support_group:
                groups.append('flemings_base.fg_business_support_group')
            if record.fg_inventory_group:
                groups.append('flemings_base.fg_inventory_group')
            if record.fg_product_group:
                groups.append('flemings_base.fg_product_group')
            if record.fg_production_group:
                groups.append('flemings_base.fg_production_group')
            if record.fg_production_controller_group:
                groups.append('flemings_base.fg_production_controller_group')
            if record.fg_logistics_group:
                groups.append('flemings_base.fg_logistics_group')
            if record.fg_operations_group:
                groups.append('flemings_base.fg_operations_group')
            if record.fg_finance_group:
                groups.append('flemings_base.fg_finance_group')
            if record.fg_hr_group:
                groups.append('flemings_base.fg_hr_group')
            if record.fg_admin_group:
                groups.append('flemings_base.fg_admin_group')

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
    fg_purchaser_group = fields.Boolean(string='Purchaser')
    fg_business_support_group = fields.Boolean(string='Business Support Executive')
    fg_inventory_group = fields.Boolean(string='Inventory/Procurement')
    fg_product_group = fields.Boolean(string='Product/E-commerce')
    fg_production_group = fields.Boolean(string='Production')
    fg_production_controller_group = fields.Boolean(string='Production Controller')
    fg_logistics_group = fields.Boolean(string='Logistics')
    fg_operations_group = fields.Boolean(string='Operations')
    fg_finance_group = fields.Boolean(string='Finance & Accounts')
    fg_hr_group = fields.Boolean(string='HR')
    fg_admin_group = fields.Boolean(string='Admin')

    @api.model
    def create(self, vals):
        res = super(FlemingsResUsers, self).create(vals)
        for record in res:
            # Flemings System - User Group Update
            if 'fg_sales_group' in vals or 'fg_purchaser_group' in vals or 'fg_business_support_group' in vals \
                    or 'fg_inventory_group' in vals or 'fg_product_group' in vals \
                    or 'fg_production_group' in vals or 'fg_production_controller_group' in vals \
                    or 'fg_logistics_group' in vals or 'fg_operations_group' in vals \
                    or 'fg_finance_group' in vals or 'fg_hr_group' in vals \
                    or 'fg_admin_group' in vals:
                record.update_flemings_external_system_user_groups()

        return res

    def write(self, vals):
        res = super(FlemingsResUsers, self).write(vals)
        for record in self:
            # Flemings System - User Group Update
            if 'fg_sales_group' in vals or 'fg_purchaser_group' in vals or 'fg_business_support_group' in vals \
                    or 'fg_inventory_group' in vals or 'fg_product_group' in vals \
                    or 'fg_production_group' in vals or 'fg_production_controller_group' in vals \
                    or 'fg_logistics_group' in vals or 'fg_operations_group' in vals \
                    or 'fg_finance_group' in vals or 'fg_hr_group' in vals \
                    or 'fg_admin_group' in vals:
                record.update_flemings_external_system_user_groups()

        return res

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super(FlemingsResUsers, self).get_view(view_id, view_type, **options)

        if view_type == 'form':
            doc = etree.XML(res['arch'])

            fg_user_groups = [
                'flemings_base.fg_sales_group', 'flemings_base.fg_purchaser_group', 'flemings_base.fg_business_support_group',
                'flemings_base.fg_inventory_group', 'flemings_base.fg_product_group',
                'flemings_base.fg_production_group', 'flemings_base.fg_production_controller_group',
                'flemings_base.fg_logistics_group', 'flemings_base.fg_operations_group',
                'flemings_base.fg_finance_group', 'flemings_base.fg_hr_group',
                'flemings_base.fg_admin_group'
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
