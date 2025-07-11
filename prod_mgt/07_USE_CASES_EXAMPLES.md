# Use Cases & Examples

## Industry Use Cases

### 1. Call Center Operations

#### Quality Assurance Pipeline
```yaml
chains:
  qa_chain:
    links:
      - deepgram_link:          # Transcribe calls
          minimum_duration: 60
      - analyze:                # Analyze for quality
          prompt: |
            Evaluate this call for:
            1. Agent professionalism
            2. Issue resolution
            3. Compliance adherence
            Rate each on 1-10 scale
          analysis_type: "qa_score"
      - tag_router:             # Route based on score
          rules:
            - tag: "qa_score:low"
              queue: "qa_review"
            - tag: "qa_score:high"
              queue: "qa_passed"
      - post_analysis_to_slack: # Alert supervisors
          channel: "#qa-alerts"
    storages:
      - postgres               # Store for reporting
```

#### Customer Sentiment Tracking
```yaml
chains:
  sentiment_chain:
    links:
      - deepgram_link
      - analyze:
          prompt: "Analyze customer sentiment and satisfaction"
          analysis_type: "sentiment"
      - webhook:               # Send to CRM
          webhook-urls:
            - "https://crm.company.com/api/sentiment"
```

### 2. Healthcare Communications

#### Telehealth Documentation
```yaml
chains:
  telehealth_chain:
    links:
      - deepgram_link:
          api:
            model: "medical"
            redact: ["pii", "ssn"]
      - analyze:
          prompt: |
            Extract:
            1. Chief complaint
            2. Symptoms discussed
            3. Treatment plan
            4. Follow-up required
          analysis_type: "medical_summary"
      - diet:                  # Remove audio for privacy
          remove_media: true
      - scitt:                # Create audit trail
          service: "healthcare_transparency"
    storages:
      - postgres:             # HIPAA-compliant storage
          encrypted: true
```

#### Patient Engagement Monitoring
```yaml
chains:
  engagement_chain:
    links:
      - detect_engagement:
          metrics:
            - talk_time_ratio
            - question_response_time
            - appointment_scheduling
      - tag:
          tags:
            - "patient_engagement:monitored"
```

### 3. Financial Services

#### Compliance Recording
```yaml
chains:
  compliance_chain:
    links:
      - deepgram_link:
          api:
            diarize: true      # Speaker identification
      - analyze:
          prompt: |
            Check for:
            1. Required disclosures made
            2. Risk warnings given
            3. Customer acknowledgments
          analysis_type: "compliance_check"
      - datatrails:           # Immutable audit trail
          event_type: "financial_communication"
      - expire_vcon:          # 7-year retention
          ttl: 220752000
    storages:
      - s3:                   # Long-term archival
          bucket: "compliance-recordings"
          lifecycle: "7-year-retention"
```

### 4. Sales & Marketing

#### Lead Qualification
```yaml
chains:
  lead_qualification:
    links:
      - deepgram_link
      - analyze:
          prompt: |
            Score this lead on:
            1. Budget mentioned
            2. Authority level
            3. Need urgency
            4. Timeline
            Provide BANT score
          analysis_type: "lead_score"
      - webhook:              # Update CRM
          webhook-urls:
            - "https://salesforce.com/api/leads/update"
```

### 5. Education & Training

#### Training Evaluation
```yaml
chains:
  training_evaluation:
    links:
      - sampler:              # Sample training calls
          rate: 0.2
      - deepgram_link
      - analyze_vcon:         # Analyze entire interaction
          prompt: |
            Evaluate training effectiveness:
            1. Key points covered
            2. Trainee understanding
            3. Areas for improvement
      - post_analysis_to_slack:
          channel: "#training-team"
```

## Technical Implementation Examples

### 1. Multi-Language Support
```yaml
chains:
  multilingual:
    links:
      - deepgram_link:
          api:
            detect_language: true
            languages: ["en", "es", "fr", "de", "ja"]
      - analyze:
          prompt: "Summarize in the original language"
      - tag:
          dynamic: true
          tag_from: "detected_language"
```

### 2. Real-Time Processing
```yaml
chains:
  realtime:
    ingress_lists:
      - "realtime_queue"
    links:
      - deepgram_link:
          streaming: true
      - analyze:
          model: "gpt-3.5-turbo"  # Faster model
          streaming: true
      - webhook:
          immediate: true
    timeout: 30
```

### 3. Batch Processing
```yaml
chains:
  batch_processing:
    links:
      - jq_link:              # Filter for batch
          expression: '.created_at > "2024-01-01"'
      - sampler:
          modulo: 10          # Every 10th vCon
      - analyze:
          batch_size: 50
    schedule: "0 2 * * *"     # Run at 2 AM daily
```

### 4. Privacy-Focused Pipeline
```yaml
chains:
  privacy_pipeline:
    links:
      - diet:
          remove_patterns:
            - ssn: "[0-9]{3}-[0-9]{2}-[0-9]{4}"
            - credit_card: "[0-9]{16}"
          redact_audio: true
      - analyze:
          no_pii: true
      - expire_vcon:
          ttl: 2592000        # 30 days
```

### 5. A/B Testing Configuration
```yaml
chains:
  ab_test:
    links:
      - tag_router:
          rules:
            - modulo: 2
              value: 0
              queue: "variant_a"
            - modulo: 2
              value: 1
              queue: "variant_b"
  
  variant_a:
    links:
      - deepgram_link
      - analyze:
          model: "gpt-3.5-turbo"
  
  variant_b:
    links:
      - groq_whisper
      - analyze:
          model: "gpt-4"
```

## Integration Examples

### 1. CRM Integration
```python
# Custom webhook handler
@app.post("/crm/webhook")
async def handle_vcon(vcon: dict):
    # Extract customer info
    customer_phone = vcon["parties"][0]["tel"]
    
    # Get analysis
    summary = next(
        a["body"] for a in vcon["analysis"] 
        if a["type"] == "summary"
    )
    
    # Update CRM
    crm_client.update_contact(
        phone=customer_phone,
        last_call_summary=summary,
        sentiment=vcon["tags"].get("sentiment")
    )
```

### 2. Analytics Dashboard
```sql
-- PostgreSQL query for dashboard
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_calls,
    AVG(CAST(analysis->>'duration' AS INTEGER)) as avg_duration,
    SUM(CASE WHEN tags @> '["sentiment:positive"]' THEN 1 ELSE 0 END) as positive_calls
FROM vcons
WHERE created_at > CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

### 3. Elasticsearch Aggregation
```json
{
  "aggs": {
    "by_agent": {
      "terms": {
        "field": "parties.name.keyword",
        "size": 10
      },
      "aggs": {
        "avg_sentiment": {
          "avg": {
            "field": "analysis.sentiment_score"
          }
        }
      }
    }
  }
}
```

## Performance Optimization Examples

### 1. High-Volume Configuration
```yaml
# Optimized for 10,000+ calls/day
chains:
  high_volume:
    links:
      - sampler:
          rate: 0.1           # Process 10%
      - deepgram_link:
          batch_size: 100
          workers: 16
      - analyze:
          cache_enabled: true
          ttl: 3600
    workers: 32
    redis:
      pool_size: 100
```

### 2. Low-Latency Configuration
```yaml
# Optimized for <5 second processing
chains:
  low_latency:
    links:
      - deepgram_link:
          priority: "high"
          timeout: 3
      - analyze:
          model: "gpt-3.5-turbo"
          max_tokens: 150
    redis:
      local_cache: true
    workers: 8
```