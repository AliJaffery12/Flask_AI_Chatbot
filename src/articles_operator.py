from requests import Session, Response
from langdetect import detect
import json
from icecream import ic
from requests.auth import HTTPBasicAuth

from src.db.weaviate_facade import WeaviateFacade
from dateutil.parser import parse
import aiohttp
import asyncio
from .util.config import CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN, GPT4_DEPLOYMENT_ID,AZURE_OPENAI_BASE,AZURE_OPENAI_KEY


class ArticlesOperator:
    BASE_URL = "https://digitalcareerinstitute.atlassian.net"

    PROMPT = """
Your task is to answer user's question only based on the provided documentation.
1. Your answer should be as detailed as possible and must include all the necessary information. Provide links to the documents that were used during the answer. Try not to ask additional questions
2. Provide any link with the markdown syntax: [article title](link)
3. Links should lead to https://digitalcareerinstitute.atlassian.net/servicedesk/customer/portal/1/article/ + ARTICLE_ID
4. Only if user needs to pass any document or request regarding theses topics:
    Absence reporting
    You missed a class and have problems with the reporting.

    Federal Employment Agency support
    You need help communicating with Jobcenter or Agentur für Arbeit.

    Giving feedback
    Let us know how we can improve.

    Internship registration
    Let us know if you found an internship position.

    Language classes
    Do you have a request about the language class?

    Any other issue
    Anything else that is on your mind.

    Official documents
    You need some paperwork from us.

    Job registration
    You got a job? Great – tell us all about it!

    Tutorship
    You are a tutor in your class and have a request.

    Technical Issues
    A device or program doesn't work.

    Leave requests
    You want to request a special leave (needs to be confirmed by job agent first).
Then:
    Give them this link: https://digitalcareerinstitute.atlassian.net/servicedesk/customer/portal/1

Documentation: {documentation}
"""

    def __init__(self, recreate_schema=False):
        self.pages = []
        self.CONFLUENCE_USERNAME = CONFLUENCE_USERNAME
        self.CONFLUENCE_API_TOKEN = CONFLUENCE_API_TOKEN
        self.DEPLOYMENT_ID = GPT4_DEPLOYMENT_ID
        self._client = WeaviateFacade(recreate_schema)
      

    def sync_data(self) -> None:
        """
            This function synchronizes the data between the local pages and the Weaviate database.
            It performs the following steps:
            1. Downloads the pages
            2. Prepares the data for upload
            3. Determines which pages to upload and delete
            4. Uploads the pages to Weaviate
            5. Deletes the pages from Weaviate if necessary
        """
        # Download the pages from Confluence
        self._download_pages()
        pages_with_text = [page for page in self.pages if page.get("text") != ""]

        # Prepare the data for upload by getting all articles from Weaviate
        weaviate_data = self._get_all_articles()
        last_edited_dates_weaviate = {parse(article.get("last_edited")) for article in weaviate_data if article.get("last_edited")}
        last_edited_dates_pages = {parse(page.get("last_edited")) for page in pages_with_text}

        # Determine which pages to upload and delete based on their last edited dates
        pages_to_upload = [page for page in pages_with_text if parse(page.get("last_edited")) not in last_edited_dates_weaviate]
        pages_to_delete_from_weaviate = [article for article in weaviate_data if parse(article.get("last_edited")) not in last_edited_dates_pages]
       
        # Upload the pages to Weaviate
        if pages_to_upload:
            try:
                self._client.upload_data(pages_to_upload, 'Article')
            except Exception as e:
                ic(f"Failed to upload pages to Weaviate: {e}")
       
        # Delete the pages from Weaviate
        if pages_to_delete_from_weaviate:
            try:
                self._client.delete_data(pages_to_delete_from_weaviate, 'Article')
            except Exception as e:
                ic(f"Failed to delete pages from Weaviate: {e}")
                
    def _get_all_articles(self):
        # it only gives 100 articles, we need to fix that
        class_name = "Article"
        class_properties = ["last_edited"]
        batch_size = 20
        cursor = None
        query = (
            self._client.query.get(class_name, class_properties)
            .with_additional(["id"])
            .with_limit(batch_size)
        )

        data = []
        while True:
            if cursor is not None:
                results = query.with_after(cursor).do()

            else:
                results = query.do()

            if len(results["data"]["Get"][class_name]) == 0:
                break

            data.extend(results["data"]["Get"][class_name])

            cursor = results["data"]["Get"][class_name][-1]["_additional"]["id"]


        ic(f'Total of {len(data)} articles')
        return data

    async def ask_question(self, query: str, limit=5, verbose=False) -> str:
        """
        Use search query to answer questions about articles.
        """
        print("Ask Quesstion is runing")
        # Get the documentation from search_articles
        documentation = self._client.search_articles(query, limit)
        pages = documentation['data']['Get']['Article']

        # Get all the pages text and article id
        pages_text = ""
        for i, page in enumerate(reversed(pages)):
            page_text = page.get("text", "").replace("`", "")
            article_id = page.get("article_id", "")
            pages_text += f"Document {i+1}: (link: https://digitalcareerinstitute.atlassian.net/servicedesk/customer/portal/1/article/{article_id})\n```Text: {page_text}```\n\n"

        if verbose:
            ic(pages_text)

        # Prepare the request
        data = {
            "messages": [
                {"role": "system",
                 "content": f"{self.PROMPT.format(documentation=documentation)}"},
                {"role": "user", "content": query}
            ]
        }

        url = f"{AZURE_OPENAI_BASE}/openai/deployments/{self.DEPLOYMENT_ID}/chat/completions?api-version=2023-05-15"
        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_KEY
        }

        # Use aiohttp for asynchronous HTTP requests
        async with aiohttp.ClientSession() as session:
            retries = 0
            while retries < 3:
                async with session.post(url, headers=headers, json=data) as response:
                    if (await response.json()).get('error', {}).get('code') == 'InternalServerError':
                        ic(await response.json())
                        await asyncio.sleep(3)
                        retries += 1
                        ic("Failed to get an answer. Retrying...")
                    else:
                        if retries > 0:
                            ic("Retry successful!")
                        break

            try:
                answer = (await response.json())['choices'][0]['message']['content']
            except KeyError:
                ic(await response.json())
                raise Exception("Failed to get answer from OpenAI")

        return answer

    @classmethod
    def _adf_to_plain_text(cls, node, is_root=True):
        """Convert an ADF node to its plain text representation, ensuring better spacing between block elements."""
        node_type = node.get("type", "")

        # Base case: if the node is a text node
        if node_type == "text":
            text = node.get("text", "")
            marks = node.get("marks", [])

            for mark in marks:
                mark_type = mark.get("type", "")
                # Handle some of the marks. Others can be added as needed.
                if mark_type == "link":
                    url = mark.get("attrs", {}).get("href", "")
                    text = f"{text} <{url}>"
                # Other mark types can be added here as required

            return text

        # If the node is a list item, add a newline at the end
        elif node_type == "listItem":
            return "".join(
                cls._adf_to_plain_text(child_node, is_root=False) for child_node in node.get("content", [])) + "\n"

        # If the node is a code block, wrap the content in backticks
        elif node_type == "codeBlock":
            return f"```\n{''.join(cls._adf_to_plain_text(child_node, is_root=False) for child_node in node.get('content', []))}\n```\n"

        # If the node is a bullet list, add bullet points before each item
        elif node_type == "bulletList":
            return "\n".join(
                f"- {cls._adf_to_plain_text(child_node, is_root=False)}" for child_node in node.get("content", []))

        # Recursive case: if the node has content
        content = node.get("content", [])

        # Add a newline between block elements but not within inline content
        separator = "\n" if is_root else ""
        return separator.join(cls._adf_to_plain_text(child_node, is_root=False) for child_node in content).strip()

    def _download_pages(self) -> None:
        """
            Downloads the pages from Confluence and stores them in the `pages` attribute.

            This method uses the Confluence API to retrieve the pages from a specific space.
            It authenticates using the provided username and API token, and retrieves the pages
            in batches of 250. The retrieved pages are then processed and stored in the `pages`
            attribute of the class.

            Returns:
                None
        """
        auth = HTTPBasicAuth(self.CONFLUENCE_USERNAME, self.CONFLUENCE_API_TOKEN)
        endpoint = f"/wiki/api/v2/spaces/1474564/pages?body-format=atlas_doc_format&status=current&limit=250"
        headers = {"Accept": "application/json"}

        page_values = []
        with Session() as session:
            session.auth = auth
            session.headers.update(headers)

            while True:
                response = self._make_request(session, endpoint)
                if response is None:
                    break

                json_data = response.json()
                page_values.extend(self._process_pages(json_data))

                endpoint = self._get_next_endpoint(json_data)

        self.pages = page_values

    def _make_request(self, session, endpoint)-> Response or None:
        try:
            response = session.get(self.BASE_URL + endpoint)
            response.raise_for_status()
            return response
        except Exception as e:
            ic(f'HTTP request failed: {e}')
            return None

    def _process_pages(self, json_data) -> list:
        page_values = []
        for page in json_data['results']:
            page_value = self._process_page(page)
            page_values.append(page_value)
        return page_values

    def _process_page(self, page):
        text = self._adf_to_plain_text(json.loads(page['body']['atlas_doc_format']['value']))
        page_value = {
            'article_id': page['id'],
            'title': page['title'],
            'last_edited': page['version']['createdAt'],
            'text': text,
            'words': len(text.split())
        }

        # Detect the language of the page
        try:
            if text.strip():
                page_value['language'] = detect(text)
            else:
                page_value['language'] = 'unknown'
        except Exception as e:
            ic(f'Language detection failed for a page: {e}')
            page_value['language'] = 'unknown'

        return page_value

    def _get_next_endpoint(self, json_data):
        return json_data['_links']['next'] if 'next' in json_data['_links'] else None
