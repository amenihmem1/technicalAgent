#!/bin/sh
python -m uvicorn services.interview.main:app --host 0.0.0.0 --port "${PORT:-8000}"
