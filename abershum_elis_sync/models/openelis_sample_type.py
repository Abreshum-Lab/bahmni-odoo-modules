# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api

class OpenELISSampleType(models.Model):
    _name = 'openelis.sample.type'
    _description = 'OpenELIS Sample Type'

    name = fields.Char(string='Name', required=True)
    uuid = fields.Char(string='UUID', readonly=True, copy=False)

    @api.model
    def create(self, vals):
        if not vals.get('uuid'):
            vals['uuid'] = str(uuid.uuid4())
        return super(OpenELISSampleType, self).create(vals)
