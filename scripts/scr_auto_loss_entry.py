# ===============================
# PROCESS LOSS (ROW LEVEL FIX)
# ===============================

exists = frappe.db.exists("Stock Entry", {
    "remarks": ["like", f"%Process Loss from {doc.name}%"]
})

if not exists:

    if not doc.supplier_warehouse:
        frappe.throw("Supplier Warehouse is required")

    loss_items = []

    # -------------------------------
    # LOOP FG ITEMS
    # -------------------------------
    for fg in doc.items:

        input_qty = fg.custom_input_qty or 0
        output_qty = fg.qty or 0

        # Only process rows with loss
        if input_qty > output_qty:

            fg_loss = input_qty - output_qty

            # -------------------------------
            # FIND MATCHING RM ROWS (INSIDE LOOP)
            # -------------------------------
            matching_rm = []

            for rm in doc.supplied_items:
                if rm.main_item_code == fg.item_code:
                    matching_rm.append(rm)

            # Total RM qty for THIS FG
            total_rm_qty = 0
            for rm in matching_rm:
                total_rm_qty += (rm.consumed_qty or 0)

            if total_rm_qty <= 0:
                continue

            # -------------------------------
            # DISTRIBUTE LOSS
            # -------------------------------
            for rm in matching_rm:

                rm_qty = rm.consumed_qty or 0

                if rm_qty <= 0:
                    continue

                loss_qty = round((rm_qty / total_rm_qty) * fg_loss, 6)

                if loss_qty > 0.0001:
                    loss_items.append({
                        "item_code": rm.rm_item_code,
                        "qty": loss_qty,
                        "uom": rm.stock_uom,
                        "stock_uom": rm.stock_uom,
                        "s_warehouse": doc.supplier_warehouse
                    })

    # -------------------------------
    # CREATE STOCK ENTRY
    # -------------------------------
    if loss_items:
        try:
            se = frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Process Loss",
                "purpose": "Material Issue",
                "company": doc.company,
                "items": loss_items,
                "custom_subcontracting_receipt": doc.name,
                "remarks": f"Auto Process Loss from {doc.name}"
            })

            se.insert(ignore_permissions=True)
            se.submit()

        except Exception:
            frappe.log_error(frappe.get_traceback(), "Process Loss Failed")