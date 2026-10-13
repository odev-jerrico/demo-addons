from odoo import fields, models


class PurchaseApprovalLevel(models.Model):
    _inherit = "purchase.approval.level"

    branch_ids = fields.Many2many(
        comodel_name="res.company",
        relation="purchase_approval_level_branch_rel",
        column1="approval_level_id",
        column2="branch_id",
        string="Branches",
        help="For intercompany purchase orders, apply this level when either company is one of these branches.",
    )
