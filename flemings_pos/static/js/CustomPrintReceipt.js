odoo.define('flemings_pos.CustomPrintReceipt', function(require) {
    'use strict';
    const OrderReceipt = require('point_of_sale.ReceiptScreen');
    const Registries = require('point_of_sale.Registries');
    const CustomPrintReceipt = ReceiptScreen =>
        class extends ReceiptScreen {
            async printReceipt() {
                const currentOrder = this.currentOrder;
                const order_id = this.env.pos.validated_orders_name_server_id_map[currentOrder.get_name()]
                const reportUrl = '/report/pdf/get_flemings_pos_order/' + order_id.toString() ;
                window.open(reportUrl, '_blank');
            }
        };
    Registries.Component.extend(OrderReceipt, CustomPrintReceipt);
    return OrderReceipt;
});