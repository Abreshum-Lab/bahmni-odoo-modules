# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OpenELISSyncService(models.Model):
    _name = 'openelis.sync.service'
    _auto = False

    @api.model
    def sync_test_order_to_openelis(self, sale_order):
        """
        Sync test order from Odoo to OpenELIS when sale order is confirmed.
        
        :param sale_order: sale.order record
        :return: dict with status and message
        """
        # Check if sync is enabled
        if not self._is_sync_enabled():
            _logger.debug("OpenELIS sync is disabled, skipping sync for sale order: %s", sale_order.name)
            return {'status': 'skipped', 'message': 'OpenELIS sync is disabled'}

        # Filter lab test products
        lab_test_lines = self._get_lab_test_order_lines(sale_order)
        if not lab_test_lines:
            _logger.debug("No lab test products found in sale order: %s", sale_order.name)
            return {'status': 'skipped', 'message': 'No lab test products found'}

        try:
            # Build payload
            payload = self._build_payload(sale_order, lab_test_lines)
            
            # Call OpenELIS API (sale_order_id is already in context from sale_order.py)
            response = self._call_openelis_api(payload)
            
            if response.get('status') == 'success':
                _logger.info("Successfully synced sale order %s to OpenELIS", sale_order.name)
                return {'status': 'success', 'message': response.get('message', 'Synced successfully')}
            else:
                _logger.error("Failed to sync sale order %s to OpenELIS: %s", 
                             sale_order.name, response.get('message', 'Unknown error'))
                return {'status': 'error', 'message': response.get('message', 'Unknown error')}
                
        except Exception as e:
            _logger.error("Error syncing sale order %s to OpenELIS: %s", sale_order.name, str(e), exc_info=True)
            # Don't raise exception - just log and return error status
            return {'status': 'error', 'message': str(e)}

    @api.model
    def _is_sync_enabled(self):
        """Check if OpenELIS sync is enabled in configuration"""
        return bool(self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.enable_openelis_sync', False))

    @api.model
    def _get_lab_test_order_lines(self, sale_order):
        """
        Filter order lines that contain lab test products.
        Lab test products are identified by category: Services/Lab/Test or Services/Lab/Panel
        """
        lab_test_lines = []
        lab_test_category_ids = self._get_lab_test_category_ids()
        
        for line in sale_order.order_line:
            if line.display_type in ('line_section', 'line_note'):
                continue
            
            # Check if product category is Lab/Test or Lab/Panel
            if line.product_id and line.product_id.categ_id:
                if line.product_id.categ_id.id in lab_test_category_ids:
                    lab_test_lines.append(line)
        
        return lab_test_lines

    @api.model
    def _get_lab_test_category_ids(self):
        """Get category IDs for Lab/Test and Lab/Panel"""
        category_ids = []
        
        # Find "Test" category under Services/Lab
        test_category = self.env['product.category'].search([
            ('name', '=', 'Test'),
            ('parent_id.name', '=', 'Lab'),
            ('parent_id.parent_id.name', '=', 'Services')
        ], limit=1)
        if test_category:
            category_ids.append(test_category.id)
        
        # Find "Panel" category under Services/Lab
        panel_category = self.env['product.category'].search([
            ('name', '=', 'Panel'),
            ('parent_id.name', '=', 'Lab'),
            ('parent_id.parent_id.name', '=', 'Services')
        ], limit=1)
        if panel_category:
            category_ids.append(panel_category.id)
        
        return category_ids

    @api.model
    def _build_payload(self, sale_order, lab_test_lines):
        """Build JSON payload for OpenELIS API"""
        # Get patient info
        patient = sale_order.partner_id
        
        # Build patient object
        birthdate_str = ''
        if patient.birthdate:
            birthdate_str = patient.birthdate.isoformat()
        elif hasattr(patient, 'age') and patient.age and patient.age > 0:
            # Calculate birthdate from age if only age is provided
            from datetime import date
            today = date.today()
            birth_year = today.year - patient.age
            birthdate_str = date(birth_year, 1, 1).isoformat()
        
        patient_data = {
            'ref': patient.ref or '',
            'uuid': patient.uuid or '',
            'name': patient.name or '',
            'phone': patient.phone or '',
            'email': patient.email or '',
            'birthdate': birthdate_str,
            'gender': patient.gender or ''
        }
        
        # Build order lines
        order_lines = []
        for line in lab_test_lines:
            product = line.product_id
            product_type = 'Panel' if product.categ_id.name == 'Panel' else 'Test'
            
            order_line = {
                'product_uuid': product.uuid or '',
                'product_name': product.name or '',
                'product_type': product_type,
                'quantity': line.product_uom_qty or 1.0,
                'comment': line.name or ''
            }
            order_lines.append(order_line)
        
        # Build payload
        payload = {
            'sale_order_id': str(sale_order.id),
            'sale_order_name': sale_order.name or '',
            'order_date': sale_order.date_order.isoformat() if sale_order.date_order else '',
            'patient': patient_data,
            'order_lines': order_lines
        }
        
        return payload

    @api.model
    def _call_openelis_api(self, payload):
        """Call OpenELIS REST API"""
        _logger.info("=== Starting test order sync to OpenELIS ===")
        
        api_url = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.openelis_api_url', '')
        api_username = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.openelis_api_username', '')
        api_password = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.openelis_api_password', '')
        
        _logger.info("OpenELIS API Configuration:")
        _logger.info("  API URL (raw): %s", api_url or '(not configured)')
        _logger.info("  API Username: %s", api_username or '(not configured)')
        _logger.info("  API Password: %s", '***' if api_password else '(not configured)')
        
        if not api_url:
            error_msg = "OpenELIS API URL is not configured. Please configure it in Settings."
            _logger.error(error_msg)
            raise UserError(error_msg)
        
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
        url = base_url + '/rest/odoo/test-order'
        
        _logger.info("=== Request Details ===")
        _logger.info("Full URL: %s", url)
        _logger.info("Method: POST")
        _logger.info("Headers: Content-Type=application/json")
        _logger.info("Authentication: %s", "Basic Auth (username: %s)" % api_username if (api_username and api_password) else "None")
        _logger.info("Timeout: 30 seconds")
        _logger.info("SSL Verification: Disabled")
        _logger.info("Payload Summary:")
        _logger.info("  Sale Order ID: %s", payload.get('sale_order_id', 'N/A'))
        _logger.info("  Sale Order Name: %s", payload.get('sale_order_name', 'N/A'))
        _logger.info("  Patient: %s (ref: %s)", 
                    payload.get('patient', {}).get('name', 'N/A'),
                    payload.get('patient', {}).get('ref', 'N/A'))
        _logger.info("  Order Lines Count: %s", len(payload.get('order_lines', [])))
        
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
        try:
            _logger.info("Sending POST request to OpenELIS...")
            response = requests.post(
                url,
                json=payload,
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
                    _logger.info("✅ Test order synced successfully")
                    return result
                except ValueError:
                    _logger.info("Response Body (text): %s", response.text[:500])
                    _logger.info("✅ Test order synced successfully (no JSON response)")
                    return {'status': 'success', 'message': 'Test order processed successfully'}
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
                
                _logger.error("❌ Failed to sync test order: %s", error_message)
                
                # Store failed event - need to get sale_order from context or payload
                sale_order_id = self.env.context.get('sale_order_id')
                if not sale_order_id and 'sale_order_id' in payload:
                    sale_order_id = self.env['sale.order'].browse(payload['sale_order_id'])
                elif not sale_order_id:
                    # Try to find by name
                    sale_order_name = payload.get('sale_order_name')
                    if sale_order_name:
                        sale_order_id = self.env['sale.order'].search([('name', '=', sale_order_name)], limit=1)
                
                self.env['openelis.failed.event'].create_or_update_failed_event(
                    event_type='test_order',
                    payload_dict=payload,
                    error_message=error_message,
                    error_type=error_type,
                    sale_order_id=sale_order_id if sale_order_id else None,
                )
                
                return {'status': 'error', 'message': error_message}
                
        except requests.exceptions.ConnectionError as e:
            error_msg = str(e)
            error_type = "ConnectionError"
            _logger.error("=== Connection Error ===")
            _logger.error("Failed to connect to OpenELIS API")
            _logger.error("Error Type: ConnectionError")
            _logger.error("Error Message: %s", error_msg)
            _logger.error("URL Attempted: %s", url)
            _logger.error("This usually means:")
            _logger.error("  1. OpenELIS service is not running")
            _logger.error("  2. Incorrect host/port in API URL")
            _logger.error("  3. Network connectivity issue between Odoo and OpenELIS containers")
            _logger.error("  4. Firewall blocking the connection")
            
            # Store failed event
            sale_order_id = self.env.context.get('sale_order_id')
            if not sale_order_id and 'sale_order_id' in payload:
                sale_order_id = self.env['sale.order'].browse(payload['sale_order_id'])
            elif not sale_order_id:
                sale_order_name = payload.get('sale_order_name')
                if sale_order_name:
                    sale_order_id = self.env['sale.order'].search([('name', '=', sale_order_name)], limit=1)
            
            self.env['openelis.failed.event'].create_or_update_failed_event(
                event_type='test_order',
                payload_dict=payload,
                error_message=error_msg,
                error_type=error_type,
                sale_order_id=sale_order_id if sale_order_id else None,
            )
            
            raise UserError(f"Failed to connect to OpenELIS API: {error_msg}")
        except requests.exceptions.Timeout as e:
            error_msg = str(e)
            error_type = "Timeout"
            _logger.error("=== Timeout Error ===")
            _logger.error("Request to OpenELIS API timed out")
            _logger.error("Error Type: Timeout")
            _logger.error("Error Message: %s", error_msg)
            _logger.error("URL Attempted: %s", url)
            _logger.error("Timeout: 30 seconds")
            
            # Store failed event
            sale_order_id = self.env.context.get('sale_order_id')
            if not sale_order_id and 'sale_order_id' in payload:
                sale_order_id = self.env['sale.order'].browse(payload['sale_order_id'])
            elif not sale_order_id:
                sale_order_name = payload.get('sale_order_name')
                if sale_order_name:
                    sale_order_id = self.env['sale.order'].search([('name', '=', sale_order_name)], limit=1)
            
            self.env['openelis.failed.event'].create_or_update_failed_event(
                event_type='test_order',
                payload_dict=payload,
                error_message=error_msg,
                error_type=error_type,
                sale_order_id=sale_order_id if sale_order_id else None,
            )
            
            raise UserError(f"Request to OpenELIS API timed out: {error_msg}")
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            error_type = type(e).__name__
            _logger.error("=== Request Exception ===")
            _logger.error("Failed to connect to OpenELIS API")
            _logger.error("Error Type: %s", error_type)
            _logger.error("Error Message: %s", error_msg)
            _logger.error("URL Attempted: %s", url)
            
            # Store failed event
            sale_order_id = self.env.context.get('sale_order_id')
            if not sale_order_id and 'sale_order_id' in payload:
                sale_order_id = self.env['sale.order'].browse(payload['sale_order_id'])
            elif not sale_order_id:
                sale_order_name = payload.get('sale_order_name')
                if sale_order_name:
                    sale_order_id = self.env['sale.order'].search([('name', '=', sale_order_name)], limit=1)
            
            self.env['openelis.failed.event'].create_or_update_failed_event(
                event_type='test_order',
                payload_dict=payload,
                error_message=error_msg,
                error_type=error_type,
                sale_order_id=sale_order_id if sale_order_id else None,
            )
            
            raise UserError(f"Failed to connect to OpenELIS API: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            _logger.error("=== Unexpected Error ===")
            _logger.error("Unexpected error syncing test order to OpenELIS")
            _logger.error("Error Type: %s", error_type)
            _logger.error("Error Message: %s", error_msg)
            _logger.error("Full traceback:", exc_info=True)
            
            # Store failed event
            sale_order_id = self.env.context.get('sale_order_id')
            if not sale_order_id and 'sale_order_id' in payload:
                sale_order_id = self.env['sale.order'].browse(payload['sale_order_id'])
            elif not sale_order_id:
                sale_order_name = payload.get('sale_order_name')
                if sale_order_name:
                    sale_order_id = self.env['sale.order'].search([('name', '=', sale_order_name)], limit=1)
            
            self.env['openelis.failed.event'].create_or_update_failed_event(
                event_type='test_order',
                payload_dict=payload,
                error_message=error_msg,
                error_type=error_type,
                sale_order_id=sale_order_id if sale_order_id else None,
            )
            
            raise
        finally:
            _logger.info("=== Test order sync attempt completed ===")
