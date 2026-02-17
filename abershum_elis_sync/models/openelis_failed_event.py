# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OpenELISFailedEvent(models.Model):
    _name = 'openelis.failed.event'
    _description = 'OpenELIS Failed Sync Event'
    _order = 'sequence_number asc, create_date asc'  # Order by sequence (FIFO) for retries
    _rec_name = 'display_name'
    
    # Internal sequence number for FIFO retry processing
    sequence_number = fields.Integer(
        string='Sequence Number',
        default=0,
        index=True,
        readonly=True,
        help='Internal sequence number for ordering retries (first failed, first retried)'
    )
    
    @api.model
    def create(self, vals):
        # Only allow creation through create_or_update_failed_event method
        # Check context flag set by our internal method
        if not self.env.context.get('allow_system_create'):
            raise UserError(_("Failed events can only be created automatically by the system. Manual creation is not allowed."))
        return super(OpenELISFailedEvent, self).create(vals)
    
    def write(self, vals):
        # Only allow modification through internal methods (retry, mark success, etc.)
        # Check context flag set by our internal methods
        if not self.env.context.get('allow_system_write'):
            raise UserError(_("Failed events can only be modified by the system. Manual editing is not allowed."))
        return super(OpenELISFailedEvent, self).write(vals)

    # Identification fields
    event_type = fields.Selection([
        ('patient', 'Patient Sync'),
        ('test_order', 'Test Order Sync'),
        ('lab_test', 'Lab Test Sync'),
    ], string='Event Type', required=True, index=True)
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Patient/Customer',
        ondelete='cascade',
        index=True,
        help='The patient/customer this event relates to'
    )
    
    partner_ref = fields.Char(
        string='Patient Reference',
        index=True,
        help='Patient reference (ref field) for deduplication'
    )
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        ondelete='cascade',
        help='The sale order this event relates to (for test orders)'
    )
    
    # Payload and error information
    payload = fields.Text(
        string='Payload',
        required=True,
        help='JSON payload that was sent to OpenELIS'
    )
    
    error_message = fields.Text(
        string='Error Message',
        required=True,
        help='Error message from the failed sync attempt'
    )
    
    error_type = fields.Char(
        string='Error Type',
        help='Type of error (e.g., ConnectionError, Timeout, HTTP 404)'
    )
    
    # Retry tracking
    retry_count = fields.Integer(
        string='Retry Count',
        default=0,
        help='Number of times this event has been retried'
    )
    
    last_retry_date = fields.Datetime(
        string='Last Retry Date',
        help='Date and time of the last retry attempt'
    )
    
    next_retry_date = fields.Datetime(
        string='Next Retry Date',
        help='Scheduled date and time for the next retry'
    )
    
    # Status
    state = fields.Selection([
        ('pending', 'Pending Retry'),
        ('retrying', 'Retrying'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], string='Status', default='pending', index=True)
    
    # Metadata
    name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
        index=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    create_date = fields.Datetime(string='Created On', readonly=True)
    write_date = fields.Datetime(string='Last Updated', readonly=True)
    
    @api.depends('event_type', 'partner_ref', 'sale_order_id', 'state')
    def _compute_display_name(self):
        for record in self:
            if record.event_type == 'patient':
                name = f"Patient Sync - {record.partner_ref or 'N/A'}"
            elif record.event_type == 'lab_test':
                # Extract product name from payload if available
                try:
                    payload = json.loads(record.payload) if record.payload else {}
                    product_name = payload.get('name', 'N/A')
                    name = f"Lab Test - {product_name}"
                except:
                    name = "Lab Test - N/A"
            else:
                name = f"Test Order - {record.sale_order_id.name if record.sale_order_id else 'N/A'}"
            record.name = name
            record.display_name = f"{name} [{record.state}]"
    
    def _get_payload_dict(self):
        """Parse payload JSON string to dict"""
        try:
            return json.loads(self.payload) if self.payload else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def _set_payload_dict(self, payload_dict):
        """Convert payload dict to JSON string"""
        self.payload = json.dumps(payload_dict, indent=2) if payload_dict else '{}'
    
    @api.model
    def create_or_update_failed_event(self, event_type, payload_dict, error_message, 
                                     error_type=None, partner_id=None, partner_ref=None, 
                                     sale_order_id=None):
        """
        Create or update a failed event. If an event already exists for the same
        partner (for patient sync) or sale order (for test order sync), update it
        instead of creating a new one. This ensures only the latest version is kept.
        
        :param event_type: 'patient' or 'test_order'
        :param payload_dict: Dictionary containing the payload
        :param error_message: Error message string
        :param error_type: Type of error (optional)
        :param partner_id: res.partner record (optional)
        :param partner_ref: Patient reference string (optional, for deduplication)
        :param sale_order_id: sale.order record (optional)
        :return: The created or updated failed event record
        """
        # Find existing event for deduplication
        domain = [('event_type', '=', event_type), ('state', 'in', ['pending', 'retrying', 'failed'])]
        
        if event_type == 'patient':
            if partner_ref:
                domain.append(('partner_ref', '=', partner_ref))
            elif partner_id:
                domain.append(('partner_id', '=', partner_id.id))
        elif event_type == 'test_order':
            if sale_order_id:
                # Handle both recordset and integer ID
                so_id = sale_order_id.id if hasattr(sale_order_id, 'id') else sale_order_id
                domain.append(('sale_order_id', '=', so_id))
        
        existing_event = self.search(domain, limit=1)
        
        if existing_event:
            # Update existing event with latest information - set context flag to allow write
            # Keep the original sequence_number (FIFO - first failed, first retried)
            _logger.info("Updating existing failed event #%d (%s) with latest payload", 
                        existing_event.sequence_number, existing_event.display_name)
            update_vals = {
                'payload': json.dumps(payload_dict, indent=2) if payload_dict else '{}',
                'error_message': error_message,
                'error_type': error_type or '',
                'retry_count': 0,  # Reset retry count for new version
                'state': 'pending',
                'next_retry_date': False,
                'last_retry_date': False,
                # Keep original sequence_number for FIFO ordering
            }
            if partner_id:
                update_vals['partner_id'] = partner_id.id
            if partner_ref:
                update_vals['partner_ref'] = partner_ref
            if sale_order_id:
                # Handle both recordset and integer ID
                update_vals['sale_order_id'] = sale_order_id.id if hasattr(sale_order_id, 'id') else sale_order_id
            
            existing_event.with_context(allow_system_write=True).write(update_vals)
            return existing_event
        else:
            # Create new event - set context flag to allow creation
            _logger.info("Creating new failed event for %s", event_type)
            # Get next sequence number for FIFO ordering
            sequence_number = self._get_next_sequence_number()
            return self.with_context(allow_system_create=True).create({
                'event_type': event_type,
                'payload': json.dumps(payload_dict, indent=2) if payload_dict else '{}',
                'error_message': error_message,
                'error_type': error_type or '',
                'partner_id': partner_id.id if partner_id else False,
                'partner_ref': partner_ref or '',
                'sale_order_id': sale_order_id.id if (sale_order_id and hasattr(sale_order_id, 'id')) else (sale_order_id if sale_order_id else False),
                'state': 'pending',
                'retry_count': 0,
                'sequence_number': sequence_number,
            })
    
    @api.model
    def _get_next_sequence_number(self):
        """Get the next sequence number for FIFO ordering"""
        # Get the highest sequence number and add 1
        max_seq = self.search([], order='sequence_number desc', limit=1)
        if max_seq and max_seq.sequence_number:
            return max_seq.sequence_number + 1
        return 1
    
    def action_retry(self):
        """Manually retry a failed event"""
        for record in self:
            if record.state == 'success':
                raise UserError(_("This event has already been successfully processed."))
            
            record._retry_sync()
    
    def _retry_sync(self):
        """Internal method to retry syncing the event"""
        self.ensure_one()
        
        if self.state == 'success':
            return True
        
        _logger.info("Retrying failed event %s (ID: %s, Type: %s)", 
                    self.display_name, self.id, self.event_type)
        
        self.with_context(allow_system_write=True).write({
            'state': 'retrying',
            'last_retry_date': fields.Datetime.now(),
            'retry_count': self.retry_count + 1,
        })
        
        try:
            payload_dict = self._get_payload_dict()
            
            if self.event_type == 'patient':
                # Retry patient sync
                partner = self.partner_id
                if not partner:
                    raise UserError(_("Partner not found for this event."))
                
                # Call the patient sync method with a flag to prevent duplicate event creation
                if not self.env['res.partner'].with_context(is_retry=True)._sync_patient_to_openelis(partner):
                    raise UserError(_("Patient sync returned failure status. See logs or updated event for details."))
                
            elif self.event_type == 'test_order':
                # Retry test order sync
                sale_order = self.sale_order_id
                if not sale_order:
                    raise UserError(_("Sale order not found for this event."))
                
                # Get the sync service and retry - use sync_test_order_to_openelis method
                sync_service = self.env['openelis.sync.service']
                # Rebuild payload if needed, or use the stored payload
                result = sync_service.with_context(sale_order_id=sale_order.id, is_retry=True).sync_test_order_to_openelis(sale_order)
                
                if result.get('status') != 'success':
                    raise UserError(_("Retry failed: %s") % result.get('message', 'Unknown error'))
            
            elif self.event_type == 'lab_test':
                # Retry lab test sync
                product_id = payload_dict.get('id')
                if not product_id:
                    raise UserError(_("Product ID not found in payload."))
                
                # We assume product.template as that's what the sync service expects/uses mostly
                product = self.env['product.template'].browse(product_id)
                if not product.exists():
                    raise UserError(_("Product not found (ID: %s)") % product_id)
                
                sync_service = self.env['openelis.sync.service']
                result = sync_service.sync_lab_test_to_openelis(product)
                
                if result.get('status') != 'success':
                     raise UserError(_("Retry failed: %s") % result.get('message', 'Unknown error'))

            else:
                 # Logic missing for this event type
                 raise UserError(_("Retry logic missing for event type '%s'. (500 Server Error)") % self.event_type)
            
            # If we get here, sync was successful
            _logger.info(">>> Failed Event Retry: Sync method returned success. Proceeding to set state=success and unlink.")
            self.with_context(allow_system_write=True).write({
                'state': 'success',
                'next_retry_date': False,
            })
            
            # Delete the event after successful sync
            _logger.info(">>> Failed Event Retry: Unlinking record #%d", self.id)
            self.unlink()
            return True
            
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Calculate next retry date (simple exponential backoff or fixed interval)
            from datetime import timedelta
            next_retry = fields.Datetime.now() + timedelta(minutes=15 * (self.retry_count or 1))
            
            self.with_context(allow_system_write=True).write({
                'state': 'failed',
                'error_message': error_msg,
                'error_type': error_type,
                'next_retry_date': next_retry,
            })
            return False
    
    @api.model
    def cron_retry_failed_events(self):
        """Scheduled action to automatically retry failed events serially (FIFO)"""
        _logger.info("Starting automatic retry of failed events (FIFO order)...")
        
        # Find events that are pending and have a next_retry_date in the past or no next_retry_date
        now = fields.Datetime.now()
        domain = [
            ('state', 'in', ['pending', 'failed']),
            '|',
            ('next_retry_date', '<=', now),
            ('next_retry_date', '=', False),
        ]
        
        # Search with order by sequence_number (FIFO - first failed, first retried)
        events_to_retry = self.search(domain, limit=50, order='sequence_number asc, create_date asc')
        
        if not events_to_retry:
            _logger.info("No events to retry at this time")
            return
        
        _logger.info("Found %d events to retry (processing in FIFO order)", len(events_to_retry))
        
        success_count = 0
        for event in events_to_retry:
            try:
                _logger.info("Processing event #%d: %s", event.sequence_number, event.display_name)
                if event._retry_sync():
                    success_count += 1
            except Exception as e:
                _logger.error("Error retrying event #%d (%s): %s", 
                            event.sequence_number, event.display_name, str(e))
        
        _logger.info("Retry completed: %d successful, %d failed", 
                    success_count, len(events_to_retry) - success_count)
    
    def action_retry_selected(self):
        """Action to retry selected failed events from list view (serially, FIFO order)"""
        # Sort by sequence_number to ensure FIFO processing
        sorted_records = self.sorted(lambda r: (r.sequence_number or 0, r.create_date))
        for record in sorted_records:
            if record.state != 'success':
                try:
                    record.action_retry()
                except Exception as e:
                    _logger.error("Error retrying event #%d (%s): %s", 
                                record.sequence_number, record.display_name, str(e))
    
    def action_mark_success(self):
        """Manually mark an event as successful (if it was fixed externally)"""
        self.with_context(allow_system_write=True).write({'state': 'success'})
        self.unlink()  # Delete after marking as success
    
    def action_delete(self):
        """Delete the failed event"""
        self.unlink()
