from flask import Blueprint
from sentry_sdk import capture_exception
from ..articles_operator import ArticlesOperator
from ..util.config import SLACK_APP_TOKEN,SLACK_BOT_TOKEN,SLACK_SIGNING_SECRET
from src.slack_app import SlackBotFacade
articles = Blueprint('articles', __name__)

@articles.route("/load")
def load_articles():
    try:
        loader = ArticlesOperator()
        bot= SlackBotFacade()
        loader.sync_data()
        
        bot.start()
        slack_app_token = SLACK_APP_TOKEN
        slack_bot_token = SLACK_BOT_TOKEN
        response_html = f"<p>Articles loaded successfully! Slack App Token: {slack_app_token}, Slack Bot Token: {slack_bot_token}</p>"
        return response_html
    except Exception as e:
        capture_exception(e)
        return "<p>Error occurred. The error has been reported to Sentry.</p>"