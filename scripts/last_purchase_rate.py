def get_last_purchase_rate():
    """
    Returns the latest submitted Purchase Order rate
    for each supplier + item combination.
    """

    query = """
        SELECT
            latest.supplier_name,
            latest.item_code,
            latest.last_purchase_rate,
            latest.currency,
            latest.uom,
            latest.purchase_order,
            latest.transaction_date,
            latest.schedule_date,
            CURDATE() AS snapshot_date

        FROM (
            SELECT
                po.supplier_name,
                poi.item_code,
                poi.rate AS last_purchase_rate,
                po.currency,
                poi.uom,
                po.name AS purchase_order,
                po.transaction_date,
                poi.schedule_date,
                poi.idx

            FROM `tabPurchase Order` po
            INNER JOIN `tabPurchase Order Item` poi
                ON poi.parent = po.name

            WHERE
                po.docstatus = 1
                AND IFNULL(poi.item_code, '') != ''
                AND NOT EXISTS (
                    SELECT 1
                    FROM `tabPurchase Order` newer_po
                    INNER JOIN `tabPurchase Order Item` newer_poi
                        ON newer_poi.parent = newer_po.name
                    WHERE
                        newer_po.docstatus = 1
                        AND newer_po.supplier_name = po.supplier_name
                        AND newer_poi.item_code = poi.item_code
                        AND (
                            newer_po.transaction_date > po.transaction_date
                            OR (
                                newer_po.transaction_date = po.transaction_date
                                AND newer_po.name > po.name
                            )
                            OR (
                                newer_po.transaction_date = po.transaction_date
                                AND newer_po.name = po.name
                                AND newer_poi.idx > poi.idx
                            )
                        )
                )
        ) latest

        ORDER BY
            latest.supplier_name,
            latest.item_code;
    """

    return frappe.db.sql(query, as_dict=True)


# API response
frappe.response["message"] = get_last_purchase_rate()
