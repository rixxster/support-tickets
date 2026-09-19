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
accounts from the **Accounts** view. Accounts and tickets are stored in
`support_tickets.db` using SQLite, so they survive app restarts. Set
`SUPPORT_DB_PATH` to use another database location.

Login is retained for 30 days with a signed browser cookie. Set
`SUPPORT_COOKIE_SECRET` to a long random value before deployment; changing it
logs all browsers out.

Administrators can manage customer accounts from the **Customers** view and
assign customers when creating or editing tickets. Existing databases are
upgraded automatically with the customer table and ticket relationship.
