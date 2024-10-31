# The $mart $tatement Agent

This is a GPT-4 (OpenAI) powered agent that answers questions about over 10,000 companies that trade on US stock exchanges! It uses each company's current year (2024) financial statements to answer your questions. If you ask about a company which the agent doesn't already have in its vector database (TiDB), the company's financial statements are downloaded, processed, and then uploaded to the database. The $mart $tatement Agent has the latest financial data which ChatGPT with its knowledge cutoff (Oct 2023) does NOT have. Have fun!

## Tech Stack

The agent is built in Python 3.12 using the following technologies:

- OpenAI
- TiDB Vector
- NLTK (Natural Language Toolkit)
- LangChain
- Gradio
- BeautifulSoup
- EDGAR API
- FastAPI

## Docker Deployment

- Copy the `.env.sample` file to a new file named `.env`.

- Edit the `.env` file and update the environment variable settings below with real values. Get the values needed by signing up for OpenAI and TiDB:
    - `OPENAI_API_KEY`: https://platform.openai.com
    - `TIDB_TABLE_NAME`, `TIDB_DATABASE_URL`: https://tidbcloud.com/free-trial - After signing up, click "Create Cluster" and choose `Serverless` (5 GB free forever).
    * For the database URL, go to https://tidbcloud.com/console/clusters click on your new cluster, then click the "Connect" button top right, then select `Connect With`|`SQLAlchemy` to get your URL for `mysqlclient`. Finally click `Download the CA cert` and put the file `isrgrootx1.pem` in the `ca_cert` folder.

- Also specify the `SCRAPING_USER_AGENT` variable in your `.env` file to access to the EDGAR API https://www.sec.gov/search-filings/edgar-application-programming-interfaces which provides all financial statements (filings) of all companies which trade on US stock exchanges:
    - first name
    - last name
    - email

- Save your changes to the `.env` file, then build the Docker image, and finally run the Docker container based on the image:
```bash
docker build -t statementagent .
docker run --name statementagent_container -p 7860:7860 -t statementagent
```

Once you see the following logs in the Docker container console, the agent's chatbot interface is running and accessible:
```bash
Running on local URL:  http://0.0.0.0:7860

To create a public link, set `share=True` in `launch()`.
```

Access the chatbot interface on your host machine in a browser via: http://localhost:7860
