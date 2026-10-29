def perform_reconciliation(pdf_rooms, xml_rooms):
    """Reconciles PDF consumption against XML records with precise routing and move checks."""
    audit_results = []
    discovered_rooms = sorted(list(pdf_rooms.keys()), key=lambda x: int(x) if x.isdigit() else 0)
    
    for room in discovered_rooms:
        pdf_items = pdf_rooms.get(room, ["1× Radisson Blu voda"])
        xml_info = xml_rooms.get(room, {"items": [], "routings": [], "zeroed": False, "raw_text": ""})
        
        xml_text_blob = xml_info["raw_text"].upper()
        xml_item_count = len(xml_info["items"])
        has_routing_or_move = len(xml_info["routings"]) > 0 or "=>" in xml_text_blob
        
        # Check if this specific room was routed or moved outward/inward explicitly
        global_text = xml_rooms.get("_GLOBAL_TEXT_", "").upper()
        explicit_routing_mention = f"#{room}=>" in global_text or f"ROOM #{room}" in global_text or f"ROOM {room}" in global_text and "ROUTED" in global_text
        
        if has_routing_or_move or explicit_routing_mention:
            status = "Paid"
            details = "Verified: Charges successfully routed or moved to another room/account according to XML log."
        elif xml_info["zeroed"]:
            status = "Unpaid"
            details = "Marked in XML as zero consumption (PREVERJENO, NI BILO PORABE)."
        elif xml_item_count > 0:
            status = "Paid"
            details = f"Verified: Found {xml_item_count} direct transaction(s) in XML log."
        else:
            status = "Unpaid"
            details = "No matching transaction or routing found in XML log."
            
        audit_results.append({
            "Room Number": room,
            "Articles": pdf_items,
            "Status": status,
            "Details": details
        })
        
    return audit_results
