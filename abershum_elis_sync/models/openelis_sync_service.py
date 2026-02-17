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
    def sync_lab_test_to_openelis(self, product):
        """
        Sync lab test (product) from Odoo to OpenELIS.
        
        :param product: product.template or product.product record
        :return: dict with status and message
        """
        if not product:
            return {'status': 'error', 'message': 'No product provided'}

        # Check if sync is enabled
        if not self._is_sync_enabled():
            _logger.debug("OpenELIS sync is disabled, skipping sync for product: %s", product.name)
            return {'status': 'skipped', 'message': 'OpenELIS sync is disabled'}

        # Check if product is a lab test or panel
        if not product.is_lab_test and not product.is_panel:
            _logger.debug("Product %s is not a lab test or panel, skipping sync", product.name)
            return {'status': 'skipped', 'message': 'Product is not a lab test or panel'}

        try:
            # Get component UUIDs for panels
            test_uuids = []
            if product.is_panel:
                test_uuids = [p.uuid for p in product.panel_test_ids if hasattr(p, 'uuid') and p.uuid]
                # Fallback to searching if UUID field name is different or missing
                if not test_uuids:
                    # In some Bahmni setups, UUID might be in a Different field or 
                    # we might need to use other identifiers. We'll use product.id as fallback 
                    # but OpenELIS expects UUIDs for linking.
                    test_uuids = [p.uuid for p in product.panel_test_ids if p.uuid]

            # Build payload
            payload = {
                'id': product.id,
                'name': product.name,
                'code': product.default_code or '',
                'description': product.description_sale or '',
                'category': product.categ_id.name,
                'active': product.active,
                'all_active': product.active, # Legacy support
                'list_price': product.list_price,
                # New OpenELIS fields
                'elis_department': product.elis_department or '',
                'elis_sample_type': product.elis_sample_type or '',
                'elis_result_type': product.elis_result_type or '',
                'elis_uom': product.elis_uom or '',
                'elis_reference_range': product.elis_reference_range or '',
                'elis_loinc': product.elis_loinc or '',
                'elis_sort_order': product.elis_sort_order or 0,
                # Panel fields
                'is_panel': product.is_panel,
                'test_uuids': test_uuids
            }
            
            # Call OpenELIS API
            response = self._call_openelis_api(payload, endpoint='/rest/odoo/test', event_type='lab_test')
            
            if response.get('status') == 'success':
                _logger.info("Successfully synced lab test %s to OpenELIS", product.name)
                return {'status': 'success', 'message': response.get('message', 'Synced successfully')}
            else:
                _logger.error("Failed to sync lab test %s to OpenELIS: %s", 
                             product.name, response.get('message', 'Unknown error'))
                return {'status': 'error', 'message': response.get('message', 'Unknown error')}
                
        except Exception as e:
            _logger.error("Error syncing lab test %s to OpenELIS: %s", product.name, str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @api.model
    def sync_test_order_to_openelis(self, sale_order):
        """
        Sync test order (sale order with lab tests) from Odoo to OpenELIS.
        
        :param sale_order: sale.order record
        :return: dict with status and message
        """
        if not self._is_sync_enabled():
            _logger.debug("OpenELIS sync is disabled, skipping test order sync")
            return {'status': 'skipped', 'message': 'OpenELIS sync is disabled'}

        # Check if order has a patient
        if not sale_order.partner_id:
            _logger.warning("Sale order %s has no customer/patient, skipping sync", sale_order.name)
            return {'status': 'skipped', 'message': 'No customer/patient'}

        # Filter order lines that are lab tests or panels
        lab_test_lines = []
        for line in sale_order.order_line:
            product = line.product_id.product_tmpl_id
            if product.is_lab_test or product.is_panel:
                lab_test_lines.append(line)

        if not lab_test_lines:
            _logger.debug("Sale order %s has no lab test products, skipping sync", sale_order.name)
            return {'status': 'skipped', 'message': 'No lab test products in order'}

        try:
            # Build payload
            payload = {
                'sale_order_id': str(sale_order.id),
                'sale_order_name': sale_order.name,
                'order_date': sale_order.date_order.strftime('%Y-%m-%d') if sale_order.date_order else '',
                'patient': {
                    'uuid': sale_order.partner_id.uuid if hasattr(sale_order.partner_id, 'uuid') and sale_order.partner_id.uuid else '',
                    'ref': sale_order.partner_id.ref or '',
                    'name': sale_order.partner_id.name or '',
                    'birthdate': sale_order.partner_id.birthdate_date.strftime('%Y-%m-%d') if hasattr(sale_order.partner_id, 'birthdate_date') and sale_order.partner_id.birthdate_date else '',
                    'gender': sale_order.partner_id.gender if hasattr(sale_order.partner_id, 'gender') else '',
                },
                'order_lines': []
            }

            # Add order lines
            for line in lab_test_lines:
                product = line.product_id.product_tmpl_id
                order_line_data = {
                    'product_uuid': str(product.id),  # Using product ID as UUID for external reference
                    'product_name': product.name,
                    'product_type': 'Panel' if product.is_panel else 'Test',
                    'quantity': line.product_uom_qty,
                    'comment': line.name or ''  # Order line description as comment
                }
                payload['order_lines'].append(order_line_data)

            # Call OpenELIS API
            response = self._call_openelis_api(payload, endpoint='/rest/odoo/test-order', event_type='test_order')

            if response.get('status') == 'success':
                _logger.info("Successfully synced test order %s to OpenELIS", sale_order.name)
                return {'status': 'success', 'message': response.get('message', 'Synced successfully')}
            else:
                _logger.error("Failed to sync test order %s to OpenELIS: %s", 
                             sale_order.name, response.get('message', 'Unknown error'))
                return {'status': 'error', 'message': response.get('message', 'Unknown error')}

        except Exception as e:
            _logger.error("Error syncing test order %s to OpenELIS: %s", sale_order.name, str(e), exc_info=True)
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
        
        for line in sale_order.order_line:
            if line.display_type in ('line_section', 'line_note'):
                continue
            
            # Use the new is_lab_test flag
            if line.product_id and line.product_id.is_lab_test:
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
            'gender': patient.gender or '',
            'primary_relative': patient.primary_relative or '',
            'occupation': patient.occupation or '',
            'age': patient.age if patient.age else 0,
            'address': {
                'street': (patient.street or '')[:30],
                'city': (patient.city or '')[:30],
                'state': patient.state_id.code or '',
                'zip': (patient.zip or '')[:10],
                'country': (patient.country_id.name or '')[:20]
            }
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
    def _call_openelis_api(self, payload, endpoint='/rest/odoo/test-order', event_type='test_order'):
        """
        Common method to call OpenELIS API.
        """
        # Get OpenELIS API configuration
        api_url = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.openelis_api_url', '')
        api_username = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.openelis_api_username', '')
        api_password = self.env['ir.config_parameter'].sudo().get_param('abershum_elis_sync.openelis_api_password', '')

        if not api_url:
            _logger.warning("OpenELIS API URL is not configured. Cannot sync %s", event_type)
            return {'status': 'error', 'message': 'API URL not configured'}

        # Ensure URL starts with schema
        if not api_url.startswith(('http://', 'https://')):
            api_url = 'http://' + api_url.lstrip('/')
        
        # Prepare request URL
        base_url = api_url.rstrip('/')
        url = base_url + endpoint
        
        _logger.info("=== Request Details ===")
        _logger.info("Full URL: %s", url)
        _logger.info("Method: POST")
        _logger.info("Headers: Content-Type=application/json")
        _logger.info("Authentication: %s", "Basic Auth (username: %s)" % api_username if (api_username and api_password) else "None")
        _logger.info("Timeout: 30 seconds")
        _logger.info("SSL Verification: Disabled")
        _logger.info("Payload Summary:")
        if event_type == 'test_order':
            _logger.info("  Sale Order ID: %s", payload.get('sale_order_id', 'N/A'))
            _logger.info("  Sale Order Name: %s", payload.get('sale_order_name', 'N/A'))
            _logger.info("  Patient: %s (ref: %s)", 
                        payload.get('patient', {}).get('name', 'N/A'),
                        payload.get('patient', {}).get('ref', 'N/A'))
            _logger.info("  Order Lines Count: %s", len(payload.get('order_lines', [])))
        else:
            _logger.info("  Product ID: %s", payload.get('id', 'N/A'))
            _logger.info("  Product Name: %s", payload.get('name', 'N/A'))
        
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
                    # payload['sale_order_id'] is a string, convert to int
                    try:
                        sale_order_id = int(payload['sale_order_id'])
                    except (ValueError, TypeError):
                        sale_order_id = None
                
                if not sale_order_id:
                    # Try to find by name
                    sale_order_name = payload.get('sale_order_name')
                    if sale_order_name:
                        sale_order_rec = self.env['sale.order'].search([('name', '=', sale_order_name)], limit=1)
                        if sale_order_rec:
                            sale_order_id = sale_order_rec.id
                
                _logger.info("Creating failed event for sale_order_id: %s", sale_order_id)
                self.env['openelis.failed.event'].create_or_update_failed_event(
                    event_type=event_type,
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
                event_type=event_type,
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
                event_type=event_type,
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
                event_type=event_type,
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
                event_type=event_type,
                payload_dict=payload,
                error_message=error_msg,
                error_type=error_type,
                sale_order_id=sale_order_id if sale_order_id else None,
            )
            
            raise
        finally:
            _logger.info("=== Test order sync attempt completed ===")
