from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _branch_approval_level_matches(self, level):
        self.ensure_one()
        if not level.branch_ids:
            return True

        vendor_companies = self.partner_id.ref_company_ids
        if not vendor_companies:
            return False

        intercompany_companies = vendor_companies | self.company_id
        return bool(level.branch_ids & intercompany_companies)

    def add_approvals(self):
        self.ensure_one()
        approval_level_obj = self.env["purchase.approval.level"]
        user_obj = self.env["res.users"]
        approval_levels = approval_level_obj.search([
            "|", ("company_id", "=", False),
            ("company_id", "=", self.company_id.id),
        ])
        approval_dicts = []
        user = self.user_id or self.env.user
        existing_approvers = user_obj
        for approval in self.approval_ids:
            existing_approvers |= approval.approver_ids
        for level in approval_levels.filtered(lambda x:
            (not x.requester_ids or user in x.requester_ids) and
            (not x.department_ids or user.department_id in x.department_ids) and
            self._branch_approval_level_matches(x)):
            if level.threshold_amount <= self.amount_total_cc and (
                not level.maximum_amount or level.maximum_amount >= self.amount_total_cc
            ):
                approvers = level.approver_ids
                if level.include_manager and user.employee_id.parent_id.user_id:
                    approvers |= user.employee_id.parent_id.user_id
                approvers -= existing_approvers
                for approver in approvers:
                    for approval_dict in approval_dicts:
                        if approver.id in approval_dict["approver_ids"]:
                            approval_dict["approver_ids"].remove(approver.id)
                if approvers:
                    approval_dicts.append({
                        "approver_ids": approvers.ids,
                        "threshold_amount": level.threshold_amount,
                    })
        approval_ids = []
        for approval_dict in approval_dicts:
            if approval_dict["approver_ids"]:
                approval_ids.append((0, 0, {
                    "approver_ids": approval_dict["approver_ids"],
                    "threshold_amount": approval_dict["threshold_amount"],
                }))
        self.approval_ids = approval_ids
