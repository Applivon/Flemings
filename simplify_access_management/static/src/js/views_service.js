/** @odoo-module **/
import { viewService } from "@web/views/view_service";

viewService.start = function(env, { orm }){
    let cache = {};
    env.bus.on("CLEAR-CACHES", null, () => {
        cache = {};
        const processedArchs = registry.category("__processed_archs__");
        processedArchs.content = {};
        processedArchs.trigger("UPDATE");
    });

    /**
     * Loads various information concerning views: fields_view for each view,
     * fields of the corresponding model, and optionally the filters.
     *
     * @param {LoadViewsParams} params
     * @param {LoadViewsOptions} options
     * @returns {Promise<ViewDescriptions>}
     */
    async function loadViews(params, options) {
        const key = JSON.stringify([params.resModel, params.views, params.context, options]);
        if (!cache[key]) {
            cache[key] = orm
                .call(params.resModel, "get_views", [], {
                    views: params.views,
                    options: {
                        action_id: options.actionId || false,
                        load_filters: options.loadIrFilters || false,
                        toolbar: options.loadActionMenus || false,
                    },
                    context: params.context,
                })
                .then((result) => {
                    const viewDescriptions = {
                        __legacy__: result,
                    }; // for legacy purpose, keys in result are left in viewDescriptions

                    // Remove restricted views //
                    debugger
                    let views_to_load = params.views ;

                    params.views.forEach(element => {
                        const is_in  = _.contains(Object.keys(result.fields_views),element[1])
                        if(!is_in){
                            views_to_load = _.filter(views_to_load, function(elem) {
                                return elem[1] != element[1];
                            });
                        }
                    });
                    params.views = views_to_load;
                    for (const [, viewType] of params.views) {
                        const viewDescription = JSON.parse(
                            JSON.stringify(result.fields_views[viewType])
                        );
                        viewDescription.viewId = viewDescription.view_id;
                        delete viewDescription.view_id;
                        if (viewDescription.toolbar) {
                            viewDescription.actionMenus = viewDescription.toolbar;
                            delete viewDescription.toolbar;
                        }
                        viewDescription.fields = Object.assign(
                            {},
                            result.fields,
                            viewDescription.fields
                        ); // before a deep freeze was done.
                        delete viewDescription.base_model; // unused
                        delete viewDescription.field_parent; // unused
                        if (viewType === "search" && options.loadIrFilters) {
                            viewDescription.irFilters = result.filters;
                        }
                        viewDescriptions[viewType] = viewDescription;
                    }
                    return viewDescriptions;
                })
                .catch((error) => {
                    delete cache[key];
                    return Promise.reject(error);
                });
        }
        return cache[key];
    }
    return { loadViews };
}
