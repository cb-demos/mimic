"""Tests for input helper functions."""

from mimic.input_helpers import format_field_name


class TestFieldNameFormatting:
    """Tests for format_field_name function."""

    def test_format_single_word(self):
        """Test formatting single word field names."""
        assert format_field_name("project") == "Project"
        assert format_field_name("name") == "Name"

    def test_format_snake_case(self):
        """Test formatting snake_case field names."""
        assert format_field_name("project_name") == "Project name"
        assert format_field_name("target_org") == "Target org"
        assert format_field_name("custom_environment") == "Custom environment"

    def test_format_multiple_underscores(self):
        """Test formatting field names with multiple underscores."""
        assert format_field_name("auto_setup_workflow") == "Auto setup workflow"
        assert format_field_name("create_fm_token_var") == "Create fm token var"

    def test_format_all_lowercase(self):
        """Test that only first word is capitalized."""
        result = format_field_name("project_name_template")
        assert result == "Project name template"
        assert result != "Project Name Template"  # Not title case

    def test_format_empty_string(self):
        """Test formatting empty string."""
        assert format_field_name("") == ""

    def test_format_single_underscore(self):
        """Test field name that starts with underscore."""
        assert format_field_name("_internal") == " internal"

    def test_format_preserves_later_words_case(self):
        """Test that later words remain lowercase."""
        assert format_field_name("github_org") == "Github org"
        assert format_field_name("api_key") == "Api key"
