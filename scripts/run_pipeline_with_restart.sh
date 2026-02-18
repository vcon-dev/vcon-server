#!/bin/bash
# Auto-restart pipeline when vfun crashes

DATE="${1:-2026-01-19}"
WORKERS="${2:-64}"
BATCH_SIZE="${3:-5000}"

echo "=== Pipeline with Auto-Restart ==="
echo "Date: $DATE"
echo "Workers: $WORKERS"
echo "Batch size: $BATCH_SIZE"
echo ""

restart_vfun() {
    echo "$(date +%H:%M:%S) Restarting vfun..."
    pkill -9 -f "vfun --port 4380" 2>/dev/null
    sleep 2
    cd ~/strolid/vfun && ./vfun --port 4380 > /tmp/vfun_4380.log 2>&1 &
    sleep 18
    if curl -s http://localhost:4380/ready > /dev/null; then
        echo "$(date +%H:%M:%S) vfun ready"
        return 0
    else
        echo "$(date +%H:%M:%S) vfun failed to start"
        return 1
    fi
}

# Initial start
restart_vfun || exit 1

TOTAL_PROCESSED=0
TOTAL_VCCONS=0
BATCH=1

while true; do
    echo ""
    echo "=== Batch $BATCH (limit $BATCH_SIZE) ==="

    # Run pipeline
    OUTPUT=$(python3 scripts/nas_transcription_pipeline.py \
        --date "$DATE" \
        --server 1 \
        --workers "$WORKERS" \
        --limit "$BATCH_SIZE" \
        --store-vcons 2>&1)

    # Extract stats
    PROCESSED=$(echo "$OUTPUT" | grep "Processed:" | grep -oE '[0-9,]+' | head -1 | tr -d ',')
    VCCONS=$(echo "$OUTPUT" | grep "vCons stored:" | grep -oE '[0-9,]+' | tr -d ',')
    FAILED=$(echo "$OUTPUT" | grep "Failed:" | grep -oE '[0-9,]+' | tr -d ',')

    if [ -n "$PROCESSED" ]; then
        TOTAL_PROCESSED=$((TOTAL_PROCESSED + PROCESSED))
        TOTAL_VCCONS=$((TOTAL_VCCONS + VCCONS))
        echo "Batch $BATCH: $PROCESSED files, $VCCONS vCons, $FAILED failed"
        echo "Total so far: $TOTAL_PROCESSED files, $TOTAL_VCCONS vCons"
    fi

    # Check if vfun crashed
    if ! curl -s http://localhost:4380/ready > /dev/null; then
        echo "$(date +%H:%M:%S) vfun crashed, restarting..."
        restart_vfun || exit 1
    fi

    # Check if we got fewer files than batch size (done)
    if [ -n "$PROCESSED" ] && [ "$PROCESSED" -lt "$BATCH_SIZE" ]; then
        echo ""
        echo "=== COMPLETE ==="
        echo "Total processed: $TOTAL_PROCESSED"
        echo "Total vCons: $TOTAL_VCCONS"
        break
    fi

    BATCH=$((BATCH + 1))

    # Safety limit
    if [ $BATCH -gt 100 ]; then
        echo "Safety limit reached"
        break
    fi
done
