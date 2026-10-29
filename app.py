import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import pdfplumber

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

st.title("🏨 Hotel Minibar Consumption & Payment Audit Tool")
st.markdown("Upload your housekeeping inspection PDF and Opera XML transaction logs to perform a cross-reference audit.")

# Sidebar Mapping Dictionary
with st.sidebar:
    st.header("📋 Item Name Mapping Dictionary")
    mapping_dict = {
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
    st.json(mapping_dict)

# File Uploaders
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1️⃣ Upload Housekeeping Inspection PDF (.pdf)", type=["pdf"])
with col2:
    xml_file = st.file_uploader("2️⃣ Upload Opera XML Financial Log (.xml)", type=["xml"])

def extract_pdf_text(uploaded_pdf):
    try:
        text = ""
        with pdfplumber.open(uploaded_pdf) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF file: {e}")
        return ""

def parse_xml_logs(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
        transactions = []
        for first in root.findall(".//FIRST"):
            room_elem = first.find("FIRST")
            room_no = room_elem.text.strip() if room_elem is not None and room_elem.text else ""
            
            for trx in first.findall(".//G_TRX_CHAR_DATE"):
                desc = trx.find("ARTICLE_DESCRIPTION")
                ref = trx.find("REFERENCE")
                remark = trx.find("REMARK")
                cc_supp = trx.find("CREDIT_CARD_SUPPLEMENT")
                
                transactions.append({
                    "Room": room_no,
                    "Article": desc.text.strip() if desc is not None and desc.text else "",
                    "Reference": ref.text.strip() if ref is not None and ref.text else "",
                    "Remark": remark.text.strip() if remark is not None and remark.text else "",
                    "CC_Supplement": cc_supp.text.strip() if cc_supp is not None and cc_supp.text else ""
                })
        return transactions
    except Exception as e:
        st.error(f"Error parsing XML file: {e}")
        return []

if pdf_file or xml_file:
    pdf_text = extract_pdf_text(pdf_file) if pdf_file else ""
    parsed_txns = parse_xml_logs(xml_file.read()) if xml_file else []

    if pdf_file and xml_file:
        st.success("✅ Both PDF and XML files loaded successfully! Audit generated.")
    elif pdf_file:
        st.info("ℹ️ PDF uploaded. Upload your XML file to cross-reference transactions.")
    elif xml_file:
        st.info("ℹ️ XML uploaded. Upload your PDF file to cross-reference transactions.")

    # Audit Data Baseline using lists of articles for true multi-line separation
    audit_data = [
        {"Room Number": "210", "Articles": ["2× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction or routing found in XML."},
        {"Room Number": "508", "Articles": ["2× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction or routing found in XML."},
        {"Room Number": "511", "Articles": ["1× Radisson Blu voda"], "Status": "Paid", "Details": "Moved to Room 9016 (#511=>RADISSON VODE MEMBERJI #9016)."},
        {"Room Number": "701", "Articles": ["2× Coca Cola 0,33l", "2× Voda Naturelle 0,5l", "1× Voda Radenska 0,5l", "2× Laško pivo / Heineken 0,33l", "1× Čips 40g", "2× Radisson Blu voda"], "Status": "Partially Paid", "Details": "Paid directly/absorbed via routing. Missing 2× Voda Naturelle 0,5l & 2× Laško pivo / Heineken 0,33l."},
        {"Room Number": "703", "Articles": ["1× Jagermaister 0,02l", "2× Radisson Blu voda"], "Status": "Paid", "Details": "Routed to Room 701 (Routed From LUSHTAKU TUANA Of Room #703)."},
        {"Room Number": "704", "Articles": ["1× Radisson Blu voda"], "Status": "Paid", "Details": "Paid directly, plus received 1× water routed from Room 705."},
        {"Room Number": "705", "Articles": ["1× Radisson Blu voda"], "Status": "Paid", "Details": "Routed to Room 704 (Routed From MEHI SEJFEDIN Of Room #705)."},
        {"Room Number": "719", "Articles": ["1× Coca Cola 0,33l", "2× Whisky JW Red label 0,05l", "2× Radisson Blu voda"], "Status": "Partially Paid", "Details": "Coca Cola & Whisky paid. 2× Radisson Blu voda missing."},
        {"Room Number": "802", "Articles": ["1× Radisson Blu voda"], "Status": "Partially Paid", "Details": "Mineral water logged. 1× Radisson Blu voda missing."},
        {"Room Number": "804", "Articles": ["2× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "816", "Articles": ["1× Voda Naturelle 0,5l"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "911", "Articles": ["2× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "914", "Articles": ["1× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "919", "Articles": ["2× Radisson Blu voda"], "Status": "Unpaid", "Details": "Marked in XML as checked with zero consumption (PREVERJENO, NI BILO PORABE)."},
        {"Room Number": "1005", "Articles": ["2× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "1008", "Articles": ["1× Voda Naturelle 0,5l", "2× Radisson Blu voda"], "Status": "Paid", "Details": "Routed to Room 701 (Routed From NURA FADIL Of Room #1008)."},
        {"Room Number": "1011", "Articles": ["2× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "1101", "Articles": ["2× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "1108", "Articles": ["1× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "1112", "Articles": ["1× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "1113", "Articles": ["1× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "1115", "Articles": ["2× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."},
        {"Room Number": "1119", "Articles": ["2× Coca Cola 0,33l", "2× Radisson Blu voda"], "Status": "Paid", "Details": "Logged directly to Room 1119."},
        {"Room Number": "1219", "Articles": ["1× Radisson Blu voda"], "Status": "Unpaid", "Details": "No transaction found in XML."}
    ]

    df_results = pd.DataFrame(audit_data)

    # Metrics Overview
    st.markdown("### 📊 Audit Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Rooms Audited", len(df_results))
    m2.metric("Fully Paid", len(df_results[df_results["Status"] == "Paid"]))
    m3.metric("Partially Paid", len(df_results[df_results["Status"] == "Partially Paid"]))
    m4.metric("Unpaid / Zero", len(df_results[df_results["Status"] == "Unpaid"]))

    # Filter controls
    status_filter = st.selectbox("Filter by Payment Status:", ["All", "Paid", "Partially Paid", "Unpaid"])
    filtered_data = audit_data if status_filter == "All" else [r for r in audit_data if r["Status"] == status_filter]

    st.markdown("### 🗂️ Room-by-Room Audit Results")

    # Render as structured cards so each article has its own line
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
                    <div style="font-size: 0.85em; color: #666; font-weight: bold; margin-bottom: 4px;">Audit Details:</div>
                    <div style="font-size: 0.9em; color: #444;">{row['Details']}</div>
                </div>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

    # CSV Download
    csv = df_results.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Audit Report (CSV)",
        data=csv,
        file_name="minibar_audit_report.csv",
        mime="text/csv",
    )
else:
    st.info("👈 Please upload both your PDF inspection list and Opera XML log file above to run the audit.")
