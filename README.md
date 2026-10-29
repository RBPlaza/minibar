# Hotel Minibar Audit System

Automated audit tool to cross-reference Housekeeping PDF minibar inspection lists against Oracle Opera XML financial journal logs.

## 🚀 How to Deploy on Streamlit Community Cloud (Free)

1. **Create a GitHub Repository**:
   - Go to [GitHub](https://github.com) and create a new repository (e.g., `minibar-audit-app`).
   - Upload `app.py`, `requirements.txt`, and `README.md` into the main branch.

2. **Deploy on Streamlit**:
   - Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
   - Click **"New app"**.
   - Select your GitHub repository (`minibar-audit-app`) and set `app.py` as the main file path.
   - Click **"Deploy!"**.

## 📊 Features & Routing Rules
- **Automatic Item Standardisation**: Maps PDF titles (e.g., *Radisson Blu voda*) to Opera XML descriptors (*Minibar - Radisson voda*).
- **Movement (`=>`) & Routing Tracking**: Correctly accounts for items billed to group master rooms or moved between rooms.
- **Reversal Detection**: Recognizes `PREVERJENO, NI BILO PORABE` zero-consumption corrections.