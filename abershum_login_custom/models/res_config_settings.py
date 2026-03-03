# -*- coding: utf-8 -*-

from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    """Extension of res.config.settings for Abershum Login Customization.
    
    Provides admin configuration options for customizing the login page
    appearance including background and positioning settings.
    """
    _inherit = 'res.config.settings'

    orientation = fields.Selection(
        selection=[
            ('default', 'Default'),
            ('left', 'Left'),
            ('middle', 'Middle'),
            ('right', 'Right'),
        ],
        string="Login Card Position",
        default='middle',
        help='Position of the login card on the login page'
    )

    background = fields.Selection(
        selection=[
            ('color', 'Color'),
            ('image', 'Image'),
            ('url', 'URL'),
        ],
        string="Background Type",
        help='Type of background for the login page'
    )

    image = fields.Binary(
        string="Background Image",
        help='Upload an image to use as login page background'
    )

    url = fields.Char(
        string="Background URL",
        help='External URL for the login page background image'
    )

    color = fields.Char(
        string="Background Color",
        help='Hex color code for login page background (e.g., #875A7B)'
    )

    card_width = fields.Integer(
        string="Login Card Width",
        default=450,
        help='Width of the login card in pixels (default: 450)'
    )

    @api.model
    def get_values(self):
        """Retrieve stored configuration values from ir.config_parameter."""
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            orientation=params.get_param('abershum_login_custom.orientation', 'middle'),
            background=params.get_param('abershum_login_custom.background'),
            image=params.get_param('abershum_login_custom.image'),
            url=params.get_param('abershum_login_custom.url'),
            color=params.get_param('abershum_login_custom.color'),
            card_width=int(params.get_param('abershum_login_custom.card_width') or 450),
        )
        return res

    def set_values(self):
        """Store configuration values to ir.config_parameter."""
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('abershum_login_custom.orientation', self.orientation or 'middle')
        params.set_param('abershum_login_custom.background', self.background or False)
        params.set_param('abershum_login_custom.image', self.image or False)
        params.set_param('abershum_login_custom.url', self.url or False)
        params.set_param('abershum_login_custom.color', self.color or False)
        params.set_param('abershum_login_custom.card_width', self.card_width or 450)

    @api.onchange('orientation')
    def onchange_orientation(self):
        """Reset background when orientation is set to default."""
        if self.orientation == 'default':
            self.background = False
