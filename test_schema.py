#!/usr/bin/env python
"""Test the actual schema."""
import os
import json
from langchain_openai import ChatOpenAI
from pathlib import Path

# Load the actual schema
schema_path = Path("src/lantern_cli/template/bottom_up/schema.json")
with open(schema_path) as f:
    schema = json.load(f)

print(f"Schema keys: {schema.keys()}")
print(f"Schema: {json.dumps(schema, indent=2)}")

# Get API key
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("No OPENAI_API_KEY found")
    exit(1)

# Create LLM
llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0)
print("LLM created successfully")

# Try structured output
try:
    structured_llm = llm.with_structured_output(schema)
    print("Structured LLM created successfully")

    # Try to invoke
    result = structured_llm.invoke("Analyze this code: def add(a, b): return a + b")
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
