# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    birthdate = fields.Date(string='Date of Birth')
    ref = fields.Char(string='Reference', index=True, copy=False, default=lambda self: 'New')

    # Radiology specific fields
    is_patient = fields.Boolean(string='Is Patient', default=False, help="Check this box if this contact is a patient.")

    # Demographics
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender')
    age = fields.Integer(string='Age', compute='_compute_age', inverse='_inverse_age', store=False)


    @api.depends('birthdate')
    def _compute_age(self):
        today = date.today()
        for partner in self:
            if partner.birthdate:
                born = partner.birthdate
                partner.age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            else:
                partner.age = 0

    def _inverse_age(self):
        today = date.today()
        for partner in self:
            if partner.age:
                # Approximate birth year
                year = today.year - partner.age
                partner.birthdate = date(year, 1, 1)

    @api.model
    def create(self, vals):
        if not vals.get('ref'):
             # If no reference provided, generate one from sequence
             # Using a dedicated sequence for patients if needed, or default partner ref
             # Requirement: "incremental order id like ORD-00001" was for ORDERS.
             # "customer/patient needs to have a proper patient ID generation in place" -> implies similar.
             vals['ref'] = self.env['ir.sequence'].next_by_code('abershum.patient.id.sequence')
        return super(ResPartner, self).create(vals)
