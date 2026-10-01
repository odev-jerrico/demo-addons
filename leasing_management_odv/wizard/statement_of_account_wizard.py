# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LeasingStatementOfAccountWizard(models.TransientModel):
    _name = 'leasing.statement.of.account.wizard'
    _description = 'Leasing Statement Of Account Wizard'

    contract_id = fields.Many2one('leasing.contract', required=True, readonly=True)
    statement_date = fields.Date(required=True, default=fields.Date.context_today)
    line_ids = fields.One2many('leasing.statement.of.account.wizard.line', 'wizard_id', string='Invoices')

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        contract, invoices = self._resolve_contract_and_invoices_from_context()
        if contract:
            vals['contract_id'] = contract.id
            vals['line_ids'] = self._build_line_commands(invoices)
        return vals

    @api.model
    def _resolve_contract_and_invoices_from_context(self):
        contract = self.env['leasing.contract']
        invoices = self.env['account.move']

        if self.env.context.get('default_contract_id'):
            contract = self.env['leasing.contract'].browse(self.env.context['default_contract_id']).exists()
        elif self.env.context.get('active_model') == 'leasing.contract' and self.env.context.get('active_id'):
            contract = self.env['leasing.contract'].browse(self.env.context['active_id']).exists()

        selected_invoice_ids = self.env.context.get('default_invoice_ids')
        if isinstance(selected_invoice_ids, (list, tuple)) and selected_invoice_ids:
            first = selected_invoice_ids[0]
            if isinstance(first, (list, tuple)) and len(first) == 3 and first[0] == 6:
                selected_invoice_ids = first[2]
        if not selected_invoice_ids and self.env.context.get('active_model') == 'account.move':
            selected_invoice_ids = self.env.context.get('active_ids', [])

        if selected_invoice_ids:
            invoices = self.env['account.move'].browse(selected_invoice_ids).exists().filtered(
                lambda m: m.move_type == 'out_invoice' and m.state != 'cancel'
            )
            if invoices:
                contracts = invoices.mapped('lease_contract_id')
                if len(contracts) != 1:
                    raise UserError(_('Please select invoices from exactly one lease contract.'))
                contract = contracts
        elif contract:
            invoices = contract.invoice_ids.filtered(
                lambda m: m.move_type == 'out_invoice' and m.state != 'cancel'
            )

        return contract, invoices

    @api.model
    def _build_line_commands(self, invoices):
        sorted_invoices = invoices.sorted(
            lambda inv: (inv.invoice_date_due or inv.invoice_date or fields.Date.context_today(self), inv.id)
        )
        return [(5, 0, 0)] + [(0, 0, {'invoice_id': invoice.id}) for invoice in sorted_invoices]

    def action_print_statement(self):
        self.ensure_one()
        invoices = self._get_selected_invoices()
        if not invoices:
            raise UserError(_('Select at least one invoice to generate the statement of account.'))
        return self.env.ref('leasing_management_odv.action_report_leasing_statement_of_account').report_action(self)

    def _get_selected_invoices(self):
        self.ensure_one()
        invoices = self.line_ids.mapped('invoice_id').filtered(lambda inv: inv)
        return invoices.sorted(lambda inv: (inv.invoice_date_due or inv.invoice_date or fields.Date.context_today(self), inv.id))

    def _get_report_meter_readings(self):
        self.ensure_one()
        selected_invoices = self._get_selected_invoices()
        Reading = self.env['leasing.utility.reading']

        readings = Reading.search([
            ('invoice_id', 'in', selected_invoices.ids),
        ], order='reading_date asc, id asc')
        if readings:
            return readings

        if selected_invoices:
            dates = [d for d in selected_invoices.mapped('invoice_date') if d]
            start_date = min(dates) if dates else self.contract_id.date_start
            end_date = max(dates) if dates else self.statement_date
            return Reading.search([
                ('contract_id', '=', self.contract_id.id),
                ('reading_date', '>=', start_date),
                ('reading_date', '<=', end_date),
            ], order='reading_date asc, id asc')

        return Reading.search([
            ('contract_id', '=', self.contract_id.id),
        ], order='reading_date asc, id asc')


class LeasingStatementOfAccountWizardLine(models.TransientModel):
    _name = 'leasing.statement.of.account.wizard.line'
    _description = 'Leasing Statement Of Account Wizard Line'

    wizard_id = fields.Many2one('leasing.statement.of.account.wizard', required=True, ondelete='cascade')
    invoice_id = fields.Many2one('account.move', required=True)

    lease_invoice_type = fields.Selection(related='invoice_id.lease_invoice_type', readonly=True)
    invoice_date = fields.Date(related='invoice_id.invoice_date', readonly=True)
    invoice_date_due = fields.Date(related='invoice_id.invoice_date_due', readonly=True)
    amount_total = fields.Monetary(related='invoice_id.amount_total', readonly=True)
    amount_residual = fields.Monetary(related='invoice_id.amount_residual', readonly=True)
    payment_state = fields.Selection(related='invoice_id.payment_state', readonly=True)
    currency_id = fields.Many2one(related='invoice_id.currency_id', readonly=True)
