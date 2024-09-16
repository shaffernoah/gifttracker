import pandas as pd

def process_gift_data(gifts):
    # Convert gifts to DataFrame if it's not already
    if not isinstance(gifts, pd.DataFrame):
        df = pd.DataFrame(gifts, columns=['id', 'giver', 'gift_details', 'date_received', 'cost', 'category', 'thank_you_sent'])
    else:
        df = gifts
    
    # Calculate summary statistics
    total_gifts = len(df)
    total_givers = df['giver'].nunique()
    total_value = df['cost'].sum()
    
    # Process gifts by date
    df['date_received'] = pd.to_datetime(df['date_received'])
    gifts_by_date = df.groupby('date_received').size()
    
    return total_gifts, total_givers, total_value, gifts_by_date
