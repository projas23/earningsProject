from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from collections import defaultdict
from flask_caching import Cache
import os
import pandas as pd
import matplotlib  # Import matplotlib before setting the backend
matplotlib.use('Agg')  # Set the backend to 'Agg'
import matplotlib.pyplot as plt  # Now, it's safe to import pyplot

app = Flask(__name__, static_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:@localhost:3307/earningsDB'
db = SQLAlchemy(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})


@app.route('/most-anticipated')
# @cache.cached(timeout=604800)  # Cache for one week
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
            date, 
            period_end_date, 
            consensus, 
            recent, 
            high, 
            low, 
            year_ago 
        FROM 
            eps_estimate 
        WHERE 
            act_symbol = :ticker
        ORDER BY 
            period_end_date;
    ''')

    with db.engine.connect() as connection:
        result = connection.execute(query, {'ticker': ticker})
        data = result.mappings().all()  # Correctly fetch data as a list of dictionaries

    if not data:
        return 'No data found for ticker: ' + ticker
    
    # Proceed with converting data to a DataFrame and plotting
    df = pd.DataFrame(data)
    df['period_end_date'] = pd.to_datetime(df['period_end_date'])
    df.set_index('period_end_date', inplace=True)

    # Example plotting
    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df['consensus'], label='Consensus EPS', marker='o')
    plt.plot(df.index, df['recent'], label='Recent EPS', marker='x')
    plt.title(f'EPS Estimates for {ticker}')
    plt.xlabel('Period End Date')
    plt.ylabel('EPS')
    plt.legend()
    plt.grid(True)
        
    # Example graph save path
    graph_path = f'static/graphs/{ticker}_eps_comparison.png'
    plt.savefig(graph_path)
    plt.close()

    # Ensure that graph_path is relative to the 'static' directory
    relative_graph_path = f'graphs/{ticker}_eps_comparison.png'

    # Pass the correct graph_image path to the template
    return render_template('stock_details.html', ticker=ticker, graph_image=relative_graph_path)


