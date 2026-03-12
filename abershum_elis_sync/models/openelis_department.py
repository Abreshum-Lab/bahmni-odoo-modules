# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api

class OpenELISDepartment(models.Model):
    _name = 'openelis.department'
    _description = 'OpenELIS Department'

    name = fields.Char(string='Name', required=True)
    uuid = fields.Char(string='UUID', readonly=True, copy=False)

    @api.model
    def create(self, vals):
        if not vals.get('uuid'):
            vals['uuid'] = str(uuid.uuid4())
        return super(OpenELISDepartment, self).create(vals)
