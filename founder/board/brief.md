# Board brief — BusinessOS

> This brief stands alone. You (the board member) cannot see the conversation it came from. Everything you need is here. It is drawn from the founder's seed pitch; treat the claims as the founder's claims, and test them.

## The idea in one sentence

A WhatsApp-native AI operating system for Indian small shopkeepers that captures every order (vendor and customer, text or Hindi voice) with zero typing, builds the shop's books automatically, and lets the owner ask their business anything in plain Hindi.

## The customer

Indian SMB owners — starting with kirana (neighbourhood grocery) and similar small shops. Profile the founder gives:

- Takes dozens of orders a day: raw material *from* vendors, goods *to* customers.
- Roughly half those orders come by phone call, half on WhatsApp (text and voice).
- udhaar (informal monthly credit) is tracked in a paper diary; stock lives in the owner's head.
- No ERP, no CRM, no ops tool — "there never was."
- A real kirana owner reportedly asked for exactly this, unprompted: "So many people call to order; keeping track of it all is hard."

## What it does (four steps)

1. **Listen** — vendor and customer orders, by phone call or WhatsApp (text + Hindi voice). No new number, no new app.
2. **Understand** — each message becomes a structured order (item, quantity, amount, delivery, payment terms); the owner confirms before anything is logged.
3. **Remember** — each customer's khata (what they ordered, what they owe) and the shop's stock are kept automatically; the owner never types.
4. **Answer** — the owner asks in Hindi ("today's sales?", "who still owes me?", "how much sugar to re-order?") and gets instant answers from real captured data; can also tell it to act ("order 15kg from Sharma") for a one-tap confirm.

## The underlying model

"Everything is an order with a direction." PURCHASE (vendor -> you) adds stock and a payable; SALE (customer -> you) removes stock and creates a receivable. Current stock, the khata, and buying patterns are all *computed* from these two streams — so (the founder claims) there is no separate inventory tool to build.

## What is real today vs. claimed/future

- **Live now:** the capture loop — message -> understand -> confirm card on WhatsApp -> owner taps Confirm -> order logged to the khata. Ran end-to-end against the Meta WhatsApp Cloud API, GPT-4o + Whisper, and a live database. Multi-item orders, voice, confirm-before-act all demonstrated.
- **Not yet built:** the conversational "ask your business anything" assistant (the headline feature), call-recording ingestion, derived stock, semantic recall, and any dashboard.
- **Known blocker:** Meta Business Verification is required to move from dev mode to Live mode before real inbound webhooks and proactive template messages work on a real phone at scale.

## Why the founder thinks nobody has won this

- Ledger apps (Khatabook, OkCredit): 50M+ installs but accounts go stale within weeks because they make the shopkeeper *type* every entry by hand.
- New AI call-bots: they *replace* the shopkeeper on the call, but trade is a relationship (the customer trusts the person), and bots demand instant UPI while this business runs on monthly udhaar.
- BusinessOS's claimed third way: keep the human, remove the work — capture how they already talk, build the books automatically.

## The claimed moat

"The models are rented; the memory is owned." The compounding, hard-to-copy asset is each business's accumulated memory: every vendor and customer, every order and balance, the shop's normalized list of what it buys and sells, the owner's way of speaking. After six months, leaving means losing all of it.

## Business model

Operations layer free (acquisition). Monetize the financial flow: fee on udhaar recovered (collections), interest spread via NBFC partner on working-capital lending underwritten by real order history (credit), transaction take-rate on the verified buyer-supplier network.

## The ask

$2M seed, 18 months. Goal stated as turning a live product into a daily habit: shops that open BusinessOS every morning to run their day (retention, not installs). Use of funds ~60/40: AI & voice/call accuracy, and in-person go-to-market one cluster at a time.

## Open numbers the founder has NOT provided (do not invent them)

- Price / expected revenue per shop, and when any revenue begins.
- Cost to acquire a shop, and cost to serve one (AI/API cost per shop per month).
- Market size (how many target shops, how dense a "cluster" is).
- Any pilot retention or usage data — there are no paying or active shops yet; the DB was wiped and a fresh business must be onboarded.
- Who the team is.
