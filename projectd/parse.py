import os
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from cxxheaderparser.options import ParserOptions
from cxxheaderparser.preprocessor import make_pcpp_preprocessor
from cxxheaderparser.simple import parse_file

from projectd.doxygen_parser import ClassDoc, EnumDoc, FileDoc, NamespaceDoc


@dataclass
class ParsedDocData:
    namespaces: dict[str, NamespaceDoc]
    classes: dict[str, ClassDoc]
    enums: dict[str, EnumDoc]
    files: dict[str, FileDoc]


def get_base_classes(ns: NamespaceDoc, class_doc: ClassDoc) -> list[str]:
    result = [class_doc.name]
    for base_class in class_doc.base_classes:
        for class_name in get_base_classes(ns, ns.classes[base_class]):
            if class_name not in result:
                result += [class_name]

    return result


def parse(directory_paths: list[str], defines: list[str] | None = None) -> ParsedDocData:
    # ruff: noqa: C901

    if defines is None:
        defines = []
    preprocessor = make_pcpp_preprocessor(passthru_includes=re.compile(".+"), defines=defines)

    options = ParserOptions(preprocessor=preprocessor)

    namespaces = {}
    classes = {}
    files = {}
    enums = {}

    for directory_path in directory_paths:
        file_list = [
            os.path.relpath(os.path.join(root, file), start=directory_path)
            for root, _, files in os.walk(directory_path)
            for file in files
        ]

        for file_path in file_list:
            print(f"parsing {file_path}...")
            file_path = os.path.join(directory_path, file_path)
            try:
                data = parse_file(file_path, options=options)
            except:
                # ruff: noqa: E722
                print(f"{file_path} cannot be parsed!!!!!!!!!!")
                continue

            file_namespaces = {}
            file_classes = {}
            file_enums = {}
            for ns in data.namespace.namespaces.values():
                namespace_doc = NamespaceDoc.parse(ns)
                if not namespace_doc:
                    continue

                if namespace_doc.name not in namespaces:
                    namespaces[namespace_doc.name] = namespace_doc
                else:
                    namespace_doc = namespaces[namespace_doc.name]

                file_namespaces[namespace_doc.name] = namespace_doc

                for cls in ns.classes:
                    if class_doc := ClassDoc.parse(cls, namespace_doc):
                        namespaces[namespace_doc.name].classes[class_doc.name] = class_doc
                        classes[class_doc.name] = class_doc
                        file_classes[class_doc.name] = class_doc

                for enum in ns.enums:
                    if enum_doc := EnumDoc.parse(enum):
                        namespaces[namespace_doc.name].enums[enum_doc.name] = enum_doc
                        enums[enum_doc.name] = enum_doc
                        file_enums[enum_doc.name] = enum_doc

            file_doc = FileDoc.parse(file_path)
            file_doc.namespaces = file_namespaces
            file_doc.classes = file_classes
            file_doc.enums = file_enums

            files[file_path] = file_doc

    parsed_data = ParsedDocData(namespaces=namespaces, classes=classes, enums=enums, files=files)
    # with open("parsed_data.json", "w") as f:
    #     f.write(json.dumps(asdict(parsed_data), indent=2))

    return parsed_data


def post_process(
    parsed_data: ParsedDocData,
    code_template: Callable[[str], str],
    class_link: Callable[[str, str, str | None], str],
) -> ParsedDocData:
    post_processed_parsed_data = deepcopy(parsed_data)
    for ns in post_processed_parsed_data.namespaces.values():
        ns.post_process(parsed_data.namespaces, ns.name, code_template, class_link)
    for cls in post_processed_parsed_data.classes.values():
        cls.post_process(parsed_data.namespaces, cls.namespace.name, code_template, class_link)

    return post_processed_parsed_data
