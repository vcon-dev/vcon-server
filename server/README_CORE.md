# vCon Server Core Documentation

## Overview

The vCon Server is a robust processing pipeline designed to handle vCon objects through configurable processing chains. It implements a Redis-based queue system for managing the flow of vCons through various processing stages.

## Core Components

### 1. Main Processing Pipeline (`main.py`)

The main processing pipeline is the heart of the vCon server, responsible for:
- Managing processing chains
- Handling vCon processing through configured links
- Managing storage operations
- Implementing queue-based processing

#### Key Classes and Functions

##### `VconChainRequest`
The primary class for processing individual vCons through a chain:
- Manages the execution of processing links
- Handles storage operations
- Controls egress queue placement
- Tracks processing metrics and timing

Key methods:
- `process()`: Main processing loop for a vCon
- `_process_link()`: Handles individual link processing
- `_process_storage()`: Manages storage backend operations
- `_wrap_up()`: Handles post-processing operations

##### Chain Configuration
The system uses a `ChainConfig` TypedDict to define processing chains with:
- Chain name
- Processing links
- Storage backends
- Ingress/egress queues
- Processing timeout
- Enable/disable status

### 2. Configuration Management (`config.py`)

The configuration system provides:
- YAML-based configuration loading
- Centralized config access
- Storage configuration management
- Follower configuration management
- Import configuration management

### 3. Redis Queue Management (`redis_mgr.py`)

The Redis management system provides:
- Connection pool management
- Synchronous and asynchronous client support
- JSON-based key-value operations
- Pattern-based key searching
- Connection lifecycle management

## Processing Flow

1. **Ingress**
   - vCons enter through configured ingress queues
   - Each ingress queue is mapped to a specific processing chain

2. **Chain Processing**
   - vCons are processed through configured links in sequence
   - Each link can modify the vCon or halt processing
   - Processing metrics and timing are tracked

3. **Storage**
   - Processed vCons are saved to configured storage backends
   - Multiple storage backends can be configured per chain

4. **Egress**
   - Processed vCons are forwarded to configured egress queues
   - Multiple egress queues can be configured per chain

## Error Handling

The system implements comprehensive error handling:
- Link-level error tracking
- Storage operation error handling
- Graceful shutdown support
- Dead Letter Queue (DLQ) for failed processing

## Metrics and Monitoring

The system tracks various metrics:
- vCon processing time
- Link-level processing time
- Processing counts
- Queue lengths
- Error rates

## Configuration

The system is configured through a YAML file that defines:
- Processing chains
- Link configurations
- Storage backends
- Queue mappings
- Processing timeouts

## Dependencies

Core dependencies include:
- Redis for queue management
- PyYAML for configuration
- Custom storage backends
- Processing link modules

## Best Practices

1. **Chain Configuration**
   - Keep chains focused and modular
   - Configure appropriate timeouts
   - Enable/disable chains as needed

2. **Link Development**
   - Implement proper error handling
   - Return appropriate continue/halt signals
   - Log processing details

3. **Storage Configuration**
   - Configure appropriate storage backends
   - Handle storage failures gracefully
   - Monitor storage performance

4. **Queue Management**
   - Monitor queue lengths
   - Configure appropriate DLQs
   - Handle queue processing errors 