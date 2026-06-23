/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onPatched, onWillDestroy, onWillStart } from "@odoo/owl";

const EMPTY_RESTRICTIONS = Object.freeze({
    buttons: [],
    tabs: [],
    buttonLabels: {},
    tabLabels: {},
});

function getFormModelName(controller) {
    const props = controller.props || {};
    const model = controller.model || {};
    return (model.root && model.root.resModel) || props.resModel || false;
}

function normalizeButtons(value) {
    if (!Array.isArray(value)) {
        return [];
    }
    return value
        .filter(Boolean)
        .map((item) => {
            if (typeof item === "object") {
                return String(item.name || "");
            }
            return String(item || "");
        })
        .filter(Boolean);
}

function normalizeTabs(value, labelMap) {
    if (!Array.isArray(value)) {
        return [];
    }
    return value
        .filter(Boolean)
        .map((item) => {
            if (typeof item === "object") {
                return {
                    name: String(item.name || ""),
                    label: String(item.label || ""),
                };
            }
            const name = String(item || "");
            return {
                name,
                label: String((labelMap && labelMap[name]) || ""),
            };
        })
        .filter((tab) => tab.name || tab.label);
}

function normalizeLabelMap(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return {};
    }
    return Object.fromEntries(
        Object.entries(value)
            .filter(([key, label]) => key && label)
            .map(([key, label]) => [String(key), String(label)])
    );
}

function normalizeRestrictions(value) {
    const tabLabels = normalizeLabelMap(value && value.tab_labels);
    return {
        buttons: normalizeButtons(value && value.buttons),
        tabs: normalizeTabs(value && value.tabs, tabLabels),
        buttonLabels: normalizeLabelMap(value && value.button_labels),
        tabLabels,
    };
}

function escapeAttributeValue(value) {
    return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function attrSelector(attributeName, value) {
    return `[${attributeName}="${escapeAttributeValue(value)}"]`;
}

function cssEscape(value) {
    if (window.CSS && window.CSS.escape) {
        return window.CSS.escape(String(value));
    }
    return String(value).replace(/([ !"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g, "\\$1");
}

function selectAll(root, selectors) {
    try {
        return root.querySelectorAll(selectors.filter(Boolean).join(", "));
    } catch (error) {
        console.warn("dynamic_restriction: failed to select restricted view elements", error);
        return [];
    }
}

function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
}

function hideElement(element) {
    if (!element || !element.classList) {
        return;
    }
    if (!element.classList.contains("d-none")) {
        element.classList.add("d-none");
    }
    if (element.style.getPropertyValue("display") !== "none") {
        element.style.setProperty("display", "none", "important");
    }
    if (element.getAttribute("aria-hidden") !== "true") {
        element.setAttribute("aria-hidden", "true");
    }
}

function getTargetId(value) {
    const rawValue = String(value || "").trim();
    if (!rawValue) {
        return false;
    }
    if (rawValue.startsWith("#")) {
        return rawValue.slice(1);
    }
    if (rawValue.includes("#")) {
        return rawValue.split("#").pop();
    }
    if (!rawValue.includes("/") && !rawValue.includes(" ")) {
        return rawValue;
    }
    return false;
}

function hideTabNavigationForTarget(root, targetId) {
    if (!targetId) {
        return;
    }
    const escapedId = escapeAttributeValue(targetId);
    const escapedHash = escapeAttributeValue(`#${targetId}`);
    const navigationSelectors = [
        `[aria-controls="${escapedId}"]`,
        `[href="${escapedHash}"]`,
        `[data-bs-target="${escapedHash}"]`,
        `[data-target="${escapedHash}"]`,
    ];
    selectAll(root, navigationSelectors).forEach((navigationElement) => {
        hideElement(navigationElement);
        hideElement(navigationElement.closest(".nav-item"));
    });
}

function hideRelatedTabElements(root, element) {
    const navigationElement =
        element.matches("a, .nav-link, .tab-link, button[role='tab'], [role='tab']")
            ? element
            : element.closest("a, .nav-link, .tab-link, button[role='tab'], [role='tab']");
    if (navigationElement) {
        hideElement(navigationElement);
        hideElement(navigationElement.closest(".nav-item"));
    }

    const pageElement = element.closest(".tab-pane, .o_notebook_page, page");
    if (pageElement) {
        hideElement(pageElement);
        hideTabNavigationForTarget(root, pageElement.id);
        const labelledBy = pageElement.getAttribute("aria-labelledby");
        if (labelledBy) {
            const labelElement = root.querySelector(`#${cssEscape(labelledBy)}`);
            hideElement(labelElement);
            hideElement(labelElement && labelElement.closest(".nav-item"));
        }
    }

    const elementId = element.getAttribute("id");
    if (elementId) {
        hideTabNavigationForTarget(root, elementId);
    }

    for (const attributeName of ["aria-controls", "href", "data-bs-target", "data-target"]) {
        const targetId = getTargetId(element.getAttribute(attributeName));
        if (!targetId) {
            continue;
        }
        const targetElement = root.querySelector(`#${cssEscape(targetId)}`);
        hideElement(targetElement);
        hideTabNavigationForTarget(root, targetId);
    }
}

function hideButton(root, buttonName) {
    const selectors = [
        `button${attrSelector("name", buttonName)}`,
        `.btn${attrSelector("name", buttonName)}`,
        `${attrSelector("type", "object")}${attrSelector("name", buttonName)}`,
    ];
    selectAll(root, selectors).forEach((button) => hideElement(button));
}

function hideTabByLabel(root, label) {
    const normalizedLabel = normalizeText(label);
    if (!normalizedLabel) {
        return;
    }
    selectAll(root, [
        ".nav-link",
        ".o_notebook .nav-link",
        ".tab-link",
        ".nav-tabs a",
        "button[role='tab']",
        "a[role='tab']",
        ".o_notebook_headers a",
        ".o_notebook_headers button",
        "[role='tab']",
    ]).forEach((tabElement) => {
        if (normalizeText(tabElement.textContent) !== normalizedLabel) {
            return;
        }
        hideElement(tabElement);
        hideElement(tabElement.closest(".nav-item"));
        hideRelatedTabElements(root, tabElement);
    });
    selectAll(root, ["*"]).forEach((element) => {
        if (normalizeText(element.textContent) !== normalizedLabel) {
            return;
        }
        const tabElement = element.closest(
            "a, .nav-link, .tab-link, button[role='tab'], a[role='tab'], [role='tab']"
        );
        hideElement(tabElement || element);
        hideElement(tabElement && tabElement.closest(".nav-item"));
        hideRelatedTabElements(root, tabElement || element);
    });
}

function hideTab(root, tabName, label) {
    const selectors = tabName
        ? [
              `page${attrSelector("name", tabName)}`,
              attrSelector("name", tabName),
              `a${attrSelector("name", tabName)}`,
              `.nav-link${attrSelector("name", tabName)}`,
              attrSelector("data-name", tabName),
              attrSelector("data-page", tabName),
              attrSelector("data-page-name", tabName),
              attrSelector("data-tab", tabName),
              `[href*="${escapeAttributeValue(tabName)}"]`,
              `[aria-controls*="${escapeAttributeValue(tabName)}"]`,
              `[data-bs-target*="${escapeAttributeValue(tabName)}"]`,
              `[data-target*="${escapeAttributeValue(tabName)}"]`,
          ]
        : [];
    selectAll(root, selectors).forEach((element) => {
        hideElement(element);
        hideRelatedTabElements(root, element);
    });
    hideTabByLabel(root, label);
}

patch(FormController.prototype, {
    setup() {
        super.setup();
        this.dynamicViewElementOrm = useService("orm");
        this.dynamicViewElementRestrictions = { ...EMPTY_RESTRICTIONS };
        this.dynamicViewElementObserver = false;
        this.dynamicViewElementApplyScheduled = false;
        this.dynamicViewElementApplyTimer = false;

        onWillStart(async () => {
            await this.loadDynamicViewElementRestrictions();
        });

        onMounted(() => {
            this.startDynamicViewElementObserver();
            this.applyDynamicViewElementRestrictions();
        });

        onPatched(() => {
            this.scheduleDynamicViewElementRestrictionsApply();
        });

        onWillDestroy(() => {
            this.stopDynamicViewElementObserver();
        });
    },

    async loadDynamicViewElementRestrictions() {
        const modelName = getFormModelName(this);
        if (!modelName || !this.dynamicViewElementOrm) {
            this.dynamicViewElementRestrictions = { ...EMPTY_RESTRICTIONS };
            return;
        }
        try {
            const restrictions = await this.dynamicViewElementOrm.call(
                "user.restrict",
                "get_view_ui_restrictions",
                [modelName]
            );
            this.dynamicViewElementRestrictions = normalizeRestrictions(restrictions);
        } catch (error) {
            console.warn("dynamic_restriction: failed to load view element restrictions", error);
            this.dynamicViewElementRestrictions = { ...EMPTY_RESTRICTIONS };
        }
    },

    getDynamicViewElementRoot() {
        return (this.rootRef && this.rootRef.el) || false;
    },

    startDynamicViewElementObserver() {
        const root = typeof document !== "undefined" ? document.body : false;
        if (!root || typeof MutationObserver === "undefined" || this.dynamicViewElementObserver) {
            return;
        }
        try {
            this.dynamicViewElementObserver = new MutationObserver(() => {
                this.scheduleDynamicViewElementRestrictionsApply();
            });
            this.dynamicViewElementObserver.observe(root, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: [
                    "aria-controls",
                    "class",
                    "data-bs-target",
                    "data-name",
                    "data-page",
                    "data-page-name",
                    "data-tab",
                    "data-target",
                    "href",
                    "id",
                    "name",
                    "role",
                ],
            });
        } catch (error) {
            console.warn("dynamic_restriction: failed to observe view element restrictions", error);
        }
    },

    stopDynamicViewElementObserver() {
        if (this.dynamicViewElementApplyTimer) {
            clearTimeout(this.dynamicViewElementApplyTimer);
            this.dynamicViewElementApplyTimer = false;
        }
        if (!this.dynamicViewElementObserver) {
            return;
        }
        try {
            this.dynamicViewElementObserver.disconnect();
        } catch (error) {
            console.warn("dynamic_restriction: failed to stop view element observer", error);
        }
        this.dynamicViewElementObserver = false;
    },

    scheduleDynamicViewElementRestrictionsApply() {
        if (this.dynamicViewElementApplyScheduled) {
            return;
        }
        this.dynamicViewElementApplyScheduled = true;
        this.dynamicViewElementApplyTimer = setTimeout(() => {
            this.dynamicViewElementApplyScheduled = false;
            this.dynamicViewElementApplyTimer = false;
            this.applyDynamicViewElementRestrictions();
        }, 300);
    },

    applyDynamicViewElementRestrictions() {
        const root = this.getDynamicViewElementRoot();
        if (!root) {
            return;
        }
        try {
            const restrictions = normalizeRestrictions(this.dynamicViewElementRestrictions);
            for (const buttonName of restrictions.buttons) {
                hideButton(root, buttonName);
            }
            const tabRoot = typeof document !== "undefined" && document.body ? document.body : root;
            for (const tab of restrictions.tabs) {
                hideTab(tabRoot, tab.name, tab.label);
            }
        } catch (error) {
            console.warn("dynamic_restriction: failed to apply view element restrictions", error);
        }
    },
});
