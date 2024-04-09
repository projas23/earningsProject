from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from collections import defaultdict
from flask_caching import Cache
import os
import pandas as pd
import matplotlib.dates as mdates
import matplotlib  # Import matplotlib before setting the backend
matplotlib.use('Agg')  # Set the backend to 'Agg'
import matplotlib.pyplot as plt  # Now, it's safe to import pyplot
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
app = Flask(__name__, static_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:@localhost:3307/earningsDB'
db = SQLAlchemy(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/most-anticipated')
@cache.cached(timeout=86400)  # Cache for one day
def most_anticipated():
    query = text('''
    SELECT 
    ec.act_symbol,
    MIN(ec.date) AS earliest_earnings_date,
    MIN(`rs`.`rank`) AS `rank`, 
    MIN(rs.growth) AS growth
FROM 
    earnings_calendar ec
JOIN 
    rank_score rs ON ec.act_symbol = rs.act_symbol
WHERE 
    ec.date BETWEEN CURDATE() + INTERVAL 1 DAY AND CURDATE() + INTERVAL 7 DAY
GROUP BY 
    ec.act_symbol
ORDER BY 
    earliest_earnings_date ASC, MIN(rs.growth)
LIMIT 40;
    ''')
    with db.engine.connect() as connection:
        result = connection.execute(query)
        rows = result.fetchall()

    # Group rows by 'earliest_earnings_date'
    grouped_by_date = defaultdict(list)
    for row in rows:
        grouped_by_date[str(row.earliest_earnings_date)].append(row)

    if grouped_by_date:
        return render_template('most_anticipated.html', grouped_by_date=grouped_by_date)
    else:
        return 'No data found'
    
@app.route('/stock/<ticker>')
def stock_details(ticker):
    query = text('''
        SELECT 
            period_end_date, 
            consensus AS estimated_eps, 
            recent AS reported_eps
        FROM 
            eps_estimate 
        WHERE 
            act_symbol = :ticker
        ORDER BY 
            period_end_date;
    ''')

    with db.engine.connect() as connection:
        result = connection.execute(query, {'ticker': ticker})
        data = result.mappings().all()

    if not data:
        return 'No data found for ticker: ' + ticker
    
    # Convert the results into a DataFrame
    df = pd.DataFrame(data)

    # Ensure that period_end_date is a datetime
    df['period_end_date'] = pd.to_datetime(df['period_end_date'])

    # Convert estimated and reported EPS to numeric
    df['estimated_eps'] = pd.to_numeric(df['estimated_eps'], errors='coerce')
    df['reported_eps'] = pd.to_numeric(df['reported_eps'], errors='coerce')

    # Drop rows with NaN values that cannot be converted to numeric
    df = df.dropna(subset=['estimated_eps', 'reported_eps'])

    # Plotting
    fig, ax = plt.subplots(figsize=(10, 6))

    # Set index to period_end_date for plotting
    df.set_index('period_end_date', inplace=True)

    # Plotting the bars side-by-side
    width = 90 # Width of the bars
    ax.bar(df.index - pd.Timedelta(days=width/2), df['estimated_eps'], width, label='Estimated EPS', color='skyblue')
    ax.bar(df.index + pd.Timedelta(days=width/2), df['reported_eps'], width, label='Reported EPS', color='royalblue')

    # Formatting the x-axis to show the date properly
    ax.xaxis_date()  # Interpret the x-axis values as dates
    fig.autofmt_xdate()  # Auto-format the dates on the x-axis

    # Set labels and title
    ax.set_xlabel('Period End Date')
    ax.set_ylabel('EPS')
    ax.set_title(f'Earnings Per Share (EPS) for {ticker}')
    ax.legend()

    # Save the figure
    graph_path = os.path.join(app.static_folder, 'graphs', f'{ticker}_eps_comparison.png')
    plt.tight_layout()
    plt.savefig(graph_path)
    plt.close()

    # Relative graph path for the HTML template
    relative_graph_path = os.path.join('graphs', f'{ticker}_eps_comparison.png')

       # Generate a prompt for the OpenAI model
    messages = [
        {"role": "system", "content": "You are a stock performance consultant."},
        {"role": "user", "content": f"  Offer general advice and information rewarding the company with stock ticker {ticker}, no need for real time data. Then summarize the top 3 key points. Do not include any other text. Format the summary as a bullet point list. Do not include any other text."},
    ]

    # Make a call to the OpenAI Chat API
    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages
        )
        summary = response.choices[0].message.content 
    except Exception as e:  # Catch a generic exception
        summary = "An error occurred while generating the summary."
        print(e)
        print(response)
   
    return render_template('stock_details.html', ticker=ticker, graph_image=relative_graph_path, summary=summary)

