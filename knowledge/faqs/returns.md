# Leafy FAQs — Returns & Refunds

## "How long does my refund take?"

Depends on the method the customer chose:

| Refund Method | Timeline |
|---|---|
| Original payment method | 5–7 business days **after item is received at our warehouse** |
| Store credit | Instant — credited on return approval |
| Bank transfer | 7–10 business days after item receipt |

Always clarify: the clock starts when **Leafy receives the item**, not when the customer ships it.
Check `get_return_status` to see the current return status and when the item was received.

---

## "Where is my refund? It's been over a week."

1. Use `get_return_status` — check if status is "Item Received" or "Refund Issued".
2. If "Refund Issued": the refund has been processed on our end. Bank processing times are outside our control — standard payment method refunds take 5–7 business days from issue date.
3. If still "Item Received" with no movement after 3+ business days: escalate — this needs warehouse team review.
4. If "Approved" but item not yet received: ask when the customer shipped it and whether they have a tracking number for the return shipment.

---

## "I never received my RMA / return authorisation"

- RMA is sent to the email address on the account after return is approved.
- Ask the customer to check spam/junk.
- Use `get_return_status` — if return is "Approved", the RMA was issued. Offer to resend to their email.
- If return is still "Requested", it hasn't been approved yet — check if it's within the return window and eligibility criteria are met.

---

## "Can I return without the original packaging / tags?"

No — items must be in original packaging with tags attached to be accepted.
If tags are removed or packaging is missing, the return will be rejected on inspection.
Be honest with the customer upfront rather than let them ship back and get rejected.

---

## "My return was rejected — why?"

Common rejection reasons (visible in return status):
- Outside the return window (30 days standard, 45 for Platinum)
- Item arrived damaged by customer (not an original defect)
- Tags removed or packaging missing
- Non-returnable item category (underwear, swimwear, pierced jewellery, Final Sale)

What to do:
- Explain the specific reason clearly and sympathetically.
- If the customer disputes it (e.g. claims damage was pre-existing), escalate — do not override.

---

## "Can I get store credit instead of a refund to my card?"

Yes — store credit can be chosen at any point before the refund is issued.
Store credit gets a **+10% bonus** (e.g. $50 item → $55 credit) and is issued instantly on return approval.
Use `get_return_status` — if refund hasn't been issued yet, the customer can still switch.

---

## "I returned an item but my loyalty points weren't credited"

Points are awarded after the order's return window closes — not immediately after delivery.
If an item was returned, points for that item are not awarded (only shipped and kept items earn points).
This is by design — confirm to the customer and check their points balance with `get_user_profile`.

---

## "I didn't use a return label — did I need to?"

- **Defective / wrong item / not as described:** Leafy provides a free return label. If the customer shipped without one and paid, escalate to review reimbursement — requires manager discretion.
- **Changed mind / size issue:** Customer pays return shipping. No reimbursement available.
- **Platinum members:** Free return labels on ALL returns — same escalation if they paid out of pocket.
