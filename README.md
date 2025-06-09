# Jira-Asana Integration Tool

A web-based tool for syncing data between Jira and Asana with customizable field mapping.

## Features

- Connect Jira and Asana accounts
- Configure field mappings between platforms
- Sync data in both directions
- Customizable field selection
- Error handling and logging

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your API credentials:
```
JIRA_URL=your_jira_url
JIRA_EMAIL=your_jira_email
JIRA_API_TOKEN=your_jira_api_token
ASANA_ACCESS_TOKEN=your_asana_access_token
```

3. Run the application:
```bash
python app.py
```

## Usage

1. Configure field mappings through the web interface
2. Select which fields to sync
3. Start the sync process
4. Monitor progress and view logs
