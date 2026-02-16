# -*- coding: utf-8 -*-
import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_lab_test = fields.Boolean(
        string='Is Lab Test',
        default=False,
        help='Mark this if the product is a lab test that should sync to OpenELIS'
    )
    elis_department = fields.Char(
        string='OpenELIS Department/Section',
        help='The Test Section in OpenELIS this test belongs to'
    )
    elis_sample_type = fields.Char(
        string='OpenELIS Sample Type',
        help='Default sample type for this test in OpenELIS'
    )
    elis_result_type = fields.Selection([
        ('numerical', 'Numerical'),
        ('text', 'Text'),
        ('coded', 'Coded')
    ], string='OpenELIS Result Type', default='text')
    elis_uom = fields.Char(
        string='OpenELIS Unit of Measure',
        help='Unit of measure recognized by OpenELIS'
    )
    elis_reference_range = fields.Text(
        string='OpenELIS Reference Range',
        help='Reference range information for the test'
    )
    elis_loinc = fields.Char(
        string='LOINC Code',
        help='LOINC code for this test'
    )
    elis_sort_order = fields.Integer(
        string='Sort Order',
        default=0,
        help='Sort order for display in OpenELIS'
    )
    is_panel = fields.Boolean(
        string='Is Lab Panel',
        default=False,
        help='Mark this if the product is a grouping of other lab tests'
    )
    panel_test_ids = fields.Many2many(
        'product.template',
        'product_panel_rel',
        'panel_id',
        'test_id',
        string='Panel Tests',
        domain=[('is_lab_test', '=', True), ('is_panel', '=', False)],
        help='Select the individual lab tests that make up this panel'
    )

    @api.onchange('is_lab_test')
    def _onchange_is_lab_test(self):
        if self.is_lab_test:
            self.detailed_type = 'service'

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
        # Check if any relevant fields changed
        relevant_fields = [
            'name', 'default_code', 'description_sale', 'categ_id', 'active', 'list_price',
            'is_lab_test', 'elis_department', 'elis_sample_type', 'elis_result_type', 
            'elis_uom', 'elis_reference_range', 'elis_loinc', 'elis_sort_order',
            'is_panel', 'panel_test_ids'
        ]
        if any(field in vals for field in relevant_fields):
            for product in self:
                if self._is_lab_test(product):
                    try:
                        self.env['openelis.sync.service'].sync_lab_test_to_openelis(product)
                    except Exception as e:
                        _logger.error("Error triggering lab test sync for %s: %s", product.name, str(e))
        return result

    def _is_lab_test(self, product):
        """Check if product is marked as lab test or panel"""
        return product.is_lab_test or product.is_panel

    def action_sync_to_openelis(self):
        """Manual sync button action"""
        for product in self:
            if not self._is_lab_test(product):
                continue
            res = self.env['openelis.sync.service'].sync_lab_test_to_openelis(product)
            if res.get('status') == 'success':
                _logger.info("Manual sync successful for product: %s", product.name)
                _logger.warning("Manual sync failed for product: %s: %s", product.name, res.get('message'))


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_sync_to_openelis(self):
        """Manual sync button action from variant view - redirects to template sync"""
        # We must sync the template, not the variant, to ensure ID consistency
        # Iterate in case of multi-record action
        for product in self:
            product.product_tmpl_id.action_sync_to_openelis()
        return True
