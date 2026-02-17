import reflex as rx
from app.components.sidebar import sidebar
from app.components.stats_cards import stats_grid
from app.components.charts import (
    tickets_pie_chart,
    refunds_area_chart,
    payments_bar_chart,
)
from app.states.dashboard_state import DashboardState
from app.states.tickets_state import TicketsState
from app.states.refunds_state import RefundsState
from app.states.payments_state import PaymentsState
from app.components.tickets_view import tickets_view
from app.components.refunds_view import refunds_view
from app.components.payments_view import payments_view
from app.components.chat_view import chat_view
from app.db import ensure_schema
import logging

_db_error: str | None = None
try:
    ensure_schema()
except Exception as e:
    _db_error = str(e)
    logging.error(
        f"Database initialization failed — the app will start but data operations will fail: {e}"
    )


def dashboard_content() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h1(
                "Dashboard Overview", class_name="text-2xl font-bold text-gray-900"
            ),
            rx.el.p(
                "Welcome back, here's what's happening today.",
                class_name="text-sm text-gray-500 mt-1",
            ),
            class_name="mb-8",
        ),
        stats_grid(),
        rx.el.div(
            refunds_area_chart(),
            tickets_pie_chart(),
            class_name="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6",
        ),
        rx.el.div(
            payments_bar_chart(),
            rx.el.div(
                rx.el.h3(
                    "Quick Actions", class_name="text-lg font-bold text-gray-900 mb-4"
                ),
                rx.el.div(
                    rx.el.button(
                        rx.icon("plus", class_name="w-4 h-4 mr-2"),
                        "New Support Ticket",
                        class_name="w-full flex items-center justify-center px-4 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors font-medium text-sm mb-3",
                        on_click=rx.redirect("/tickets?new=true"),
                    ),
                    rx.el.button(
                        rx.icon("search", class_name="w-4 h-4 mr-2"),
                        "Search Records",
                        class_name="w-full flex items-center justify-center px-4 py-3 bg-white border border-gray-200 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors font-medium text-sm mb-3",
                        on_click=rx.redirect("/tickets"),
                    ),
                    rx.el.button(
                        rx.icon("message-square", class_name="w-4 h-4 mr-2"),
                        "Ask AI Assistant",
                        class_name="w-full flex items-center justify-center px-4 py-3 bg-white border border-gray-200 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors font-medium text-sm",
                        on_click=rx.redirect("/chat"),
                    ),
                    class_name="flex flex-col",
                ),
                class_name="bg-white p-6 rounded-2xl shadow-sm border border-gray-100",
            ),
            class_name="grid grid-cols-1 lg:grid-cols-2 gap-6",
        ),
        class_name="max-w-7xl mx-auto",
    )


def index() -> rx.Component:
    return rx.el.div(
        sidebar(),
        rx.el.main(
            rx.cond(
                DashboardState.is_loading,
                rx.el.div(
                    rx.spinner(size="3"),
                    class_name="flex items-center justify-center w-full h-full min-h-[50vh]",
                ),
                dashboard_content(),
            ),
            class_name="flex-1 md:ml-72 p-4 md:p-8 min-h-screen bg-gray-50/50",
        ),
        class_name="flex min-h-screen font-['Inter']",
    )


def tickets_page() -> rx.Component:
    return rx.el.div(
        sidebar(), tickets_view(), class_name="flex min-h-screen font-['Inter']"
    )


def refunds_page() -> rx.Component:
    return rx.el.div(
        sidebar(), refunds_view(), class_name="flex min-h-screen font-['Inter']"
    )


def payments_page() -> rx.Component:
    return rx.el.div(
        sidebar(), payments_view(), class_name="flex min-h-screen font-['Inter']"
    )


def chat_page() -> rx.Component:
    return rx.el.div(
        sidebar(), chat_view(), class_name="flex min-h-screen font-['Inter']"
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index, route="/", on_load=DashboardState.fetch_dashboard_data)
app.add_page(tickets_page, route="/tickets", on_load=TicketsState.fetch_tickets)
app.add_page(refunds_page, route="/refunds", on_load=RefundsState.fetch_refunds)
app.add_page(payments_page, route="/payments", on_load=PaymentsState.fetch_payments)
app.add_page(chat_page, route="/chat")