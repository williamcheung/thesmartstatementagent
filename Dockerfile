FROM python:3.12-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Add the requirements file to the container
ADD requirements.txt .

# Install the app dependencies
RUN apt-get update
RUN apt-get install -y python3-dev default-libmysqlclient-dev build-essential pkg-config
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m nltk.downloader punkt_tab

# Copy the source code into the container
COPY . .

# Set env variables
ENV PYTHONUNBUFFERED=1

# Command to run the app on container startup
CMD ["python", "-u", "/app/gradio_ui.py"]
