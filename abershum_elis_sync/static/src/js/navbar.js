/** @odoo-module **/

import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(NavBar.prototype, "abershum_elis_sync_navbar", {
    setup() {
        this._super();
        this.rpc = useService("rpc");
    },

    async onOpenElisClick() {
        const url = await this.rpc("/web/dataset/call_kw/res.config.settings/get_values", {
            model: 'res.config.settings',
            method: 'get_values',
            args: [],
            kwargs: {},
        });
        
        let openelisUrl = url.openelis_api_url || "http://localhost:8080/openelis";
        // Strip /rest if present in URL
        openelisUrl = openelisUrl.split('/rest')[0];
        window.open(openelisUrl, '_blank');
    }
});
