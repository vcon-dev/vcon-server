"""Keyword Tagger Link

This link searches vCon transcriptions for specific keywords and phrases,
then adds corresponding tags based on matches.

Categories:
- Compliance & Regulatory (do_not_call, take_me_off, stop_calling, fcc, etc.)
- Voicemail Service Detection (youmail variants)
- Recording/Transcription mentions
- Greeting Patterns
- Legal/Professional
- Other Content

Configuration options:
    categories: List of category names to enable (default: all)
    custom_keywords: Dict of additional tag -> keywords mappings
    case_sensitive: Whether to match case-sensitively (default: false)
"""

import re
from typing import Any, Dict, List, Optional, Set

from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger

logger = init_logger(__name__)

# Keyword definitions organized by category
# Format: tag_name -> list of keywords/phrases to search for
KEYWORD_RULES = {
    # Compliance & Regulatory
    "compliance": {
        "do_not_call": ["do not call", "don't call", "dont call", "do-not-call"],
        "take_me_off": ["take me off", "take us off", "remove me", "remove us"],
        "stop_calling": ["stop calling", "quit calling", "stop call"],
        "mentions_fcc": ["fcc", "federal communications"],
        "mentions_report": ["report you", "report this", "reporting", "file a complaint"],
        "mentions_enforcement": ["enforc", "attorney general", "lawsuit", "sue you", "legal action"],
        "mentions_scam": ["scam", "scammer", "scamming", "fraudulent", "fraud"],
        "mentions_spam": ["spam", "spammer", "spamming", "junk call"],
        "mentions_robocall": ["robo", "robocall", "auto-dial", "autodial", "autodialer"],
        "mentions_protection": ["protect", "protection", "tcpa", "consumer protection"],
    },

    # Voicemail Service Detection (YouMail variants)
    "voicemail_service": {
        "youmail_detected": [
            "youmail", "youmale", "you mail", "you male",
            "umale", "umail", "u mail", "u-mail",
        ],
    },

    # Recording/Transcription mentions
    "recording": {
        "mentions_transcribe": ["transcribe", "transcription", "transcribing"],
        "mentions_recording": ["being recorded", "this call is recorded", "call is being recorded",
                               "may be recorded", "will be recorded", "recording this call"],
        "mentions_email": ["email", "e-mail"],  # Note: may want to exclude "voicemail"
    },

    # Greeting Patterns
    "greetings": {
        "greeting_yea_hello": ["yea hello", "yeah hello", "ya hello"],
        "greeting_hi_informal": ["hi j", "hi g", "hey j", "hey g"],
    },

    # Legal/Professional
    "legal": {
        "mentions_law": ["law office", "lawoffice", "law firm", "lawfirm",
                         "attorney", "lawyer", "legal department"],
    },

    # Other Content
    "other": {
        "profanity": ["fuck", "shit", "damn", "ass"],
        "mentions_torn": ["torn"],
        "mentions_push": ["push"],
        "mentions_pitch": ["pitch", "sales pitch"],
        "mentions_bank": ["bank", "banking", "banker"],
        "mentions_county": ["county"],
        "mentions_general": ["general"],
        "mentions_subscribe": ["subscribe", "subscription"],
        "why_calling": ["why are you calling", "why you calling", "why do you keep calling"],
    },
}

default_options = {
    "categories": None,  # None means all categories
    "custom_keywords": {},  # Additional tag -> keywords mappings
    "case_sensitive": False,
    "min_confidence": 0.0,  # Minimum transcription confidence to process
}


def get_transcription_text(vcon: Any) -> Optional[str]:
    """Extract transcription text from vCon analysis entries."""
    texts = []

    for analysis in vcon.analysis:
        analysis_type = analysis.get("type", "")

        # Handle WTF transcription format
        if analysis_type == "wtf_transcription":
            body = analysis.get("body", {})
            if isinstance(body, dict):
                transcript = body.get("transcript", {})
                if isinstance(transcript, dict):
                    text = transcript.get("text", "")
                    if text:
                        texts.append(text)
                # Also check segments for text
                segments = body.get("segments", [])
                for seg in segments:
                    seg_text = seg.get("text", "")
                    if seg_text:
                        texts.append(seg_text)

        # Handle standard transcription format
        elif analysis_type == "transcription":
            body = analysis.get("body", "")
            if isinstance(body, str):
                texts.append(body)
            elif isinstance(body, dict):
                text = body.get("text", body.get("transcript", ""))
                if text:
                    texts.append(text)

    if texts:
        return " ".join(texts)
    return None


def find_keywords(text: str, keywords: List[str], case_sensitive: bool = False) -> Set[str]:
    """Find which keywords are present in the text."""
    if not case_sensitive:
        text = text.lower()

    found = set()
    for keyword in keywords:
        search_keyword = keyword if case_sensitive else keyword.lower()
        if search_keyword in text:
            found.add(keyword)

    return found


def run(
    vcon_uuid: str,
    link_name: str,
    opts: Dict[str, Any] = None,
) -> Optional[str]:
    """Process a vCon and add keyword-based tags."""
    merged_opts = default_options.copy()
    if opts:
        merged_opts.update(opts)
    opts = merged_opts

    logger.info(f"Starting keyword_tagger for vCon: {vcon_uuid}")

    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)

    if not vcon:
        logger.error(f"keyword_tagger: vCon {vcon_uuid} not found")
        return vcon_uuid

    # Get transcription text
    text = get_transcription_text(vcon)

    if not text:
        logger.debug(f"No transcription found for vCon {vcon_uuid}")
        return vcon_uuid

    logger.debug(f"Analyzing transcription ({len(text)} chars) for vCon {vcon_uuid}")

    case_sensitive = opts.get("case_sensitive", False)
    enabled_categories = opts.get("categories")  # None = all
    custom_keywords = opts.get("custom_keywords", {})

    tags_added = []

    # Process built-in keyword rules
    for category, rules in KEYWORD_RULES.items():
        # Skip if category filtering is enabled and this category is not in the list
        if enabled_categories is not None and category not in enabled_categories:
            continue

        for tag_name, keywords in rules.items():
            found = find_keywords(text, keywords, case_sensitive)
            if found:
                vcon.add_tag(tag_name=tag_name, tag_value=",".join(sorted(found)))
                tags_added.append(tag_name)
                logger.debug(f"Added tag '{tag_name}' (matched: {found})")

    # Process custom keywords
    for tag_name, keywords in custom_keywords.items():
        if isinstance(keywords, str):
            keywords = [keywords]
        found = find_keywords(text, keywords, case_sensitive)
        if found:
            vcon.add_tag(tag_name=tag_name, tag_value=",".join(sorted(found)))
            tags_added.append(tag_name)
            logger.debug(f"Added custom tag '{tag_name}' (matched: {found})")

    if tags_added:
        vcon_redis.store_vcon(vcon)
        logger.info(f"Added {len(tags_added)} tags to vCon {vcon_uuid}: {tags_added}")
    else:
        logger.debug(f"No keyword matches for vCon {vcon_uuid}")

    return vcon_uuid
