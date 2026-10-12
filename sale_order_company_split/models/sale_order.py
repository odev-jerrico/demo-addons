from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    origin_sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Original Sales Order",
        copy=False,
        index=True,
        ondelete="restrict",
    )
    split_sale_order_ids = fields.One2many(
        comodel_name="sale.order",
        inverse_name="origin_sale_order_id",
        string="Split Sales Orders",
        copy=False,
    )
    split_sale_order_count = fields.Integer(
        string="Split Sales Orders",
        compute="_compute_split_sale_order_count",
    )
    company_assignment_override = fields.Boolean(
        string="Owning Company Override",
        copy=False,
        help="The order was created from an authorized owning-company override in the split wizard.",
    )

    def _compute_split_sale_order_count(self):
        for order in self:
            order.split_sale_order_count = len(order.split_sale_order_ids)

    def _company_mismatch_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda line: line.product_id
            and not line.display_type
            and not line.is_downpayment
            and line.product_id.product_tmpl_id.owning_company_id != self.company_id
        )

    def _owning_company_errors(self):
        self.ensure_one()
        missing = self.order_line.filtered(
            lambda line: line.product_id
            and not line.display_type
            and not line.is_downpayment
            and not line.product_id.product_tmpl_id.owning_company_id
        )
        if missing:
            return _(
                "Every product on sales order %s must have an Owning Company."
            ) % self.display_name
        mismatch = self._company_mismatch_lines() if not self.company_assignment_override else self.env["sale.order.line"]
        if mismatch:
            companies = ", ".join(mismatch.mapped("product_id.product_tmpl_id.owning_company_id.name"))
            return _(
                "Sales order %s contains products owned by another company (%s). "
                "Correct the lines or split the sales order before confirming it."
            ) % (self.display_name, companies)
        return False

    def action_confirm(self):
        for order in self:
            error = order._owning_company_errors()
            if error:
                raise ValidationError(error)
        return super().action_confirm()

    def action_open_company_split_wizard(self):
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            raise UserError(_("Only draft quotations or sent quotations can be split."))
        if self.split_sale_order_ids:
            raise UserError(_("This sales order has already been split."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Split Sales Order"),
            "res_model": "sale.order.split.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_source_sale_order_id": self.id},
        }

    def action_view_split_sale_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Split Sales Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.split_sale_order_ids.ids)],
            "context": {"create": False},
        }

    def _check_split_allowed(self):
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            raise UserError(_("Sales order %s cannot be split after confirmation or cancellation.") % self.display_name)
        if self.split_sale_order_ids:
            raise UserError(_("Sales order %s has already been split.") % self.display_name)
        if self.invoice_ids or self.order_line.filtered(lambda line: line.qty_delivered or line.qty_invoiced):
            raise UserError(_(
                "Sales order %s cannot be split because it has delivered or invoiced lines. "
                "Resolve downstream transactions using standard Odoo procedures first."
            ) % self.display_name)
        if "move_ids" in self.env["sale.order.line"]._fields and self.order_line.filtered(
            lambda line: line.move_ids.filtered(lambda move: move.state != "cancel")
        ):
            raise UserError(_("Sales order %s has stock moves and cannot be split.") % self.display_name)

    def _execute_company_split(self, details):
        self.ensure_one()
        self._check_split_allowed()
        missing = self.order_line.filtered(
            lambda line: not line.display_type
            and not line.is_downpayment
            and line.product_id
            and not line.product_id.product_tmpl_id.owning_company_id
        )
        if missing:
            raise ValidationError(_("All affected products must have an Owning Company before splitting."))

        lines_by_company = defaultdict(lambda: self.env["sale.order.line"])
        override_by_company = {}
        for detail in details:
            if detail.keep_on_original_order:
                continue
            for line in detail.sale_order_line_ids:
                product_company = line.product_id.product_tmpl_id.owning_company_id
                target_company = detail.owning_company_id
                if product_company != target_company and not self.env.user.has_group(
                    "sales_team.group_sale_manager"
                ):
                    raise ValidationError(_("A line can only be assigned to its product's Owning Company."))
                lines_by_company[target_company.id] |= line
                override_by_company[target_company.id] = override_by_company.get(target_company.id, False) or (
                    product_company != target_company
                )

        created_orders = self.env["sale.order"]
        for company_id, lines in lines_by_company.items():
            if company_id == self.company_id.id or not lines:
                continue
            company = self.env["res.company"].browse(company_id).exists()
            if not company or not company.active or company not in self.env.user.company_ids:
                raise UserError(_("You do not have access to the destination company."))
            order_vals = self.with_company(company).copy_data({
                "company_id": company.id,
                "origin_sale_order_id": self.id,
                "order_line": [],
                "company_assignment_override": override_by_company.get(company_id, False),
            })[0]
            order_vals["name"] = _("New")
            if "warehouse_id" in self.env["sale.order"]._fields:
                warehouse_id = self.env["ir.default"].with_company(
                    company.id
                )._get_model_defaults("sale.order").get("warehouse_id")
                warehouse = self.env["stock.warehouse"].browse(warehouse_id).exists()
                if not warehouse:
                    warehouse = self.env.user.with_company(
                        company.id
                    )._get_default_warehouse_id()
                if (
                    not warehouse
                    or not warehouse.active
                    or warehouse.company_id != company
                ):
                    raise UserError(_(
                        "Company %s has no valid default warehouse for the split sales order."
                    ) % company.display_name)
                order_vals["warehouse_id"] = warehouse.id
            for field_name in ("pricelist_id", "payment_term_id", "fiscal_position_id", "team_id"):
                record = self.env["sale.order"]._fields[field_name]
                value = order_vals.get(field_name)
                related = self.env[record.comodel_name].browse(value).exists() if value else self.env[record.comodel_name]
                if related and "company_id" in related._fields and related.company_id not in (False, company):
                    order_vals[field_name] = False
            # Company-dependent computes (taxes, currency, fiscal position) must run in the destination company.
            new_order = self.env["sale.order"].with_company(company).create(order_vals)
            lines.with_company(company).write({"order_id": new_order.id})
            created_orders |= new_order

        if created_orders:
            self.message_post(body=_(
                "Split into %s.",
                ", ".join(created_orders.mapped("name")),
            ))
        return created_orders
