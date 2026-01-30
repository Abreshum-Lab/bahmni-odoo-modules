# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid
import logging

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
    
    radiologist_id = fields.Many2one('res.users', string='Radiologist', tracking=True)
    signed_at = fields.Datetime(string='Signed At', readonly=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('signed', 'Signed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)
    cancel_reason = fields.Text(string='Cancellation Reason', tracking=True, readonly=True)

    def action_sign_report(self):
        self.ensure_one()
        self.write({
            'state': 'signed',
            'signed_at': fields.Datetime.now(),
            'radiologist_id': self.env.user.id
        })
    
    def action_reset_draft(self):
         self.ensure_one()
         self.write({'state': 'draft', 'signed_at': False, 'radiologist_id': False})

    def unlink(self):
        for record in self:
            if record.state != 'draft':
                 raise api.exc.UserError("You cannot delete an order that is not in Draft state. Please cancel it instead.")
        return super(OrthancOrder, self).unlink()

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('orthanc.order') or 'New'
        if not vals.get('study_uuid'):
            vals['study_uuid'] = str(uuid.uuid4())
        return super(OrthancOrder, self).create(vals)


    def _send_to_orthanc(self):
        self.ensure_one()
        _logger.info("Sending order %s to Orthanc with Study UUID %s", self.name, self.study_uuid)
        # Placeholder for actual API call
        pass

    def action_open_orthanc(self):
        self.ensure_one()
        # Retrieve config settings
        orthanc_url = self.env['ir.config_parameter'].sudo().get_param('abershum_orthanc.orthanc_api_url')
        if not orthanc_url:
            return
        
        # Construct URL (Example structure)
        # Assuming Orthanc generic viewer or OHIF viewer url structure
        # http://<server>/app/explorer.html#study?uuid=<UUID> is a generic placeholder assumption
        # or http://<server>/ohif/viewer/<UUID>
        
        target_url = f"{orthanc_url.rstrip('/')}/app/explorer.html#study?uuid={self.study_uuid}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': target_url,
            'target': 'new',
        }
