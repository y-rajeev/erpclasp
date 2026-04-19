WITH receipts AS (

    -- Purchase Reports
    SELECT
        'Purchase' AS receipt_type,
        pri.name AS receipt_item_name,
        pr.name AS name,
        pr.supplier_name AS supplier_name,
        pr.supplier_delivery_note AS supplier_delivery_note,
        pr.custom_lot_no AS custom_lot_no,
        pr.posting_date AS posting_date,
        pri.item_code AS item_code,
        pri.warehouse AS warehouse,
        sle.qty_after_transaction AS qty_after_transaction,
        pri.received_qty AS received_qty,
        (pri.received_qty - IFNULL(pri.rejected_qty, 0)) AS accepted_qty,
        IFNULL(pri.rejected_qty, 0) AS rejected_qty
    FROM `tabPurchase Receipt` pr
    INNER JOIN `tabPurchase Receipt Item` pri
        ON pri.parent = pr.name
    LEFT JOIN `tabPurchase Order` po
        ON po.name = pri.purchase_order
    LEFT JOIN `tabStock Ledger Entry` sle
        ON sle.voucher_type = 'Purchase Receipt'
        AND sle.voucher_no = pr.name
        AND sle.voucher_detail_no = pri.name
        AND sle.is_cancelled = 0
    WHERE pr.docstatus = 1
        AND IFNULL(po.is_subcontracted, 0) = 0

    UNION ALL

    -- Subcontracting Receipt
    SELECT
        'Subcontracting' AS receipt_type,
        scri.name AS receipt_item_name,
        scr.name AS name,
        scr.supplier_name AS supplier_name,
        scr.supplier_delivery_note AS supplier_delivery_note,
        scr.custom_lot_no AS custom_lot_no,
        scr.posting_date AS posting_date,
        scri.item_code AS item_code,
        scri.warehouse AS warehouse,
        sle.qty_after_transaction AS qty_after_transaction,
        scri.received_qty AS received_qty,
        (scri.received_qty - IFNULL(scri.rejected_qty, 0)) AS accepted_qty,
        IFNULL(scri.rejected_qty, 0) AS rejected_qty
    FROM `tabSubcontracting Receipt` scr
    INNER JOIN `tabSubcontracting Receipt Item` scri
        ON scri.parent = scr.name
    LEFT JOIN `tabStock Ledger Entry` sle
        ON sle.voucher_type = 'Subcontracting Receipt'
        AND sle.voucher_no = scr.name
        AND sle.voucher_detail_no = scri.name
        AND sle.is_cancelled = 0
    WHERE scr.docstatus = 1

),
billed_purchase_receipts AS (
    SELECT
        pii.purchase_receipt AS receipt_name,
        pii.pr_detail AS receipt_item_name,
        SUM(IFNULL(pii.qty, 0)) AS billed_qty
    FROM `tabPurchase Invoice Item` pii
    INNER JOIN `tabPurchase Invoice` pi
        ON pi.name = pii.parent
    WHERE pi.docstatus = 1
        AND IFNULL(pii.purchase_receipt, '') != ''
        AND IFNULL(pii.pr_detail, '') != ''
    GROUP BY
        pii.purchase_receipt,
        pii.pr_detail
),
subcontracting_elongation AS (
    SELECT
        se.custom_subcontracting_receipt AS receipt_name,
        sed.item_code AS item_code,
        SUM(IFNULL(sed.qty, 0)) AS elongation
    FROM `tabStock Entry` se
    INNER JOIN `tabStock Entry Detail` sed
        ON sed.parent = se.name
    WHERE se.docstatus = 1
        AND se.stock_entry_type = 'Elongation'
        AND IFNULL(se.custom_subcontracting_receipt, '') != ''
    GROUP BY
        se.custom_subcontracting_receipt,
        sed.item_code
),
subcontracting_process_loss_supplied_rows AS (
    SELECT
        base.receipt_name,
        base.fg_item_code,
        base.rm_item_code,
        ROW_NUMBER() OVER (
            PARTITION BY base.receipt_name, base.rm_item_code
            ORDER BY base.fg_idx, base.supplied_idx, base.supplied_name
        ) AS rm_occurrence
    FROM (
        SELECT
            scr.name AS receipt_name,
            scri.item_code AS fg_item_code,
            scrsi.rm_item_code AS rm_item_code,
            IFNULL(scri.idx, 0) AS fg_idx,
            IFNULL(scrsi.idx, 0) AS supplied_idx,
            scrsi.name AS supplied_name
        FROM `tabSubcontracting Receipt` scr
        INNER JOIN `tabSubcontracting Receipt Item` scri
            ON scri.parent = scr.name
        INNER JOIN `tabSubcontracting Receipt Supplied Item` scrsi
            ON scrsi.parent = scr.name
            AND scrsi.main_item_code = scri.item_code
        WHERE scr.docstatus = 1
    ) base
),
subcontracting_process_loss_rows AS (
    SELECT
        loss_base.receipt_name,
        loss_base.rm_item_code,
        loss_base.loss_qty,
        ROW_NUMBER() OVER (
            PARTITION BY loss_base.receipt_name, loss_base.rm_item_code
            ORDER BY loss_base.entry_idx, loss_base.detail_idx, loss_base.detail_name
        ) AS rm_occurrence
    FROM (
        SELECT
            loss_entry.custom_subcontracting_receipt AS receipt_name,
            loss_detail.item_code AS rm_item_code,
            IFNULL(loss_detail.qty, 0) AS loss_qty,
            IFNULL(loss_entry.idx, 0) AS entry_idx,
            IFNULL(loss_detail.idx, 0) AS detail_idx,
            loss_detail.name AS detail_name
        FROM `tabStock Entry` loss_entry
        INNER JOIN `tabStock Entry Detail` loss_detail
            ON loss_detail.parent = loss_entry.name
        WHERE loss_entry.docstatus = 1
            AND loss_entry.stock_entry_type = 'Process Loss'
            AND IFNULL(loss_entry.custom_subcontracting_receipt, '') != ''
    ) loss_base
),
subcontracting_process_loss AS (
    SELECT
        supplied_rows.receipt_name,
        supplied_rows.fg_item_code AS item_code,
        SUM(loss_rows.loss_qty) AS process_loss
    FROM subcontracting_process_loss_supplied_rows supplied_rows
    INNER JOIN subcontracting_process_loss_rows loss_rows
        ON loss_rows.receipt_name = supplied_rows.receipt_name
        AND loss_rows.rm_item_code = supplied_rows.rm_item_code
        AND loss_rows.rm_occurrence = supplied_rows.rm_occurrence
    GROUP BY
        supplied_rows.receipt_name,
        supplied_rows.fg_item_code
)

SELECT
    receipts.receipt_type,
    receipts.name,
    receipts.supplier_name,
    receipts.supplier_delivery_note,
    receipts.custom_lot_no,
    receipts.posting_date,
    receipts.item_code,
    receipts.received_qty,
    receipts.accepted_qty,
    receipts.rejected_qty,
    CASE
        WHEN receipts.receipt_type = 'Purchase' THEN IFNULL(bpr.billed_qty, 0)
        ELSE NULL
    END AS billed_qty,
    CASE
        WHEN receipts.receipt_type = 'Subcontracting' THEN IFNULL(se.elongation, 0)
        ELSE NULL
    END AS elongation,
    CASE
        WHEN receipts.receipt_type = 'Subcontracting' THEN IFNULL(spl.process_loss, 0)
        ELSE NULL
    END AS process_loss,
    receipts.warehouse,
    receipts.qty_after_transaction
FROM receipts
LEFT JOIN billed_purchase_receipts bpr
    ON bpr.receipt_name = receipts.name
    AND bpr.receipt_item_name = receipts.receipt_item_name
LEFT JOIN subcontracting_elongation se
    ON se.receipt_name = receipts.name
    AND se.item_code = receipts.item_code
LEFT JOIN subcontracting_process_loss spl
    ON spl.receipt_name = receipts.name
    AND spl.item_code = receipts.item_code
ORDER BY receipts.posting_date DESC, receipts.name DESC, receipts.item_code ASC
