from typing import Dict, Any, Optional
from transformers import pipeline


class HuggingLLMLink:
    """A vCon link for analyzing conversations using HuggingFace models."""

    def __init__(self, model_name: str = "facebook/bart-large-mnli", **kwargs):
        """Initialize the HuggingLLM Link.

        Args:
            model_name: The HuggingFace model to use
            **kwargs: Additional arguments passed to the model pipeline
        """
        self.classifier = pipeline(
            "zero-shot-classification", model=model_name, **kwargs
        )

    def process(self, vcon: Dict[str, Any]) -> Dict[str, Any]:
        """Process a vCon document.

        Args:
            vcon: A vCon document

        Returns:
            The processed vCon document with analysis results
        """
        # Extract text from turns
        if "turns" not in vcon:
            return vcon

        for turn in vcon["turns"]:
            if "text" not in turn:
                continue

            # Example analysis: Sentiment classification
            result = self.classifier(
                turn["text"], candidate_labels=["positive", "negative", "neutral"]
            )

            # Add analysis results to the turn
            if "analysis" not in turn:
                turn["analysis"] = {}

            turn["analysis"]["sentiment"] = {
                "scores": dict(zip(result["labels"], result["scores"])),
                "label": result["labels"][0],  # Most likely label
            }

        return vcon

    def batch_process(self, vcons: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """Process multiple vCon documents.

        Args:
            vcons: List of vCon documents

        Returns:
            List of processed vCon documents
        """
        return [self.process(vcon) for vcon in vcons]


# Optional: Add a convenience function for creating the link
def create_link(**kwargs) -> HuggingLLMLink:
    """Create a new HuggingLLM Link instance."""
    return HuggingLLMLink(**kwargs)
