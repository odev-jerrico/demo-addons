# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    permit_ids = fields.One2many('product.permit.lot', 'product_tmpl_id', string='Permit Lots')
    permit_registration_date = fields.Date(
        string='Permit Registration Date',
        related='product_variant_id.permit_registration_date',
        readonly=True,
        store=False,
    )
    permit_expiry_date = fields.Date(
        string='Permit Expiry Date',
        related='product_variant_id.permit_expiry_date',
        readonly=True,
        store=False,
    )
    permit_state = fields.Selection(
        [
            ('none', 'No Expiry Set'),
            ('valid', 'Valid'),
            ('warning', 'Near Expiry'),
            ('expired', 'Expired'),
        ],
        string='Permit Status',
        related='product_variant_id.permit_state',
        readonly=True,
        store=False,
    )
    permit_days_remaining = fields.Integer(
        string='Permit Days Remaining',
        related='product_variant_id.permit_days_remaining',
        readonly=True,
        store=False,
    )
    has_expired_permit = fields.Boolean(
        string='Expired Permit',
        related='product_variant_id.has_expired_permit',
        readonly=True,
        store=False,
    )
    has_near_expiry_permit = fields.Boolean(
        string='Near Expiry Permit',
        related='product_variant_id.has_near_expiry_permit',
        readonly=True,
        store=False,
    )
