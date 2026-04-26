doc = frappe.get_doc("SKU Replacement", frappe.form_dict["docname"])

data = frappe.form_dict["data"] if "data" in frappe.form_dict else ""

updated_count = 0
merged_count = 0
deleted_count = 0
logs = []

try:
    lines = (data or "").strip().split("\n")

    for idx, line in enumerate(lines):

        if not line.strip():
            continue

        # Skip header automatically
        if idx == 0 and "po_no" in line.lower():
            continue

        # Detect separator
        if "\t" in line:
            parts = [x.strip() for x in line.split("\t")]
        elif "|" in line:
            parts = [x.strip() for x in line.split("|")]
        else:
            logs.append({
                "type": "error",
                "message": "Unknown separator",
                "line": line
            })
            continue

        if len(parts) != 3:
            logs.append({
                "type": "error",
                "message": "Invalid format",
                "line": line
            })
            continue

        po_no = parts[0]
        old_sku = parts[1]
        new_sku = parts[2]

        # Optional: skip same SKU
        if old_sku == new_sku:
            logs.append({
                "type": "skip",
                "reason": "Same SKU",
                "po_no": po_no,
                "sku": old_sku
            })
            continue

        sales_orders = frappe.db.sql("""
            SELECT name
            FROM `tabSales Order`
            WHERE po_no = %s AND docstatus != 2
        """, (po_no,), as_dict=True)

        for so in sales_orders:
            so_name = so.get("name")

            old_rows = frappe.db.sql("""
                SELECT name, qty
                FROM `tabSales Order Item`
                WHERE parent = %s AND item_code = %s
            """, (so_name, old_sku), as_dict=True)

            if not old_rows:
                continue

            new_row = frappe.db.sql("""
                SELECT name, qty
                FROM `tabSales Order Item`
                WHERE parent = %s AND item_code = %s
                LIMIT 1
            """, (so_name, new_sku), as_dict=True)

            new_name = new_row[0].get("name") if new_row else None
            running_new_qty = (new_row[0].get("qty") or 0) if new_row else 0

            for old in old_rows:
                old_name = old.get("name")
                old_qty = old.get("qty") or 0

                if new_row:
                    # Merge
                    updated_qty = running_new_qty + old_qty

                    frappe.db.set_value("Sales Order Item", new_name, "qty", updated_qty, update_modified=False)
                    frappe.delete_doc("Sales Order Item", old_name, force=True, ignore_permissions=True)
                    running_new_qty = updated_qty

                    merged_count += 1
                    deleted_count += 1

                    logs.append({
                        "type": "merge",
                        "so": so_name,
                        "old_row": old_name,
                        "new_row": new_name,
                        "added_qty": old_qty,
                        "final_qty": updated_qty
                    })

                else:
                    # Replace
                    frappe.db.set_value("Sales Order Item", old_name, "item_code", new_sku, update_modified=False)

                    updated_count += 1

                    logs.append({
                        "type": "replace",
                        "so": so_name,
                        "row": old_name,
                        "old_sku": old_sku,
                        "new_sku": new_sku
                    })

    frappe.db.commit()

    result = {
        "updated": updated_count,
        "merged": merged_count,
        "deleted": deleted_count,
        "logs": logs
    }

    frappe.db.set_value("SKU Replacement", doc.name, {
        "status": "Completed",
        "result_log": str(result)
    })

    frappe.response["message"] = result

except Exception as e:
    frappe.db.set_value("SKU Replacement", doc.name, {
        "status": "Error",
        "result_log": str(e)
    })

    frappe.response["message"] = {"error": str(e)}
