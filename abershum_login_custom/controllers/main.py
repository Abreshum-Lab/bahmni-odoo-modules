# -*- coding: utf-8 -*-

import hashlib
from odoo.tools import pycompat
from odoo import http
from odoo.http import request
import odoo
from odoo.tools.translate import _
from odoo.addons.web.controllers.home import Home as WebHome
from odoo.addons.web.controllers.utils import ensure_db, _get_login_redirect_url


# Shared parameters for all login/signup flows
SIGN_UP_REQUEST_PARAMS = {'db', 'login', 'debug', 'token', 'message', 'error', 'scope', 'mode',
                          'redirect', 'redirect_hostname', 'email', 'name', 'partner_id',
                          'password', 'confirm_password', 'city', 'country_id', 'lang'}


class Home(WebHome):

    @http.route('/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        """Override web_login to render custom login templates based on configuration."""
        ensure_db()
        request.params['login_success'] = False
        if request.httprequest.method == 'GET' and redirect and request.session.uid:
            return request.redirect(redirect)

        if not request.uid:
            request.update_env(user=odoo.SUPERUSER_ID)

        values = {k: v for k, v in request.params.items() if k in SIGN_UP_REQUEST_PARAMS}
        try:
            values['databases'] = http.db_list()
        except odoo.exceptions.AccessDenied:
            values['databases'] = None

        if request.httprequest.method == 'POST':
            try:
                uid = request.session.authenticate(request.session.db, request.params['login'],
                                                   request.params['password'])
                request.params['login_success'] = True
                return request.redirect(self._login_redirect(uid, redirect=redirect))
            except odoo.exceptions.AccessDenied as e:
                if e.args == odoo.exceptions.AccessDenied().args:
                    values['error'] = _("Wrong login/password")
                else:
                    values['error'] = e.args[0]
        else:
            if 'error' in request.params and request.params.get('error') == 'access':
                values['error'] = _('Only employees can access this database. Please contact the administrator.')

        if 'login' not in values and request.session.get('auth_login'):
            values['login'] = request.session.get('auth_login')

        if not odoo.tools.config['list_db']:
            values['disable_database_manager'] = True

        # Get configuration parameters
        conf_param = request.env['ir.config_parameter'].sudo()
        orientation = conf_param.get_param('abershum_login_custom.orientation', 'middle')
        image = conf_param.get_param('abershum_login_custom.image')
        url = conf_param.get_param('abershum_login_custom.url')
        background_type = conf_param.get_param('abershum_login_custom.background') or 'url'
        card_width = int(conf_param.get_param('abershum_login_custom.card_width') or 450)

        # Default background image URL (major.jpg)
        default_bg_url = '/abershum_login_custom/static/src/img/major.jpg'

        # Handle background based on type
        if background_type == 'color':
            values['bg'] = ''
            values['color'] = conf_param.get_param('abershum_login_custom.color') or '#875A7B'

        elif background_type == 'image':
            exist_rec = request.env['ir.attachment'].sudo().search([('is_background', '=', True)])
            if exist_rec:
                exist_rec.unlink()
            attachments = request.env['ir.attachment'].sudo().create({
                'name': 'Background Image',
                'datas': image,
                'type': 'binary',
                'mimetype': 'image/png',
                'public': True,
                'is_background': True
            })
            base_url = conf_param.get_param('web.base.url')
            img_url = base_url + '/web/image?' + 'model=ir.attachment&id=' + str(attachments.id) + '&field=datas'
            values['bg_img'] = img_url or ''

        elif background_type == 'url':
            custom_url = conf_param.get_param('abershum_login_custom.url')
            if custom_url:
                pre_exist = request.env['ir.attachment'].sudo().search([('url', '=', custom_url)])
                if not pre_exist:
                    attachments = request.env['ir.attachment'].sudo().create({
                        'name': 'Background Image URL',
                        'url': custom_url,
                        'type': 'url',
                        'public': True
                    })
                else:
                    attachments = pre_exist
                encode = hashlib.md5(pycompat.to_text(attachments.url).encode("utf-8")).hexdigest()[0:7]
                encode_url = "/web/image/{}-{}".format(attachments.id, encode)
                values['bg_img'] = encode_url or ''
            else:
                # Use default background image
                values['bg_img'] = default_bg_url

        # Pass card_width to templates
        values['card_width'] = card_width

        # Render appropriate template based on orientation
        if orientation == 'right':
            response = request.render('abershum_login_custom.login_template_right', values)
        elif orientation == 'left':
            response = request.render('abershum_login_custom.login_template_left', values)
        elif orientation == 'middle':
            response = request.render('abershum_login_custom.login_template_middle', values)
        else:
            response = request.render('web.login', values)

        response.headers['X-Frame-Options'] = 'DENY'
        return response
