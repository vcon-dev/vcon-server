# vCon Server Links

This directory contains various link implementations for the vCon server. Each link provides specific functionality for processing and analyzing vCon data.

## Available Links

### analyze
A powerful OpenAI-based analysis link that performs AI-powered analysis on vCon transcripts. Supports customizable analysis types, prompts, and models with configurable sampling and retry mechanisms.

### analyze_vcon
A specialized link that performs AI-powered analysis on entire vCon objects, returning structured JSON output. Unlike the standard analyze link, it processes the complete vCon structure rather than individual dialogs, with support for system prompts and JSON response validation.

### datatrails
A specialized link that integrates vCon data with the DataTrails platform, creating verifiable audit trails for vCon operations. Supports both asset-based and asset-free events, with automatic token management and structured event attributes mapping to SCITT envelopes.

### deepgram
A specialized link that performs speech-to-text transcription on audio recordings in vCon dialogs using the Deepgram API. Supports automatic language detection, confidence scoring, and minimum duration filtering for transcription quality.

### diet
A specialized link that helps reduce the size and content of vCon objects by selectively removing or modifying specific elements. Useful for data minimization, privacy protection, and optimizing storage with options for media redirection and system prompt removal.

### expire_vcon
A simple but effective link that sets an expiration time for vCon objects in Redis, enabling automatic cleanup after a specified period. Useful for data retention policy enforcement and storage optimization.

### @groq_whisper
A specialized link that performs speech-to-text transcription on audio recordings in vCon dialogs using Groq's implementation of the Whisper ASR service, with support for various audio formats and robust error handling.

### @hugging_face_whisper
A specialized link that performs speech-to-text transcription on audio recordings in vCon dialogs using Hugging Face's implementation of the Whisper ASR service, with support for various audio formats and robust error handling.

### @hugging_llm_link
A specialized link that performs AI-powered analysis on vCon transcripts using Hugging Face's language models, supporting both API-based and local model inference with configurable parameters and robust error handling.

### @jq_link
A specialized link that filters vCon objects using jq expressions, allowing for complex content-based filtering with configurable forwarding rules for matching or non-matching vCons.

### @post_analysis_to_slack
A specialized link that posts vCon analysis results to Slack channels, with support for team-specific notifications, conditional posting based on analysis content, and rich message formatting.

### @sampler
A specialized link that selectively processes vCons based on various sampling methods, including percentage, rate, modulo, and time-based sampling, enabling efficient resource utilization and focused analysis.

### @scitt
A specialized link that provides integrity and inclusion protection for vCon objects by creating and registering signed statements on a SCITT Transparency Service, ensuring vCons can be verified as authentic and complete.

### @tag
A simple link that adds configurable tags to vCon objects, enabling better organization and filtering of conversations.

### @tag_router
A specialized link that routes vCon objects to different Redis lists based on their tags, enabling flexible distribution of conversations to different processing queues or storage locations.

### @webhook
A specialized link that sends vCon objects to configured webhook URLs, enabling integration with external systems and event-driven workflows. 