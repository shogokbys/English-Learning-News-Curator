# English Learning News Curator
This application is designed to help users curate news articles and turn them into effective study materials for improving English reading and listening skills. It also includes comprehension questions that encourage logical thinking and deep understanding. While the primary audience is English learners, this tool is equally beneficial for anyone looking to enhance their critical thinking and language skills.

## Features
- Web GUI Interaction: Users can input a URL through the web interface.
- Automated Content Processing:
  - Fetches and summarises the article from the provided URL.
  - Estimates the CEFR (Common European Framework of Reference for Languages) level of the content.
  - Generates comprehension questions to facilitate understanding and logical thinking.
  - Saves all data as a database entry in Notion.
- Audio Generation: Converts the main body of the article into an MP3 file and saves it to Google Drive for listening practice.

## Getting Started
### Prerequisites
Ensure you have the following installed on your system:

- Python 3.8+
- pip (Python package installer)

### Installation
1. Clone this repository:

```
git clone https://github.com/your-username/english-learning-news-curator.git
cd english-learning-news-curator
```

2. Install the required packages:

```
pip install -r requirements.txt
```

3. Set up your *Notion API key* and *Google Drive credentials*. (Instructions can be found in the respective API documentation.)

### Running the Application
1. Start the server:
```
uvicorn main:app --host 0.0.0.0 --port 8000
```

2. Access the application by visiting the following address in your web browser:

```
http://<host-ip>:8000
```

Replace <host-ip> with your machine's IP address (e.g., http://192.168.1.100:8000).

## How It Works
1. Provide a URL: Enter the URL of a news article in the application.
2. Content Processing:
  - The application fetches and summarises the article.
  - Determines the CEFR level for English learners.
  - Generates comprehension questions and uploads everything to your Notion database.
3. Audio File Creation: The article’s main body is converted into an MP3 file and saved to Google Drive for easy listening.

## Contributing
Contributions are welcome! If you have suggestions for improvements or new features, feel free to open an issue or submit a pull request.

## License
This project is licensed under the [MIT License]().

## Acknowledgements
[Notion API]()
[Google Drive API]()
