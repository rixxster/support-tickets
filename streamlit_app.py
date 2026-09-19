import datetime
import hashlib
import hmac
import os
import random

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Support tickets", page_icon="🎫")


def hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 120_000
    ).hex()
    return f"{salt}${digest}"


def password_matches(password, stored_hash):
    salt, expected_digest = stored_hash.split("$", 1)
    actual_digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 120_000
    ).hex()
    return hmac.compare_digest(actual_digest, expected_digest)


def initialise_accounts():
    if "accounts" not in st.session_state:
        admin_password = os.getenv("SUPPORT_ADMIN_PASSWORD", "admin")
        st.session_state.accounts = {
            "admin": {"password": hash_password(admin_password), "role": "admin"}
        }


def render_login():
    st.title("🎫 Support tickets")
    st.subheader("Sign in")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")

    if submitted:
        account = st.session_state.accounts.get(username.strip())
        if account and password_matches(password, account["password"]):
            st.session_state.current_user = username.strip()
            st.rerun()
        st.error("Invalid username or password.")

    if os.getenv("SUPPORT_ADMIN_PASSWORD") is None:
        st.caption("First-run admin: admin / admin. Set SUPPORT_ADMIN_PASSWORD before deployment.")


def render_account_admin():
    st.header("Account administration")
    accounts = st.session_state.accounts

    with st.form("add_account_form"):
        st.subheader("Add account")
        new_username = st.text_input("Username", key="new_username")
        new_password = st.text_input("Password", type="password", key="new_password")
        new_role = st.selectbox("Role", ["agent", "admin"], key="new_role")
        add_account = st.form_submit_button("Add account", type="primary")

    if add_account:
        username = new_username.strip()
        if not username or not new_password:
            st.error("Username and password are required.")
        elif username in accounts:
            st.error("That username already exists.")
        else:
            accounts[username] = {"password": hash_password(new_password), "role": new_role}
            st.success(f"Account '{username}' added.")
            st.rerun()

    st.subheader("Modify or remove accounts")
    for username, account in list(accounts.items()):
        with st.expander(f"{username} ({account['role']})"):
            with st.form(f"edit_account_{username}"):
                role = st.selectbox(
                    "Role", ["agent", "admin"], index=["agent", "admin"].index(account["role"]),
                    key=f"role_{username}",
                )
                replacement_password = st.text_input(
                    "New password (leave blank to keep current)",
                    type="password",
                    key=f"password_{username}",
                )
                save_account = st.form_submit_button("Save changes")
                remove_account = st.form_submit_button("Remove account")

            if save_account:
                account["role"] = role
                if replacement_password:
                    account["password"] = hash_password(replacement_password)
                st.success(f"Account '{username}' updated.")
                st.rerun()
            if remove_account:
                if username == st.session_state.current_user:
                    st.error("You cannot remove the account you are currently using.")
                elif len(accounts) == 1:
                    st.error("At least one account must remain.")
                else:
                    del accounts[username]
                    st.success(f"Account '{username}' removed.")
                    st.rerun()


def initialise_tickets():
    if "df" in st.session_state:
        return
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
    st.session_state.df = pd.DataFrame({
        "ID": [f"TICKET-{i}" for i in range(1100, 1000, -1)],
        "Issue": np.random.choice(issue_descriptions, size=100),
        "Status": np.random.choice(["Open", "In Progress", "Closed"], size=100),
        "Priority": np.random.choice(["High", "Medium", "Low"], size=100),
        "Date Submitted": [datetime.date(2023, 6, 1) + datetime.timedelta(days=random.randint(0, 182)) for _ in range(100)],
    })


def render_tickets():
    st.title("🎫 Support tickets")
    st.write("Create, manage, and visualize internal support tickets.")
    st.header("Add a ticket")
    with st.form("add_ticket_form"):
        issue = st.text_area("Describe the issue")
        priority = st.selectbox("Priority", ["High", "Medium", "Low"])
        submitted = st.form_submit_button("Submit")
    if submitted:
        recent_ticket_number = int(max(st.session_state.df.ID).split("-")[1])
        df_new = pd.DataFrame([{
            "ID": f"TICKET-{recent_ticket_number + 1}", "Issue": issue,
            "Status": "Open", "Priority": priority,
            "Date Submitted": datetime.datetime.now().strftime("%m-%d-%Y"),
        }])
        st.success("Ticket submitted!")
        st.dataframe(df_new, use_container_width=True, hide_index=True)
        st.session_state.df = pd.concat([df_new, st.session_state.df], axis=0)

    st.header("Existing tickets")
    st.write(f"Number of tickets: `{len(st.session_state.df)}`")
    edited_df = st.data_editor(
        st.session_state.df, use_container_width=True, hide_index=True,
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=["Open", "In Progress", "Closed"], required=True),
            "Priority": st.column_config.SelectboxColumn("Priority", options=["High", "Medium", "Low"], required=True),
        }, disabled=["ID", "Date Submitted"],
    )
    st.session_state.df = edited_df
    st.header("Statistics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Number of open tickets", len(edited_df[edited_df.Status == "Open"]), delta=10)
    col2.metric("First response time (hours)", 5.2, delta=-1.5)
    col3.metric("Average resolution time (hours)", 16, delta=2)
    status_plot = alt.Chart(edited_df).mark_bar().encode(
        x="month(Date Submitted):O", y="count():Q", xOffset="Status:N", color="Status:N"
    ).configure_legend(orient="bottom", titleFontSize=14, labelFontSize=14, titlePadding=5)
    st.altair_chart(status_plot, use_container_width=True, theme="streamlit")
    priority_plot = alt.Chart(edited_df).mark_arc().encode(
        theta="count():Q", color="Priority:N"
    ).properties(height=300).configure_legend(orient="bottom", titleFontSize=14, labelFontSize=14, titlePadding=5)
    st.altair_chart(priority_plot, use_container_width=True, theme="streamlit")


initialise_accounts()
if "current_user" not in st.session_state:
    render_login()
    st.stop()

current_user = st.session_state.current_user
account = st.session_state.accounts.get(current_user)
if account is None:
    del st.session_state.current_user
    st.rerun()

with st.sidebar:
    st.write(f"Signed in as **{current_user}** ({account['role']})")
    if st.button("Sign out"):
        del st.session_state.current_user
        st.rerun()
    view = st.radio("View", ["Tickets", "Accounts"] if account["role"] == "admin" else ["Tickets"])

if view == "Accounts":
    render_account_admin()
else:
    initialise_tickets()
    render_tickets()
