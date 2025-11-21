#!/bin/bash
cd /home/kavia/workspace/code-generation/study-notes-quiz-generator-209833-209842/quiz_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

