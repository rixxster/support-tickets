import datetime
import hashlib
import hmac
import os
import random
import secrets
import sqlite3
from pathlib import Path

import altair as alt
import extra_streamlit_components as stx
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Support tickets", page_icon="🎫")
st.markdown(
    """
    <style>
        #MainMenu,
        footer,
        .stDeployButton,
        .stAppDeployButton,
        [data-testid="stFooter"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {
            display: none !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

DATABASE_PATH = Path(os.getenv("SUPPORT_DB_PATH", "support_tickets.db"))
COOKIE_NAME = "support_ticket_auth"
COOKIE_SECRET = os.getenv("SUPPORT_COOKIE_SECRET", "development-cookie-secret")
COOKIE_DAYS = 30


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return f"{salt}${digest}"


def password_matches(password, stored_hash):
    try:
        salt, expected_digest = stored_hash.split("$", 1)
    except ValueError:
        return False
    actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return hmac.compare_digest(actual_digest, expected_digest)


def initialise_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('agent', 'admin')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                issue TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('Open', 'In Progress', 'Closed')),
                priority TEXT NOT NULL CHECK (priority IN ('High', 'Medium', 'Low')),
                date_submitted TEXT NOT NULL,
                customer_id INTEGER REFERENCES customers(customer_id)
            );
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT ''
            );
            """
        )
        ticket_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tickets)")
        }
        if "customer_id" not in ticket_columns:
            connection.execute("ALTER TABLE tickets ADD COLUMN customer_id INTEGER REFERENCES customers(customer_id)")
        if connection.execute("SELECT 1 FROM customers LIMIT 1").fetchone() is None:
            connection.executemany(
                "INSERT INTO customers (name, email, company) VALUES (?, ?, ?)",
                [
                    ("Acme Corporation", "support@acme.example", "Acme Corporation"),
                    ("Northwind Traders", "it@northwind.example", "Northwind Traders"),
                    ("Contoso Ltd", "helpdesk@contoso.example", "Contoso Ltd"),
                ],
            )
        if connection.execute("SELECT 1 FROM accounts WHERE username = 'admin'").fetchone() is None:
            admin_password = os.getenv("SUPPORT_ADMIN_PASSWORD", "admin")
            connection.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, ?)",
                ("admin", hash_password(admin_password), "admin", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            )
        if connection.execute("SELECT 1 FROM tickets LIMIT 1").fetchone() is None:
            seed_tickets(connection)


def seed_tickets(connection):
    np.random.seed(42)
    issue_descriptions = [
        "Network connectivity issues in the office", "Software application crashing on startup",
        "Printer not responding to print commands", "Email server downtime", "Data backup failure",
        "Login authentication problems", "Website performance degradation", "Security vulnerability identified",
        "Hardware malfunction in the server room", "Employee unable to access shared files",
        "Database connection failure", "Mobile application not syncing data", "VoIP phone system issues",
        "VPN connection problems for remote employees", "System updates causing compatibility issues",
        "File server running out of storage space", "Intrusion detection system alerts",
        "Inventory management system errors", "Customer data not loading in CRM",
        "Collaboration tool not sending notifications",
    ]
    tickets = [
        (f"TICKET-{number}", np.random.choice(issue_descriptions),
         np.random.choice(["Open", "In Progress", "Closed"]),
         np.random.choice(["High", "Medium", "Low"]),
         str(datetime.date(2023, 6, 1) + datetime.timedelta(days=random.randint(0, 182))),
         None)
        for number in range(1100, 1000, -1)
    ]
    connection.executemany("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)", tickets)


def get_account(username):
    if not username:
        return None
    with get_connection() as connection:
        row = connection.execute(
            "SELECT username, password_hash, role FROM accounts WHERE username = ?", (username,)
        ).fetchone()
    return dict(row) if row else None


def get_accounts():
    with get_connection() as connection:
        rows = connection.execute("SELECT username, password_hash, role FROM accounts ORDER BY username").fetchall()
    return [dict(row) for row in rows]


def make_auth_cookie(username):
    signature = hmac.new(COOKIE_SECRET.encode(), username.encode(), hashlib.sha256).hexdigest()
    return f"{username}.{signature}"


def username_from_cookie(value):
    if not value or "." not in value:
        return None
    username, signature = value.rsplit(".", 1)
    expected = hmac.new(COOKIE_SECRET.encode(), username.encode(), hashlib.sha256).hexdigest()
    return username if username and hmac.compare_digest(signature, expected) else None


def restore_login(cookie_manager):
    username = st.session_state.get("current_user")
    if username:
        account = get_account(username)
        if account:
            return account
    username = username_from_cookie(cookie_manager.get(COOKIE_NAME))
    account = get_account(username)
    if account:
        st.session_state.current_user = account["username"]
    return account


def render_login(cookie_manager):
    st.title("🎫 Support tickets")
    st.subheader("Sign in")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        account = get_account(username.strip())
        if account and password_matches(password, account["password_hash"]):
            st.session_state.current_user = account["username"]
            cookie_manager.set(
                COOKIE_NAME, make_auth_cookie(account["username"]),
                expires_at=datetime.datetime.now() + datetime.timedelta(days=COOKIE_DAYS),
            )
            st.rerun()
        st.error("Invalid username or password.")
    if os.getenv("SUPPORT_ADMIN_PASSWORD") is None:
        st.caption("First-run admin: admin / admin. Set SUPPORT_ADMIN_PASSWORD before deployment.")


def add_account(username, password, role):
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO accounts VALUES (?, ?, ?, ?)",
            (username, hash_password(password), role, datetime.datetime.now(datetime.timezone.utc).isoformat()),
        )


def render_account_admin():
    st.header("Account administration")
    with st.form("add_account_form"):
        st.subheader("Add account")
        new_username = st.text_input("Username", key="new_username")
        new_password = st.text_input("Password", type="password", key="new_password")
        new_role = st.selectbox("Role", ["agent", "admin"], key="new_role")
        add_account_button = st.form_submit_button("Add account", type="primary")
    if add_account_button:
        username = new_username.strip()
        if not username or not new_password:
            st.error("Username and password are required.")
        else:
            try:
                add_account(username, new_password, new_role)
                st.success(f"Account '{username}' added.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("That username already exists.")

    st.subheader("Modify or remove accounts")
    for account in get_accounts():
        username = account["username"]
        with st.expander(f"{username} ({account['role']})"):
            with st.form(f"edit_account_{username}"):
                role = st.selectbox("Role", ["agent", "admin"], index=["agent", "admin"].index(account["role"]), key=f"role_{username}")
                replacement_password = st.text_input("New password (leave blank to keep current)", type="password", key=f"password_{username}")
                save_account = st.form_submit_button("Save changes")
                remove_account = st.form_submit_button("Remove account")
            if save_account:
                with get_connection() as connection:
                    if replacement_password:
                        connection.execute("UPDATE accounts SET role = ?, password_hash = ? WHERE username = ?", (role, hash_password(replacement_password), username))
                    else:
                        connection.execute("UPDATE accounts SET role = ? WHERE username = ?", (role, username))
                st.success(f"Account '{username}' updated.")
                st.rerun()
            if remove_account:
                if username == st.session_state.current_user:
                    st.error("You cannot remove the account you are currently using.")
                elif len(get_accounts()) == 1:
                    st.error("At least one account must remain.")
                else:
                    with get_connection() as connection:
                        connection.execute("DELETE FROM accounts WHERE username = ?", (username,))
                    st.success(f"Account '{username}' removed.")
                    st.rerun()


def get_customers():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT customer_id, name, email, company FROM customers ORDER BY name"
        ).fetchall()
    return [dict(row) for row in rows]


def render_customer_admin():
    st.header("Customer accounts")
    with st.form("add_customer_form"):
        st.subheader("Add customer")
        name = st.text_input("Customer name")
        email = st.text_input("Customer email")
        company = st.text_input("Company")
        add_customer = st.form_submit_button("Add customer", type="primary")
    if add_customer:
        if not name.strip() or not email.strip():
            st.error("Customer name and email are required.")
        else:
            try:
                with get_connection() as connection:
                    connection.execute(
                        "INSERT INTO customers (name, email, company) VALUES (?, ?, ?)",
                        (name.strip(), email.strip(), company.strip()),
                    )
                st.success(f"Customer '{name.strip()}' added.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("That customer name already exists.")

    st.subheader("Modify or remove customers")
    for customer in get_customers():
        customer_id = customer["customer_id"]
        with st.expander(f"{customer['name']} ({customer['email']})"):
            with st.form(f"edit_customer_{customer_id}"):
                edited_name = st.text_input("Customer name", value=customer["name"])
                edited_email = st.text_input("Customer email", value=customer["email"])
                edited_company = st.text_input("Company", value=customer["company"])
                save_customer = st.form_submit_button("Save changes")
                remove_customer = st.form_submit_button("Remove customer")
            if save_customer:
                try:
                    with get_connection() as connection:
                        connection.execute(
                            "UPDATE customers SET name = ?, email = ?, company = ? WHERE customer_id = ?",
                            (edited_name.strip(), edited_email.strip(), edited_company.strip(), customer_id),
                        )
                    st.success(f"Customer '{edited_name.strip()}' updated.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That customer name already exists.")
            if remove_customer:
                with get_connection() as connection:
                    ticket_count = connection.execute(
                        "SELECT COUNT(*) FROM tickets WHERE customer_id = ?", (customer_id,)
                    ).fetchone()[0]
                    if ticket_count:
                        st.error("This customer cannot be removed while tickets are linked to it.")
                    else:
                        connection.execute("DELETE FROM customers WHERE customer_id = ?", (customer_id,))
                        st.success(f"Customer '{customer['name']}' removed.")
                        st.rerun()


def get_tickets():
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT t.ticket_id AS ID, t.issue AS Issue, t.status AS Status,
                   t.priority AS Priority, t.date_submitted AS 'Date Submitted',
                   COALESCE(c.name, 'Unassigned') AS Customer
            FROM tickets t LEFT JOIN customers c ON c.customer_id = t.customer_id
            ORDER BY t.rowid DESC
            """,
            connection,
        )


def save_tickets(dataframe):
    with get_connection() as connection:
        customer_ids = {
            row["name"]: row["customer_id"]
            for row in connection.execute("SELECT customer_id, name FROM customers")
        }
        connection.executemany(
            "UPDATE tickets SET issue = ?, status = ?, priority = ?, date_submitted = ?, customer_id = ? WHERE ticket_id = ?",
            [
                (row["Issue"], row["Status"], row["Priority"], str(row["Date Submitted"]),
                 customer_ids.get(row["Customer"]), row["ID"])
                for _, row in dataframe.iterrows()
            ],
        )


def render_tickets(is_admin):
    st.title("🎫 Support tickets")
    st.write("Create, manage, and visualize internal support tickets.")
    tickets = get_tickets()
    customer_names = ["Unassigned"] + [customer["name"] for customer in get_customers()]
    st.header("Add a ticket")
    with st.form("add_ticket_form"):
        issue = st.text_area("Describe the issue")
        priority = st.selectbox("Priority", ["High", "Medium", "Low"])
        customer = st.selectbox("Customer", customer_names)
        submitted = st.form_submit_button("Submit")
    if submitted:
        recent_number = max(int(ticket_id.split("-")[1]) for ticket_id in tickets.ID)
        with get_connection() as connection:
            customer_id = connection.execute(
                "SELECT customer_id FROM customers WHERE name = ?", (customer,)
            ).fetchone()
            connection.execute(
                "INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)",
                (f"TICKET-{recent_number + 1}", issue, "Open", priority,
                 str(datetime.date.today()), customer_id[0] if customer_id else None),
            )
        st.success("Ticket submitted!")
        tickets = get_tickets()

    st.header("Existing tickets")
    st.write(f"Number of tickets: `{len(tickets)}`")
    if is_admin:
        st.info("As an administrator, you can edit ticket details directly in the table.")
    else:
        st.info("Ticket details are read-only. Contact an administrator to make changes.")
    edited_tickets = st.data_editor(
        tickets, use_container_width=True, hide_index=True,
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=["Open", "In Progress", "Closed"], required=True),
            "Priority": st.column_config.SelectboxColumn("Priority", options=["High", "Medium", "Low"], required=True),
            "Customer": st.column_config.SelectboxColumn("Customer", options=customer_names, required=True),
        },
        disabled=[] if is_admin else list(tickets.columns),
    )
    if is_admin:
        save_tickets(edited_tickets)
    st.header("Statistics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Number of open tickets", len(edited_tickets[edited_tickets.Status == "Open"]), delta=10)
    col2.metric("First response time (hours)", 5.2, delta=-1.5)
    col3.metric("Average resolution time (hours)", 16, delta=2)
    status_plot = alt.Chart(edited_tickets).mark_bar().encode(x="month(Date Submitted):O", y="count():Q", xOffset="Status:N", color="Status:N").configure_legend(orient="bottom", titleFontSize=14, labelFontSize=14, titlePadding=5)
    st.altair_chart(status_plot, use_container_width=True, theme="streamlit")
    priority_plot = alt.Chart(edited_tickets).mark_arc().encode(theta="count():Q", color="Priority:N").properties(height=300).configure_legend(orient="bottom", titleFontSize=14, labelFontSize=14, titlePadding=5)
    st.altair_chart(priority_plot, use_container_width=True, theme="streamlit")


initialise_database()
cookie_manager = stx.CookieManager()
account = restore_login(cookie_manager)
if account is None:
    render_login(cookie_manager)
    st.stop()

with st.sidebar:
    st.write(f"Signed in as **{account['username']}** ({account['role']})")
    if st.button("Sign out"):
        st.session_state.pop("current_user", None)
        cookie_manager.delete(COOKIE_NAME)
        st.rerun()
    view = st.radio(
        "View",
        ["Tickets", "Accounts", "Customers"] if account["role"] == "admin" else ["Tickets"],
    )

if view == "Accounts":
    render_account_admin()
elif view == "Customers":
    render_customer_admin()
else:
    render_tickets(account["role"] == "admin")
