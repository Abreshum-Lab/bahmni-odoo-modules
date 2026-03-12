import requests
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    provider_id = fields.Many2one('abershum.provider', string='Provider', tracking=True)
    radiology_priority = fields.Selection([
        ('stat', 'STAT'),
        ('urgent', 'URGENT'),
        ('scheduled', 'SCHEDULED')
    ], string='Radiology Priority', default='scheduled', tracking=True)

    test_results_data = fields.Text(string='Test Results Data', help='Stored JSON data from OpenELIS')

    def action_print_patient_result(self):
        """Fetch results from OpenELIS and print PDF"""
        self.ensure_one()
        
        # Get API configuration from the other module's parameters
        # (Assuming they share settings or we can read them)
        get_param = self.env['ir.config_parameter'].sudo().get_param
        api_url = get_param('abershum_elis_sync.openelis_api_url', '')
        api_username = get_param('abershum_elis_sync.openelis_api_username', '')
        api_password = get_param('abershum_elis_sync.openelis_api_password', '')

        if not api_url:
            raise UserError(_("OpenELIS API URL is not configured in Sync Settings."))

        if not api_url.startswith(('http://', 'https://')):
            api_url = 'http://' + api_url.lstrip('/')
        
        # Endpoint for fetching results for a specific sale order
        url = api_url.rstrip('/') + f'/rest/odoo/test-results/{self.id}'
        auth = (api_username, api_password) if api_username and api_password else None

        try:
            _logger.info("Fetching test results from OpenELIS: %s", url)
            response = requests.get(url, auth=auth, timeout=15, verify=False)
            
            if response.status_code == 200:
                results_data = response.json()
                # Store it as JSON string for the report to parse
                self.write({'test_results_data': json.dumps(results_data)})
                return self.env.ref('abreshum_orthanc.action_report_patient_result').report_action(self)
            else:
                error_msg = f"Failed to fetch results from OpenELIS. HTTP {response.status_code}: {response.text[:200]}"
                _logger.error(error_msg)
                raise UserError(_(error_msg))

        except Exception as e:
            _logger.error("Error calling OpenELIS API: %s", str(e))
            raise UserError(_("Connection error: %s") % str(e))

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
                            'radiologist_id': order.provider_id.id,
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
                ('state', '!=', 'cancel')
            ])
            for orthanc_order in orthanc_orders:
                orthanc_order.write({
                    'state': 'cancel',
                    'cancel_reason': f"Sales Order {order.name} was cancel."
                })
        return res
