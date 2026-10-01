# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class LeasingContract(models.Model):
    _name = 'leasing.contract'
    _description = 'Leasing Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(required=True, copy=False, default='New', tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, store=True)

    unit_id = fields.Many2one('leasing.unit', required=True, tracking=True)
    tenant_id = fields.Many2one('res.partner', required=True, tracking=True, domain="[('is_company', '=', True)]")

    date_start = fields.Date(required=True, tracking=True)
    date_end = fields.Date(required=True, tracking=True)
    billing_day = fields.Integer(default=1, required=True)
    billing_interval = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ], default='monthly', required=True, tracking=True)
    annual_escalation_rate = fields.Float(string='Annual Escalation %', default=0.0, tracking=True)

    rent_amount = fields.Monetary(required=True, currency_field='currency_id')
    service_charge_amount = fields.Monetary(currency_field='currency_id')
    security_deposit_amount = fields.Monetary(currency_field='currency_id')
    advance_deposit_amount = fields.Monetary(currency_field='currency_id')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)

    next_invoice_date = fields.Date(copy=False)
    last_invoice_date = fields.Date(copy=False)

    invoice_ids = fields.One2many('account.move', 'lease_contract_id', string='Invoices')
    invoice_count = fields.Integer(compute='_compute_invoice_count')
    total_invoiced = fields.Monetary(compute='_compute_total_invoiced', currency_field='currency_id')
    payment_ids = fields.Many2many('account.payment', compute='_compute_payment_ids', string='Related Payments')
    meter_reading_ids = fields.One2many('leasing.utility.reading', 'contract_id', string='Meter Readings')
    meter_reading_count = fields.Integer(compute='_compute_meter_reading_count')
    maintenance_request_count = fields.Integer(compute='_compute_maintenance_request_count')

    total_contract_value = fields.Monetary(compute='_compute_contract_kpis', currency_field='currency_id')
    collected_to_date = fields.Monetary(compute='_compute_contract_kpis', currency_field='currency_id')
    future_contracted_income = fields.Monetary(compute='_compute_contract_kpis', currency_field='currency_id')
    outstanding_overdue = fields.Monetary(compute='_compute_contract_kpis', currency_field='currency_id')

    deposit_invoice_id = fields.Many2one('account.move', copy=False)
    advance_deposit_invoice_id = fields.Many2one('account.move', copy=False)
    deposit_status = fields.Selection([
        ('not_invoiced', 'Not Invoiced'),
        ('invoiced', 'Invoiced'),
        ('paid', 'Paid'),
    ], compute='_compute_deposit_status')

    _sql_constraints = [
        ('leasing_contract_date_check', 'check(date_end >= date_start)', 'End date must be greater than or equal to start date.'),
    ]

    @api.constrains('billing_day')
    def _check_billing_day(self):
        for contract in self:
            if contract.billing_day < 1 or contract.billing_day > 28:
                raise ValidationError(_('Billing day must be between 1 and 28.'))

    @api.constrains('annual_escalation_rate')
    def _check_annual_escalation_rate(self):
        for contract in self:
            if contract.annual_escalation_rate < 0:
                raise ValidationError(_('Annual escalation rate cannot be negative.'))

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        grouped = self.env['account.move'].read_group(
            [('lease_contract_id', 'in', self.ids), ('move_type', '=', 'out_invoice')],
            ['lease_contract_id'],
            ['lease_contract_id'],
        )
        count_by_contract = {
            data['lease_contract_id'][0]: data['lease_contract_id_count']
            for data in grouped
            if data.get('lease_contract_id')
        }
        for contract in self:
            contract.invoice_count = count_by_contract.get(contract.id, 0)

    @api.depends('invoice_ids.amount_total_signed', 'invoice_ids.move_type')
    def _compute_total_invoiced(self):
        for contract in self:
            customer_invoices = contract.invoice_ids.filtered(
                lambda m: m.move_type == 'out_invoice' and m.state == 'posted'
            )
            contract.total_invoiced = sum(customer_invoices.mapped('amount_total_signed'))

    @api.depends('invoice_ids.reconciled_payment_ids')
    def _compute_payment_ids(self):
        for contract in self:
            payments = contract.invoice_ids.filtered(
                lambda m: m.move_type == 'out_invoice' and m.state == 'posted'
            ).mapped('reconciled_payment_ids')
            contract.payment_ids = payments

    @api.depends('meter_reading_ids')
    def _compute_meter_reading_count(self):
        grouped = self.env['leasing.utility.reading'].read_group(
            [('contract_id', 'in', self.ids)],
            ['contract_id'],
            ['contract_id'],
        )
        count_by_contract = {
            data['contract_id'][0]: data['contract_id_count']
            for data in grouped
            if data.get('contract_id')
        }
        for contract in self:
            contract.meter_reading_count = count_by_contract.get(contract.id, 0)

    @api.depends('unit_id', 'tenant_id')
    def _compute_maintenance_request_count(self):
        grouped = self.env['leasing.maintenance.request'].read_group(
            [('contract_id', 'in', self.ids)],
            ['contract_id'],
            ['contract_id'],
        )
        count_by_contract = {
            data['contract_id'][0]: data['contract_id_count']
            for data in grouped
            if data.get('contract_id')
        }
        for contract in self:
            contract.maintenance_request_count = count_by_contract.get(contract.id, 0)

    @api.depends(
        'invoice_ids.amount_total',
        'invoice_ids.amount_residual',
        'invoice_ids.payment_state',
        'invoice_ids.state',
        'invoice_ids.invoice_date',
        'invoice_ids.lease_invoice_type',
        'invoice_ids.move_type',
    )
    def _compute_contract_kpis(self):
        today = fields.Date.context_today(self)
        for contract in self:
            recurring = contract.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.state != 'cancel'
                and inv.lease_invoice_type == 'recurring'
            )

            contract.total_contract_value = sum(recurring.mapped('amount_total'))
            contract.collected_to_date = sum(
                max(inv.amount_total - inv.amount_residual, 0.0)
                for inv in recurring
                if inv.state == 'posted'
            )
            contract.future_contracted_income = sum(
                inv.amount_total
                for inv in recurring
                if inv.invoice_date and inv.invoice_date > today
            )
            contract.outstanding_overdue = sum(
                inv.amount_residual
                for inv in recurring
                if inv.state == 'posted'
                and inv.invoice_date
                and inv.invoice_date <= today
                and inv.payment_state not in ('paid', 'reversed')
            )

    @api.depends('deposit_invoice_id.payment_state', 'deposit_invoice_id.state')
    def _compute_deposit_status(self):
        for contract in self:
            if not contract.deposit_invoice_id:
                contract.deposit_status = 'not_invoiced'
            elif contract.deposit_invoice_id.payment_state == 'paid':
                contract.deposit_status = 'paid'
            else:
                contract.deposit_status = 'invoiced'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('leasing.contract') or 'New'
        return super().create(vals_list)

    def action_activate(self):
        for contract in self:
            if contract.state != 'draft':
                continue
            if contract.unit_id.status not in ('draft', 'available', 'occupied'):
                raise UserError(_('Unit must be draft, available, or occupied to activate contract.'))

            overlapping = self.search([
                ('id', '!=', contract.id),
                ('unit_id', '=', contract.unit_id.id),
                ('state', '=', 'active'),
                ('date_start', '<=', contract.date_end),
                ('date_end', '>=', contract.date_start),
            ], limit=1)
            if overlapping:
                raise UserError(_('An active contract already exists for this unit in the selected date range.'))

            contract.unit_id.write({
                'status': 'occupied',
                'tenant_id': contract.tenant_id.id,
            })
            contract.write({
                'state': 'active',
            })
            contract.action_generate_security_deposit_invoice()
            contract._rebuild_draft_invoice_schedule()
            contract._update_invoice_markers()

    def action_close(self):
        for contract in self:
            contract.write({'state': 'closed'})
            active_other = self.search([
                ('id', '!=', contract.id),
                ('unit_id', '=', contract.unit_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if not active_other:
                contract.unit_id.write({
                    'status': 'available',
                    'tenant_id': False,
                })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def _prepare_invoice_vals(self, invoice_date, line_vals):
        return self._prepare_invoice_vals_with_type(invoice_date, line_vals, 'recurring')

    def _prepare_invoice_vals_with_type(self, invoice_date, line_vals, invoice_type):
        self.ensure_one()
        return {
            'move_type': 'out_invoice',
            'partner_id': self.tenant_id.id,
            'invoice_date': invoice_date,
            'invoice_origin': self.name,
            'lease_contract_id': self.id,
            'lease_invoice_type': invoice_type,
            'invoice_line_ids': [(0, 0, line) for line in line_vals],
        }

    def action_generate_security_deposit_invoice(self):
        for contract in self:
            if contract.deposit_invoice_id or contract.advance_deposit_invoice_id:
                continue

            security_amount = contract.security_deposit_amount or 0.0
            advance_amount = contract.advance_deposit_amount or 0.0
            if security_amount <= 0 and advance_amount <= 0:
                continue

            lines = []
            if security_amount > 0:
                lines.append({
                    'name': _('Security Deposit - %s', contract.name),
                    'quantity': 1.0,
                    'price_unit': security_amount,
                })
            if advance_amount > 0:
                lines.append({
                    'name': _('Advance Deposit - %s', contract.name),
                    'quantity': 1.0,
                    'price_unit': advance_amount,
                })

            invoice = self.env['account.move'].create(
                contract._prepare_invoice_vals_with_type(fields.Date.context_today(self), lines, 'deposit')
            )
            values = {}
            if security_amount > 0:
                values['deposit_invoice_id'] = invoice.id
            if advance_amount > 0:
                values['advance_deposit_invoice_id'] = invoice.id
            if values:
                contract.write(values)

    def action_generate_rent_schedule(self):
        for contract in self:
            if contract.state != 'draft':
                continue
            contract._rebuild_draft_invoice_schedule()
            contract._update_invoice_markers()

    def action_post_due_invoices(self):
        today = fields.Date.context_today(self)
        for contract in self:
            due_invoices = contract.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.lease_invoice_type == 'recurring'
                and inv.state == 'draft'
                and inv.invoice_date
                and inv.invoice_date <= today
            )
            if due_invoices:
                due_invoices.action_post()
            contract._update_invoice_markers()

    def _get_interval_months(self):
        self.ensure_one()
        return {
            'monthly': 1,
            'quarterly': 3,
            'annually': 12,
        }[self.billing_interval]

    def _get_first_billing_date(self):
        self.ensure_one()
        billing_date = self.date_start + relativedelta(day=self.billing_day)
        if billing_date < self.date_start:
            billing_date += relativedelta(months=1)
        return billing_date

    def _get_expected_billing_dates(self):
        self.ensure_one()
        dates = []
        interval_months = self._get_interval_months()
        cursor = self._get_first_billing_date()
        while cursor <= self.date_end:
            dates.append(cursor)
            cursor += relativedelta(months=interval_months)
        return dates

    def _get_period_line_vals(self, invoice_date):
        self.ensure_one()
        years_elapsed = max(relativedelta(invoice_date, self.date_start).years, 0)
        escalation_multiplier = (1 + (self.annual_escalation_rate / 100.0)) ** years_elapsed
        escalated_rent = self.rent_amount * escalation_multiplier

        lines = [{
            'name': _('Base Rent - %s', self.unit_id.display_name),
            'quantity': 1.0,
            'price_unit': escalated_rent,
        }]
        if self.service_charge_amount:
            lines.append({
                'name': _('Service Charge - %s', self.unit_id.display_name),
                'quantity': 1.0,
                'price_unit': self.service_charge_amount,
            })
        return lines

    def _generate_draft_invoice_schedule(self):
        for contract in self:
            if not contract.date_start or not contract.date_end:
                continue

            billing_dates = contract._get_expected_billing_dates()
            existing_dates = set(contract.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.lease_invoice_type == 'recurring'
                and inv.state != 'cancel'
                and inv.invoice_date
            ).mapped('invoice_date'))

            vals_list = []
            for invoice_date in billing_dates:
                if invoice_date in existing_dates:
                    continue
                lines = contract._get_period_line_vals(invoice_date)
                vals_list.append(contract._prepare_invoice_vals_with_type(invoice_date, lines, 'recurring'))

            if vals_list:
                self.env['account.move'].create(vals_list)

            contract._update_invoice_markers()

    def _rebuild_draft_invoice_schedule(self):
        for contract in self:
            if not contract.date_start or not contract.date_end:
                continue

            expected_dates = set(contract._get_expected_billing_dates())
            draft_recurring = contract.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.lease_invoice_type == 'recurring'
                and inv.state == 'draft'
                and inv.invoice_date
            )
            posted_recurring_dates = set(contract.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.lease_invoice_type == 'recurring'
                and inv.state == 'posted'
                and inv.invoice_date
            ).mapped('invoice_date'))

            # Remove obsolete draft schedule invoices that are no longer part of expected periods.
            obsolete_draft_ids = [inv.id for inv in draft_recurring if inv.invoice_date not in expected_dates]
            obsolete_drafts = self.env['account.move'].browse(obsolete_draft_ids)
            if obsolete_drafts:
                obsolete_drafts.button_draft()
                obsolete_drafts.unlink()

            drafts_by_date = {
                inv.invoice_date: inv
                for inv in contract.invoice_ids.filtered(
                    lambda rec: rec.move_type == 'out_invoice'
                    and rec.lease_invoice_type == 'recurring'
                    and rec.state == 'draft'
                    and rec.invoice_date
                )
            }

            create_vals = []
            for invoice_date in sorted(expected_dates):
                if invoice_date in posted_recurring_dates:
                    continue

                lines = contract._get_period_line_vals(invoice_date)
                existing_draft = drafts_by_date.get(invoice_date)
                if existing_draft:
                    existing_draft.write({
                        'partner_id': contract.tenant_id.id,
                        'invoice_origin': contract.name,
                        'invoice_line_ids': [(5, 0, 0)] + [(0, 0, line) for line in lines],
                    })
                else:
                    create_vals.append(
                        contract._prepare_invoice_vals_with_type(invoice_date, lines, 'recurring')
                    )

            if create_vals:
                self.env['account.move'].create(create_vals)

    def _update_invoice_markers(self):
        for contract in self:
            recurring = contract.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice' and inv.lease_invoice_type == 'recurring'
            )
            posted_dates = sorted(recurring.filtered(lambda inv: inv.state == 'posted' and inv.invoice_date).mapped('invoice_date'))
            draft_dates = sorted(recurring.filtered(lambda inv: inv.state == 'draft' and inv.invoice_date).mapped('invoice_date'))
            contract.last_invoice_date = posted_dates[-1] if posted_dates else False
            contract.next_invoice_date = draft_dates[0] if draft_dates else False

    @api.model
    def _cron_generate_monthly_soa(self):
        contracts = self.search([
            ('state', '=', 'active'),
            ('date_end', '>=', fields.Date.context_today(self)),
        ])
        contracts._generate_draft_invoice_schedule()
        contracts.action_post_due_invoices()

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['domain'] = [('lease_contract_id', '=', self.id)]
        action['context'] = {
            'default_lease_contract_id': self.id,
            'default_partner_id': self.tenant_id.id,
            'show_lease_invoice_type': True,
        }
        return action

    def action_view_meter_readings(self):
        self.ensure_one()
        action = self.env.ref('leasing_management_odv.action_leasing_utility_reading').read()[0]
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {
            'default_contract_id': self.id,
            'default_unit_id': self.unit_id.id,
        }
        return action

    def action_view_maintenance_requests(self):
        self.ensure_one()
        action = self.env.ref('leasing_management_odv.action_leasing_maintenance_request').read()[0]
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {
            'default_contract_id': self.id,
            'default_unit_id': self.unit_id.id,
            'default_tenant_id': self.tenant_id.id,
        }
        return action

    def action_open_statement_of_account_wizard(self):
        self.ensure_one()
        action = self.env.ref('leasing_management_odv.action_leasing_statement_of_account_wizard').read()[0]
        action['context'] = {
            'default_contract_id': self.id,
            'active_model': 'leasing.contract',
            'active_id': self.id,
            'active_ids': [self.id],
        }
        return action


class AccountMove(models.Model):
    _inherit = 'account.move'

    lease_contract_id = fields.Many2one('leasing.contract', index=True, copy=False)
    lease_invoice_type = fields.Selection([
        ('recurring', 'Recurring Rent'),
        ('utility', 'Utility Charge'),
        ('deposit', 'Deposit'),
        ('advance_deposit', 'Advance Deposit'),
        ('manual', 'Manual Adjustment'),
    ], default='recurring', copy=False, index=True)

    def action_open_statement_of_account_wizard_from_selection(self):
        invoices = self.filtered(lambda m: m.move_type == 'out_invoice' and m.state != 'cancel')
        if not invoices:
            raise UserError(_('Please select at least one customer invoice.'))

        contracts = invoices.mapped('lease_contract_id')
        if any(not inv.lease_contract_id for inv in invoices):
            raise UserError(_('All selected invoices must belong to a lease contract.'))
        if len(contracts) != 1:
            raise UserError(_('Please select invoices from exactly one lease contract.'))

        contract = contracts[0]
        wizard = self.env['leasing.statement.of.account.wizard'].create({
            'contract_id': contract.id,
            'line_ids': [(0, 0, {'invoice_id': inv.id}) for inv in invoices],
        })

        action = self.env.ref('leasing_management_odv.action_leasing_statement_of_account_wizard').read()[0]
        action['res_id'] = wizard.id
        action['context'] = {
            'default_contract_id': contract.id,
            'default_invoice_ids': [(6, 0, invoices.ids)],
            'active_model': 'account.move',
            'active_ids': invoices.ids,
        }
        return action


class ResPartner(models.Model):
    _inherit = 'res.partner'

    leasing_contract_ids = fields.One2many('leasing.contract', 'tenant_id', string='Lease Contracts')
    leasing_unit_ids = fields.One2many('leasing.unit', 'tenant_id', string='Current Leased Units')
