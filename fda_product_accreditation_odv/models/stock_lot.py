# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    permit_ids = fields.One2many('product.permit.lot', 'lot_id', string='Permit Lots')
    permit_lot_id = fields.Many2one(
        'product.permit.lot',
        string='Current Permit',
        compute='_compute_permit_lot_id',
        store=True,
        readonly=True,
    )
    permit_registration_date = fields.Date(
        string='Permit Registration Date',
        related='permit_lot_id.registration_date',
        readonly=True,
        store=False,
    )
    permit_expiry_date = fields.Date(
        string='Permit Expiry Date',
        related='permit_lot_id.expiry_date',
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
        related='permit_lot_id.state',
        readonly=True,
        store=False,
    )

    @api.depends('permit_ids.expiry_date', 'permit_ids.state', 'permit_ids.lot_id')
    def _compute_permit_lot_id(self):
        for lot in self:
            permits = lot.permit_ids.filtered('active')
            if not permits:
                lot.permit_lot_id = False
                continue

            specific_permits = permits.filtered(lambda p: p.lot_id == lot)
            blanket_permits = permits.filtered(lambda p: not p.lot_id)
            lot.permit_lot_id = specific_permits.sorted('expiry_date')[:1] or blanket_permits.sorted('expiry_date')[:1] or False
