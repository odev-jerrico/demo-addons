from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("odev", "purchase_approval_matrix_branch", "post_install", "-at_install")
class TestPurchaseApprovalMatrixBranch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Purchase = cls.env["purchase.order"]
        cls.approver = cls.env.ref("base.user_admin")
        cls.product = cls.env["product.product"].create({
            "name": "Branch Approval Test Product",
            "type": "service",
        })
        cls.source_company = cls.env["res.company"].create({
            "name": "Branch Source Company",
            "parent_id": cls.env.company.id,
        })
        cls.destination_company = cls.env["res.company"].create({
            "name": "Branch Destination Company",
            "parent_id": cls.env.company.id,
        })
        cls.vendor = cls.source_company.partner_id

    def _create_purchase(self):
        return self.Purchase.with_company(self.destination_company).create({
            "company_id": self.destination_company.id,
            "partner_id": self.vendor.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 100,
                "tax_ids": False,
            })],
        })

    def test_branch_level_matches_intercompany_purchase(self):
        level = self.env["purchase.approval.level"].create({
            "threshold_amount": 25,
            "approver_ids": [(4, self.approver.id)],
            "branch_ids": [(6, 0, [self.source_company.id])],
        })
        purchase = self._create_purchase()

        purchase.add_approvals()

        self.assertTrue(purchase.approval_ids)
        self.assertEqual(purchase.approval_ids.approver_ids, self.approver)
        self.assertEqual(purchase.approval_ids.threshold_amount, level.threshold_amount)

    def test_branch_level_does_not_match_non_intercompany_purchase(self):
        level = self.env["purchase.approval.level"].create({
            "threshold_amount": 25,
            "approver_ids": [(4, self.approver.id)],
            "branch_ids": [(6, 0, [self.source_company.id])],
        })
        purchase = self.Purchase.with_company(self.destination_company).create({
            "company_id": self.destination_company.id,
            "partner_id": self.env.ref("base.partner_root").id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 100,
                "tax_ids": False,
            })],
        })

        purchase.add_approvals()

        self.assertFalse(purchase.approval_ids)
        self.assertTrue(level)
