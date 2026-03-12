# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def post_init_hook(cr, registry):
    """
    Update existing patient records to have a default birthdate if missing.
    This prevents validation errors during module installation/update.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    patients = env['res.partner'].search([
        ('is_patient', '=', True),
        ('is_company', '=', False),
        ('birthdate', '=', False),
        ('age', '=', 0),
        ('birth_months', '=', 0),
        ('birth_days', '=', 0)
    ])
    
    if patients:
        _logger.info("Updating %s legacy patient records with default birthdate info", len(patients))
        for patient in patients:
            try:
                # Set a default/placeholder or try to find some other info
                # For now, we'll set age to 0 and skip constraint during this update if possible
                # or just set a very old birthdate/placeholder.
                # Usually, it's safer to just set age=0 if info is missing but we're forcing mandatory.
                # But since age=0, months=0, days=0 is caught by our constraint, we should set something.
                patient.with_context(skip_compute_age=True).write({
                    'age': 0,
                    'birth_months': 0,
                    'birth_days': 1, # 1 day old as default to pass constraint if absolutely nothing exists
                })
            except Exception as e:
                _logger.error("Failed to update legacy patient %s: %s", patient.name, str(e))
