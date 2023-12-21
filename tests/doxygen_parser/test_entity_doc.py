from projectd.doxygen_parser.dataclasses import CommandDoc, DocBlock, DocElement
from projectd.doxygen_parser.doxygen_parser import EntityDoc


class TestEntityDoc:
    def test_parse_all_attributes(self) -> None:
        doxygen_string = """
        /**
         * @brief Class brief description
         *
         * Class longer description that spreads
         * over multiple lines
         *
         * @todo TODO message
         * @deprecated Deprecation message
         */
        """

        expected_kwargs = {
            "brief": DocBlock(elements=[DocElement(text="Class brief description", element_type="text")]),
            "desc": DocBlock(
                elements=[
                    DocElement(text="Class longer description that spreads over multiple lines", element_type="text")
                ]
            ),
            "deprecated": DocBlock(elements=[DocElement(text="Deprecation message", element_type="text")]),
            "todo": DocBlock(elements=[DocElement(text="TODO message", element_type="text")]),
        }

        expected_commands = [
            CommandDoc(name="", doc=expected_kwargs["desc"]),
            CommandDoc(name="brief", doc=expected_kwargs["brief"]),
            CommandDoc(name="todo", doc=expected_kwargs["todo"]),
            CommandDoc(name="deprecated", doc=expected_kwargs["deprecated"]),
        ]

        assert EntityDoc._from_doxygen_string(doxygen_string) == (expected_kwargs, expected_commands)

    def test_with_unknown_keyword(self) -> None:
        doxygen_string = """
        /**
         * @keyword1 Some text
         * @code
         * int x = 2;
         * @endcode
         */
        """

        expected_kwargs = {
            "brief": None,
            "desc": None,
            "deprecated": None,
            "todo": None,
        }

        expected_commands = [
            CommandDoc(
                name="keyword1",
                doc=DocBlock(
                    elements=[
                        DocElement(text="Some text", element_type="text"),
                        DocElement(text="int x = 2;", element_type="code"),
                    ]
                ),
            ),
        ]

        assert EntityDoc._from_doxygen_string(doxygen_string) == (expected_kwargs, expected_commands)
