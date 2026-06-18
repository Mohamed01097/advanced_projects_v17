/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { CogMenu } from "@web/search/cog_menu/cog_menu";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { onPatched, onWillStart, useEffect, useExternalListener, useState } from "@odoo/owl";

const EMPTY_RESTRICTIONS = Object.freeze({
    hide_restricted_buttons: false,
    prevent_create: false,
    prevent_edit: false,
    prevent_delete: false,
    prevent_duplicate: false,
    prevent_export: false,
    prevent_archive: false,
    prevent_import: false,
});

const ACTION_FIELDS = [
    "hide_restricted_buttons",
    "prevent_create",
    "prevent_edit",
    "prevent_delete",
    "prevent_duplicate",
    "prevent_export",
    "prevent_archive",
    "prevent_import",
];

const STATIC_ACTIONS = {
    archive: "prevent_archive",
    unarchive: "prevent_archive",
    duplicate: "prevent_duplicate",
    delete: "prevent_delete",
    export: "prevent_export",
    import: "prevent_import",
};

const COMPONENT_ACTIONS = {
    ExportAll: "prevent_export",
    ImportRecords: "prevent_import",
};

const LABEL_ACTIONS = new Map([
    ["Delete", "prevent_delete"],
    ["Export", "prevent_export"],
    ["Export All", "prevent_export"],
    ["Duplicate", "prevent_duplicate"],
    ["Archive", "prevent_archive"],
    ["Unarchive", "prevent_archive"],
    ["Import", "prevent_import"],
    ["Import records", "prevent_import"],
]);

const restrictionsByModel = new Map();

function normalizeRestrictions(restrictions) {
    const normalized = { ...EMPTY_RESTRICTIONS, ...(restrictions || {}) };
    for (const fieldName of ACTION_FIELDS) {
        normalized[fieldName] = Boolean(normalized[fieldName]);
    }
    return normalized;
}

function setModelRestrictions(modelName, restrictions) {
    const normalized = normalizeRestrictions(restrictions);
    if (modelName) {
        restrictionsByModel.set(modelName, normalized);
    }
    return normalized;
}

function getModelRestrictions(modelName) {
    return normalizeRestrictions(restrictionsByModel.get(modelName));
}

function isPrevented(restrictions, fieldName) {
    const normalized = normalizeRestrictions(restrictions);
    return normalized[fieldName];
}

function getControllerModelName(controller) {
    const props = controller.props || {};
    const model = controller.model || {};
    return (model.root && model.root.resModel) || props.resModel || false;
}

function getControllerResId(controller) {
    if (typeof controller.getUiRestrictionResId === "function") {
        return controller.getUiRestrictionResId() || false;
    }
    const props = controller.props || {};
    const model = controller.model || {};
    return (model.root && model.root.resId) || props.resId || false;
}

function getCogModelName(cogMenu) {
    const props = cogMenu.props || {};
    const env = cogMenu.env || {};
    return (
        props.resModel ||
        (env.searchModel && env.searchModel.resModel) ||
        (env.model && env.model.root && env.model.root.resModel) ||
        false
    );
}

function getActionMenuModelName(actionMenu, props) {
    const menuProps = props || actionMenu.props || {};
    const env = actionMenu.env || {};
    return (
        menuProps.resModel ||
        (env.searchModel && env.searchModel.resModel) ||
        (env.model && env.model.root && env.model.root.resModel) ||
        false
    );
}

function setupControllerRestrictionsState(controller) {
    const restrictions = getModelRestrictions(getControllerModelName(controller));
    controller.dynamicUiRestrictionState = useState({ restrictions });
    controller.uiRestrictions = restrictions;
}

function updateControllerRestrictionsState(controller, restrictions) {
    const normalized = normalizeRestrictions(restrictions);
    controller.uiRestrictions = normalized;
    if (controller.dynamicUiRestrictionState) {
        controller.dynamicUiRestrictionState.restrictions = normalized;
    }
    return normalized;
}

async function loadUiRestrictions(controller) {
    const modelName = getControllerModelName(controller);
    if (!modelName) {
        return normalizeRestrictions(EMPTY_RESTRICTIONS);
    }
    if (!controller.orm || !controller.orm.call) {
        return setModelRestrictions(modelName, EMPTY_RESTRICTIONS);
    }

    try {
        const restrictions = await controller.orm.call(
            "user.restrict",
            "get_ui_restrictions",
            [modelName, getControllerResId(controller)]
        );
        const normalized = setModelRestrictions(modelName, restrictions);
        console.log("[Dynamic Restriction UI]", modelName, normalized);
        return normalized;
    } catch (error) {
        console.warn("dynamic_restriction: failed to load UI restrictions", error);
        return setModelRestrictions(modelName, EMPTY_RESTRICTIONS);
    }
}

function restrictStaticActionItems(items, restrictions) {
    const normalized = normalizeRestrictions(restrictions);
    const restrictedItems = { ...items };
    for (const [actionName, fieldName] of Object.entries(STATIC_ACTIONS)) {
        if (!restrictedItems[actionName]) {
            continue;
        }
        const originalIsAvailable = restrictedItems[actionName].isAvailable;
        restrictedItems[actionName] = {
            ...restrictedItems[actionName],
            isAvailable: () =>
                !normalized[fieldName] &&
                (originalIsAvailable === undefined || originalIsAvailable()),
        };
    }
    return restrictedItems;
}

function normalizeMenuLabel(label) {
    return String(label || "").replace(/\s+/g, " ").trim();
}

function getActionItemLabel(item) {
    return normalizeMenuLabel(
        (item && (item.description || item.name)) ||
            (item && item.action && item.action.name) ||
            ""
    );
}

function getRestrictionFieldForActionItem(item) {
    if (!item) {
        return false;
    }
    if (item.key && STATIC_ACTIONS[item.key]) {
        return STATIC_ACTIONS[item.key];
    }
    return LABEL_ACTIONS.get(getActionItemLabel(item)) || false;
}

function isActionItemPrevented(item, restrictions) {
    const fieldName = getRestrictionFieldForActionItem(item);
    return Boolean(fieldName && isPrevented(restrictions, fieldName));
}

function isCogItemPrevented(item, restrictions) {
    const componentName = item && item.Component && item.Component.name;
    const fieldName =
        (componentName && COMPONENT_ACTIONS[componentName]) ||
        (item && item.key && COMPONENT_ACTIONS[item.key]) ||
        getRestrictionFieldForActionItem(item);
    return Boolean(fieldName && isPrevented(restrictions, fieldName));
}

function filterActionMenuItems(items, restrictions) {
    const actionItems = (items && items.action) || [];
    return {
        ...(items || {}),
        action: actionItems.filter((item) => !isActionItemPrevented(item, restrictions)),
    };
}

function filterRenderedActionItems(items, restrictions) {
    return (items || []).filter((item) => !isActionItemPrevented(item, restrictions));
}

function cleanupRestrictedDropdownItems(restrictions, root) {
    const target = root || (typeof document !== "undefined" ? document : false);
    if (!target || !target.querySelectorAll) {
        return;
    }

    try {
        const normalized = normalizeRestrictions(restrictions);
        target
            .querySelectorAll(
                ".dropdown-menu .o_menu_item, .dropdown-menu .dropdown-item, " +
                    ".o-dropdown--menu .o_menu_item, .o-dropdown--menu .dropdown-item"
            )
            .forEach((item) => {
                const label = normalizeMenuLabel(item.textContent);
                const fieldName = LABEL_ACTIONS.get(label);
                if (!fieldName) {
                    return;
                }
                const shouldHide = normalized[fieldName];
                item.classList.toggle("d-none", shouldHide);
                if (shouldHide) {
                    item.setAttribute("aria-hidden", "true");
                } else if (item.getAttribute("aria-hidden") === "true") {
                    item.removeAttribute("aria-hidden");
                }
            });
    } catch (error) {
        console.warn("dynamic_restriction: failed to clean up action menu items", error);
    }
}

function scheduleRestrictedDropdownCleanup(restrictions, root) {
    if (typeof window === "undefined") {
        cleanupRestrictedDropdownItems(restrictions, root);
        return;
    }
    window.setTimeout(() => cleanupRestrictedDropdownItems(restrictions, root), 0);
}

patch(ActionMenus.prototype, {
    setup() {
        super.setup();
        onPatched(() => {
            scheduleRestrictedDropdownCleanup(
                getModelRestrictions(getActionMenuModelName(this))
            );
        });
        useExternalListener(document, "click", () => {
            scheduleRestrictedDropdownCleanup(
                getModelRestrictions(getActionMenuModelName(this))
            );
        });
    },

    async getActionItems(props) {
        const actionItems = await super.getActionItems(props);
        return filterRenderedActionItems(
            actionItems,
            getModelRestrictions(getActionMenuModelName(this, props))
        );
    },

    async onItemSelected(item) {
        const restrictions = getModelRestrictions(getActionMenuModelName(this));
        if (isActionItemPrevented(item, restrictions) || isCogItemPrevented(item, restrictions)) {
            return;
        }
        return super.onItemSelected(item);
    },
});

patch(CogMenu.prototype, {
    get cogItems() {
        const restrictions = getModelRestrictions(getCogModelName(this));
        return super.cogItems.filter((item) => !isCogItemPrevented(item, restrictions));
    },
});

patch(FormController.prototype, {
    setup() {
        super.setup();
        setupControllerRestrictionsState(this);
        this.baseCanCreate = this.canCreate;
        this.baseCanEdit = this.canEdit;

        onWillStart(async () => {
            await this.loadDynamicUiRestrictions(false);
        });

        useEffect(
            () => {
                this.loadDynamicUiRestrictions(true);
            },
            () => [(this.model.root && this.model.root.resId) || false]
        );

        onPatched(() => this.applyDynamicUiFallbacks());
    },

    getUiRestrictionResId() {
        return (this.model.root && this.model.root.resId) || this.props.resId || false;
    },

    async loadDynamicUiRestrictions(shouldRender) {
        updateControllerRestrictionsState(this, await loadUiRestrictions(this));
        this.applyDynamicUiState();
        this.applyDynamicUiFallbacks();
        if (shouldRender) {
            this.render();
        }
    },

    applyDynamicUiState() {
        this.canCreate = this.baseCanCreate && !isPrevented(this.uiRestrictions, "prevent_create");
        this.canEdit = this.baseCanEdit && !isPrevented(this.uiRestrictions, "prevent_edit");

        const root = this.model && this.model.root;
        if (
            root &&
            root.switchMode &&
            !root.isNew &&
            root.isInEdition &&
            isPrevented(this.uiRestrictions, "prevent_edit")
        ) {
            root.switchMode("readonly");
        }
    },

    applyDynamicUiFallbacks() {
        const rootEl = this.rootRef && this.rootRef.el;
        if (!rootEl) {
            return;
        }
        rootEl
            .querySelectorAll(".o_form_button_create")
            .forEach((button) =>
                button.classList.toggle(
                    "d-none",
                    isPrevented(this.uiRestrictions, "prevent_create")
                )
            );
        rootEl
            .querySelectorAll(".o_form_status_indicator")
            .forEach((button) =>
                button.classList.toggle(
                    "d-none",
                    isPrevented(this.uiRestrictions, "prevent_edit")
                )
            );
        scheduleRestrictedDropdownCleanup(this.uiRestrictions);
    },

    getStaticActionMenuItems() {
        return restrictStaticActionItems(
            super.getStaticActionMenuItems(),
            this.uiRestrictions
        );
    },

    get actionMenuItems() {
        return filterActionMenuItems(super.actionMenuItems, this.uiRestrictions);
    },

    async shouldExecuteAction(item) {
        if (isActionItemPrevented(item, this.uiRestrictions)) {
            return false;
        }
        return super.shouldExecuteAction(item);
    },

    async create(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_create")) {
            return;
        }
        return super.create(...args);
    },

    async duplicateRecord(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_duplicate")) {
            return;
        }
        return super.duplicateRecord(...args);
    },

    async deleteRecord(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_delete")) {
            return;
        }
        return super.deleteRecord(...args);
    },
});

patch(ListController.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        setupControllerRestrictionsState(this);
        this.baseActiveActions = { ...this.activeActions };
        this.baseEditable = this.editable;

        onWillStart(async () => {
            await this.loadDynamicUiRestrictions(false);
        });

        useEffect(
            () => {
                this.loadDynamicUiRestrictions(true);
            },
            () => [getControllerModelName(this)]
        );

        useEffect(
            () => {
                this.applyDynamicUiFallbacks();
            },
            () => [
                this.model.root.selection.length,
                this.model.root.isDomainSelected,
            ]
        );

        onPatched(() => this.applyDynamicUiFallbacks());
    },

    async loadDynamicUiRestrictions(shouldRender) {
        updateControllerRestrictionsState(this, await loadUiRestrictions(this));
        this.applyDynamicUiState();
        this.applyDynamicUiFallbacks();
        if (shouldRender) {
            this.render();
        }
    },

    applyDynamicUiState() {
        this.activeActions = {
            ...this.baseActiveActions,
            create:
                this.baseActiveActions.create &&
                !isPrevented(this.uiRestrictions, "prevent_create"),
            edit:
                this.baseActiveActions.edit &&
                !isPrevented(this.uiRestrictions, "prevent_edit"),
            delete:
                this.baseActiveActions.delete &&
                !isPrevented(this.uiRestrictions, "prevent_delete"),
            duplicate:
                this.baseActiveActions.duplicate &&
                !isPrevented(this.uiRestrictions, "prevent_duplicate"),
        };
        this.editable = isPrevented(this.uiRestrictions, "prevent_edit")
            ? false
            : this.baseEditable;
    },

    applyDynamicUiFallbacks() {
        const rootEl = this.rootRef && this.rootRef.el;
        if (!rootEl) {
            return;
        }
        rootEl
            .querySelectorAll(".o_list_button_add")
            .forEach((button) =>
                button.classList.toggle(
                    "d-none",
                    isPrevented(this.uiRestrictions, "prevent_create")
                )
            );
        scheduleRestrictedDropdownCleanup(this.uiRestrictions);
    },

    getStaticActionMenuItems() {
        return restrictStaticActionItems(
            super.getStaticActionMenuItems(),
            this.uiRestrictions
        );
    },

    get actionMenuItems() {
        return filterActionMenuItems(super.actionMenuItems, this.uiRestrictions);
    },

    async onClickCreate(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_create")) {
            return;
        }
        return super.onClickCreate(...args);
    },

    async createRecord(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_create")) {
            return;
        }
        return super.createRecord(...args);
    },

    async onExportData(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_export")) {
            return;
        }
        return super.onExportData(...args);
    },

    async onDirectExportData(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_export")) {
            return;
        }
        return super.onDirectExportData(...args);
    },

    async toggleArchiveState(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_archive")) {
            return;
        }
        return super.toggleArchiveState(...args);
    },

    async duplicateRecords(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_duplicate")) {
            return;
        }
        return super.duplicateRecords(...args);
    },

    async onDeleteSelectedRecords(...args) {
        if (isPrevented(this.uiRestrictions, "prevent_delete")) {
            return;
        }
        return super.onDeleteSelectedRecords(...args);
    },
});
