from queue import Queue
from threading import Lock, Thread

from tidb_financial_statements_vector_store import load_ticker_filings_into_vector_store

def begin_vector_store_loader_thread(is_daemon = False) -> Thread:
    thread = Thread(target=_queue_handler)
    thread.daemon = is_daemon
    thread.start()
    return thread

_vector_store_loader_queue = Queue()
_tickers_in_process: set[str] = set()
_in_process_lock = Lock()

def queue_vector_store_load(ticker: str):
    with _in_process_lock:
        if not _is_in_process(ticker):
            _vector_store_loader_queue.put(ticker)
            _tickers_in_process.add(ticker)

def ticker_being_loaded_to_vector_store(ticker: str) -> bool:
    with _in_process_lock:
        return _is_in_process(ticker)

def _is_in_process(ticker: str):
    exists = ticker in _tickers_in_process
    return exists

def _queue_handler():
    while True:
        try:
            ticker: str = _vector_store_loader_queue.get()
            load_ticker_filings_into_vector_store(ticker)
            _vector_store_loader_queue.task_done()

        except Exception as e:
            print(f'Error trying to load ticker [{ticker}] to vector store: {e}') #TODO retry

        finally:
            with _in_process_lock:
                _tickers_in_process.remove(ticker)
