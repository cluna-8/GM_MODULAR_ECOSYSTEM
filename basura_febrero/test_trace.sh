#!/bin/bash

function run_case() {
    name=$1
    message=$2
    session=$3
    context=$4

    echo -e "\n🚀 Running Test Case: $name"
    
    # 1. Send Chat Request
    response=$(curl -s -X POST http://localhost:7005/chat \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"$message\",
            \"session\": \"$session\",
            \"context\": $context
        }")
    
    echo "✅ Chat Response Received."
    
    sleep 1

    # 2. Fetch Audit Trace
    echo -e "\n🔍 AUDIT TRACE FLOW (Session: $session):"
    curl -s http://localhost:7005/audit/trace/$session | jq -r '.trace[] | "--- [STEP: \(.step)] ---\nVerdict/Data: \(.data.verdict // .data.response // "N/A")\n"'
}

# Scenario 1: Septicemia
run_case "Septicemia (79F)" \
    "cual es el tratamiento para la septicemia?" \
    "trace_septicemia" \
    '{"genero": "F", "edad": 79, "diagnostico": "OTROS ESTADOS POSTQUIRURGICOS ESPECIFICADOS"}'

# Scenario 2: Colecistectomía (The Trap)
run_case "Colecistectomía Trap (20F)" \
    "cual es el tratamiento para COLECISTECTOMIA" \
    "trace_colecistectomia" \
    '{"genero": "F", "edad": 20, "diagnostico": "DOLOR LOCALIZADO EN OTRAS PARTES INFERIORES DEL ABDOMEN"}'
