from dotenv import load_dotenv
load_dotenv()

import os

from langchain_community.vectorstores import TiDBVectorStore
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.pydantic_v1 import BaseModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from filing_embedder_openai import embed_model_dims, OPENAI_EMBEDDING_API_KEY, OPENAI_EMBEDDING_MODEL
from tidb_financial_statements_vector_store import get_tidb_init_params

embeddings = OpenAIEmbeddings(api_key=OPENAI_EMBEDDING_API_KEY, model=OPENAI_EMBEDDING_MODEL, dimensions=embed_model_dims)
init_params = get_tidb_init_params()

class Question(BaseModel):
    __root__: str

def ask_question(ticker: str, question: str) -> str:
    vectorstore = TiDBVectorStore.from_existing_vector_table(
        embedding=embeddings,
        connection_string=init_params['connection_string'],
        table_name=init_params['table_name'])
    search_kwargs = {'filter': {'ticker': ticker}} if ticker else {}
    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)

    # define the RAG prompt
    template = '''Answer the question based only on the following context:
    {context}
    Question: {question}

    NOTE: If the answer is not found in the context or cannot be inferred from it, say "I can't find the answer in this year's financial statements."

    Your answer is for an end user so do not mention the word "context"; instead you can refer to "financial statements" if needed.
    '''
    prompt = ChatPromptTemplate.from_template(template)

    # define the RAG model
    model = ChatOpenAI(temperature=0, model=os.getenv('OPENAI_MODEL'),
                       max_tokens=16_384) # max for GPT-4o and GPT-4o mini, per: https://platform.openai.com/docs/models

    chain = (
        RunnableParallel({'context': retriever, 'question': RunnablePassthrough()})
        | prompt
        | model
        | StrOutputParser()
    )
    chain = chain.with_types(input_type=Question)

    print(f'LANGCHAIN RAG Q: [{ticker}] {question}')
    answer = chain.invoke(question)
    print(f'A: {answer}')

    return answer

if __name__ == '__main__':
    # test usage
    tickers = ['DOCU', 'MSFT']
    questions = [
        'Where are the headquarters of the company?',
        'What are the latest revenue numbers and when were they announced?',
        'What is the AI strategy?'
    ]

    for ticker in tickers:
        for question in questions:
            answer = ask_question(ticker, question)
