def build_email_body(notification: dict) -> str:
    is_status_change = notification.get("is_status_change", True)

    if is_status_change:
        lines = [
            "Visa status has changed.\n",
            f"Previous status: {notification['from_status']}",
            f"Current status:  {notification['to_status']}",
            f"Last updated:    {notification['case_last_updated']}",
            f"Case created:    {notification['case_created']}",
        ]
        to_status = notification["to_status"]
        if to_status == "Refused (AP)":
            lines.append(
                "\nThis is a 221(g) administrative processing hold, NOT a final refusal. "
                "Your case is still being processed and will be re-adjudicated once the review is complete."
            )
        elif to_status == "Refused (Final)":
            lines.append(
                "\nThis appears to be a final refusal (no mention of administrative processing "
                "in the CEAC description). Consult your refusal letter for the specific reason."
            )
    else:
        lines = [
            "Case updated (status unchanged).\n",
            f"Current status:  {notification['to_status']} (unchanged)",
            f"Last updated:    {notification.get('previous_last_updated', '?')}"
            f" -> {notification['case_last_updated']}",
            f"Case created:    {notification['case_created']}",
        ]

    if notification["history"]:
        lines.append("\n--- Status Timeline ---")
        for entry in notification["history"]:
            lines.append(f"  {entry['from']} -> {entry['to']}  ({entry['at']})")

    lines.append("\n--- Details ---")
    lines.append(f"Visa type:    {notification['visa_type']}")
    lines.append(f"Description:  {notification['description']}")

    return "\n".join(lines)
