import importlib
import json
import os
import tempfile
import unittest
from datetime import date


class RegressionTests(unittest.TestCase):
    def test_runtime_modules_import(self):
        for module_name in (
            "daily_scan",
            "fcas_engine_v2",
            "fcas_mcp",
            "tianshi_overlay",
            "contrarian_analysis_mcp",
            "backtest",
            "backtest_extended",
            "backtest_metals",
        ):
            with self.subTest(module=module_name):
                importlib.import_module(module_name)

    def test_fcas_mcp_reexports_core_engine(self):
        import fcas_engine_v2
        import fcas_mcp

        self.assertIs(fcas_mcp.analyze, fcas_engine_v2.analyze)
        self.assertIs(fcas_mcp.paipan, fcas_engine_v2.paipan)

    def test_telegram_split_handles_single_long_line(self):
        from fcas_utils import _MAX_CHUNK, _split_telegram_chunks

        text = "a" * (_MAX_CHUNK * 2 + 17)
        chunks = _split_telegram_chunks(text)

        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk) <= _MAX_CHUNK for chunk in chunks))
        self.assertEqual(len(chunks), 3)

    def test_backtest_115w_uses_previous_month_end_cutoff(self):
        from backtest_115w import get_macro_available

        rows = get_macro_available("macro_pmi_manufacturing.json", "2024-03-15")
        self.assertTrue(rows)
        self.assertEqual(rows[-1]["date"], "2024-02-29")

    def test_special_state_transitions_are_constrained_to_neighbor_band(self):
        from daily_scan import constrain_assessment

        self.assertEqual(
            constrain_assessment("FAVORABLE", "STAGNANT_XIONG"),
            ("SLIGHT_ADV", True),
        )
        self.assertEqual(
            constrain_assessment("STAGNANT_JI", "FAVORABLE"),
            ("STAGNANT_JI", False),
        )

    def test_missing_gate_does_not_render_as_open(self):
        from daily_scan import get_channel_name

        self.assertEqual(get_channel_name(None), "Unknown")
        self.assertEqual(get_channel_name(999), "Unknown")

    def test_daily_scan_recovers_from_invalid_history_file(self):
        import daily_scan

        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = os.path.join(tmpdir, "daily_scan_history.json")
            with open(history_path, "w", encoding="utf-8") as f:
                f.write("{invalid")

            original_path = daily_scan.HISTORY_FILE
            try:
                daily_scan.HISTORY_FILE = history_path
                daily_scan.save_history(
                    {"timestamp": "2026-04-03 13:00", "cycle": "Y6", "stocks": []}
                )

                with open(history_path, encoding="utf-8") as f:
                    saved = json.load(f)
                self.assertEqual(len(saved), 1)
                self.assertTrue(
                    any(name.startswith("daily_scan_history.json.corrupt.") for name in os.listdir(tmpdir))
                )
            finally:
                daily_scan.HISTORY_FILE = original_path

    def test_verify_predictions_recovers_invalid_verification_file(self):
        import verify_predictions

        with tempfile.TemporaryDirectory() as tmpdir:
            verification_path = os.path.join(tmpdir, "verification_results.json")
            with open(verification_path, "w", encoding="utf-8") as f:
                json.dump([], f)

            original_path = verify_predictions.VERIFICATION_FILE
            try:
                verify_predictions.VERIFICATION_FILE = verification_path
                data = verify_predictions.load_verification()

                self.assertEqual(data, {"records": [], "last_run": None})
                self.assertTrue(
                    any(name.startswith("verification_results.json.corrupt.") for name in os.listdir(tmpdir))
                )
            finally:
                verify_predictions.VERIFICATION_FILE = original_path

    def test_verify_predictions_retries_previous_no_data_records(self):
        from verify_predictions import run_verification

        flat_records = [
            {
                "stock_code": "600547.SH",
                "stock_name": "山东黄金",
                "scan_date": "2024-03-15",
                "scan_time": "2024-03-15 08:00",
                "ju": "Y1",
                "assessment": "SLIGHT_FAV",
                "family": "FAVORABLE",
                "score": 1.0,
                "special": "",
                "zone": "Yield",
            }
        ]
        existing = [
            {
                "stock_code": "600547.SH",
                "scan_date": "2024-03-15",
                "verification": {"1w_grade": "NO_DATA"},
            }
        ]

        all_records, _ = run_verification(flat_records, existing)
        self.assertEqual(all_records[0]["verification"]["1w_grade"], "CORRECT")

    def test_renshi_classification_prefers_intent_assessment(self):
        from tianshi_validation import classify_renshi as validation_classify
        from tianshi_overlay import classify_renshi as overlay_classify

        record = {"signal": "MIXED", "intent_assessment": "strongly_supported"}
        self.assertEqual(validation_classify(record), "H_FAV")
        self.assertEqual(overlay_classify(record), "RENSHI_JI")


if __name__ == "__main__":
    unittest.main()
