odoo.define('point_of_sale.OrderNoteButton', function (require) {
    'use strict';

    const PosComponent = require('point_of_sale.PosComponent');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const {useListener} = require("@web/core/utils/hooks");
    const Registries = require('point_of_sale.Registries');

    class OrderNoteButton extends PosComponent {
        setup() {
            super.setup();
            useListener('click', this.onClick);
        }

        async onClick() {
            const currentPosOrder = this.env.pos.get_order()
            if (!currentPosOrder) return;
            const {confirmed, payload: inputNote} = await this.showPopup('TextAreaPopup', {
                startingValue: currentPosOrder.note,
                title: this.env._t('Add Customer Note'),
            });

            if (confirmed) {
                currentPosOrder.addOrderNote(inputNote);
            }
        }
    }

    OrderNoteButton.template = 'OrderNoteButton';

    ProductScreen.addControlButton({
        component: OrderNoteButton,
    });

    Registries.Component.add(OrderNoteButton);

    return OrderNoteButton;
});
