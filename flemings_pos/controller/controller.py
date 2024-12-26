from odoo.http import content_disposition, request
from odoo import http
from odoo.http import request

class FlemingReportController(http.Controller):

    @http.route(['/report/pdf/get_flemings_pos_order/<int:order_id>'], type='http', auth="user")
    def fleming_report_download(self, order_id, **post):
        report_id = request.env.ref('flemings_pos.print_report_pos_customer_receipt').sudo().id
        pdf = request.env.ref('flemings_pos.print_report_pos_customer_receipt').sudo()._render_qweb_pdf(report_id,order_id)[0]
        pos_id = request.env['pos.order'].sudo().browse(int(order_id))
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', content_disposition(f'Customer Receipt - '+str(pos_id.name)+'.pdf'))  # Đặt tên file tại đây
        ]
        return request.make_response(pdf, headers=pdfhttpheaders)
    @http.route('/pos/check_stock', type='json', auth='user')
    def check_stock(self, order_lines):
        insufficient_products = request.env['pos.order'].check_product_stock(order_lines)
        return insufficient_products