from flask import Flask, render_template, request, send_file
import pandas as pd
import io
from scraper import scrape_gmaps

app = Flask(__name__)
last_results = []

@app.route('/', methods=['GET', 'POST'])
def index():
    global last_results
    city = ''
    keyword = ''
    num_results = 10
    page = int(request.args.get('page', 1))
    per_page = 10
    remove_website = request.values.get('no_website') == 'on'
    remove_instagram = request.values.get('no_instagram') == 'on'
    has_website = request.values.get('has_website') == 'on'  # New filter
    search_query = request.values.get('search', '').lower()

    if request.method == 'POST':
        city = request.form['city']
        keyword = request.form['keyword']
        num_results = int(request.form.get('num_results', 10))
        last_results = scrape_gmaps(city, keyword, max_results=num_results)

    # Apply filters
    if search_query:
        filtered_results = [
            r for r in last_results 
            if search_query in (r['name'] or '').lower() or 
               search_query in (r['phone'] or '').lower()
        ]
    else:
        filtered_results = last_results.copy()

    # New: Filter by website existence
    if has_website:
        filtered_results = [r for r in filtered_results if r['website'] != 'Not found']

    total = len(filtered_results)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    paginated_results = filtered_results[start:end]

    return render_template(
        'index.html',
        results=paginated_results,
        city=city,
        keyword=keyword,
        num_results=num_results,
        remove_website=remove_website,
        remove_instagram=remove_instagram,
        has_website=has_website,  # Pass to template
        page=page,
        total_pages=total_pages,
        search_query=search_query
    )

@app.route('/download')
def download():
    global last_results
    if not last_results:
        return "No data to download."
    df = pd.DataFrame(last_results)
    csv = df.to_csv(index=False)
    return send_file(
        io.BytesIO(csv.encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='results.csv'
    )

if __name__ == '__main__':
    app.run(debug=True)
