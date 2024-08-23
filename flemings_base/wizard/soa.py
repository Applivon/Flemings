# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar
import logging
from datetime import timedelta, datetime
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

import base64
import io

_logger = logging.getLogger(__name__)


class StatementAccountReportWizard(models.TransientModel):
    _name = 'statement.account.report.wizard'
    _description = 'statement.account.report.wizard'

    date = fields.Date(string='Date', required=True, default=fields.Date.today())
    partner_ids = fields.Many2many('res.partner', 'soa_report_rel_partner', string="Customers")
    company_ids = fields.Many2many("res.company", string="Companies", default=lambda self: self.env.user.company_ids.ids)
    rp_logo = fields.Boolean('Include Logo in SOA report')
    
    def print_report(self):
        self.ensure_one()
        [data] = self.read()        
        
        if not data['partner_ids']:
            partner_ids = self.env['res.partner'].search([]).ids
        else:
            partner_ids = data['partner_ids']
        
        datas = {
            'ids': partner_ids,
            'model': 'res.partner',
            'form': data
        }
        
        return self.env.ref('flemings_base.action_statement_of_account').report_action(docids=self.ids, data=datas)

    def generate_excel_report(self):
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'flemings_base.statement_account_report_wizard_xlsx'
        }


class StatementOfAccount(models.AbstractModel):
    _name = 'report.flemings_base.report_statement_of_account_document'
    _description = 'Statement Of Account'
    
    @api.model
    def _get_report_values(self, docids, data=None):        
        partner_ids = self.env['res.partner'].browse(data['ids'])
        new_partner_ids = self.env['res.partner']
        values = {}
        for partner in partner_ids:
            datas = partner.get_partner_soa(datetime.strptime(data['form']['date'],DEFAULT_SERVER_DATE_FORMAT))
            
            if len(datas) > 0:
                new_partner_ids |= partner
                values.update({partner: datas})
                
        return {
            'doc_ids': self.ids,
            'doc_model': 'res.partner',
            'docs': new_partner_ids,
            'date': data['form']['date'],
            'print_logo': data['form']['rp_logo'],
            'datas': values,
            'company': self.env.user.company_id
        }


class ResPartner(models.Model):
    _inherit = "res.partner"
    
    @api.model
    def get_partner_soa(self, date):
        self._cr.execute('''
            select am.id as invoice_id, am.name as invoice_name, am.move_type as move_type, to_char(am.invoice_date,'dd.mm.yyyy') as invoice_date, curr.name as currency,
                am.amount_total_signed as amount_total,
                CASE WHEN am.move_type = 'out_refund' THEN -sum(residual.amount_sgd) ELSE sum(residual.amount_sgd) END as residual_amount,
                am.customer_po
            from account_move am
            join account_move_line aml on aml.move_id = am.id
            join account_account acc on aml.account_id = acc.id
            join res_currency curr on am.currency_id = curr.id
            left join (
                select am.id as move_id, am.move_type, am.name as move_name, part_rec.debit_amount_currency,
                    CASE WHEN am.move_type = 'out_invoice' THEN credit_line.date ELSE debit_line.date END payment_date,
                    CASE WHEN am.move_type = 'out_invoice' THEN part_rec.debit_currency_id ELSE part_rec.credit_currency_id END currency,
                    CASE WHEN am.move_type = 'out_invoice' THEN part_rec.credit_amount_currency ELSE part_rec.debit_amount_currency END amount_currency,
                    CASE WHEN am.move_type = 'out_invoice' THEN part_rec.amount ELSE part_rec.amount END amount_sgd
                from account_partial_reconcile part_rec
                join account_move_line aml on (part_rec.credit_move_id = aml.id or part_rec.debit_move_id = aml.id)
                join account_move am on aml.move_id = am.id
                left join account_move_line credit_line on (part_rec.credit_move_id = credit_line.id)
                left join account_move_line debit_line on (part_rec.debit_move_id = debit_line.id)
                --where aml.exclude_from_invoice_tab = 't'
            ) residual on residual.move_id = am.id and residual.payment_date <= '%s'
            where am.move_type in ('out_invoice', 'out_refund') and acc.account_type in ('asset_receivable', 'liability_payable') and am.state = 'posted' 
            --and aml.exclude_from_invoice_tab = 't' 
            and am.partner_id = %s 
                AND (COALESCE(am.invoice_date_due,am.invoice_date) <= '%s' OR (am.invoice_date <= '%s' and am.invoice_date_due>= '%s'))
            group by am.id, am.name, am.amount_total_signed, am.move_type, am.invoice_date, curr.name, am.customer_po
            order by am.invoice_date, am.name
        ''' % (date, self.id, date, date, date))
        res = self._cr.dictfetchall()
        flag = False
        
        index = 0
        for item in res:
            if item['amount_total'] != item['residual_amount'] and item['amount_total'] != 0:
                flag = True
            res[index]['invoice_id'] = self.env['account.move'].browse(item['invoice_id'])
            index += 1
        return flag and res or []
    
    def sql_to_get_payment(self, date, range_date):
        domain = " AND "
        args = {'date': date, 'partner': self.id}
        if range_date['pre_date']:
            domain += " am.invoice_date_due >= %(pre_date)s"
            args.update({'pre_date': str(range_date['pre_date'])})
        if range_date['next_date']:
            if range_date['pre_date']:
                domain += " AND"
            domain += " am.invoice_date_due < %(next_date)s"
            args.update({'next_date': str(range_date['next_date'])})
        
        self._cr.execute('''
            SELECT 
                CASE WHEN sum(amount_total) IS NOT NULL THEN sum(amount_total) ELSE 0 END as amount_total,
                CASE WHEN sum(residual_amount) IS NOT NULL THEN sum(residual_amount) ELSE 0 END as residual_amount, invoice.currency as currency
            FROM (
                select am.name as invoice_name, am.move_type as move_type, am.invoice_date as invoice_date, curr.name as currency,
                    CASE WHEN am.move_type = 'out_refund' THEN -am.amount_total ELSE am.amount_total END as amount_total,
                    CASE WHEN am.move_type = 'out_refund' THEN -sum(residual.amount_currency) ELSE sum(residual.amount_currency) END as residual_amount
                from account_move am
                join account_move_line aml on aml.move_id = am.id
                join account_account acc on aml.account_id = acc.id
                join res_currency curr on am.currency_id = curr.id
                left join (
                    select am.id as move_id, am.move_type, am.name as move_name, part_rec.debit_amount_currency,
                        CASE WHEN am.move_type = 'out_invoice' THEN credit_line.date ELSE debit_line.date END payment_date,
                        CASE WHEN am.move_type = 'out_invoice' THEN part_rec.debit_currency_id ELSE part_rec.credit_currency_id END currency,
                        CASE WHEN am.move_type = 'out_invoice' THEN part_rec.debit_amount_currency ELSE part_rec.credit_amount_currency END amount_currency
                    from account_partial_reconcile part_rec
                    join account_move_line aml on (part_rec.credit_move_id = aml.id or part_rec.debit_move_id = aml.id)
                    join account_move am on aml.move_id = am.id
                    left join account_move_line credit_line on (part_rec.credit_move_id = credit_line.id)
                    left join account_move_line debit_line on (part_rec.debit_move_id = debit_line.id)
                    --where aml.exclude_from_invoice_tab = 't'
                ) residual on residual.move_id = am.id and residual.payment_date <= %(date)s
                where am.move_type in ('out_invoice', 'out_refund') and acc.account_type in ('asset_receivable', 'liability_payable') and am.state = 'posted' 
                --and aml.exclude_from_invoice_tab = 't' 
                and am.partner_id = %(partner)s 
                    AND (COALESCE(am.invoice_date_due,am.invoice_date) <= %(date)s OR (am.invoice_date <= %(date)s and am.invoice_date_due>= %(date)s)) ''' + domain + '''
                group by am.name, am.amount_total, am.move_type, am.invoice_date, curr.name
                order by am.name
            ) invoice
            group by invoice.currency
            ORDER BY invoice.currency
        ''', args)
        
        res = self._cr.dictfetchall()
        return res

    def sql_to_get_payment_summary(self, date):
        now_time = datetime.now()
        if date:
            now_time = datetime.strptime(date, "%Y-%m-%d")
        current_date = datetime.strftime(now_time, '%Y-%m-%d')
        date_01 = now_time - timedelta(days=30)
        date_01 = datetime.strftime(date_01, '%Y-%m-%d')
        date_02 = now_time - timedelta(days=60)
        date_02 = datetime.strftime(date_02, '%Y-%m-%d')
        date_03 = now_time - timedelta(days=90)
        date_03 = datetime.strftime(date_03, '%Y-%m-%d')
        
        data = {
            'range_1': {'desc': 'current', 'range': {'pre_date': current_date, 'next_date': False}}, 
            'range_2': {'desc': '1-30 days', 'range': {'pre_date': date_01, 'next_date': current_date}}, 
            'range_3': {'desc': '31-60 days', 'range': {'pre_date': date_02, 'next_date': date_01}}, 
            'range_4': {'desc': '61-90 days', 'range': {'pre_date': date_03, 'next_date': date_02}}, 
            'range_5': {'desc': '>90 days', 'range': {'pre_date': False, 'next_date': date_03}}, 
        }
        
        for key, val in data.items():
            data[key]['data'] = self.sql_to_get_payment(date, val['range'])
            
        new_data = {'key': data, 'content': {}}
        
        for range_title, details in data.items():
            for item in details['data']:
                if item['amount_total'] != item['residual_amount']:
                    if item['currency'] not in new_data['content']:
                        new_data['content'].update({item['currency']: {key: 0 for key in data.keys()}})
                    new_data['content'][item['currency']][range_title] = item['amount_total'] - item['residual_amount']
                    
        return new_data


class FlemingsSoAReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.statement_account_report_wizard_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Statement of Account'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('STATEMENT OF ACCOUNT')

        align_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        align_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True})
        align_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        align_bold_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True, 'border': 1})

        row = 1
        for obj in objects:
            sheet.set_row(row, 20)
            sheet.set_row(row + 1, 20)

            sheet.set_column('A:A', 25)
            sheet.set_column('B:B', 25)
            sheet.set_column('C:C', 25)
            sheet.set_column('D:D', 25)
            sheet.set_column('E:E', 25)
            sheet.set_column('F:F', 25)

            partner_domain = []
            if obj.partner_ids:
                partner_domain += [('id', 'in', obj.partner_ids.ids or [])]

            partner_ids = self.env['res.partner'].sudo().search(partner_domain)
            new_partner_ids = self.env['res.partner']
            values = {}
            for partner in partner_ids:
                datas = partner.get_partner_soa(datetime.strptime(str(obj.date), DEFAULT_SERVER_DATE_FORMAT))

                if len(datas) > 0:
                    new_partner_ids |= partner
                    values.update({partner: datas})
            datas = values

            date = datetime.strftime(obj.date, '%d.%m.%Y')
            for partner in datas:

                # Insert Company Logo
                company_id = self.env['res.company'].sudo().search([('id', 'in', obj.company_ids.ids)], order='id asc', limit=1)
                # if obj.rp_logo and company_id and company_id.banner_report:
                #     image_width = 300.0
                #     image_height = 400.0
                #     cell_width = 128.0
                #     cell_height = 262.0
                #
                #     x_scale = cell_width / image_width
                #     y_scale = cell_height / image_height
                #
                #     sheet.insert_image(
                #         'A' + str(row), '', {
                #             'x_scale': x_scale, 'y_scale': y_scale, 'align': 'center',
                #             'image_data': io.BytesIO(base64.b64decode(company_id.banner_report))
                #         }
                #     )
                #     row += 10

                if obj.rp_logo:
                    sheet.merge_range(row, 0, row + 7, 0, '', align_bold_center)
                    sheet.merge_range(row, 4, row + 7, 5, '', align_bold_center)

                    image_width = 140.0
                    image_height = 180.0
                    cell_width = 80.0
                    cell_height = 100.0

                    x_scale = cell_width / image_width
                    y_scale = cell_height / image_height

                    if company_id.logo:
                        sheet.insert_image(
                            'A' + str(row + 2), '',
                            {'x_scale': x_scale, 'y_scale': y_scale, 'align': 'center',
                             'image_data': io.BytesIO(base64.b64decode(company_id.logo))
                             }
                        )
                    if company_id.sgs_img:
                        image_width = 240.0
                        image_height = 300.0
                        cell_width = 40.0
                        cell_height = 50.0

                        x_scale = cell_width / image_width
                        y_scale = cell_height / image_height

                        sheet.insert_image(
                            'E' + str(row + 2), '',
                            {'x_scale': x_scale, 'y_scale': y_scale, 'align': 'center',
                             'image_data': io.BytesIO(base64.b64decode(company_id.sgs_img))
                             }
                        )

                    company_address = (
                            str(company_id.street or '') + ' ' + str(company_id.street2 or '') + '\n' +
                            str(company_id.country_id.name or '') + ' ' + str(company_id.zip or '') + ' Tel: ' + str(company_id.phone or '') + ' Fax: ' + str(company_id.fax or '') + '\n' +
                            'Email: ' + str(company_id.email or '') + ' ' + str(company_id.website or '')
                    )

                    sheet.merge_range(row, 1, row + 2, 3, str(company_id.name), workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'bottom', 'bold': True, 'text_wrap': True, 'font_size': 18}))
                    sheet.merge_range(row + 3, 1, row + 7, 3, company_address, align_center)

                    row += 9

                sheet.merge_range(row, 0, row, 5, 'STATEMENT OF ACCOUNT', workbook.add_format(
                    {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True}))

                row += 1
                sheet.merge_range(row, 0, row, 3, partner.display_name, workbook.add_format(
                    {'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'bold': True}))
                sheet.merge_range(row, 4, row, 5, 'Date: ' + str(date), workbook.add_format(
                    {'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'bold': True}))

                row += 1
                sheet.merge_range(row, 0, row, 3, str(partner.street or '') + ' ' + str(partner.street2 or ''), workbook.add_format(
                    {'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'bold': True}))

                row += 1
                sheet.merge_range(row, 0, row, 3, str(partner.city or '') + ' ' + str(partner.country_id.name or '') + ' ' + str(partner.zip or ''), workbook.add_format(
                    {'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'bold': True}))

                row += 1
                tell_no = partner.phone or partner.mobile
                sheet.merge_range(row, 0, row, 3, 'TELL: ' + str(tell_no or ''), workbook.add_format(
                    {'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'bold': True}))

                row += 2
                titles = ['DATE', 'INVOICE', 'YOUR PO', 'DO NO.', 'TOTAL AMOUNT', 'OUTSTANDING AMOUNT']
                for index in range(0, len(titles)):
                    sheet.write(row, index, titles[index], align_bold_center)
                row += 1

                balance = 0
                for soa in datas[partner]:
                    if soa['residual_amount']:
                        outstanding = soa['amount_total'] - soa['residual_amount']
                    else:
                        outstanding = soa['amount_total']

                    balance = balance + outstanding
                    if outstanding != 0:
                        sheet.write(row, 0, soa['invoice_date'], align_center)
                        sheet.write(row, 1, soa['invoice_name'], align_left)
                        sheet.write(row, 2, soa['customer_po'], align_left)
                        sheet.write(row, 3, soa['invoice_id'].delivery_order_names, align_left)
                        sheet.write(row, 4, str('{:.2f}'.format(outstanding)), align_right)
                        sheet.write(row, 5, str('{:.2f}'.format(balance)), align_right)
                        row += 1

                row += 2
                summary_data = partner.sql_to_get_payment_summary(str(obj.date))

                titles = [str(summary_data['key'][v]['desc']).upper() for v in summary_data.get('key')]
                titles += ['TOTAL DUE']
                for index in range(0, len(titles)):
                    sheet.write(row, index, titles[index], align_bold_center)
                row += 1

                for currency in summary_data.get('content'):
                    total_outstanding = 0
                    index = 0
                    for v in summary_data['content'][currency]:
                        outstanding = 0

                        if summary_data['content'][currency][v]:
                            outstanding = summary_data['content'][currency][v]
                            total_outstanding = total_outstanding + outstanding

                        sheet.write(row, index, str(currency) + ' ' + str('{:.2f}'.format(outstanding)), align_right)
                        index += 1
                    sheet.write(row, index, str(currency) + ' ' + str('{:.2f}'.format(total_outstanding)), align_right)

                row += 6

            row += 4
