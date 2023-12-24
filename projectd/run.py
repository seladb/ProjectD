import os
import re
from shutil import rmtree

from jinja2 import Environment, FileSystemLoader

from projectd.config import TemplateType, get_config
from projectd.parse import parse, post_process


def _delete_current_files(directory_path: str) -> None:
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)

        if os.path.isfile(item_path):
            os.remove(item_path)

        elif os.path.isdir(item_path):
            rmtree(item_path)


def _regex_replace(string: str, find: str, replace: str):  # type: ignore[no-untyped-def]
    return re.sub(find, replace, string)


def run() -> None:
    config = get_config()

    template_loader = FileSystemLoader(searchpath=config.template_dir)
    env = Environment(
        loader=template_loader, trim_blocks=True, lstrip_blocks=True, autoescape=config.auto_escape  # noqa: S701
    )
    env.filters["regex_replace"] = _regex_replace

    parsed_data = parse(config.input_dirs, config.defines)

    _delete_current_files(config.output_dir)

    code_template = env.get_template(config.code_template)
    for template_config in config.templates:
        template = env.get_template(template_config.template)
        class_link_template = env.get_template(template_config.class_link_template)
        post_processed_parsed_data = post_process(
            parsed_data,
            lambda v: code_template.render(value=v),
            # ruff: noqa: B023
            lambda word, namespace, klass, method: class_link_template.render(
                word=word, namespace=namespace, klass=klass, method=method
            ),
        )

        if template_config.template_type == TemplateType.CLASS:
            for ns in post_processed_parsed_data.namespaces.values():
                for cls in ns.classes.values():
                    file_path = os.path.join(
                        config.output_dir, template_config.output_file.replace("{class_name}", cls.name)
                    )
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "w") as f:
                        f.write(template.render(klass=cls))

        elif template_config.template_type == TemplateType.FILE:
            for file in post_processed_parsed_data.files.values():
                file_path = os.path.join(
                    config.output_dir, template_config.output_file.replace("{file_name}", file.name)
                )
                if "SSLLayer.h" in file_path:
                    print(file_path)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w") as f:
                    f.write(template.render(file=file))

        elif template_config.template_type == TemplateType.ENUMS:
            file_path = os.path.join(config.output_dir, template_config.output_file)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(template.render(enums=post_processed_parsed_data.enums.values()))
