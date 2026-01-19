# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "streamlit",
#   "pandas",
#   "plotly",
# ]
# ///

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# =========================================================
# 1. CORE ENGINE
# =========================================================
SCENARIO_MODIFIERS = {
    "AS_IS":    {"vol": 1.0,  "fixed": 1.0, "cogs_adj": 0.0},
    "STRESS":   {"vol": 0.8,  "fixed": 1.1, "cogs_adj": 0.0},
    "BLUE_SKY": {"vol": 1.0,  "fixed": 1.0, "cogs_adj": -0.1},
    "REALITY":  {"vol": 0.75, "fixed": 1.0, "cogs_adj": 0.0}
}

def calculate_monthly_pnl(c, mods, s_index):
    max_vol = c['max_daily_capacity'] * c['operating_days']
    vol = max(0.0, min(max_vol * mods['vol'] * s_index, float(max_vol)))
    fixed = c['fixed_costs'] * mods['fixed']
    cogs_pct = c['cogs_base_pct'] + mods['cogs_adj']
    rev = vol * c['arpu_base']
    prof = rev - (fixed + (rev * cogs_pct))
    return {"vol": vol, "rev": rev, "prof": prof}

def process_state(prof, cash_bal, debt_rem, repay_pct):
    m_repay = 0.0
    if prof > 0 and debt_rem > 0:
        available_cash = cash_bal + prof
        if available_cash > 0:
            potential_repay = prof * repay_pct
            m_repay = max(0.0, min(potential_repay, debt_rem, available_cash))
    
    new_debt = debt_rem - m_repay
    new_cash = round(cash_bal + (prof - m_repay), 2)
    return m_repay, new_debt, new_cash

# =========================================================
# 2. STREAMLIT UI
# =========================================================
st.set_page_config(page_title="F&B ROI Calculator", layout="wide")

st.title("Interactive F&B ROI Simulator")
st.markdown("---")

# SIDEBAR
st.sidebar.header("1. Core Configuration")
config = {
    "capital": st.sidebar.number_input("Initial Capital (RM)", value=20000.0, step=1000.0),
    "fixed_costs": st.sidebar.number_input("Monthly Fixed Costs (RM)", value=4000.0, step=100.0),
    "max_daily_capacity": st.sidebar.slider("Max Daily Sales (Pax)", 10, 500, 100),
    "operating_days": st.sidebar.number_input("Operating Days/Month", value=26),
    "arpu_base": st.sidebar.number_input("Average Sales Per Customer (RM)", 5.0, 50.0, 8.90),
    "cogs_base_pct": st.sidebar.slider("COGS %", 0.1, 1.0, 0.5),
    "repayment_percentage": st.sidebar.slider("Repayment % (Take-home)", 0, 100, 100) / 100
}

st.sidebar.markdown("---")
st.sidebar.header("2. Seasonal Index (0 to 2)")
months_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
default_indices = [1.1, 1.1, 1.0, 0.7, 0.9, 1.2, 1.0, 1.0, 0.8, 0.9, 1.1, 1.2]

custom_seasonal_index = []
with st.sidebar.expander("Adjust Monthly Multipliers"):
    for i, month in enumerate(months_names):
        val = st.slider(f"{month} Index", 0.0, 2.0, default_indices[i], 0.1)
        custom_seasonal_index.append(val)

# SCENARIO TABS
st.header("Business Scenarios")
tabs = st.tabs([name.replace('_', ' ') for name in SCENARIO_MODIFIERS.keys()])

for i, (name, mods) in enumerate(SCENARIO_MODIFIERS.items()):
    with tabs[i]:
        debt, cash = config['capital'], 0.0
        history = []
        
        for m in range(1, 13):
            s_idx = custom_seasonal_index[(m-1) % 12]
            pnl = calculate_monthly_pnl(config, mods, s_idx)
            m_repay, debt, cash = process_state(pnl['prof'], cash, debt, config['repayment_percentage'])
            
            history.append({
                "Month": months_names[m-1], 
                "Sales (Pax)": int(pnl['vol']), 
                "Revenue": pnl['rev'], 
                "Net Profit": pnl['prof'], 
                "Monthly Repay": m_repay, 
                "Total Repaid": config['capital'] - debt, 
                "Cash in Hand": cash
            })
        
        df = pd.DataFrame(history)

        # ROI CALCULATION
        roi_m = "UNVIABLE"
        rd, rc = config['capital'], 0.0
        for m_long in range(1, 241):
            s_long = custom_seasonal_index[(m_long-1) % 12]
            pnl_l = calculate_monthly_pnl(config, mods, s_long)
            mr_l, rd, rc = process_state(pnl_l['prof'], rc, rd, config['repayment_percentage'])
            if rd <= 0:
                roi_m = f"{m_long} Months"
                break

        # METRICS
        m1, m2, m3 = st.columns(3)
        m1.metric("Year 1 Cash Balance", f"RM {cash:,.2f}")
        m2.metric("Capital Recovered", f"RM {config['capital']-debt:,.2f}")
        m3.metric("Payback Period", roi_m)

        st.markdown("---")
        
        # FIXED CHART SECTION
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Monthly Collections (Revenue vs Profit)")
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df["Month"], y=df["Revenue"], name="Revenue", marker_color="#3366CC"))
            fig_bar.add_trace(go.Bar(x=df["Month"], y=df["Net Profit"], name="Net Profit", marker_color="#109618"))
            fig_bar.update_layout(
                barmode='group', 
                height=400, 
                xaxis={'categoryorder':'trace'}, # Preserves chronological order
                margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with c2:
            st.subheader("Cash vs Capital Recovery")
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(x=df["Month"], y=df["Cash in Hand"], name="Cash in Hand", mode='lines+markers', line=dict(color='#FF9900', width=3)))
            fig_line.add_trace(go.Scatter(x=df["Month"], y=df["Total Repaid"], name="Total Repaid", mode='lines+markers', line=dict(color='#DC3912', width=3, dash='dash')))
            fig_line.update_layout(
                height=400,
                xaxis={'categoryorder':'trace'}, # Crucial for keeping Jan -> Dec
                margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified"
            )
            st.plotly_chart(fig_line, use_container_width=True)

        # DATA TABLE
        st.subheader("Monthly Detail")
        def color_negative_red(val):
            return 'color: red' if val < 0 else 'color: white'

        st.dataframe(
            df.style.format(precision=2, subset=["Revenue", "Net Profit", "Monthly Repay", "Total Repaid", "Cash in Hand"])
            .applymap(color_negative_red, subset=['Net Profit', 'Cash in Hand']),
            use_container_width=True
        )