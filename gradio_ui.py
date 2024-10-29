import gradio as gr

from edgar_cik import get_companies
from edgar_filings_scraper import MIN_YEAR
from langchain_tidb_rag import ask_question
from tidb_financial_statements_vector_store import check_ticker_exists_in_vector_store
from vector_store_loader_queue import begin_vector_store_loader_thread, queue_vector_store_load, ticker_being_loaded_to_vector_store

companies = get_companies()
begin_vector_store_loader_thread()

GREETING = \
f'''
Hi, I'm your cool & free <b>$mart $tatement Agent</b> ❤️💵💶💷💴💰
Ask a question about any of the <b>{f'{len(companies):,}'}</b> companies in the list and I'll look for an answer for you from their <b>{MIN_YEAR}</b> financial statements!
'''.strip()

# send_button click handler
def submit_message(message: str, ticker: str, history: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], str]:
    if not message:
        return history, '' # '' clears the input text box

    if not ticker:
        history.append((None, f'Oops, please select a company from the list... you only have to choose from {len(companies):,} 😊'))
        return history, message

    if not check_ticker_exists_in_vector_store(ticker):
        if not ticker_being_loaded_to_vector_store(ticker):
            history.append((None, f"Wow, you're the first person to ask me about <b>{companies[ticker]}</b>! Give me a few minutes to get their {MIN_YEAR} financial statements ⌛"))
            queue_vector_store_load(ticker)
        else:
            history.append((None, f"Still loading <b>{companies[ticker]}</b>'s financial statements... they seem to have a lot of data 🤷‍♂️"))
        return history, message

    print(f'question for {ticker}: {message}')
    answer = ask_question(ticker, message)
    history.append((f'[{ticker}] {message}', answer)) # add ticker to start of question to display in UI
    return history, ''

# retry_button click handler
def retry_message(ticker: str, history: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], str]:
    if history:
        last_message: str = history[-1][0]
        if last_message:
            last_message = last_message.split(']', 1)[1].strip() # remove ticker previously added to start of question
        return submit_message(last_message, ticker, history)
    return history, ''

# undo_message click handler
def undo_message(history: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], str]:
    if history:
        return history[:-1] if len(history) > 1 else history, ''
    return history, ''

# clear_button click handler
def clear_messages() -> tuple[list[tuple[str, str]], str, str]:
    return [(None, GREETING)], '', None

with gr.Blocks() as demo:
    gr.Markdown('<h1 style="text-align:center;">The $mart $tatement Agent</h1>')

    chatbot = gr.Chatbot(
        label='$tatement Agent',
        height='60vh',
        show_copy_button=True,
        value=[(None, GREETING)]
    )

    with gr.Row(variant='panel'):
        with gr.Column(scale=6):
            msg = gr.Textbox(autofocus=True, label='Question?', lines=4)
        with gr.Column(scale=2):
            company_dropdown = gr.Dropdown(label='Company (name & stock ticker)', choices=[(f'{title} [{ticker}]', ticker) for ticker, title in companies.items()])
            send_button = gr.Button('Ask Question')

    with gr.Row():
        retry_button = gr.Button('Retry')
        undo_button = gr.Button('Undo')
        clear_button = gr.Button('Clear')

    send_button.click(submit_message, inputs=[msg, company_dropdown, chatbot], outputs=[chatbot, msg])
    retry_button.click(retry_message, inputs=[company_dropdown, chatbot], outputs=[chatbot, msg])
    undo_button.click(undo_message, inputs=[chatbot], outputs=[chatbot, msg])
    clear_button.click(clear_messages, outputs=[chatbot, msg, company_dropdown])

demo.launch(server_name='0.0.0.0')
