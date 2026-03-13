# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import UserError
import logging
import uuid

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    elis_uuid = fields.Char(
        string='ELIS UUID',
        readonly=True,
        copy=False,
        default=lambda self: str(uuid.uuid4()),
        help='Unique Identifier for OpenELIS sync'
    )

    def action_print_patient_result(self):
        """Forward request to OpenELIS for report generation"""
        self.ensure_one()
        
        get_param = self.env['ir.config_parameter'].sudo().get_param
        api_url = get_param('abershum_elis_sync.openelis_api_url', '')

        if not api_url:
            raise UserError(_("OpenELIS API URL is not configured in Sync Settings."))

        if not api_url.startswith(('http://', 'https://')):
            api_url = 'http://' + api_url.lstrip('/')
        
        # Use the REST-based bridge handler in OpenELIS
        url = api_url.rstrip('/') + f'/ws/rest/odoo-report/{self.elis_uuid}'
        
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_confirm(self):
        """Override to sync test orders to OpenELIS after confirmation"""
        res = super(SaleOrder, self).action_confirm()
        
        # Sync test orders to OpenELIS
        try:
            for order in self:
                # Pass sale_order_id in context for failed event tracking
                self.env['openelis.sync.service'].with_context(sale_order_id=order.id).sync_test_order_to_openelis(order)
        except Exception as e:
            _logger.error("Error syncing sale order to OpenELIS: %s", str(e), exc_info=True)
            # Don't block sale order confirmation if sync fails
        
        return res
