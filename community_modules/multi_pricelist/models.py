# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Adding the missing field that caused the error.
    # Assuming it's a boolean config parameter or just a field.
    multi_pricelist = fields.Boolean(string="Multi Pricelists")
