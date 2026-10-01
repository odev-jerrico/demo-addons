# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LeasingUnit(models.Model):
    _name = 'leasing.unit'
    _description = 'Leasing Unit'
    _rec_name = 'display_name'
    _order = 'code, id'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    floor = fields.Char()
    area_sqm = fields.Float(string='Area (sqm)', default=0.0)
    base_rent = fields.Monetary(currency_field='currency_id')
    service_charge = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True, readonly=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Maintenance'),
        ('inactive', 'Inactive'),
    ], default='draft', required=True)
    tenant_id = fields.Many2one('res.partner', string='Current Tenant', readonly=True, copy=False)
    active_contract_id = fields.Many2one('leasing.contract', compute='_compute_active_contract_id', store=False)
    contract_ids = fields.One2many('leasing.contract', 'unit_id', string='Contracts')
    meter_ids = fields.One2many('leasing.utility.meter', 'unit_id', string='Utility Meters', copy=False)

    _sql_constraints = [
        ('leasing_unit_code_company_uniq', 'unique(code, company_id)', 'Unit code must be unique per company.'),
    ]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for unit in self:
            unit.display_name = f"[{unit.code}] {unit.name}" if unit.code else unit.name

    def _compute_active_contract_id(self):
        active_contracts = self.env['leasing.contract'].search([
            ('unit_id', 'in', self.ids),
            ('state', '=', 'active'),
        ])
        mapped = {contract.unit_id.id: contract.id for contract in active_contracts}
        for unit in self:
            unit.active_contract_id = mapped.get(unit.id)

    def action_mark_available(self):
        self.write({'status': 'available', 'tenant_id': False})

    def action_mark_maintenance(self):
        self.write({'status': 'maintenance'})

    def action_mark_inactive(self):
        self.write({'status': 'inactive', 'tenant_id': False})

    @api.model
    def _next_copy_code(self, model_name, base_code, company_id):
        model = self.env[model_name]
        candidate = f"{base_code}-COPY"
        seq = 2
        while model.search_count([('code', '=', candidate), ('company_id', '=', company_id)]):
            candidate = f"{base_code}-COPY-{seq}"
            seq += 1
        return candidate

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.setdefault('code', self._next_copy_code(self._name, self.code, self.company_id.id))
        default.setdefault('status', 'draft')
        default.setdefault('tenant_id', False)

        new_unit = super().copy(default)

        for meter in self.meter_ids:
            meter_vals = meter.copy_data()[0]
            meter_vals.update({
                'unit_id': new_unit.id,
                'company_id': new_unit.company_id.id,
                'code': self._next_copy_code('leasing.utility.meter', meter.code, new_unit.company_id.id),
            })
            self.env['leasing.utility.meter'].create(meter_vals)

        return new_unit
