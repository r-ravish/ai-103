"""
backend/routes/bot.py
---------------------
FastAPI routes to handle incoming messages from Microsoft Teams via Bot Framework.
"""
from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, Request, Response
from botbuilder.core import (
    ActivityHandler,
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity

router = APIRouter(tags=["bot"])
logger = logging.getLogger(__name__)

# Initialize the Bot Framework Adapter with credentials from the environment.
APP_ID = os.getenv("MICROSOFT_APP_ID", "")
APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD", "")
settings = BotFrameworkAdapterSettings(app_id=APP_ID, app_password=APP_PASSWORD)
adapter = BotFrameworkAdapter(settings)

class TeamsKnowledgeBot(ActivityHandler):
    """
    Handles incoming activities from the Bot Framework (e.g. Teams).
    Passes text messages to the Azure AI Foundry agent and returns the reply.
    """
    async def on_message_activity(self, turn_context: TurnContext):
        # Local import to avoid circular dependencies with main.py
        from app.main import foundry_service

        if not foundry_service:
            await turn_context.send_activity("The AI Agent service is currently unavailable.")
            return

        question = turn_context.activity.text
        if not question:
            return

        # Send a typing indicator to let the user know we're processing
        typing_activity = Activity(type="typing")
        await turn_context.send_activity(typing_activity)

        try:
            # For this basic integration, we treat each message as a new question.
            # In a full production setup, you would map turn_context.activity.conversation.id
            # to your DB Conversation to persist multi-turn context.
            result = await asyncio.to_thread(
                foundry_service.ask,
                question,
                previous_response_id=None
            )
            
            answer = result.get("answer", "I couldn't find an answer.")
            
            # Optionally append citations if they exist
            citations = result.get("citations", [])
            if citations:
                answer += "\n\n**Sources:**\n"
                for i, c in enumerate(citations):
                    answer += f"- [{i+1}] {c.get('title')}\n"

            await turn_context.send_activity(answer)
        except Exception as e:
            logger.exception("Error processing message in Teams bot:")
            await turn_context.send_activity("I encountered an internal error while processing your request.")

bot_handler = TeamsKnowledgeBot()

@router.post("/api/messages")
async def messages(req: Request):
    """
    Main endpoint for the Microsoft Bot Framework.
    Teams (via Azure Bot Service) will send POST requests here.
    """
    if "application/json" not in req.headers.get("Content-Type", ""):
        return Response(status_code=415)

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    try:
        response = await adapter.process_activity(activity, auth_header, bot_handler.on_turn)
        
        # BotFrameworkAdapter returns an object with a status and body, 
        # but often it's None if no HTTP response is explicitly required.
        if response:
            return Response(status_code=response.status, content=response.body)
        return Response(status_code=201)
    except Exception as e:
        logger.exception("Exception in bot adapter:")
        raise e
