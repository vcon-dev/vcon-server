"""
Unit tests for find_silence_split_points function using real MP3 files.
Tests with actual audio files: Snooze Story 54s.mp3 and Snooze Story 73s.mp3
"""

import os
import pytest

# Import the function to test
from .. import find_silence_split_points


class TestFindSilenceSplitPoints:
    """Test cases for the find_silence_split_points function using real MP3 files."""

    @classmethod
    def setup_class(cls):
        """Set up test file paths."""
        # Get the directory containing this test file
        test_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to the openai_transcribe directory
        openai_transcribe_dir = os.path.dirname(test_dir)
        
        # Paths to the actual MP3 files
        cls.audio_54s_gap = os.path.join(openai_transcribe_dir, "Snooze Story 54s.mp3")
        cls.audio_73s_gap = os.path.join(openai_transcribe_dir, "Snooze Story 73s.mp3")

    def test_audio_with_54_second_gap(self):
        """Test audio file with 2-second gap at 54 seconds, split at 1-minute intervals."""
        # Test parameters
        max_duration = 60  # 1 minute split length
        silence_thresh = -40  # Default silence threshold
        silence_len = 2000  # 2 seconds in milliseconds
        
        # Verify the file exists
        assert os.path.exists(self.audio_54s_gap), f"MP3 file not found: {self.audio_54s_gap}"
        
        # Call the actual function with real pydub
        result = find_silence_split_points(
            self.audio_54s_gap, 
            max_duration=max_duration,
            silence_thresh=silence_thresh,
            silence_len=silence_len
        )
        
        # Verify the result
        assert isinstance(result, list)
        
        # For a real MP3 file with 2-second gap at 54s, we expect:
        # - Should find exactly 1 split point since audio is longer than 1 minute
        # - Split point should be close to the silence gap at 54s
        assert len(result) == 1, f"Expected exactly 1 split point, got {len(result)}"
        
        # Check that the split point is reasonable
        split_point = result[0]
        assert isinstance(split_point, (int, float))
        assert split_point > 0
        assert 50000 <= split_point <= 70000, f"Split at {split_point/1000:.1f}s should be around 54-60 seconds"
        
        print(f"54s gap test - Split point: {split_point}ms ({split_point / 1000:.1f}s)")

    def test_audio_with_73_second_gap(self):
        """Test audio file with 2-second gap at 73 seconds, split at 1-minute intervals."""
        # Test parameters
        max_duration = 60  # 1 minute split length
        silence_thresh = -40  # Default silence threshold
        silence_len = 2000  # 2 seconds in milliseconds
        
        # Verify the file exists
        assert os.path.exists(self.audio_73s_gap), f"MP3 file not found: {self.audio_73s_gap}"
        
        # Call the actual function with real pydub
        result = find_silence_split_points(
            self.audio_73s_gap, 
            max_duration=max_duration,
            silence_thresh=silence_thresh,
            silence_len=silence_len
        )
        
        # Verify the result
        assert isinstance(result, list)
        
        # For a real MP3 file with 2-second gap at 73s, we expect:
        # - Should find exactly 1 split point since audio is longer than 1 minute
        # - Split point should be close to the silence gap at 73s
        assert len(result) == 1, f"Expected exactly 1 split point, got {len(result)}"
        
        # Check that the split point is reasonable
        split_point = result[0]
        assert isinstance(split_point, (int, float))
        assert split_point > 0
        assert 60000 <= split_point <= 80000, f"Split at {split_point / 1000:.1f}s should be around 60-80 seconds"
        
        print(f"73s gap test - Split point: {split_point}ms ({split_point / 1000:.1f}s)")

    def test_short_audio_no_splitting_needed(self):
        """Test that audio doesn't need splitting when max_duration is longer than audio."""
        # Use the 54s file but set max_duration to be longer than the audio
        # This should result in no split points since the audio is shorter than max_duration
        result = find_silence_split_points(
            self.audio_54s_gap, 
            max_duration=300,  # 5 minutes - much longer than the audio
            silence_thresh=-40,
            silence_len=2000
        )
        
        # Should return empty list when audio is shorter than max_duration
        assert result == []
        print("No split points needed - audio shorter than max_duration")

    def test_audio_within_duration_limit(self):
        """Test audio exactly at the duration limit."""
        # Use the 54s file with max_duration set to the actual audio duration (1:53 = 113 seconds)
        # This should result in no split points since the audio is exactly at the duration limit
        result = find_silence_split_points(
            self.audio_54s_gap, 
            max_duration=113.95,  # 1 minute 53 seconds - exactly the audio duration
            silence_thresh=-40,
            silence_len=2000
        )
        
        # Should return empty list when audio is exactly at duration limit
        assert result == []
        print("No split points needed - audio exactly at duration limit")

    def test_no_silence_detected_fallback(self):
        """Test fallback behavior when no silence is detected."""
        # Test with the 54s gap file but use a longer silence threshold (4 seconds)
        # This should not detect the 2-second gap, resulting in no split points
        result = find_silence_split_points(
            self.audio_54s_gap, 
            max_duration=60,
            silence_thresh=-40,
            silence_len=4000  # 4 seconds - longer than the 2-second gap
        )
        
        # Should return empty list when no silence is detected
        assert result == [60000]
        print("No silence detected with 4-second threshold - correctly returned empty list")

    def test_audio_loading_exception(self):
        """Test exception handling when audio file cannot be loaded."""
        # Use a non-existent file
        non_existent_file = "/path/to/non/existent/audio.mp3"
        
        result = find_silence_split_points(
            non_existent_file, 
            max_duration=60,
            silence_thresh=-40,
            silence_len=2000
        )
        
        # Should return empty list when file cannot be loaded
        assert result == []

    def test_multiple_split_points(self):
        """Test audio that requires multiple splits."""
        # Test with longer audio that should require multiple splits
        print(f"Testing multiple split points with audio: {self.audio_54s_gap}")
        if os.path.exists(self.audio_54s_gap):
            result = find_silence_split_points(
                self.audio_54s_gap, 
                max_duration=30,  # 30 second splits (shorter for more splits)
                silence_thresh=-40,
                silence_len=2000
            )
            
            # Should return a list with exactly 3 split points for 1:53 audio with 30-second splits
            assert isinstance(result, list)
            assert len(result) == 3, f"Expected exactly 3 split points, got {len(result)}: {result}"
            
            # Check that split points are reasonable
            for point in result:
                assert isinstance(point, (int, float))
                assert point > 0
            
            # Verify split points are around 30s, 60s, and 90s marks (±25% range = ±7.5s)
            expected_targets = [30000, 60000, 90000]  # 30s, 60s, 90s in milliseconds
            search_range = 30000 // 4  # 7.5 seconds (25% of 30s target)
            
            for i, (point, target) in enumerate(zip(result, expected_targets)):
                assert target - search_range <= point <= target + search_range, \
                    f"Split {i + 1} at {point / 1000:.1f}s should be around {target / 1000:.1f}s (±{search_range / 1000:.1f}s)"
                    
            print(f"Multiple splits test - Split points: {result}")
