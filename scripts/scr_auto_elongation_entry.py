# ===============================
# ELONGATION (GAIN)
# ===============================

# Prevent duplicate
exists = frappe.db.exists("Stock Entry", {
    "remarks": ["like", f"%Elongation from {doc.name}%"]
})

if not exists:

    gain_items = []

    for row in doc.items:
        input_qty = row.custom_input_qty or 0
        output_qty = row.qty or 0

        # Gain condition
        if output_qty > input_qty:
            gain_qty = output_qty - input_qty

            if gain_qty > 0:
                gain_items.append({
                    "item_code": row.item_code,
                    "qty": gain_qty,
                    "uom": row.uom,
                    "stock_uom": row.stock_uom,
                    # FG goes to target warehouse
                    "t_warehouse": doc.set_warehouse or row.warehouse
                })

    if gain_items:
        try:
            se = frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Elongation",
                "purpose": "Material Receipt",
                "company": doc.company,
                "items": gain_items,
                "custom_subcontracting_receipt": doc.name,
                "remarks": f"Elongation from {doc.name}"
            })

            se.insert(ignore_permissions=True)
            se.submit()

        except Exception:
            frappe.log_error(frappe.get_traceback(), "Elongation Entry Failed")