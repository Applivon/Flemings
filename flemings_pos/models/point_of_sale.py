from odoo import api, fields, models
from datetime import datetime,date
import pytz
from odoo.exceptions import UserError
array_coin = [10,5,2,1,0.5,0.2,0,1,0.05]
class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def get_total_cash(self, type):
        total_cash_in = 0
        for statement in self.statement_line_ids:
            if type in statement.payment_ref:
                total_cash_in += statement.amount
        return total_cash_in

    def report_get_format_time(self,date, type):
        sgt = pytz.timezone('Singapore')
        if date == 'now' and type == 'datetime':
            now = datetime.now(sgt)
            return now.strftime('%d-%m-%Y %I:%M:%S %p')
        elif date and type == 'time':
            date = date.astimezone(sgt)
            return date.strftime('%I:%M:%S %p')
        elif date and type == 'datetime':
            date = date.astimezone(sgt)
            return date.strftime('%d-%m-%Y %I:%M:%S %p')
        
    def convert_currency(self,value):
        res = 'S$ ' + str('%.2f' % value)
        return res
    def cash_should_be_func(self):
        cash_shoule_be = 0
        cash_in = self.get_total_cash('-in-')
        cash_out = self.get_total_cash('-out-')
        all_cash_payment = 0 
        for payment in self.payment_method_ids:
            if payment.is_cash_count:
                result = self.env['pos.payment'].read_group([('session_id', '=', self.id), ('payment_method_id', '=', payment.id)], ['amount'], ['session_id'])
                if result:
                    all_cash_payment += result[0]['amount']
        return_paid = 0
        for order in self.order_ids:
            if order.refunded_orders_count > 0:
                for payment in order.payment_ids:
                    if payment.payment_method_id.is_cash_count:
                        return_paid += payment.amount
        cash_shoule_be = (cash_in + cash_out + self.cash_register_balance_start + all_cash_payment + return_paid)
        return cash_shoule_be
    def get_session_value(self,type):
        res = ''
        if type == 'total_cash_value':
            sql = '''
                select round(sum(amount),2) as data from pos_payment where session_id = %s and payment_method_id in (
                    select id from pos_payment_method where is_cash_count = true
                )
            '''%(self.id)
            self.env.cr.execute(sql)
            data = self.env.cr.dictfetchone()
            res = data.get('data')
        elif type == 'total_bank_value':
            sql = '''
                select round(sum(amount),2) as data from pos_payment where session_id = %s and payment_method_id in (
                    select id from pos_payment_method where is_cash_count = false
                )
            '''%(self.id)
            self.env.cr.execute(sql)
            data = self.env.cr.dictfetchone()
            res = data.get('data')
        elif type == 'cash_shoule_be':
            cash_shoule_be = self.cash_should_be_func()
            res = 'S$ ' + str('%.2f' % cash_shoule_be)
        elif type == 'cash_diff':
            cash_shoule_be = self.cash_should_be_func()
            cash_diff = self.cash_register_balance_end_real - cash_shoule_be
            res = 'S$ ' + str('%.2f' % cash_diff)
        elif type == 'cash_in_amount':
            cash_in = self.get_total_cash('-in-')
            res = 'S$ ' + str('%.2f' % cash_in)
        elif type == 'cash_out_amount':
            cash_out = self.get_total_cash('-out-')
            res = 'S$ ' + str('%.2f' % cash_out)
            # res = 'S$' + str('%.2f' % cash_out)
        elif type == 'domination':
            res = []
            if 'Money details:' in self.opening_notes:
                res = self.opening_notes.replace('Money details:','').split('\n')
                res = [x.replace('-','') for x in res if x.strip()]
                res = res[::-1]

            else:
                res = ''
            # account_cashbox = self.cash_register_id.cashbox_end_id
            # if account_cashbox:
            #     cashbox_line_ids = self.env['account.cashbox.line'].search([('cashbox_id','=',account_cashbox.id)], order="coin_value desc")
            # for cashbox in array_coin:
            #     res.append(str(cashbox.number) + ' * $' + str(int(cashbox.coin_value)) + ' = $' + str(int(cashbox.coin_value * cashbox.number)))
        elif type == 'payment_method':
            res = []
            for payment in self.payment_method_ids:
                sum_value = 0
                result = self.env['pos.payment'].read_group([('session_id', '=', self.id), ('payment_method_id', '=', payment.id)], ['amount'], ['session_id'])
                if result:
                    sum_value = result[0]['amount']
                res.append(str(payment.name) + ' : S$ ' + str('%.2f' % sum_value))
        elif type == 'void_sales':
            amount_paid = 0
            for order in self.order_ids:
                if order.refunded_orders_count > 0:
                    amount_paid += order.amount_paid
            res = 'S$ ' + str('%.2f' % amount_paid)
        return res
    def get_sale_data(self,type):
        res = ''
        sgt = pytz.timezone('Singapore')
        if type == 'first_sale':
            pos_id = self.env['pos.order'].search([('session_id','=',self.id)], order='id asc', limit = 1)
            if pos_id:
                res = pos_id.name
        elif type == 'first_time':
            pos_id = self.env['pos.order'].search([('session_id', '=', self.id)], order='id asc', limit=1)
            if pos_id:
                res = pos_id.create_date.astimezone(sgt).strftime('%d-%m-%Y %I:%M:%S %p')
        elif type == 'last_sale':
            pos_id = self.env['pos.order'].search([('session_id', '=', self.id)], order='id desc', limit=1)
            if pos_id:
                res = pos_id.name
        elif type == 'last_time':
            pos_id = self.env['pos.order'].search([('session_id', '=', self.id)], order='id desc', limit=1)
            if pos_id:
                res = pos_id.create_date.astimezone(sgt).strftime('%d-%m-%Y %I:%M:%S %p')
        return res

    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        result['search_params']['fields'].extend(['property_payment_term_id'])
        return result
