"""Custom exceptions used by Copier."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from subprocess import CompletedProcess
from typing import TYPE_CHECKING

from ._tools import printf_exception
from ._types import PathSeq

if TYPE_CHECKING:  # always false
    from ._template import Template
    from ._user_data import AnswersMap, Question

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


__all__ = [
    "CopierError",
    "UserMessageError",
    "UnsupportedVersionError",
    "ConfigFileError",
    "InvalidConfigFileError",
    "MultipleConfigFilesError",
    "InvalidTypeError",
    "PathError",
    "PathNotAbsoluteError",
    "PathNotRelativeError",
    "ForbiddenPathError",
    "ExtensionNotFoundError",
    "CopierAnswersInterrupt",
    "UnsafeTemplateError",
    "YieldTagInFileError",
    "MultipleYieldTagsError",
    "TaskError",
    "CopierWarning",
    "UnknownCopierVersionWarning",
    "OldTemplateWarning",
    "DirtyLocalWarning",
    "ShallowCloneWarning",
    "MissingSettingsWarning",
    "MissingFileWarning",
    "InteractiveSessionError",
    "TemplateRenderError",
    "MissingFieldError",
    "InvalidTemplateVariableError",
    "AnswersFileError",
]


# Errors
class CopierError(Exception):
    """Base class for all other Copier errors."""


class UserMessageError(CopierError):
    """Exit the program giving a message to the user."""

    def __init__(self, message: str):
        self.message = message

    def __str__(self) -> str:
        return self.message


class UnsupportedVersionError(UserMessageError):
    """Copier version does not support template version."""


class ConfigFileError(UserMessageError, ValueError):
    """Parent class defining problems with the config file.

    This error inherits from UserMessageError so it can be properly
    caught and displayed by the CLI error handler.
    It also inherits from ValueError for backward compatibility.
    """


class InvalidConfigFileError(ConfigFileError):
    """Indicates that the config file is wrong.

    Attributes:
        conf_path: Path to the invalid config file.
        original_error: The original exception that caused this error.
        line_number: Line number where the error occurred (if available).
        column_number: Column number where the error occurred (if available).
        problem: Description of the problem (if available).
    """

    def __init__(
        self,
        conf_path: Path,
        original_error: Exception | None = None,
        quiet: bool = False,
    ):
        self.conf_path = conf_path
        self.original_error = original_error
        self.line_number: int | None = None
        self.column_number: int | None = None
        self.problem: str | None = None
        self.context: str | None = None

        message_parts = [f"ERROR: Invalid config file: {conf_path}"]

        if original_error:
            if hasattr(original_error, "problem") and original_error.problem:
                self.problem = str(original_error.problem)

            if hasattr(original_error, "problem_mark") and original_error.problem_mark:
                mark = original_error.problem_mark
                self.line_number = mark.line + 1
                self.column_number = mark.column + 1
                message_parts.append(
                    f"  at line {self.line_number}, column {self.column_number}"
                )

            if self.problem:
                message_parts.append(f"  Problem: {self.problem}")

            if hasattr(original_error, "context") and original_error.context:
                self.context = str(original_error.context)
                message_parts.append(f"  Context: {self.context}")

            if not self.problem and not self.line_number:
                message_parts.append(f"  Error: {original_error}")
        else:
            message_parts.append("  The configuration file contains syntax errors.")

        message_parts.append("")
        message_parts.append("Hint: Please check your YAML syntax.")
        message_parts.append("  Common issues include:")
        message_parts.append("  - Missing colons after key names")
        message_parts.append("  - Incorrect indentation")
        message_parts.append("  - Unclosed quotes or brackets")

        super().__init__("\n".join(message_parts))


class MultipleConfigFilesError(ConfigFileError):
    """Both copier.yml and copier.yaml found, and that's an error.

    Attributes:
        conf_paths: List of paths to the conflicting config files.
    """

    def __init__(self, conf_paths: PathSeq):
        self.conf_paths = conf_paths

        message_parts = [
            f"ERROR: Multiple config files found: {conf_paths}",
            "",
            "Hint: Please remove all but one of them.",
            f"  Copier supports either 'copier.yml' or 'copier.yaml', not both.",
        ]

        super().__init__("\n".join(message_parts))


class InvalidTypeError(TypeError, CopierError):
    """The question type is not among the supported ones."""


class PathError(CopierError, ValueError):
    """The path is invalid in the given context."""


class PathNotAbsoluteError(PathError):
    """The path is not absolute, but it should be."""

    def __init__(self, *, path: Path) -> None:
        super().__init__(f'"{path}" is not an absolute path')


class PathNotRelativeError(PathError):
    """The path is not relative, but it should be."""

    def __init__(self, *, path: Path) -> None:
        super().__init__(f'"{path}" is not a relative path')


class ForbiddenPathError(PathError):
    """The path is forbidden in the given context."""

    def __init__(self, *, path: Path, hint: str = "") -> None:
        super().__init__(f'"{path}" is forbidden' + (f"\n\n{hint}" if hint else ""))


class ExtensionNotFoundError(UserMessageError):
    """Extensions listed in the configuration could not be loaded."""


class CopierAnswersInterrupt(CopierError, KeyboardInterrupt):
    """CopierAnswersInterrupt is raised during interactive question prompts.

    It typically follows a KeyboardInterrupt (i.e. ctrl-c) and provides an
    opportunity for the caller to conduct additional cleanup, such as writing
    the partially completed answers to a file.

    Attributes:
        answers:
            AnswersMap that contains the partially completed answers object.

        last_question:
            Question representing the last_question that was asked at the time
            the interrupt was raised.

        template:
            Template that was being processed for answers.

    """

    def __init__(
        self, answers: AnswersMap, last_question: Question, template: Template
    ) -> None:
        self.answers = answers
        self.last_question = last_question
        self.template = template


class UnsafeTemplateError(CopierError):
    """Unsafe Copier template features are used without explicit consent."""

    def __init__(self, features: Sequence[str]):
        assert features
        s = "s" if len(features) > 1 else ""
        super().__init__(
            f"Template uses potentially unsafe feature{s}: {', '.join(features)}.\n"
            "If you trust this template, consider adding the `--trust` option when running `copier copy/update`."
        )


class YieldTagInFileError(CopierError):
    """A yield tag is used in the file content, but it is not allowed."""


class MultipleYieldTagsError(CopierError):
    """Multiple yield tags are used in one path name, but it is not allowed."""


class TaskError(subprocess.CalledProcessError, UserMessageError):
    """Exception raised when a task fails."""

    def __init__(
        self,
        command: str | Sequence[str],
        returncode: int,
        stdout: str | bytes | None,
        stderr: str | bytes | None,
    ):
        subprocess.CalledProcessError.__init__(
            self, returncode=returncode, cmd=command, output=stdout, stderr=stderr
        )
        message = f"Task {command!r} returned non-zero exit status {returncode}."
        UserMessageError.__init__(self, message)

    @classmethod
    def from_process(
        cls, process: CompletedProcess[str] | CompletedProcess[bytes]
    ) -> Self:
        """Create a TaskError from a CompletedProcess."""
        return cls(
            command=process.args,
            returncode=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
        )


# Warnings
class CopierWarning(Warning):
    """Base class for all other Copier warnings."""


class UnknownCopierVersionWarning(UserWarning, CopierWarning):
    """Cannot determine installed Copier version."""


class OldTemplateWarning(UserWarning, CopierWarning):
    """Template was designed for an older Copier version."""


class DirtyLocalWarning(UserWarning, CopierWarning):
    """Changes and untracked files present in template."""


class ShallowCloneWarning(UserWarning, CopierWarning):
    """The template repository is a shallow clone."""


class MissingSettingsWarning(UserWarning, CopierWarning):
    """Settings path has been defined but file is missing."""


class MissingFileWarning(UserWarning, CopierWarning):
    """I still couldn't find what I'm looking for."""


class InteractiveSessionError(UserMessageError):
    """An interactive session is required to run this program."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Interactive session required: {message}")


class SettingsError(CopierError):
    """Exception raised when the settings are invalid."""


class AnswersFileError(UserMessageError):
    """Base exception for answers file related errors."""


class MissingFieldError(AnswersFileError):
    """Exception raised when a required field is missing from the answers file.

    Attributes:
        field_name: The name of the missing field.
        template_path: Path to the template that defines the field.
        answers_file_path: Path to the answers file that is missing the field.
    """

    def __init__(
        self,
        field_name: str,
        template_path: str | None = None,
        answers_file_path: str | None = None,
    ):
        self.field_name = field_name
        self.template_path = template_path
        self.answers_file_path = answers_file_path

        message_parts = [f"Missing required field: '{field_name}'"]
        if template_path:
            message_parts.append(f"  Defined in template: {template_path}")
        if answers_file_path:
            message_parts.append(f"  Missing from answers file: {answers_file_path}")
        message_parts.append("\nThis field is required by the template but was not found in your answers file.")
        message_parts.append("Please provide a value for this field or check your answers file.")

        super().__init__("\n".join(message_parts))


class InvalidTemplateVariableError(UserMessageError):
    """Exception raised when an invalid template variable is used.

    Attributes:
        variable_name: The name of the invalid/undefined variable.
        template_file: Path to the template file containing the invalid variable.
        line_number: Line number where the variable was used (if available).
        context: Additional context about the error.
    """

    def __init__(
        self,
        variable_name: str,
        template_file: str | None = None,
        line_number: int | None = None,
        context: str | None = None,
    ):
        self.variable_name = variable_name
        self.template_file = template_file
        self.line_number = line_number
        self.context = context

        message_parts = [f"Undefined template variable: '{variable_name}'"]
        if template_file:
            file_info = f"  In file: {template_file}"
            if line_number:
                file_info += f" (line {line_number})"
            message_parts.append(file_info)
        if context:
            message_parts.append(f"  Context: {context}")
        message_parts.append("\nThis variable is not defined in the template context.")
        message_parts.append("Please check your template for typos or ensure the variable is properly defined.")

        super().__init__("\n".join(message_parts))


class TemplateRenderError(UserMessageError):
    """Exception raised when template rendering fails.

    Attributes:
        template_file: Path to the template file that failed to render.
        original_error: The original exception that caused the failure.
        context: Additional context about where the error occurred.
    """

    def __init__(
        self,
        template_file: str | None = None,
        original_error: Exception | None = None,
        context: str | None = None,
    ):
        self.template_file = template_file
        self.original_error = original_error
        self.context = context

        message_parts = ["Template rendering failed"]
        if template_file:
            message_parts.append(f"  File: {template_file}")
        if context:
            message_parts.append(f"  Context: {context}")
        if original_error:
            message_parts.append(f"\nOriginal error: {original_error}")
        message_parts.append("\nPlease check your template syntax and variables.")

        super().__init__("\n".join(message_parts))
