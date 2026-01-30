# -*- coding: utf-8 -*-
import logging
import requests
from datetime import date, datetime
from odoo import models, api, fields
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

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

    @api.depends('birthdate')
    def _compute_age(self):
        """Calculate age from birthdate"""
        # Skip if we're in inverse method to prevent recursion
        if self.env.context.get('skip_compute_age'):
            # Still need to set a value, so keep current age if exists
            return
            
        today = date.today()
        for partner in self:
            if partner.birthdate:
                try:
                    # Calculate age in years
                    age = today.year - partner.birthdate.year
                    # Adjust if birthday hasn't occurred this year
                    if today.month < partner.birthdate.month or \
                       (today.month == partner.birthdate.month and today.day < partner.birthdate.day):
                        age -= 1
                    partner.age = max(0, age)
                except (AttributeError, TypeError):
                    # Handle any date parsing issues gracefully
                    partner.age = 0
            else:
                # Only set age to 0 if birthdate is not set
                if not partner.birthdate:
                    partner.age = 0

    def _inverse_age(self):
        """Calculate birthdate from age - only when age is explicitly set by user"""
        # Use context to prevent recursion
        if self.env.context.get('skip_inverse_age'):
            return
            
        today = date.today()
        for partner in self:
            if partner.age and partner.age > 0:
                try:
                    # Calculate what birthdate would be for this age
                    birth_year = today.year - partner.age
                    if birth_year > today.year:
                        birth_year = today.year
                    new_birthdate = date(birth_year, 1, 1)
                    
                    # Only update if birthdate is not set or would be different
                    # Use context to prevent triggering compute_age
                    if not partner.birthdate or partner.birthdate != new_birthdate:
                        partner.with_context(skip_compute_age=True).birthdate = new_birthdate
                except (ValueError, TypeError):
                    # Handle any calculation errors gracefully
                    pass

    @api.constrains('birthdate', 'age', 'customer_rank', 'gender')
    def _check_birthdate_or_age(self):
        """Validate that birthdate or age is provided for customers"""
        for partner in self:
            if partner.customer_rank > 0 and not partner.is_company:
                # Check if either birthdate or age is provided
                has_birthdate = partner.birthdate is not False and partner.birthdate is not None
                has_age = partner.age and partner.age > 0
                
                if not has_birthdate and not has_age:
                    raise ValidationError(
                        'For customers/patients, either Date of Birth or Age must be provided. '
                        'OpenELIS requires this information.'
                    )

    @api.model
    def create(self, vals):
        """
        Auto-generate patient ID (ref) when creating a customer/patient.
        Only generate if:
        - ref is not provided
        - customer_rank > 0 (is a customer)
        """
        # Only auto-generate for customers
        if vals.get('customer_rank', 0) > 0 and not vals.get('ref'):
            # Generate patient ID using sequence
            try:
                sequence_code = 'abershum.patient.id.sequence'
                patient_id = self.env['ir.sequence'].next_by_code(sequence_code)
                if patient_id:
                    vals['ref'] = patient_id
                    _logger.info("Auto-generated patient ID: %s for customer: %s", patient_id, vals.get('name', 'Unknown'))
                else:
                    _logger.warning("Failed to generate patient ID sequence. Sequence '%s' may not exist.", sequence_code)
            except Exception as e:
                _logger.error("Error generating patient ID: %s", str(e), exc_info=True)
                # Don't fail customer creation if sequence generation fails
                # Just log the error
        
        # Create the partner
        partner = super(ResPartner, self).create(vals)
        
        # Sync patient to OpenELIS if enabled and ref was generated
        if partner.ref and partner.customer_rank > 0:
            try:
                self._sync_patient_to_openelis(partner)
            except Exception as e:
                _logger.error("Error syncing patient %s to OpenELIS: %s", partner.name, str(e), exc_info=True)
                # Don't fail customer creation if sync fails
        
        return partner

    def write(self, vals):
        """
        Sync patient updates to OpenELIS if ref or other relevant fields change.
        """
        result = super(ResPartner, self).write(vals)
        
        # Sync to OpenELIS if relevant fields changed and this is a customer
        if any(field in vals for field in ['ref', 'name', 'phone', 'email', 'uuid', 'birthdate', 'age', 'gender']) and self.customer_rank > 0:
            for partner in self:
                if partner.ref:  # Only sync if ref exists
                    try:
                        self._sync_patient_to_openelis(partner)
                    except Exception as e:
                        _logger.error("Error syncing patient %s to OpenELIS: %s", partner.name, str(e), exc_info=True)
        
        return result

    @api.model
    def _sync_patient_to_openelis(self, partner):
        """
        Sync patient data to OpenELIS.
        This creates/updates patient in OpenELIS when customer is created/updated in Odoo.
        """
        _logger.info("=== Starting patient sync to OpenELIS ===")
        _logger.info("Patient: ref=%s, name=%s, uuid=%s", partner.ref, partner.name, partner.uuid or 'N/A')
        
        # Check if patient sync is enabled
        sync_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'abershum_elis_sync.enable_patient_sync', 
            False
        )
        
        _logger.info("Patient sync enabled: %s", sync_enabled)
        
        if not sync_enabled:
            _logger.debug("Patient sync to OpenELIS is disabled, skipping sync for patient: %s", partner.ref)
            return
        
        # Get OpenELIS API configuration
        api_url = self.env['ir.config_parameter'].sudo().get_param(
            'abershum_elis_sync.openelis_api_url', 
            ''
        )
        api_username = self.env['ir.config_parameter'].sudo().get_param(
            'abershum_elis_sync.openelis_api_username', 
            ''
        )
        api_password = self.env['ir.config_parameter'].sudo().get_param(
            'abershum_elis_sync.openelis_api_password', 
            ''
        )
        
        _logger.info("OpenELIS API Configuration:")
        _logger.info("  API URL (raw): %s", api_url or '(not configured)')
        _logger.info("  API Username: %s", api_username or '(not configured)')
        _logger.info("  API Password: %s", '***' if api_password else '(not configured)')
        
        if not api_url:
            _logger.warning("OpenELIS API URL is not configured. Cannot sync patient: %s", partner.ref)
            return
        
        # Build patient payload
        birthdate_str = ''
        if partner.birthdate:
            birthdate_str = partner.birthdate.isoformat()
        elif partner.age and partner.age > 0:
            # Calculate birthdate from age if only age is provided
            today = date.today()
            birth_year = today.year - partner.age
            birthdate_str = date(birth_year, 1, 1).isoformat()
        
        patient_data = {
            'ref': partner.ref or '',
            'uuid': partner.uuid or '',
            'name': partner.name or '',
            'phone': partner.phone or '',
            'email': partner.email or '',
            'birthdate': birthdate_str,
            'gender': partner.gender or ''
        }
        
        # Call OpenELIS patient sync endpoint
        try:
            # Normalize API URL - ensure it has http:// or https:// scheme
            original_url = api_url
            if not api_url.startswith(('http://', 'https://')):
                # If no scheme provided, default to http://
                api_url = 'http://' + api_url.lstrip('/')
                _logger.info("URL scheme normalized: '%s' -> '%s'", original_url, api_url)
            
            # For Docker internal communication, replace localhost with service name
            # Check if we're likely in Docker (common indicators)
            import socket
            is_docker = False
            try:
                # Try to resolve 'openelis' hostname - if it works, we're in Docker network
                socket.gethostbyname('openelis')
                is_docker = True
                _logger.info("Detected Docker network - 'openelis' hostname is resolvable")
            except socket.gaierror:
                _logger.info("Not in Docker network or 'openelis' hostname not resolvable")
            
            # If URL contains localhost and we're in Docker, replace with service name
            if is_docker and 'localhost' in api_url.lower():
                # Replace localhost with openelis service name
                if 'https://localhost' in api_url.lower():
                    api_url = api_url.replace('https://localhost', 'http://openelis:8052')
                    _logger.info("Replaced localhost with Docker service name: '%s'", api_url)
                elif 'http://localhost' in api_url.lower():
                    api_url = api_url.replace('http://localhost', 'http://openelis:8052')
                    _logger.info("Replaced localhost with Docker service name: '%s'", api_url)
                # Also handle localhost with port
                import re
                api_url = re.sub(r'localhost(:\d+)?', 'openelis:8052', api_url, flags=re.IGNORECASE)
                _logger.info("Final normalized URL: '%s'", api_url)
            
            # Prepare request URL
            base_url = api_url.rstrip('/')
            url = base_url + '/rest/odoo/patient'
            
            _logger.info("=== Request Details ===")
            _logger.info("Full URL: %s", url)
            _logger.info("Method: POST")
            _logger.info("Headers: Content-Type=application/json")
            _logger.info("Authentication: %s", "Basic Auth (username: %s)" % api_username if (api_username and api_password) else "None")
            _logger.info("Timeout: 30 seconds")
            _logger.info("SSL Verification: Disabled")
            _logger.info("Patient Data Payload:")
            _logger.info("  ref: %s", patient_data.get('ref', 'N/A'))
            _logger.info("  uuid: %s", patient_data.get('uuid', 'N/A'))
            _logger.info("  name: %s", patient_data.get('name', 'N/A'))
            _logger.info("  phone: %s", patient_data.get('phone', 'N/A'))
            _logger.info("  email: %s", patient_data.get('email', 'N/A'))
            _logger.info("  birthdate: %s", patient_data.get('birthdate', 'N/A'))
            _logger.info("  gender: %s", patient_data.get('gender', 'N/A'))
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Add authentication if provided
            auth = None
            if api_username and api_password:
                auth = (api_username, api_password)
                _logger.debug("Using Basic Authentication with username: %s", api_username)
            else:
                _logger.warning("No authentication credentials provided - request may fail if OpenELIS requires auth")
            
            # Make request
            _logger.info("Sending POST request to OpenELIS...")
            response = requests.post(
                url,
                json=patient_data,
                headers=headers,
                auth=auth,
                timeout=30,
                verify=False  # Disable SSL verification for internal Docker network
            )
            
            _logger.info("=== Response Details ===")
            _logger.info("Status Code: %s", response.status_code)
            _logger.info("Response Headers: %s", dict(response.headers))
            
            # Check response
            if response.status_code == 200:
                try:
                    result = response.json()
                    _logger.info("Response Body (JSON): %s", result)
                    if result.get('status') == 'success':
                        _logger.info("✅ Successfully synced patient %s (%s) to OpenELIS", 
                                    partner.ref, partner.name)
                    else:
                        _logger.warning("⚠️ OpenELIS returned error for patient %s: %s", 
                                       partner.ref, result.get('message', 'Unknown error'))
                except ValueError:
                    _logger.info("Response Body (text): %s", response.text[:500])
                    _logger.info("✅ Patient %s (%s) synced to OpenELIS (no JSON response)", 
                               partner.ref, partner.name)
            else:
                error_message = f"HTTP {response.status_code}"
                error_type = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', error_message)
                    _logger.error("Response Body (JSON): %s", error_data)
                except ValueError:
                    error_message = response.text or error_message
                    _logger.error("Response Body (text): %s", response.text[:500] if response.text else '(empty)')
                
                _logger.error("❌ Failed to sync patient %s to OpenELIS: %s", 
                            partner.ref, error_message)
                # Store failed event
                self.env['openelis.failed.event'].create_or_update_failed_event(
                    event_type='patient',
                    payload_dict=patient_data,
                    error_message=error_message,
                    error_type=error_type,
                    partner_id=partner,
                    partner_ref=partner.ref
                )
                
        except requests.exceptions.ConnectionError as e:
            error_msg = str(e)
            error_type = "ConnectionError"
            _logger.error("=== Connection Error ===")
            _logger.error("Failed to connect to OpenELIS API for patient %s", partner.ref)
            _logger.error("Error Type: ConnectionError")
            _logger.error("Error Message: %s", error_msg)
            _logger.error("URL Attempted: %s", url if 'url' in locals() else 'N/A (URL construction failed)')
            _logger.error("This usually means:")
            _logger.error("  1. OpenELIS service is not running")
            _logger.error("  2. Incorrect host/port in API URL")
            _logger.error("  3. Network connectivity issue between Odoo and OpenELIS containers")
            _logger.error("  4. Firewall blocking the connection")
            # Store failed event
            self.env['openelis.failed.event'].create_or_update_failed_event(
                event_type='patient',
                payload_dict=patient_data,
                error_message=error_msg,
                error_type=error_type,
                partner_id=partner,
                partner_ref=partner.ref
            )
        except requests.exceptions.Timeout as e:
            error_msg = str(e)
            error_type = "Timeout"
            _logger.error("=== Timeout Error ===")
            _logger.error("Request to OpenELIS API timed out for patient %s", partner.ref)
            _logger.error("Error Type: Timeout")
            _logger.error("Error Message: %s", error_msg)
            _logger.error("URL Attempted: %s", url if 'url' in locals() else 'N/A')
            _logger.error("Timeout: 30 seconds")
            # Store failed event
            self.env['openelis.failed.event'].create_or_update_failed_event(
                event_type='patient',
                payload_dict=patient_data,
                error_message=error_msg,
                error_type=error_type,
                partner_id=partner,
                partner_ref=partner.ref
            )
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            error_type = type(e).__name__
            _logger.error("=== Request Exception ===")
            _logger.error("Failed to connect to OpenELIS API for patient %s", partner.ref)
            _logger.error("Error Type: %s", error_type)
            _logger.error("Error Message: %s", error_msg)
            _logger.error("URL Attempted: %s", url if 'url' in locals() else 'N/A')
            # Store failed event
            self.env['openelis.failed.event'].create_or_update_failed_event(
                event_type='patient',
                payload_dict=patient_data,
                error_message=error_msg,
                error_type=error_type,
                partner_id=partner,
                partner_ref=partner.ref
            )
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            _logger.error("=== Unexpected Error ===")
            _logger.error("Unexpected error syncing patient %s to OpenELIS", partner.ref)
            _logger.error("Error Type: %s", error_type)
            _logger.error("Error Message: %s", error_msg)
            _logger.error("URL Attempted: %s", url if 'url' in locals() else 'N/A')
            _logger.error("Full traceback:", exc_info=True)
            # Store failed event
            self.env['openelis.failed.event'].create_or_update_failed_event(
                event_type='patient',
                payload_dict=patient_data,
                error_message=error_msg,
                error_type=error_type,
                partner_id=partner,
                partner_ref=partner.ref
            )
        finally:
            _logger.info("=== Patient sync attempt completed ===")
