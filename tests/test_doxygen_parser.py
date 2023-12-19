import pytest

from projectd.doxygen_parser import remove_comment_chars_from_line


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
def test_remove_comment_chars_from_line(line, expected):
    assert remove_comment_chars_from_line(line) == expected
