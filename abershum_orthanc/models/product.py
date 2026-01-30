# -*- coding: utf-8 -*-
from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_radiology = fields.Boolean(string="Is Radiology Product", help="Check if this product is a radiology service.")
