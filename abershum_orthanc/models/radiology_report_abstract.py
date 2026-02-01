# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
import pytz

class ReportRadiologyOrder(models.AbstractModel):
    _name = 'report.abershum_orthanc.report_radiology_order'
    _description = 'Radiology Report Logic'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['orthanc.order'].browse(docids)
        
        # Validation: Ensure all requested reports are signed or completed
        for doc in docs:
            if doc.state not in ('sign', 'complete'):
                raise UserError(f"The report for {doc.name} is not signed yet. Click on 'Sign Report' to proceed.")
        
        # Track printing
        user = self.env.user
        tz = pytz.timezone(user.tz or 'UTC')
        now = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        
        for doc in docs:
            msg = f"Report printed by {user.name} at {now}"
            doc.message_post(body=msg)

        return {
            'doc_ids': docids,
            'doc_model': 'orthanc.order',
            'docs': docs,
            'printed_by': user.name,
            'printed_at': now,
        }
