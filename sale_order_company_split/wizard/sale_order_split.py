from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class SaleOrderSplitDetail(models.TransientModel):
    _name = "sale.order.split.detail"
    _description = "Sales Order Split Detail"
    _order = "owning_company_id"

    wizard_id = fields.Many2one(
        comodel_name="sale.order.split.wizard",
        required=True,
        ondelete="cascade",
    )
    owning_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Owning Company",
        required=True,
        domain="[(\"active\", \"=\", True)]",
    )
    original_owning_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Original Owning Company",
        readonly=True,
    )
    sale_order_line_ids = fields.Many2many(
        comodel_name="sale.order.line",
        relation="sale_order_split_detail_line_rel",
        column1="detail_id",
        column2="line_id",
        string="Sales Order Lines",
        readonly=True,
    )
    source_line_ids = fields.Json(
        string="Source Line IDs",
        readonly=True,
    )
    keep_on_original_order = fields.Boolean(
        string="Keep on Original Order",
        compute="_compute_keep_on_original_order",
        readonly=True,
    )
    product_summary = fields.Char(string="Products", compute="_compute_product_summary")
    quantity = fields.Float(compute="_compute_totals")
    subtotal = fields.Monetary(compute="_compute_totals")
    currency_id = fields.Many2one(related="wizard_id.source_sale_order_id.currency_id")
    can_override = fields.Boolean(related="wizard_id.can_override", readonly=True)

    @api.depends("owning_company_id", "wizard_id.source_sale_order_id.company_id")
    def _compute_keep_on_original_order(self):
        for detail in self:
            detail.keep_on_original_order = (
                detail.owning_company_id == detail.wizard_id.source_sale_order_id.company_id
            )

    @api.depends("sale_order_line_ids.product_id", "sale_order_line_ids.product_uom_qty")
    def _compute_product_summary(self):
        for detail in self:
            detail.product_summary = ", ".join(detail.sale_order_line_ids.mapped("product_id.display_name"))

    @api.depends("sale_order_line_ids.product_uom_qty", "sale_order_line_ids.price_subtotal")
    def _compute_totals(self):
        for detail in self:
            detail.quantity = sum(detail.sale_order_line_ids.mapped("product_uom_qty"))
            detail.subtotal = sum(detail.sale_order_line_ids.mapped("price_subtotal"))


class SaleOrderSplitWizard(models.TransientModel):
    _name = "sale.order.split.wizard"
    _description = "Sales Order Splitting Wizard"

    source_sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Source Sales Order",
        required=True,
        readonly=True,
    )
    source_company_id = fields.Many2one(
        related="source_sale_order_id.company_id",
        string="Assigned Company",
        readonly=True,
    )
    split_detail_ids = fields.One2many(
        comodel_name="sale.order.split.detail",
        inverse_name="wizard_id",
        string="Split Details",
    )
    can_override = fields.Boolean(compute="_compute_can_override")

    def _compute_can_override(self):
        can_override = self.env.user.has_group("sales_team.group_sale_manager")
        for wizard in self:
            wizard.can_override = can_override

    def _restore_detail_lines(self, source):
        for detail in self.split_detail_ids:
            line_ids = detail.source_line_ids or detail.sale_order_line_ids.ids
            if not line_ids and detail.original_owning_company_id:
                line_ids = source.order_line.filtered(
                    lambda line: line.product_id
                    and not line.display_type
                    and not line.is_downpayment
                    and line.product_id.product_tmpl_id.owning_company_id
                    == detail.original_owning_company_id
                ).ids
            detail.sale_order_line_ids = [Command.set(line_ids)]

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        source = self.env["sale.order"].browse(values.get("source_sale_order_id")).exists()
        if source:
            source._check_split_allowed()
            missing = source.order_line.filtered(
                lambda line: line.product_id
                and not line.display_type
                and not line.is_downpayment
                and not line.product_id.product_tmpl_id.owning_company_id
            )
            if missing:
                raise UserError(_("Every product line must have an Owning Company before splitting."))
            detail_commands = []
            groups = defaultdict(lambda: self.env["sale.order.line"])
            for line in source.order_line.filtered(
                lambda line: line.product_id and not line.display_type and not line.is_downpayment
            ):
                company = line.product_id.product_tmpl_id.owning_company_id
                if company:
                    groups[company.id] |= line
            for company_id, lines in groups.items():
                detail_commands.append(Command.create({
                    "owning_company_id": company_id,
                    "original_owning_company_id": company_id,
                    "sale_order_line_ids": [Command.set(lines.ids)],
                    "source_line_ids": lines.ids,
                }))
            values["split_detail_ids"] = detail_commands
        return values

    def action_split(self):
        self.ensure_one()
        source = self.source_sale_order_id
        if not source:
            raise UserError(_("Select a source sales order."))
        source._check_split_allowed()
        self._restore_detail_lines(source)
        if any(
            detail.owning_company_id != line.product_id.product_tmpl_id.owning_company_id
            for detail in self.split_detail_ids
            for line in detail.sale_order_line_ids
        ) and not self.can_override:
            raise UserError(_("Only Sales Managers can override a product's Owning Company."))
        details = self.split_detail_ids
        line_ids = details.sale_order_line_ids.ids
        expected_line_ids = source.order_line.filtered(
            lambda line: line.product_id and not line.display_type and not line.is_downpayment
        ).ids
        if set(line_ids) != set(expected_line_ids):
            raise UserError(_("The split preview is out of date. Close the wizard and open it again."))
        created = source._execute_company_split(details)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "sticky": True,
                "message": _(
                    "Sales order %s was split successfully. Created orders: %s",
                    source.name,
                    ", ".join(created.mapped("name")) or _("none"),
                ),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
