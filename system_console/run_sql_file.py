from __future__ import annotations

import os
import sys
import json
import csv
from pathlib import Path
from typing import Any, List, Dict

import requests
from dotenv import load_dotenv


# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
ENV_PATH = Path(__file__).resolve().parent / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


# --------------------------------------------------
# Read SQL file
# --------------------------------------------------
def read_sql_file(path: str) -> str:
    file_path = Path(path).expanduser().resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"SQL file not found: {file_path}")

    query = file_path.read_text(encoding="utf-8").strip()

    if not query:
        raise ValueError("SQL file is empty")

    return query


# --------------------------------------------------
# Call ERPNext API
# --------------------------------------------------
def call_api(query: str) -> List[Dict[str, Any]]:
    base_url = os.getenv("BASE_URL")
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")

    if not all([base_url, api_key, api_secret]):
        raise ValueError("Missing BASE_URL / API_KEY / API_SECRET")

    url = f"{base_url.rstrip('/')}/api/method/execute_sql"

    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"query": query},
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc

    if response.status_code != 200:
        raise RuntimeError(f"API Error {response.status_code}: {response.text}")

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("Invalid JSON response from API")

    if "message" not in data:
        raise RuntimeError(f"Unexpected API response: {data}")

    return data["message"] or []


# --------------------------------------------------
# Print Table
# --------------------------------------------------
def print_table(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        print("No data returned")
        return

    headers = list(rows[0].keys())

    widths = {h: len(h) for h in headers}

    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row.get(h, ""))))

    print("\n" + " | ".join(h.ljust(widths[h]) for h in headers))
    print("-+-".join("-" * widths[h] for h in headers))

    for row in rows:
        print(" | ".join(str(row.get(h, "")).ljust(widths[h]) for h in headers))


# --------------------------------------------------
# Export CSV
# --------------------------------------------------
def export_csv(rows: List[Dict[str, Any]], file_path: str) -> None:
    if not rows:
        print("No data to export")
        return

    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = list(rows[0].keys())

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCSV exported to: {path}")


# --------------------------------------------------
# Export JSON
# --------------------------------------------------
def export_json(rows: List[Dict[str, Any]], file_path: str) -> None:
    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)

    print(f"\nJSON exported to: {path}")


# --------------------------------------------------
# Main
# --------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "python run_sql_file.py <sql_file> [--csv output.csv] [--json output.json]"
        )
        sys.exit(1)

    sql_file = sys.argv[1]

    csv_path = None
    json_path = None

    # Simple CLI parsing
    if "--csv" in sys.argv:
        idx = sys.argv.index("--csv")
        if idx + 1 < len(sys.argv):
            csv_path = sys.argv[idx + 1]

    if "--json" in sys.argv:
        idx = sys.argv.index("--json")
        if idx + 1 < len(sys.argv):
            json_path = sys.argv[idx + 1]

    try:
        query = read_sql_file(sql_file)
        rows = call_api(query)

        # Print table always
        print_table(rows)
        print(f"\nRows returned: {len(rows)}")

        # Export options
        if csv_path:
            export_csv(rows, csv_path)

        if json_path:
            export_json(rows, json_path)

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


# --------------------------------------------------
# Run
# --------------------------------------------------
if __name__ == "__main__":
    main()