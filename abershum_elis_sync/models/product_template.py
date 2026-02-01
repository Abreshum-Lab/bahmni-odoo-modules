# -*- coding: utf-8 -*-
import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def create(self, vals):
        product = super(ProductTemplate, self).create(vals)
        if self._is_lab_test(product):
            try:
                self.env['openelis.sync.service'].sync_lab_test_to_openelis(product)
            except Exception as e:
                _logger.error("Error triggering lab test sync for %s: %s", product.name, str(e))
        return product

    def write(self, vals):
        result = super(ProductTemplate, self).write(vals)
        relevant_fields = ['name', 'default_code', 'description_sale', 'categ_id', 'active', 'list_price']
        if any(field in vals for field in relevant_fields):
            for product in self:
                if self._is_lab_test(product):
                    try:
                        self.env['openelis.sync.service'].sync_lab_test_to_openelis(product)
                    except Exception as e:
                        _logger.error("Error triggering lab test sync for %s: %s", product.name, str(e))
        return result

    def _is_lab_test(self, product):
        """Check if product belongs to lab test categories"""
        # We need to use the sync service method to get category IDs
        sync_service = self.env['openelis.sync.service']
        lab_test_category_ids = sync_service._get_lab_test_category_ids()
        return product.categ_id.id in lab_test_category_ids

    def action_sync_to_openelis(self):
        """Manual sync button action"""
        for product in self:
            res = self.env['openelis.sync.service'].sync_lab_test_to_openelis(product)
            if res.get('status') == 'success':
                _logger.info("Manual sync successful for product: %s", product.name)
            else:
                _logger.warning("Manual sync failed for product: %s: %s", product.name, res.get('message'))
