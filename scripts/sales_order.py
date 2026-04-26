def get_sales_order():
    data = frappe.db.sql("""
        SELECT
            soi.name as "key",
            so.name AS "so_id",
            so.transaction_date AS "date",
            date(coalesce(soi.custom_added_on, so.transaction_date)) AS "item_added_on",
            so.po_no AS "shipment_id",
            so.branch AS "production",
            so.custom_destination AS "channel_abb",
            so.custom_shipment_mode AS "mode",
            soi.item_code AS "sku",
            soi.qty AS "po_qty",
            COALESCE(SUM(CASE WHEN si.custom_shipment_name IS NOT NULL THEN sii.qty ELSE 0 END), 0) AS "dispatched_qty",
            GREATEST(soi.qty - COALESCE(SUM(CASE WHEN si.custom_shipment_name IS NOT NULL THEN sii.qty ELSE 0 END), 0), 0) AS "pending_qty",  -- Ensures pending_qty is not negative
            soi.custom_use_stock AS "use_stock",
            so.delivery_date AS "ETD",
            CASE
                WHEN so.status = 'Closed' THEN 'Closed'
            ELSE 'In-Prod'
            END AS "status"
        FROM
            `tabSales Order` so
        LEFT JOIN
            `tabSales Order Item` soi ON soi.parent = so.name
        LEFT JOIN
            `tabSales Invoice` si ON si.po_no = so.po_no AND si.docstatus IN (0, 1)  -- Include both Draft (0) and Submitted (1)
        LEFT JOIN
            `tabSales Invoice Item` sii ON sii.parent = si.name AND sii.item_code = soi.item_code
        WHERE
            so.customer = "Encasa Homes Private Limited"
            AND so.custom_destination IS NOT NULL
            AND so.status != 'Closed'  -- Exclude closed sales orders
        GROUP BY
            soi.name,
            so.name,
            so.transaction_date,
            item_added_on,
            so.po_no,
            so.delivery_date,
            so.branch,
            so.custom_destination,
            so.custom_shipment_mode,
            soi.item_code,
            soi.qty,
            soi.custom_use_stock,
            so.status
        ORDER BY
            so.transaction_date DESC
        """, as_dict=1)
    return data

frappe.response["message"] = get_sales_order()
