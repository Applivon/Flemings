/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { ListController } from '@web/views/list/list_controller';
import { FormController } from '@web/views/form/form_controller';



import { useService } from "@web/core/utils/hooks";

//const { Component, onWillStart, useSubEnv, useEffect, useRef } = owl;

patch(ListController.prototype, "getActionMenuItems", {
        setup() {
	        var def = this._super(...arguments);
	        this.orm = useService("orm");
	        var self = this;
	        self.action_to_remove = [];
	        var def2 =  this.orm.call(
                    "access.management",
                    "get_remove_options",
                    ["",this.props.resModel], {}
                ).then(function (remove_options) {
                self.action_to_remove =  remove_options;
            })
            return Promise.all([def,def2]);
	    },
        getActionMenuItems() {
            var sup = this._super.apply(this, arguments);
            var self = this;
            if(sup){
                var menu_items = sup.other;
					if (self.action_to_remove && self.action_to_remove.length > 0){
	                    if(menu_items){
	                        self.action_to_remove.forEach(function(action) {
								
	                            menu_items = _.reject(menu_items, function (item) {
	                                return item.description === action;
	                            });
	                        });
	                    }
                }
                sup.other = menu_items;
            }
            return sup;
        }
});



patch(FormController.prototype, "getActionMenuItems", {
        setup() {
	        var def = this._super(...arguments);
	        this.orm = useService("orm");
	        var self = this;
	        self.action_to_remove = [];
	        var def2 =  this.orm.call(
                    "access.management",
                    "get_remove_options",
                    ["",this.props.resModel], {}
                ).then(function (remove_options) {
                self.action_to_remove =  remove_options;
            })
            return Promise.all([def,def2]);
	    },
        getActionMenuItems() {
            var sup = this._super.apply(this, arguments);
            var self = this;
            if(sup){
                var menu_items = sup.other;
					if (self.action_to_remove && self.action_to_remove.length > 0){
	                    if(menu_items){
	                        self.action_to_remove.forEach(function(action) {
								
	                            menu_items = _.reject(menu_items, function (item) {
	                                return item.description === action;
	                            });
	                        });
	                    }
                }
                sup.other = menu_items;
            }
            return sup;
        }
});
