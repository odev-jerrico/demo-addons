from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    default_owning_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Default Owning Company",
        domain="[(\"active\", \"=\", True)]",
        tracking=True,
    )
