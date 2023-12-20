import pytest

from projectd.doxygen_parser import (
    get_keyword_and_rest_of_line,
    preprocess_lines,
    remove_comment_chars_from_line,
)


@pytest.mark.parametrize(
    "line,expected",
    [
        ("/// line", " line"),
        ("  /// line  ", " line"),
        ("///< line", " line"),
        ("//!< line", " line"),
        ("/* line */", " line "),
        ("/** line", " line"),
        ("/*! line", " line"),
        ("/** line */", " line "),
        ("line */", "line "),
        ("/**** line ****/", " line "),
    ],
)
def test_remove_comment_chars_from_line(line: str, expected: str) -> None:
    assert remove_comment_chars_from_line(line) == expected


class TestPreprocessLinesVerbatimBlock:
    @pytest.mark.parametrize("escape_char", ["@", "\\"])
    def test_verbatim_block(self, escape_char: str) -> None:
        verbatim_block = [
            f"{escape_char}verbatim",
            "line1: some text",
            "line2: some more text",
            f"{escape_char}endverbatim",
        ]

        expected = f"{escape_char}verbatim\nline1: some text\nline2: some more text"

        assert preprocess_lines(verbatim_block) == [expected]

    def test_verbatim_block_with_chars_before_endverbatim(self) -> None:
        verbatim_block = [
            "@verbatim",
            "line1: some text",
            "line2: some more text",
            "line3: even more text@endverbatim",
        ]

        expected = "@verbatim\nline1: some text\nline2: some more text\nline3: even more text"

        assert preprocess_lines(verbatim_block) == [expected]

    def test_verbatim_block_with_indentation(self) -> None:
        verbatim_block = [
            "\t  @verbatim",
            "\t  line1: some text",
            "\t  line2: some more text",
            "\t  @endverbatim",
        ]

        expected = "@verbatim\nline1: some text\nline2: some more text"

        assert preprocess_lines(verbatim_block) == [expected]

    def test_verbatim_block_with_indentation_and_prefix_spaces(self) -> None:
        verbatim_block = [
            "\t  @verbatim",
            "\t    line1: some text",
            "\t    line2: some more text",
            "\t  @endverbatim",
        ]

        expected = "@verbatim\n  line1: some text\n  line2: some more text"

        assert preprocess_lines(verbatim_block) == [expected]


class TestPreprocessLinesCodeBlock:
    @pytest.mark.parametrize("escape_char", ["@", "\\"])
    def test_code_block(self, escape_char: str) -> None:
        verbatim_block = [
            f"{escape_char}code",
            "int i = 1;",
            "call_method(i);",
            f"{escape_char}endcode",
        ]

        expected = f"{escape_char}code\nint i = 1;\ncall_method(i);"

        assert preprocess_lines(verbatim_block) == [expected]

    def test_code_block_with_ignore_chars_before_endcode(self) -> None:
        verbatim_block = [
            "@code",
            "int i = 1;",
            "call_method(i);",
            "ignore@endcode",
        ]

        expected = "@code\nint i = 1;\ncall_method(i);"

        assert preprocess_lines(verbatim_block) == [expected]

    def test_code_block_with_indentation(self) -> None:
        verbatim_block = [
            "\t  @code",
            "\t  int i = 1;",
            "\t  call_method(i);",
            "\t  @endcode",
        ]

        expected = "@code\nint i = 1;\ncall_method(i);"

        assert preprocess_lines(verbatim_block) == [expected]

    def test_code_block_with_indentation_and_prefix_spaces(self) -> None:
        verbatim_block = [
            "\t  @code",
            "\t  def some_func():",
            "\t    x = 1",
            "\t  @endcode",
        ]

        expected = "@code\ndef some_func():\n  x = 1"

        assert preprocess_lines(verbatim_block) == [expected]


class TestPreprocessLineListBlock:
    @pytest.mark.parametrize("list_item_char", ["-", "+"])
    def test_list_block(self, list_item_char: str) -> None:
        list_block = [
            f"{list_item_char} item 1",
            f"{list_item_char} item 2",
        ]

        expected = [f"@li {item}" for item in list_block]

        assert preprocess_lines(list_block) == expected

    def test_list_block_with_star(self) -> None:
        # include the comment char before the item
        list_block = [
            "* * item 1",
            "* * item 2",
        ]

        expected = [
            "@li  * item 1",
            "@li  * item 2",
        ]

        assert preprocess_lines(list_block) == expected

    def test_list_indentation_is_kept(self) -> None:
        list_block = ["* - item 1", "*  - sub item 1", "*      - sub sub item 1", "* - item 2"]

        expected = [f"@li {item.lstrip('*')}" for item in list_block]

        assert preprocess_lines(list_block) == expected

    def test_items_with_multiple_lines(self) -> None:
        list_block = [
            "* - item 1",
            "* has multiple",
            "* lines",
            "* - item 2 has one line",
            "*   - sub item 2",
            "*     has multiple lines",
        ]

        expected = [
            "@li  - item 1 has multiple lines",
            "@li  - item 2 has one line",
            "@li    - sub item 2 has multiple lines",
        ]

        assert preprocess_lines(list_block) == expected


class TestPreprocessLineOtherBlocks:
    @pytest.mark.parametrize("escape_char", ["@", "\\"])
    def test_multiple_blocks(self, escape_char: str) -> None:
        block = [
            f"{escape_char}keyword1 some text",
            f"{escape_char}keyword2 some other text",
        ]

        assert preprocess_lines(block) == block

    def test_other_block_with_multiple_lines(self) -> None:
        block = [
            "@keyword1 this item",
            "has multiple lines",
            "@keyword2 this item has one line",
            "@keyword3 this item",
            "also",
            "has multiple",
            "lines",
        ]

        expected = [
            "@keyword1 this item has multiple lines",
            "@keyword2 this item has one line",
            "@keyword3 this item also has multiple lines",
        ]

        assert preprocess_lines(block) == expected

    @pytest.mark.parametrize("list_item_char", ["-", "+", "*"])
    def test_other_block_follows_by_list(self, list_item_char: str) -> None:
        block = [
            "* @keyword1 some text",
            f"* {list_item_char} list item",
        ]

        expected = [
            "@keyword1 some text",
            f"@li  {list_item_char} list item",
        ]

        assert preprocess_lines(block) == expected

    def test_empty_input(self) -> None:
        assert preprocess_lines([""]) == []

    def test_blank_line(self) -> None:
        block = [
            "@keyword1 line 1",
            "",
            "@keyword2 line 2",
        ]

        expected = [
            "@keyword1 line 1",
            "@blank",
            "@keyword2 line 2",
        ]
        assert preprocess_lines(block) == expected

    def test_all_block_types(self) -> None:
        block = [
            "@keyword1 some text",
            "@code",
            "int i = 1;",
            "@endcode",
            "@keyword2 some text",
            "- list item 1",
            "- list item 2",
            "@verbatim",
            "line 1",
            "line 2@endverbatim",
        ]

        expected = [
            "@keyword1 some text",
            "@code\nint i = 1;",
            "@keyword2 some text",
            "@li - list item 1",
            "@li - list item 2",
            "@verbatim\nline 1\nline 2",
        ]

        assert preprocess_lines(block) == expected


class TestGetKeywordAndRestOfLine:
    @pytest.mark.parametrize("escape_char", ["@", "\\"])
    def test_simple_line(self, escape_char: str) -> None:
        line = f"{escape_char}keyword some text"
        assert get_keyword_and_rest_of_line(line) == ("keyword", "some text")

    def test_line_with_line_break(self) -> None:
        line = "@keyword\nsome text"
        assert get_keyword_and_rest_of_line(line) == ("keyword", "some text")

    def test_line_with_multiple_line_breaks(self) -> None:
        line = "@keyword\nsome text\nanother line"
        assert get_keyword_and_rest_of_line(line) == ("keyword", "some text\nanother line")

    def test_no_keyword(self) -> None:
        line = "no keyword"
        assert get_keyword_and_rest_of_line(line) == ("", line)

    def test_multiple_escape_chars_in_line(self) -> None:
        line = "@keyword @some @text"
        assert get_keyword_and_rest_of_line(line) == ("keyword", "@some @text")


# class TestProcessLines:
#     @pytest.fixture(scope="class")
#     def mock_preprocess_lines(self):
#         with patch("projectd.doxygen_parser.preprocess_lines") as p:
#             p.side_effect = lambda lines: lines
#             yield
#
#     def test_multiple_blocks(self, mock_preprocess_lines):
#         lines = [
#             "@keyword1 some text",
#             "@code\nint i = 1;",
#             "@keyword2 some text",
#             "@li - list item 1",
#             "@li - list item 2",
#             "@verbatim\nline 1\nline 2",
#         ]
#
#         expected = process_lines(lines)
#         print(expected)
