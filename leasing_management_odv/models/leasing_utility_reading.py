# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LeasingUtilityReading(models.Model):
    _name = 'leasing.utility.reading'
    _description = 'Leasing Utility Reading'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reading_date desc, id desc'

    meter_id = fields.Many2one('leasing.utility.meter', required=True, tracking=True)
    unit_id = fields.Many2one('leasing.unit', related='meter_id.unit_id', store=True, readonly=True)
    meter_type = fields.Selection(related='meter_id.meter_type', store=True, readonly=True)
    company_id = fields.Many2one('res.company', related='meter_id.company_id', store=True, readonly=True)

    reading_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    previous_reading = fields.Float(required=True, tracking=True)
    current_reading = fields.Float(required=True, tracking=True)
    rate_snapshot = fields.Float(string='Rate per Unit', required=True, default=0.0, tracking=True)
    consumption = fields.Float(compute='_compute_consumption', store=True)
    amount = fields.Monetary(compute='_compute_amount', store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True, readonly=True)

    billed = fields.Boolean(default=False, copy=False, tracking=True)
    invoice_id = fields.Many2one('account.move', copy=False, readonly=True, tracking=True)
    utility_invoice_count = fields.Integer(compute='_compute_utility_invoice_count')
    contract_id = fields.Many2one('leasing.contract', required=True, copy=False, tracking=True)

    _LOCKED_FIELDS_ON_BILLED = {'meter_id', 'reading_date', 'previous_reading', 'current_reading', 'rate_snapshot', 'contract_id'}

    @api.depends('previous_reading', 'current_reading')
    def _compute_consumption(self):
        for reading in self:
            reading.consumption = max(reading.current_reading - reading.previous_reading, 0.0)

    @api.depends('consumption', 'rate_snapshot')
    def _compute_amount(self):
        for reading in self:
            reading.amount = reading.consumption * reading.rate_snapshot

    @api.model_create_multi
    def create(self, vals_list):
        Meter = self.env['leasing.utility.meter']
        Contract = self.env['leasing.contract']
        for vals in vals_list:
            meter = False
            if vals.get('meter_id'):
                meter = Meter.browse(vals['meter_id'])

            if not vals.get('rate_snapshot') and meter:
                vals['rate_snapshot'] = meter.rate

            # Associate to the active contract at creation time unless user overrides.
            if not vals.get('contract_id') and meter and meter.unit_id:
                contract = Contract.search([
                    ('unit_id', '=', meter.unit_id.id),
                    ('state', '=', 'active'),
                ], limit=1)
                if contract:
                    vals['contract_id'] = contract.id

            if not vals.get('contract_id'):
                raise UserError(_('Please set a contract on the reading. No active lease contract was found for this unit.'))
        return super().create(vals_list)

    @api.onchange('meter_id')
    def _onchange_meter_id_set_rate_snapshot(self):
        for reading in self:
            if reading.meter_id:
                reading.rate_snapshot = reading.meter_id.rate
                if not reading.contract_id and reading.meter_id.unit_id:
                    contract = self.env['leasing.contract'].search([
                        ('unit_id', '=', reading.meter_id.unit_id.id),
                        ('state', '=', 'active'),
                    ], limit=1)
                    reading.contract_id = contract

    @api.constrains('current_reading', 'previous_reading')
    def _check_reading_values(self):
        for reading in self:
            if reading.current_reading < reading.previous_reading:
                raise UserError(_('Current reading cannot be less than previous reading.'))

    @api.depends('invoice_id')
    def _compute_utility_invoice_count(self):
        for reading in self:
            reading.utility_invoice_count = 1 if reading.invoice_id else 0

    def write(self, vals):
        if self._LOCKED_FIELDS_ON_BILLED.intersection(vals.keys()):
            billed_records = self.filtered('billed')
            if billed_records:
                raise UserError(_('You cannot modify meter/date/reading/rate fields after the reading is billed.'))
        return super().write(vals)

    def action_generate_utility_invoice(self):
        for reading in self:
            if reading.billed:
                continue
            if not reading.contract_id:
                raise UserError(_('No active contract found for this unit and reading date.'))
            if reading.amount <= 0:
                continue

            line = {
                'name': _('%s Utility Charge (%s)', reading.meter_id.display_name, reading.reading_date),
                'quantity': 1.0,
                'price_unit': reading.amount,
            }
            invoice = self.env['account.move'].create(
                reading.contract_id._prepare_invoice_vals_with_type(reading.reading_date, [line], 'utility')
            )
            reading.write({
                'billed': True,
                'invoice_id': invoice.id,
            })

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('No linked invoice found for this utility reading.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Utility Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
            'target': 'current',
        }
