# -*- coding: utf-8 -*-

from odoo import models, fields, api , _
from datetime import datetime, date, timedelta, time
import pytz

from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

month_dict = {
    '1': 'JAN', '2': 'FEB', '3': 'MAR', '4': 'APR', '5': 'MAY', '6': 'JUN',
    '7': 'JUL', '8': 'AUG', '9': 'SEP', '10': 'OCT', '11': 'NOV', '12': 'DEC'
}


class FGSalarySummaryReport(models.TransientModel):
    _name = 'fg.salary.summary.report'
    _description = 'Salary Summary Report'

    @api.model
    def default_get(self, fields):
        res = super(FGSalarySummaryReport, self).default_get(fields)

        tz = pytz.timezone(self.env.user.tz) if self.env.user.tz else pytz.utc
        user_current_datetime = pytz.utc.localize(datetime.now()).astimezone(tz)
        current_date = user_current_datetime.date()

        res['from_month'], res['to_month'] = '1', str(current_date.month)
        res['from_year'] = res['to_year'] = str(current_date.year)
        return res

    @api.onchange('from_month', 'to_month', 'from_year', 'to_year')
    def onchange_date_from_to(self):
        if self.from_month and self.from_year:
            self.date_from = str(self.from_year) + '-' + str(self.from_month.zfill(2)) + '-01'
        if self.to_month and self.to_year:
            date_to = self.date_to = str(self.to_year) + '-' + str(self.to_month.zfill(2)) + '-01'
            self.date_to = (datetime.strptime(date_to, DEFAULT_SERVER_DATE_FORMAT)) + relativedelta(months=+1, day=1, days=-1)

    @api.onchange('date_from', 'date_to')
    def onchange_date_to(self):
        if self.date_to and self.date_from and self.date_to < self.date_from:
            self.to_month = self.to_year = self.date_to = False
            return {'warning': {
                'title': _("Warning"),
                'message': _("Period 'To' must be greater than or equal to From ..!")}
            }

    from_month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='From Month')
    to_month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='To Month')
    from_year = fields.Selection([(str(num), str(num)) for num in reversed(range(2024, datetime.now().year + 1))], string='From Year')
    to_year = fields.Selection([(str(num), str(num)) for num in reversed(range(2024, datetime.now().year + 1))], string='To Year')

    date_from = fields.Date('From Date')
    date_to = fields.Date('To Date')

    employee_ids = fields.Many2many('hr.employee', string='Employee', domain="['|', ('active', '=', True), ('active', '=', False)]")
    salary_rule_ids = fields.Many2many('hr.salary.rule', string='Salary Rules', domain="['|', ('active', '=', True), ('active', '=', False)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)

    def generate_xlsx_report(self):
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'flemings_base.fg_salary_summary_report_xlsx'
        }

    def _get_salary_summary_report_name(self):
        self.ensure_one()

        report_name = 'Salary Summary Report'
        if self and self.date_from and self.date_to:
            report_name += ' - ' + str(str(month_dict[str(self.date_from.month)]) + ' ' + str(self.date_from.year)[2:] + ' - ' + str(month_dict[str(self.date_to.month)]) + ' ' + str(self.date_to.year)[2:])

        return report_name


class FGGrossProfitReportXlsx(models.AbstractModel):
    _name = 'report.flemings_base.fg_salary_summary_report_xlsx'
    _description = 'Salary Summary Report XLSX'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('SALARY SUMMARY REPORT')

        align_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        align_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True})
        align_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        align_bold_left = workbook.add_format({'font_name': 'Arial', 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_right = workbook.add_format({'font_name': 'Arial', 'align': 'right', 'valign': 'vcenter', 'text_wrap': True, 'bold': True})
        align_bold_center = workbook.add_format({'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'bold': True, 'border': 1})

        row = 0
        for obj in objects:
            emp_domain = ['|', ('active', '=', True), ('active', '=', False)]
            if obj.employee_ids:
                emp_domain += [('id', 'in', obj.employee_ids.ids or [])]

            salary_rule_domain = ['|', ('salary_rule_id.active', '=', True), ('salary_rule_id.active', '=', False)]
            salary_rule_emp_domain = ['|', ('active', '=', True), ('active', '=', False)]
            if obj.salary_rule_ids:
                salary_rule_domain += [('salary_rule_id', 'in', obj.salary_rule_ids.ids or [])]
                salary_rule_emp_domain += [('id', 'in', obj.salary_rule_ids.ids or [])]

            employee_ids = self.env['hr.employee'].sudo().search(emp_domain, order='name')
            payslip_line_ids = self.env['hr.payslip.line'].sudo().search([
                ('slip_id.employee_id', 'in', employee_ids.ids or []), ('slip_id.date_from', '>=', obj.date_from), ('slip_id.date_from', '<=', obj.date_to)
            ] + salary_rule_domain)

            if payslip_line_ids:
                sheet.set_column('A:A', 40)
                sheet.set_column('B:CZ', 14)

                sheet.set_row(row, 35)
                sheet.set_row(row + 1, 18)
                sheet.set_row(row + 2, 18)
                sheet.set_row(row + 4, 18)

                sheet.merge_range(row, 0, row, 6, 'SALARY SUMMARY REPORT', workbook.add_format(
                    {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 18}))

                row += 1
                sheet.merge_range(row, 0, row, 6, str(obj.company_id.name).upper(), workbook.add_format(
                    {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 14}))

                row += 1
                sheet.merge_range(row, 0, row, 6, 'Period : ' + str(str(month_dict[str(obj.date_from.month)]) + ' ' + str(obj.date_from.year)[2:] + ' - ' + str(month_dict[str(obj.date_to.month)]) + ' ' + str(obj.date_to.year)[2:]), workbook.add_format(
                    {'font_name': 'Arial', 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_size': 11}))

                row += 2
                title_column = 0
                sheet.write(row, title_column, 'EMPLOYEE NAME', align_bold_center)

                start_date, end_date = obj.date_from, obj.date_to
                delta = relativedelta(months=+1)
                while start_date <= end_date:
                    title_column += 1
                    sheet.write(row, title_column, str(month_dict[str(start_date.month)]) + ' ' + str(start_date.year)[2:], align_bold_center)
                    start_date += delta

                title_column += 1
                sheet.write(row, title_column, 'TOTAL', align_bold_center)

                annual_leave_type_id = self.env['hr.leave.type'].sudo().search([('is_annual_leave', '=', True)], limit=1)

                remaining_leaves = []
                if annual_leave_type_id:
                    start_date, end_date = obj.date_from, obj.date_to
                    delta = relativedelta(months=+1)
                    while start_date <= end_date:
                        month_to_date = start_date + relativedelta(months=+1, day=1, days=-1)
                        remaining_leaves.append({
                            str(month_to_date): annual_leave_type_id.with_context(ignore_future=True).get_employees_days(employee_ids.ids, date=month_to_date)
                        })
                        start_date += delta

                for employee_id in employee_ids:
                    emp_payslip_line_ids = payslip_line_ids.filtered(lambda x: x.slip_id.employee_id.id == employee_id.id)
                    emp_rule_ids = self.env['hr.salary.rule'].sudo().search([
                        ('id', 'in', emp_payslip_line_ids.mapped('salary_rule_id').ids or [])
                    ] + salary_rule_emp_domain, order='sequence')

                    if emp_rule_ids:
                        row += 1
                        sheet.set_row(row, 18)
                        sheet.write(row, 0, str(employee_id.name).upper(), align_bold_left)

                        row += 1
                        emp_column = 0
                        sheet.write(row, emp_column, '   UNUSED LEAVE', align_left)

                        start_date, end_date = obj.date_from, obj.date_to
                        delta = relativedelta(months=+1)
                        while start_date <= end_date:
                            emp_column += 1
                            month_to_date = start_date + relativedelta(months=+1, day=1, days=-1)
                            if annual_leave_type_id:
                                leaves_dict = [i[str(month_to_date)] for i in remaining_leaves if str(month_to_date) in i]
                                sheet.write(row, emp_column, str((leaves_dict[0][employee_id.id][annual_leave_type_id.id].get('remaining_leaves', 0.0)) if leaves_dict else 0), align_right)
                            else:
                                sheet.write(row, emp_column, str(0), align_right)
                            start_date += delta

                        for emp_rule_id in emp_rule_ids:
                            emp_rule_total = 0
                            row += 1
                            emp_column = 0
                            if emp_rule_id.code == 'NET':
                                row += 1
                                sheet.set_row(row + 1, 18)
                            sheet.write(row + 1, emp_column, '   ' + str(emp_rule_id.name).upper(), align_bold_left if emp_rule_id.code == 'NET' else align_left)

                            start_date, end_date = obj.date_from, obj.date_to
                            delta = relativedelta(months=+1)
                            while start_date <= end_date:
                                emp_column += 1
                                month_from_date = start_date
                                month_to_date = start_date + relativedelta(months=+1, day=1, days=-1)

                                emp_specific_rule_ids = emp_payslip_line_ids.filtered(lambda x: x.salary_rule_id.id == emp_rule_id.id and x.slip_id.date_from >= month_from_date and x.slip_id.date_to <= month_to_date)
                                emp_rule_month_total = sum(emp_specific_rule_ids.mapped('total')) or 0
                                emp_rule_total += emp_rule_month_total

                                sheet.write(row + 1, emp_column, str(obj.company_id.currency_id.symbol or '') + ' ' + str('%.2f' % emp_rule_month_total), align_bold_right if emp_rule_id.code == 'NET' else align_right)
                                start_date += delta

                            emp_column += 1
                            sheet.write(row + 1, emp_column, str(obj.company_id.currency_id.symbol or '') + ' ' + str('%.2f' % emp_rule_total), align_bold_right)

                        row += 5

            else:
                raise UserError(_("No Record(s) found !"))
