from cxxheaderparser.simple import NamespaceScope

from projectd.doxygen_parser import NamespaceDoc
from projectd.doxygen_parser.dataclasses import DocBlock, DocElement


class TestNamespaceDocParse:
    def test_parse(self) -> None:
        doxygen_string = """
        /// Namespace description
        """

        namespace_scope = NamespaceScope(name="foo", doxygen=doxygen_string)

        namespace_doc = NamespaceDoc.parse(namespace_scope)
        assert namespace_doc is not None
        assert namespace_doc.name == "foo"
        assert namespace_doc.desc == DocBlock(elements=[DocElement(text="Namespace description", element_type="text")])

    def test_parse_with_namespace_keyword_and_name(self) -> None:
        doxygen_string = """
        /// @namespace foo
        """

        namespace_scope = NamespaceScope(name="foo", doxygen=doxygen_string)

        namespace_doc = NamespaceDoc.parse(namespace_scope)
        assert namespace_doc is not None
        assert namespace_doc.name == "foo"
        assert namespace_doc.desc is None

    def test_parse_with_namespace_keyword_and_name_desc(self) -> None:
        doxygen_string = """
        /// @namespace foo Namespace
        /// description
        """

        namespace_scope = NamespaceScope(name="foo", doxygen=doxygen_string)

        namespace_doc = NamespaceDoc.parse(namespace_scope)
        assert namespace_doc is not None
        assert namespace_doc.name == "foo"
        assert namespace_doc.desc == DocBlock(elements=[DocElement(text="Namespace description", element_type="text")])

    def test_parse_with_namespace_keyword_and_name_desc_and_more_desc(self) -> None:
        doxygen_string = """
        /// @namespace foo Namespace
        /// description
        ///
        /// more description
        """

        namespace_scope = NamespaceScope(name="foo", doxygen=doxygen_string)

        namespace_doc = NamespaceDoc.parse(namespace_scope)
        assert namespace_doc is not None
        assert namespace_doc.name == "foo"
        assert namespace_doc.desc == DocBlock(
            elements=[
                DocElement(text="Namespace description", element_type="text"),
                DocElement(text="more description", element_type="text"),
            ]
        )

    def test_parse_with_namespace_keyword_without_name(self) -> None:
        doxygen_string = """
        /// @namespace
        """

        namespace_scope = NamespaceScope(name="foo", doxygen=doxygen_string)

        assert NamespaceDoc.parse(namespace_scope) is None

    def test_parse_with_namespace_keyword_with_different_name(self) -> None:
        doxygen_string = """
        /// @namespace bar
        """

        namespace_scope = NamespaceScope(name="foo", doxygen=doxygen_string)

        assert NamespaceDoc.parse(namespace_scope) is None
