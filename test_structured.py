#!/usr/bin/env python
"""Test structured output with OpenAI."""
import os
import json
from langchain_openai import ChatOpenAI

# Simple schema
schema = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_insights": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["summary"]
}

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
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
