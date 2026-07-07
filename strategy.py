import pandas as pd

def calculate_zones(df):
    df['high_roll'] = df['high'].rolling(window=10).max()
    df['low_roll'] = df['low'].rolling(window=10).min()

    resistance = df['high_roll'].iloc[-1]
    support = df['low_roll'].iloc[-1]

    return support, resistance


def generate_signal(df):
    support, resistance = calculate_zones(df)
    current_price = df['close'].iloc[-1]

    # Basic logic
    if current_price <= support:
        return "BUY", support, resistance

    elif current_price >= resistance:
        return "SELL", support, resistance

    return None, support, resistance
