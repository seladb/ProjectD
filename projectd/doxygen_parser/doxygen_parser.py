import os
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Any, Callable

from cxxheaderparser.simple import ClassScope, NamespaceScope
from cxxheaderparser.types import AnonymousName, EnumDecl, Enumerator, Field, Method, Parameter

from projectd.doxygen_parser.dataclasses import CommandDoc, DocBlock, DocElement
from projectd.doxygen_parser.process_lines import process_lines


class Direction(str, Enum):
    IN = "in"
    OUT = "out"
    INOUT = "in,out"


@dataclass
class Param:
    name: str
    desc: DocBlock
    param_type: str
    direction: Direction


@dataclass
class EntityDoc:
    name: str
    desc: DocBlock | None
    brief: DocBlock | None
    deprecated: DocBlock | None
    todo: DocBlock | None

    @classmethod
    def _from_doxygen_string(cls, doxygen: str | None) -> tuple[dict[str, Any], list[CommandDoc]]:
        commands_and_data: list[CommandDoc] = []
        if doxygen:
            commands_and_data = process_lines(doxygen.splitlines())

        kwargs = {
            "brief": next((cmd.doc for cmd in commands_and_data if cmd.name == "brief"), None),
            "desc": next((cmd.doc for cmd in commands_and_data if cmd.name == ""), None),
            "deprecated": next((cmd.doc for cmd in commands_and_data if cmd.name == "deprecated"), None),
            "todo": next((cmd.doc for cmd in commands_and_data if cmd.name == "todo"), None),
        }
        return kwargs, commands_and_data

    @classmethod
    def _is_public_attribute_or_method(cls, class_doc: "ClassDoc", attr_or_method_name: str) -> bool:
        return any(attr_or_method_name == public_method.name for public_method in class_doc.public_methods) or any(
            attr_or_method_name == public_attr.name for public_attr in class_doc.public_attributes
        )

    @classmethod
    def _update_text_block(
        cls,
        text_block: str,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        class_link: Callable[[str, str, str | None], str],
    ) -> str:
        # ruff: noqa: C901
        text_block_str = str(text_block)
        index_of_first_non_whitespace = len(text_block_str) - len(text_block_str.lstrip())
        prefix = text_block_str[:index_of_first_non_whitespace]
        words = []
        for word in text_block_str.split():
            if word in ["@ref", "\\ref"]:
                continue

            namespace = ""
            klass = ""
            method = ""

            stripped_word = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", word)
            split_word = re.split(r"::|#", stripped_word)
            if len(split_word) == 1:
                if split_word[0] in namespace_docs:
                    namespace = split_word[0]
                elif split_word[0] in namespace_docs[cur_namespace].classes:
                    namespace = cur_namespace
                    klass = split_word[0]
            elif len(split_word) == 2:
                split_word[1] = split_word[1].replace("()", "")
                if split_word[0] in namespace_docs and split_word[1] in namespace_docs[split_word[0]].classes:
                    namespace = split_word[0]
                    klass = split_word[1]
                elif split_word[0] in namespace_docs[cur_namespace].classes and cls._is_public_attribute_or_method(
                    namespace_docs[cur_namespace].classes[split_word[0]], split_word[1]
                ):
                    namespace = cur_namespace
                    klass = split_word[0]
                    method = split_word[1]
            elif len(split_word) == 3 and (
                split_word[0] in namespace_docs
                and split_word[1] in namespace_docs[split_word[0]].classes
                and cls._is_public_attribute_or_method(
                    namespace_docs[split_word[0]].classes[split_word[1]], split_word[2]
                )
            ):
                namespace = split_word[0]
                klass = split_word[1]
                method = split_word[2]

            if namespace or klass or method:
                word_with_link = word.replace(stripped_word, class_link(namespace, klass, method))
                words.append(word_with_link)
            else:
                words.append(word)

        return prefix + " ".join(words)

    def _update_doc_block(
        self,
        block: DocBlock,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ) -> DocBlock:
        doc_elements = []
        for element in block.elements:
            updated_text = ""
            if element.element_type in ["code", "verbatim"]:
                updated_text = code_template(element.text)
            elif element.element_type == "text":
                updated_text = self._update_text_block(element.text, namespace_docs, cur_namespace, class_link)

            doc_elements.append(DocElement(text=updated_text, element_type=element.element_type))

        return DocBlock(elements=doc_elements)

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ) -> None:
        if self.brief:
            self.brief = self._update_doc_block(self.brief, namespace_docs, cur_namespace, code_template, class_link)
        if self.desc:
            self.desc = self._update_doc_block(self.desc, namespace_docs, cur_namespace, code_template, class_link)

    def __repr__(self) -> str:
        return self.name


@dataclass
class MethodDoc(EntityDoc):
    params: list[Param]
    static: bool
    inline: bool
    const: bool
    volatile: bool
    constructor: bool
    explicit: bool
    default: bool
    deleted: bool
    destructor: bool
    pure_virtual: bool
    virtual: bool
    final: bool
    override: bool
    returns: DocBlock | None = None
    return_type: str | None = None

    @classmethod
    def parse_param(cls, param_doc: CommandDoc, params: list[Parameter]) -> Param | None:
        param_pattern = r"^param(?:\[(in|out|inout)\])?$"

        if not param_doc.doc:
            return None

        match = re.match(param_pattern, param_doc.name)

        if not match:
            return None

        direction_from_regex = match.group(1)
        if direction_from_regex == "inout":
            direction_from_regex = "in,out"

        direction = Direction(direction_from_regex) if direction_from_regex else Direction.IN

        try:
            param_name, param_desc = param_doc.doc.elements[0].text.split(" ", 1)
        except ValueError:
            return None

        if param := next((param for param in params if param.name == param_name), None):
            param_desc_block = DocBlock(
                elements=[DocElement(text=param_desc, element_type="text")] + param_doc.doc.elements[1:]
            )
            return Param(name=param_name, desc=param_desc_block, direction=direction, param_type=param.type.format())

        return None

    @classmethod
    def parse(cls, method: Method) -> "MethodDoc | None":
        kwargs, commands_and_data = super()._from_doxygen_string(method.doxygen)
        kwargs["name"] = method.name.format()
        params = []

        kwargs["returns"] = next((cmd.doc for cmd in commands_and_data if cmd.name in ["return", "returns"]), None)

        param_docs = [cmd for cmd in commands_and_data if cmd.name.startswith("param")]
        for param_doc in param_docs:
            if param := cls.parse_param(param_doc, method.parameters):
                params.append(param)

        kwargs["params"] = params
        if method.return_type:
            kwargs["return_type"] = method.return_type.format()

        for attr in [
            "static",
            "inline",
            "const",
            "volatile",
            "constructor",
            "explicit",
            "default",
            "deleted",
            "destructor",
            "pure_virtual",
            "virtual",
            "final",
            "override",
        ]:
            kwargs[attr] = getattr(method, attr)

        return cls(**kwargs)

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ) -> None:
        super().post_process(namespace_docs, cur_namespace, code_template, class_link)

        for param in self.params:
            param.desc = self._update_doc_block(param.desc, namespace_docs, cur_namespace, code_template, class_link)

        if self.returns:
            self.returns = self._update_doc_block(
                self.returns, namespace_docs, cur_namespace, code_template, class_link
            )


@dataclass
class AttributeDoc(EntityDoc):
    attribute_type: str

    @classmethod
    def parse(cls, field_scope: Field) -> "AttributeDoc":
        kwargs, _ = cls._from_doxygen_string(field_scope.doxygen)

        return cls(name=field_scope.name or "Unknown", attribute_type=field_scope.type.format(), **kwargs)


@dataclass
class EnumeratorDoc(EntityDoc):
    value: str | None

    @classmethod
    def parse(cls, enumerator: Enumerator) -> "EnumeratorDoc":
        kwargs, _ = super()._from_doxygen_string(enumerator.doxygen)
        kwargs["value"] = enumerator.value.format() if enumerator.value else None
        kwargs["name"] = enumerator.name
        return cls(**kwargs)


@dataclass
class EnumDoc(EntityDoc):
    values: list[EnumeratorDoc]

    @classmethod
    def parse(cls, enum_decl: EnumDecl) -> "EnumDoc | None":
        kwargs, commands_and_data = super()._from_doxygen_string(enum_decl.doxygen)

        enum_name = enum_decl.typename.segments[-1].format()
        for cmd in commands_and_data:
            if cmd.name == "enum" and cmd.doc:
                enum_name_and_desc = cmd.doc.elements[0].text.split(" ", 1)
                if enum_name_and_desc[0] != enum_name:
                    return None
                if len(enum_name_and_desc) > 1 and isinstance(kwargs["desc"], DocBlock):
                    kwargs["desc"] = DocBlock(elements=cmd.doc.elements + kwargs["desc"].elements)

        kwargs["name"] = enum_name
        kwargs["values"] = [EnumeratorDoc.parse(val) for val in enum_decl.values]
        return cls(**kwargs)

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ) -> None:
        super().post_process(namespace_docs, cur_namespace, code_template, class_link)

        for val in self.values:
            val.post_process(namespace_docs, cur_namespace, code_template, class_link)


@dataclass
class ClassDoc(EntityDoc):
    class_key: str
    full_name: str
    public_methods: list[MethodDoc]
    public_attributes: list[AttributeDoc]
    public_enums: dict[str, EnumDoc]
    base_classes: list[str]
    namespace: "NamespaceDoc"

    @classmethod
    def parse(cls, class_scope: ClassScope, namespace: "NamespaceDoc") -> "ClassDoc | None":
        # ruff: noqa: C901
        kwargs, commands_and_data = super()._from_doxygen_string(class_scope.class_decl.doxygen)

        name_segment = class_scope.class_decl.typename.segments[-1]
        if isinstance(name_segment, AnonymousName):
            return None

        class_name = name_segment.format()
        kwargs["name"] = class_name
        kwargs["full_name"] = "::".join(seg.format() for seg in class_scope.class_decl.typename.segments)

        for cmd in commands_and_data:
            if cmd.name == "class" and cmd.doc:
                class_name_and_desc = cmd.doc.elements[0].text.split(" ", 1)
                if class_name_and_desc[0] != class_name:
                    return None
                if len(class_name_and_desc) > 1:
                    elements = [DocElement(text=class_name_and_desc[1], element_type="text")] + cmd.doc.elements[1:]
                    kwargs["desc"] = DocBlock(elements=elements)

        public_methods = []
        for method in class_scope.methods:
            if not method.doxygen or method.access != "public":
                continue
            if method_doc := MethodDoc.parse(method):
                public_methods.append(method_doc)

        public_attributes = []
        for fld in class_scope.fields:
            if fld.access == "public":
                public_attributes.append(AttributeDoc.parse(fld))

        public_enums = {}
        for enum in class_scope.enums:
            if enum.access == "public" and (enum_doc := EnumDoc.parse(enum)):
                public_enums[enum_doc.name] = enum_doc

        kwargs["public_methods"] = public_methods
        kwargs["public_attributes"] = public_attributes
        kwargs["public_enums"] = public_enums
        kwargs["class_key"] = class_scope.class_decl.typename.classkey
        kwargs["base_classes"] = [
            base_class.typename.segments[-1].format() for base_class in class_scope.class_decl.bases
        ]
        kwargs["namespace"] = namespace

        return cls(**kwargs)

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ) -> None:
        super().post_process(namespace_docs, cur_namespace, code_template, class_link)

        for public_method in self.public_methods:
            public_method.post_process(namespace_docs, cur_namespace, code_template, class_link)

        for public_attr in self.public_attributes:
            public_attr.post_process(namespace_docs, cur_namespace, code_template, class_link)

        for public_enum in self.public_enums.values():
            public_enum.post_process(namespace_docs, cur_namespace, code_template, class_link)

    @cached_property
    def inheritance_tree(self) -> list["ClassDoc"]:
        result = [self]
        for base_class in self.base_classes:
            if base_class not in self.namespace.classes:
                continue

            base_inheritance_tree = self.namespace.classes[base_class].inheritance_tree
            for cls in base_inheritance_tree:
                if cls not in result:
                    result.append(cls)

        return result


@dataclass
class NamespaceDoc(EntityDoc):
    classes: dict[str, ClassDoc] = field(default_factory=dict)
    enums: dict[str, EnumDoc] = field(default_factory=dict)

    @classmethod
    def parse(cls, namespace_scope: NamespaceScope) -> "NamespaceDoc | None":
        kwargs, commands_and_data = super()._from_doxygen_string(namespace_scope.doxygen)

        if any(
            cmd.name == "namespace" and cmd.doc.elements[0].text.split()[0] != namespace_scope.name
            for cmd in commands_and_data
        ):
            return None

        kwargs["name"] = namespace_scope.name
        return cls(**kwargs)

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ) -> None:
        super().post_process(namespace_docs, cur_namespace, code_template, class_link)

        for enum in self.enums.values():
            enum.post_process(namespace_docs, cur_namespace, code_template, class_link)


@dataclass
class FileDoc(EntityDoc):
    namespaces: dict[str, NamespaceDoc] = field(default_factory=dict)
    classes: dict[str, ClassDoc] = field(default_factory=dict)
    enums: dict[str, EnumDoc] = field(default_factory=dict)

    @classmethod
    def parse(cls, file_path: str) -> "FileDoc":
        file_name = os.path.basename(file_path)
        return cls(name=file_name, desc=DocBlock(), brief=None, deprecated=None, todo=None)
