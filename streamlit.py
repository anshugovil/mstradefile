#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAFRA Dual Transformer - Streamlit Web Application
Enhanced with Excel Password Support and Custom Mapping Files
"""

import streamlit as st
import pandas as pd
import sys
import re
import calendar
from pathlib import Path
from datetime import datetime, date, timedelta
import warnings
import io
import base64
warnings.filterwarnings('ignore')

# For Excel password support
try:
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False

try:
    import xlrd
    XLS_SUPPORT = True
except ImportError:
    XLS_SUPPORT = False

try:
    import msoffcrypto
    MSOFFCRYPTO_SUPPORT = True
except ImportError:
    MSOFFCRYPTO_SUPPORT = False

# Hardcoded password
EXCEL_PASSWORD = "Aurigin2024"

# Page config
st.set_page_config(
    page_title="WAFRA Dual Transformer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
    }
    .success-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------- Hardcoded headers ----------------
OPTIONS_HEADERS = [
    "Trade_ID","Portfolio","Broker","Custodian","Strategy","Fund Class","Transaction","Status",
    "SecurityType","Security","Exchange","Counterparty","CP Ref Id","RED Code","Seniority","Doc Clause",
    "Sedol","ISIN","Cusip","Bberg  Code","Underlying ISIN","Description","Underlying","Underlying Description",
    "Order_Quantity","Order_Price","Yield_Price","Trade_Currency","Settlement_Currency","Strike_Price",
    "Option_Indicator","Exercise_Type","Option Type","Buy_Currency","Buy_Quantity","Sell_Currency","Sell_Quantity",
    "Trade_Date","Settle_Date","Principal","Total_Fees","Total_Commission","Net_Amount_Trade","Net_Amount_Settle",
    "Accrued_Interest","Expense","Expense_Type","Maturity_Date","FX_Rate","Contract Size","Issue Country",
    "Instrument Currency","Swap - Effective Date","Swap - Maturity Date","Accrual Start Date",
    "PAY Leg","PAY Leg Currency","PAY Leg Coupon Rate","PAY Leg Spread","PAY Leg First Coupon Date",
    "PAY Leg Coupon Frequency","PAY Leg Day Count","PAY Leg First Reset Date","PAY Leg Rate Reset Frequency",
    "REC Leg","REC Leg Currency","REC Leg Coupon Rate","REC Leg Spread","REC Leg First Coupon Date",
    "REC Leg Coupon Frequency","Rec Leg Day Count","REC Leg First Reset Date","REC Leg Rate Reset Frequency",
    "LXID","Facility Coupon Frequency","Facilty Coupon Rate","Issuer","Tranche","Global Amount","Contract Amount",
    "Contract Frequency","Contract Rate"
]

FUTURES_HEADERS = OPTIONS_HEADERS[:]

# Session state initialization
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'futures_mapping' not in st.session_state:
    st.session_state.futures_mapping = None
if 'index_mapping' not in st.session_state:
    st.session_state.index_mapping = None
if 'mapping_loaded' not in st.session_state:
    st.session_state.mapping_loaded = False

# ---------------- Excel Reading Functions ----------------
@st.cache_data
def read_excel_with_password(file_content, file_name, password=EXCEL_PASSWORD):
    """Read password-protected Excel file"""
    file_ext = Path(file_name).suffix.lower()
    
    if file_ext == '.xlsx':
        if not EXCEL_SUPPORT:
            st.error("openpyxl is required for .xlsx files. Install with: pip install openpyxl")
            return None
        
        # Try multiple approaches
        approaches = []
        
        # Method 1: msoffcrypto
        if MSOFFCRYPTO_SUPPORT:
            approaches.append(lambda: _read_xlsx_msoffcrypto(file_content, password))
        
        # Method 2: Direct pandas with password
        approaches.append(lambda: pd.read_excel(io.BytesIO(file_content), engine='openpyxl', password=password))
        
        # Method 3: Without password
        approaches.append(lambda: pd.read_excel(io.BytesIO(file_content), engine='openpyxl'))
        
        for i, approach in enumerate(approaches, 1):
            try:
                df = approach()
                return df
            except Exception as e:
                continue
        
        st.error("Failed to read Excel file. Please check if the file is corrupted or password protected.")
        return None
    
    elif file_ext == '.xls':
        if not XLS_SUPPORT:
            st.error("xlrd is required for .xls files. Install with: pip install xlrd")
            return None
        
        try:
            df = pd.read_excel(io.BytesIO(file_content), engine='xlrd')
            return df
        except Exception as e:
            st.error(f"Failed to read .xls file: {e}")
            return None
    
    else:
        st.error(f"Unsupported Excel format: {file_ext}")
        return None

def _read_xlsx_msoffcrypto(file_content, password):
    """Use msoffcrypto-tool to decrypt password-protected Excel files"""
    import msoffcrypto
    from io import BytesIO
    
    # Create file-like object from content
    encrypted_file = BytesIO(file_content)
    office_file = msoffcrypto.OfficeFile(encrypted_file)
    
    # Decrypt with password
    office_file.load_key(password=password)
    
    # Decrypt to memory
    decrypted = BytesIO()
    office_file.decrypt(decrypted)
    decrypted.seek(0)
    
    # Read decrypted content with pandas
    df = pd.read_excel(decrypted, engine='openpyxl')
    return df

# ---------------- Helper Functions ----------------
def _normalize(name: str) -> str:
    return ''.join(ch for ch in name.lower() if ch.isalnum())

def _parse_to_dt(exp_str: str):
    s = str(exp_str).strip().replace(".", "/").replace("-", "/")
    fmts = ["%d/%m/%Y","%d/%m/%y","%m/%d/%Y","%m/%d/%y","%Y/%m/%d","%Y/%d/%m"]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.isna(dt): return None
        return dt.to_pydatetime()
    except Exception:
        return None

def _mmddyy(exp: str) -> str:
    dt = _parse_to_dt(exp)
    return dt.strftime("%m/%d/%y") if dt else ""

def _ddMMMyyyy(exp: str) -> str:
    dt = _parse_to_dt(exp)
    return dt.strftime("%d%b%Y") if dt else str(exp)

def _yyyymmdd(exp: str) -> str:
    dt = _parse_to_dt(exp)
    return dt.strftime("%Y%m%d") if dt else ""

MONTH_CODE = {1:"F",2:"G",3:"H",4:"J",5:"K",6:"M",7:"N",8:"Q",9:"U",10:"V",11:"X",12:"Z"}

def _fut_code(exp: str):
    dt = _parse_to_dt(exp)
    if not dt: return None, None
    return MONTH_CODE.get(dt.month), str(dt.year)[-1]

def _month_weekday_dates(dt_obj, target_wd: int):
    first_day = date(dt_obj.year, dt_obj.month, 1)
    _, ndays = calendar.monthrange(dt_obj.year, dt_obj.month)
    days = [first_day + timedelta(days=i) for i in range(ndays)]
    return [d for d in days if d.weekday() == target_wd]

def _nearest_in_month(dt_obj, candidates):
    d0 = dt_obj.date()
    best = None
    best_key = None
    for d in candidates:
        delta = abs((d - d0).days)
        key = (delta, d)
        if best is None or key < best_key:
            best = d
            best_key = key
    return best

def _nifty_weekly_suffix(exp_dt):
    cutoff = date(2025, 9, 1)
    target_wd = 3 if exp_dt.date() < cutoff else 1
    targets = _month_weekday_dates(exp_dt, target_wd)
    if not targets: return ""
    nearest = _nearest_in_month(exp_dt, targets)
    if nearest == targets[-1]:
        return ""
    ordinal = targets.index(nearest) + 1
    total = len(targets)
    if ordinal == 1: return "C"
    if ordinal == 2: return "D"
    if ordinal == 3: return "E"
    if ordinal == 4 and total >= 5: return "F"
    return ""

def _col_by_pos(d, i): 
    return list(d.columns)[i] if i < len(d.columns) else None

# ---------------- Processing Functions ----------------
def build_options(df, fmap, idx_map, trade_date):
    instr_col  = _col_by_pos(df, 4)
    symbol_col = _col_by_pos(df, 5)
    expiry_col = _col_by_pos(df, 6)
    strike_col = _col_by_pos(df, 8)
    opttype_col= _col_by_pos(df, 9)
    side_col   = _col_by_pos(df, 10)
    tmname_col = _col_by_pos(df, 3)
    qty_col    = _col_by_pos(df, 12)
    price_col  = _col_by_pos(df, 13)
    lot_col    = _col_by_pos(df, 7)

    out = pd.DataFrame(index=range(len(df)), columns=OPTIONS_HEADERS, dtype=object)
    out[:] = ""

    instr = df[instr_col].astype(str).str.upper()
    sym   = df[symbol_col].astype(str).str.upper()
    exp   = df[expiry_col].astype(str)
    strike= df[strike_col].astype(str).str.replace(",","", regex=False)
    opttp = df[opttype_col].astype(str).str.upper().str.strip()
    side  = df[side_col].astype(str).str.upper().str.strip()
    tm    = df[tmname_col].astype(str)
    qty   = df[qty_col].astype(str) if qty_col else pd.Series([""]*len(df))
    price = df[price_col].astype(str) if price_col else pd.Series([""]*len(df))
    lot = df[lot_col].astype(str).str.replace(",", "", regex=False).str.strip() if lot_col else pd.Series([""]*len(df))

    def _cp_letter(s):
        s = str(s).upper().strip()
        if s in ("C","CE","CALL","CALLS") or s.startswith("C"): return "C"
        if s in ("P","PE","PUT","PUTS") or s.startswith("P") or "PE" in s: return "P"
        return ""

    # Build security + type
    security_vals = []
    sectype_vals = []
    for i in range(len(df)):
        i_instr = instr.iat[i]
        i_sym = sym.iat[i]
        i_exp = exp.iat[i]
        i_strk = strike.iat[i]
        cp = _cp_letter(opttp.iat[i])
        exp_fmt = _mmddyy(i_exp)
        
        if i_instr == "OPTSTK":
            ticker = fmap.get(i_sym, "UPDATE")
            sectype_vals.append("EQYOPTION")
            sec = f"{ticker} IS {exp_fmt} {cp}{i_strk} Equity" if ticker != "UPDATE" and exp_fmt and cp and i_strk else "UPDATE"
        else:
            idx_ticker = idx_map.get(i_sym, "")
            if idx_ticker == "NIFTY":
                dt = _parse_to_dt(i_exp)
                suffix = _nifty_weekly_suffix(dt) if dt else ""
                idx_ticker = f"{idx_ticker}{suffix}"
            sectype_vals.append("IDXOPTION")
            sec = f"{idx_ticker} {exp_fmt} {cp}{i_strk} Index" if idx_ticker and exp_fmt and cp and i_strk else "UPDATE"
        security_vals.append(sec)

    transaction = ["BUY" if s.startswith("B") else "SELL" for s in side.tolist()]
    strategy = ["FUSH" if (s.startswith("B") and t in ("PE","P")) or (s.startswith("S") and t in ("CE","C")) else "FULO"
                for s,t in zip(side.tolist(), opttp.tolist())]

    # Constants & required fields
    CONST = {
        "Portfolio":"Wafra","Custodian":"MSI","Exchange":"IS","Fund Class":"Default","Status":"NEW",
        "CP Ref Id":"0","Seniority":"0","Trade_Currency":"INR","Settlement_Currency":"INR",
        "Yield_Price":"0","Principal":"0","Total_Fees":"FILL FROM BROKER SHEET","Total_Commission":"FILL FROM BROKER SHEET",
        "Accrued_Interest":"0","Expense":"0","Expense_Type":"0","FX_Rate":"1","Issue Country":"India","Instrument Currency":"INR"
    }
    for k,v in CONST.items():
        if k in out.columns: out[k]=v

    # Direct fills
    if "Broker" in out.columns: out["Broker"] = tm
    if "Counterparty" in out.columns: out["Counterparty"] = tm
    if "SecurityType" in out.columns: out["SecurityType"] = sectype_vals
    for c in ["Security","Bberg  Code"]:
        if c in out.columns: out[c] = security_vals
    if "Strategy" in out.columns: out["Strategy"] = strategy
    if "Transaction" in out.columns: out["Transaction"] = transaction
    if "Order_Quantity" in out.columns and len(qty): out["Order_Quantity"] = qty
    if "Order_Price" in out.columns and len(price): out["Order_Price"] = price
    if "Strike_Price" in out.columns: out["Strike_Price"] = strike
    if "Option Type" in out.columns: out["Option Type"] = opttp
    if "Trade_Date" in out.columns: out["Trade_Date"] = trade_date
    if "Settle_Date" in out.columns: out["Settle_Date"] = trade_date
    if "Maturity_Date" in out.columns: out["Maturity_Date"] = exp.apply(_yyyymmdd)
    if "Contract Size" in out.columns and len(lot): out["Contract Size"] = lot

    # Description
    def _cp_word(s):
        s = str(s).upper().strip()
        if s in ("C","CE","CALL","CALLS") or s.startswith("C"): return "Call"
        if s in ("P","PE","PUT","PUTS") or s.startswith("P") or "PE" in s: return "Put"
        return ""
    
    desc_vals = []
    for i in range(len(df)):
        i_instr = instr.iat[i]
        i_sym = sym.iat[i]
        tick = fmap.get(i_sym, "").upper() if i_instr=="OPTSTK" else idx_map.get(i_sym, "").upper()
        date_txt = _ddMMMyyyy(exp.iat[i])
        cpw = _cp_word(opttp.iat[i])
        k = strike.iat[i]
        parts_ok = [p for p in [tick, date_txt, k, cpw, "Listed"] if str(p).strip()!=""]
        desc_vals.append(" ".join(parts_ok))
    if "Description" in out.columns: out["Description"] = desc_vals

    # Buy/Sell split quantities/currencies
    if "Buy_Currency" in out.columns: out["Buy_Currency"] = "INR"
    if "Sell_Currency" in out.columns: out["Sell_Currency"] = "INR"
    if "Buy_Quantity" in out.columns:
        out["Buy_Quantity"] = [q if s.startswith("B") else "0" for q,s in zip(qty.tolist(), side.tolist())]
    if "Sell_Quantity" in out.columns:
        out["Sell_Quantity"] = [q if s.startswith("S") else "0" for q,s in zip(qty.tolist(), side.tolist())]

    return out

def build_futures(df, fmap, trade_date):
    instr_col  = _col_by_pos(df, 4)
    symbol_col = _col_by_pos(df, 5)
    expiry_col = _col_by_pos(df, 6)
    side_col   = _col_by_pos(df, 10)
    tmname_col = _col_by_pos(df, 3)
    qty_col = _col_by_pos(df, 12)
    price_col = _col_by_pos(df, 13)
    lot_col    = _col_by_pos(df, 7)

    out = pd.DataFrame(index=range(len(df)), columns=FUTURES_HEADERS, dtype=object)
    out[:] = ""

    instr = df[instr_col].astype(str).str.upper()
    sym   = df[symbol_col].astype(str).str.upper()
    exp   = df[expiry_col].astype(str)
    side  = df[side_col].astype(str).str.upper().str.strip()
    tm    = df[tmname_col].astype(str)
    qty   = df[qty_col].astype(str) if qty_col else pd.Series([""]*len(df))
    price = df[price_col].astype(str) if price_col else pd.Series([""]*len(df))
    lot = df[lot_col].astype(str).str.replace(",", "", regex=False).str.strip() if lot_col else pd.Series([""]*len(df))

    # Security + type
    security_vals = []
    sectype_vals = []
    for i in range(len(df)):
        i_instr = instr.iat[i]
        i_sym = sym.iat[i]
        i_exp = exp.iat[i]
        mcode, ycode = _fut_code(i_exp)
        ticker = fmap.get(i_sym, "UPDATE")
        if i_instr == "FUTSTK":
            sec = f"{ticker}={mcode}{ycode} IS Equity" if ticker != "UPDATE" and mcode and ycode else "UPDATE"
            stype = "EQFUT"
        else:
            sec = f"{ticker}{mcode}{ycode} Index" if ticker != "UPDATE" and mcode and ycode else "UPDATE"
            stype = "IDXFUT"
        security_vals.append(sec)
        sectype_vals.append(stype)

    transaction = ["BUY" if s.startswith("B") else "SELL" for s in side.tolist()]
    strategy = ["FULO" if s.startswith("B") else "FUSH" for s in side.tolist()]

    # Constants & required fields
    CONST = {
        "Portfolio":"Wafra","Custodian":"MSI","Exchange":"IS","Fund Class":"Default","Status":"NEW",
        "CP Ref Id":"0","Seniority":"0","Trade_Currency":"INR","Settlement_Currency":"INR",
        "Yield_Price":"0","Principal":"0","Total_Fees":"FILL FROM BROKER SHEET","Total_Commission":"FILL FROM BROKER SHEET",
        "Accrued_Interest":"0","Expense":"0","Expense_Type":"0","FX_Rate":"1","Issue Country":"India","Instrument Currency":"INR",
        "Strike_Price":"0"
    }
    for k,v in CONST.items():
        if k in out.columns: out[k]=v

    # Fills
    if "Broker" in out.columns: out["Broker"] = tm
    if "Counterparty" in out.columns: out["Counterparty"] = tm
    if "SecurityType" in out.columns: out["SecurityType"] = "FUTURE"
    for c in ["Security","Bberg  Code"]:
        if c in out.columns: out[c] = security_vals
    if "Strategy" in out.columns: out["Strategy"] = strategy
    if "Transaction" in out.columns: out["Transaction"] = transaction
    if "Order_Quantity" in out.columns and len(qty): out["Order_Quantity"] = qty
    if "Order_Price" in out.columns and len(price): out["Order_Price"] = price
    if "Description" in out.columns:
        def _mmmyy(exp_str):
            dt = _parse_to_dt(exp_str)
            return dt.strftime("%b%y") if dt else str(exp_str)
        out["Description"] = [f"{sym.iat[i]} {_mmmyy(exp.iat[i])}" for i in range(len(df))]
    if "Trade_Date" in out.columns: out["Trade_Date"] = trade_date
    if "Settle_Date" in out.columns: out["Settle_Date"] = trade_date
    if "Maturity_Date" in out.columns: out["Maturity_Date"] = exp.apply(_yyyymmdd)
    if "Contract Size" in out.columns and len(lot): out["Contract Size"] = lot

    # Buy/Sell split quantities/currencies
    if "Buy_Currency" in out.columns: out["Buy_Currency"] = "INR"
    if "Sell_Currency" in out.columns: out["Sell_Currency"] = "INR"
    if "Buy_Quantity" in out.columns:
        out["Buy_Quantity"] = [q if s.startswith("B") else "0" for q,s in zip(qty.tolist(), side.tolist())]
    if "Sell_Quantity" in out.columns:
        out["Sell_Quantity"] = [q if s.startswith("S") else "0" for q,s in zip(qty.tolist(), side.tolist())]

    return out

# ---------------- Load Mapping Functions ----------------
@st.cache_data
def load_default_futures_mapping():
    """Load default futures mapping from GitHub repository"""
    try:
        # Update this URL to point to your GitHub repository
        url = "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/futures_mapping.csv"
        df = pd.read_csv(url, dtype=str).fillna("")
        
        # Check if the file is empty or has no valid mappings
        if df.empty or len(df.columns) < 2:
            # Return a default minimal mapping if file is empty
            return {
                "RELIANCE": "RELIANCE",
                "TCS": "TCS",
                "INFY": "INFY",
                "NIFTY": "NIFTY",
                "BANKNIFTY": "BANKNIFTY"
            }
        
        return process_futures_mapping(df)
    except Exception as e:
        # Return a default mapping if GitHub file can't be loaded
        st.warning(f"Using default mapping. GitHub file issue: {e}")
        return {
            "RELIANCE": "RELIANCE",
            "TCS": "TCS",
            "INFY": "INFY",
            "NIFTY": "NIFTY",
            "BANKNIFTY": "BANKNIFTY"
        }

def process_futures_mapping(df):
    """Process futures mapping dataframe into dictionary"""
    cols = list(df.columns)
    if len(cols) < 2:
        st.error("Futures mapping must have at least two columns (Symbol, Ticker)")
        return None
    
    sym_col, tic_col = cols[0], cols[1]
    mapping = {
        str(r[sym_col]).strip().upper(): str(r[tic_col]).strip().upper() or "UPDATE"
        for _, r in df.iterrows() if str(r[sym_col]).strip()
    }
    return mapping

def load_index_options_mapping():
    """Load index options mapping with defaults"""
    default = {"NIFTY":"NIFTY","NSEBANK":"NSEBANK","NMIDSELP":"NMIDSELP"}
    return default

# ---------------- Streamlit UI ----------------
def main():
    st.title("🔄 WAFRA Dual Transformer")
    st.markdown("**Enhanced Excel Transformation Tool with Password Support**")
    
    # Auto-load default mapping on first run
    if not st.session_state.mapping_loaded:
        default_mapping = load_default_futures_mapping()
        if default_mapping:
            st.session_state.futures_mapping = default_mapping
            st.session_state.mapping_loaded = True
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Configuration")
        
        # Mapping file selection
        st.subheader("Futures Mapping")
        
        # Show current mapping status
        if st.session_state.futures_mapping:
            st.success(f"✅ {len(st.session_state.futures_mapping)} mappings loaded")
        else:
            st.warning("⚠️ No mapping loaded")
        
        mapping_source = st.radio(
            "Mapping options:",
            ["Use default mapping", "Upload custom mapping file", "Reload from GitHub"]
        )
        
        if mapping_source == "Upload custom mapping file":
            custom_mapping = st.file_uploader(
                "Upload futures_mapping.csv",
                type=['csv'],
                help="CSV file with Symbol and Ticker columns"
            )
            if custom_mapping:
                try:
                    df = pd.read_csv(custom_mapping, dtype=str).fillna("")
                    mapping = process_futures_mapping(df)
                    if mapping:
                        st.session_state.futures_mapping = mapping
                        st.success("✅ Custom mapping loaded successfully")
                except Exception as e:
                    st.error(f"Error loading mapping: {e}")
        
        elif mapping_source == "Reload from GitHub":
            if st.button("🔄 Reload from GitHub"):
                mapping = load_default_futures_mapping()
                if mapping:
                    st.session_state.futures_mapping = mapping
                    st.success("✅ Mapping reloaded from GitHub")
                    st.rerun()
        
        # Display mapping info
        if st.session_state.futures_mapping:
            with st.expander("View Current Mappings"):
                mapping_df = pd.DataFrame(
                    list(st.session_state.futures_mapping.items()),
                    columns=["Symbol", "Ticker"]
                )
                st.dataframe(mapping_df, height=200)
        
        st.divider()
        
        # Trade date input
        st.subheader("📅 Trade Date")
        default_date = datetime.now()
        trade_date = st.date_input(
            "Select trade date:",
            value=default_date,
            format="YYYY-MM-DD"
        )
        trade_date_str = trade_date.strftime("%Y%m%d")
        
        st.divider()
        
        # Library status
        st.subheader("📚 Library Status")
        libs = {
            "openpyxl": EXCEL_SUPPORT,
            "xlrd": XLS_SUPPORT,
            "msoffcrypto": MSOFFCRYPTO_SUPPORT
        }
        for lib, status in libs.items():
            if status:
                st.success(f"✅ {lib}")
            else:
                st.warning(f"⚠️ {lib} not installed")
    
    # Main content area
    st.header("📤 Upload Data File")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a file (CSV or Excel)",
        type=['csv', 'xls', 'xlsx'],
        help="Supported formats: CSV, XLS, XLSX (password-protected files supported)"
    )
    
    if uploaded_file is not None:
        # Check if we have futures mapping
        if not st.session_state.futures_mapping:
            st.warning("⚠️ Please load a futures mapping file first (from sidebar)")
            return
        
        # Load index mapping
        st.session_state.index_mapping = load_index_options_mapping()
        
        # Process the file
        with st.spinner("Processing file..."):
            try:
                # Read file based on type
                file_ext = Path(uploaded_file.name).suffix.lower()
                
                if file_ext == '.csv':
                    df = pd.read_csv(uploaded_file, dtype=str).fillna("")
                else:
                    # Excel file
                    file_content = uploaded_file.read()
                    df = read_excel_with_password(file_content, uploaded_file.name)
                    if df is not None:
                        df = df.astype(str).fillna("")
                    else:
                        st.error("Failed to read Excel file")
                        return
                
                # Display file info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Rows", len(df))
                with col2:
                    st.metric("Total Columns", len(df.columns))
                with col3:
                    st.metric("File Type", file_ext.upper()[1:])
                
                # Preview data
                with st.expander("📊 Preview Input Data"):
                    st.dataframe(df.head(10), use_container_width=True)
                
                # Process data
                st.header("⚙️ Processing")
                
                # Get instrument column
                instr_col = list(df.columns)[4] if len(df.columns) > 4 else None
                if not instr_col:
                    st.error("Input file must have at least 5 columns")
                    return
                
                # Split into options and futures
                upp = df[instr_col].astype(str).str.upper()
                df_opts = df[upp.isin(["OPTSTK","OPTIDX"])].reset_index(drop=True)
                df_futs = df[upp.isin(["FUTSTK","FUTIDX"])].reset_index(drop=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"📈 Options: {len(df_opts)} rows")
                with col2:
                    st.info(f"📊 Futures: {len(df_futs)} rows")
                
                # Process button
                if st.button("🚀 Transform Data", type="primary"):
                    progress = st.progress(0)
                    status = st.empty()
                    
                    # Process options
                    status.text("Processing options...")
                    progress.progress(33)
                    out_opts = build_options(df_opts, st.session_state.futures_mapping, 
                                            st.session_state.index_mapping, trade_date_str) if len(df_opts) else pd.DataFrame(columns=OPTIONS_HEADERS)
                    
                    # Process futures
                    status.text("Processing futures...")
                    progress.progress(66)
                    out_futs = build_futures(df_futs, st.session_state.futures_mapping, 
                                           trade_date_str) if len(df_futs) else pd.DataFrame(columns=FUTURES_HEADERS)
                    
                    progress.progress(100)
                    status.text("Processing complete!")
                    
                    # Store in session state
                    st.session_state.processed_data = {
                        'options': out_opts,
                        'futures': out_futs
                    }
                    
                    st.success("✅ Processing complete!")
                
                # Display results if available
                if st.session_state.processed_data:
                    st.header("📥 Download Results")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if len(st.session_state.processed_data['options']) > 0:
                            st.subheader("Options Output")
                            
                            # Preview
                            with st.expander("Preview Options Data"):
                                st.dataframe(st.session_state.processed_data['options'].head(10), 
                                           use_container_width=True)
                            
                            # Download button
                            csv = st.session_state.processed_data['options'].to_csv(index=False).encode('utf-8-sig')
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            st.download_button(
                                label="📥 Download Options CSV",
                                data=csv,
                                file_name=f"wafra_option_trades_{timestamp}.csv",
                                mime="text/csv"
                            )
                        else:
                            st.info("No options data to download")
                    
                    with col2:
                        if len(st.session_state.processed_data['futures']) > 0:
                            st.subheader("Futures Output")
                            
                            # Preview
                            with st.expander("Preview Futures Data"):
                                st.dataframe(st.session_state.processed_data['futures'].head(10), 
                                           use_container_width=True)
                            
                            # Download button
                            csv = st.session_state.processed_data['futures'].to_csv(index=False).encode('utf-8-sig')
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            st.download_button(
                                label="📥 Download Futures CSV",
                                data=csv,
                                file_name=f"wafra_futures_trades_{timestamp}.csv",
                                mime="text/csv"
                            )
                        else:
                            st.info("No futures data to download")
            
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
                st.exception(e)
    
    # Footer
    st.divider()
    st.markdown("""
    ### 📝 Instructions:
    1. **Load Mapping**: Select or upload a futures mapping file from the sidebar
    2. **Set Trade Date**: Choose the trade date in the sidebar
    3. **Upload File**: Upload your CSV or Excel file (password-protected files supported)
    4. **Transform**: Click the Transform Data button
    5. **Download**: Download the processed Options and Futures files
    
    ### 🔐 Password Support:
    - Default password for Excel files: `Aurigin2024`
    - Supports both .xls and .xlsx formats
    
    ### 📋 Required Libraries:
    ```bash
    pip install streamlit pandas openpyxl xlrd msoffcrypto-tool
    ```
    """)

if __name__ == "__main__":
    main()
