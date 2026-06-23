# -*- coding: utf-8 -*-

from lxml import etree

from odoo import SUPERUSER_ID, _, api, fields, models, tools
from odoo.exceptions import UserError


class UserRestriction(models.Model):
    _inherit = 'user.restrict'

    button_rule_ids = fields.One2many(
        'dynamic.restriction.button',
        'restriction_id',
        string='Button Restrictions',
    )
    tab_rule_ids = fields.One2many(
        'dynamic.restriction.tab',
        'restriction_id',
        string='Tab Restrictions',
    )

    @api.model
    def _empty_view_ui_restrictions(self):
        return {
            'buttons': [],
            'tabs': [],
            'button_labels': {},
            'tab_labels': {},
        }

    @api.model
    def _is_view_ui_restriction_admin_bypassed(self, uid=False, include_su=True):
        user_id = uid or self.env.uid
        if (include_su and self.env.su) or user_id == SUPERUSER_ID:
            return True
        user = self.env['res.users'].sudo().browse(user_id)
        group_system = self.sudo().env.ref('base.group_system', raise_if_not_found=False)
        return bool(group_system and group_system.id in user.groups_id.ids)

    @api.model
    def _view_element_parent_matches_scope(self, restriction, model_name, user, user_group_ids, company_id):
        if not restriction.active:
            return False
        if model_name not in restriction.model_ids.mapped('model'):
            return False
        if not restriction.user_ids and not restriction.group_ids:
            return False
        if user.id not in restriction.user_ids.ids and not user_group_ids.intersection(restriction.group_ids.ids):
            return False
        if restriction.company_ids and company_id not in restriction.company_ids.ids:
            return False

        return True

    @api.constrains('model_ids', 'button_rule_ids', 'tab_rule_ids')
    def _check_view_element_rules_single_model(self):
        for restriction in self:
            if (restriction.button_rule_ids or restriction.tab_rule_ids) and len(restriction.model_ids) != 1:
                raise UserError(_('Button and Tab restrictions require exactly one model on the main restriction.'))

    @api.model
    def _extract_form_view_elements(self, model):
        result = {
            'buttons': [],
            'tabs': [],
        }
        seen_buttons = set()
        seen_tabs = set()

        def add_element(items, seen, technical_name, label):
            name = (technical_name or '').strip()
            if not name or name in seen:
                return
            seen.add(name)
            items.append({
                'technical_name': name,
                'display_label': (label or '').strip(),
            })

        views = self.env['ir.ui.view'].sudo().search([
            ('active', '=', True),
            ('model', '=', model.model),
            ('type', '=', 'form'),
        ])
        for view in views:
            arch = view.arch_db or ''
            if not arch:
                continue
            try:
                root = etree.fromstring(arch.encode('utf-8'))
            except Exception:
                continue
            for node in root.xpath('.//button[@name]'):
                add_element(
                    result['buttons'],
                    seen_buttons,
                    node.get('name'),
                    node.get('string') or node.get('title'),
                )
            for node in root.xpath('.//page[@name]'):
                add_element(
                    result['tabs'],
                    seen_tabs,
                    node.get('name'),
                    node.get('string'),
                )

        return result

    @api.model
    def _load_view_elements_for_models(self, models_to_scan):
        result = {
            'buttons': [],
            'tabs': [],
        }
        ViewButton = self.env['dynamic.view.button'].sudo()
        ViewTab = self.env['dynamic.view.tab'].sudo()

        for model in models_to_scan.exists():
            elements = self._extract_form_view_elements(model)
            existing_buttons = {
                button.technical_name: button
                for button in ViewButton.search([('model_id', '=', model.id)])
            }
            existing_tabs = {
                tab.technical_name: tab
                for tab in ViewTab.search([('model_id', '=', model.id)])
            }

            for button in elements['buttons']:
                values = {
                    'model_id': model.id,
                    'technical_name': button['technical_name'],
                    'display_label': button['display_label'],
                }
                existing_button = existing_buttons.get(button['technical_name'])
                if existing_button:
                    existing_button.write({'display_label': button['display_label']})
                else:
                    ViewButton.create(values)
                result['buttons'].append(values)

            for tab in elements['tabs']:
                values = {
                    'model_id': model.id,
                    'technical_name': tab['technical_name'],
                    'display_label': tab['display_label'],
                }
                existing_tab = existing_tabs.get(tab['technical_name'])
                if existing_tab:
                    existing_tab.write({'display_label': tab['display_label']})
                else:
                    ViewTab.create(values)
                result['tabs'].append(values)

        return result

    def action_load_view_elements(self):
        self.ensure_one()
        if not self.model_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Model Selected',
                    'message': 'Select at least one model before loading view elements.',
                    'type': 'warning',
                    'sticky': False,
                },
            }
        elements = self._load_view_elements_for_models(self.model_ids)
        notification_type = 'success'
        message = 'Loaded %s buttons and %s tabs.' % (
            len(elements['buttons']),
            len(elements['tabs']),
        )
        if len(self.model_ids) > 1:
            notification_type = 'warning'
            message += ' Button and tab hiding works best with one model per restriction.'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'View Elements Loaded',
                'message': message,
                'type': notification_type,
                'sticky': False,
            },
        }

    @api.model
    @tools.ormcache('uid', 'company_id', 'model_name')
    def _get_view_ui_restrictions_cached(self, uid, company_id, model_name):
        if not model_name or self._is_view_ui_restriction_admin_bypassed(uid, include_su=False):
            return self._empty_view_ui_restrictions()

        user = self.env['res.users'].sudo().browse(uid).exists()
        if not user:
            return self._empty_view_ui_restrictions()

        user_group_ids = set(user.groups_id.ids)
        restrictions = self.sudo().search([
            ('active', '=', True),
            ('model_ids.model', '=', model_name),
        ])

        button_names = []
        buttons = []
        tab_names = []
        tabs = []
        button_labels = {}
        tab_labels = {}

        for restriction in restrictions:
            if not self._view_element_parent_matches_scope(
                restriction,
                model_name,
                user,
                user_group_ids,
                company_id,
            ):
                continue
            for rule in restriction.button_rule_ids.filtered('active'):
                button_name = (rule.button_name or '').strip()
                if not button_name:
                    continue
                button_label = (rule.button_label or '').strip()
                if button_name not in button_names:
                    button_names.append(button_name)
                    buttons.append({
                        'name': button_name,
                        'label': button_label,
                    })
                if button_label and button_name not in button_labels:
                    button_labels[button_name] = button_label

            for rule in restriction.tab_rule_ids.filtered('active'):
                tab_name = (rule.tab_name or '').strip()
                if not tab_name:
                    continue
                tab_label = (rule.tab_label or '').strip()
                if tab_name not in tab_names:
                    tab_names.append(tab_name)
                    tabs.append({
                        'name': tab_name,
                        'label': tab_label,
                    })
                if tab_label and tab_name not in tab_labels:
                    tab_labels[tab_name] = tab_label

        return {
            'buttons': buttons,
            'tabs': tabs,
            'button_labels': button_labels,
            'tab_labels': tab_labels,
        }

    @api.model
    def get_view_ui_restrictions(self, model_name):
        if self._is_view_ui_restriction_admin_bypassed():
            return self._empty_view_ui_restrictions()
        result = self._get_view_ui_restrictions_cached(
            self.env.uid,
            self.env.company.id,
            model_name or '',
        )
        return {
            'buttons': list(result.get('buttons') or []),
            'tabs': list(result.get('tabs') or []),
            'button_labels': dict(result.get('button_labels') or {}),
            'tab_labels': dict(result.get('tab_labels') or {}),
        }

    @api.model
    def scan_view_elements(self, model_name):
        result = {
            'buttons': [],
            'tabs': [],
        }
        if not model_name or not self._is_view_ui_restriction_admin_bypassed():
            return result

        model = self.env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        if not model:
            return result

        elements = self._load_view_elements_for_models(model)
        result['buttons'] = [
            {
                'name': button['technical_name'],
                'label': button['display_label'],
            }
            for button in elements['buttons']
        ]
        result['tabs'] = [
            {
                'name': tab['technical_name'],
                'label': tab['display_label'],
            }
            for tab in elements['tabs']
        ]
        return result


class DynamicViewButton(models.Model):
    _name = 'dynamic.view.button'
    _description = 'Dynamic View Button'
    _rec_name = 'name'
    _order = 'model_id, display_label, technical_name'

    name = fields.Char(compute='_compute_name', store=True)
    model_id = fields.Many2one(
        'ir.model',
        required=True,
        ondelete='cascade',
        index=True,
    )
    technical_name = fields.Char(required=True, index=True)
    display_label = fields.Char()

    _sql_constraints = [
        (
            'dynamic_view_button_model_name_uniq',
            'unique(model_id, technical_name)',
            'A discovered button already exists for this model and technical name.',
        ),
    ]

    @api.depends('technical_name', 'display_label')
    def _compute_name(self):
        for button in self:
            if button.display_label:
                button.name = '%s (%s)' % (button.display_label, button.technical_name)
            else:
                button.name = button.technical_name or 'View Button'


class DynamicViewTab(models.Model):
    _name = 'dynamic.view.tab'
    _description = 'Dynamic View Tab'
    _rec_name = 'name'
    _order = 'model_id, display_label, technical_name'

    name = fields.Char(compute='_compute_name', store=True)
    model_id = fields.Many2one(
        'ir.model',
        required=True,
        ondelete='cascade',
        index=True,
    )
    technical_name = fields.Char(required=True, index=True)
    display_label = fields.Char()

    _sql_constraints = [
        (
            'dynamic_view_tab_model_name_uniq',
            'unique(model_id, technical_name)',
            'A discovered tab already exists for this model and technical name.',
        ),
    ]

    @api.depends('technical_name', 'display_label')
    def _compute_name(self):
        for tab in self:
            if tab.display_label:
                tab.name = '%s (%s)' % (tab.display_label, tab.technical_name)
            else:
                tab.name = tab.technical_name or 'View Tab'


class DynamicRestrictionButton(models.Model):
    _name = 'dynamic.restriction.button'
    _description = 'Dynamic Button Restriction'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    active = fields.Boolean(default=True)
    restriction_id = fields.Many2one(
        'user.restrict',
        ondelete='cascade',
        index=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        ondelete='cascade',
    )
    view_button_id = fields.Many2one(
        'dynamic.view.button',
        string='Button',
        ondelete='set null',
    )
    button_name = fields.Char(required=True)
    button_label = fields.Char()
    user_ids = fields.Many2many(
        'res.users',
        'dynamic_restriction_button_user_rel',
        'button_rule_id',
        'user_id',
        string='Users',
    )
    group_ids = fields.Many2many(
        'res.groups',
        'dynamic_restriction_button_group_rel',
        'button_rule_id',
        'group_id',
        string='Groups',
    )
    company_ids = fields.Many2many(
        'res.company',
        'dynamic_restriction_button_company_rel',
        'button_rule_id',
        'company_id',
        string='Companies',
    )
    description = fields.Text()

    @api.depends('model_id', 'button_name', 'button_label', 'view_button_id')
    def _compute_name(self):
        for rule in self:
            parts = []
            if rule.model_id:
                parts.append(rule.model_id.model or rule.model_id.name)
            if rule.button_name:
                parts.append(rule.button_name)
            rule.name = ' / '.join(parts) or rule.button_label or 'Button Restriction'

    @api.onchange('model_id')
    def _onchange_model_id(self):
        for rule in self:
            if rule.view_button_id and rule.view_button_id.model_id != rule.model_id:
                rule.view_button_id = False

    @api.onchange('view_button_id')
    def _onchange_view_button_id(self):
        for rule in self:
            button = rule.view_button_id
            if not button:
                continue
            rule.model_id = button.model_id
            rule.button_name = button.technical_name
            rule.button_label = button.display_label

    @api.model
    def _prepare_view_button_values(self, values):
        view_button_id = values.get('view_button_id')
        if not view_button_id:
            return values
        button = self.env['dynamic.view.button'].sudo().browse(view_button_id).exists()
        if not button:
            return values
        values = dict(values)
        values['model_id'] = button.model_id.id
        values['button_name'] = button.technical_name
        values['button_label'] = button.display_label
        return values

    def _clear_dynamic_view_restriction_cache(self):
        self.env['user.restrict']._clear_dynamic_restriction_cache()

    def _check_parent_restriction_model_count(self):
        for rule in self:
            if rule.restriction_id:
                rule.restriction_id._check_view_element_rules_single_model()

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_view_button_values(values) for values in vals_list]
        records = super().create(vals_list)
        records._check_parent_restriction_model_count()
        records._clear_dynamic_view_restriction_cache()
        return records

    def write(self, vals):
        vals = self._prepare_view_button_values(vals)
        result = super().write(vals)
        self._check_parent_restriction_model_count()
        self._clear_dynamic_view_restriction_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self._clear_dynamic_view_restriction_cache()
        return result


class DynamicRestrictionTab(models.Model):
    _name = 'dynamic.restriction.tab'
    _description = 'Dynamic Tab Restriction'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    active = fields.Boolean(default=True)
    restriction_id = fields.Many2one(
        'user.restrict',
        ondelete='cascade',
        index=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        ondelete='cascade',
    )
    view_tab_id = fields.Many2one(
        'dynamic.view.tab',
        string='Tab',
        ondelete='set null',
    )
    tab_name = fields.Char(required=True)
    tab_label = fields.Char()
    user_ids = fields.Many2many(
        'res.users',
        'dynamic_restriction_tab_user_rel',
        'tab_rule_id',
        'user_id',
        string='Users',
    )
    group_ids = fields.Many2many(
        'res.groups',
        'dynamic_restriction_tab_group_rel',
        'tab_rule_id',
        'group_id',
        string='Groups',
    )
    company_ids = fields.Many2many(
        'res.company',
        'dynamic_restriction_tab_company_rel',
        'tab_rule_id',
        'company_id',
        string='Companies',
    )
    description = fields.Text()

    @api.depends('model_id', 'tab_name', 'tab_label', 'view_tab_id')
    def _compute_name(self):
        for rule in self:
            parts = []
            if rule.model_id:
                parts.append(rule.model_id.model or rule.model_id.name)
            if rule.tab_name:
                parts.append(rule.tab_name)
            rule.name = ' / '.join(parts) or rule.tab_label or 'Tab Restriction'

    @api.onchange('model_id')
    def _onchange_model_id(self):
        for rule in self:
            if rule.view_tab_id and rule.view_tab_id.model_id != rule.model_id:
                rule.view_tab_id = False

    @api.onchange('view_tab_id')
    def _onchange_view_tab_id(self):
        for rule in self:
            tab = rule.view_tab_id
            if not tab:
                continue
            rule.model_id = tab.model_id
            rule.tab_name = tab.technical_name
            rule.tab_label = tab.display_label

    @api.model
    def _prepare_view_tab_values(self, values):
        view_tab_id = values.get('view_tab_id')
        if not view_tab_id:
            return values
        tab = self.env['dynamic.view.tab'].sudo().browse(view_tab_id).exists()
        if not tab:
            return values
        values = dict(values)
        values['model_id'] = tab.model_id.id
        values['tab_name'] = tab.technical_name
        values['tab_label'] = tab.display_label
        return values

    def _clear_dynamic_view_restriction_cache(self):
        self.env['user.restrict']._clear_dynamic_restriction_cache()

    def _check_parent_restriction_model_count(self):
        for rule in self:
            if rule.restriction_id:
                rule.restriction_id._check_view_element_rules_single_model()

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_view_tab_values(values) for values in vals_list]
        records = super().create(vals_list)
        records._check_parent_restriction_model_count()
        records._clear_dynamic_view_restriction_cache()
        return records

    def write(self, vals):
        vals = self._prepare_view_tab_values(vals)
        result = super().write(vals)
        self._check_parent_restriction_model_count()
        self._clear_dynamic_view_restriction_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self._clear_dynamic_view_restriction_cache()
        return result
