import reflex as rx
import os
from typing import Any
from openai import AsyncOpenAI
from databricks.sdk import WorkspaceClient
from app.db import fetch_all
import logging
import json

LLM_MODEL = os.environ.get("DATABRICKS_LLM_MODEL", "databricks-claude-sonnet-4-5")


class ChatState(rx.State):
    messages: list[dict[str, str]] = [
        {
            "role": "assistant",
            "content": "Hello! I'm your AI assistant. I have access to your Help Tickets, Refund Requests, and Payment records. How can I help you today?",
        }
    ]
    loading: bool = False
    context_selector: str = "all"

    @rx.event
    def set_context(self, value: str):
        self.context_selector = value

    @rx.event
    def clear_chat(self):
        self.messages = [
            {
                "role": "assistant",
                "content": "Chat history cleared. How can I help you?",
            }
        ]

    @rx.event(background=True)
    async def send_message(self, form_data: dict[str, Any]):
        user_msg = form_data.get("message_input", "").strip()
        if not user_msg:
            return
        async with self:
            self.messages.append({"role": "user", "content": user_msg})
            self.loading = True
            current_context = self.context_selector
        yield
        data_context = ""
        try:
            if current_context in ["all", "tickets"]:
                t_rows_stats = await fetch_all(
                    "SELECT status, COUNT(*) FROM help_ticket GROUP BY status"
                )
                t_stats = {row[0]: row[1] for row in t_rows_stats}
                t_recent_rows = await fetch_all(
                    "SELECT ticket_id, subject, status, customer_id FROM help_ticket ORDER BY created_at DESC LIMIT 10"
                )
                t_rows = [
                    dict(zip(["id", "subject", "status", "customer"], row))
                    for row in t_recent_rows
                ]
                data_context += f"\nTICKET STATISTICS:\n{json.dumps(t_stats)}\nRECENT TICKETS:\n{json.dumps(t_rows)}\n"
            if current_context in ["all", "refunds"]:
                r_rows_stats = await fetch_all(
                    "SELECT approved, COUNT(*) FROM refund_requests GROUP BY approved"
                )
                r_stats = {str(row[0]): row[1] for row in r_rows_stats}
                r_recent_rows = await fetch_all(
                    "SELECT refund_id, amount_cents, sku, approved FROM refund_requests LEFT JOIN stripe_payments ON refund_requests.payment_id = stripe_payments.payment_id ORDER BY request_date DESC LIMIT 10"
                )
                r_rows = []
                for row in r_recent_rows:
                    r_rows.append(
                        {
                            "id": row[0],
                            "amount": f"${(row[1] or 0) / 100:.2f}",
                            "sku": row[2],
                            "approved": str(row[3]),
                        }
                    )
                data_context += f"\nREFUND STATISTICS (None=Pending):\n{json.dumps(r_stats)}\nRECENT REFUNDS:\n{json.dumps(r_rows)}\n"
            if current_context in ["all", "payments"]:
                p_rows_stats = await fetch_all(
                    "SELECT payment_status, COUNT(*), SUM(amount_cents) FROM stripe_payments GROUP BY payment_status"
                )
                p_stats = []
                for row in p_rows_stats:
                    p_stats.append(
                        {
                            "status": row[0],
                            "count": row[1],
                            "volume": f"${(row[2] or 0) / 100:.2f}",
                        }
                    )
                p_recent_rows = await fetch_all(
                    "SELECT payment_id, amount_cents, payment_status, customer_id FROM stripe_payments ORDER BY payment_date DESC LIMIT 10"
                )
                p_rows = [
                    dict(
                        zip(
                            ["id", "amount", "status", "customer"],
                            [row[0], f"${(row[1] or 0) / 100:.2f}", row[2], row[3]],
                        )
                    )
                    for row in p_recent_rows
                ]
                data_context += f"\nPAYMENT STATISTICS:\n{json.dumps(p_stats)}\nRECENT PAYMENTS:\n{json.dumps(p_rows)}\n"
        except Exception as e:
            logging.exception(f"Error fetching context data: {e}")
            data_context = (
                "Error retrieving live data. Please answer based on general knowledge."
            )
        system_prompt = f"\n        You are a helpful AI assistant for a Customer Support Admin Dashboard.\n        You have access to the following REAL-TIME database records:\n        \n        {data_context}\n        \n        Instructions:\n        1. Use the provided data to answer specific questions about tickets, refunds, or payments.\n        2. If the data is present, cite specific numbers or IDs.\n        3. If the user asks about data not shown here, politely explain you only see the recent 10 records and summary stats.\n        4. Be concise, professional, and helpful.\n        "
        try:
            w = WorkspaceClient()
            host = w.config.host
            if not host.startswith("http"):
                host = f"https://{host}"
            auth_headers = w.config.authenticate()
            token = auth_headers.get("Authorization", "").replace("Bearer ", "")
        except Exception as e:
            logging.exception(f"Databricks auth error: {e}")
            async with self:
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": "AI chat requires a Databricks workspace with Foundation Model Serving. "
                        "Could not authenticate — please check that DATABRICKS_HOST is set and your credentials are configured.",
                    }
                )
                self.loading = False
            return
        if not token or not host:
            async with self:
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": "Error: Could not authenticate with Databricks. Please check DATABRICKS_HOST and Service Principal credentials.",
                    }
                )
                self.loading = False
            return
        try:
            client = AsyncOpenAI(api_key=token, base_url=f"{host}/serving-endpoints")
            api_messages = [{"role": "system", "content": system_prompt}]
            api_messages.extend(
                [m for m in self.messages if m["role"] != "system"][-10:]
            )
            response = await client.chat.completions.create(
                messages=api_messages,
                model=LLM_MODEL,
                max_tokens=512,
                temperature=0.5,
                stream=True,
            )
            async with self:
                self.messages.append({"role": "assistant", "content": ""})
            yield
            current_content = ""
            async for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    content_chunk = chunk.choices[0].delta.content
                    current_content += content_chunk
                    async with self:
                        self.messages[-1]["content"] = current_content
                    yield
        except Exception as e:
            logging.exception(f"LLM Error: {e}")
            error_hint = str(e)
            if "404" in error_hint or "not found" in error_hint.lower():
                friendly = (
                    f"The model endpoint `{LLM_MODEL}` was not found. "
                    "Make sure Foundation Model Serving is enabled in your Databricks workspace "
                    "and the model is available. You can override the model name with the "
                    "DATABRICKS_LLM_MODEL environment variable."
                )
            else:
                friendly = f"I encountered an error connecting to the AI service: {error_hint}"
            async with self:
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": friendly,
                    }
                )
        finally:
            async with self:
                self.loading = False