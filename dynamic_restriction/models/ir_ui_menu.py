# -*- coding: utf-8 -*-

from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.returns('self')
    def _filter_visible_menus(self):
        """
        Override to filter out menus hidden by user.restrict rules.

        A menu is hidden when a user.restrict rule matches:
        - active=True
        - hide_menu_items=True
        - menu_ids contains this menu
        - current user is in user_ids OR belongs to group_ids
        - if user_ids and group_ids are both empty: do not apply
        - if company_ids empty: apply to all companies
        - if company_ids set: current env.company must be included

        Exclude from hiding:
        - env.su
        - SUPERUSER_ID
        - base.group_system users
        """
        menus = super()._filter_visible_menus()

        user = self.env.user
        company = self.env.company

        # Get hidden menus from user.restrict rules
        user_restrict = self.env['user.restrict']
        hidden_menus = user_restrict._get_hidden_menus_for_user(user, company)

        # Filter out hidden menus
        return menus - hidden_menus

