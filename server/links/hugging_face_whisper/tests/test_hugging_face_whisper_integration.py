import unittest
import os
import base64
from pathlib import Path
from server.links.hugging_face_whisper import transcribe_hugging_face_whisper
from server.config import Configuration


# Check if the TEST_HF_API_KEY environment variable is defined
SKIP_TESTS = os.environ.get("TEST_HF_API_KEY") is None
SKIP_REASON = "TEST_HF_API_KEY environment variable not defined"


@unittest.skipIf(SKIP_TESTS, SKIP_REASON)
class TestHuggingFaceWhisperIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Skip class setup if the environment variable is not set
        if SKIP_TESTS:
            raise unittest.SkipTest(SKIP_REASON)
            
        # Load config and API credentials
        config = Configuration.get_config()
        cls.api_options = {
            "API_URL": config.get("links.hugging_face_whisper.API_URL"),
            # Use the environment variable as priority, fallback to config
            "API_KEY": os.environ.get("TEST_HF_API_KEY") or config.get("links.hugging_face_whisper.API_KEY"),
            "Content-Type": "audio/flac",
        }

        # Create test audio file path
        cls.test_audio_path = Path(__file__).parent / "test_audio.flac"

        if not cls.test_audio_path.exists():
            raise unittest.SkipTest("Test audio file not found. Please add test_audio.flac to run integration tests.")

    def test_transcribe_inline_audio(self):
        """Test transcription with real API call using inline audio."""
        # Read test audio file
        with open(self.test_audio_path, 'rb') as f:
            audio_content = f.read()

        # Create test dialog with inline audio
        test_dialog = {"encoding": "base64url", "body": base64.urlsafe_b64encode(audio_content).decode('utf-8')}

        # Make actual API call
        result = transcribe_hugging_face_whisper(test_dialog, self.api_options)

        # Verify response structure
        self.assertIn("text", result)
        self.assertIn("confidence", result)
        self.assertIsInstance(result["text"], str)
        self.assertIsInstance(result["confidence"], float)
        self.assertTrue(0 <= result["confidence"] <= 1)

        # Log the actual transcription for manual verification
        print(f"\nTranscription result: {result['text']}")
        print(f"Confidence: {result['confidence']}")

    def test_transcribe_url_audio(self):
        """Test transcription with real API call using URL audio."""
        # For this test, we'll use a publicly accessible audio URL
        test_dialog = {
            "url": "https://github.com/openai/whisper/raw/main/tests/jfk.flac",
            "alg": "SHA-512",
            # Note: In a real scenario, you should verify the file integrity
            "signature": "dummy_signature",
        }

        # Make actual API call
        result = transcribe_hugging_face_whisper(test_dialog, self.api_options)

        # Verify response structure
        self.assertIn("text", result)
        self.assertIn("confidence", result)
        self.assertIsInstance(result["text"], str)
        self.assertIsInstance(result["confidence"], float)
        self.assertTrue(0 <= result["confidence"] <= 1)

        # Log the actual transcription for manual verification
        print(f"\nTranscription result: {result['text']}")
        print(f"Confidence: {result['confidence']}")


if __name__ == '__main__':
    unittest.main()
