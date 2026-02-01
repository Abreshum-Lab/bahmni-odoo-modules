# -*- coding: utf-8 -*-
from odoo import models, fields

class AbershumProvider(models.Model):
    _name = 'abershum.provider'
    _description = 'Radiology Provider'
    _order = 'name'

    name = fields.Char(string='Name', required=True, tracking=True)
    title = fields.Selection([
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('radiologist', 'Radiologist'),
        ('technician', 'Technician'),
        ('physician_assistant', 'Physician Assistant'),
        ('other', 'Other'),
    ], string='Title', required=True, default='doctor', tracking=True)
    license_number = fields.Char(string='License Number', tracking=True)
    active = fields.Boolean(default=True, help="Set to False to archive this provider.")
