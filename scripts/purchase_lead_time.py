def get_purchase_lead_time():
    """
    Calculates supplier + item level purchase lead time
    based on last 1 year of GRN / Subcontracting Receipts.
    """

    query = """
        SELECT
            supplier_name,
            item_code,

            /* Lead time metrics */
            ROUND(AVG(lead_time_days)) AS avg_lead_time_days,
            MIN(lead_time_days) AS min_lead_time_days,
            MAX(lead_time_days) AS max_lead_time_days,
            ROUND(STDDEV(lead_time_days), 1) AS stddev_lead_time_days,
            COUNT(*) AS total_grns,

            /* Planning lead time (mean + buffer) */
            CAST(
                CEILING(
                    ROUND(AVG(lead_time_days))
                    + IFNULL(ROUND(STDDEV(lead_time_days), 1), 0)
                ) AS UNSIGNED
            ) AS planning_lead_time_days,

            /* Metadata */
            365 AS data_window_days,
            CURDATE() AS snapshot_date

        FROM (

            /* --------------------------------------------------
               NORMAL PURCHASE (GRN BASED)
            -------------------------------------------------- */
            SELECT
                po.supplier_name,
                poi.item_code,

                /* Clamp negative lead times to 0 */
                GREATEST(
                    DATEDIFF(pr.posting_date, po.transaction_date),
                    0
                ) AS lead_time_days

            FROM `tabPurchase Order` po
            INNER JOIN `tabPurchase Order Item` poi
                ON poi.parent = po.name

            INNER JOIN `tabPurchase Receipt Item` pri
                ON pri.purchase_order = po.name
                AND pri.item_code = poi.item_code

            INNER JOIN `tabPurchase Receipt` pr
                ON pr.name = pri.parent
                AND pr.docstatus = 1
                AND pr.posting_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)

            WHERE
                po.is_subcontracted = 0
                AND po.docstatus = 1

            UNION ALL

            /* --------------------------------------------------
               SUBCONTRACTING PURCHASE (SR BASED)
            -------------------------------------------------- */
            SELECT
                po.supplier_name,
                poi.fg_item AS item_code,

                GREATEST(
                    DATEDIFF(sr.posting_date, po.transaction_date),
                    0
                ) AS lead_time_days

            FROM `tabPurchase Order` po
            INNER JOIN `tabPurchase Order Item` poi
                ON poi.parent = po.name

            INNER JOIN `tabSubcontracting Order` so
                ON so.purchase_order = po.name

            INNER JOIN `tabSubcontracting Receipt Item` sor
                ON sor.subcontracting_order = so.name
                AND sor.item_code = poi.fg_item

            INNER JOIN `tabSubcontracting Receipt` sr
                ON sr.name = sor.parent
                AND sr.docstatus = 1
                AND sr.posting_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)

            WHERE
                po.is_subcontracted = 1
                AND po.docstatus = 1

        ) base_data

        GROUP BY
            supplier_name,
            item_code

        ORDER BY
            supplier_name,
            item_code;
    """

    return frappe.db.sql(query, as_dict=True)


# API response
frappe.response["message"] = get_purchase_lead_time()
