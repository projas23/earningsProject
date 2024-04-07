from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from collections import defaultdict
from flask_caching import Cache
import os
import pandas as pd
import matplotlib.pyplot as plt

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:@localhost:3307/earningsDB'
db = SQLAlchemy(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/most-anticipated')
@cache.cached(timeout=604800)  # Cache for one week
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
    # Example: Query to fetch data for the ticker
    query = text("SELECT * FROM earnings_calendar WHERE act_symbol = :ticker")
    with db.engine.connect() as connection:
        result = connection.execute(query, {'ticker': ticker})
        data = result.fetchall()
    
    # Assuming 'data' is now a DataFrame or can be converted into one
    # df = pd.DataFrame(data)
    
    # Data processing and graph generation with Pandas and Matplotlib
    # Placeholder for actual data processing and graph generation code
    
    # Example graph save path
    graph_path = f'static/graphs/{ticker}_details.png'
    if not os.path.exists('static/graphs/'):
        os.makedirs('static/graphs/')
    
    # Save your Matplotlib figure
    plt.figure()
    # Example plotting code
    # plt.plot(df['date'], df['some_metric'])
    plt.savefig(graph_path)
    plt.close()
    
    return render_template('stock_details.html', ticker=ticker, graph_image=graph_path)