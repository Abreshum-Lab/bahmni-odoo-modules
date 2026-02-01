# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import uuid
import logging

import os

_logger = logging.getLogger(__name__)

class OrthancOrder(models.Model):
    _name = 'orthanc.order'
    _description = 'Orthanc Radiology Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: ('New'))
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    product_id = fields.Many2one('product.product', string='Service', readonly=True)
    study_uuid = fields.Char(string='Study UUID', readonly=True, copy=False)
    
    # Reporting Fields
    findings = fields.Html(string='Findings', tracking=True)
    impression = fields.Html(string='Impression', tracking=True)
    recommendation = fields.Html(string='Recommendation', tracking=True)
    
    radiologist_id = fields.Many2one('abershum.provider', string='Radiologist', tracking=True)
    signed_at = fields.Datetime(string='Signed At', readonly=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sign', 'Signed'),
        ('complete', 'Completed'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)
    cancel_reason = fields.Text(string='Cancellation Reason', tracking=True, readonly=True)

    def action_sign_report(self):
        self.ensure_one()
        vals = {
            'state': 'sign',
            'signed_at': fields.Datetime.now(),
        }
        # If no radiologist assigned, try to find a provider linked to current user or just leave it
        if not self.radiologist_id:
             # This is optional, but let's see if we should auto-assign. 
             # For now, let's just sign it. The user might have selected it manually.
             pass
        self.write(vals)
    
    def action_reset_draft(self):
         self.ensure_one()
         self.write({'state': 'draft', 'signed_at': False})

    def action_complete(self):
        self.ensure_one()
        if self.state != 'sign':
             raise UserError("Only signed reports can be marked as completed.")
        self.write({'state': 'complete'})

    def action_print_report(self):
        for record in self:
            if record.state not in ('sign', 'complete'):
                raise UserError("The report is not signed yet. Click on 'Sign Report' to proceed.")
        return self.env.ref('abershum_orthanc.action_report_radiology_order').report_action(self)

    def unlink(self):
        for record in self:
            if record.state != 'draft':
                 raise UserError("You cannot delete an order that is not in Draft state. Please cancel it instead.")
        return super(OrthancOrder, self).unlink()

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('orthanc.order') or 'New'
        if not vals.get('study_uuid'):
            vals['study_uuid'] = str(uuid.uuid4())
        return super(OrthancOrder, self).create(vals)

    def write(self, vals):
        # Allow state changes and message posting, but block content changes on finalized records
        if any(rec.state in ('sign', 'complete', 'cancel') for rec in self) and 'state' not in vals and 'message_follower_ids' not in vals:
             restricted = ['findings', 'impression', 'recommendation', 'product_id', 
                           'sale_order_id', 'radiologist_id', 'study_uuid']
             if any(f in vals for f in restricted):
                 state_labels = dict(self._fields['state'].selection)
                 current_state = state_labels.get(self[0].state)
                 raise UserError(f"You cannot modify a radiology order in '{current_state}' state. Please reset to draft first (if allowed).")
        return super(OrthancOrder, self).write(vals)


    def _send_to_orthanc(self):
        self.ensure_one()
        self.env['orthanc.service'].create_worklist(self)

    def action_send_email(self):
        self.ensure_one()
        template_id = self.env.ref('abershum_orthanc.email_template_radiology_report').id
        ctx = {
            'default_model': 'orthanc.order',
            'default_res_id': self.id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'force_email': True,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def action_open_orthanc(self):
        self.ensure_one()
        # Retrieve config settings (Env var > DB param)
        orthanc_url = self.env['ir.config_parameter'].sudo().get_param('abershum_orthanc.orthanc_api_url') or os.environ.get('ORTHANC_URL')
        if not orthanc_url:
            return
        
        # target_url = f"{orthanc_url.rstrip('/')}/app/explorer.html#study?uuid={self.study_uuid}"
        
        # OHIF Viewer Link
        # Note: OHIF typically expects StudyInstanceUID, but our self.study_uuid is effectively acting as the StudyInstanceUID in generation
        target_url = f"{orthanc_url.rstrip('/')}/ohif/viewer?StudyInstanceUIDs={self.study_uuid}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': target_url,
            'target': 'new',
        }
