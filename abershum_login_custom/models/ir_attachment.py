# -*- coding: utf-8 -*-

from odoo import fields, models


class IrAttachment(models.Model):
    """Extension of ir.attachment to support background images.
    
    Adds a boolean field to mark attachments used as login page backgrounds.
    """
    _inherit = 'ir.attachment'

    is_background = fields.Boolean(
        string='Is Background',
        default=False,
        help='Mark this attachment as a login page background image'
    )
