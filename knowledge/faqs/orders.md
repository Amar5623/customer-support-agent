# Leafy FAQs — Orders & Delivery

## "Where is my order?"

Use the `get_order_details` tool with the customer's order ID.
Walk them through the current status using the status reference below.

| Status | What to tell the customer |
|---|---|
| Processing | "Your order is being prepared — it hasn't shipped yet. Orders placed before 2 PM EST ship same day." |
| Shipped | "Your order is on its way — share the tracking number and carrier name." |
| Out for Delivery | "Good news — your order is with the local driver today." |
| Delivered | "Tracking shows it was delivered on [date]. If you haven't received it, wait 24 hours and then contact us." |
| Delayed | "There's a carrier delay on this one. We're monitoring it — if there's no update in 7 business days we'll file a claim." |
| Returned to Sender | "The package came back to us. Let's sort out the address and get it reshipped at no extra charge." |

---

## "Can I change my delivery address?"

- **Order status = Processing:** Yes — check immediately using `get_order_details`, then escalate to the team to update the address. Do not promise the change has been made until confirmed.
- **Order status = Shipped or later:** No — the package cannot be redirected once in transit. If it comes back to Leafy, we reship at no charge. If it delivers to the wrong address, the customer is responsible.

---

## "My tracking hasn't updated in days"

- Domestic: if no update for **7+ business days**, report to support — Leafy will file a carrier claim.
- International: if no update for **14+ business days**, same process.
- Tracking updates can lag 24–48 hours after the shipping notification — mention this if the order shipped recently.

---

## "I never received a shipping confirmation email"

- Check with `get_order_details` — if status is "Shipped", the tracking number is in the system.
- Ask the customer to check spam/junk folders.
- Offer to resend the shipping notification to their email on file.

---

## "Can I change or add items to my order?"

No — orders cannot be modified once placed. Options:
1. Cancel the order (only if still in "Processing") and reorder with the correct items.
2. Keep the order and place a separate order for the additional items.

---

## "My order arrived but something is missing"

- Verify the order with `get_order_details` — check if it was a multi-item order.
- Some multi-item orders ship in separate packages — check if a second tracking number exists.
- If an item is genuinely missing: escalate immediately with order ID and the missing item name. Do not ask the customer to wait.

---

## "I received the wrong item"

This qualifies as "Wrong item received" — Leafy covers the return shipping.
1. Confirm with `get_order_details` what was supposed to be in the order.
2. Use `check_return_eligibility` and then `initiate_return` with reason = "Wrong item received".
3. A free return label will be provided.
4. Offer a replacement or refund once the return is initiated.
