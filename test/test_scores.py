#!/usr/bin/env python3
"""
Test suite for codegen/scores.py
Exercises all major functionality without writing data to disk.
"""

import unittest
from pathlib import Path
from dataclasses import fields

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'codegen'))

from scores import (
    # Constants
    HIGHLIGHT_KEY_MARKER,
    SCREEN_PLACE_HOLDER,
    ASCII_FILL_CHARACTER,
    
    # Functions
    find_highlight_idx_in_unicode,
    filter_special_markers_from_unicode,
    unicode_to_atari_hex2,
    byte_as_hex,
    center_string,
    replace_template,
    get_label_text,
    get_screen_frame,
    create_pip_region,
    create_dice_region,
    create_ram_region,
    add_game_values_to_region,
    
    # Classes
    DiePip,
    ScreenElement,
    TextProcessingMixin,
    GameValue,
    LabelText,
    DieContainer,
    TextCollection,
    LabelPosition,
    LabelExtractor,
    ScreenElements,
)


class TestHighlightMarkers(unittest.TestCase):
    """Test highlight marker extraction and filtering."""
    
    def test_no_markers(self):
        """Test text with no highlight markers."""
        filtered, positions = find_highlight_idx_in_unicode("Hello World")
        self.assertEqual(filtered, "Hello World")
        self.assertEqual(positions, [])
    
    def test_single_marker(self):
        """Test text with single highlight marker."""
        filtered, positions = find_highlight_idx_in_unicode("H~e~l~lo")
        self.assertEqual(filtered, "Hello")
        self.assertEqual(positions, [1, 2, 3])
    
    def test_consecutive_markers(self):
        """Test consecutive highlight markers - each marker gets a position."""
        filtered, positions = find_highlight_idx_in_unicode("~~Test~~")
        # Each ~ creates a position entry; first two map to pos 0 in filtered text,
        # last two map to pos 4 (after removing 2 markers)
        self.assertEqual(filtered, "Test")
        self.assertEqual(positions, [0, 0, 4, 4])
    
    def test_mixed_positions(self):
        """Test markers at various positions."""
        filtered, positions = find_highlight_idx_in_unicode("A~B~CDE~F")
        self.assertEqual(filtered, "ABCDEF")
        self.assertEqual(positions, [1, 2, 5])
    
    def test_filter_function(self):
        """Test the filter function directly."""
        result = filter_special_markers_from_unicode("Te~st")
        self.assertEqual(result, "Test")


class TestUnicodeToATASCII(unittest.TestCase):
    """Test Unicode to ATASCII conversion."""
    
    def test_simple_text(self):
        """Test simple ASCII text conversion."""
        result = unicode_to_atari_hex2("ABC", [])
        # Verify it produces hex byte strings
        self.assertTrue(all(b.startswith('$') for b in result))
        # Verify we got 3 bytes back
        self.assertEqual(len(result), 3)
        # 'A' should convert to some valid ATASCII value
        self.assertIsNotNone(result[0])
    
    def test_high_bit_on_highlighted_chars(self):
        """Test that high bit is set on highlighted characters."""
        result = unicode_to_atari_hex2("AB", [1])  # Highlight position 1 (B)
        
        # Check second byte contains '8' or '9' indicating high bit set
        # High bit adds $80, so hex digits will be 8-F
        has_high_bit = any(c in '89ABCDEF' for c in result[1])
        self.assertTrue(has_high_bit, f"Expected high bit in {result[1]}")
    
    def test_space_conversion(self):
        """Test space character conversion."""
        result = unicode_to_atari_hex2(" ", [])
        # Space is at index 32 in ATASCII, so should be $20
        self.assertEqual(result[0], '$20')
    
    def test_invalid_char_raises_error(self):
        """Test that invalid characters raise ValueError."""
        with self.assertRaises(ValueError):
            # Use a character not in the ATASCII map
            unicode_to_atari_hex2("日本語", [])


class TestByteFormatting(unittest.TestCase):
    """Test byte formatting utilities."""
    
    def test_valid_bytes(self):
        """Test valid byte range."""
        self.assertEqual(byte_as_hex(0), "$00")
        self.assertEqual(byte_as_hex(255), "$FF")
        self.assertEqual(byte_as_hex(128), "$80")
        self.assertEqual(byte_as_hex(42), "$2A")
    
    def test_out_of_range_low(self):
        """Test negative values raise error."""
        with self.assertRaises(ValueError):
            byte_as_hex(-1)
    
    def test_out_of_range_high(self):
        """Test values > 255 raise error."""
        with self.assertRaises(ValueError):
            byte_as_hex(256)


class TestStringCentering(unittest.TestCase):
    """Test string centering function."""
    
    def test_perfect_fit(self):
        """Test text that fits exactly."""
        result = center_string("ABC", 3)
        self.assertEqual(result, "ABC")
    
    def test_even_padding(self):
        """Test text with even padding."""
        result = center_string("AB", 6)
        # Should have 2 spaces on each side
        self.assertEqual(result, "  AB  ")
    
    def test_odd_padding(self):
        """Test text with odd padding (extra space on right)."""
        result = center_string("A", 4)
        # 3 spaces total: left=1, right=2
        self.assertEqual(result, " A  ")
    
    def test_with_markers(self):
        """Test centering uses only visible chars for width calculation."""
        result = center_string("~A~B", 10)
        # "~A~B" has 4 chars total, but filter removes '~' giving "AB" (length 2)
        # total_padding = 10 - 2 = 8 -> 5 left, 3 right
        # result = 5 + 4 + 3 = 12 characters total
        self.assertEqual(len(result), 12)
        # Verify the markers are preserved in output
        self.assertIn(HIGHLIGHT_KEY_MARKER, result)
    
    def test_too_long_text(self):
        """Test text longer than width returns unchanged."""
        result = center_string("ABCDEFG", 5)
        self.assertEqual(result, "ABCDEFG")


class TestTemplateReplacement(unittest.TestCase):
    """Test template replacement function."""
    
    def test_basic_replacement(self):
        """Test basic template replacement."""
        original = "Hello World"
        new_text = "TEST"
        idx = 0
        length = 5
        
        result = replace_template(original, new_text, idx, length)
        
        # Should replace first 5 characters with dots
        self.assertEqual(result[:5], ASCII_FILL_CHARACTER * 5)
        self.assertEqual(result[5:], " World")
    
    def test_middle_replacement(self):
        """Test replacement replaces characters with dots at given position."""
        original = "0123456789"
        result = replace_template(original, "", 3, 4)
        
        # Characters before idx should be unchanged
        self.assertEqual(result[:3], "012")
        # The template_length=4 chars starting at idx=3 become dots
        self.assertEqual(result[3:7], ASCII_FILL_CHARACTER * 4)
        # Characters after the replaced section (starting at index 7) remain
        self.assertEqual(result[7:], "789")
    
    def test_full_length(self):
        """Test replacing entire string."""
        original = "Complete"
        result = replace_template(original, "", 0, len(original))
        
        self.assertTrue(all(c == ASCII_FILL_CHARACTER for c in result))


class TestLabelExtraction(unittest.TestCase):
    """Test label extraction from Unicode art."""
    
    def setUp(self):
        """Set up sample ASCII art lines."""
        self.sample_lines = [
            " |#L1C####### #S1C |#L3K####### #S3K  | ",
            " |#L2C####### #S2C |#L4K####### #S4K  | ",
        ]
    
    def test_extract_labels(self):
        """Test basic label extraction."""
        extractor = LabelExtractor(self.sample_lines)
        labels = extractor.extract_labels()
        
        self.assertIsInstance(labels, list)
        self.assertGreater(len(labels), 0)
    
    def test_label_names(self):
        """Test that label names are extracted correctly."""
        extractor = LabelExtractor(self.sample_lines)
        labels = extractor.extract_labels()
        
        label_names = [l.name for l in labels]
        self.assertIn("L1C", label_names)
        self.assertIn("S1C", label_names)
        self.assertIn("L3K", label_names)
    
    def test_label_positions(self):
        """Test that positions are calculated correctly."""
        extractor = LabelExtractor(self.sample_lines)
        labels = extractor.extract_labels()
        
        # First line (index 0) should have L1C at column 2
        l1c = next((l for l in labels if l.name == "L1C"), None)
        self.assertIsNotNone(l1c)
        self.assertEqual(l1c.screen_row, 0)
        self.assertEqual(l1c.screen_col, 2)
    
    def test_template_length_calculation(self):
        """Test template length includes name and padding."""
        lines = [" |#ABC######|"]
        extractor = LabelExtractor(lines)
        labels = extractor.extract_labels()
        
        abc_label = labels[0]
        self.assertEqual(abc_label.template_length, 10)


class TestDataClasses(unittest.TestCase):
    """Test dataclass initialization and default values."""
    
    def test_die_pip_defaults(self):
        """Test DiePip with defaults."""
        pip = DiePip()
        self.assertEqual(pip.screen_row, -1)
        self.assertEqual(pip.screen_col, -1)
    
    def test_die_pip_values(self):
        """Test DiePip with values."""
        pip = DiePip(screen_row=10, screen_col=20)
        self.assertEqual(pip.screen_row, 10)
        self.assertEqual(pip.screen_col, 20)
    
    def test_screen_element_defaults(self):
        """Test ScreenElement base class."""
        elem = ScreenElement(key="TEST")
        self.assertEqual(elem.key, "TEST")
        self.assertEqual(elem.screen_row, -1)
        self.assertEqual(elem.screen_col, -1)
        self.assertEqual(elem.length, 0)
        self.assertEqual(len(elem.asm_bytes), 0)
        self.assertEqual(elem.keyboard_code, -1)
    
    def test_game_value_defaults(self):
        """Test GameValue default value."""
        gv = GameValue(key="SCORE")
        self.assertEqual(gv.default_value, 0xFFFF)
    
    def test_label_text_processing(self):
        """Test LabelText processes unicode on init."""
        label = LabelText(key="TEST", unicode="~Hel~lo")
        
        # Should have processed the text
        self.assertIsNotNone(label.highlight_key_positions)
        self.assertTrue(len(label.highlight_key_positions) > 0)
        self.assertTrue(len(label.asm_bytes) > 0)
        self.assertEqual(label.unicode, "Hello")  # Tildes removed
    
    def test_die_container_pips_list(self):
        """Test DieContainer initializes empty pips list."""
        die = DieContainer(key="DIE0", unicode="   ")
        self.assertIsInstance(die.pips, list)


class TestLabelText(unittest.TestCase):
    """Test label text retrieval and structure."""
    
    def test_get_label_text_returns_collection(self):
        """Test that get_label_text returns TextCollection."""
        collection = get_label_text()
        self.assertIsInstance(collection, TextCollection)
    
    def test_screen_labels_populated(self):
        """Test that screen labels are populated."""
        collection = get_label_text()
        self.assertGreater(len(collection.screen_labels), 0)
    
    def test_game_values_populated(self):
        """Test that game values are populated."""
        collection = get_label_text()
        self.assertGreater(len(collection.game_values), 0)
    
    def test_dice_containers_populated(self):
        """Test that dice containers are populated."""
        collection = get_label_text()
        self.assertGreater(len(collection.die_container), 0)
        self.assertEqual(len(collection.die_container), 5)  # DICE0 through DICE4
    
    def test_replacement_labels_exist(self):
        """Test replacement labels for instructions exist."""
        collection = get_label_text()
        self.assertGreater(len(collection.label_replacement_text), 0)
    
    def test_label_keys_unique(self):
        """Test that all label keys are unique."""
        collection = get_label_text()
        
        all_keys = []
        all_keys.extend([l.key for l in collection.screen_labels])
        all_keys.extend([l.key for l in collection.game_values])
        all_keys.extend([l.key for l in collection.die_container])
        all_keys.extend([l.key for l in collection.label_replacement_text])
        
        self.assertEqual(len(all_keys), len(set(all_keys)), "Duplicate keys found")
    
    def test_linked_labels_have_targets(self):
        """Test that linked labels reference valid targets."""
        collection = get_label_text()
        
        all_keys = set()
        all_keys.update(l.key for l in collection.screen_labels)
        all_keys.update(l.key for l in collection.game_values)
        all_keys.update(l.key for l in collection.die_container)
        
        for repl in collection.label_replacement_text:
            if repl.linked_to:
                self.assertIn(
                    repl.linked_to, 
                    all_keys,
                    f"Linked target {repl.linked_to} not found"
                )


class TestScreenFrame(unittest.TestCase):
    """Test screen frame generation."""
    
    def test_get_screen_frame_returns_collection(self):
        """Test main function returns TextCollection."""
        result = get_screen_frame()
        self.assertIsInstance(result, TextCollection)
    
    def test_screen_frame_exists(self):
        """Test that screen frame is created."""
        result = get_screen_frame()
        self.assertIsNotNone(result.screen_frame)
    
    def test_all_elements_positioned(self):
        """Test that all elements have positions assigned."""
        result = get_screen_frame()
        
        # Check all labels are positioned
        for label in result.screen_labels + result.game_values + result.die_container:
            self.assertGreaterEqual(label.screen_row, 0, 
                                   f"{label.key} has invalid row")
            self.assertGreaterEqual(label.screen_col, 0,
                                   f"{label.key} has invalid col")
    
    def test_dice_have_pips(self):
        """Test dice containers have pip data."""
        result = get_screen_frame()
        
        for die in result.die_container:
            self.assertEqual(len(die.pips), 7)  # NUMBER_OF_PIPS
    
    def test_text_conversion_complete(self):
        """Test all text was converted to ATASCII bytes."""
        result = get_screen_frame()
        
        # GameValue doesn't process text, only LabelText and DieContainer do
        # Check LabelText and DieContainer have asm_bytes
        for label in result.screen_labels + result.die_container:
            self.assertTrue(
                len(label.asm_bytes) > 0,
                f"{label.key} has no ASM bytes"
            )


class TestAssemblyGeneration(unittest.TestCase):
    """Test assembly code generation functions."""
    
    def setUp(self):
        """Create sample data for tests."""
        self.collection = get_label_simple()
    
    def test_create_ram_region_structure(self):
        """Test RAM region creation structure."""
        labels = [
            GameValue(key="TEST1", default_value=100),
            GameValue(key="TEST2", default_value=200),
        ]
        
        lines = create_ram_region("PREFIX", labels)
        
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 0)
        
        # Verify header/footer comments
        self.assertTrue(any("REGION" in line for line in lines))
        self.assertTrue(any("START_REGION" in line for line in lines))
        self.assertTrue(any("END_REGION" in line for line in lines))
    
    def test_create_dice_region_structure(self):
        """Test dice region creation."""
        dice = [DieContainer(key=f"DICE{i}", unicode=" ") for i in range(5)]
        
        lines = create_dice_region(dice)
        
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 0)
        self.assertTrue(any("DICE_VALUES" in line for line in lines))
    
    def test_create_pip_region_structure(self):
        """Test pip region creation."""
        # Create a die with actual pips
        die = DieContainer(key="DIE0", unicode="   ")
        for _i in range(7):
            die.pips.append(DiePip(screen_row=10+_i, screen_col=20+_i))
        
        lines = create_pip_region([die])
        
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 0)
        self.assertTrue(any("PIP_PTR" in line for line in lines))
        self.assertTrue(any(".BYTE" in line for line in lines))


class TestScreenElements(unittest.TestCase):
    """Test ScreenElements data structure."""
    
    def test_empty_screen_elements(self):
        """Test empty ScreenElements initialization."""
        h = ScreenElements()
        
        self.assertEqual(h.offset_counter, 0)
        self.assertEqual(len(h.header), 0)
        self.assertEqual(len(h.equates), 0)
        self.assertEqual(len(h.out_text), 0)
    
    def test_add_game_values_modifies_state(self):
        """Test adding game values modifies ScreenElements."""
        h = ScreenElements()
        labels = [
            GameValue(key="GV1", default_value=100),
            GameValue(key="GV2", default_value=200),
        ]
        
        add_game_values_to_region("TEST", labels, h)
        
        # Should have modified the structure
        self.assertGreater(len(h.equates), 0)
        self.assertGreater(len(h.pos_row), 0)


def get_label_simple():
    """Helper to create a minimal label text collection for testing."""
    return TextCollection(
        screen_labels=[
            LabelText(key="LBL1", unicode="~Test"),
        ],
        game_values=[
            GameValue(key="GVAL", default_value=42),
        ],
        die_container=[
            DieContainer(key="DIE0", unicode="   "),
        ]
    )


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows."""
    
    def test_full_pipeline(self):
        """Test the complete generation pipeline."""
        # Get screen frame (main entry point)
        collection = get_screen_frame()
        
        # Verify all components present
        self.assertIsNotNone(collection.screen_frame)
        self.assertTrue(len(collection.screen_labels) > 0)
        self.assertTrue(len(collection.game_values) > 0)
        self.assertTrue(len(collection.die_container) == 5)
    
    def test_text_conversion_integration(self):
        """Test that highlight markers work through entire pipeline."""
        label = LabelText(key="TEST", unicode="~A~B~C")
        
        # Verify processing happened
        self.assertEqual(label.unicode, "ABC")
        self.assertEqual(len(label.highlight_key_positions), 3)
        self.assertTrue(all(pos < len("ABC") for pos in label.highlight_key_positions))
    
    def test_dice_pip_generation(self):
        """Test dice pip positions are valid."""
        result = get_screen_frame()
        
        for die in result.die_container:
            for pip in die.pips:
                if pip.screen_row >= 0:  # Skip uninitialized pips
                    self.assertGreaterEqual(pip.screen_col, 0)


if __name__ == '__main__':
    unittest.main()