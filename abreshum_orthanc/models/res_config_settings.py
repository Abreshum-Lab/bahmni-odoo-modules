# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    orthanc_api_url = fields.Char(string="Orthanc API URL", config_parameter='abreshum_orthanc.orthanc_api_url', help="URL of the Orthanc server (e.g., http://localhost:8042)")
    orthanc_username = fields.Char(string="Orthanc Username", config_parameter='abreshum_orthanc.orthanc_username')
    orthanc_password = fields.Char(string="Orthanc Password", config_parameter='abreshum_orthanc.orthanc_password')
