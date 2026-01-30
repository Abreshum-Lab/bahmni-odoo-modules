# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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
