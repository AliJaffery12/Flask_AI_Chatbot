import re
import logging
import asyncio
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from icecream import ic
from src.articles_operator import ArticlesOperator
from .util.config import SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SlackBotFacade:
    def __init__(self):

        self.app = AsyncApp(
            token = SLACK_BOT_TOKEN,
            signing_secret = SLACK_SIGNING_SECRET
        )
        self.operator = ArticlesOperator()

    def start(self):
        asyncio.run(self.create_slack_asyncfunc())


    async def create_slack_asyncfunc(self):
        @self.app.event("message")
        async def message_hello(message, say):
            message_text = self.extract_text_from_blocks(message)
            ic(message_text)
            ic(await say("Searching for the answer... 🔎"))

            answer = await self.operator.ask_question(message_text)
            slack_formatted_answer = self.convert_text_for_slack(answer)
            await say(slack_formatted_answer)

        handler = AsyncSocketModeHandler(self.app, SLACK_APP_TOKEN)
        await handler.start_async()

    def extract_text_from_blocks(self, data):
        """
        Extracts plain text from the given data structure.
        """
        blocks = data.get('blocks', [])

        texts = []

        for block in blocks:
            block_elements = block.get('elements', [])

            for element in block_elements:
                if element['type'] == 'rich_text_section':
                    nested_elements = element.get('elements', [])

                    for nested_element in nested_elements:
                        if nested_element['type'] == 'text':
                            texts.append(nested_element['text'])

        # Join all the extracted texts
        plain_text = ' '.join(texts)
        return plain_text
   
    @staticmethod
    def convert_text_for_slack(text: str) -> dict:
        """
        Converts links in the given text to the Slack format.

        Args:
            text (str): The text containing links in the format [text](url).

        Returns:
            dict: The payload containing the converted text in the Slack format.
        """
        # Convert markdown links to Slack's mrkdwn format
        text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<\2|\1>', text)
        
        # Convert bullet list markdown to Slack's mrkdwn format
        text = re.sub(r'^-\s', r' •  ', text, flags=re.MULTILINE)

        # Convert bold text
        text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
        
        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text 
                    }
                }
            ]
        }

        return payload
    