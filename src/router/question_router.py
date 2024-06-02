import requests
import os
from flask import Blueprint, request, jsonify
import json
from ..util.config import WS_TOKEN
from ..articles_operator import ArticlesOperator
# from .config import MOODLE_API_TOKEN
import asyncio
from threading import Thread

question_router = Blueprint('question_router', __name__)

MOODLE_API_TOKEN = WS_TOKEN

@question_router.route("/receive_question", methods=["POST"])
def receive_question():
    data = request.json
    user_id = data.get("user_id")
    question = data.get("message")
    token = data.get("token")

    if "token" not in data or data["token"] != MOODLE_API_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if not user_id or not question:
        return jsonify({"error": "Invalid request"}), 400

    # Start the background task for processing the question
    thread = Thread(target=process_question, args=(user_id, question))
    thread.start()

    # Respond immediately to the request
    return jsonify({"message": "Searching for the answer..."}), 202

def process_question(user_id, question):
    loader = ArticlesOperator()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    answer = loop.run_until_complete(loader.ask_question(question))
    print(answer)
    send_answer_to_moodle(user_id, answer)

def send_answer_to_moodle(user_id, answer):
    
    moodle_url = "https://dev.edu.digitalcareerinstitute.org/webservice/rest/server.php?"
    
    # Prepare the headers and data
    headers = {
        
        "Content-Type": "application/json"
    }

    data = {
        
        "user_id":user_id,
        
        "message": answer
    }
    
    params={
        "moodlewsrestformat": "json",
        "wsfunction": "local_chatbot_receive ",  
        "wstoken":MOODLE_API_TOKEN,
    }
   
    # Send the POST request to Moodle
    response = requests.post(moodle_url, headers=headers, params=params, json=data)
    print("sending response  data is",response)
    # Check and log the response
    if response.status_code == 200:
        print("Successfully sent the answer back to Moodle",response.text)
    else:
        print(f"Failed to send the answer. Status Code: {response.status_code}, Response: {response.text}")
