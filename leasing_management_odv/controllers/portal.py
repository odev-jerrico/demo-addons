# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.http import request


class LeasingPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'maintenance_count' in counters:
            values['maintenance_count'] = request.env['leasing.maintenance.request'].sudo().search_count([
                ('tenant_id', '=', request.env.user.partner_id.id),
            ])
        return values

    @http.route(['/my/leasing/maintenance'], type='http', auth='user', website=True)
    def portal_my_maintenance_requests(self, page=1, **kw):
        Maintenance = request.env['leasing.maintenance.request'].sudo()
        domain = [('tenant_id', '=', request.env.user.partner_id.id)]
        total = Maintenance.search_count(domain)
        pager = portal_pager(
            url='/my/leasing/maintenance',
            total=total,
            page=page,
            step=20,
        )
        requests = Maintenance.search(domain, limit=20, offset=pager['offset'], order='request_date desc, id desc')
        values = self._prepare_portal_layout_values()
        values.update({
            'requests': requests,
            'pager': pager,
            'page_name': 'leasing_maintenance',
        })
        return request.render('leasing_management_odv.portal_my_maintenance_requests', values)

    @http.route(['/my/leasing/maintenance/new'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_create_maintenance_request(self, **post):
        partner = request.env.user.partner_id
        units = request.env['leasing.unit'].sudo().search([('tenant_id', '=', partner.id)])
        values = self._prepare_portal_layout_values()
        values.update({'units': units, 'error': False})

        if request.httprequest.method == 'POST':
            unit_id = int(post.get('unit_id') or 0)
            description = post.get('description')
            priority = post.get('priority') or '1'
            if not unit_id or not description:
                values['error'] = 'Please provide unit and description.'
                return request.render('leasing_management_odv.portal_new_maintenance_request', values)

            if unit_id not in units.ids:
                values['error'] = 'Selected unit is not linked to your tenant account.'
                return request.render('leasing_management_odv.portal_new_maintenance_request', values)

            request.env['leasing.maintenance.request'].sudo().create({
                'tenant_id': partner.id,
                'unit_id': unit_id,
                'description': description,
                'priority': priority,
            })
            return request.redirect('/my/leasing/maintenance')

        return request.render('leasing_management_odv.portal_new_maintenance_request', values)

    @http.route(['/my/leasing/maintenance/<int:request_id>'], type='http', auth='user', website=True)
    def portal_maintenance_request_detail(self, request_id, **kw):
        maintenance = request.env['leasing.maintenance.request'].sudo().browse(request_id)
        if not maintenance.exists() or maintenance.tenant_id != request.env.user.partner_id:
            return request.redirect('/my')

        values = self._prepare_portal_layout_values()
        values.update({
            'maintenance': maintenance,
            'page_name': 'leasing_maintenance',
        })
        return request.render('leasing_management_odv.portal_maintenance_request_detail', values)
