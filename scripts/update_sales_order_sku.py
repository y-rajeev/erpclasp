sku_mappings = [{
  "po_no": "EH1259-US",
  "old_sku": "IBM-60108-S",
  "new_sku": "IBM-60108-S-D"
}, {
  "po_no": "EH1255-IN",
  "old_sku": "TC-00804-142x142",
  "new_sku": "TC-00804-142x142-New"
}, {
  "po_no": "EH1255-IN",
  "old_sku": "TC-00803-142x180",
  "new_sku": "TC-00803-142x180-New"
}, {
  "po_no": "EH1255-IN",
  "old_sku": "TC-00803-145-Round",
  "new_sku": "TC-00803-145-Round-New"
}, {
  "po_no": "EH1255-IN",
  "old_sku": "TC-00801-142x142",
  "new_sku": "TC-00801-142x142-New"
}, {
  "po_no": "EH1255-IN",
  "old_sku": "TC-00802-142x180",
  "new_sku": "TC-00802-142x180-New"
}, {
  "po_no": "EH1255-IN",
  "old_sku": "TC-00805-145-Round",
  "new_sku": "TC-00805-145-Round-New"
}, {
  "po_no": "EH2253-IN",
  "old_sku": "FA-90202",
  "new_sku": "FA-90202-New"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "TC-00803-145-Round",
  "new_sku": "TC-00803-145-Round-New"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "CN-00417-140x213-2",
  "new_sku": "CN-00417-140x213-2-New"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "TC-00801-142x180",
  "new_sku": "TC-00801-142x180-New"
}, {
  "po_no": "EH2255-IN",
  "old_sku": "FA-90210",
  "new_sku": "FA-90210-New"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "TC-00803-142x180",
  "new_sku": "TC-00803-142x180-New"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "CN-68324-142x213",
  "new_sku": "CN-68324-142x213-New"
}, {
  "po_no": "EH2253-IN",
  "old_sku": "FA-90221",
  "new_sku": "FA-90221-New"
}, {
  "po_no": "EH2255-IN",
  "old_sku": "FA-90215",
  "new_sku": "FA-90215-New"
}, {
  "po_no": "EH1257-IN",
  "old_sku": "TC-00803-145-Round",
  "new_sku": "TC-00803-145-Round-New"
}, {
  "po_no": "EH1257-IN",
  "old_sku": "TC-00803-142x180",
  "new_sku": "TC-00803-142x180-New"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "CN-68311-112x150",
  "new_sku": "CN-68311-112x150-New"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "TC-00802-142x180",
  "new_sku": "TC-00802-142x180-New"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "PMCR-04801-4",
  "new_sku": "PMCR-04801-4-New"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "TC-00803-142x142",
  "new_sku": "TC-00803-142x142-New"
}, {
  "po_no": "EH2253-IN",
  "old_sku": "FA-90203",
  "new_sku": "FA-90203-New"
}, {
  "po_no": "EH1257-IN",
  "old_sku": "TC-00802-142x180",
  "new_sku": "TC-00802-142x180-New"
}, {
  "po_no": "EH1256-EU",
  "old_sku": "IB-60169-M",
  "new_sku": "IB-60169-M-New"
}, {
  "po_no": "EH2255-IN",
  "old_sku": "FA-90202",
  "new_sku": "FA-90202-New"
}, {
  "po_no": "EH1259-US",
  "old_sku": "IB-60169-W",
  "new_sku": "IB-60169-W-New"
}, {
  "po_no": "EH2257-IN",
  "old_sku": "FA-90221",
  "new_sku": "FA-90221-New"
}, {
  "po_no": "EH2253-IN",
  "old_sku": "FA-90209",
  "new_sku": "FA-90209-New"
}, {
  "po_no": "EH2254-EU",
  "old_sku": "PM-00109-48x33-6",
  "new_sku": "PM-00109-48x33-6-New"
}, {
  "po_no": "EH1259-US",
  "old_sku": "IB-60169-M",
  "new_sku": "IB-60169-M-New"
}, {
  "po_no": "EH2256-US",
  "old_sku": "CC-10773-40x40-2",
  "new_sku": "CC-10773-40x40-2-New"
}, {
  "po_no": "EH1259-US",
  "old_sku": "IM-69016",
  "new_sku": "IM-69016-D"
}, {
  "po_no": "EH1258-IN",
  "old_sku": "IM-69016",
  "new_sku": "IM-69016-D"
}]

updated_count = 0
merged_count = 0
deleted_count = 0
logs = []

for mapping in sku_mappings:
    # ✅ support both keys
    po_no = mapping.get("po_no") or mapping.get("shipment_id")
    old_sku = mapping.get("old_sku")
    new_sku = mapping.get("new_sku")

    # ✅ validation
    if not po_no or not old_sku or not new_sku:
        logs.append({
            "type": "error",
            "message": "Invalid mapping",
            "data": mapping
        })
        continue

    # Get Sales Orders
    sales_orders = frappe.db.sql("""
        SELECT name
        FROM `tabSales Order`
        WHERE po_no = %s
          AND docstatus != 2
    """, (po_no,), as_dict=True)

    for so in sales_orders:
        so_name = so.get("name")

        # Fetch old SKU rows
        old_rows = frappe.db.sql("""
            SELECT name, qty
            FROM `tabSales Order Item`
            WHERE parent = %s
              AND item_code = %s
        """, (so_name, old_sku), as_dict=True)

        if not old_rows:
            continue

        # Fetch new SKU row (if exists)
        new_row = frappe.db.sql("""
            SELECT name, qty
            FROM `tabSales Order Item`
            WHERE parent = %s
              AND item_code = %s
            LIMIT 1
        """, (so_name, new_sku), as_dict=True)

        for old in old_rows:
            old_name = old.get("name")
            old_qty = old.get("qty") or 0

            if new_row:
                # ✅ Merge case
                new_name = new_row[0].get("name")
                new_qty = new_row[0].get("qty") or 0

                updated_qty = new_qty + old_qty

                # Update new SKU qty
                frappe.db.set_value(
                    "Sales Order Item",
                    new_name,
                    "qty",
                    updated_qty,
                    update_modified=False
                )

                # ❌ delete not allowed → ✅ soft delete
                frappe.db.set_value(
                    "Sales Order Item",
                    old_name,
                    "qty",
                    0,
                    update_modified=False
                )

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
                # ✅ Replace case
                frappe.db.set_value(
                    "Sales Order Item",
                    old_name,
                    "item_code",
                    new_sku,
                    update_modified=False
                )

                updated_count += 1

                logs.append({
                    "type": "replace",
                    "so": so_name,
                    "row": old_name,
                    "old_sku": old_sku,
                    "new_sku": new_sku
                })

# Commit once
frappe.db.commit()

frappe.response["message"] = {
    "updated": updated_count,
    "merged": merged_count,
    "soft_deleted": deleted_count,
    "changes": logs
}