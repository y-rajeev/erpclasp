# ============================================================================
# ERPNext Server Script for Updating Sales Order Item Quantities
# ============================================================================
# 
# This server script allows updating quantities on SUBMITTED Sales Orders
# and optionally inserting brand new Sales Order Item rows by using direct
# database updates to bypass after-submit validation.
# 
# INSTALLATION INSTRUCTIONS:
# 
# 1. Login to ERPNext as Administrator
# 2. Go to: Settings → Automation → Server Script → New
# 3. Set the following:
#    - Name: Update Sales Order Items
#    - Script Type: API
#    - API Method: update_sales_order_items
#    - Allow Guest: [ ] (unchecked)
# 
# 4. Copy the code BELOW THE LINE into the "Script" field
# 5. Click "Save"
# 
# ============================================================================
# 
# COPY FROM HERE (lines below) into ERPNext Server Script editor:
# ----------------------------------------------------------------------------

# type: ignore
# NOTE: 'frappe' is available in ERPNext Server Script runtime, not in local Python

# Get parameters from form_dict
sales_order = frappe.form_dict.get("sales_order")  # noqa: F821
updates = frappe.form_dict.get("updates")  # noqa: F821
new_items = frappe.form_dict.get("new_items")  # noqa: F821
remove_items = frappe.form_dict.get("remove_items")  # noqa: F821

# Parse updates if it's a JSON string
if isinstance(updates, str):
    updates = frappe.parse_json(updates)  # noqa: F821
if isinstance(new_items, str):
    new_items = frappe.parse_json(new_items)  # noqa: F821
if isinstance(remove_items, str):
    remove_items = frappe.parse_json(remove_items)  # noqa: F821

sales_order_doc = None
if sales_order:
    sales_order_doc = frappe.get_doc("Sales Order", sales_order)  # noqa: F821

results = {"success": [], "failed": [], "added": [], "add_failed": [], "removed": [], "remove_failed": []}

for upd in updates or []:
    try:
        item_name = upd.get("item_name")
        new_qty = float(upd.get("qty"))
        
        # Validate delivered_qty
        item = frappe.get_doc("Sales Order Item", item_name)  # noqa: F821
        delivered = item.delivered_qty or 0
        
        if new_qty < delivered:
            results["failed"].append({
                "item_code": upd.get("item_code"),
                "error": "New qty ({0}) < delivered ({1})".format(new_qty, delivered)
            })
            continue
        
        # Direct DB update (bypasses validation)
        frappe.db.set_value("Sales Order Item", item_name, "qty", new_qty)  # noqa: F821
        results["success"].append(upd.get("item_code"))
    except Exception as e:
        results["failed"].append({
            "item_code": upd.get("item_code", "unknown"),
            "error": str(e)
        })

for new_item in (new_items or []):
    try:
        if not sales_order or not sales_order_doc:
            raise Exception("Sales Order not loaded.")

        qty = float(new_item.get("qty") or 0)
        if qty <= 0:
            raise Exception("Qty must be > 0")

        delivery_date = new_item.get("delivery_date") or sales_order_doc.delivery_date
        schedule_date = new_item.get("schedule_date") or delivery_date

        child = frappe.get_doc({  # noqa: F821
            "doctype": "Sales Order Item",
            "parent": sales_order,
            "parenttype": "Sales Order",
            "parentfield": "items",
            "docstatus": sales_order_doc.docstatus,
            "item_code": new_item.get("item_code"),
            "item_name": new_item.get("item_name") or new_item.get("item_code"),
            "description": new_item.get("description") or new_item.get("item_name"),
            "qty": qty,
            "stock_uom": new_item.get("stock_uom"),
            "uom": new_item.get("uom") or new_item.get("stock_uom"),
            "conversion_factor": new_item.get("conversion_factor") or 1,
            "warehouse": new_item.get("warehouse") or sales_order_doc.set_warehouse,
            "delivery_date": delivery_date,
            "schedule_date": schedule_date,
            "rate": float(new_item.get("rate") or 0),
            "price_list_rate": float(new_item.get("price_list_rate") or 0),
        })
        child.flags.ignore_permissions = True
        child.flags.ignore_mandatory = True
        child.insert()
        results["added"].append(new_item.get("item_code"))
    except Exception as e:
        results["add_failed"].append({
            "item_code": new_item.get("item_code", "unknown"),
            "error": str(e)
        })

# Remove items (delete child rows)
for remove_item in (remove_items or []):
    try:
        item_name = remove_item.get("item_name")
        item_code = remove_item.get("item_code")
        
        # Validate delivered_qty before removing
        item = frappe.get_doc("Sales Order Item", item_name)  # noqa: F821
        delivered = item.delivered_qty or 0
        
        if delivered > 0:
            results["remove_failed"].append({
                "item_code": item_code,
                "error": "Cannot remove - already delivered {0} units".format(delivered)
            })
            continue
        
        # Delete the child row
        frappe.delete_doc("Sales Order Item", item_name, ignore_permissions=True)  # noqa: F821
        results["removed"].append(item_code)
    except Exception as e:
        results["remove_failed"].append({
            "item_code": remove_item.get("item_code", "unknown"),
            "error": str(e)
        })

frappe.db.commit()  # noqa: F821

# Invalidate cache so frontend shows updated values
if sales_order:
    try:
        # Try multiple cache clearing methods for compatibility
        frappe.cache().hdel("sales_order", sales_order)  # noqa: F821
        frappe.cache().delete_value(f"sales_order::{sales_order}")  # noqa: F821
    except Exception:
        pass  # Cache clearing is optional, don't fail if it doesn't work

frappe.response["message"] = results  # noqa: F821

