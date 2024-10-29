import nltk

from langchain.text_splitter import RecursiveCharacterTextSplitter

nltk.download('punkt_tab')

CHUNK_OVERLAP = 50

def chunk_filing(text: str, form_type: str) -> list[str]:
    sentences = nltk.sent_tokenize(text)

    match form_type.rstrip('/A'): # strip amendment suffix
        case '10-K' | '20-F': # annual filings
            chunk_size = 800
        case '10-Q': # quarterly filings
            chunk_size = 500
        case '8=K' | '6-K' | _: # interim filings
            chunk_size = 400

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=CHUNK_OVERLAP
    )

    chunks = []
    for sentence in sentences:
        chunks.extend(text_splitter.split_text(sentence))
    return chunks

if __name__ == '__main__':
    text = 'Includes $3.6 billion of debt at face value related to the Activision Blizzard acquisition. See Note 7 – Business Combinations for further information.'
    chunks = chunk_filing(text, '10-Q')
    print(f'{chunks=}')
