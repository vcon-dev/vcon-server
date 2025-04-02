import unittest
from unittest.mock import patch, MagicMock
import json
import base64
import tempfile
import os
from server.links.hugging_face_whisper import transcribe_hugging_face_whisper, get_file_content


# Check if the TEST_HF_API_KEY environment variable is defined
SKIP_TESTS = os.environ.get("TEST_HF_API_KEY") is None
SKIP_REASON = "TEST_HF_API_KEY environment variable not defined"


@unittest.skipIf(SKIP_TESTS, SKIP_REASON)
class TestHuggingFaceWhisper(unittest.TestCase):
    def setUp(self):
        # Skip individual tests if the environment variable is not set
        if SKIP_TESTS:
            self.skipTest(SKIP_REASON)
            
        self.test_options = {
            "API_URL": "https://test-api.huggingface.cloud",
            "API_KEY": os.environ.get("TEST_HF_API_KEY", "test_key"),
            "Content-Type": "audio/flac",
        }

        self.test_dialog_inline = {
            "encoding": "base64url",
            "body": base64.urlsafe_b64encode(b"test audio content").decode('utf-8'),
        }

        self.test_dialog_url = {
            "url": "https://test-url.com/audio.flac",
            "alg": "SHA-512",
            "signature": "test_signature",
        }

    @patch('requests.post')
    def test_transcribe_inline_audio(self, mock_post):
        # Mock the API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "This is a test transcription", "confidence": 0.95}
        mock_post.return_value = mock_response

        # Call the function
        result = transcribe_hugging_face_whisper(self.test_dialog_inline, self.test_options)

        # Verify the result
        self.assertEqual(result["text"], "This is a test transcription")
        self.assertEqual(result["confidence"], 0.95)

        # Verify the API was called correctly
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {self.test_options['API_KEY']}")
        self.assertEqual(kwargs["headers"]["Content-Type"], self.test_options["Content-Type"])

    @patch('requests.post')
    @patch('requests.get')
    def test_transcribe_url_audio(self, mock_get, mock_post):
        # Mock the download response
        mock_get_response = MagicMock()
        mock_get_response.content = b"test audio content"
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        # Mock the API response
        mock_post_response = MagicMock()
        mock_post_response.json.return_value = {"text": "This is a test transcription", "confidence": 0.95}
        mock_post.return_value = mock_post_response

        # Call the function
        result = transcribe_hugging_face_whisper(self.test_dialog_url, self.test_options)

        # Verify the result
        self.assertEqual(result["text"], "This is a test transcription")
        self.assertEqual(result["confidence"], 0.95)

        # Verify both API calls were made correctly
        mock_get.assert_called_once_with(self.test_dialog_url["url"], verify=True)
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_retry_on_failure(self, mock_post):
        # Mock a failed response followed by a successful one
        mock_post.side_effect = [
            Exception("API Error"),
            MagicMock(json=lambda: {"text": "Success after retry", "confidence": 0.9}),
        ]

        # Call the function
        result = transcribe_hugging_face_whisper(self.test_dialog_inline, self.test_options)

        # Verify the retry worked
        self.assertEqual(result["text"], "Success after retry")
        self.assertEqual(mock_post.call_count, 2)


if __name__ == '__main__':
    unittest.main()
