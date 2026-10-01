# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class LeasingMaintenanceRequest(models.Model):
    _name = 'leasing.maintenance.request'
    _description = 'Leasing Maintenance Request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(required=True, copy=False, default='New', tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    tenant_id = fields.Many2one('res.partner', required=True, tracking=True)
    unit_id = fields.Many2one('leasing.unit', required=True, tracking=True)
    contract_id = fields.Many2one('leasing.contract', tracking=True)

    request_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    description = fields.Text(required=True)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], default='1', required=True, tracking=True)
    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled'),
    ], default='new', required=True, tracking=True)
    assigned_user_id = fields.Many2one('res.users', string='Assigned To', tracking=True)
    resolution_notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('leasing.maintenance.request') or 'New'
            if not vals.get('tenant_id') and self.env.user.partner_id:
                vals['tenant_id'] = self.env.user.partner_id.id
        records = super().create(vals_list)
        for record in records:
            if not record.contract_id:
                contract = self.env['leasing.contract'].search([
                    ('unit_id', '=', record.unit_id.id),
                    ('tenant_id', '=', record.tenant_id.id),
                    ('state', '=', 'active'),
                ], limit=1)
                if contract:
                    record.contract_id = contract.id
        return records

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_resolve(self):
        self.write({'state': 'resolved'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def _compute_access_url(self):
        super()._compute_access_url()
        for request in self:
            request.access_url = '/my/leasing/maintenance/%s' % request.id
