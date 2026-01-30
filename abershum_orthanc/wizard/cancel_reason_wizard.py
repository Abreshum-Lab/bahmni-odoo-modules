# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CancelReasonWizard(models.TransientModel):
    _name = 'orthanc.cancel.wizard'
    _description = 'Radiology Order Cancellation Wizard'

    reason = fields.Text(string='Reason for Cancellation', required=True)

    def action_confirm_cancel(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            order = self.env['orthanc.order'].browse(active_id)
            order.write({
                'state': 'cancelled',
                'cancel_reason': self.reason
            })
