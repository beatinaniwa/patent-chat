"""Tests for patent specification version display and finalization logic."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm import check_spec_completeness, next_questions
from app.state import Idea


class TestVersionDisplay(unittest.TestCase):
    """Test cases for version display logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.idea = Idea(
            id="test-id",
            title="Test Patent",
            category="防災",
            description="Test description",
            draft_spec_markdown="# Test Draft",
            draft_version=1,
            is_final=False,
        )

    def test_initial_version_is_not_final(self):
        """Test that version 1 is not marked as final."""
        self.assertEqual(self.idea.draft_version, 1)
        self.assertFalse(self.idea.is_final)

    def test_version_increments(self):
        """Test that version counter increments correctly."""
        initial_version = self.idea.draft_version
        self.idea.draft_version += 1
        self.assertEqual(self.idea.draft_version, initial_version + 1)

    def test_is_final_flag_persists(self):
        """Test that is_final flag persists when set."""
        self.idea.is_final = True
        self.assertTrue(self.idea.is_final)

        # Should remain final even if version changes
        self.idea.draft_version = 3
        self.assertTrue(self.idea.is_final)


class TestQuestionGeneration(unittest.TestCase):
    """Test cases for question generation with version control."""

    @patch('app.llm._get_client')
    def test_no_questions_when_final(self, mock_client):
        """Test that no questions are generated when specification is final."""
        mock_client.return_value = MagicMock()

        # Test with is_final=True
        questions, error = next_questions(
            instruction_md="test",
            transcript=[],
            current_spec_md="test draft",
            num_questions=5,
            version=3,
            is_final=True,
        )
        self.assertEqual(questions, [])
        self.assertIsNone(error)

    @patch('app.llm._get_client')
    def test_no_questions_at_version_5(self, mock_client):
        """Test that no questions are generated at version 5."""
        mock_client.return_value = MagicMock()

        # Test with version=5
        questions, error = next_questions(
            instruction_md="test",
            transcript=[],
            current_spec_md="test draft",
            num_questions=5,
            version=5,
            is_final=False,
        )
        self.assertEqual(questions, [])
        self.assertIsNone(error)

    @patch('app.llm._get_client')
    def test_questions_generated_before_final(self, mock_client):
        """Test that questions are generated for non-final versions < 5."""
        mock_client.return_value = None  # Use fallback questions

        # Test with version=2, is_final=False
        questions, error = next_questions(
            instruction_md="test",
            transcript=[],
            current_spec_md="test draft",
            num_questions=3,
            version=2,
            is_final=False,
        )
        self.assertIsNotNone(error)  # Has error because mock_client is None
        self.assertGreater(len(questions), 0)
        self.assertLessEqual(len(questions), 3)


class TestSpecCompleteness(unittest.TestCase):
    """Test cases for specification completeness checking."""

    @patch('app.llm._get_client')
    def test_version_5_always_complete(self, mock_client):
        """Test that version 5 is always considered complete."""
        mock_client.return_value = MagicMock()

        is_complete, score = check_spec_completeness(
            instruction_md="test", current_spec_md="short draft", version=5
        )
        self.assertTrue(is_complete)
        self.assertEqual(score, 100.0)

        # Should not call the client for version 5
        mock_client.assert_not_called()

    @patch('app.llm._get_client')
    def test_completeness_with_placeholders(self, mock_client):
        """Test completeness check with placeholder text."""
        mock_client.return_value = None  # Use heuristic fallback

        # Draft with placeholder
        draft_with_placeholder = "# Patent\n## Section\n未記載"
        is_complete, score = check_spec_completeness(
            instruction_md="test", current_spec_md=draft_with_placeholder, version=2
        )
        self.assertFalse(is_complete)
        self.assertLess(score, 85)

    @patch('app.llm._get_client')
    def test_completeness_without_placeholders(self, mock_client):
        """Test completeness check without placeholder text."""
        mock_client.return_value = None  # Use heuristic fallback

        # Long draft without placeholders
        draft_complete = "# Patent Specification\n" + "Content " * 500
        self.assertGreater(len(draft_complete), 3000)

        is_complete, score = check_spec_completeness(
            instruction_md="test", current_spec_md=draft_complete, version=3
        )
        # May or may not be complete based on length
        self.assertIsInstance(is_complete, bool)
        self.assertGreaterEqual(score, 60)
        self.assertLessEqual(score, 100)

    @patch('app.llm._get_client')
    def test_completeness_api_response(self, mock_client):
        """Test completeness check with API response."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.text = "90"
        mock_client.return_value.models.generate_content.return_value = mock_response

        is_complete, score = check_spec_completeness(
            instruction_md="test", current_spec_md="test draft", version=3
        )
        self.assertTrue(is_complete)  # 90 >= 85
        self.assertEqual(score, 90.0)

    @patch('app.llm._get_client')
    def test_completeness_low_score(self, mock_client):
        """Test completeness check with low score."""
        # Mock API response with low score
        mock_response = MagicMock()
        mock_response.text = "70"
        mock_client.return_value.models.generate_content.return_value = mock_response

        is_complete, score = check_spec_completeness(
            instruction_md="test", current_spec_md="test draft", version=2
        )
        self.assertFalse(is_complete)  # 70 < 85
        self.assertEqual(score, 70.0)


class TestVersionLimits(unittest.TestCase):
    """Test cases for version limits and boundaries."""

    def test_version_progression(self):
        """Test the progression from version 1 to 5."""
        idea = Idea(
            id="test",
            title="Test",
            category="test",
            description="test",
            draft_version=1,
            is_final=False,
        )

        # Version 1-4 should not be automatically final
        for version in range(1, 5):
            idea.draft_version = version
            self.assertFalse(idea.is_final)

        # Simulate reaching version 5
        idea.draft_version = 5
        # In real code, this would be set by the logic
        # Here we test that version 5 can be marked as final
        idea.is_final = True
        self.assertTrue(idea.is_final)

    @patch('app.llm._get_client')
    def test_no_questions_beyond_version_5(self, mock_client):
        """Test that no questions are generated for versions > 5."""
        mock_client.return_value = MagicMock()

        for version in [5, 6, 10]:
            questions, error = next_questions(
                instruction_md="test",
                transcript=[],
                current_spec_md="test",
                version=version,
                is_final=False,
            )
            self.assertEqual(questions, [], f"Version {version} should generate no questions")
            self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
