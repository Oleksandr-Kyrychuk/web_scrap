# Work.ua Job Scraper

A Python script to scrape job listings from work.ua based on user-specified vacancy and city.

## Features
- Filters jobs by vacancy title and city.
- Saves results to CSV with title, company, salary, city, publication date, and link.
- Logs progress and errors to `workua_scraper.log`.
- Sorts results by salary (highest first).

## Requirements
- Python 3.8+
- Libraries: `requests`, `beautifulsoup4`, `selenium`, `webdriver-manager`
- Firefox browser and geckodriver

## Usage
```bash
python main2.py

Output

    workua_jobs.csv: Job listings in CSV format.
    workua_scraper.log: Execution log.
    page_X.html: Debug HTML files (optional).

Notes

    Randomized delays prevent server blocking.
    Complex city parsing due to inconsistent site structure.
