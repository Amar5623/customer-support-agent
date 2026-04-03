# backend/tools/mongo_tools.py

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.tools.base import BaseTool

logger = logging.getLogger(__name__)


def _serialize(doc: dict) -> dict:
    """Convert MongoDB doc to JSON-serializable dict."""
    if doc is None:
        return {}
    result = {}
    for k, v in doc.items():
        if k == "_id":
            result[k] = str(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, dict):
            result[k] = _serialize(v)
        elif isinstance(v, list):
            result[k] = [
                _serialize(i) if isinstance(i, dict) else str(i) if isinstance(i, ObjectId) else i
                for i in v
            ]
        else:
            result[k] = v
    return result


# ── 1. Get Order Details ────────────────────────────────────────────────────────

class GetOrderDetails(BaseTool):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    @property
    def name(self) -> str:
        return "get_order_details"

    @property
    def description(self) -> str:
        return (
            "Retrieve full details of a specific order by its order ID. "
            "Returns order status, products, shipping address, estimated dates, "
            "and status history. Use when the customer asks about a specific order."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The MongoDB order ID (e.g. 682b73a0463e7f2b09ed2b1a)"
                }
            },
            "required": ["order_id"]
        }

    async def execute(self, **kwargs: Any) -> dict:
        order_id = kwargs.get("order_id", "").strip()
        if not order_id:
            return self.error("order_id is required.")

        try:
            oid = ObjectId(order_id)
        except Exception:
            return self.error(f"'{order_id}' is not a valid order ID format.")

        try:
            order = await self._db.orders.find_one({"_id": oid})
            if not order:
                return self.error(f"No order found with ID {order_id}.")

            # Enrich with invoice if available
            invoice = None
            if order.get("invoiceId"):
                try:
                    inv_id = ObjectId(str(order["invoiceId"]))
                    invoice = await self._db.invoices.find_one({"_id": inv_id})
                except Exception:
                    pass

            data = _serialize(order)

            # Attach payment summary from invoice if found
            if invoice:
                erp = invoice.get("metadata", {}).get("erpDetails", {})
                data["payment_summary"] = {
                    "total_amount": invoice.get("totalAmount"),
                    "status": invoice.get("status"),
                    "due_date": erp.get("dueDate"),
                }

            return self.success(data)

        except Exception as e:
            logger.exception(f"get_order_details failed for {order_id}")
            return self.error(f"Failed to retrieve order: {str(e)}")


# ── 2. Get User Profile ─────────────────────────────────────────────────────────

class GetUserProfile(BaseTool):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    @property
    def name(self) -> str:
        return "get_user_profile"

    @property
    def description(self) -> str:
        return (
            "Retrieve a customer's profile by their email address. "
            "Returns name, account status, loyalty tier, loyalty points, "
            "and contact details. Use when the customer asks about their account."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The customer's email address"
                }
            },
            "required": ["email"]
        }

    async def execute(self, **kwargs: Any) -> dict:
        email = kwargs.get("email", "").strip().lower()
        if not email:
            return self.error("email is required.")

        try:
            user = await self._db.users.find_one(
                {"email": {"$regex": f"^{email}$", "$options": "i"}},
                # Never expose sensitive internals
                {"lastRecommendations": 0, "vai_text_embedding": 0}
            )
            if not user:
                return self.error(f"No account found for email: {email}")

            return self.success(_serialize(user))

        except Exception as e:
            logger.exception(f"get_user_profile failed for {email}")
            return self.error(f"Failed to retrieve profile: {str(e)}")


# ── 3. Get Order History ────────────────────────────────────────────────────────

class GetOrderHistory(BaseTool):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    @property
    def name(self) -> str:
        return "get_order_history"

    @property
    def description(self) -> str:
        return (
            "Retrieve all orders for a customer using their email address. "
            "Returns a summary list of orders with status and total amount. "
            "Use when the customer asks 'what are my orders' or 'my order history'."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The customer's email address"
                }
            },
            "required": ["email"]
        }

    async def execute(self, **kwargs: Any) -> dict:
        email = kwargs.get("email", "").strip().lower()
        if not email:
            return self.error("email is required.")

        try:
            user = await self._db.users.find_one(
                {"email": {"$regex": f"^{email}$", "$options": "i"}},
                {"_id": 1}
            )
            if not user:
                return self.error(f"No account found for email: {email}")

            cursor = self._db.orders.find(
                {"userId": user["_id"]},
                {
                    "_id": 1,
                    "status": 1,
                    "createdAt": 1,
                    "estimated_destination_date": 1,
                    "products": 1,
                }
            ).sort("createdAt", -1).limit(10)

            orders = []
            async for order in cursor:
                products = order.get("products", [])
                orders.append({
                    "order_id": str(order["_id"]),
                    "status": order.get("status"),
                    "created_at": (
                        order["createdAt"].isoformat()
                        if isinstance(order.get("createdAt"), datetime)
                        else str(order.get("createdAt"))
                    ),
                    "estimated_delivery": (
                        order["estimated_destination_date"].isoformat()
                        if isinstance(order.get("estimated_destination_date"), datetime)
                        else None
                    ),
                    "item_count": len(products),
                    "items": [p.get("name", "Unknown") for p in products[:3]]
                })

            if not orders:
                return self.success({
                    "orders": [],
                    "message": "No orders found for this account."
                })

            return self.success({"orders": orders, "total": len(orders)})

        except Exception as e:
            logger.exception(f"get_order_history failed for {email}")
            return self.error(f"Failed to retrieve order history: {str(e)}")


# ── 4. Get Return Status ────────────────────────────────────────────────────────

class GetReturnStatus(BaseTool):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    @property
    def name(self) -> str:
        return "get_return_status"

    @property
    def description(self) -> str:
        return (
            "Retrieve the return/refund status for a specific order. "
            "Returns return status, items being returned, refund amount, and timeline. "
            "Use when the customer asks about a return or refund."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID to look up the return for"
                }
            },
            "required": ["order_id"]
        }

    async def execute(self, **kwargs: Any) -> dict:
        order_id = kwargs.get("order_id", "").strip()
        if not order_id:
            return self.error("order_id is required.")

        # FIX: orderId is stored as ObjectId in the returns collection, not a string.
        # Passing a raw string to find_one() would never match — convert first.
        try:
            oid = ObjectId(order_id)
        except Exception:
            return self.error(f"'{order_id}' is not a valid order ID format.")

        try:
            ret = await self._db.returns.find_one({"orderId": oid})
            if not ret:
                return self.error(f"No return found for order {order_id}.")

            return self.success(_serialize(ret))

        except Exception as e:
            logger.exception(f"get_return_status failed for {order_id}")
            return self.error(f"Failed to retrieve return status: {str(e)}")


# ── 5. Change Delivery Date ─────────────────────────────────────────────────────


class ChangeDeliveryDate(BaseTool):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    @property
    def name(self) -> str:
        return "change_delivery_date"

    @property
    def description(self) -> str:
        return (
            "Request a change to the estimated delivery date of an order. "
            "Automatically approves or rejects based on warehouse schedule. "
            "Use when the customer asks to change, reschedule, or delay their delivery."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID to change delivery date for"
                },
                "requested_date": {
                    "type": "string",
                    "description": "Requested new delivery date in YYYY-MM-DD format"
                }
            },
            "required": ["order_id", "requested_date"]
        }

    async def execute(self, **kwargs: Any) -> dict:
        order_id       = kwargs.get("order_id", "").strip()
        requested_date = kwargs.get("requested_date", "").strip()

        if not order_id or not requested_date:
            return self.error("Both order_id and requested_date are required.")

        try:
            req_dt = datetime.strptime(requested_date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return self.error(
                f"Invalid date format '{requested_date}'. Please use YYYY-MM-DD."
            )

        try:
            oid = ObjectId(order_id)
        except Exception:
            return self.error(f"'{order_id}' is not a valid order ID.")

        try:
            order = await self._db.orders.find_one(
                {"_id": oid},
                {
                    "status": 1,
                    "userId": 1,
                    "estimated_warehouse_date": 1,
                    "estimated_destination_date": 1,
                    "delivery_date_change_request": 1,
                    "products": 1,
                }
            )
            if not order:
                return self.error(f"No order found with ID {order_id}.")

            status = order.get("status", "")

            # 1. Terminal states
            if status in ("Delivered", "Completed", "Cancelled"):
                return self.success({
                    "outcome": "rejected",
                    "reason": (
                        f"Your order is already '{status}' — "
                        "the delivery date cannot be changed at this stage."
                    ),
                    "order_id": order_id,
                })

            # 2. Get warehouse date
            warehouse_dt = order.get("estimated_warehouse_date")
            if not warehouse_dt:
                return self.error(
                    "Order is missing warehouse date — cannot evaluate request."
                )

            if isinstance(warehouse_dt, datetime) and warehouse_dt.tzinfo is None:
                warehouse_dt = warehouse_dt.replace(tzinfo=timezone.utc)

            # 3. Feasibility check first
            if req_dt < warehouse_dt:
                return self.success({
                    "outcome": "rejected",
                    "reason": (
                        f"Your order is estimated to reach our dispatch warehouse on "
                        f"{warehouse_dt.strftime('%B %d, %Y')}. "
                        f"We cannot deliver before that date — "
                        f"the earliest possible delivery is after "
                        f"{warehouse_dt.strftime('%B %d, %Y')}."
                    ),
                    "requested_date": requested_date,
                    "earliest_possible": (
                        warehouse_dt + timedelta(days=1)
                    ).date().isoformat(),
                })

            # 4. Check for existing pending request
            existing = order.get("delivery_date_change_request")
            if existing and existing.get("status") == "pending":
                return self.success({
                    "outcome": "already_pending",
                    "reason": (
                        "There is already a pending date change request for this order. "
                        "Our team is reviewing it and will confirm within 24 hours. "
                        "Please wait for that confirmation before submitting a new request."
                    ),
                    "existing_requested_date": (
                        existing["requested_date"].isoformat()
                        if isinstance(existing.get("requested_date"), datetime)
                        else str(existing.get("requested_date"))
                    ),
                    "request_id": existing.get("request_id"),
                })

            # 5. Feasible + no existing — write to pending_requests collection
            now = datetime.now(timezone.utc)

            pending_doc = {
                "type":               "date_change",
                "status":             "pending",
                "order_id":           oid,
                "user_id":            order.get("userId"),
                "requested_value":    req_dt,
                "current_value":      order.get("estimated_destination_date"),
                "warehouse_date":     warehouse_dt,
                "created_at":         now,
                "resolved_at":        None,
                "resolved_by":        None,
                "resolution_note":    None,
                "session_id":         None,
            }

            result = await self._db.pending_requests.insert_one(pending_doc)
            request_id = str(result.inserted_id)

            # Mirror lightweight reference back to order
            await self._db.orders.update_one(
                {"_id": oid},
                {"$set": {
                    "delivery_date_change_request": {
                        "request_id":     request_id,
                        "status":         "pending",
                        "requested_date": req_dt,
                        "created_at":     now,
                    }
                }}
            )

            return self.success({
                "outcome":   "pending_approval",
                "request_id": request_id,
                "message": (
                    "Your request is possible based on the current warehouse schedule. "
                    "We've flagged it for our team to confirm. "
                    "You'll hear back within 24 hours."
                ),
                "requested_date":            requested_date,
                "earliest_possible_delivery": warehouse_dt.date().isoformat(),
            })

        except Exception as e:
            logger.exception(f"change_delivery_date failed for {order_id}")
            return self.error(f"Failed to process date change request: {str(e)}")

# ── 6. Change Delivery Address ──────────────────────────────────────────────────

class ChangeDeliveryAddress(BaseTool):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    @property
    def name(self) -> str:
        return "change_delivery_address"

    @property
    def description(self) -> str:
        return (
            "Change the delivery address on an order. "
            "Only possible if the order has not yet been shipped. "
            "Use when the customer wants to update where their order is delivered."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID to update the address for"
                },
                "street_and_number": {
                    "type": "string",
                    "description": "New street address and number"
                },
                "city": {
                    "type": "string",
                    "description": "City"
                },
                "country": {
                    "type": "string",
                    "description": "Country"
                },
                "state": {
                    "type": "string",
                    "description": "State or province (optional)"
                },
                "cp": {
                    "type": "string",
                    "description": "Postal / zip code"
                }
            },
            "required": ["order_id", "street_and_number", "city", "country"]
        }

    async def execute(self, **kwargs: Any) -> dict:
        order_id = kwargs.get("order_id", "").strip()
        if not order_id:
            return self.error("order_id is required.")

        try:
            oid = ObjectId(order_id)
        except Exception:
            return self.error(f"'{order_id}' is not a valid order ID.")

        try:
            order = await self._db.orders.find_one(
                {"_id": oid},
                {"status": 1, "shipping_address": 1}
            )
            if not order:
                return self.error(f"No order found with ID {order_id}.")

            status = order.get("status", "")

            if status not in ("In process", "Ready for delivery"):
                return self.success({
                    "outcome": "rejected",
                    "reason": (
                        f"Your order is currently '{status}'. "
                        "Address changes are only possible before the order is shipped. "
                        "Once an order is picked up from the warehouse, "
                        "we can no longer redirect it."
                    ),
                    "current_status": status,
                })

            new_address = {
                "street_and_number": kwargs.get("street_and_number", "").strip(),
                "city":              kwargs.get("city", "").strip(),
                "country":           kwargs.get("country", "").strip(),
                "state":             kwargs.get("state", "").strip(),
                "cp":                kwargs.get("cp", "").strip(),
            }

            await self._db.orders.update_one(
                {"_id": oid},
                {"$set": {"shipping_address": new_address}}
            )

            return self.success({
                "outcome": "updated",
                "message": "Delivery address successfully updated.",
                "new_address": new_address,
                "order_id": order_id,
            })

        except Exception as e:
            logger.exception(f"change_delivery_address failed for {order_id}")
            return self.error(f"Failed to update address: {str(e)}")


# ── Registry — all tools in one place ──────────────────────────────────────────

def get_all_tools(db: AsyncIOMotorDatabase) -> list[BaseTool]:
    """
    Returns all registered tools.
    Import this in container.py — don't instantiate tools individually.

    Usage:
        from backend.tools.mongo_tools import get_all_tools
        tools = get_all_tools(db)
    """
    return [
        GetOrderDetails(db),
        GetUserProfile(db),
        GetOrderHistory(db),
        GetReturnStatus(db),
        ChangeDeliveryDate(db),
        ChangeDeliveryAddress(db),
    ]