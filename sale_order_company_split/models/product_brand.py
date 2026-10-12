from odoo import fields, models


class ProductBrand(models.Model):
    _name = "product.brand"
    _description = "Product Brand"
    _order = "name"

    name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
