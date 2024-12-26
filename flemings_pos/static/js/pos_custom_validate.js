
odoo.define('flemings_pos.pos_custom_validate', function (require) {
    "use strict";
    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const rpc = require('web.rpc');
    const Registries = require('point_of_sale.Registries');
    const CustomPaymentScreen = PaymentScreen => class extends PaymentScreen {
        async validateOrder(isForceValidate) {
            const order = this.currentOrder;
            const orderLines = order.get_orderlines().map(line => ({
                product_id: line.product.id,
                quantity: line.quantity,
            }));
            const insufficientProducts = await rpc.query({
                route: '/pos/check_stock',
                params: { order_lines: orderLines },
            });

            if (insufficientProducts.length > 0) {
                const productNames = insufficientProducts.map(p => `${p.count}. [${p.default_code}] ${p.product_name}`).join('\n');
                debugger;
                this.showPopup('ErrorPopup', {
                    title: 'Insufficient Stock',
                    body: `No stock on hand available for the below products \n ${productNames}`,
                });
                return;
            }
            super.validateOrder(isForceValidate);
        }
    };

    Registries.Component.extend(PaymentScreen, CustomPaymentScreen);
    return CustomPaymentScreen;
});
