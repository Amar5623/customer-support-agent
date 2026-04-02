# Leafy FAQs — Account & Profile

## "I forgot my password / can't log in"

- Agents cannot see or reset passwords — direct the customer to the "Forgot Password" link on the login page.
- A reset link is sent to the email on the account and expires in 30 minutes.
- If the customer no longer has access to their email address: escalate — identity verification is required before any account change.

---

## "How do I change my email address?"

- Customers can update their email in Account Settings → Profile.
- A verification link is sent to the new email before the change takes effect.
- If the customer cannot access the old email to verify: escalate to the team — identity verification required.
- Agents cannot change email addresses directly.

---

## "How do I delete my account?"

Under GDPR and similar privacy laws, customers have the right to erasure.
- Personal data is anonymised within 30 days of deletion request.
- Order records are retained for 7 years for legal/tax compliance — inform the customer.
- Loyalty points and store credit are forfeited and cannot be recovered after deletion.
- Direct the customer to email support@leafy.store with subject: "Account Deletion Request — [email]"
- Do not process deletion requests via chat — must go through the formal email process.

---

## "How do I unsubscribe from marketing emails?"

- Every Leafy marketing email has an "Unsubscribe" link at the bottom.
- Alternatively: Account Settings → Notifications → uncheck marketing emails.
- Unsubscribing from marketing does NOT affect transactional emails (order confirmations, shipping updates, return notifications).
- Changes take effect within 48 hours.

---

## "My account is suspended — why?"

Use `get_user_profile` — check account status. If suspended, explain the common triggers:
- Suspected payment fraud
- A chargeback was filed without contacting support first
- Unusual return patterns (returning 80%+ of orders over several months)
- Terms of service violation

What agents can do:
- Explain the likely reason based on the account notes.
- Direct the customer to appeal: email support@leafy.store with subject "Account Appeal — [email or order ID]".
- Appeals are reviewed within 5 business days.
- Agents cannot unsuspend accounts — this requires the trust & safety team.

Existing orders in transit will still be fulfilled even for suspended accounts.

---

## "Can I have two accounts?"

No — one account per person per email address is the policy.
Duplicate accounts may be merged or the secondary account suspended.

---

## "How do I update my shipping address?"

- Customers can add/edit saved addresses in Account Settings → Addresses.
- To change the address on an order that's already placed: see the orders FAQ — depends on order status.

---

## "I'm not receiving any emails from Leafy"

1. Check spam/junk folder.
2. Confirm the email address on the account is correct using `get_user_profile`.
3. Check if the customer unsubscribed from all emails (transactional emails should still arrive regardless).
4. If still not receiving: escalate — may be a deliverability issue with their email provider.

---

## "How do I request a copy of my data?"

Customers can request a full data export under their privacy rights.
- Direct them to email support@leafy.store with subject: "Data Export Request — [email]"
- Requests are processed within 30 days.
- Identity verification is required before data is shared.
- Agents cannot generate or send data exports from the chat.
