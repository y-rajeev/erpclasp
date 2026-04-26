"""
Server Script (readability export): SO Item Tracking (Qty + Added Date)
script_type: DocType Event

Source of truth for backup/import is the sibling .json next to this folder.
"""
# Run only on update (not first insert)
if not doc.is_new():

    old_doc = frappe.get_doc("Sales Order", doc.name)

    # Existing item row IDs
    old_item_map = {d.name: d for d in old_doc.items}

    for item in doc.items:

        # -----------------------------
        # 1. Detect NEW ITEM ADDED
        # -----------------------------
        if item.name not in old_item_map:
            item.custom_added_on = frappe.utils.now()

        else:
            old_item = old_item_map[item.name]

            # -----------------------------
            # 2. Detect QTY CHANGE
            # -----------------------------
            if float(old_item.qty) != float(item.qty):

                log = frappe.new_doc("Sales Order Item Change Log")
                log.sales_order = doc.name
                log.item_code = item.item_code
                log.old_qty = old_item.qty
                log.new_qty = item.qty
                log.changed_by = frappe.session.user
                log.changed_on = frappe.utils.now()

                log.insert(ignore_permissions=True)

    # -----------------------------
    # 3. Detect REMOVED ITEM ROWS (deleted from SO)
    # -----------------------------
    current_row_names = {row.name for row in doc.items}
    for old_row in old_doc.items:
        if old_row.name not in current_row_names:
            log = frappe.new_doc("Sales Order Item Change Log")
            log.sales_order = doc.name
            log.item_code = old_row.item_code
            log.old_qty = old_row.qty
            log.new_qty = 0
            log.changed_by = frappe.session.user
            log.changed_on = frappe.utils.now()

            log.insert(ignore_permissions=True)
