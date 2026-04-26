sql_query = """
SELECT
    so.po_no AS po_no,
    so.transaction_date AS po_date,
    so.delivery_date AS dispatch_date,
    so.branch AS branch,
    so.custom_destination AS "channel_abb",
    so.custom_shipment_mode AS mode,
    so.total_qty AS po_qty,
    COALESCE(SUM(CASE WHEN si.custom_shipment_name IS NOT NULL THEN si.total_qty ELSE 0 END), 0) AS dispatched_qty,
    (so.total_qty - COALESCE(SUM(CASE WHEN si.custom_shipment_name IS NOT NULL THEN si.total_qty ELSE 0 END), 0)) AS pending_qty,
    CASE
        WHEN so.status = 'Closed' THEN 'Closed'
        WHEN so.delivery_date < CURDATE() THEN 'Overdue'
        ELSE 'In-Prod'
    END AS "status"
FROM
    `tabSales Order` so
LEFT JOIN
    `tabSales Invoice` si ON si.po_no = so.po_no
WHERE
    so.customer = "Encasa Homes Private Limited"
    AND so.custom_destination IS NOT NULL
    AND so.status != 'Closed'
GROUP BY
    so.po_no,
    so.transaction_date,
    so.delivery_date,
    so.branch,
    so.custom_destination,
    so.custom_shipment_mode,
    so.total_qty,
    so.status
ORDER BY
    so.branch,
    so.delivery_date ASC;
"""

results = frappe.db.sql(sql_query, as_dict=True)

branch_email_map = {
    "Mumbai": {
        "recipients": ["yrajeev733@gmail.com"],
        "cc": ["yrajeev5911@gmail.com"],
        "subject": "Need your attention - Mumbai",
    },
    "Karur": {
        "recipients": ["mail.yrajeev@gmail.com"],
        "cc": ["yrajeev5911@gmail.com"],
        "subject": "Need your attention - Karur",
    },
}

if results:
    branch_rows = {}

    for row in results:
        branch = row.get("branch") or "Unknown"
        branch_rows.setdefault(branch, []).append(row)

    for branch, rows_for_branch in branch_rows.items():
        mail_config = branch_email_map.get(
            branch,
            {
                "recipients": ["mail.yrajeev@gmail.com"],
                "cc": ["yrajeev5911@gmail.com"],
                "subject": f"Need your attention - {branch}",
            },
        )

        rows = []
        rows.append("<div style='font-family:Segoe UI, Arial, sans-serif; color:#1f2937; background:#f4f7fb; padding:16px;'>")
        rows.append("<div style='max-width:960px; margin:0 auto; background:#ffffff; border:1px solid #dbe4f0; border-radius:12px; overflow:hidden;'>")
        rows.append("<div style='padding:18px;'>")
        rows.append("<p style='margin:0 0 8px 0; font-size:14px;'><strong>Hi Team,</strong></p>")
        rows.append("<p style='margin:0 0 12px 0; font-size:13px; line-height:1.45; color:#475467;'>Please confirm that the following orders will be dispatched according to the agreed dates:</p>")
        rows.append("<div style='overflow-x:auto;'>")
        rows.append("<table style='width:100%; border-collapse:collapse; font-size:12px; border:1px solid #dbe4f0; table-layout:auto;'>")
        rows.append("<tr style='background:#ecfdf3; color:#134e4a;'><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:left; white-space:nowrap;'>PO No</th><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:left; white-space:nowrap;'>PO Date</th><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:left; white-space:nowrap;'>Dispatch Date</th><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:left; white-space:nowrap;'>Branch</th><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:left; white-space:nowrap;'>Country</th><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:left; white-space:nowrap;'>Mode</th><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:right; white-space:nowrap;'>PO Qty</th><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:right; white-space:nowrap;'>Dispatched Qty</th><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:right; white-space:nowrap;'>Pending Qty</th><th style='padding:8px 8px; border:1px solid #dbe4f0; text-align:left; white-space:nowrap;'>Status</th></tr>")

        for row in rows_for_branch:
            rows.append(
                f"<tr style='background:#ffffff;'><td style='padding:7px 8px; border:1px solid #dbe4f0; white-space:nowrap;'>{row['po_no']}</td><td style='padding:7px 8px; border:1px solid #dbe4f0; white-space:nowrap;'>{row['po_date']}</td><td style='padding:7px 8px; border:1px solid #dbe4f0; white-space:nowrap;'>{row['dispatch_date']}</td><td style='padding:7px 8px; border:1px solid #dbe4f0; white-space:nowrap;'>{row['branch']}</td><td style='padding:7px 8px; border:1px solid #dbe4f0; white-space:nowrap;'>{row['channel_abb']}</td><td style='padding:7px 8px; border:1px solid #dbe4f0; white-space:nowrap;'>{row['mode']}</td><td style='padding:7px 8px; border:1px solid #dbe4f0; text-align:right; white-space:nowrap;'>{row['po_qty']}</td><td style='padding:7px 8px; border:1px solid #dbe4f0; text-align:right; white-space:nowrap;'>{row['dispatched_qty']}</td><td style='padding:7px 8px; border:1px solid #dbe4f0; text-align:right; white-space:nowrap;'>{row['pending_qty']}</td><td style='padding:7px 8px; border:1px solid #dbe4f0; white-space:nowrap;'><span style='display:inline-block; padding:2px 8px; border-radius:999px; background:#fef3c7; color:#92400e; font-weight:600; white-space:nowrap; font-size:11px;'>{row['status']}</span></td></tr>"
            )

        rows.append("</table>")
        rows.append("</div>")
        rows.append("<p style='margin:12px 0 0 0; font-size:13px; line-height:1.45; color:#475467;'>If there are any changes, please let us know along with the reason for the delay.</p>")
        rows.append("<p style='margin:12px 0 0 0; font-size:12px; color:#667085;'>Regards,<br>ERPNext System</p>")
        rows.append("<p style='margin:10px 0 0 0; font-size:11px; color:#98a2b3;'>This is an auto-generated mail.</p>")
        rows.append("</div>")
        rows.append("</div>")
        rows.append("</div>")
        html_content = "".join(rows)

        recipients = ", ".join(mail_config["recipients"])
        cc_recipients = ", ".join(mail_config["cc"])

        log("Auto email branch=" + branch)
        log("To=" + recipients)
        log("CC=" + cc_recipients)
        log("Rows=" + str(len(rows_for_branch)))

        frappe.sendmail(
            recipients=recipients,
            cc=cc_recipients,
            subject=mail_config["subject"],
            message=html_content,
            expose_recipients="header",
            queue_separately=False,
        )
else:
    log("No data found for the query.")
