from odoo import fields, models, api, _, SUPERUSER_ID
from odoo.exceptions import UserError
from datetime import datetime


class FGResUsers(models.Model):
    _inherit = 'res.users'

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


class FGIRModelAccess(models.Model):
    _inherit = 'ir.model.access'

    fg_custom_internal_access = fields.Boolean(string='Custom Access ?', default=False, copy=False)

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(FGIRModelAccess, self).fields_get(allfields, attributes)
        fields_to_hide = ['fg_custom_internal_access']
        for field in fields_to_hide:
            if res.get(field):
                res.get(field)['searchable'] = False  # hide from filter
                res.get(field)['sortable'] = False  # hide from group by
                res.get(field)['exportable'] = False  # hide from Export List
        return res


class access_management(models.Model):
    _name = 'access.management'
    _description = "Access Management"

    def _domain_access_group_id(self):
        return [('category_id', '=', self.env.ref('flemings_base.flemings_user_system_group_category').id)]

    name = fields.Char('Name')
    group_id = fields.Many2one('res.groups', string='Group', domain=_domain_access_group_id)
    user_ids = fields.Many2many('res.users', 'access_management_users_rel_ah', 'access_management_id', 'user_id', 'Users')

    readonly = fields.Boolean('Read-Only')
    active = fields.Boolean('Active', default=True)

    hide_menu_ids = fields.Many2many('ir.ui.menu', 'access_management_menu_rel_ah', 'access_management_id', 'menu_id', 'Hide Menu')
    hide_field_ids = fields.One2many('hide.field', 'access_management_id', 'Hide Field')
    remove_action_ids = fields.One2many('remove.action', 'access_management_id', 'Remove Action')

    access_domain_ah_ids = fields.One2many('access.domain.ah', 'access_management_id', 'Access Domain')
    hide_view_nodes_ids = fields.One2many('hide.view.nodes', 'access_management_id', 'Button/Tab Access')

    self_module_menu_ids = fields.Many2many('ir.ui.menu', 'access_management_ir_ui_self_module_menu', 'access_management_id', 'menu_id', 'Self Module Menu', compute="_get_self_module_info")
    self_model_ids = fields.Many2many('ir.model', 'access_management_ir_model_self', 'access_management_id', 'model_id', 'Self Model', compute="_get_self_module_info")
    total_rules = fields.Integer('Access Rules', compute="_count_total_rules")

    hide_chatter = fields.Boolean('Hide Chatter')
    disable_debug_mode = fields.Boolean('Disable Developer Mode')

    company_ids = fields.Many2many('res.company', 'access_management_company_rel', 'access_management_id', 'company_id', 'Companies', required=True, default=lambda self: self.env.user.company_ids.ids)
    hide_filters_groups_ids = fields.One2many('hide.filters.groups', 'access_management_id', string='Hide Filters/Group By')

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

    def _count_total_rules(self):
        for rec in self:
            rule = 0
            rule = rule + len(rec.hide_menu_ids) + len(rec.hide_field_ids) + len(rec.remove_action_ids) + len(rec.access_domain_ah_ids) + len(rec.hide_view_nodes_ids)
            rec.total_rules = rule

    def action_show_rules(self):
        pass

    def _get_self_module_info(self):
        access_menu_id = self.env.ref('simplify_access_management.main_menu_simplify_access_management')
        model_list = ['access.management', 'access.domain.ah', 'action.data', 'hide.field', 'hide.view.nodes', 'store.model.nodes', 'remove.action', 'view.data']
        models_ids = self.env['ir.model'].search([('model', 'in', model_list)])
        for rec in self:
            rec.self_module_menu_ids = False
            rec.self_model_ids = False
            if access_menu_id:
                rec.self_module_menu_ids = [(6,0,access_menu_id.ids)]
            if models_ids:
                rec.self_model_ids = [(6,0,models_ids.ids)]

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

    def update_model_access_internal_user_group(self):
        internal_user_group_id = self.sudo().env.ref('base.group_user')
        if internal_user_group_id:
            for model_id in self.env['ir.model'].sudo().search([]):
                record_name = 'fg_internal_user_custom_access_' + str(model_id.model.replace('.', '_'))
                self._cr.execute("""
                  INSERT INTO ir_model_access (name, model_id, group_id, create_date, write_date, create_uid, write_uid, active, perm_read, perm_write, perm_create, perm_unlink, fg_custom_internal_access) 
                    SELECT '%s', %d, %d, '%s', '%s', %d, %d, True, True, True, True, True, True 
                    WHERE NOT EXISTS (SELECT model_id FROM ir_model_access WHERE model_id = %s and group_id = %s and fg_custom_internal_access = True)
                """ % (record_name, model_id.id, internal_user_group_id.id, datetime.now(), datetime.now(), self.env.user.id, self.env.user.id, model_id.id, internal_user_group_id.id))

    @api.model
    def create(self, vals):
        res = super(access_management, self).create(vals)
        # for user in self.env['res.users'].sudo().search([('share','=',False)]):
            # user.clear_caches()
        self.clear_caches()
        if res.readonly:
            for user in res.user_ids:
                if user.has_group('base.group_system') or user.has_group('base.group_erp_manager'):
                    raise UserError(_('Admin user can not be set as a read-only..!'))

        for record in res:
            record.update_menu_items_internal_user_group()
            # record.update_model_access_internal_user_group()

        return res

    def unlink(self):
        res = super(access_management, self).unlink()
        self.clear_caches()
        # for user in self.env['res.users'].sudo().search([('share','=',False)]):
        #     user.clear_caches()
        return res

    def write(self, vals):
        res = super(access_management, self).write(vals)
        for record in self:
            if record.readonly:
                for user in record.user_ids:
                    if user.has_group('base.group_system') or user.has_group('base.group_erp_manager'):
                        raise UserError(_('Admin user can not be set as a read-only..!'))
        # for user in self.env['res.users'].sudo().search([('share','=',False)]):
        #     user.clear_caches()
        self.clear_caches()

        if 'group_id' in vals or 'user_ids' in vals:
            for record in self:
                record.update_menu_items_internal_user_group()
                # record.update_model_access_internal_user_group()

        return res

    def get_remove_options(self, model):
        remove_action = self.env['remove.action'].sudo().search([('access_management_id.company_ids', 'in', self.env.company.id), ('access_management_id', 'in', self.env.user.access_management_ids.ids), ('model_id.model', '=', model)])
        options = []
        for action in remove_action:
            if action.restrict_export:
                options.append(_('Export'))
            if action.restrict_archive_unarchive:
                options.append(_('Archive'))
                options.append(_('Unarchive'))
            if action.restrict_duplicate:
                options.append(_('Duplicate'))
        return options
