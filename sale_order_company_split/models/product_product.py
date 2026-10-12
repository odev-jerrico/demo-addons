from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    brand_id = fields.Many2one(
        related="product_tmpl_id.brand_id",
        string="Brand",
        readonly=False,
    )
    owning_company_id = fields.Many2one(
        related="product_tmpl_id.owning_company_id",
        string="Owning Company",
        readonly=False,
        domain="[(\"active\", \"=\", True)]",
    )
