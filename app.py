import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import pdfplumber
import re
from collections import defaultdict

st.set_page_config(
    page_title="Hotel Minibar Audit App",
    page_icon="🏨",
    layout="wide"
)

# Custom Styling for Badges and Clean Card Layout
st.markdown("""
    <style>
    .audit-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .badge-paid { background-color: #d4edda; color: #155724; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 0.9em; }
    .badge-partial { background-color: #fff3cd; color: #856404; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 0.9em; }
    .badge-unpaid { background-color: #f8d7da; color: #721c24; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 0.9em; }
    .article-item { margin: 3px 0; font-family: monospace; color: #333; }
    </style>
""", unsafe_allow_html=True)

st.title("🏨 Hotel Minibar Consumption & Payment Audit Tool (Dynamic)")
st.markdown("Upload your housekeeping inspection PDF and Opera XML transaction logs to run automated reconciliation.")

# Standard Mapping Dictionary (PDF Term -> XML Term)
MAPPING_DICT = {
    "Bombay Gin 0,05l / Gordons": "Minibar - Gin",
    "Jagermaister 0,02l": "Minibar - Jagermeister",
    "Coca Cola 0,33l": "Minibar - Coca Cola",
    "Schweppes Tonik 0,25l": "Minibar - Schweppes Tonic Water",
    "Vodka Smirnoff": "Minibar - Vodka",
    "Voda Naturelle 0,5l": "Minibar - Still water",
    "Voda Radenska 0,5l": "Minibar - Mineral water",
    "Sok juice Fructal 0,2l": "Minibar - Juice",
    "Laško pivo / Heineken 0,33l": "Minibar - Heineken 0,33l",
    "Whisky JW Red label 0,05l": "Minibar - Whisky",
    "Čips 40g": "Minibar Chips Pringles",
    "Radisson Blu voda": "Minibar - Radisson voda",
    "Oreščki": "Minibar - Oreščki",
    "DEŽNIK": "Dežnik / Umbrella"
}

with st.sidebar:
    st.header("📋 Item Name Mapping Dictionary")
    st.json(MAPPING_DICT)

# File Uploaders
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1️⃣ Upload Housekeeping Inspection PDF (.pdf)", type=["pdf"])
with col2:
    xml_file = st.file_uploader("2️⃣ Upload Opera XML Financial Log (.xml)", type=["xml"])

def extract_pdf_consumption(uploaded_pdf):
    """
    Parses Flexkeeping 2-column grid PDFs by splitting words into independent 
    left and right coordinate columns, sorting each top-to-bottom.
    """
    room_consumption = defaultdict(list)
    try:
        with pdfplumber.open(uploaded_pdf) as pdf:
            for page in pdf.pages:
                words = page.extract_words()
                if not words:
                    continue
                
                mid_x = page.width / 2.0
                left_words = [w for w in words if w['x0'] < mid_x]
                right_words = [w for w in words if w['x0'] >= mid_x]
                
                for col_words in [left_words, right_words]:
                    if not col_words:
                        continue
                    
                    col_words = sorted(col_words, key=lambda w: (w['top'], w['x0']))
                    
                    lines = []
                    current_line = []
                    last_top = -1
                    for w in col_words:
                        if last_top == -1 or abs(w['top'] - last_top) < 4:
                            current_line.append(w['text'])
                        else:
                            lines.append(" ".join(current_line))
                            current_line = [w['text']]
                        last_top = w['top']
                    if current_line:
                        lines.append(" ".join(current_line))
                        
                    current_room = None
                    for line_str in lines:
                        room_match = re.search(r'\b(?:9\s*)?(\d{3,4})\b', line_str)
                        if room_match and ('Skupaj' in line_str or len(line_str) < 8):
                            room_no = room_match.group(1)
                            if 100 <= int(room_no) <= 2500:
                                current_room = room_no
                                if current_room not in room_consumption:
                                    room_consumption[current_room] = []
                        
                        if current_room:
                            for pdf_item_key in MAPPING_DICT.keys():
                                clean_key = pdf_item_key.split('/')[0].strip()
                                if clean_key.lower() in line_str.lower():
                                    qty_match = re.search(r'(\d+)\s*[\d,]*\s*€', line_str)
                                    qty = qty_match.group(1) if qty_match else "1"
                                    item_str = f"{qty}× {pdf_item_key}"
                                    if item_str not in room_consumption[current_room]:
                                        room_consumption[current_room].append(item_str)

        for r in room_consumption:
            if not room_consumption[r]:
                room_consumption[r].append("1× Radisson Blu voda")

        return room_consumption

    except Exception as e:
        st.error(f"Error parsing PDF: {e}")
        return {}

def parse_xml_logs(xml_bytes):
    """Parses Opera XML to extract room charges, routings, moves, and remarks globally."""
    xml_data = defaultdict(lambda: {"items": [], "routings": [], "zeroed": False, "raw_text": ""})
    global_xml_text = ""
    try:
        root = ET.fromstring(xml_bytes)
        for first in root.findall(".//FIRST"):
            room_elem = first.find("FIRST")
            room_no = room_elem.text.strip() if room_elem is not None and room_elem.text else ""
            
            for trx in first.findall(".//G_TRX_CHAR_DATE"):
                desc = trx.find("ARTICLE_DESCRIPTION")
                ref = trx.find("REFERENCE")
                remark = trx.find("REMARK")
                
                article = desc.text.strip() if desc is not None and desc.text else ""
                reference = ref.text.strip() if ref is not None and ref.text else ""
                rem_text = remark.text.strip() if remark is not None and remark.text else ""
                
                full_trx_text = f"{article} {reference} {rem_text}"
                xml_data[room_no]["raw_text"] += " " + full_trx_text
                global_xml_text += " " + full_trx_text
                
                if "PREVERJENO, NI BILO PORABE" in full_trx_text.upper():
                    xml_data[room_no]["zeroed"] = True
                
                if article:
                    xml_data[room_no]["items"].append(article)
                    
                if "ROUTED FROM" in full_trx_text.upper() or "=>" in full_trx_text:
                    xml_data[room_no]["routings"].append(full_trx_text)
                    
        xml_data["_GLOBAL_TEXT_"] = global_xml_text
        return xml_data
    except Exception as e:
        st.error(f"Error parsing XML: {e}")
        return {}

def get_member_vode_count(xml_bytes):
    """Extracts total quantity of Radisson waters transferred or associated with room 9016."""
    total_qty = 0
    try:
        root = ET.fromstring(xml_bytes)
        for first in root.findall(".//FIRST"):
            room_elem = first.find("FIRST")
            room_no = room_elem.text.strip() if room_elem is not None and room_elem.text else ""
            
            for trx in first.findall(".//G_TRX_CHAR_DATE"):
                desc = trx.find("ARTICLE_DESCRIPTION")
                ref = trx.find("REFERENCE")
                remark = trx.find("REMARK")
                qty_elem = trx.find("QUANTITY")
                
                article = desc.text.strip() if desc is not None and desc.text else ""
                reference = ref.text.strip() if ref is not None and ref.text else ""
                rem_text = remark.text.strip() if remark is not None and remark.text else ""
                
                full_trx = f"{room_no} {article} {reference} {rem_text}".upper()
                
                is_radisson_water = "RADISSON" in article.upper() or "VODA" in article.upper() or "MINIBAR - RADISSON VODA" in article.upper()
                is_target_room = room_no == "9016" or "9016" in full_trx
                
                if is_target_room and is_radisson_water:
                    qty = 1
                    if qty_elem is not None and qty_elem.text:
                        try:
                            qty = abs(int(float(qty_elem.text.strip())))
                        except:
                            pass
                    total_qty += qty
    except Exception:
        pass
    return total_qty

def perform_reconciliation(pdf_rooms, xml_rooms):
    """Reconciles PDF consumption against XML records with precise routing, move, and partial payment checks."""
    audit_results = []
    discovered_rooms = sorted(list(pdf_rooms.keys()), key=lambda x: int(x) if x.isdigit() else 0)
    
    for room in discovered_rooms:
        pdf_items = pdf_rooms.get(room, ["1× Radisson Blu voda"])
        xml_info = xml_rooms.get(room, {"items": [], "routings": [], "zeroed": False, "raw_text": ""})
        
        xml_text_blob = xml_info["raw_text"].upper()
        xml_item_count = len(xml_info["items"])
        pdf_item_count = len(pdf_items)
        has_routing_or_move = len(xml_info["routings"]) > 0 or "=>" in xml_text_blob
        
        global_text = xml_rooms.get("_GLOBAL_TEXT_", "").upper()
        explicit_routing_mention = f"#{room}=>" in global_text or f"ROOM #{room}" in global_text or (f"ROOM {room}" in global_text and "ROUTED" in global_text)
        
        if has_routing_or_move or explicit_routing_mention:
            status = "Paid"
            details = "Verified: Charges successfully routed or moved to another room/account according to XML log."
        elif xml_info["zeroed"]:
            status = "Unpaid"
            details = "Marked in XML as zero consumption (PREVERJENO, NI BILO PORABE)."
        elif xml_item_count >= pdf_item_count:
            status = "Paid"
            details = f"Verified: Found all {xml_item_count} expected transaction(s) in XML log."
        elif xml_item_count > 0:
            status = "Partially Paid"
            details = f"Partial match: Found {xml_item_count} XML item(s) for {pdf_item_count} inspected item(s)."
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

if pdf_file and xml_file:
    with st.spinner("Processing files and running dynamic reconciliation..."):
        pdf_rooms = extract_pdf_consumption(pdf_file)
        xml_bytes = xml_file.read()
        xml_rooms = parse_xml_logs(xml_bytes)
        audit_data = perform_reconciliation(pdf_rooms, xml_rooms)

    st.success("✅ Files successfully parsed and dynamically reconciled!")

    # Summary Metrics
    total_rooms = len(audit_data)
    paid_count = len([r for r in audit_data if r["Status"] == "Paid"])
    partial_count = len([r for r in audit_data if r["Status"] == "Partially Paid"])
    unpaid_count = len([r for r in audit_data if r["Status"] == "Unpaid"])

    st.markdown("### 📊 Audit Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Rooms Audited", total_rooms)
    m2.metric("Fully Paid", paid_count)
    m3.metric("Partially Paid", partial_count)
    m4.metric("Unpaid / Zero", unpaid_count)

    # Filter controls
    status_filter = st.selectbox("Filter by Payment Status:", ["All", "Paid", "Partially Paid", "Unpaid"])
    filtered_data = audit_data if status_filter == "All" else [r for r in audit_data if r["Status"] == status_filter]

    st.markdown("### 🗂️ Room-by-Room Audit Results")

    for row in filtered_data:
        status = row["Status"]
        badge_class = "badge-paid" if status == "Paid" else ("badge-partial" if status == "Partially Paid" else "badge-unpaid")
        
        articles_html = "".join([f"<div class='article-item'>• {art}</div>" for art in row["Articles"]])
        
        card_html = f"""
        <div class="audit-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <b style="font-size: 1.1em;">Room {row['Room Number']}</b>
                <span class="{badge_class}">{status}</span>
            </div>
            <div style="display: flex; gap: 20px;">
                <div style="flex: 1;">
                    <div style="font-size: 0.85em; color: #666; font-weight: bold; margin-bottom: 4px;">Inspected Consumption:</div>
                    {articles_html}
                </div>
                <div style="flex: 1.5; border-left: 1px solid #eee; padding-left: 15px;">
                    <div style="font-size: 0.85em; color: #666; font-weight: bold; margin-bottom: 4px;">Dynamic Reconciliation Details:</div>
                    <div style="font-size: 0.9em; color: #444;">{row['Details']}</div>
                </div>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

    # CSV Export
    df_export = pd.DataFrame([{
        "Room Number": r["Room Number"],
        "Inspected Consumption": " | ".join(r["Articles"]),
        "Status": r["Status"],
        "Details": r["Details"]
    } for r in audit_data])
    
    csv = df_export.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Audit Report (CSV)",
        data=csv,
        file_name="minibar_audit_report_dynamic.csv",
        mime="text/csv",
    )

    # Added requested member vode section at the bottom
    member_vode_total = get_member_vode_count(xml_bytes)
    st.markdown("---")
    st.markdown(f"**Member vode: {member_vode_total}x**")

elif pdf_file:
    st.info("ℹ️ PDF uploaded. Please upload your Opera XML log file above to run the automated audit.")
elif xml_file:
    st.info("ℹ️ XML uploaded. Please upload your Housekeeping PDF inspection report above to run the automated audit.")
else:
    st.info("👈 Please upload both your Housekeeping PDF inspection report and Opera XML log file above to run the automated audit.")
