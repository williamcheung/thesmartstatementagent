import json

from typing import Any

# read tickers and CIKs (Central Index Keys) from company_tickers.json file, downloaded manually from: https://www.sec.gov/files/company_tickers.json
with open('data/company_tickers.json', 'r', encoding='utf-8') as f:
    data: dict[str, dict[str, Any]] = json.load(f)

cik_map: dict[str, str] = {v['ticker']: str(v['cik_str']) for v in data.values()}
cik_map = dict(sorted(cik_map.items()))

company_map: dict[str, str] = {v['ticker']: v['title'].title() if v['title'].isupper() else v['title'] for v in data.values()}
company_map = dict(sorted(company_map.items(), key=lambda item: (item[1].casefold(), item[0])))

def get_cik(ticker: str) -> str:
    return cik_map[ticker].zfill(10) if ticker in cik_map else None

def get_companies() -> dict[str, str]:
    return company_map

if __name__ == '__main__':
    # test usage
    ticker = 'AAPL'
    print(f'{ticker}: {get_cik(ticker)}')

    companies = get_companies()
    print(f'companies: {companies}')
