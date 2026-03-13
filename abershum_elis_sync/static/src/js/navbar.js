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
        const urlParam = await this.rpc("/web/dataset/call_kw/ir.config_parameter/get_param", {
            model: 'ir.config_parameter',
            method: 'get_param',
            args: ['abershum_elis_sync.openelis_api_url', 'http://localhost/openelis'],
            kwargs: {},
        });

        let openelisUrl = urlParam || "http://localhost/openelis";
        // Strip /rest if present in URL
        openelisUrl = openelisUrl.split('/rest')[0];
        window.open(openelisUrl, '_blank');
    }
});
