# -*- coding: utf-8 -*-

from odoo import fields, http, SUPERUSER_ID, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.addons.portal.controllers import portal


class CustomerPortal(portal.CustomerPortal):

    @http.route(['/my/orders/<int:order_id>'], type='http', auth="public", website=True)
    def portal_order_page(self, order_id, report_type=None, access_token=None, message=False, download=False, **kw):
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if report_type in ('html', 'pdf', 'text'):
            # return self._show_report(model=order_sudo, report_type=report_type, report_ref='sale.action_report_saleorder', download=download)
            return self._show_report(model=order_sudo, report_type=report_type, report_ref='flemings_base.print_report_fg_sales_order', download=download)

        if request.env.user.share and access_token:
            # If a public/portal user accesses the order with the access token
            # Log a note on the chatter.
            today = fields.Date.today().isoformat()
            session_obj_date = request.session.get('view_quote_%s' % order_sudo.id)
            if session_obj_date != today:
                # store the date as a string in the session to allow serialization
                request.session['view_quote_%s' % order_sudo.id] = today
                # The "Quotation viewed by customer" log note is an information
                # dedicated to the salesman and shouldn't be translated in the customer/website lgg
                context = {'lang': order_sudo.user_id.partner_id.lang or order_sudo.company_id.partner_id.lang}
                msg = _('Quotation viewed by customer %s',
                        order_sudo.partner_id.name if request.env.user._is_public() else request.env.user.partner_id.name)
                del context
                _message_post_helper(
                    "sale.order",
                    order_sudo.id,
                    message=msg,
                    token=order_sudo.access_token,
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                    partner_ids=order_sudo.user_id.sudo().partner_id.ids,
                )

        backend_url = f'/web#model={order_sudo._name}' \
                      f'&id={order_sudo.id}' \
                      f'&action={order_sudo._get_portal_return_action().id}' \
                      f'&view_type=form'
        values = {
            'sale_order': order_sudo,
            'message': message,
            'report_type': 'html',
            'backend_url': backend_url,
            'res_company': order_sudo.company_id,  # Used to display correct company logo
        }

        # Payment values
        if order_sudo._has_to_be_paid():
            values.update(self._get_payment_values(order_sudo))

        if order_sudo.state in ('draft', 'sent', 'cancel'):
            history_session_key = 'my_quotations_history'
        else:
            history_session_key = 'my_orders_history'

        values = self._get_page_view_values(
            order_sudo, access_token, values, history_session_key, False)

        return request.render('sale.sale_order_portal_template', values)

    # Update Download & Print button to Custom Report on Invoice Preview
    @http.route(['/my/invoices/<int:invoice_id>'], type='http', auth="public", website=True)
    def portal_my_invoice_detail(self, invoice_id, access_token=None, report_type=None, download=False, **kw):
        try:
            invoice_sudo = self._document_check_access('account.move', invoice_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if report_type in ('html', 'pdf', 'text'):
            # return self._show_report(model=invoice_sudo, report_type=report_type, report_ref='account.account_invoices', download=download)
            if invoice_sudo and invoice_sudo.move_type == 'out_refund':
                return self._show_report(model=invoice_sudo, report_type=report_type, report_ref='flemings_base.print_report_fg_credit_note', download=download)
            else:
                return self._show_report(model=invoice_sudo, report_type=report_type, report_ref='flemings_base.print_report_fg_tax_invoice', download=download)

        values = self._invoice_get_page_view_values(invoice_sudo, access_token, **kw)
        return request.render("account.portal_invoice_page", values)
