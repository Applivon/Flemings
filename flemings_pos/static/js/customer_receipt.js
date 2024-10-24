// static/src/js/customer_receipt.js
odoo.define('flemings_pos.customer_receipt', function(require) {
    'use strict';
    const PosComponent = require('point_of_sale.PosComponent');
    const { useListener } = require("@web/core/utils/hooks");
    const { patch } = require( "@web/core/utils/patch");
    class CustomReceipt extends PosComponent {
        setup() {
            super.setup();
            useListener('click', this.onPrintReceipt);
        }
        async onPrintReceipt() {
            const orderId = this.env.pos.get_order().id;
            const reportUrl = '/report/pdf/flemings_pos.report_pos_customer_receipt_document/${orderId}';
            window.open(reportUrl, '_blank');
        }
    }

    patch(PosComponent.prototype, 'flemings_pos.CustomReceipt', CustomReceipt);
})