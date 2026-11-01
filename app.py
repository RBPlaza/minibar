import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import pdfplumber
import re
import unicodedata
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
    .badge-overpaid { background-color: #e2d9f3; color: #4a235a; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 0.9em; }
    .badge-mismatch { background-color: #fce4d6; color: #a04000; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 0.9em; }
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

def clean_text(text):
    """Normalizes text for robust matching across character encodings."""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()

def extract_pdf_consumption(uploaded_pdf):
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
    xml_data = defaultdict(lambda: {"items": [], "total_qty": 0, "routings": [], "zeroed": False, "raw_text": "", "incoming_routings": [], "routed_out": []})
    global_xml_text = ""
    try:
        root = ET.fromstring(xml_bytes)
        
        # First, scan room 9016 (or any member room) for member water routings format: "Guest Name #ROOM=>..."
        member_routing_map = defaultdict(list)
        for first in root.findall(".//FIRST"):
            room_elem = first.find("FIRST")
            room_no = room_elem.text.strip() if room_elem is not None and room_elem.text else ""
            if room_no == "9016":
                for trx in first.findall(".//G_TRX_CHAR_DATE"):
                    desc = trx.find("ARTICLE_DESCRIPTION")
                    ref = trx.find("REFERENCE")
                    remark = trx.find("REMARK")
                    cc_supp = trx.find("CREDIT_CARD_SUPPLEMENT")
                    qty_elem = trx.find("QUANTITY")
                    
                    article = desc.text.strip() if desc is not None and desc.text else "Minibar - Radisson voda"
                    combined_ref = f"{ref.text if ref is not None else ''} {cc_supp.text if cc_supp is not None else ''}"
                    
                    qty = 1
                    if qty_elem is not None and qty_elem.text:
                        try:
                            qty = abs(int(float(qty_elem.text.strip())))
                        except:
                            pass
                    
                    # Match pattern like: "OZCELIK TANSEL #819=>" or "Sodja Gregor #1111=>"
                    match_origin = re.search(r'#(\d{3,4})\s*=>', combined_ref)
                    if match_origin:
                        origin_room = match_origin.group(1)
                        member_routing_map[origin_room].append((room_no, article, qty))

        for first in root.findall(".//FIRST"):
            room_elem = first.find("FIRST")
            room_no = room_elem.text.strip() if room_elem is not None and room_elem.text else ""
            
            # Inject member routings discovered from 9016
            if room_no in member_routing_map:
                for dest_room, art, q in member_routing_map[room_no]:
                    xml_data[room_no]["incoming_routings"].append((dest_room, art, q))
                    xml_data[dest_room]["routed_out"].append((room_no, art, q))

            for trx in first.findall(".//G_TRX_CHAR_DATE"):
                desc = trx.find("ARTICLE_DESCRIPTION")
                ref = trx.find("REFERENCE")
                remark = trx.find("REMARK")
                cc_supp = trx.find("CREDIT_CARD_SUPPLEMENT")
                qty_elem = trx.find("QUANTITY")
                
                article = desc.text.strip() if desc is not None and desc.text else ""
                reference = ref.text.strip() if ref is not None and ref.text else ""
                rem_text = remark.text.strip() if remark is not None and remark.text else ""
                cc_text = cc_supp.text.strip() if cc_supp is not None and cc_supp.text else ""
                
                qty = 1
                if qty_elem is not None and qty_elem.text:
                    try:
                        qty = abs(int(float(qty_elem.text.strip())))
                    except:
                        pass
                
                full_trx_text = f"{article} {reference} {rem_text} {cc_text}"
                xml_data[room_no]["raw_text"] += " " + full_trx_text
                global_xml_text += " " + full_trx_text
                
                if "PREVERJENO, NI BILO PORABE" in full_trx_text.upper():
                    xml_data[room_no]["zeroed"] = True
                
                if article:
                    xml_data[room_no]["items"].append((article, qty))
                    xml_data[room_no]["total_qty"] += qty
                    
                combined_source_check = f"{reference} {rem_text} {cc_text}"
                route_match = re.search(r'Routed\s+From.*?Room\s*#(\d{3,4})', combined_source_check, re.IGNORECASE)
                if route_match:
                    origin_room = route_match.group(1)
                    if origin_room != room_no:
                        xml_data[room_no]["incoming_routings"].append((origin_room, article, qty))
                        xml_data[origin_room]["routed_out"].append((room_no, article, qty))
                        
        xml_data["_GLOBAL_TEXT_"] = global_xml_text
        return xml_data
    except Exception as e:
        st.error(f"Error parsing XML: {e}")
        return {}

def get_member_vode_count(xml_bytes):
    """Accurately counts member water transactions routed to room 9016[cite: 6]."""
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
                cc_supp = trx.find("CREDIT_CARD_SUPPLEMENT")
                qty_elem = trx.find("QUANTITY")
                
                article = desc.text.strip() if desc is not None and desc.text else ""
                reference = ref.text.strip() if ref is not None and ref.text else ""
                rem_text = remark.text.strip() if remark is not None and remark.text else ""
                cc_text = cc_supp.text.strip() if cc_supp is not None and cc_supp.text else ""
                
                full_trx = f"{room_no} {article} {reference} {rem_text} {cc_text}".upper()
                
                is_radisson_water = "RADISSON" in article.upper() or "VODA" in article.upper()
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
    audit_results = []
    discovered_rooms = sorted(list(pdf_rooms.keys()), key=lambda x: int(x) if x.isdigit() else 0)
    
    for room in discovered_rooms:
        pdf_items = pdf_rooms.get(room, ["1× Radisson Blu voda"])
        xml_info = xml_rooms.get(room, {"items": [], "total_qty": 0, "routings": [], "zeroed": False, "raw_text": "", "incoming_routings": [], "routed_out": []})
        
        xml_items_raw = xml_info["items"]
        incoming_routings = xml_info["incoming_routings"]
        routed_out = xml_info["routed_out"]
        
        pdf_total_qty = 0
        pdf_parsed_items = []
        for item in pdf_items:
            q_match = re.search(r'^(\d+)\s*×', item)
            q = int(q_match.group(1)) if q_match else 1
            pdf_total_qty += q
            raw_pdf_name = item.split("×")[-1].strip()
            xml_eq = MAPPING_DICT.get(raw_pdf_name, raw_pdf_name)
            pdf_parsed_items.append((item, q, clean_text(raw_pdf_name), clean_text(xml_eq)))

        validated_articles = []
        matched_pdf_count = 0
        total_pdf_types = len(pdf_parsed_items)
        unconsumed_paid_items = []

        routed_out_descs = {clean_text(r[1]) for r in routed_out}
        for x_desc, x_q in xml_items_raw:
            clean_x = clean_text(x_desc)
            if clean_x in routed_out_descs:
                continue
            found_match = False
            for _, _, c_pdf, c_xml_eq in pdf_parsed_items:
                if c_xml_eq in clean_x or clean_x in c_xml_eq or c_pdf in clean_x:
                    found_match = True
                    break
            if not found_match and len(incoming_routings) == 0:
                unconsumed_paid_items.append(f"{x_q}x {x_desc}")

        for item_str, p_q, c_pdf, c_xml_eq in pdf_parsed_items:
            item_matched_qty = 0
            for x_desc, x_q in xml_items_raw:
                clean_x = clean_text(x_desc)
                if c_xml_eq in clean_x or clean_x in c_xml_eq or c_pdf in clean_x:
                    item_matched_qty += x_q

            incoming_match_qty = 0
            origin_room_name = ""
            for o_room, o_desc, o_q in incoming_routings:
                clean_o = clean_text(o_desc)
                if c_xml_eq in clean_o or clean_o in c_xml_eq or c_pdf in clean_o:
                    incoming_match_qty += o_q
                    origin_room_name = o_room

            total_accounted = item_matched_qty + incoming_match_qty

            if total_accounted >= p_q:
                if incoming_match_qty > 0 or origin_room_name == "9016":
                    validated_articles.append(f"✅ {item_str} (Routed to Member Room 9016)")
                else:
                    validated_articles.append(f"✅ {item_str}")
                matched_pdf_count += 1
            elif total_accounted > 0:
                validated_articles.append(f"⚠️ {item_str} (Partial: Accounted {total_accounted}/{p_q})")
                matched_pdf_count += 0.5
            else:
                if len(incoming_routings) > 0 and not any("routed" in va.lower() for va in validated_articles):
                    o_room, o_desc, o_q = incoming_routings[0]
                    if o_room == "9016":
                        validated_articles.append(f"✅ {item_str} (Routed to Member Room 9016)")
                        matched_pdf_count += 1
                        continue
                    else:
                        validated_articles.append(f"❌ {item_str} — Note: Received {o_q}x {o_desc} routed from Room {o_room}")
                else:
                    validated_articles.append(f"❌ {item_str}")

        routed_out_notes = []
        for dst_room, r_desc, r_q in routed_out:
            routed_out_notes.append(f"{r_q}x {r_desc} routed to Room {dst_room}")

        if len(unconsumed_paid_items) > 0 and len(incoming_routings) == 0:
            status = "Item Mismatch"
            unconsumed_str = ", ".join(unconsumed_paid_items)
            details = f"Discrepancy: Paid for unconsumed item(s) [{unconsumed_str}]."
        elif len(incoming_routings) > 0 and matched_pdf_count == 0:
            status = "Item Mismatch"
            o_room, o_desc, o_q = incoming_routings[0]
            details = f"Discrepancy: Inspected items not matched, but received {o_q}x {o_desc} routed from Room {o_room}."
        elif len(routed_out) > 0 and matched_pdf_count < total_pdf_types:
            status = "Unpaid"
            routed_desc_str = ", ".join(routed_out_notes)
            details = f"Charges posted: {routed_desc_str}, but inspected consumption items not fully matched."
        elif matched_pdf_count == total_pdf_types and len(incoming_routings) == 0:
            status = "Paid"
            details = "Verified: All inspected items accounted for in XML log."
        elif len(incoming_routings) > 0 and matched_pdf_count == total_pdf_types:
            status = "Paid"
            origin_str = incoming_routings[0][0]
            if origin_str == "9016":
                details = f"Verified: Charges successfully routed to **Member Room 9016**."
            else:
                details = f"Verified: Charges successfully received/routed from **Room {origin_str}**."
        elif xml_info["zeroed"]:
            status = "Unpaid"
            details = "Marked in XML as zero consumption (PREVERJENO, NI BILO PORABE)."
        elif matched_pdf_count > 0:
            status = "Partially Paid"
            details = f"Partial match: Accounted for {int(matched_pdf_count)} of {total_pdf_types} inspected item type(s)."
        else:
            if len(routed_out) > 0:
                status = "Unpaid"
                routed_desc_str = ", ".join(routed_out_notes)
                details = f"Posted: {routed_desc_str} (inspected items remain unpaid/unmatched)."
            else:
                status = "Unpaid"
                details = "No matching transaction or routing found in XML log for this room."
            
        audit_results.append({
            "Room Number": room,
            "Articles": validated_articles,
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
    overpaid_count = len([r for r in audit_data if r["Status"] == "Overpaid"])
    mismatch_count = len([r for r in audit_data if r["Status"] == "Item Mismatch"])
    unpaid_count = len([r for r in audit_data if r["Status"] == "Unpaid"])

    st.markdown("### 📊 Audit Summary")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Rooms", total_rooms)
    m2.metric("Fully Paid", paid_count)
    m3.metric("Partially Paid", partial_count)
    m4.metric("Item Mismatch", mismatch_count)
    m5.metric("Overpaid", overpaid_count)
    m6.metric("Unpaid / Zero", unpaid_count)

    # Filter controls
    status_filter = st.selectbox("Filter by Payment Status:", ["All", "Paid", "Partially Paid", "Item Mismatch", "Overpaid", "Unpaid"])
    filtered_data = audit_data if status_filter == "All" else [r for r in audit_data if r["Status"] == status_filter]

    st.markdown("### 🗂️ Room-by-Room Audit Results")

    if "internal_notes" not in st.session_state:
        st.session_state.internal_notes = {}

    for row in filtered_data:
        room_no = row["Room Number"]
        status = row["Status"]
        
        if status == "Paid":
            badge_class = "badge-paid"
        elif status == "Partially Paid":
            badge_class = "badge-partial"
        elif status == "Overpaid":
            badge_class = "badge-overpaid"
        elif status == "Item Mismatch":
            badge_class = "badge-mismatch"
        else:
            badge_class = "badge-unpaid"
        
        articles_html = "".join([f"<div class='article-item'>{art}</div>" for art in row["Articles"]])
        
        col_card1, col_card2 = st.columns([3, 1])
        
        with col_card1:
            card_html = f"""
            <div class="audit-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <b style="font-size: 1.1em;">Room {room_no}</b>
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
            
        with col_card2:
            st.markdown(f"<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            if status != "Paid":
                current_note = st.session_state.internal_notes.get(room_no, "— Select Note —")
                note_options = ["— Select Note —", "Paid", "Declined", "no CC"]
                selected_note = st.selectbox(
                    f"Note (Room {room_no})",
                    note_options,
                    index=note_options.index(current_note) if current_note in note_options else 0,
                    key=f"note_{room_no}"
                )
                st.session_state.internal_notes[room_no] = selected_note
            else:
                st.markdown("<span style='color: green; font-size: 0.85em;'>✔ Paid</span>", unsafe_allow_html=True)

    # CSV Export
    df_export = pd.DataFrame([{
        "Room Number": r["Room Number"],
        "Inspected Consumption": " | ".join(r["Articles"]),
        "Status": r["Status"],
        "Internal Note": st.session_state.internal_notes.get(r["Room Number"], "— Select Note —"),
        "Details": r["Details"]
    } for r in audit_data])
    
    csv = df_export.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Audit Report (CSV)",
        data=csv,
        file_name="minibar_audit_report_dynamic.csv",
        mime="text/csv",
    )

    declined_rooms = [r for r, note in st.session_state.internal_notes.items() if note == "Declined"]
    nocc_rooms = [r for r, note in st.session_state.internal_notes.items() if note == "no CC"]

    declined_str = ", ".join(sorted(declined_rooms, key=lambda x: int(x) if x.isdigit() else 0))
    nocc_str = ", ".join(sorted(nocc_rooms, key=lambda x: int(x) if x.isdigit() else 0))

    member_vode_total = get_member_vode_count(xml_bytes)
    st.markdown("---")
    st.markdown(f"**Member vode: {member_vode_total}x**")
    st.markdown(f"Declined: {declined_str}, No CC: {nocc_str}")

elif pdf_file:
    st.info("ℹ️ PDF uploaded. Please upload your Opera XML log file above to run the automated audit.")
elif xml_file:
    st.info("ℹ️ XML uploaded. Please upload your Housekeeping PDF inspection report above to run the automated audit.")
else:
    st.info("👈 Please upload both your Housekeeping PDF inspection report and Opera XML log file above to run the automated audit.")
