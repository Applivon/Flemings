from odoo import fields, models, api, _, SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.http import request
from datetime import datetime


class access_management(models.Model):
    _name = 'access.management'
    _description = "Hide Menu Access"

    def _domain_access_group_id(self):
        return [('category_id', '=', self.env.ref('flemings_base.flemings_user_system_group_category').id)]

    name = fields.Char('Name')
    group_id = fields.Many2one('res.groups', string='Group', domain=_domain_access_group_id)
    user_ids = fields.Many2many('res.users', 'access_management_users_rel_ah', 'access_management_id', 'user_id', 'Users')
    active = fields.Boolean('Active', default=True)

    hide_menu_ids = fields.Many2many('ir.ui.menu', 'access_management_menu_rel_ah', 'access_management_id', 'menu_id', 'Hide Menu')
    total_menus = fields.Integer('Total Menus', compute="_count_total_menus")
    company_ids = fields.Many2many('res.company', 'access_management_company_rel', 'access_management_id', 'company_id', 'Companies', required=True, default=lambda self: self.env.user.company_ids.ids)

    self_module_menu_ids = fields.Many2many('ir.ui.menu', 'access_management_ir_ui_self_module_menu', 'access_management_id', 'menu_id', 'Self Module Menu', compute="_get_self_module_info")

    def _get_self_module_info(self):
        access_menu_id = self.env.ref('flemings_base.main_menu_simplify_access_management')
        for rec in self:
            rec.self_module_menu_ids = [(6, 0, access_menu_id.ids or [])]

    @api.onchange('group_id')
    def onchange_group_id(self):
        for record in self:
            record.name = record.user_ids = False
            if record.group_id:
                if self.sudo().search([('group_id', '=', record.group_id.id)]):
                    group_name = record.group_id.name
                    record.group_id = False
                    return {'warning': {'title': _("Warning"), 'message': _("Access Management already exists for this Group '%s' !") % group_name}}
            if record.group_id:
                record.name = record.group_id.full_name
                record.user_ids = [(6, 0, record.sudo().group_id.users.ids or [])]

    @api.constrains('group_id')
    def check_exists_group_id(self):
        for record in self:
            if record.group_id:
                if self.sudo().search([('id', '!=', record.id), ('group_id', '=', record.group_id.id)]):
                    raise UserError(_('Access Management already exists for this Group !'))

    @api.depends('hide_menu_ids')
    def _count_total_menus(self):
        for rec in self:
            rec.total_menus = len(rec.hide_menu_ids) or 0

    def toggle_active_value(self):
        for record in self:
            record.write({'active': not record.active})
        return True

    def update_menu_items_internal_user_group(self):
        internal_user_group_id = self.sudo().env.ref('base.group_user')
        context = self._context.copy()
        context.update({'ir.ui.menu.full_list': True})

        if internal_user_group_id:
            for menu_id in self.env['ir.ui.menu'].with_context(context).sudo().search([
                ('groups_id', '!=', False), ('groups_id', '!=', internal_user_group_id.id), '|', ('active', '=', True),
                ('active', '=', False)
            ]):
                self._cr.execute("""
                  INSERT INTO ir_ui_menu_group_rel (menu_id, gid) SELECT %s, %s 
                    WHERE NOT EXISTS (SELECT gid FROM ir_ui_menu_group_rel WHERE menu_id = %s and gid = %s)
                """ % (menu_id.id, internal_user_group_id.id, menu_id.id, internal_user_group_id.id))

    @api.model
    def create(self, vals):
        res = super(access_management, self).create(vals)
        self.clear_caches()
        for record in res:
            record.update_menu_items_internal_user_group()

        return res

    def unlink(self):
        res = super(access_management, self).unlink()
        self.clear_caches()
        return res

    def write(self, vals):
        res = super(access_management, self).write(vals)
        self.clear_caches()
        if 'group_id' in vals or 'user_ids' in vals:
            for record in self:
                record.update_menu_items_internal_user_group()

        return res


class FGResUsers(models.Model):
    _inherit = 'res.users'

    access_management_ids = fields.Many2many('access.management', 'access_management_users_rel_ah', 'user_id', 'access_management_id', string='Access Pack')

    @api.model
    def create(self, vals):
        res = super(FGResUsers, self).create(vals)
        for record in res:
            # Flemings System - User Group Update
            if 'fg_sales_group' in vals or 'fg_procurement_group' in vals or 'fg_inventory_group' in vals \
                    or 'fg_finance_with_report_group' in vals or 'fg_finance_wo_report_group' in vals \
                    or 'fg_operations_group' in vals or 'fg_mr_group' in vals \
                    or 'fg_product_marketing_group' in vals or 'fg_su_wo_account_group' in vals \
                    or 'fg_su_with_hr_group' in vals or 'fg_su_group' in vals:

                access_ids = self.env['access.management'].sudo().search(['|', ('active', '=', True), ('active', '=', False)])
                for access_id in access_ids:
                    access_id.user_ids = [(6, 0, access_id.sudo().group_id.users.ids or [])]

        return res

    def write(self, vals):
        res = super(FGResUsers, self).write(vals)
        for record in self:
            # Flemings System - User Group Update
            if 'fg_sales_group' in vals or 'fg_procurement_group' in vals or 'fg_inventory_group' in vals \
                    or 'fg_finance_with_report_group' in vals or 'fg_finance_wo_report_group' in vals \
                    or 'fg_operations_group' in vals or 'fg_mr_group' in vals \
                    or 'fg_product_marketing_group' in vals or 'fg_su_wo_account_group' in vals \
                    or 'fg_su_with_hr_group' in vals or 'fg_su_group' in vals:

                access_ids = self.env['access.management'].sudo().search(['|', ('active', '=', True), ('active', '=', False)])
                for access_id in access_ids:
                    access_id.user_ids = [(6, 0, access_id.sudo().group_id.users.ids or [])]

        return res


class ir_ui_menu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.returns('self')
    def _filter_visible_menus(self):
        """ Filter `self` to only keep the menu items that should be visible in
			the menu hierarchy of the current user.
			Uses a cache for speeding up the computation.
		"""
        visible_ids = self._visible_menu_ids(request.session.debug if request else False)
        cids = request.httprequest.cookies.get('cids') and request.httprequest.cookies.get('cids').split(',')[0] or self.env.company.id
        hide_ids = self.env.user.access_management_ids.filtered(lambda line: int(cids) in line.company_ids.ids).mapped('hide_menu_ids')
        return self.filtered(lambda menu: menu.id in visible_ids and menu.id not in hide_ids.ids)
