"""Terminal receipt report mirrored by system_console/receipts_report.sql."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from erpclasp.config import load_app_config

DEFAULT_FIELDS = [
    "receipt_type",
    "name",
    "supplier_name",
    "supplier_delivery_note",
    "custom_lot_no",
    "posting_date",
    "item_code",
    "received_qty",
    "accepted_qty",
    "rejected_qty",
    "warehouse",
    "qty_after_transaction",
]
DEFAULT_LIMIT = 20
DEFAULT_TIMEOUT = (10, 60)
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBMITTED_FILTER = ["docstatus", "=", 1]
RECEIPT_DOCTYPES = ("Purchase Receipt", "Subcontracting Receipt")
RECEIPT_TYPE_LABELS = {
    "Purchase Receipt": "Purchase",
    "Subcontracting Receipt": "Subcontracting",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Purchase Receipt rows from ERPNext and print them in the terminal.",
    )
    parser.add_argument(
        "--project-root",
        default=str(DEFAULT_PROJECT_ROOT),
        help="Path that contains the project's .env file. Defaults to the repo root.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of rows to fetch (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        default=DEFAULT_FIELDS,
        help="Space-separated field names to fetch.",
    )
    parser.add_argument(
        "--filters",
        default="[]",
        help=(
            "JSON array of ERPNext filters, for example "
            "'[[\"status\", \"=\", \"Completed\"]]'"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON instead of a text table.",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="Write the result rows to a CSV file.",
    )
    return parser


def parse_filters(raw_filters: str) -> list[Any]:
    try:
        parsed = json.loads(raw_filters)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid --filters JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise SystemExit("--filters must decode to a JSON array.")
    return ensure_submitted_filter(parsed)


def ensure_submitted_filter(filters: list[Any]) -> list[Any]:
    for entry in filters:
        if (
            isinstance(entry, list)
            and len(entry) >= 3
            and str(entry[0]) == "docstatus"
        ):
            return filters
    return [SUBMITTED_FILTER, *filters]


def build_session(base_url: str, api_key: str, api_secret: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"token {api_key}:{api_secret}",
            "Accept": "application/json",
        }
    )
    return session


def fetch_purchase_receipts(
    session: requests.Session,
    base_url: str,
    filters: list[Any],
    limit: int,
) -> list[dict[str, Any]]:
    detailed_rows: list[dict[str, Any]] = []
    purchase_order_flags: dict[str, bool] = {}
    for doctype in RECEIPT_DOCTYPES:
        detailed_rows.extend(
            fetch_receipt_rows_for_doctype(
                session,
                base_url,
                doctype,
                filters,
                limit,
                purchase_order_flags,
            )
        )
    detailed_rows.sort(
        key=lambda row: (
            str(row.get("posting_date", "")),
            str(row.get("name", "")),
            str(row.get("item_code", "")),
        ),
        reverse=True,
    )
    return detailed_rows


def fetch_receipt_rows_for_doctype(
    session: requests.Session,
    base_url: str,
    doctype_name: str,
    filters: list[Any],
    limit: int,
    purchase_order_flags: dict[str, bool],
) -> list[dict[str, Any]]:
    doctype = quote(doctype_name, safe="")
    url = f"{base_url}/api/resource/{doctype}"
    parent_fields = [
        "name",
        "supplier_name",
        "supplier_delivery_note",
        "custom_lot_no",
        "posting_date",
        "status",
    ]
    params = {
        "fields": json.dumps(parent_fields),
        "filters": json.dumps(filters),
        "limit_page_length": limit,
        "order_by": "modified desc",
    }
    response = session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list):
        raise SystemExit("Unexpected ERPNext response: missing data array.")

    detailed_rows: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        receipt_name = row.get("name")
        if not receipt_name:
            continue
        detail = fetch_receipt_detail(session, base_url, doctype_name, str(receipt_name))
        if should_skip_receipt(detail, doctype_name, session, base_url, purchase_order_flags):
            continue
        normalized_row = normalize_parent_row(row, detail, doctype_name)
        stock_balances = fetch_stock_balances_for_receipt(
            session,
            base_url,
            doctype_name,
            str(receipt_name),
        )
        items = detail.get("items")
        if not isinstance(items, list) or not items:
            detailed_rows.append(normalized_row)
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            received_qty = item.get("received_qty", "")
            rejected_qty = item.get("rejected_qty", "")
            detailed_rows.append(
                {
                    **normalized_row,
                    "item_code": item.get("item_code", ""),
                    "warehouse": item.get("warehouse", ""),
                    "qty_after_transaction": resolve_qty_after_transaction(item, stock_balances),
                    "received_qty": received_qty,
                    "accepted_qty": resolve_accepted_qty(item, received_qty, rejected_qty),
                    "rejected_qty": rejected_qty,
                }
            )
    return detailed_rows


def should_skip_receipt(
    detail: dict[str, Any],
    doctype_name: str,
    session: requests.Session,
    base_url: str,
    purchase_order_flags: dict[str, bool],
) -> bool:
    if doctype_name != "Purchase Receipt":
        return False

    items = detail.get("items")
    if not isinstance(items, list):
        return False

    for item in items:
        if not isinstance(item, dict):
            continue
        purchase_order = item.get("purchase_order")
        if not purchase_order:
            continue
        if is_subcontracted_purchase_order(
            session,
            base_url,
            str(purchase_order),
            purchase_order_flags,
        ):
            return True
    return False


def is_subcontracted_purchase_order(
    session: requests.Session,
    base_url: str,
    purchase_order_name: str,
    purchase_order_flags: dict[str, bool],
) -> bool:
    if purchase_order_name in purchase_order_flags:
        return purchase_order_flags[purchase_order_name]

    doctype = quote("Purchase Order", safe="")
    docname = quote(purchase_order_name, safe="")
    url = f"{base_url}/api/resource/{doctype}/{docname}"
    response = session.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SystemExit("Unexpected ERPNext response: missing purchase order data.")

    result = bool(data.get("is_subcontracted"))
    purchase_order_flags[purchase_order_name] = result
    return result


def normalize_parent_row(
    row: dict[str, Any],
    detail: dict[str, Any],
    doctype_name: str,
) -> dict[str, Any]:
    grand_total = row.get("grand_total")
    if grand_total in (None, ""):
        grand_total = detail.get("grand_total", detail.get("total", ""))

    rounded_total = row.get("rounded_total")
    if rounded_total in (None, ""):
        rounded_total = detail.get("rounded_total", grand_total)

    return {
        "receipt_type": RECEIPT_TYPE_LABELS.get(doctype_name, doctype_name),
        **row,
        "grand_total": grand_total,
        "rounded_total": rounded_total,
    }


def resolve_accepted_qty(
    item: dict[str, Any],
    received_qty: Any,
    rejected_qty: Any,
) -> Any:
    accepted_qty = item.get("accepted_qty")
    if accepted_qty not in (None, ""):
        return accepted_qty

    try:
        received_value = float(received_qty or 0)
        rejected_value = float(rejected_qty or 0)
    except (TypeError, ValueError):
        return accepted_qty if accepted_qty is not None else ""
    return received_value - rejected_value


def fetch_receipt_detail(
    session: requests.Session,
    base_url: str,
    doctype_name: str,
    receipt_name: str,
) -> dict[str, Any]:
    doctype = quote(doctype_name, safe="")
    docname = quote(receipt_name, safe="")
    url = f"{base_url}/api/resource/{doctype}/{docname}"
    response = session.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SystemExit("Unexpected ERPNext response: missing document data.")
    return data


def fetch_stock_balances_for_receipt(
    session: requests.Session,
    base_url: str,
    doctype_name: str,
    receipt_name: str,
) -> dict[str, Any]:
    doctype = quote("Stock Ledger Entry", safe="")
    url = f"{base_url}/api/resource/{doctype}"
    params = {
        "fields": json.dumps(
            [
                "voucher_detail_no",
                "item_code",
                "warehouse",
                "qty_after_transaction",
                "posting_date",
                "posting_time",
                "creation",
            ]
        ),
        "filters": json.dumps(
            [
                ["voucher_type", "=", doctype_name],
                ["voucher_no", "=", receipt_name],
                ["is_cancelled", "=", 0],
            ]
        ),
        "limit_page_length": 1000,
        "order_by": "posting_date desc, posting_time desc, creation desc",
    }
    response = session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list):
        raise SystemExit("Unexpected ERPNext response: missing stock ledger data.")

    balances: dict[str, Any] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        voucher_detail_no = row.get("voucher_detail_no")
        if voucher_detail_no and voucher_detail_no not in balances:
            balances[str(voucher_detail_no)] = row.get("qty_after_transaction", "")
    return balances


def resolve_qty_after_transaction(
    item: dict[str, Any],
    stock_balances: dict[str, Any],
) -> Any:
    item_name = item.get("name")
    if item_name in stock_balances:
        return stock_balances[item_name]
    return ""


def print_table(rows: list[dict[str, Any]], fields: list[str]) -> None:
    if not rows:
        print("No Purchase Receipt rows matched the query.")
        return

    widths: dict[str, int] = {field: len(field) for field in fields}
    for row in rows:
        for field in fields:
            widths[field] = max(widths[field], len(str(row.get(field, ""))))

    header = " | ".join(field.ljust(widths[field]) for field in fields)
    divider = "-+-".join("-" * widths[field] for field in fields)
    print(header)
    print(divider)
    for row in rows:
        print(" | ".join(str(row.get(field, "")).ljust(widths[field]) for field in fields))


def write_csv(rows: list[dict[str, Any]], fields: list[str], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.limit <= 0:
        raise SystemExit("--limit must be greater than 0.")

    project_root = Path(args.project_root).resolve()
    config = load_app_config(project_root)
    session = build_session(config.base_url, config.api_key, config.api_secret)
    filters = parse_filters(args.filters)
    rows = fetch_purchase_receipts(session, config.base_url, filters, args.limit)
    if args.csv_path:
        write_csv(rows, args.fields, Path(args.csv_path).resolve())

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print_table(rows, args.fields)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        response = exc.response
        body = ""
        if response is not None:
            body = response.text.strip()
            message = f"ERPNext request failed with HTTP {response.status_code}"
            if body:
                message = f"{message}: {body[:500]}"
        else:
            message = f"ERPNext request failed: {exc}"
        print(message, file=sys.stderr)
        raise SystemExit(1) from exc
    except requests.RequestException as exc:
        print(f"ERPNext request failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
