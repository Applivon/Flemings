from odoo import api, models
from functools import partial


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _order_fields(self, ui_order):
        result = super(PosOrder, self)._order_fields(ui_order)
        if ui_order.get('note'):
            result['note'] = ui_order['note']
        return result
