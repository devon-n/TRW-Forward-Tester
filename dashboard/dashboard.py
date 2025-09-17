import pandas as pd
import streamlit as st

from helpers import calculate_profit, truncate_name
from dotenv import load_dotenv
from pymongo import MongoClient # type: ignore
import os

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import minQtyDict, precisionDecimalDict


load_dotenv()

st.set_page_config(layout='wide')

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_data_from_mongodb():
    print('\nGetting data from DB...\n')
    mongo_client = MongoClient(os.getenv('MONGO_URI'))
    db = mongo_client.trading
    trades_collection = db.trades
    trades = list(trades_collection.find({}))
    df = pd.DataFrame(trades)
    print('Data retrieved from MongoDB')
    return df


df = get_data_from_mongodb()
print('Saving CSV')
df.to_csv('test.csv', index=False)

if len(df) == 0:
    print("\n\nNo trades in database check webhook settings, network access for database, .env file and render environment variables are correct\n\n")
    sys.exit()

df['Time'] = pd.to_datetime(df['time'])
df['close'] = pd.to_numeric(df['close'])
df['order_price'] = pd.to_numeric(df['order_price'])
df['quantity'] = pd.to_numeric(df['quantity'])

# For minQtyDict check and update
df['symbol'] = df['symbol'].str.replace('.P', '')
df['symbol'] = df['symbol'].apply(lambda x: x + "T" if x.endswith("USD") else x)

# Apply minimum quantity check
df.loc[df['symbol'].isin(minQtyDict), 'quantity'] = df.loc[df['symbol'].isin(minQtyDict)].apply(
    lambda row: max(row['quantity'], float(minQtyDict[row['symbol']])), axis=1
)

# Apply precision decimal rounding
df.loc[df['symbol'].isin(precisionDecimalDict), 'quantity'] = df.loc[df['symbol'].isin(precisionDecimalDict)].apply(
    lambda row: round(row['quantity'], precisionDecimalDict[row['symbol']]), axis=1
)

strategy_balances = {}
df[['Rolling Asset', 'Rolling USD High', 'Rolling USD Low', 'Rolling Total USD High', 'Rolling Total USD Low']] = df.apply(
        lambda row: calculate_profit(row, strategy_balances), axis=1, result_type='expand'
    )

def get_aggregates(df):
    # Calculate total profit and trade count per strategy
    _strategy_aggregates = df.groupby('strategy_name').agg(
        Time=('Time', 'first'),
        Symbol=('symbol', 'last'),
        # timeframe=('timeframe', 'last'),
        total_profit_high=('Rolling Total USD High', 'last'),
        total_profit_low=('Rolling Total USD Low', 'last'),
        total_trades=('strategy_name', 'size')
    ).reset_index()

    _strategy_aggregates.columns = [
        'Strategy Name', 'Time', 'Symbol', 'Total Profit High', 'Total Profit Low', 'Total Trades'
    ]

    # Add layout config for charts
    _strategy_aggregates['strategy_name_truncate'] = _strategy_aggregates['Strategy Name'].apply(truncate_name)
    _strategy_aggregates['Color'] = _strategy_aggregates['Total Profit High'].apply(lambda x: '#ffaa00' if x > 0 else '#ffaa0088')
    _strategy_aggregates['Profit Status'] = _strategy_aggregates['Total Profit High'].apply(lambda x: 'Profitable' if x > 0 else 'Non-Profitable')

    return _strategy_aggregates



####### DASHBOARD #######

###### INPUTS ######

unique_strategy_names = sorted(df['strategy_name'].unique())

# Total symbols
total_symbols = df['symbol'].unique()
timeframes = df['timeframe'].unique() # This hasn't been added yet

# Calculate counts of paper and real strategies
num_paper = df[df['order_type'] == 'PAPER']['strategy_name'].nunique()
num_real = df[df['order_type'] != 'PAPER']['strategy_name'].nunique()
total_strategies = num_paper + num_real

# How many months each strategy is trading
df['trading_months'] = df.groupby('strategy_name')['Time'].transform(lambda x: (x.max() - x.min()).days / 30)

# Get all trading months
allMonths = [date.strftime('%b') for date in df['Time'].dt.to_period('M').unique()]


def reset_filters():
    st.session_state['select_strategies'] = unique_strategy_names
    st.session_state['month_picker'] = allMonths
    # st.session_state['date_slider'] = (
    #     df['Time'].iloc[0].to_pydatetime(),
    #     df['Time'].iloc[-1].to_pydatetime()
    # )
    st.session_state['min_months'] = 0
    st.session_state['min_trades'] = 0
    st.session_state['order_type_selector'] = 'All'
    st.session_state['profitable_selector'] = 'All'
    st.session_state['select_symbols'] = [*total_symbols]


select_all = st.sidebar.button("Reset Filters", on_click=reset_filters)

st.sidebar.write("## TIME FILTERS")
MONTHS = st.sidebar.multiselect(
    'What months do you want to view?',
    default=allMonths,
    options=allMonths,
    key='month_picker',
    label_visibility='collapsed'
)

MIN_MONTHS = st.sidebar.number_input(
    'Filter by Min Trading Months',
    min_value=0,
    max_value=int(df['trading_months'].max()),
    value=0,
    step=1,
    key="min_months"
)

NUM_TRADES = st.sidebar.number_input(
    'Filter by Min Trades',
    max_value=df['strategy_name'].value_counts().max(),
    key="min_trades"
)

st.sidebar.write("## Trade Types")
ORDER_TYPE = st.sidebar.radio("Filter by paper/real", options=['All', 'Paper', 'Real'], key='order_type_selector')

PROFITABLE = st.sidebar.radio("Filter by Profitable", options=['All', 'Profitable', 'Unprofitable'], key='profitable_selector')

st.sidebar.write("## STRATEGY SELECTION")
STRATEGY_NAME = st.sidebar.multiselect(
    'What strategies do you want to view?',
    options=unique_strategy_names,
    default=unique_strategy_names,
    key='select_strategies'
)

st.sidebar.write("## SYMBOL SELECTION")
SYMBOLS = st.sidebar.multiselect(
    "What symbols do you want to see?",
    options = total_symbols,
    default = total_symbols,
    key='select_symbols'
)

###### FILTERS ######
df_selection = df.query("strategy_name == @STRATEGY_NAME and symbol == @SYMBOLS")

df_selection = df_selection.groupby('strategy_name').filter(lambda x: len(x) >= NUM_TRADES)

if PROFITABLE == 'Profitable':
    df_selection = df_selection.groupby('strategy_name').filter(lambda x: x['Rolling Total USD High'].iloc[-1] > 0 and x['Rolling Total USD High'].iloc[-1] > x['Rolling Total USD High'].iloc[1])
elif PROFITABLE == 'Unprofitable':
    df_selection = df_selection.groupby('strategy_name').filter(lambda x: x['Rolling Total USD High'].iloc[-1] < 0)
elif PROFITABLE ==' All':
    df_selection = df_selection.groupby('strategy_name').filter(lambda x: x['Rolling Total USD High'].iloc[-1] >= 0 or x['Rolling Total USD High'].iloc[-1] <= 0)

if ORDER_TYPE == 'Paper':
    df_selection = df_selection.loc[df_selection['order_type'] == 'PAPER']
elif ORDER_TYPE == 'Real':
    df_selection = df_selection.loc[df_selection['order_type'] == 'REAL']
elif ORDER_TYPE == 'All':
    df_selection = df_selection[(df_selection['order_type'] == 'PAPER') | (df_selection['order_type'] != 'PAPER')]


###### Aggregates ######

# Get aggregate stats
strategy_aggregates = get_aggregates(df_selection)

# Get profit per trade and portfolio total value
df_selection['Profit Per Trade Low'] = df_selection.groupby('strategy_name')['Rolling Total USD Low'].diff()
df_selection['Profit Per Trade High'] = df_selection.groupby('strategy_name')['Rolling Total USD High'].diff()
df_selection['Cumulative Profit Low'] = df_selection['Profit Per Trade Low'].cumsum()
df_selection['Cumulative Profit High'] = df_selection['Profit Per Trade High'].cumsum()
df_selection = df_selection.groupby('strategy_name').filter(lambda x: x['trading_months'].iloc[0] >= MIN_MONTHS)

###### CHARTS ######
st.write('## Strategies over time')
st.write(f'#### Displaying {len(df_selection["strategy_name"].unique())} Strategies')
st.line_chart(df_selection, x='Time', y=['Cumulative Profit Low', 'Cumulative Profit High'])
st.line_chart(df_selection, x='Time', y='Rolling Total USD High', color='strategy_name')
st.write("## Total Trades")
st.bar_chart(strategy_aggregates, x='Strategy Name', y='Total Trades')
st.write("## Total Profit (High / Low Estimates)")
st.line_chart(strategy_aggregates, x='Strategy Name', y=['Total Profit High','Total Profit Low'])
