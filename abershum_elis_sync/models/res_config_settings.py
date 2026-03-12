# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"
    
    # OpenELIS Integration Settings
    enable_openelis_sync = fields.Boolean(
        string="Enable OpenELIS Sync", 
        config_parameter="abershum_elis_sync.enable_openelis_sync",
        help="Enable automatic sync of patient and lab test data to OpenELIS"
    )
    openelis_api_url = fields.Char(
        string="OpenELIS API URL", 
        config_parameter="abershum_elis_sync.openelis_api_url",
        help="Base URL for OpenELIS REST API (e.g., http://openelis:8080/openelis)"
    )
    openelis_api_username = fields.Char(
        string="OpenELIS API Username", 
        config_parameter="abershum_elis_sync.openelis_api_username",
        help="Username for OpenELIS API authentication"
    )
    openelis_api_password = fields.Char(
        string="OpenELIS API Password",
        config_parameter='abershum_elis_sync.openelis_api_password',
        help="Password for OpenELIS API authentication"
    )

    def action_pull_lab_catalog(self):
        """Trigger catalog pull from OpenELIS and show notification"""
        res = self.env['openelis.sync.service'].pull_catalog_from_openelis()
        
        notification_type = 'success' if res.get('status') == 'success' else 'danger'
        title = _('Abershum Lab Sync') if res.get('status') == 'success' else _('Sync Error')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': res.get('message'),
                'sticky': False,
                'type': notification_type,
            }
        }
