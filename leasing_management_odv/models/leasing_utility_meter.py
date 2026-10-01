# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LeasingUtilityMeter(models.Model):
    _name = 'leasing.utility.meter'
    _description = 'Leasing Utility Meter'
    _rec_name = 'display_name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    unit_id = fields.Many2one('leasing.unit', required=True)
    meter_type = fields.Selection([
        ('electricity', 'Electricity'),
        ('water', 'Water'),
        ('other', 'Other'),
    ], required=True, default='electricity')
    unit_of_measure = fields.Char(default='kWh')
    rate = fields.Float(string='Rate per Unit', required=True, default=0.0)
    active = fields.Boolean(default=True)
    reading_ids = fields.One2many('leasing.utility.reading', 'meter_id')

    _sql_constraints = [
        ('leasing_utility_meter_code_company_uniq', 'unique(code, company_id)', 'Meter code must be unique per company.'),
    ]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for meter in self:
            meter.display_name = f"[{meter.code}] {meter.name}" if meter.code else meter.name
