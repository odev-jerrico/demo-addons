from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    brand_id = fields.Many2one(
        comodel_name="product.brand",
        string="Brand",
        help="Brand associated with this product.",
    )
    owning_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Owning Company",
        domain="[(\"active\", \"=\", True)]",
        tracking=True,
        help="Company responsible for purchasing, owning, and selling this product.",
    )

    def _get_related_fields_variant_template(self):
        return super()._get_related_fields_variant_template() + [
            "brand_id",
            "owning_company_id",
        ]

    def _prepare_variant_values(self, combination):
        values = super()._prepare_variant_values(combination)
        values.update({
            "brand_id": self.brand_id.id,
            "owning_company_id": self.owning_company_id.id,
        })
        return values

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("owning_company_id"):
                category = self.env["product.category"].browse(vals.get("categ_id")).exists()
                if category.default_owning_company_id:
                    vals["owning_company_id"] = category.default_owning_company_id.id
        return super().create(vals_list)

    def write(self, vals):
        if "categ_id" in vals and "owning_company_id" not in vals:
            category = self.env["product.category"].browse(vals["categ_id"]).exists()
            if category.default_owning_company_id:
                vals = dict(vals, owning_company_id=category.default_owning_company_id.id)
        return super().write(vals)

    @api.constrains("owning_company_id")
    def _check_owning_company_active(self):
        inactive = self.filtered(lambda product: product.owning_company_id and not product.owning_company_id.active)
        if inactive:
            raise ValidationError(_("The owning company must be active."))
