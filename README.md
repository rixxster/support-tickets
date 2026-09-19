# 🎫 Support tickets template

A simple Streamlit app showing an internal tool that lets you create, manage, and visualize support tickets. 

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://support-tickets-template.streamlit.app/)

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```

### Accounts

The first account is the administrator. For local development, sign in with
`admin` / `admin`. Set `SUPPORT_ADMIN_PASSWORD` to choose a different initial
admin password before deployment. Administrators can add, modify, and remove
accounts from the **Accounts** view. Accounts are stored in the current
Streamlit session, so use a database-backed store if account changes must
survive app restarts or be shared across processes.
