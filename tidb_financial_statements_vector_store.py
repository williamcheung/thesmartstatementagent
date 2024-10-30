from dotenv import load_dotenv
load_dotenv()

import os
import time

from tidb_vector.integrations import TiDBVectorClient

from edgar_filings_scraper import get_filing_text, get_form_type, scrape_filings_from_edgar
from filing_chunker import chunk_filing
from filing_embedder_openai import embed_filing_chunk, embed_filing_chunks, embed_model_dims
from rest_api import send_heartbeat

ONE_EMBEDDING_REQ_FOR_ALL_CHUNKS_IN_FILING = True
MAX_INSERT_BATCH_SIZE = os.getenv('MAX_INSERT_BATCH_SIZE')

get_tidb_init_params = lambda drop_existing_table=False: dict(
    # The table which stores the vector data.
    table_name=os.getenv('TIDB_TABLE_NAME'),
    # The connection string to the TiDB cluster.
    connection_string=os.getenv('TIDB_DATABASE_URL'),
    # The dimension of the vector generated by the embedding model.
    vector_dimension=embed_model_dims,
    # Determine whether to recreate the table if it already exists.
    drop_existing_table=drop_existing_table)

def _get_vector_store(drop_existing_table=False) -> TiDBVectorClient:
    vector_store = TiDBVectorClient(**get_tidb_init_params(drop_existing_table))
    return vector_store

def _get_chunk_embeddings(ticker: str) -> list[tuple[str, list[float]], dict[str, str]]:
    filing_urls, filing_titles, filing_dates = scrape_filings_from_edgar(ticker)

    start_time = time.time()
    total_chunking_time = 0

    chunk_embeddings: list[tuple[str, list[float]], dict[str, str]] = []
    for url, title, date in zip(filing_urls, filing_titles, filing_dates):
        text = get_filing_text(ticker, url)
        print(f'[{ticker}] [{date}] [{title}] -> {text[0:100]}...')

        form_type = get_form_type(title)

        chunk_start_time = time.time()
        chunks = chunk_filing(text, form_type)
        chunk_end_time = time.time()
        total_chunking_time += chunk_end_time - chunk_start_time

        send_heartbeat()

        try:
            if ONE_EMBEDDING_REQ_FOR_ALL_CHUNKS_IN_FILING:
                API_LIST_SIZE_LIMIT = 2048
                sublists = [chunks[i:i + API_LIST_SIZE_LIMIT] for i in range(0, len(chunks), API_LIST_SIZE_LIMIT)]
                for subchunks in sublists:
                    embeddings = embed_filing_chunks(subchunks)
            else:
                embeddings = []
                for chunk in chunks:
                    embedding = embed_filing_chunk(chunk)
                    embeddings.append(embedding)

        except Exception as e:
            print(f'Error embedding [{ticker}] chunks for {url}: {e}')
            continue # skip this filing

        finally:
            send_heartbeat()

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings), start=1):
            chunk_embeddings.append((chunk, embedding, _build_chunk_metadata(ticker, url, title, date, form_type, i)))
        print(f'[{ticker}] text len={len(text)} -> {len(chunks)} chunks')
    end_time = time.time()
    total_duration = end_time - start_time
    print(f'[{ticker}] Elapsed time to chunk and embed: {round(total_duration, 2)} secs')
    print(f'[{ticker}] Elapsed time to chunk ONLY: {round(total_chunking_time, 2)} secs')
    print(f'[{ticker}] Elapsed time to embed ONLY: {round(total_duration - total_chunking_time, 2)} secs')
    return chunk_embeddings

def _build_chunk_metadata(ticker, url, title, date, form_type, chunk_num):
    metadata = {'ticker': ticker, 'url': url, 'title': title, 'date': date, 'form_type': form_type, 'chunk': chunk_num}
    return metadata

def check_ticker_exists_in_vector_store(ticker):
    vector_store = _get_vector_store()
    result = vector_store.query(filter={'ticker': ticker}, k=1, query_vector=[0.0] * embed_model_dims)
    exists = len(result) > 0
    print(f'[{ticker}] Ticker exists in vector store: {exists}')
    return exists

def load_ticker_filings_into_vector_store(ticker):
    chunk_embeddings = _get_chunk_embeddings(ticker)
    total_embeddings = len(chunk_embeddings)
    print(f'[{ticker}] {total_embeddings} chunk embeddings')

    batch_size = int(MAX_INSERT_BATCH_SIZE) if MAX_INSERT_BATCH_SIZE else total_embeddings
    sublists = [chunk_embeddings[i:i + min(total_embeddings, batch_size)] for i in range(0, total_embeddings, batch_size)]

    vector_store = _get_vector_store()
    vector_store.delete(filter={'ticker': ticker})
    start_time = time.time()
    for sublist in sublists:
        print(f'[{ticker}] Inserting {len(sublist)} embeddings')
        vector_store = _get_vector_store() # refresh connection
        vector_store.insert(
            ids=[f"{meta['ticker']}_{seq_no}_{meta['date']}_{meta['form_type']}_{meta['chunk']}" for seq_no, (_, _, meta) in enumerate(sublist, start=1)],
            texts=[chunk for (chunk, _, _) in sublist],
            embeddings=[embedding for (_, embedding, _) in sublist],
            metadatas=[meta for (_, _, meta) in sublist]
        )
        send_heartbeat()
    end_time = time.time()
    print(f'[{ticker}] Elapsed time to insert to vector store: {round(end_time - start_time, 2)} secs')

if __name__ == '__main__':
    # test usage
    # tickers = ['DOCU']
    # vector store seeding - load tickers for S&P 500 (actually 503 stocks)
    tickers = ['AAPL','MSFT','NVDA','AMZN','GOOG','GOOGL','META','BRK.B','LLY','TSLA','AVGO','WMT','JPM','UNH','V','XOM','MA','PG','JNJ','COST','ORCL','HD','ABBV','KO','BAC','MRK','NFLX','CVX','ADBE','PEP','TMO','CRM','TMUS','AMD','LIN','ACN','MCD','ABT','PM','DHR','CSCO','IBM','WFC','TXN','VZ','GE','QCOM','AXP','NOW','INTU','AMGN','ISRG','NEE','PFE','GS','CAT','SPGI','RTX','DIS','MS','T','CMCSA','UNP','PGR','UBER','AMAT','LOW','SYK','LMT','TJX','HON','BLK','BKNG','ELV','REGN','COP','BSX','VRTX','PLD','NKE','CB','MDT','SCHW','ETN','C','MMC','ADP','PANW','AMT','UPS','ADI','BX','DE','KKR','SBUX','ANET','MDLZ','BA','CI','HCA','FI','GILD','BMY','SO','MU','KLAC','LRCX','ICE','MO','SHW','DUK','MCO','CL','ZTS','WM','GD','INTC','CTAS','EQIX','CME','TT','WELL','NOC','AON','PH','CMG','ABNB','ITW','MSI','APH','TDG','PNC','SNPS','CVS','ECL','PYPL','USB','MMM','FDX','TGT','CDNS','BDX','EOG','MCK','AJG','CSX','ORLY','RSG','MAR','CARR','PSA','AFL','DHI','APD','CRWD','ROP','NXPI','NEM','NSC','FCX','FTNT','SLB','TFC','EMR','GEV','AEP','ADSK','TRV','O','CEG','MPC','COF','WMB','OKE','PSX','AZO','GM','HLT','MET','SPG','SRE','CCI','KDP','ROST','BK','PCAR','MNST','KMB','LEN','ALL','DLR','OXY','D','PAYX','CPRT','GWW','AIG','KMI','CHTR','COR','URI','JCI','STZ','FIS','KVUE','TEL','MSCI','IQV','KHC','FICO','LHX','RCL','VLO','AMP','F','PCG','ACGL','GIS','HUM','NDAQ','PRU','HSY','MPWR','CMI','ODFL','MCHP','PEG','A','EW','HES','IDXX','FAST','VRSK','GEHC','EXC','CTVA','SYY','HWM','EA','AME','IT','CTSH','KR','YUM','CNC','EXR','PWR','EFX','OTIS','RMD','ED','DOW','VICI','XEL','IR','GRMN','GLW','CBRE','HIG','DFS','BKR','NUE','EIX','DD','HPQ','AVB','CSGP','IRM','FANG','TRGP','XYL','EL','MLM','LYB','VMC','LULU','WEC','WTW','ON','BRO','LVS','MRNA','PPG','TSCO','ROK','MTD','EBAY','BIIB','CDW','WAB','EQR','AWK','ADM','MTB','NVR','FITB','DAL','GPN','DXCM','K','AXON','CAH','TTWO','PHM','ANSS','VLTO','VTR','IFF','ETR','DVN','CHD','DTE','SBAC','VST','FE','FTV','HAL','KEYS','TYL','STT','DOV','BR','ES','STE','RJF','ROL','SMCI','PPL','NTAP','TSN','SW','TROW','HPE','DECK','WRB','AEE','MKC','CBOE','WY','FSLR','WST','BF.B','INVH','LYV','GDDY','COO','WDC','CINF','ZBH','CPAY','STX','HBAN','BBY','ATO','ARE','LDOS','CMS','RF','CLX','CCL','HUBB','TER','PTC','BAX','TDY','WAT','BALL','BLDR','OMC','ESS','HOLX','LH','SYF','GPC','MOH','EQT','CFG','MAA','DRI','FOXA','APTV','PFG','PKG','ULTA','J','WBD','CNP','LUV','DG','HRL','VRSN','FOX','NTRS','AVY','L','JBHT','EXPE','EXPD','DGX','STLD','ZBRA','MAS','CTRA','EG','IP','ALGN','FDS','TXT','NRG','AMCR','UAL','SWKS','GEN','CAG','KIM','DOC','CPB','NWS','PODD','LNT','NWSA','UHS','KEY','NI','IEX','MRO','SWK','DPZ','UDR','RVTY','SNA','DLTR','AKAM','PNR','CF','NDSN','BG','ENPH','EVRG','REG','VTRS','TRMB','POOL','CE','CPT','SJM','JNPR','DVA','KMX','JKHY','INCY','CHRW','HST','EPAM','BXP','ALLE','IPG','FFIV','JBL','TAP','SOLV','TFX','AES','EMN','TECH','AOS','CTLT','RL','MGM','LKQ','HII','BEN','PNW','AIZ','QRVO','FRT','MKTX','CRL','TPR','HAS','MHK','MTCH','GL','APA','ALB','PAYC','LW','BIO','DAY','HSIC','GNRC','WYNN','MOS','CZR','NCLH','WBA','FMC','BWA','AAL','IVZ','PARA','BBWI','ETSY']
    for ticker in tickers:
        ticker = ticker.replace('.', '-') # EDGAR uses dash instead of the dot in actual symbol
        if not check_ticker_exists_in_vector_store(ticker):
            load_ticker_filings_into_vector_store(ticker)
