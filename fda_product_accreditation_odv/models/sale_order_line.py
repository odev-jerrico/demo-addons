# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    permit_registration_date = fields.Date(
        string='Permit Registration Date',
        related='product_id.permit_registration_date',
        readonly=True,
        store=False,
    )
    permit_expiry_date = fields.Date(
        string='Permit Expiry Date',
        related='product_id.permit_expiry_date',
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
        related='product_id.permit_state',
        readonly=True,
        store=False,
    )
    permit_days_remaining = fields.Integer(
        string='Permit Days Remaining',
        related='product_id.permit_days_remaining',
        readonly=True,
        store=False,
    )
