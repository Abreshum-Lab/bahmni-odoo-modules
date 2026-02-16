# -*- coding: utf-8 -*-
import logging
import requests
import uuid
import json
from datetime import date, datetime
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_patient = fields.Boolean(
        string='Is Patient',
        default=True,
        help='Check this box if this contact is a patient.'
    )
    uuid = fields.Char(
        string='UUID',
        readonly=True,
        copy=False,
        help='Unique Identifier for OpenELIS sync'
    )
    birthdate = fields.Date(
        string='Date of Birth',
        help='Patient date of birth. If age is entered, this will be calculated automatically.'
    )
    age = fields.Integer(
        string='Age (Years)',
        compute='_compute_age',
        inverse='_inverse_age',
        store=False,
        readonly=False,
        help='Patient age in years. If date of birth is entered, this will be calculated automatically. You can also enter age directly.'
    )
    gender = fields.Selection(
        [
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other')
        ],
        string='Gender',
        help='Patient gender'
    )
    primary_relative = fields.Char(
        string="Father's/Husband's Name",
        help="Name of the father or husband"
    )
    occupation = fields.Char(
        string='Occupation',
        help='Occupation of the patient'
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
        """Calculate age from birthdate"""
        if self.env.context.get('skip_compute_age'):
            return
            
        today = date.today()
        for partner in self:
            if partner.birthdate:
                try:
                    age = today.year - partner.birthdate.year
                    if today.month < partner.birthdate.month or \
                       (today.month == partner.birthdate.month and today.day < partner.birthdate.day):
                        age -= 1
                    partner.age = max(0, age)
                except (AttributeError, TypeError):
                    partner.age = 0
            else:
                if not partner.birthdate:
                    partner.age = 0

    def _inverse_age(self):
        """Calculate birthdate from age"""
        if self.env.context.get('skip_inverse_age'):
            return
            
        today = date.today()
        for partner in self:
            if partner.age and partner.age > 0:
                try:
                    birth_year = today.year - partner.age
                    new_birthdate = date(birth_year, 1, 1)
                    if not partner.birthdate or partner.birthdate != new_birthdate:
                        partner.with_context(skip_compute_age=True).birthdate = new_birthdate
                except (ValueError, TypeError):
                    pass

    @api.constrains('birthdate', 'age', 'is_patient', 'is_company')
    def _check_birthdate_or_age(self):
        """Validate that birthdate or age is provided for patients"""
        for partner in self:
            if partner.is_patient and not partner.is_company:
                has_birthdate = partner.birthdate is not False and partner.birthdate is not None
                has_age = partner.age and partner.age > 0
                if not has_birthdate and not has_age:
                    raise ValidationError(
                        'For patients, either Date of Birth or Age must be provided. '
                        'OpenELIS requires this information.'
                    )

    @api.model
    def create(self, vals):
        """Auto-generate patient ID and UUID"""
        if not vals.get('uuid'):
            vals['uuid'] = str(uuid.uuid4())
            
        if vals.get('is_patient') and not vals.get('is_company') and not vals.get('ref'):
            sequence_code = 'abershum.patient.id.sequence'
            patient_id = self.env['ir.sequence'].next_by_code(sequence_code)
            if patient_id:
                vals['ref'] = patient_id
        
        partner = super(ResPartner, self).create(vals)
        
        if partner.ref and partner.is_patient and not partner.is_company:
            try:
                self._sync_patient_to_openelis(partner)
            except Exception as e:
                _logger.error("Error syncing patient %s to OpenELIS: %s", partner.name, str(e))
        
        return partner

    def write(self, vals):
        """Sync updates and toggle patient ID generation"""
        if vals.get('is_patient'):
            for partner in self:
                if not partner.ref and not partner.is_company:
                    sequence_code = 'abershum.patient.id.sequence'
                    patient_id = self.env['ir.sequence'].next_by_code(sequence_code)
                    if patient_id:
                        partner.write({'ref': patient_id})

        result = super(ResPartner, self).write(vals)
        
        # Ensure UUID
        no_uuid_partners = self.filtered(lambda p: not p.uuid)
        if no_uuid_partners:
            import uuid
            for p in no_uuid_partners:
                p.write({'uuid': str(uuid.uuid4())})

        # Sync if relevant fields changed
        relevant_fields = [
            'ref', 'name', 'phone', 'email', 'uuid', 'birthdate', 'age', 'gender',
            'primary_relative', 'occupation', 'street', 'street2', 'city', 'zip', 'state_id', 'country_id', 'is_patient'
        ]
        if any(field in vals for field in relevant_fields):
            for partner in self:
                is_pat = vals.get('is_patient', partner.is_patient)
                is_comp = vals.get('is_company', partner.is_company)
                if partner.ref and is_pat and not is_comp:
                    try:
                        # Pass context to avoid resetting retry counters if this is triggered during a retry
                        self.with_context(is_retry=self.env.context.get('is_retry'))._sync_patient_to_openelis(partner)
                    except Exception as e:
                        _logger.error("Error syncing patient %s: %s", partner.name, str(e))
        
        return result

    @api.model
    def _sync_patient_to_openelis(self, partner):
        """
        Sync patient data to OpenELIS. Returns True on success, False on failure.
        """
        _logger.info(">>> OpenELIS Sync: Attempting patient sync for %s (ref: %s)", partner.name, partner.ref)
        
        # 1. Verification
        sync_enabled = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.enable_patient_sync', False)
        if not sync_enabled:
            _logger.debug("OpenELIS Sync: Disabled in settings.")
            return False
            
        api_url = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.openelis_api_url', '')
        if not api_url:
            _logger.warning("OpenELIS Sync: API URL not configured.")
            return False

        # 2. Build Payload
        birthdate_str = partner.birthdate.isoformat() if partner.birthdate else ''
        if not birthdate_str and partner.age:
            birth_year = date.today().year - partner.age
            birthdate_str = date(birth_year, 1, 1).isoformat()

        payload = {
            'ref': partner.ref or '',
            'uuid': partner.uuid or '',
            'name': partner.name or '',
            'phone': partner.phone or '',
            'email': partner.email or '',
            'birthdate': birthdate_str,
            'gender': partner.gender or '',
            'primary_relative': partner.primary_relative or '',
            'occupation': partner.occupation or '',
            'address': {
                'street': partner.street or '',
                'street2': partner.street2 or '',
                'city': partner.city or '',
                'zip': partner.zip or '',
                'state': partner.state_id.name or '',
                'country': partner.country_id.name or ''
            }
        }

        # 3. Request URL preparation
        if not api_url.startswith(('http://', 'https://')):
            api_url = 'http://' + api_url.lstrip('/')
            
        url = api_url.rstrip('/') + '/rest/odoo/patient'
        
        # 4. Auth
        api_username = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.openelis_api_username', '')
        api_password = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.openelis_api_password', '')
        auth = (api_username, api_password) if api_username and api_password else None

        # 5. Request
        try:
            _logger.info(">>> OpenELIS Sync: POST %s", url)
            response = requests.post(url, json=payload, auth=auth, timeout=15, verify=False)
            
            if response.status_code == 200:
                _logger.info(">>> OpenELIS Sync: Success (HTTP 200)")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                _logger.error(">>> OpenELIS Sync: Failed - %s", error_msg)
                if not self.env.context.get('is_retry'):
                    self._create_failed_event(partner, payload, error_msg, f"HTTP {response.status_code}")
                return False

        except Exception as e:
            error_msg = str(e)
            _logger.error(">>> OpenELIS Sync: Exception - %s", error_msg)
            if not self.env.context.get('is_retry'):
                self._create_failed_event(partner, payload, error_msg, type(e).__name__)
            return False

    @api.model
    def _create_failed_event(self, partner, payload, error_message, error_type):
        """Helper to create or update failed event"""
        self.env['openelis.failed.event'].sudo().create_or_update_failed_event(
            event_type='patient',
            payload_dict=payload,
            error_message=error_message,
            error_type=error_type,
            partner_id=partner,
            partner_ref=partner.ref
        )
