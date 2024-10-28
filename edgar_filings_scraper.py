from dotenv import load_dotenv
load_dotenv()

import datetime
import hashlib
import json
import os
import requests
import time
import unicodedata

from brotli import decompress
from bs4 import BeautifulSoup
from typing import Any
from urllib.parse import urlparse

from edgar_cik import get_cik

# constants
MIN_YEAR = int(os.getenv('MIN_YEAR', str(datetime.datetime.now().year)))
DEFAULT_DATA_DIR = 'data'
UTF_8_ENCODING = 'utf-8'

SCRAPING_USER_AGENT = os.getenv('SCRAPING_USER_AGENT')
BROWSER_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0'

def scrape_filings_from_edgar(ticker: str) -> tuple[list[str], list[str], list[str]]:
    cik = get_cik(ticker)
    if not cik:
        return None

    os.makedirs(f'{DEFAULT_DATA_DIR}/{ticker}', exist_ok=True)

    _get_edgar_submissions_json_file(ticker)

    filing_urls, filing_titles, filing_dates = _edgar_save_filing_metadata(ticker)

    _edgar_save_filing_text(ticker, filing_urls)

    return filing_urls, filing_titles, filing_dates

def _get_edgar_submissions_json_file(ticker: str) -> None:
    cik = get_cik(ticker)

    submissions_json_file_path = f'{DEFAULT_DATA_DIR}/{ticker}/submissions_{ticker}.json'
    # check if file exists before downloading again
    if os.path.exists(submissions_json_file_path):
        return

    submissions_json_url = f'https://data.sec.gov/submissions/CIK{cik}.json'
    # for example: https://data.sec.gov/submissions/CIK0000059478.json
    print(f'[{ticker}]: GET {submissions_json_url}')
    submissions_json = _get_json(submissions_json_url, mimic_browser=True)
    with open(submissions_json_file_path, 'w', encoding=UTF_8_ENCODING) as f:
        json.dump(submissions_json, f)

def _edgar_extract_filing_metadata(ticker: str) -> tuple[list[str], list[str], list[str]]:
    cik = get_cik(ticker)

    with open(f'{DEFAULT_DATA_DIR}/{ticker}/submissions_{ticker}.json', 'r', encoding=UTF_8_ENCODING) as f:
        data = json.load(f)

    urls: list[str] = []
    titles: list[str] = []
    filing_dates: list[str] = []

    earliest_matched_date: str = None
    name: str = data['name']
    recent_filings: dict[str, Any] = data['filings']['recent'] # includes 2021 onward

    forms = ['10-K', '10-Q', '8-K'] # for US firms
    forms += ['20-F', '6-K'] # for non-US firms
    forms += [f'{form}/A' for form in forms] # include amendments
    # source: https://www.investor.gov/introduction-investing/getting-started/researching-investments/using-edgar-research-investments

    for i in range(len(recent_filings['accessionNumber'])):
        filing_date: str = recent_filings['filingDate'][i]
        form: str = recent_filings['form'][i]

        if (int(filing_date[:4]) >= MIN_YEAR and form in forms):
            # build URL for HTML filing form
            # like: https://www.sec.gov/ix?doc=/Archives/edgar/data/0000059478/000005947824000118/lly-20240331.htm
            accession_number: str = recent_filings['accessionNumber'][i]
            primary_document: str = recent_filings['primaryDocument'][i]
            url = f"https://www.sec.gov/ix?doc=/Archives/edgar/data/{cik}/{accession_number.replace('-', '')}/{primary_document}"
            urls.append(url)

            title = f'{name} - FORM {form} - {filing_date}'
            titles.append(title)

            filing_dates.append(filing_date)

            # update earliest_matched_date
            if earliest_matched_date is None or filing_date < earliest_matched_date:
                earliest_matched_date = filing_date

    print(f'[{ticker}]: {len(urls)} filings since: {earliest_matched_date}')
    return urls, titles, filing_dates

def get_form_type(filing_title) -> str:
    form_type = filing_title.split(' - FORM ')[1].split(' - ')[0]
    return form_type

def _edgar_save_filing_metadata(ticker: str) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    urls_file_path = f'{DEFAULT_DATA_DIR}/{ticker}/filing_urls_{ticker}.txt'
    titles_file_path = f'{DEFAULT_DATA_DIR}/{ticker}/filing_titles_{ticker}.txt'
    dates_file_path = f'{DEFAULT_DATA_DIR}/{ticker}/filing_dates_{ticker}.txt'
    if os.path.exists(urls_file_path) and os.path.exists(titles_file_path) and os.path.exists(dates_file_path):
        with open(urls_file_path, 'r', encoding=UTF_8_ENCODING) as f:
            filing_urls = [line.strip() for line in f]
        with open(titles_file_path, 'r', encoding=UTF_8_ENCODING) as f:
            filing_titles = [line.strip() for line in f]
        with open(dates_file_path, 'r', encoding=UTF_8_ENCODING) as f:
            filing_dates = [line.strip() for line in f]
    else:
        filing_urls, filing_titles, filing_dates = _edgar_extract_filing_metadata(ticker)
        if filing_urls:
            with open(urls_file_path, 'w', encoding=UTF_8_ENCODING) as f:
                for url in filing_urls:
                    f.write(f'{url}\n')
            with open(titles_file_path, 'w', encoding=UTF_8_ENCODING) as f:
                for title in filing_titles:
                    f.write(f'{title}\n')
            with open(dates_file_path, 'w', encoding=UTF_8_ENCODING) as f:
                for filing_date in filing_dates:
                    f.write(f'{filing_date}\n')

    return filing_urls, filing_titles, filing_dates

# the text of all filings are saved to disk to save on memory usage
def _edgar_save_filing_text(ticker: str, filing_urls: list[str]) -> None:
    output_dir = f'{DEFAULT_DATA_DIR}/{ticker}/{ticker}_filings'
    os.makedirs(output_dir, exist_ok=True)

    for url in filing_urls:
        url = url.strip()
        if os.path.exists(_get_filing_text_file_path(output_dir, url)):
            continue

        print(f'Getting [{ticker}] filing: {url}')

        plain_html_url = url.replace('ix?doc=/', '')

        soup = _get_html(plain_html_url, mimic_browser=True)

        hidden_divs_to_remove = soup.find_all('div', style='display:none')
        for div in hidden_divs_to_remove: # remove these for human reader, these are for the XBRL viewer
            div.decompose()

        filing_text = soup.text.strip()
        filing_text = _clean_filing_text(filing_text)

        start_of_filing_index = filing_text.find('SECURITIES AND EXCHANGE COMMISSION') # at top of filing to avoid other hidden XBRL noise
        if start_of_filing_index == -1: # some filings use mixed case
            start_of_filing_index = filing_text.find('Securities and Exchange Commission')
        if start_of_filing_index == -1: # some filings start with TOC instead
            start_of_filing_index = filing_text.find('Table of Contents​')

        if start_of_filing_index != -1:
            filing_text = filing_text[start_of_filing_index:]
        else:
            print(f'Warning: SEC title not found for: {plain_html_url}')

        if not filing_text:
            error = f'Error: No text found for: {plain_html_url}'
            print(error)
            raise Exception(error)

        _save_filing_text(output_dir, url, filing_text)

def _save_filing_text(output_dir: str, url: str, filing_text: str) -> None:
    filing_text_filepath = _get_filing_text_file_path(output_dir, url)
    with open(filing_text_filepath, 'w', encoding=UTF_8_ENCODING) as f:
        f.write(filing_text)

def _get_filing_text(output_dir: str, url: str) -> str:
    filing_text_filepath = _get_filing_text_file_path(output_dir, url)
    with open(filing_text_filepath, 'r', encoding=UTF_8_ENCODING) as f:
        filing_text = f.read()
        print(f'Extracted text from saved: {filing_text_filepath}')
        return filing_text

def _get_filing_text_file_path(output_dir, url) -> str:
    filing_url_hash = hashlib.sha256(url.encode()).hexdigest()
    filing_text_filepath = f'{output_dir}/{filing_url_hash}.txt'
    return filing_text_filepath

def get_filing_text(ticker: str, url: str) -> str:
    output_dir = f'{DEFAULT_DATA_DIR}/{ticker}/{ticker}_filings'
    return _get_filing_text(output_dir, url)

# helpers

EXP_BACKOFF_MAX_RETRIES = 2
EXP_BACKOFF_INITIAL_DELAY = 1 # seconds

def _get_html(search_url: str, mimic_browser=False, max_retries_increment=0) -> BeautifulSoup:
    """
    Fetches HTML content from a URL, retrying with exponential backoff if necessary.

    Args:
        search_url (str): The URL to fetch.

    Returns:
        BeautifulSoup: A BeautifulSoup object representing the HTML content.

    Raises:
        Exception: If the request fails after all retries.
    """

    max_retries = EXP_BACKOFF_MAX_RETRIES + max_retries_increment
    delay = EXP_BACKOFF_INITIAL_DELAY

    headers = _get_headers(search_url, mimic_browser, BROWSER_USER_AGENT)

    for i in range(max_retries + 1):
        response = requests.get(search_url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup

        if response.status_code == 404:
            print(f'404: {search_url}')
            return None

        if i == max_retries:
            error = f'Failed to fetch [{search_url}] after {max_retries} retries: {response.status_code} {response.reason}'
            print(f'Error: {error}')
            raise Exception(error)

        time.sleep(delay)
        delay *= 2 # exponential backoff

def _get_json(search_url: str, mimic_browser=False) -> dict[str, Any]:
    """
    Fetches JSON content from a URL, retrying with exponential backoff if necessary.

    Args:
        search_url (str): The URL to fetch.

    Returns:
        dict[str, Any]: A dict representing the JSON content.

    Raises:
        Exception: If the request fails after all retries.
    """

    max_retries = EXP_BACKOFF_MAX_RETRIES
    delay = EXP_BACKOFF_INITIAL_DELAY

    headers = _get_headers(search_url, mimic_browser, SCRAPING_USER_AGENT)

    response = None
    e = None

    for i in range(max_retries + 1):
        try:
            response = requests.get(search_url, headers=headers)

            if response.status_code == 200:
                try:
                    return response.json()

                except requests.exceptions.JSONDecodeError as e:
                    if response.headers.get('Content-Encoding') == 'br':
                        try: # try decode the Brotli-compressed response
                            decoded_content = decompress(response.content)
                            return json.loads(decoded_content.decode(UTF_8_ENCODING))

                        except Exception as e:
                            print(f'Error: {e}')
                            raise
                    print(f"Error: {response.headers.get('Content-Encoding')=} - {e}")
                    raise

            else:
                print(f'Error: {response.status_code} {response.reason}')

        except requests.exceptions.RequestException as e:
            print(f'Error: {e}')
            # don't raise, go on to retry

        if i == max_retries:
            error = f'Failed to fetch [{search_url}] after {max_retries} retries.'
            print(f'Error: {error}')
            raise Exception(error)

        time.sleep(delay)
        delay *= 2 # exponential backoff

def _get_headers(search_url: str, mimic_browser: bool, user_agent: str) -> dict[str, str] | None:
    headers = None
    if mimic_browser:
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'br', # only support Brotli to simplify what to expect # 'Accept-Encoding': 'gzip, deflate, br, zstd'
            'Accept-Language': 'en-CA,en-US;q=0.7,en;q=0.3',
            'Connection': 'keep-alive',
            'Host': urlparse(search_url).netloc,
            'Priority': 'u=1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': user_agent
        }

    return headers

def _clean_filing_text(text: str) -> str:
    # normalize newlines
    text = text.replace('\r', '\n')

    # replace newlines with spaces
    text = text.replace('\n', ' ')

    # for simpler parsing, replace Unicode special characters like "\u00a0", "\u2013", "\u2018", etc. with their standard text equivalents ("NFKC" form)
    text = unicodedata.normalize('NFKC', text)

    return text.strip()

if __name__ == '__main__':
    # test usage
    filings = scrape_filings_from_edgar('MSFT')
    print(f'{filings=}')
