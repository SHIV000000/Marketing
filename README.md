# Marketing Agency Management System

## Overview
This project is a comprehensive management system for marketing agencies. It integrates various tools and platforms to streamline agency operations, including email management, bank transaction tracking, Google Ads campaign management, and data analysis.

## Features
- User Authentication and Agency Management
- Email Integration
  - Connect and manage multiple email accounts
  - View and search emails
  - Handle email attachments
- Bank Integration
  - Connect bank accounts (Deutsche Bank support)
  - Track and analyze bank transactions
- Google Ads Integration
  - Manage Google Ads accounts
  - View and analyze campaign performance
- Data Analysis Tools
  - Perform various types of data analysis on agency data
- Manual Data Entry
  - Allow manual entry of financial data for comprehensive reporting

## Technologies Used
- Python 3.x
- Flask (Web Framework)
- SQLAlchemy (ORM)
- HTML/CSS/JavaScript (Frontend)
- PostgreSQL (Database)

## Setup and Installation
1. Clone the repository:
```bash
git clone https://github.com/SHIV000000/Marketing.git
```
```bash
cd Marketing
```
2. Create and activate a virtual environment:
`python -m venv env`  `source env/bin/activate` ` env\Scripts\activate`

3. Install the required packages:
```bash
pip install -r requirements.txt
```
4. Set up environment variables:
   Create a `.env` file in the root directory

5. Initialize the database:

```bash
flask db upgrade
```


7. Run the application:

```bash
flask run
```

## Usage
After setting up the project, you can access the application by navigating to `http://localhost:5000` in your web browser. From there, you can:
- Create an agency account
- Connect email accounts
- Link bank accounts
- Set up Google Ads integration
- Perform data analysis
- View and manage various aspects of your marketing agency












