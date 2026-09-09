import unittest
from src.utils.time_utils import (
    DEBOUNCE_PRESETS,
    format_duration,
    format_duration_display,
    parse_duration_string,
)


class TestTimeUtils(unittest.TestCase):
    def test_parse_duration_string_minutes(self):
        self.assertEqual(parse_duration_string("1m"), 60)
        self.assertEqual(parse_duration_string("4m"), 240)
        self.assertEqual(parse_duration_string("5m"), 300)
        self.assertEqual(parse_duration_string("10m"), 600)
        self.assertEqual(parse_duration_string("30m"), 1800)

    def test_parse_duration_string_hours(self):
        self.assertEqual(parse_duration_string("1h"), 3600)
        self.assertEqual(parse_duration_string("2h"), 7200)
        self.assertEqual(parse_duration_string("3h"), 10800)
        self.assertEqual(parse_duration_string("4h"), 14400)
        self.assertEqual(parse_duration_string("8h"), 28800)
        self.assertEqual(parse_duration_string("24h"), 86400)

    def test_parse_duration_string_with_labels(self):
        self.assertEqual(parse_duration_string("5m (Recomendado)"), 300)
        self.assertEqual(parse_duration_string("1h (1 hora)"), 3600)
        self.assertEqual(parse_duration_string("10m (10 minutos)"), 600)

    def test_parse_duration_raw_seconds(self):
        self.assertEqual(parse_duration_string("300"), 300)
        self.assertEqual(parse_duration_string("240"), 240)
        self.assertEqual(parse_duration_string("45s"), 45)

    def test_parse_duration_invalid(self):
        self.assertIsNone(parse_duration_string(""))
        self.assertIsNone(parse_duration_string("invalid"))
        self.assertIsNone(parse_duration_string("-10m"))

    def test_format_duration(self):
        self.assertEqual(format_duration(60), "1m")
        self.assertEqual(format_duration(240), "4m")
        self.assertEqual(format_duration(300), "5m")
        self.assertEqual(format_duration(600), "10m")
        self.assertEqual(format_duration(3600), "1h")
        self.assertEqual(format_duration(7200), "2h")
        self.assertEqual(format_duration(10800), "3h")
        self.assertEqual(format_duration(28800), "8h")
        self.assertEqual(format_duration(86400), "1d")
        self.assertEqual(format_duration(5400), "1h 30m")
        self.assertEqual(format_duration(45), "45s")

    def test_format_duration_display(self):
        self.assertEqual(format_duration_display(300), "5m (Recomendado)")
        self.assertEqual(format_duration_display(3600), "1h")
        self.assertEqual(format_duration_display(600), "10m")

    def test_debounce_presets_are_valid(self):
        self.assertTrue(len(DEBOUNCE_PRESETS) > 5)
        for preset in DEBOUNCE_PRESETS:
            parsed = parse_duration_string(preset)
            self.assertIsNotNone(parsed)
            self.assertGreater(parsed, 0)
