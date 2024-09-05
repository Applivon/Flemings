/** @odoo-modules */

import {Order, Orderline, PosGlobalState} from 'point_of_sale.models';
import Registries from 'point_of_sale.Registries';


const OrderInherit = (Order) => class OrderInherit extends Order {
    // constructor() {
    //     super(...arguments);
    //     this.note=null
    //     this._initializePrograms({});
    //
    // //
    // }

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.note = this.note
        return json;
    }

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.note = json.note;
    }

    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.note = this.note;
        return result;
    }

    addOrderNote(note) {
        this.note = note;
    }
}

Registries.Model.extend(Order, OrderInherit);