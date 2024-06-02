from src.articles_operator import ArticlesOperator
from flask import Flask
from src.router.question_router import question_router 
from src.router.articles import articles
from src.scripts.cronjob import database_scheduler
import sentry_sdk

import asyncio

from src.slack_app import SlackBotFacade
# Add this decorator to instrument your python function
import threading

sentry_sdk.init(
    dsn="https://bd9804963261404b14353239ecf78bda@o1264169.ingest.sentry.io/4506064744349696",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
)

application= Flask(__name__)

# POST /receive_question
application.register_blueprint(question_router)
# GET /articles
application.register_blueprint(articles)

@application.route('/')
def home():
    response_html = f"<p>Connecting the deployed endpoint to moodle for test response</p>"
    return response_html

if __name__ == "__main__":
    
    slack_bot = SlackBotFacade()
    
    # Create a thread for the Slack bot
    slack_bot_thread = threading.Thread(target=lambda: asyncio.run(slack_bot.create_slack_asyncfunc()))
    
    # Create a thread for the database scheduler
    database_scheduler_thread = threading.Thread(target=database_scheduler.start)
    
    # Start both threads
    slack_bot_thread.start()
    database_scheduler_thread.start()

   
    #slack_bot_thread.join()
    #database_scheduler_thread.join()

    
    application.run(debug=True)
