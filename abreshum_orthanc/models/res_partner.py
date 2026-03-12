# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Patient Identification
    ref = fields.Char(string='Reference', index=True, copy=False)
    uuid = fields.Char(
        string='UUID',
        readonly=True,
        copy=False,
        help='Unique Identifier'
    )

    # Demographics
    birthdate = fields.Date(string='Date of Birth')
    age = fields.Integer(
        string='Age (Years)',
        compute='_compute_age',
        inverse='_inverse_age',
        store=False,
        readonly=False
    )
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender')
    
    primary_relative = fields.Char(
        string="Father's/Husband's Name",
        help="Name of the father or husband"
    )
    occupation = fields.Char(
        string='Occupation',
        help='Occupation of the patient'
    )

    # Radiology specific fields
    is_patient = fields.Boolean(
        string='Is Patient', 
        default=True, 
        help="Check this box if this contact is a patient."
    )

    @api.onchange('is_company')
    def _onchange_is_company(self):
        """
        Automatically uncheck Is Patient if Company is selected.
        """
        if self.is_company:
            self.is_patient = False
        else:
            self.is_patient = True

    @api.depends('birthdate')
    def _compute_age(self):
        today = date.today()
        for partner in self:
            if partner.birthdate:
                born = partner.birthdate
                # Calculate age
                age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
                partner.age = max(0, age)
            else:
                partner.age = 0

    def _inverse_age(self):
        today = date.today()
        for partner in self:
            if partner.age and partner.age > 0:
                # Approximate birth year
                year = today.year - partner.age
                partner.birthdate = date(year, 1, 1)

    @api.model
    def create(self, vals):
        # Generate UUID if not present
        if not vals.get('uuid'):
            import uuid
            vals['uuid'] = str(uuid.uuid4())

        # Auto-generate Patient ID for patients (not companies)
        if vals.get('is_patient') and not vals.get('is_company') and not vals.get('ref'):
             # Using a dedicated sequence for patients
             sequence_code = 'abershum.patient.id.sequence'
             max_retries = 10
             for i in range(max_retries):
                try:
                    patient_id = self.env['ir.sequence'].next_by_code(sequence_code)
                    if not patient_id:
                        _logger.warning("Sequence '%s' returned empty value.", sequence_code)
                        break
                        
                    # Check if this ID already exists
                    existing = self.env['res.partner'].search([('ref', '=', patient_id)], count=True)
                    if not existing:
                        vals['ref'] = patient_id
                        break
                    else:
                        _logger.info("Generated Patient ID %s already exists, retrying... (%d/%d)", patient_id, i+1, max_retries)
                except Exception as e:
                     _logger.error("Error generating patient ID: %s", str(e), exc_info=True)
                     break

        return super(ResPartner, self).create(vals)

    def write(self, vals):
        # If toggling is_patient to True, generate Patient ID if none exists
        if vals.get('is_patient'):
            for partner in self:
                if not partner.ref and not partner.is_company:
                    try:
                        sequence_code = 'abershum.patient.id.sequence'
                        max_retries = 10
                        for i in range(max_retries):
                            patient_id = self.env['ir.sequence'].next_by_code(sequence_code)
                            if not patient_id:
                                break
                            
                            existing = self.env['res.partner'].search([('ref', '=', patient_id)], count=True)
                            if not existing:
                                partner.write({'ref': patient_id})
                                break
                    except Exception as e:
                        _logger.error("Error generating patient ID for write: %s", str(e), exc_info=True)
        
        # Ensure UUID
        if not vals.get('uuid'):
             for partner in self:
                if not partner.uuid:
                     import uuid
                     partner.write({'uuid': str(uuid.uuid4())})

        return super(ResPartner, self).write(vals)
