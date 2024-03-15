# vcon-server

## Installation Steps

### Requirements
- If docker is not installed, install it first on your system. Please refer to the installation instructions for your system.


### Install

- git clone https://github.com/vcon-dev/vcon-server.git
- cd vcon-server/
- cp .env.example .env
- cp example_config.yml config.yml
- docker compose up

## Configuration

###  .env file
Here is an example .env file:

    AWS_BUCKET=[YOUR TOKEN GOES HERE]
    AWS_KEY_ID=[YOUR TOKEN GOES HERE]
    AWS_SECRET_KEY=[YOUR TOKEN GOES HERE]
    DEEPGRAM_KEY=[YOUR TOKEN GOES HERE]
    ENV=dev

    # CORE DEPENDENCIES
    ENV=dev
    HOSTNAME=http://0.0.0.0:8000
    HOST=0.0.0.0
    PORT=8000
    REDIS_URL=redis://redis

    # Overriding these on pairing so they don't conflict with django port etc
    REDIS_EXTERNAL_PORT=8001
    CONSERVER_EXTERNAL_PORT=8000

    CONSERVER_API_TOKEN=[YOUR TOKEN GOES HERE]
    CONSERVER_CONFIG_FILE=./config.yml

### config.yml

This is a

      links:
      webhook_store_call_log:
         module: links.webhook
         options:
            webhook-urls:
            - https://example.com/conserver
      expire_vcon_1_day_later:
         module: links.expire_vcon
         options:
            seconds: 604800
      deepgram:
         module: links.deepgram
         options:
            DEEPGRAM_KEY: xxxxxxxxxxxxxxxxx
            minimum_duration: 30
            api:
            model: "nova-2"
            smart_format: true  
            detect_language: true
      summarize:
         module: links.analyze
         options:
            OPENAI_API_KEY: xxxxxxxxxxxxxxxx
            prompt: "Summarize this transcript in a few sentences, identify the purpose of the call and then indicate if there is a clear frustration expressed by the customer and if this was a conversation between two people or if someone left a message, and if agent was helpful?"
            analysis_type: summary
            model: 'gpt-3.5-turbo-16k'
      sentiment:
         module: links.analyze
         options:
            OPENAI_API_KEY: xxxxxxxxxxx
            prompt: "Based on the transcript - if there were any clear frustration expressed by the customer, respond with only the words 'NEEDS REVIEW', otherwise respond 'NO REVIEW NEEDED'."
            analysis_type: customer_frustration
            model: 'gpt-3.5-turbo-16k'
      storages:
         postgres:
            module: storage.postgres
            options:
               user: xxxxxxx
               password: xxxxxxxxx
               host: xxxxxxxxx.us-east-1.rds.amazonaws.com
               port: "5432"
               database: postgres
         s3:
            module: storage.s3
            options:
               aws_access_key_id: xxxxxxxx
               aws_secret_access_key: xxxxxxx
               aws_bucket: vcons
      chains:
         bria_chain:
            links:
               - deepgram
               - summarize
               - sentiment
               - diarize
               - agent_note
               - webhook_store_call_log
               - send_frustration_for_review
               - expire_vcon_1_day_later
            ingress_lists:
               - default_ingress
            storages:
               - postgres
               - s3
            egress_lists:
               - default_egress
            enabled: 1
