# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    provider_id = fields.Many2one('abershum.provider', string='Provider', tracking=True)

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            for line in order.order_line:
                if line.product_id.is_radiology:
                    # Check for existing to avoid duplicates
                    existing = self.env['orthanc.order'].search([
                        ('sale_order_id', '=', order.id),
                        ('product_id', '=', line.product_id.id)
                    ], limit=1)
                    
                    if not existing:
                        orthanc_order = self.env['orthanc.order'].create({
                            'sale_order_id': order.id,
                            'product_id': line.product_id.id,
                        })
                        # Explicitly trigger the worklist creation
                        orthanc_order._send_to_orthanc()
        return res
                 
    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        for order in self:
            # OPTIMIZE: This could be done with a search on sale_order_id to handle all at once
            orthanc_orders = self.env['orthanc.order'].search([
                ('sale_order_id', '=', order.id),
                ('state', '!=', 'cancelled')
            ])
            for orthanc_order in orthanc_orders:
                orthanc_order.write({
                    'state': 'cancelled',
                    'cancel_reason': f"Sales Order {order.name} was cancelled."
                })
        return res
