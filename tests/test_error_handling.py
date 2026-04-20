from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from plumbum import local

import copier
from copier._cli import CopierApp
from copier._template import load_template_config
from copier.errors import (
    InvalidConfigFileError,
    InvalidTemplateVariableError,
    MissingFieldError,
    MultipleConfigFilesError,
    TemplateRenderError,
)

from .helpers import build_file_tree, git_save


class TestConfigFileErrors:
    """Test cases for config file errors."""

    def test_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        """Test that invalid YAML syntax provides detailed error info with line/column numbers."""
        conf_path = tmp_path / "copier.yml"

        invalid_yaml = """\
project_name: My Project
invalid_yaml: [this is invalid
description: A test project
"""

        conf_path.write_text(dedent(invalid_yaml))

        with pytest.raises(InvalidConfigFileError) as exc_info:
            load_template_config(conf_path)

        error = exc_info.value
        assert error.conf_path == conf_path
        assert error.line_number is not None
        assert error.column_number is not None
        assert error.line_number > 0
        assert error.column_number >= 0
        assert "Invalid config file" in str(error)

    def test_invalid_yaml_problem_extraction(self, tmp_path: Path) -> None:
        """Test that YAML problem and context are extracted."""
        conf_path = tmp_path / "copier.yml"

        invalid_yaml = """\
project_name: My Project
bad_syntax: { this is wrong
description: A test project
"""

        conf_path.write_text(dedent(invalid_yaml))

        with pytest.raises(InvalidConfigFileError) as exc_info:
            load_template_config(conf_path)

        error = exc_info.value
        assert error.problem is not None or error.original_error is not None
        assert "Invalid config file" in str(error)

    def test_multiple_config_files(self, tmp_path: Path) -> None:
        """Test that multiple config files error provides helpful message."""
        (tmp_path / "copier.yml").write_text("project_name: test\n")
        (tmp_path / "copier.yaml").write_text("project_name: test\n")

        with pytest.raises(MultipleConfigFilesError) as exc_info:
            load_template_config(tmp_path)

        error = exc_info.value
        assert error.conf_paths is not None
        assert "Multiple config files" in str(error)
        assert "copier.yml" in str(error) or "copier.yaml" in str(error)

    def test_config_file_error_is_user_message_error(self) -> None:
        """Test that ConfigFileError is a UserMessageError for CLI handling."""
        from copier.errors import ConfigFileError, UserMessageError

        assert issubclass(ConfigFileError, UserMessageError)
        assert issubclass(ConfigFileError, ValueError)


class TestTemplateVariableErrors:
    """Test cases for template variable errors."""

    def test_invalid_template_variable_in_file(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """Test that invalid template variables in files provide detailed error messages."""
        src = tmp_path_factory.mktemp("src")
        dst = tmp_path_factory.mktemp("dst")

        build_file_tree(
            {
                (src / "copier.yml"): (
                    """\
                    project_name:
                        type: str
                        default: My Project
                    """
                ),
                (src / "README.md.jinja"): (
                    """\
                    # {{ project_name }}
                    This is a project called {{ project_name }}.
                    But this variable does not exist: {{ nonexistent_variable }}.
                    """
                ),
                (src / "{{ _copier_conf.answers_file }}.jinja"): (
                    "{{ _copier_answers|to_nice_yaml }}"
                ),
            }
        )

        with pytest.raises(InvalidTemplateVariableError) as exc_info:
            copier.run_copy(str(src), dst, defaults=True, overwrite=True)

        error = exc_info.value
        assert error.variable_name == "nonexistent_variable"
        assert error.template_file is not None
        assert "README.md" in error.template_file
        assert "nonexistent_variable" in str(error)

    def test_invalid_template_variable_in_config(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """Test that invalid template variables in config provide detailed error messages."""
        src = tmp_path_factory.mktemp("src")
        dst = tmp_path_factory.mktemp("dst")

        build_file_tree(
            {
                (src / "copier.yml"): (
                    """\
                    _subdirectory: "{{ nonexistent_subdir }}"
                    project_name:
                        type: str
                        default: My Project
                    """
                ),
                (src / "{{ _copier_conf.answers_file }}.jinja"): (
                    "{{ _copier_answers|to_nice_yaml }}"
                ),
            }
        )

        with pytest.raises(InvalidTemplateVariableError) as exc_info:
            copier.run_copy(str(src), dst, defaults=True, overwrite=True)

        error = exc_info.value
        assert error.variable_name == "nonexistent_subdir"
        assert "nonexistent_subdir" in str(error)

    def test_template_render_error_general(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """Test that general template rendering errors are properly wrapped."""
        src = tmp_path_factory.mktemp("src")
        dst = tmp_path_factory.mktemp("dst")

        build_file_tree(
            {
                (src / "copier.yml"): (
                    """\
                    project_name:
                        type: str
                        default: My Project
                    """
                ),
                (src / "broken.md.jinja"): (
                    """\
                    {% for i in %}  {# Broken for loop #}
                    {{ i }}
                    {% endfor %}
                    """
                ),
                (src / "{{ _copier_conf.answers_file }}.jinja"): (
                    "{{ _copier_answers|to_nice_yaml }}"
                ),
            }
        )

        with pytest.raises(TemplateRenderError) as exc_info:
            copier.run_copy(str(src), dst, defaults=True, overwrite=True)

        error = exc_info.value
        assert error.template_file is not None
        assert "broken.md" in error.template_file
        assert "Template rendering failed" in str(error)


class TestMissingFieldErrors:
    """Test cases for missing field errors."""

    def test_missing_required_field(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """Test that missing required fields provide detailed error messages."""
        src = tmp_path_factory.mktemp("src")
        dst = tmp_path_factory.mktemp("dst")

        build_file_tree(
            {
                (src / "copier.yml"): (
                    """\
                    required_field:
                        type: str
                    optional_field:
                        type: str
                        default: optional
                    """
                ),
                (src / "{{ _copier_conf.answers_file }}.jinja"): (
                    "{{ _copier_answers|to_nice_yaml }}"
                ),
            }
        )

        with pytest.raises(MissingFieldError) as exc_info:
            copier.run_copy(str(src), dst, defaults=True, overwrite=True)

        error = exc_info.value
        assert error.field_name == "required_field"
        assert error.template_path is not None
        assert "required_field" in str(error)
        assert "Missing required field" in str(error)

    def test_missing_field_in_update(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """Test that missing fields during update provide detailed error messages.

        This test simulates an update scenario where a new required field is added
        to the template, but the existing answers file does not have a value for it.
        """
        src = tmp_path_factory.mktemp("src")
        dst = tmp_path_factory.mktemp("dst")

        with local.cwd(src):
            build_file_tree(
                {
                    "copier.yml": (
                        """\
                        old_field:
                            type: str
                            default: old_value
                        """
                    ),
                    "{{ _copier_conf.answers_file }}.jinja": (
                        "{{ _copier_answers|to_nice_yaml }}"
                    ),
                }
            )
            git_save()

        copier.run_copy(str(src), dst, defaults=True, overwrite=True)
        git_save(dst)

        with local.cwd(src):
            new_config = """\
old_field:
    type: str
    default: old_value
new_required_field:
    type: str
"""
            Path("copier.yml").write_text(dedent(new_config))
            git_save()

        with pytest.raises(MissingFieldError) as exc_info:
            copier.run_recopy(dst, defaults=True, overwrite=True)

        error = exc_info.value
        assert error.field_name == "new_required_field"
        assert "new_required_field" in str(error)
        assert "Missing required field" in str(error)

class TestExitStatus:
    """Test cases for command exit status."""

    def test_invalid_template_variable_exit_status(
        self, tmp_path_factory: pytest.TempPathFactory, capsys: pytest.CaptureFixture
    ) -> None:
        """Test that invalid template variables result in exit code 1."""
        src = tmp_path_factory.mktemp("src")
        dst = tmp_path_factory.mktemp("dst")

        build_file_tree(
            {
                (src / "copier.yml"): (
                    """\
                    project_name:
                        type: str
                        default: My Project
                    """
                ),
                (src / "README.md.jinja"): (
                    """\
                    # {{ nonexistent_variable }}
                    """
                ),
                (src / "{{ _copier_conf.answers_file }}.jinja"): (
                    "{{ _copier_answers|to_nice_yaml }}"
                ),
            }
        )

        result = CopierApp.run(
            [
                "copier",
                "copy",
                "--defaults",
                "--overwrite",
                str(src),
                str(dst),
            ],
            exit=False,
        )

        assert result[1] == 1

        _, err = capsys.readouterr()
        assert "nonexistent_variable" in err
        assert "Undefined template variable" in err

    def test_missing_field_exit_status(
        self, tmp_path_factory: pytest.TempPathFactory, capsys: pytest.CaptureFixture
    ) -> None:
        """Test that missing required fields result in exit code 1."""
        src = tmp_path_factory.mktemp("src")
        dst = tmp_path_factory.mktemp("dst")

        build_file_tree(
            {
                (src / "copier.yml"): (
                    """\
                    required_field:
                        type: str
                    """
                ),
                (src / "{{ _copier_conf.answers_file }}.jinja"): (
                    "{{ _copier_answers|to_nice_yaml }}"
                ),
            }
        )

        result = CopierApp.run(
            [
                "copier",
                "copy",
                "--defaults",
                "--overwrite",
                str(src),
                str(dst),
            ],
            exit=False,
        )

        assert result[1] == 1

        _, err = capsys.readouterr()
        assert "required_field" in err
        assert "Missing required field" in err

    def test_successful_copy_exit_status(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """Test that successful copy results in exit code 0."""
        src = tmp_path_factory.mktemp("src")
        dst = tmp_path_factory.mktemp("dst")

        build_file_tree(
            {
                (src / "copier.yml"): (
                    """\
                    project_name:
                        type: str
                        default: My Project
                    """
                ),
                (src / "README.md.jinja"): (
                    """\
                    # {{ project_name }}
                    """
                ),
                (src / "{{ _copier_conf.answers_file }}.jinja"): (
                    "{{ _copier_answers|to_nice_yaml }}"
                ),
            }
        )

        result = CopierApp.run(
            [
                "copier",
                "copy",
                "--defaults",
                "--overwrite",
                str(src),
                str(dst),
            ],
            exit=False,
        )

        assert result[1] == 0


class TestExtractUndefinedVariable:
    """Test cases for extracting undefined variable names from error messages."""

    def test_extract_simple_undefined(self):
        """Test extracting simple undefined variable."""
        from copier._main import _extract_undefined_variable

        error_msg = "'nonexistent_var' is undefined"
        result = _extract_undefined_variable(error_msg)
        assert result == "nonexistent_var"

    def test_extract_attribute_error(self):
        """Test extracting attribute access error."""
        from copier._main import _extract_undefined_variable

        error_msg = "'dict_obj' has no attribute 'nonexistent_key'"
        result = _extract_undefined_variable(error_msg)
        assert result == "dict_obj.nonexistent_key"

    def test_extract_element_error(self):
        """Test extracting element access error."""
        from copier._main import _extract_undefined_variable

        error_msg = "'obj' has no element 'nonexistent_key'"
        result = _extract_undefined_variable(error_msg)
        assert result == "obj.nonexistent_key"

    def test_extract_unknown_format(self):
        """Test extracting from unknown format returns None."""
        from copier._main import _extract_undefined_variable

        error_msg = "Some random error message"
        result = _extract_undefined_variable(error_msg)
        assert result is None
