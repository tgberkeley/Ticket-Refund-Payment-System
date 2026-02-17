import reflex as rx
from app.states.dashboard_state import SidebarState


def sidebar_item(label: str, icon: str, href: str) -> rx.Component:
    is_active = rx.cond(
        href == "/",
        SidebarState.current_page == "/",
        SidebarState.current_page.startswith(href),
    )
    return rx.el.a(
        rx.el.div(
            rx.icon(
                icon,
                class_name=rx.cond(
                    is_active, "w-5 h-5 text-indigo-600", "w-5 h-5 text-gray-500"
                ),
            ),
            rx.el.span(
                label,
                class_name=rx.cond(
                    is_active,
                    "font-medium text-indigo-900",
                    "font-medium text-gray-600",
                ),
            ),
            class_name=rx.cond(
                is_active,
                "flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 bg-indigo-50 border border-indigo-100 shadow-sm",
                "flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 hover:bg-gray-50 hover:text-gray-900 border border-transparent",
            ),
        ),
        href=href,
        class_name="w-full",
    )


def sidebar() -> rx.Component:
    return rx.el.aside(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.icon("layout-grid", class_name="w-6 h-6 text-white"),
                    class_name="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-200",
                ),
                rx.el.span(
                    "Admin", class_name="text-xl font-bold text-gray-900 tracking-tight"
                ),
                class_name="flex items-center gap-3 px-4 mb-10",
            ),
            rx.el.nav(
                rx.el.div(
                    rx.el.p(
                        "MAIN MENU",
                        class_name="text-xs font-bold text-gray-400 px-4 mb-4 tracking-wider",
                    ),
                    rx.el.div(
                        sidebar_item("Dashboard", "layout-dashboard", "/"),
                        sidebar_item("Help Tickets", "ticket", "/tickets"),
                        sidebar_item("Refund Requests", "rotate-ccw", "/refunds"),
                        sidebar_item("Payments", "credit-card", "/payments"),
                        sidebar_item("AI Assistant", "message-square", "/chat"),
                        class_name="flex flex-col gap-2",
                    ),
                    class_name="mb-8",
                ),
                class_name="flex-1",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.icon("user", class_name="w-5 h-5 text-gray-600"),
                        class_name="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center border border-gray-200",
                    ),
                    rx.el.div(
                        rx.el.p(
                            "Admin User",
                            class_name="text-sm font-semibold text-gray-900",
                        ),
                        rx.el.p(
                            "admin@company.com", class_name="text-xs text-gray-500"
                        ),
                        class_name="flex flex-col",
                    ),
                    class_name="flex items-center gap-3",
                ),
                class_name="border-t border-gray-100 pt-6 mt-auto",
            ),
            class_name="flex flex-col h-full",
        ),
        class_name="hidden md:flex flex-col w-72 h-screen bg-white border-r border-gray-200 p-6 fixed left-0 top-0 z-50",
    )