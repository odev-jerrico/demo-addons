from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSaleOrderCompanySplit(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Split Destination"})
        cls.env.user.write({"company_ids": [Command.link(cls.company_b.id)]})
        cls.product_a = cls.env["product.product"].create({
            "name": "Company A Product",
            "owning_company_id": cls.company_a.id,
            "list_price": 10,
        })
        cls.product_b = cls.env["product.product"].create({
            "name": "Company B Product",
            "owning_company_id": cls.company_b.id,
            "list_price": 20,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Split Customer"})

    def _order(self):
        return self.env["sale.order"].create({
            "company_id": self.company_a.id,
            "partner_id": self.partner.id,
            "order_line": [
                Command.create({"product_id": self.product_a.id, "product_uom_qty": 2, "price_unit": 10}),
                Command.create({"product_id": self.product_b.id, "product_uom_qty": 3, "price_unit": 20}),
            ],
        })

    def test_split_moves_lines_without_duplication(self):
        order = self._order()
        wizard = self.env["sale.order.split.wizard"].with_context(
            default_source_sale_order_id=order.id,
        ).create({})

        result = wizard.action_split()

        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(len(order.split_sale_order_ids), 1)
        split = order.split_sale_order_ids
        self.assertEqual(split.company_id, self.company_b)
        self.assertEqual(split.order_line.product_id, self.product_b)
        self.assertEqual(order.order_line.product_id, self.product_a)
        self.assertEqual(split.order_line.product_uom_qty, 3)

    def test_confirmation_rejects_mismatched_product(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            order.action_confirm()
