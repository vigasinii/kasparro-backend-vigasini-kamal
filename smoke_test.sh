#!/bin/bash

# Kasparro ETL System - Smoke Test
# This script performs end-to-end verification of the system

set -e

echo "=================================="
echo "Kasparro ETL System - Smoke Test"
echo "=================================="
echo ""

API_URL="http://localhost:8000"
SLEEP_TIME=5

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to test endpoint
test_endpoint() {
    local endpoint=$1
    local expected_status=$2
    local test_name=$3
    
    echo -n "Testing ${test_name}... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}${endpoint}")
    
    if [ "$response" -eq "$expected_status" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (HTTP $response)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC} (Expected HTTP $expected_status, got HTTP $response)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Helper function to check JSON response
test_json_field() {
    local endpoint=$1
    local field=$2
    local test_name=$3
    
    echo -n "Testing ${test_name}... "
    
    response=$(curl -s "${API_URL}${endpoint}")
    value=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('$field', 'NOT_FOUND'))")
    
    if [ "$value" != "NOT_FOUND" ] && [ "$value" != "null" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (Found field: $field)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC} (Field not found: $field)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo "Step 1: Checking if system is running..."
echo "========================================="

# Test root endpoint
test_endpoint "/" 200 "Root endpoint"

# Test health endpoint
test_endpoint "/health" 200 "Health check endpoint"

# Check database connectivity
echo -n "Checking database connectivity... "
health_response=$(curl -s "${API_URL}/health")
db_status=$(echo "$health_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('database', 'unknown'))")

if [ "$db_status" = "connected" ]; then
    echo -e "${GREEN}✓ PASSED${NC} (Database: $db_status)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ FAILED${NC} (Database: $db_status)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "Step 2: Testing API endpoints..."
echo "================================="

# Test data endpoint
test_endpoint "/data" 200 "Data endpoint"

# Test pagination
test_endpoint "/data?page=1&page_size=10" 200 "Data pagination"

# Test filtering
test_endpoint "/data?source=coinpaprika" 200 "Data filtering by source"
test_endpoint "/data?symbol=BTC" 200 "Data filtering by symbol"

# Test stats endpoint
test_endpoint "/stats" 200 "Stats endpoint"

# Test runs endpoint
test_endpoint "/runs" 200 "Runs endpoint"

# Test metrics endpoint
test_endpoint "/metrics" 200 "Metrics endpoint"

# Test API docs
test_endpoint "/docs" 200 "API documentation"

echo ""
echo "Step 3: Verifying data ingestion..."
echo "===================================="

# Wait for ETL to run
echo "Waiting ${SLEEP_TIME}s for ETL to complete initial run..."
sleep $SLEEP_TIME

# Check if data was ingested
echo -n "Checking data ingestion... "
data_response=$(curl -s "${API_URL}/data")
total_records=$(echo "$data_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total', 0))")

if [ "$total_records" -gt 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (Found $total_records records)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠ WARNING${NC} (No records found yet - ETL may still be running)"
fi

# Check ETL status
echo -n "Checking ETL status... "
stats_response=$(curl -s "${API_URL}/stats")
sources_count=$(echo "$stats_response" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")

if [ "$sources_count" -eq 3 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (All 3 sources reporting)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ FAILED${NC} (Expected 3 sources, found $sources_count)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "Step 4: Testing data quality..."
echo "==============================="

# Test data response structure
test_json_field "/data" "data" "Data array present"
test_json_field "/data" "total" "Total count present"
test_json_field "/data" "request_id" "Request ID present"
test_json_field "/data" "api_latency_ms" "API latency present"

# Test individual record structure
echo -n "Checking record structure... "
first_record=$(curl -s "${API_URL}/data?page=1&page_size=1")
has_coin_id=$(echo "$first_record" | python3 -c "import sys, json; data = json.load(sys.stdin); print('coin_id' in data.get('data', [{}])[0] if data.get('data') else False)")

if [ "$has_coin_id" = "True" ]; then
    echo -e "${GREEN}✓ PASSED${NC} (Records have proper structure)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ FAILED${NC} (Records missing expected fields)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "Step 5: Testing error handling..."
echo "=================================="

# Test invalid pagination
test_endpoint "/data?page=0" 422 "Invalid pagination handling"

# Test invalid page size
test_endpoint "/data?page_size=1000" 422 "Invalid page size handling"

echo ""
echo "Step 6: Performance checks..."
echo "============================="

# Test API latency
echo -n "Checking API latency... "
start_time=$(date +%s%N)
curl -s "${API_URL}/data" > /dev/null
end_time=$(date +%s%N)
latency=$(( (end_time - start_time) / 1000000 ))

if [ "$latency" -lt 500 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (Latency: ${latency}ms)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠ WARNING${NC} (Latency: ${latency}ms - exceeds 500ms)"
fi

echo ""
echo "=========================================="
echo "Smoke Test Results"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "System is ready for use!"
    echo "API Documentation: ${API_URL}/docs"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Please check the logs for more details:"
    echo "  docker-compose logs api"
    exit 1
fi
