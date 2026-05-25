#!/bin/bash
cd "$(dirname "$0")"

case "${1:-cli}" in
    ui|web|streamlit)
        echo "Starting SQL Copilot UI..."
        exec streamlit run ui.py --server.headless true
        ;;
    cli|*)
        exec python3 main.py
        ;;
esac
