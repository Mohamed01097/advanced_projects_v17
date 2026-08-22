from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..const import DYNAMIC_REPORT_NAME_PREFIX, REQUIRED_STYLE_KEYS


@tagged("post_install", "-at_install")
class TestDynamicPdfRenderingContext(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.action_model = cls.env["ir.actions.report"]
        cls.report_model = cls.env["dynamic.pdf.report"]
        cls.rendering_model = cls.env[
            "report.dynamic_pdf_report_builder.dynamic_pdf_report_template"
        ]
        cls.partner_model = cls.env["ir.model"].search(
            [("model", "=", "res.partner")],
            limit=1,
        )
        fields = cls.env["ir.model.fields"].search([
            ("model_id", "=", cls.partner_model.id),
            ("name", "in", ["name", "email", "phone"]),
        ])
        cls.field_map = {field.name: field for field in fields}
        cls.partners = cls.env["res.partner"].create([
            {
                "name": "Rendering Context Partner One",
                "email": "render-one@example.com",
                "phone": "+10000000001",
            },
            {
                "name": "Rendering Context Partner Two",
                "email": "render-two@example.com",
                "phone": "+10000000002",
            },
        ])
        cls.reports = cls.env["dynamic.pdf.report"]
        cls.reports |= cls._create_report(
            "Context Modern",
            "CONTEXT MODERN TITLE",
            "name",
            "modern",
            "#2563EB",
        )
        cls.reports |= cls._create_report(
            "Context RTL",
            "CONTEXT RTL TITLE",
            "email",
            "classic",
            "#0F766E",
            direction="rtl",
        )
        cls.reports |= cls._create_report(
            "Context Minimal",
            "CONTEXT MINIMAL TITLE",
            "phone",
            "minimal",
            "#111827",
        )

    @classmethod
    def _create_report(cls, name, title, field_name, layout_style, primary_color, direction="ltr"):
        report = cls.report_model.create({
            "name": name,
            "report_title": title,
            "model_id": cls.partner_model.id,
            "layout_style": layout_style,
            "direction": direction,
            "primary_color": primary_color,
            "table_header_bg_color": primary_color,
            "field_line_ids": [(0, 0, {
                "field_id": cls.field_map[field_name].id,
                "sequence": 10,
            })],
        })
        report.action_create_report()
        return report

    def _render_html(self, report, record_ids=None):
        record_ids = record_ids or self.partners[:1].ids
        return self.action_model._render_qweb_html(
            report.report_action_id,
            record_ids,
            data={},
        )[0]

    def test_multiple_reports_on_same_model_have_authoritative_actions(self):
        self.assertEqual(len(self.reports.report_action_id), 3)
        self.assertEqual(len(set(self.reports.report_action_id.ids)), 3)
        self.assertEqual(self.reports.report_action_id.mapped("dynamic_pdf_report_id"), self.reports)
        for report in self.reports:
            action = report.report_action_id
            self.assertEqual(self.action_model._get_dynamic_pdf_report_config(action), report)
            self.assertEqual(action.model, "res.partner")
            self.assertEqual(action.report_name, "%s%s" % (DYNAMIC_REPORT_NAME_PREFIX, report.id))

    def test_each_action_renders_its_own_fields_title_and_style(self):
        expected_values = (
            (self.reports[0], b"CONTEXT MODERN TITLE", b"Rendering Context Partner One"),
            (self.reports[1], b"CONTEXT RTL TITLE", b"render-one@example.com"),
            (self.reports[2], b"CONTEXT MINIMAL TITLE", b"+10000000001"),
        )
        for report, title, field_value in expected_values:
            html = self._render_html(report)
            self.assertIn(title, html)
            self.assertIn(field_value, html)
            for other_report in self.reports - report:
                self.assertNotIn(other_report.report_title.encode(), html)

    def test_rendering_context_contract_is_complete_without_ui_context(self):
        report = self.reports[0]
        marker = object()
        values = self.action_model._get_rendering_context(
            report.report_action_id,
            self.partners.ids,
            {"caller_marker": marker},
        )
        self.assertIs(values["caller_marker"], marker)
        self.assertEqual(values["report_config"], report)
        self.assertIsInstance(values["style"], dict)
        self.assertEqual(set(values["style"]), set(REQUIRED_STYLE_KEYS))
        self.assertEqual(values["docs"], self.partners)
        self.assertEqual(values["doc_ids"], self.partners.ids)
        self.assertEqual(values["doc_model"], "res.partner")

    def test_style_builder_always_returns_all_required_keys(self):
        for report in self.reports:
            style = self.rendering_model._get_style_values(report)
            self.assertIsInstance(style, dict)
            self.assertEqual(set(style), set(REQUIRED_STYLE_KEYS))

    def test_empty_legacy_style_values_use_model_defaults(self):
        legacy_report = self.report_model.new({
            "layout_style": False,
            "paper_size": False,
            "direction": False,
            "primary_color": False,
            "secondary_color": False,
            "text_color": False,
            "table_header_bg_color": False,
            "table_header_text_color": False,
            "border_color": False,
            "font_size": False,
            "title_font_size": False,
            "table_border_style": False,
            "footer_text": False,
            "show_company_logo": False,
        })
        style = self.rendering_model._get_style_values(legacy_report)
        self.assertIsInstance(style, dict)
        self.assertEqual(set(style), set(REQUIRED_STYLE_KEYS))
        self.assertIn("direction: ltr", style["article"])
        self.assertIn("color: #111827", style["article"])
        self.assertEqual(
            legacy_report._get_paperformat(),
            self.env.ref("dynamic_pdf_report_builder.paperformat_dynamic_report_a4"),
        )
        self.assertNotIn("None", "".join(style.values()))
        self.assertNotIn("False", "".join(style.values()))

    def test_generated_report_names_ending_2_and_3_use_custom_context(self):
        for report, suffix in zip(self.reports[:2], ("_2", "_3")):
            route = "%stest_context_%s%s" % (
                DYNAMIC_REPORT_NAME_PREFIX,
                report.id,
                suffix,
            )
            action_values = report._prepare_report_action_vals()
            action_values.update({"report_name": route, "report_file": route})
            action = self.action_model.sudo().create(action_values)

            html = self.action_model._render_qweb_html(
                action.report_name,
                self.partners[:1].ids,
                data={},
            )[0]

            self.assertTrue(action.report_name.endswith(suffix))
            self.assertIn(report.report_title.encode(), html)

    def test_legacy_reverse_action_mapping_renders_and_preserves_style(self):
        report = self.reports[0]
        action = report.report_action_id
        action.dynamic_pdf_report_id = False

        values = self.action_model._get_rendering_context(action, self.partners[:1].ids, {})
        html = self.action_model._render_qweb_html(action.report_name, self.partners[:1].ids, data={})[0]

        self.assertEqual(values["report_config"], report)
        self.assertIsInstance(values["style"], dict)
        self.assertIn(report.report_title.encode(), html)

    def test_ambiguous_reverse_action_mapping_fails_explicitly(self):
        action = self.reports[0].report_action_id
        action.dynamic_pdf_report_id = False
        self.reports[1].report_action_id = action

        with self.assertRaisesRegex(UserError, "linked to multiple configurations"):
            self.action_model._get_rendering_context(action, self.partners[:1].ids, {})

    def test_invalid_dynamic_action_mapping_fails_before_qweb(self):
        route = "%smissing_configuration" % DYNAMIC_REPORT_NAME_PREFIX
        action = self.action_model.sudo().create({
            "name": "Invalid Dynamic Action",
            "model": "res.partner",
            "report_type": "qweb-pdf",
            "report_name": route,
            "report_file": route,
        })

        with self.assertRaisesRegex(UserError, "Unable to find the dynamic report configuration"):
            self.action_model._render_qweb_html(action.report_name, self.partners[:1].ids, data={})

    def test_preview_path_prepares_the_same_context(self):
        report = self.reports[0].with_context(
            active_model="res.partner",
            active_id=self.partners[0].id,
            active_ids=self.partners[:1].ids,
        )
        preview_action = report.action_preview_report()
        values = self.action_model.with_context(
            dynamic_pdf_report_id=report.id,
            dynamic_pdf_report_source="preview",
        )._get_rendering_context(report.report_action_id, self.partners[:1].ids, {})

        self.assertEqual(preview_action["type"], "ir.actions.act_url")
        self.assertIn(report.report_action_id.report_name, preview_action["url"])
        self.assertEqual(values["report_config"], report)
        self.assertIsInstance(values["style"], dict)

    def test_standard_pdf_rendering_path_uses_dynamic_context(self):
        report = self.reports[1]
        content, output_type = self.action_model.with_context(
            dynamic_pdf_report_source="print_menu",
        )._render_qweb_pdf(report.report_action_id, self.partners[:1].ids, data={})

        # Odoo intentionally falls back to HTML while running transactional
        # tests; real wkhtmltopdf output is covered by the HTTP audit matrix.
        self.assertEqual(output_type, "html")
        self.assertIn(report.report_title.encode(), content)

    def test_multi_record_rendering_keeps_all_records_once(self):
        report = self.reports[0]
        values = self.action_model._get_rendering_context(report.report_action_id, self.partners.ids, {})
        html = self._render_html(report, self.partners.ids)

        self.assertEqual(values["docs"].ids, self.partners.ids)
        self.assertEqual(values["doc_ids"], self.partners.ids)
        self.assertEqual(values["doc_model"], "res.partner")
        self.assertEqual(values["report_config"], report)
        for partner in self.partners:
            self.assertEqual(html.count(partner.name.encode()), 1)
