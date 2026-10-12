# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    permit_ids = fields.One2many('product.permit.lot', 'product_id', string='Permit Lots')
    permit_registration_date = fields.Date(
        string='Permit Registration Date',
        compute='_compute_permit_summary',
        store=True,
        readonly=True,
    )
    permit_expiry_date = fields.Date(
        string='Permit Expiry Date',
        compute='_compute_permit_summary',
        store=True,
        readonly=True,
    )
    permit_state = fields.Selection([
        ('none', 'No Expiry Set'),
        ('valid', 'Valid'),
        ('warning', 'Near Expiry'),
        ('expired', 'Expired'),
    ], string='Permit Status', compute='_compute_permit_summary', store=True, readonly=True)
    permit_days_remaining = fields.Integer(string='Permit Days Remaining', compute='_compute_permit_summary', store=True, readonly=True)
    has_expired_permit = fields.Boolean(string='Expired Permit', compute='_compute_permit_summary', store=True, readonly=True)
    has_near_expiry_permit = fields.Boolean(string='Near Expiry Permit', compute='_compute_permit_summary', store=True, readonly=True)

    @api.depends('permit_ids.expiry_date', 'permit_ids.state', 'permit_ids.registration_date', 'permit_ids.warning_days', 'permit_ids.lot_id')
    def _compute_permit_summary(self):
        for product in self:
            permits = product.permit_ids.filtered('active')
            if not permits:
                product.permit_registration_date = False
                product.permit_expiry_date = False
                product.permit_state = 'none'
                product.permit_days_remaining = 0
                product.has_expired_permit = False
                product.has_near_expiry_permit = False
                continue

            blanket_permits = permits.filtered(lambda p: not p.lot_id)
            permit = blanket_permits.sorted('expiry_date')[:1] or permits.sorted('expiry_date')[:1]

            product.permit_registration_date = permit.registration_date
            product.permit_expiry_date = permit.expiry_date
            product.permit_state = permit.state
            product.permit_days_remaining = permit.days_remaining
            product.has_expired_permit = permit.is_expired
            product.has_near_expiry_permit = permit.is_near_expiry
