import reflex as rx
from typing import Optional, TypedDict
from app.db import fetch_all, fetch_one
import datetime
import logging


class TicketStatusData(TypedDict):
    name: str
    value: int
    fill: str


class PaymentStatusData(TypedDict):
    name: str
    count: int
    amount: float
    fill: str


class RefundTrendData(TypedDict):
    date: str
    count: int


class SidebarState(rx.State):
    @rx.var
    def current_page(self) -> str:
        path = self.router.url.path
        return "/" if not path else path


class DashboardState(rx.State):
    total_tickets: int = 0
    tickets_open_count: int = 0
    total_refunds_pending: int = 0
    refund_approval_rate: float = 0.0
    total_payment_volume: float = 0.0
    payment_success_rate: float = 0.0
    ticket_status_data: list[TicketStatusData] = []
    payment_status_data: list[PaymentStatusData] = []
    refunds_over_time: list[RefundTrendData] = []
    is_loading: bool = False

    @rx.event(background=True)
    async def fetch_dashboard_data(self):
        async with self:
            self.is_loading = True
        try:
            ticket_rows = await fetch_all("""
                SELECT status, COUNT(*) as count 
                FROM help_ticket 
                GROUP BY status
            """)
            status_colors = {
                "open": "#10B981",
                "pending": "#F59E0B",
                "resolved": "#3B82F6",
                "closed": "#6B7280",
            }
            temp_ticket_data = []
            total_t = 0
            open_t = 0
            for row in ticket_rows:
                status = row[0]
                count = row[1]
                total_t += count
                if status == "open":
                    open_t = count
                temp_ticket_data.append(
                    {
                        "name": status.title(),
                        "value": count,
                        "fill": status_colors.get(status, "#6B7280"),
                    }
                )
            refund_metrics = await fetch_one("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN approved IS NULL THEN 1 END) as pending,
                    COUNT(CASE WHEN approved = TRUE THEN 1 END) as approved
                FROM refund_requests
            """)
            total_r = refund_metrics[0] if refund_metrics else 0
            pending_r = refund_metrics[1] if refund_metrics else 0
            approved_r = refund_metrics[2] if refund_metrics else 0
            approval_rate = approved_r / total_r * 100 if total_r > 0 else 0.0
            refund_trend_rows = await fetch_all("""
                SELECT DATE(request_date) as r_date, COUNT(*) as count
                FROM refund_requests
                GROUP BY DATE(request_date)
                ORDER BY r_date ASC
            """)
            temp_refund_trend = []
            for row in refund_trend_rows:
                if row[0]:
                    temp_refund_trend.append(
                        {"date": row[0].strftime("%b %d"), "count": row[1]}
                    )
            payment_rows = await fetch_all("""
                SELECT payment_status, COUNT(*), SUM(amount_cents)
                FROM stripe_payments
                GROUP BY payment_status
            """)
            payment_colors = {
                "succeeded": "#10B981",
                "failed": "#EF4444",
                "pending": "#F59E0B",
                "refunded": "#8B5CF6",
            }
            temp_payment_data = []
            total_payments_count = 0
            succeeded_count = 0
            total_volume_cents = 0
            for row in payment_rows:
                status = row[0]
                count = row[1]
                amount_cents = row[2] or 0
                total_payments_count += count
                if status == "succeeded":
                    succeeded_count = count
                    total_volume_cents += amount_cents
                temp_payment_data.append(
                    {
                        "name": status.title(),
                        "count": count,
                        "amount": amount_cents / 100.0,
                        "fill": payment_colors.get(status, "#6B7280"),
                    }
                )
            success_rate = (
                succeeded_count / total_payments_count * 100
                if total_payments_count > 0
                else 0.0
            )
            async with self:
                self.total_tickets = total_t
                self.tickets_open_count = open_t
                self.ticket_status_data = temp_ticket_data
                self.total_refunds_pending = pending_r
                self.refund_approval_rate = round(approval_rate, 1)
                self.refunds_over_time = temp_refund_trend
                self.total_payment_volume = round(total_volume_cents / 100.0, 2)
                self.payment_success_rate = round(success_rate, 1)
                self.payment_status_data = temp_payment_data
                self.is_loading = False
        except Exception as e:
            logging.exception(f"Dashboard Error: {e}")
            async with self:
                self.is_loading = False