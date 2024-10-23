from odoo import api, fields, models, tools, _
from datetime import datetime,date
from odoo.exceptions import UserError,AccessError
from bs4 import BeautifulSoup
from lxml import etree
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
import ast
from odoo.http import request


class BaseModel(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def get_views(self, views, options=None):
        actions_and_prints = []
        for access in self.env['remove.action'].search([('access_management_id.company_ids', 'in', self.env.company.id), ('access_management_id', 'in', self.env.user.access_management_ids.ids), ('model_id.model', '=', self._name)]):
            actions_and_prints = actions_and_prints + access.mapped('report_action_ids.action_id').ids
            actions_and_prints = actions_and_prints + access.mapped('server_action_ids.action_id').ids
            for view_data in access.view_data_ids:
                for view_data_list in views:
                    if view_data.techname == view_data_list[1]:
                        views.pop(views.index(view_data_list))
        
        res = super().get_views(views, options)
        if 'views' in res.keys():
            for view in ['list', 'form']:
                if view in res['views'].keys():
                    if 'toolbar' in res['views'][view].keys():
                        if 'print' in res['views'][view]['toolbar'].keys():
                            prints = res['views'][view]['toolbar']['print'][:]
                            for pri in prints:
                                if pri['id'] in actions_and_prints:
                                    res['views'][view]['toolbar']['print'].remove(pri)
                
                        if 'print' in res['views'][view]['toolbar'].keys():
                            if 'action' in res['views'][view]['toolbar'].keys():
                                action = res['views'][view]['toolbar']['action'][:]
                                for act in action:
                                    if act['id'] in actions_and_prints:
                                        res['views'][view]['toolbar']['action'].remove(act)
        
        access_management_obj = self.env['access.management']
        cids = request.httprequest.cookies.get('cids') and request.httprequest.cookies.get('cids').split(',')[0] or request.env.company.id

        readonly_access_id = access_management_obj.search([('company_ids', 'in', int(cids)),
                                                           ('active', '=', True),
                                                           ('user_ids', 'in', self.env.user.id),
                                                           ('readonly', '=', True)])
        #for holidays
        today_date = date.today()
        today_start_datetime = datetime.strftime(today_date, "%Y-%m-%d 00:00:00")
        today_end_datetime = datetime.strftime(today_date, "%Y-%m-%d 23:59:59")
        """readonly_holidays = self.env['resource.calendar.leaves'].sudo().search([
                                                           ('work_entry_type_id.name', 'ilike', 'Legal leaves'),
                                                           ('date_from', '>=', today_start_datetime),
                                                           ('date_to', '<=', today_end_datetime),
                                                           ])"""

        access_recs_domain = [('access_management_id.company_ids', 'in', self.env.company.id),
                              ('access_management_id.user_ids', 'in', self.env.user.id),
                              ('access_management_id.active', '=', True),
                              # ('model_id.model','=',res['model'])
                              ]
        access_recs_common = self.env['access.domain.ah'].search(access_recs_domain)

        access_model_recs_domain = [('access_management_id.company_ids', 'in', self.env.company.id),
                                    ('access_management_id.user_ids', 'in', self.env.user.id),
                                    ('access_management_id.active', '=', True)]
        access_model_recs_common = self.env['remove.action'].search(access_model_recs_domain)
        
        form = 'form' in res['views']
        tree = 'list' in res['views']
        kanban = 'kanban' in res['views']
        
        # if 'form' in final_views:
        #     doc = etree.XML(final_views['form']['arch'])
        #     doc.attrib.update({'create':'false', 'delete':'false','edit':'false'})
        #     res['views']['form']['arch'] = etree.tostring(doc, encoding='unicode')
        
        #
        if form:
            if res['views']['form']['arch']:
                if access_management_obj.search([('company_ids', 'in', self.env.company.id), ('active', '=', True), ('user_ids', 'in', self.env.user.id), ('hide_chatter', '=', True)], limit=1).id \
                        or self.env['remove.action'].search([('access_management_id.company_ids', 'in', self.env.company.id), ('access_management_id.active', '=', True), ('access_management_id.user_ids', 'in', self.env.user.id), ('model_id.model', '=', res['views']['form']['model']), ('restrict_chatter', '=', True)], limit=1):
                    doc = etree.XML(res['views']['form']['arch'])
                    for div in doc.xpath("//div[@class='oe_chatter']"):
                        div.getparent().remove(div)
                    res['views']['form']['arch'] = etree.tostring(doc, encoding='unicode')
        if readonly_access_id:# or readonly_holidays:
            if form:
                if res['views']['form']['arch']:
                    doc = etree.XML(res['views']['form']['arch'])
                    doc.attrib.update({'create': 'false', 'delete': 'false', 'edit': 'false'})
                    res['views']['form']['arch'] = etree.tostring(doc, encoding='unicode')
            if tree:
                if res['views']['list']['arch']:
                    doc = etree.XML(res['views']['list']['arch'])
                    doc.attrib.update({'create': 'false', 'delete': 'false', 'edit': 'false'})
                    res['views']['list']['arch'] = etree.tostring(doc, encoding='unicode')
            if kanban:
                if res['views']['kanban']['arch']:
                    doc = etree.XML(res['views']['kanban']['arch'])
                    doc.attrib.update({'create': 'false', 'delete': 'false' ,'edit': 'false'})
                    res['views']['kanban']['arch'] = etree.tostring(doc, encoding='unicode').replace('&amp;quot;', '&quot;')
        else:
            if access_model_recs_common:
                if form:
                    access_model_recs = self.env['remove.action'].search(access_model_recs_domain + [('model_id.model', '=', res['views']['form']['model'])])
                    
                    delete = 'true'
                    edit = 'true'
                    create = 'true'
                    for access_model in access_model_recs:
                        if access_model.restrict_create:
                            create = 'false'
                        if access_model.restrict_edit:
                            edit = 'false'
                        if access_model.restrict_delete:
                            delete = 'false'
                    doc = etree.XML(res['views']['form']['arch'])
                    doc.attrib.update({'create': create, 'delete': delete, 'edit': edit})
                    res['views']['form']['arch'] = etree.tostring(doc, encoding='unicode')
                if tree:
                    
                    access_model_recs = self.env['remove.action'].search(access_model_recs_domain + [('model_id.model', '=', res['views']['list']['model'])])
                    delete = 'true'
                    edit = 'true'
                    create = 'true'
                    for access_model in access_model_recs:
                        if access_model.restrict_create:
                            create = 'false'
                        if access_model.restrict_edit:
                            edit = 'false'
                        if access_model.restrict_delete:
                            delete = 'false'
                    doc = etree.XML(res['views']['list']['arch'])
                    doc.attrib.update({'create': create, 'delete': delete, 'edit': edit})
                    res['views']['list']['arch'] = etree.tostring(doc, encoding='unicode')
    
                if kanban:
                    access_model_recs = self.env['remove.action'].search(access_model_recs_domain + [('model_id.model', '=', res['views']['kanban']['model'])])
                    delete = 'true'
                    edit = 'true'
                    create = 'true'
                    for access_model in access_model_recs:
                        if access_model.restrict_create:
                            create = 'false'
                        if access_model.restrict_edit:
                            edit = 'false'
                        if access_model.restrict_delete:
                            delete = 'false'
                    doc = etree.XML(res['views']['kanban']['arch'])
                    doc.attrib.update({'create': create, 'delete': delete, 'edit': edit})
                    res['views']['kanban']['arch'] = etree.tostring(doc, encoding='unicode')
    
            if access_recs_common:
                if form:
                    access_model_recs = self.env['access.domain.ah'].search(access_recs_domain + [('model_id.model', '=', res['views']['form']['model'])])
                    delete = 'true'
                    edit = 'true'
                    create = 'true'
                    for access_model in access_model_recs:
                        if access_model.create_right:
                            create = 'false'
                        if access_model.write_right:
                            edit = 'false'
                        if access_model.delete_right:
                            delete = 'false'
                    doc = etree.XML(res['views']['form']['arch'])
                    doc.attrib.update({'create': create, 'delete': delete, 'edit': edit})
                    res['views']['form']['arch'] = etree.tostring(doc, encoding='unicode')
                    
                if tree:
                    access_model_recs = self.env['access.domain.ah'].search(access_recs_domain + [('model_id.model', '=', res['views']['list']['model'])])
                    delete = 'true'
                    edit = 'true'
                    create = 'true'
                    for access_model in access_model_recs:
                        if access_model.create_right:
                            create = 'false'
                        if access_model.write_right:
                            edit = 'false'
                        if access_model.delete_right:
                            delete = 'false'
                    doc = etree.XML(res['views']['list']['arch'])
                    doc.attrib.update({'create': create, 'delete': delete, 'edit': edit})
                    res['views']['list']['arch'] = etree.tostring(doc, encoding='unicode')
                    
                if kanban:
                    access_model_recs = self.env['access.domain.ah'].search(access_recs_domain + [('model_id.model', '=', res['views']['kanban']['model'])])
                    delete = 'true'
                    edit = 'true'
                    create = 'true'
                    for access_model in access_model_recs:
                        if access_model.create_right:
                            create = 'false'
                        if access_model.write_right:
                            edit = 'false'
                        if access_model.delete_right:
                            delete = 'false'
                    doc = etree.XML(res['views']['kanban']['arch'])
                    doc.attrib.update({'create': create, 'delete': delete, 'edit': edit})
                    res['views']['kanban']['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    def _get_access_management_domain_record(self, model=False):
        records = None
        try:
            if model:
                self._cr.execute("SELECT id FROM ir_model WHERE model='" + model + "'")
                model_numeric_id = self._cr.fetchone()[0]
                if model_numeric_id and isinstance(model_numeric_id, int) and self.env.user:
                    
                    self._cr.execute("""
                                    SELECT dm.id
                                    FROM access_domain_ah as dm
                                    WHERE dm.model_id=%s AND dm.access_management_id 
                                    IN (SELECT am.id 
                                        FROM access_management as am 
                                        WHERE am.active='t' AND am.id 
                                        IN (SELECT amusr.access_management_id
                                            FROM access_management_users_rel_ah as amusr
                                            WHERE amusr.user_id=%s))
                                    """, [model_numeric_id, self.env.user.id])
                    records = self.env['access.domain.ah'].browse(row[0] for row in self._cr.fetchall())
        except:
            pass                    
        return records

    def _check_access_management_right(self, mode=False, records=False):
        access_flag = False
        access_rule = None
        for record in records.sudo():
            if mode == 'create' and record.create_right:
                access_flag = True
                break
            elif mode in ['write','unlink']:
                access = False
                if mode == 'unlink':
                    access = record.delete_right
                elif mode == 'write':
                    access = record.write_right

                domain_list = []
                # eval_context = rec._eval_context()
                dom = safe_eval(record.domain) if record.domain else []
                dom = expression.normalize_domain(dom)
                if isinstance(dom,list):
                    for tuple in dom:
                        operator_value = tuple[1]
                        right_value = tuple[2]
                        if operator_value in ['in', 'not in']:
                            if isinstance(right_value, list) and 0 in right_value:
                                zero_index = right_value.index(0)
                                right_value[zero_index] = self.env.user.id

                domain_list.append(dom)
                search_domain = expression.AND(domain_list)
                if 'active' in self._fields:
                    search_domain = ['|', ('active', '=', False), ('active', '=', True)] + search_domain
                record_ids = self.search(search_domain)

                if self in record_ids and access:
                    access_flag = access
                    break
            access_rule = record.access_management_id.name
        return {'access_flag' : access_flag, 'access_rule': access_rule}

    def _display_access_management_error(self,mode=None,rule=None):
        if mode and rule:
            msg_heads = {
                        'unlink': _("Due to access management rule,\nYou are not allowed to delete record '%(record)s' from (%(document_model)s) model.", record=self.display_name, document_model=self._name),
                        'write': _("Due to access management rule,\nYou are not allowed to edit record '%(record)s' from (%(document_model)s) model.", record=self.display_name, document_model=self._name),
                        'create': _("Due to access management rule,\nYou are not allowed to create records from (%(document_model)s) model.", document_model=self.display_name),        
                        }
            operation_error = msg_heads[mode]
            resolution_info = _("Check Applied Rule on Access Management:\n %(access_name)s",access_name=rule)        
                        
            msg = """{operation_error}            

{resolution_info}""".format(operation_error=operation_error,resolution_info=resolution_info)
            raise AccessError(msg)

    def unlink(self):
        value = self.env['ir.config_parameter'].sudo().search([('key','=','uninstall_simplify_access_management')],limit=1).value
        if not value:
            for rec in self:
                if rec._name:
                    access_domain_ah_ids = rec._get_access_management_domain_record(model=rec._name)
                    if access_domain_ah_ids:
                        access_domain_ah_ids = access_domain_ah_ids.filtered(lambda line: self.env.company in line.access_management_id.company_ids)
                    if access_domain_ah_ids:
                        flag = rec._check_access_management_right(mode='unlink',records=access_domain_ah_ids)
                        unlink_flag = flag['access_flag']
                        access_rule = flag['access_rule']
                        if not unlink_flag:
                            rec._display_access_management_error(mode='unlink',rule=access_rule)
        
        return super().unlink()

    def write(self, vals):
        value = self.env['ir.config_parameter'].sudo().search([('key','=','uninstall_simplify_access_management')],limit=1).value
        if not value:
            for rec in self:
                if rec._name:
                    access_domain_ah_ids = rec._get_access_management_domain_record(model=rec._name)
                    if access_domain_ah_ids:
                        access_domain_ah_ids = access_domain_ah_ids.filtered(lambda line: self.env.company in line.access_management_id.company_ids)
                    if access_domain_ah_ids:
                        flag = rec._check_access_management_right(mode='write',records=access_domain_ah_ids)
                        write_flag = flag['access_flag']
                        access_rule = flag['access_rule']
                        if not write_flag:
                            rec._display_access_management_error(mode='write',rule=access_rule)
        return super().write(vals)

    # @api.model_create_multi
    # @api.returns('self', lambda value: value.id)
    # def create(self, vals_list):
    #     value = self.env['ir.config_parameter'].sudo().search([('key','=','uninstall_simplify_access_management')],limit=1).value
    #     if not value:
    #         if self._name:
    #             access_domain_ah_ids = self._get_access_management_domain_record(model=self._name)
    #             if access_domain_ah_ids:
    #                 access_domain_ah_ids = access_domain_ah_ids.filtered(lambda line: self.env.company in line.access_management_id.company_ids)
    #             if access_domain_ah_ids:
    #                     flag = self._check_access_management_right(mode='create',records=access_domain_ah_ids)
    #                     create_flag = flag['access_flag']
    #                     access_rule = flag['access_rule']
    #                     if not create_flag:
    #                         self._display_access_management_error(mode='create',rule=access_rule)

    #     return super().create(vals_list)
