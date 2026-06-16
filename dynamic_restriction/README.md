# Dynamic Access Manager

Dynamic Access Manager by DevOdooX is a professional Odoo security and access-control module for managing practical business restrictions without custom code.

It helps administrators restrict sensitive actions, hide unavailable UI controls, require approvals, protect readonly fields, limit users to their own records, and review audit logs from a dedicated Odoo backend menu.

## Overview

Standard Odoo access rights and record rules are powerful, but many businesses need action-level governance that can be configured quickly by administrators. Dynamic Access Manager adds a configurable layer for controlling create, edit, delete, duplicate, archive, import, export, mass actions, ownership access, approvals, and audit traceability.

The module is designed for Odoo consultants, implementation partners, system administrators, and companies that need stronger operational control across sales, CRM, accounting, inventory, HR, and custom models.

## Features

- Dynamic action restrictions for create, edit, delete, duplicate, archive, import, export, mass edit, mass delete, and mass archive.
- User, group, company, domain, ownership, time, and IP based policy targeting.
- Own Documents Only mode using a configurable user owner field.
- UI action hiding for restricted create, edit, delete, duplicate, export, and archive actions.
- Readonly field protection for sensitive stored fields.
- Approval workflow for edit, delete, duplicate, and archive actions.
- Approval request queue with pending, approved, rejected, and cancelled states.
- Audit logs for blocked actions and approval-required events.
- IP restrictions by single IP address or CIDR range.
- Time restrictions by weekday, allowed hours, and timezone mode.
- Restriction templates for faster security policy deployment.
- Multi-company compatible configuration.
- Backend validation as the source of truth.

## Installation

1. Copy the `dynamic_restriction` folder into your Odoo addons path.
2. Restart the Odoo service.
3. Update the Apps list from Odoo.
4. Search for `Dynamic Access Manager`.
5. Install the module.

Command-line update example:

```bash
./odoo-bin -d DB_NAME -u dynamic_restriction
```

Replace `DB_NAME` with your Odoo database name.

## Configuration

1. Open `Dynamic Access Manager`.
2. Go to `Restrictions`.
3. Create a new restriction.
4. Select the target model or models.
5. Select the users, groups, and companies that should be affected.
6. Enable the required blocked actions, such as Prevent Edit, Prevent Delete, Prevent Export, or Prevent Import.
7. Optionally configure:
   - Domain-based restrictions.
   - Own Documents Only rules.
   - Readonly protected fields.
   - Approval workflow.
   - UI button hiding.
   - IP restrictions.
   - Time restrictions.
8. Save the restriction and test with a non-admin user.

## Usage

### Restrict Editing Confirmed Sales Orders

Create a restriction for `sale.order`, enable Prevent Edit, and add a domain such as:

```python
[('state', '=', 'sale')]
```

Users can continue working on quotations, while confirmed orders remain protected.

### Require Approval Before Deleting CRM Opportunities

Create a restriction for `crm.lead`, enable Require Approval, and select Delete as an approval action. When a restricted user attempts to delete a lead, an approval request is created instead of deleting the record immediately.

### Limit Users to Their Own Records

Enable Own Documents Only and select a user owner field such as `user_id`. Users will only access records assigned to them.

### Protect Sensitive Fields

Enable Protect Readonly Fields and select stored fields such as price, discount, payment terms, or responsible user fields. Writes to those fields are blocked while other fields can remain editable.

### Review Audit Logs

Open `Dynamic Access Manager > Audit Logs` to review blocked operations, approval-required events, affected records, users, companies, and restriction names.

## Support

DevOdooX provides support for installation, configuration, troubleshooting, custom development, and module customization.

Support Email: [devodoox06@gmail.com](mailto:devodoox06@gmail.com)

## Compatibility

- Odoo 17
- Odoo 18
- Odoo 19

Dependencies:

- `base`
- `web`

## Contact Information

Company: DevOdooX

Support Email: [devodoox06@gmail.com](mailto:devodoox06@gmail.com)

LinkedIn: DevOdooX

YouTube: DevOdooX

## License

OPL-1
