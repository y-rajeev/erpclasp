def get_sales_order_events():
    customer = frappe.form_dict.get("customer") or "Encasa Homes Private Limited"
    sales_order = frappe.form_dict.get("sales_order")

    conditions = ""
    params = {"customer": customer}

    if sales_order:
        conditions += " AND so.name = %(sales_order)s "
        params["sales_order"] = sales_order

    query = f"""
        SELECT
            -- Core Identifiers
            events.so_id,
            events.shipment_id,
            events.sku,

            -- Item Attributes
            i.item_group AS product,
            i.custom_product_type AS product_type,
            i.custom_line AS line,
            i.custom_design AS color,
            i.custom_size AS size,
            i.custom_pcs__pack AS pcs_pack,

            -- Quantities
            events.sets,
            (events.sets * COALESCE(i.custom_pcs__pack, 0)) AS pcs,

            -- Event Info
            events.event_type,
            events.event_date

        FROM (

            -- 🔥 1. INITIAL QTY
            SELECT
                so.name AS so_id,
                so.po_no AS shipment_id,
                soi.item_code AS sku,

                COALESCE(
                    (
                        SELECT cl.old_qty
                        FROM `tabSales Order Item Change Log` cl
                        WHERE cl.sales_order = so.name
                          AND cl.item_code = soi.item_code
                        ORDER BY cl.changed_on ASC
                        LIMIT 1
                    ),
                    soi.qty
                ) AS sets,

                DATE(COALESCE(soi.custom_added_on, so.transaction_date)) AS event_date,
                'INITIAL' AS event_type

            FROM `tabSales Order` so
            INNER JOIN `tabSales Order Item` soi
                ON soi.parent = so.name

            WHERE
                so.customer = %(customer)s
                AND so.custom_destination IS NOT NULL
                AND so.status != 'Closed'
                {conditions}

            UNION ALL

            -- 🔼 2. QTY INCREASE
            SELECT
                cl.sales_order AS so_id,
                so.po_no AS shipment_id,
                cl.item_code AS sku,
                (cl.new_qty - cl.old_qty) AS sets,
                DATE(cl.changed_on) AS event_date,
                'INCREASE' AS event_type

            FROM `tabSales Order Item Change Log` cl
            INNER JOIN `tabSales Order` so
                ON so.name = cl.sales_order

            WHERE
                so.customer = %(customer)s
                AND so.custom_destination IS NOT NULL
                AND so.status != 'Closed'
                AND (cl.new_qty - cl.old_qty) > 0
                {conditions}

            UNION ALL

            -- 🔽 3. QTY DECREASE / REMOVED (new_qty = 0 => line gone or qty fully removed)
            SELECT
                cl.sales_order AS so_id,
                so.po_no AS shipment_id,
                cl.item_code AS sku,
                (cl.new_qty - cl.old_qty) AS sets,  -- negative values
                DATE(cl.changed_on) AS event_date,
                CASE
                    WHEN IFNULL(cl.new_qty, -1) = 0 THEN 'REMOVED'
                    ELSE 'DECREASE'
                END AS event_type

            FROM `tabSales Order Item Change Log` cl
            INNER JOIN `tabSales Order` so
                ON so.name = cl.sales_order

            WHERE
                so.customer = %(customer)s
                AND so.custom_destination IS NOT NULL
                AND so.status != 'Closed'
                AND (cl.new_qty - cl.old_qty) < 0
                {conditions}

        ) AS events

        LEFT JOIN `tabItem` i
            ON i.name = events.sku

        ORDER BY
            events.so_id,
            events.sku,
            events.event_date,
            events.event_type
    """

    try:
        data = frappe.db.sql(query, params, as_dict=True)
        return data

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Sales Order Events API Error")
        frappe.throw("Failed to fetch sales order events")


frappe.response["message"] = get_sales_order_events()
