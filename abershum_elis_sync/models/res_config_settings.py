# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"
    
    # OpenELIS Integration Settings
    enable_openelis_sync = fields.Boolean(
        string="Enable OpenELIS Test Order Sync", 
        config_parameter="abershum_elis_sync.enable_openelis_sync",
        help="Enable automatic sync of lab test orders to OpenELIS when sale orders are confirmed"
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
        config_parameter="abershum_elis_sync.openelis_api_password",
        help="Password for OpenELIS API authentication"
    )
    enable_patient_sync = fields.Boolean(
        string="Enable Patient Sync to OpenELIS",
        config_parameter="abershum_elis_sync.enable_patient_sync",
        help="Enable automatic sync of patient data to OpenELIS when customers are created or updated"
    )
