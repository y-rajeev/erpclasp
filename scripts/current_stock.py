def get_current_stock():
    data = frappe.db.sql("""
        SELECT
            ROW_NUMBER() OVER (ORDER BY b.warehouse, b.item_code) AS name,
            b.item_code,
            i.item_name AS description,
            i.item_group,
            b.warehouse,
            w.branch,
            w.warehouse_type,
            b.actual_qty
        FROM
            `tabBin` b
        LEFT JOIN `tabWarehouse` w ON b.warehouse = w.name
        LEFT JOIN `tabItem` i ON b.item_code = i.item_code
        WHERE
            b.actual_qty != 0 and
            b.warehouse IN (
                "Finished Goods - Govandi - SLPL",
                "Finished Goods - KAR - SLPL",
                "Finished Goods - MUM - SLPL",
                "LPN Stock - KAR - SLPL",
                "Raw Materials - Govandi - SLPL",
                "Raw Materials - KAR - SLPL",
                "Raw Materials - MUM - SLPL")
        ORDER BY
            b.warehouse, b.item_code;
        """, as_dict=1)
    return data

frappe.response["message"] = get_current_stock()
