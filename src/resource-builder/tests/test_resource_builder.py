import os
import sys
import unittest

TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, TEST_ROOT)

import resource_builder as rb


class ResourceBuilderTests(unittest.TestCase):
    def test_byte_as_hex_valid(self):
        self.assertEqual(rb.byte_as_hex(0), "$00")
        self.assertEqual(rb.byte_as_hex(255), "$FF")

    def test_byte_as_hex_out_of_range(self):
        with self.assertRaises(ValueError):
            rb.byte_as_hex(256)

        with self.assertRaises(ValueError):
            rb.byte_as_hex(-1)

    def test_filter_special_markers_from_unicode(self):
        self.assertEqual(rb.filter_special_markers_from_unicode("a~b~c"), "abc")

    def test_find_highlight_idx_in_unicode(self):
        filtered, positions = rb.find_highlight_idx_in_unicode("~A~bc~D")
        self.assertEqual(filtered, "AbcD")
        self.assertEqual(positions, [0, 1, 3])

    def test_unicode_to_atari_hex2_basic(self):
        expected_a = rb.byte_as_hex(rb.ATASCII_MAP["A"] + 0x80)
        expected_exc = rb.byte_as_hex(rb.ATASCII_MAP["!"])
        self.assertEqual(rb.unicode_to_atari_hex2("A!", [0]), [expected_a, expected_exc])

    def test_unicode_to_atari_hex2_requires_escape(self):
        output = rb.unicode_to_atari_hex2("←", [])
        self.assertEqual(output[0], rb.byte_as_hex(rb.ATASCII_MAP[rb.ATASCII_ESCAPE]))
        self.assertEqual(output[1], rb.byte_as_hex(rb.ATASCII_MAP["←"]))

    def test_replace_template(self):
        self.assertEqual(rb.replace_template("abcdef", "x", 1, 3), "a===ef")

    def test_center_string(self):
        self.assertEqual(rb.center_string("abc", 7), "  abc  ")
        self.assertEqual(rb.center_string("~ab~c", 7), "  ~ab~c  ")

    def test_label_extractor(self):
        lines = ["foo #TEST#### bar", "nothing here"]
        extractor = rb.LabelExtractor(lines)
        labels = extractor.extract_labels()
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0].name, "TEST")
        self.assertEqual(labels[0].screen_row, 0)
        self.assertEqual(labels[0].screen_col, 4)
        self.assertEqual(labels[0].template_length, 1 + len("TEST") + 4)

    def test_get_screen_frame_assigns_positions(self):
        frame = rb.get_screen_frame()
        self.assertIsNotNone(frame.screen_frame)
        self.assertGreater(len(frame.game_values), 0)
        self.assertEqual(len(frame.screen_elements), 5)
        self.assertTrue(all(label.screen_row >= 0 for label in frame.game_values))
        self.assertTrue(all(label.screen_col >= 0 for label in frame.game_values))

    def test_create_ram_region(self):
        label = rb.ScreenElement(key="TST", default_value=0x1234)
        region = rb.create_ram_region("RAM", [label])
        self.assertIn("START_REGION_RAM", region)
        self.assertIn("END_REGION_RAM", region)
        self.assertIn("RAM_VALUE_LSB_TST  .BYTE <4660", region)
        self.assertIn("RAM_VALUE_MSB_TST  .BYTE >4660", region)


if __name__ == "__main__":
    unittest.main()
