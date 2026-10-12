# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductPermitLot(models.Model):
    _name = 'product.permit.lot'
    _description = 'Product Permit Lot'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, id desc'

    name = fields.Char(string='Permit Lot', required=True, copy=False, default='New', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        store=True,
        readonly=True,
        index=True,
    )
    product_id = fields.Many2one('product.product', string='Product', required=True, tracking=True, index=True, ondelete='restrict')
    lot_id = fields.Many2one('stock.lot', string='Lot/Batch', required=False, tracking=True, index=True, ondelete='restrict')
    permit_number = fields.Char(string='Permit Number', required=True, tracking=True)
    permit_type = fields.Selection([
        ('accreditation', 'Accreditation'),
        ('permit', 'Permit'),
        ('certificate', 'Certificate'),
    ], string='Permit Type', required=True, default='permit', tracking=True)
    registration_date = fields.Date(string='Registration Date', tracking=True)
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    warning_days = fields.Integer(string='Warning Days', default=30, help='Days before expiry to trigger the early warning.')
    state = fields.Selection([
        ('none', 'No Expiry Set'),
        ('valid', 'Valid'),
        ('warning', 'Near Expiry'),
        ('expired', 'Expired'),
    ], string='Permit Status', compute='_compute_expiry_status', store=True, tracking=True)
    days_remaining = fields.Integer(string='Days Remaining', compute='_compute_expiry_status', store=True)
    is_expired = fields.Boolean(string='Expired', compute='_compute_expiry_status', store=True)
    is_near_expiry = fields.Boolean(string='Near Expiry', compute='_compute_expiry_status', store=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'registration_expiry_valid',
            "CHECK((registration_date IS NULL) OR (expiry_date IS NULL) OR (expiry_date >= registration_date))",
            'Expiry date must be greater than or equal to the registration date.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('product.permit.lot') or 'New'
            if vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                if product.exists() and not vals.get('product_tmpl_id'):
                    vals['product_tmpl_id'] = product.product_tmpl_id.id
            elif vals.get('product_tmpl_id'):
                template = self.env['product.template'].browse(vals['product_tmpl_id'])
                if template.exists() and template.product_variant_id:
                    vals['product_id'] = template.product_variant_id.id
        return super().create(vals_list)

    @api.constrains('registration_date', 'expiry_date')
    def _check_registration_expiry_dates(self):
        for record in self:
            if record.registration_date and record.expiry_date and record.expiry_date < record.registration_date:
                raise ValidationError(_('Expiry date must be greater than or equal to the registration date.'))

    @api.depends('expiry_date', 'warning_days')
    def _compute_expiry_status(self):
        today = fields.Date.context_today(self)
        for record in self:
            if not record.expiry_date:
                record.state = 'none'
                record.days_remaining = 0
                record.is_expired = False
                record.is_near_expiry = False
                continue

            delta_days = (record.expiry_date - today).days
            record.days_remaining = delta_days
            record.is_expired = delta_days < 0
            record.is_near_expiry = delta_days >= 0 and delta_days <= (record.warning_days or 0)

            if record.is_expired:
                record.state = 'expired'
            elif record.is_near_expiry:
                record.state = 'warning'
            else:
                record.state = 'valid'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and self.lot_id and self.lot_id.product_id != self.product_id:
            self.lot_id = False
        if self.product_id:
            return {'domain': {'lot_id': [('product_id', '=', self.product_id.id)]}}
        return {'domain': {'lot_id': []}}

    def _cron_expiry_warning(self):
        warning_records = self.search([
            ('expiry_date', '!=', False),
            ('state', '=', 'warning'),
            ('active', '=', True),
        ])
        for record in warning_records:
            if record.product_id:
                record.product_id.message_post(
                    body=_(
                        'Permit alert: %s for %s will expire on %s in %s days.'
                    ) % (record.permit_number, record.product_id.display_name, record.expiry_date, record.days_remaining),
                    subject='Permit Expiry Warning'
                )
        return len(warning_records)

    def action_view_product(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_mode': 'form',
            'res_id': self.product_id.id,
            'target': 'current',
        }
