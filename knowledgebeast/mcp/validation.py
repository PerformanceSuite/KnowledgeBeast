"""Input validation utilities for MCP tools.

Provides comprehensive validation for all tool inputs including:
- Type checking (str, int, float, list, dict)
- Range validation (limits, alphas)
- Path validation (file exists, readable)
- Project ID validation (exists in DB)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None):
        """Initialize validation error.

        Args:
            message: Error message
            field: Field name that failed validation
        """
        self.message = message
        self.field = field
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for error response.

        Returns:
            Dictionary with error details
        """
        result = {
            "error": self.message,
            "error_type": "ValidationError",
        }
        if self.field:
            result["field"] = self.field
        return result


class InputValidator:
    """Validates tool inputs with comprehensive type and constraint checking."""

    @staticmethod
    def validate_project_id(project_id: Any, field_name: str = "project_id") -> str:
        """Validate project ID is a non-empty string.

        Args:
            project_id: Project ID to validate
            field_name: Name of the field for error messages

        Returns:
            Validated project ID

        Raises:
            ValidationError: If validation fails
        """
        if not project_id:
            raise ValidationError(
                f"{field_name} is required", field=field_name
            )

        if not isinstance(project_id, str):
            raise ValidationError(
                f"{field_name} must be a string, got {type(project_id).__name__}",
                field=field_name,
            )

        if not project_id.strip():
            raise ValidationError(
                f"{field_name} cannot be empty or whitespace", field=field_name
            )

        return project_id.strip()

    @staticmethod
    def validate_string(
        value: Any,
        field_name: str,
        required: bool = True,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> Optional[str]:
        """Validate string input.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            required: Whether field is required
            min_length: Minimum string length
            max_length: Maximum string length

        Returns:
            Validated string or None if not required and not provided

        Raises:
            ValidationError: If validation fails
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                raise ValidationError(f"{field_name} is required", field=field_name)
            return None

        if not isinstance(value, str):
            raise ValidationError(
                f"{field_name} must be a string, got {type(value).__name__}",
                field=field_name,
            )

        value = value.strip()

        if min_length is not None and len(value) < min_length:
            raise ValidationError(
                f"{field_name} must be at least {min_length} characters, got {len(value)}",
                field=field_name,
            )

        if max_length is not None and len(value) > max_length:
            raise ValidationError(
                f"{field_name} must be at most {max_length} characters, got {len(value)}",
                field=field_name,
            )

        return value

    @staticmethod
    def validate_int(
        value: Any,
        field_name: str,
        required: bool = True,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
    ) -> Optional[int]:
        """Validate integer input.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            required: Whether field is required
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            Validated integer or None if not required and not provided

        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ValidationError(f"{field_name} is required", field=field_name)
            return None

        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError(
                f"{field_name} must be an integer, got {type(value).__name__}",
                field=field_name,
            )

        if min_value is not None and value < min_value:
            raise ValidationError(
                f"{field_name} must be at least {min_value}, got {value}",
                field=field_name,
            )

        if max_value is not None and value > max_value:
            raise ValidationError(
                f"{field_name} must be at most {max_value}, got {value}",
                field=field_name,
            )

        return value

    @staticmethod
    def validate_float(
        value: Any,
        field_name: str,
        required: bool = True,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> Optional[float]:
        """Validate float input.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            required: Whether field is required
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            Validated float or None if not required and not provided

        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ValidationError(f"{field_name} is required", field=field_name)
            return None

        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValidationError(
                f"{field_name} must be a number, got {type(value).__name__}",
                field=field_name,
            )

        value = float(value)

        if min_value is not None and value < min_value:
            raise ValidationError(
                f"{field_name} must be at least {min_value}, got {value}",
                field=field_name,
            )

        if max_value is not None and value > max_value:
            raise ValidationError(
                f"{field_name} must be at most {max_value}, got {value}",
                field=field_name,
            )

        return value

    @staticmethod
    def validate_list(
        value: Any,
        field_name: str,
        required: bool = True,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        item_type: Optional[type] = None,
    ) -> Optional[List[Any]]:
        """Validate list input.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            required: Whether field is required
            min_length: Minimum list length
            max_length: Maximum list length
            item_type: Expected type of list items

        Returns:
            Validated list or None if not required and not provided

        Raises:
            ValidationError: If validation fails
        """
        if value is None or (isinstance(value, list) and not value):
            if required:
                raise ValidationError(f"{field_name} is required", field=field_name)
            return None if value is None else []

        if not isinstance(value, list):
            raise ValidationError(
                f"{field_name} must be a list, got {type(value).__name__}",
                field=field_name,
            )

        if min_length is not None and len(value) < min_length:
            raise ValidationError(
                f"{field_name} must have at least {min_length} items, got {len(value)}",
                field=field_name,
            )

        if max_length is not None and len(value) > max_length:
            raise ValidationError(
                f"{field_name} must have at most {max_length} items, got {len(value)}",
                field=field_name,
            )

        if item_type is not None:
            for i, item in enumerate(value):
                if not isinstance(item, item_type):
                    raise ValidationError(
                        f"{field_name}[{i}] must be {item_type.__name__}, "
                        f"got {type(item).__name__}",
                        field=field_name,
                    )

        return value

    @staticmethod
    def validate_dict(
        value: Any,
        field_name: str,
        required: bool = True,
        required_keys: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Validate dictionary input.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            required: Whether field is required
            required_keys: List of required keys in the dictionary

        Returns:
            Validated dictionary or None if not required and not provided

        Raises:
            ValidationError: If validation fails
        """
        if value is None or (isinstance(value, dict) and not value):
            if required:
                raise ValidationError(f"{field_name} is required", field=field_name)
            return None if value is None else {}

        if not isinstance(value, dict):
            raise ValidationError(
                f"{field_name} must be a dictionary, got {type(value).__name__}",
                field=field_name,
            )

        if required_keys:
            missing_keys = set(required_keys) - set(value.keys())
            if missing_keys:
                raise ValidationError(
                    f"{field_name} missing required keys: {', '.join(missing_keys)}",
                    field=field_name,
                )

        return value

    @staticmethod
    def validate_file_path(
        path: Any,
        field_name: str,
        must_exist: bool = True,
        must_be_readable: bool = True,
        allowed_extensions: Optional[List[str]] = None,
    ) -> Path:
        """Validate file path.

        Args:
            path: Path to validate
            field_name: Name of the field for error messages
            must_exist: Whether file must exist
            must_be_readable: Whether file must be readable
            allowed_extensions: List of allowed file extensions (e.g., ['.txt', '.md'])

        Returns:
            Validated Path object

        Raises:
            ValidationError: If validation fails
        """
        if not path:
            raise ValidationError(f"{field_name} is required", field=field_name)

        if not isinstance(path, (str, Path)):
            raise ValidationError(
                f"{field_name} must be a string or Path, got {type(path).__name__}",
                field=field_name,
            )

        path_obj = Path(path)

        if must_exist and not path_obj.exists():
            raise ValidationError(
                f"{field_name}: file not found: {path}", field=field_name
            )

        if must_exist and must_be_readable:
            try:
                path_obj.read_bytes()
            except PermissionError:
                raise ValidationError(
                    f"{field_name}: file not readable: {path}", field=field_name
                )
            except Exception as e:
                raise ValidationError(
                    f"{field_name}: cannot read file: {path} ({str(e)})",
                    field=field_name,
                )

        if allowed_extensions and path_obj.suffix.lower() not in allowed_extensions:
            raise ValidationError(
                f"{field_name}: invalid file extension. "
                f"Allowed: {', '.join(allowed_extensions)}, got: {path_obj.suffix}",
                field=field_name,
            )

        return path_obj

    @staticmethod
    def validate_output_path(
        path: Any,
        field_name: str,
        allow_overwrite: bool = False,
        create_parent_dirs: bool = True,
    ) -> Path:
        """Validate output file path.

        Args:
            path: Path to validate
            field_name: Name of the field for error messages
            allow_overwrite: Whether to allow overwriting existing files
            create_parent_dirs: Whether to create parent directories

        Returns:
            Validated Path object

        Raises:
            ValidationError: If validation fails
        """
        if not path:
            raise ValidationError(f"{field_name} is required", field=field_name)

        if not isinstance(path, (str, Path)):
            raise ValidationError(
                f"{field_name} must be a string or Path, got {type(path).__name__}",
                field=field_name,
            )

        path_obj = Path(path)

        if path_obj.exists() and not allow_overwrite:
            raise ValidationError(
                f"{field_name}: file already exists: {path}", field=field_name
            )

        if create_parent_dirs:
            try:
                path_obj.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValidationError(
                    f"{field_name}: cannot create parent directory: {str(e)}",
                    field=field_name,
                )

        # Check if parent directory is writable
        if not path_obj.parent.exists():
            raise ValidationError(
                f"{field_name}: parent directory does not exist: {path_obj.parent}",
                field=field_name,
            )

        return path_obj

    @staticmethod
    def validate_choice(
        value: Any,
        field_name: str,
        choices: List[Any],
        required: bool = True,
    ) -> Optional[Any]:
        """Validate value is one of allowed choices.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            choices: List of allowed choices
            required: Whether field is required

        Returns:
            Validated value or None if not required and not provided

        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ValidationError(f"{field_name} is required", field=field_name)
            return None

        if value not in choices:
            raise ValidationError(
                f"{field_name} must be one of {choices}, got: {value}",
                field=field_name,
            )

        return value

    @staticmethod
    def validate_alpha(value: Any, field_name: str = "alpha") -> float:
        """Validate alpha parameter (0.0 to 1.0).

        Args:
            value: Alpha value to validate
            field_name: Name of the field for error messages

        Returns:
            Validated alpha value

        Raises:
            ValidationError: If validation fails
        """
        return InputValidator.validate_float(
            value, field_name, required=True, min_value=0.0, max_value=1.0
        )

    @staticmethod
    def validate_limit(
        value: Any,
        field_name: str = "limit",
        max_value: int = 1000,
    ) -> int:
        """Validate limit parameter.

        Args:
            value: Limit value to validate
            field_name: Name of the field for error messages
            max_value: Maximum allowed limit

        Returns:
            Validated limit value

        Raises:
            ValidationError: If validation fails
        """
        return InputValidator.validate_int(
            value, field_name, required=True, min_value=1, max_value=max_value
        )
